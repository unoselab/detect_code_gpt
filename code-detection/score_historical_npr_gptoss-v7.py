#!/usr/bin/env python3
"""B01 v7: deferred-synchronization pipelining probe for GPT-OSS historical NPR.

WHY THIS EXISTS
---------------
v6's MODE=profile measured, on real hardware, that the forward pass is ~90% of
runtime while rank extraction is ~3%, so no rank-side optimization can approach
the conference budget. Its device-stage diagnostic then measured that the busiest
GPU is active only a fraction of wall-clock time:

    r158 (3x A6000):        max_single_device_active_fraction = 0.346  (ceiling 2.888x)
    173  (2x RTX 6000 Ada): max_single_device_active_fraction = 0.491  (ceiling 2.037x)

device_map splits the decoder layers across GPUs, so a single B=1 sequence walks
GPU0 -> GPU1 (-> GPU2) and each device idles while the others compute. That idle
time is a scheduling artifact, not a compute floor.

WHAT V7 CHANGES (AND WHAT IT DELIBERATELY DOES NOT)
---------------------------------------------------
v7 does NOT batch. v4 established that giving GPT-OSS a batch dimension > 1
changes the numerical result, and that finding stands: every sequence here is
still evaluated with its own B=1 forward, in the same shape, with the same ops,
in the same order as v6's BatchedRankEngine.

The ONLY change is WHEN results are copied back to the host. v6 calls .item()
(and several validation/statistics .item()s) after every sequence, which blocks
the CPU until that sequence's GPU work has fully drained -- so the next
sequence's first-stage work cannot start on GPU0 while the previous sequence is
still finishing on GPU1. v7 keeps up to `pipeline_depth` sequences' scalar
results as GPU tensors, issuing their forwards back to back, and synchronizes
once per group. CUDA can then overlap independent per-device queues.

Deferred does NOT mean skipped. The non-finite-logits guard and the tie
statistics that v6 evaluates inline are still evaluated for every sequence --
they are accumulated as device tensors and asserted at flush time, before any
value is returned to the caller.

Because the arithmetic is unchanged, v7 must reproduce v6 EXACTLY, not merely
within a tolerance. MODE=pipeline_profile enforces exact integer/float equality
of all 51 per-window components against v6's own BatchedRankEngine, and any
depth that fails is discarded and never recommended.

SCOPE OF THIS VERSION -- READ THIS BEFORE ASKING FOR A PRODUCTION RUN
---------------------------------------------------------------------
This version implements ONE mode: pipeline_profile. It is the cheap, decisive
experiment that answers "does deferring host synchronization actually buy
overlap on this hardware, at identical numbers?" It grants no approval, writes
no production checkpoint, and applies no threshold (tau=1.545529 remains
downstream, as in every B01 stage).

If -- and only if -- a depth is both EXACT and meaningfully faster, the next
version adds the 25-window validate / 128-window benchmark / gated run stages,
in that order, exactly as v5 and v6 did. Do not skip ahead.

v6 is imported as a frozen dependency rather than copied, so the ~2500 lines of
already-validated loading, sampling, provenance and aggregation code are reused
verbatim; its SHA-256 is pinned and recorded.

Versioned delivery filename:
    code-detection/score_historical_npr_gptoss-v7.py
"""

from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import math
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

SCRIPT_VERSION = "run-x-b01-v7"
DEFAULT_V6_SCRIPT = Path("code-detection/score_historical_npr_gptoss.py")
# The v6 build whose measurements this experiment builds on, and whose engine is
# the equivalence reference here. Override with --expected-v6-sha256 "" only if
# v6 is intentionally revised; the recorded value always goes into the outputs.
EXPECTED_V6_SHA256 = "321ca3331bc2e8f3c5a8cb5feff86a8722053aec636a50c9a433a64c0e3f7485"


def load_v6(path: Path, expected_sha: str) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Missing v6 engine module: {path}")
    spec = importlib.util.spec_from_file_location("run_x_b01_v6_engine", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import v6 engine module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    actual = module.sha256_file(path)
    if expected_sha and actual != expected_sha:
        raise RuntimeError(
            "v6 engine SHA-256 changed; v7 compares against a specific v6 build.\n"
            f"  expected={expected_sha}\n  actual  ={actual}\n"
            "Re-run the v6 profile and update EXPECTED_V6_SHA256, or pass "
            "--expected-v6-sha256 '' to proceed deliberately."
        )
    return module


class DeferredEquivalenceError(RuntimeError):
    """A pipelined result did not reproduce v6's sequential result exactly."""


# --------------------------------------------------------------------------
# Deferred-synchronization rank extraction.
#
# Each function below computes the SAME integer ranks as its v6 counterpart on
# the same logits. The difference is that nothing is copied to the host: the
# non-finite guard and the tie statistics are returned as device tensors so the
# caller can assert them after several sequences have been issued.
# --------------------------------------------------------------------------


def deferred_count_priority_ranks(
    logits: Any, labels: Any, torch: Any, tile_tokens: int, rule: str,
    priority_cache: dict[str, Any], v6: Any,
) -> tuple[Any, dict[str, Any]]:
    """Device-only equivalent of v6.count_priority_rank_vector.

    rank = #(logit > observed) + #(equal-logit tokens ordered before the observed
    token by the profiled tie precedence) + 1 -- identical arithmetic, identical
    tiling, identical dtypes. Only the .item() calls v6 makes for its guard and
    its tie counters are replaced by tensors the caller checks at flush time.
    """
    n = int(labels.numel())
    if n == 0:
        empty = torch.empty(0, dtype=torch.int64, device=logits.device)
        return empty, {"finite": torch.ones((), dtype=torch.bool, device=logits.device),
                       "tie_positions": torch.zeros((), dtype=torch.int64, device=logits.device),
                       "max_tie_group": torch.ones((), dtype=torch.int64, device=logits.device),
                       "ranked_tokens": 0}
    vocab = int(logits.shape[-1])
    priority = v6.tie_priority_vector(vocab, rule, logits, torch, priority_cache)
    out = []
    finite = torch.ones((), dtype=torch.bool, device=logits.device)
    tie_positions = torch.zeros((), dtype=torch.int64, device=logits.device)
    max_tie_group = torch.ones((), dtype=torch.int64, device=logits.device)
    for start in range(0, n, tile_tokens):
        values = logits[:, start:start + tile_tokens, :]
        target = labels[:, start:start + tile_tokens].unsqueeze(-1)
        finite = finite & torch.isfinite(values).all()
        observed = values.gather(-1, target)
        equal = values == observed
        equal_counts = equal.sum(-1)
        tie_positions = tie_positions + (equal_counts > 1).sum().to(torch.int64)
        max_tie_group = torch.maximum(max_tie_group, equal_counts.max().to(torch.int64))
        target_priority = priority[labels[:, start:start + tile_tokens]].unsqueeze(-1)
        before = equal & (priority.view(1, 1, -1) < target_priority)
        rank = (values > observed).sum(-1) + before.sum(-1) + 1
        out.append(rank.reshape(-1).to(torch.int64))
    return torch.cat(out), {"finite": finite, "tie_positions": tie_positions,
                            "max_tie_group": max_tie_group, "ranked_tokens": n}


def deferred_argsort_ranks(logits: Any, labels: Any, torch: Any) -> tuple[Any, dict[str, Any]]:
    """Device-only equivalent of v6.reference_rank_vector.

    v6 locates the observed token in the descending argsort with .nonzero(),
    whose output shape is data dependent, so reading it forces a host sync. Each
    timestep has exactly one match (v6 asserts this), so the position of that
    single match is recovered here with argmax over the one-hot comparison --
    the same integer, without the sync. The exactness of this substitution is
    not assumed: MODE=pipeline_profile compares every rank against v6.
    """
    order = logits.argsort(-1, descending=True)
    hit = order == labels.unsqueeze(-1)
    # Exactly one True per row; argmax returns its index. matches_per_row is kept
    # so the flush can assert the one-match invariant v6 asserts inline.
    position = hit.to(torch.int64).argmax(-1)
    matches_per_row = hit.sum(-1)
    ranks = (position + 1).reshape(-1)
    stats = {
        "finite": torch.isfinite(logits).all(),
        "one_match": (matches_per_row == 1).all(),
        "ranked_tokens": int(labels.numel()),
    }
    return ranks, stats


class PipelinedRankEngine:
    """Issues up to `pipeline_depth` B=1 forwards before any host synchronization.

    Every sequence still gets its own forward with batch dimension 1, the same
    padding-free single-item input v6 builds, and the same rank arithmetic. The
    engine holds only small per-sequence scalars between flushes -- logits are
    consumed into ranks immediately, so deferring costs a bounded amount of
    memory, not a bounded number of live logit tensors.
    """

    def __init__(self, runtime: Any, config: dict[str, Any], v6: Any, pipeline_depth: int):
        if int(config.get("batch_size", 1)) != 1:
            raise ValueError("v7 pipelines B=1 forwards only; batching is out of scope")
        self.runtime, self.config, self.v6 = runtime, dict(config), v6
        self.pipeline_depth = max(1, int(pipeline_depth))
        self.priority_cache: dict[str, Any] = {}
        self.stats: dict[str, Any] = {
            "sequences": 0, "forwards": 0, "flushes": 0, "host_syncs": 0,
            "ranked_tokens": 0, "observed_token_ties": 0, "max_observed_tie_group": 1,
            "real_input_tokens": 0, "deepest_group": 0,
        }

    def _issue(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """Queue one B=1 forward and its rank reduction; return device-side handles.

        Returns None for a degenerate (<2 token) input, matching v6's NaN result.
        """
        torch = self.runtime.torch
        model = self.runtime.model_config["base_model"]
        length = int(item["length"])
        if length < 2:
            return None
        ids = item["input_ids"].to(self.runtime.args.DEVICE)
        mask = item["attention_mask"].to(self.runtime.args.DEVICE)
        kwargs = {"input_ids": ids, "attention_mask": mask}
        if self.config["use_cache"] == "false":
            kwargs["use_cache"] = False
        with torch.no_grad():
            output = model(**kwargs)
            logits = output.logits
            del output
            # Shape is static here, so this comparison costs no synchronization.
            if logits.ndim != 3 or tuple(logits.shape[:2]) != tuple(ids.shape):
                raise RuntimeError("Model must return all next-token logits, not logits_to_keep/top-k")
            labels = ids.to(logits.device)
            real_logits = logits[:, :length - 1, :]
            real_labels = labels[:, 1:length]
            backend = self.config["rank_backend"]
            if backend in self.v6.PROFILE_TIE_RULES:
                ranks, stats = deferred_count_priority_ranks(
                    real_logits, real_labels, torch, self.config["rank_tile_tokens"],
                    backend, self.priority_cache, self.v6,
                )
            elif backend == "argsort":
                ranks, stats = deferred_argsort_ranks(real_logits, real_labels, torch)
            else:
                raise RuntimeError(f"v7 supports argsort and exact tie rules only; got {backend}")
            value = torch.log(ranks.float()).float().mean()
            del logits, ranks
        self.stats["forwards"] += 1
        self.stats["real_input_tokens"] += length
        return {"value": value, "stats": stats}

    def _flush(self, pending: list[tuple[int, dict[str, Any] | None]], results: list[float]) -> None:
        """One host synchronization for the whole group, after all guards pass."""
        if not pending:
            return
        torch = self.runtime.torch
        live = [(index, handle) for index, handle in pending if handle is not None]
        self.stats["flushes"] += 1
        self.stats["deepest_group"] = max(self.stats["deepest_group"], len(pending))
        for index, handle in pending:
            if handle is None:
                results[index] = float("nan")
        if not live:
            return
        # Collapse the group's guards and statistics into single reads so a deep
        # group still costs a constant, small number of synchronizations.
        finite_all = live[0][1]["stats"]["finite"]
        tie_total = None
        tie_max = None
        one_match_all = None
        for _, handle in live:
            stats = handle["stats"]
            finite_all = finite_all & stats["finite"]
            if "one_match" in stats:
                one_match_all = stats["one_match"] if one_match_all is None else (one_match_all & stats["one_match"])
            if "tie_positions" in stats:
                tie_total = stats["tie_positions"] if tie_total is None else tie_total + stats["tie_positions"]
                tie_max = stats["max_tie_group"] if tie_max is None else torch.maximum(tie_max, stats["max_tie_group"])
        values = torch.stack([handle["value"] for _, handle in live])
        self.stats["host_syncs"] += 1
        if not bool(finite_all.item()):
            raise RuntimeError("Non-finite model logits in a pipelined group; refusing to assign a rank")
        if one_match_all is not None and not bool(one_match_all.item()):
            raise RuntimeError("Expected exactly one rank match per next-token label")
        if tie_total is not None:
            self.stats["observed_token_ties"] += int(tie_total.item())
            self.stats["max_observed_tie_group"] = max(
                self.stats["max_observed_tie_group"], int(tie_max.item()))
        for (index, handle), value in zip(live, values.tolist()):
            results[index] = float(value)
            self.stats["ranked_tokens"] += int(handle["stats"]["ranked_tokens"])
            self.stats["sequences"] += 1

    def score_items(self, items: Sequence[dict[str, Any]]) -> list[float]:
        results: list[float] = [float("nan")] * len(items)
        pending: list[tuple[int, dict[str, Any] | None]] = []
        for index, item in enumerate(items):
            pending.append((index, self._issue(item)))
            if len(pending) >= self.pipeline_depth:
                self._flush(pending, results)
                pending = []
        self._flush(pending, results)
        return results


def pipelined_window(record: dict[str, Any], a02: Any, engine: PipelinedRankEngine, v6: Any) -> dict[str, Any]:
    """Mirror of v6.optimized_window with pipelined scoring.

    Seeding, the tokenizer call, the original/perturbation split, the
    context-limit exclusion and every reported field follow v6 exactly; only the
    scoring call differs. MODE=pipeline_profile checks the resulting fields
    against v6's own optimized_window on the same records.
    """
    runtime, torch = engine.runtime, engine.runtime.torch
    a02.set_all_seeds(int(record["window_seed"]), torch)
    v6.synchronize(torch)
    started = time.perf_counter()
    items = v6.encode_exact_texts(runtime.model_config["base_tokenizer"],
                                  [record["original_text"]] + record["perturbations"], torch)
    lengths = [x["length"] for x in items]
    limit = runtime.reported_model_context_limit
    base = {
        "original_llm_token_count": lengths[0], "expected_perturbations": 50,
        "perturbed_llm_token_count_min": min(lengths[1:]),
        "perturbed_llm_token_count_mean": sum(lengths[1:]) / 50,
        "perturbed_llm_token_count_max": max(lengths[1:]),
        "scoring_error_type": None, "scoring_error_message": None,
        "deterministic_exclusion_reason": None,
    }
    if limit is not None and lengths[0] > limit:
        base.update(original_log_rank=None, mean_perturbed_log_rank=None, window_npr=None,
                    valid_perturbation_scores=0,
                    deterministic_exclusion_reason="model_context_exceeded",
                    _component_log_ranks=[], _input_lengths=lengths)
    else:
        # The original and the 50 perturbations are pipelined together; the
        # original still gets its own B=1 forward, exactly as in v6.
        scored = engine.score_items(items)
        original, perturbed = scored[0], scored[1:]
        finite = [float(x) for x in perturbed if a02.sanitize_float(x) is not None]
        mean = sum(finite) / len(finite) if finite else None
        value = mean / original if mean is not None and a02.sanitize_float(original) not in (None, 0.0) else None
        base.update(original_log_rank=a02.sanitize_float(original),
                    mean_perturbed_log_rank=mean, window_npr=value,
                    valid_perturbation_scores=len(finite),
                    _component_log_ranks=[a02.sanitize_float(x) for x in scored],
                    _input_lengths=lengths)
    v6.synchronize(torch)
    base["scoring_seconds"] = time.perf_counter() - started
    return base


def compare_exact(reference: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    """Exact comparison. v7 changes no arithmetic, so equality is the bar.

    A tolerance is deliberately not offered here: any drift means the deferred
    path is not the computation v6 performs, and a depth that drifts is dropped
    rather than accommodated.
    """
    fields = ("original_log_rank", "mean_perturbed_log_rank", "window_npr",
              "valid_perturbation_scores", "original_llm_token_count",
              "deterministic_exclusion_reason")
    mismatches = []
    worst = 0.0
    for field in fields:
        ref, new = reference.get(field), observed.get(field)
        if ref != new:
            mismatches.append({"field": field, "reference": ref, "observed": new})
            if isinstance(ref, (int, float)) and isinstance(new, (int, float)):
                worst = max(worst, abs(float(ref) - float(new)))
    ref_components = reference.get("_component_log_ranks", [])
    new_components = observed.get("_component_log_ranks", [])
    if len(ref_components) != len(new_components):
        mismatches.append({"field": "component_count", "reference": len(ref_components),
                           "observed": len(new_components)})
    else:
        for i, (ref, new) in enumerate(zip(ref_components, new_components)):
            if ref != new:
                label = "original_component" if i == 0 else f"perturbation_{i:02d}"
                mismatches.append({"field": label, "reference": ref, "observed": new})
                if ref is not None and new is not None:
                    worst = max(worst, abs(float(ref) - float(new)))
    if reference.get("_input_lengths") != observed.get("_input_lengths"):
        mismatches.append({"field": "all_51_tokenized_lengths",
                           "reference": str(reference.get("_input_lengths")),
                           "observed": str(observed.get("_input_lengths"))})
    return {"exact": not mismatches, "mismatches": mismatches,
            "max_abs_difference": worst, "compared_components": len(ref_components)}


def build_v6_args(args: argparse.Namespace, v6: Any) -> SimpleNamespace:
    """The attribute surface v6's reusable helpers read."""
    return SimpleNamespace(
        a02_script=args.a02_script, rank_script=args.rank_script, a09_root=args.a09_root,
        reference_db=args.reference_db, scope=args.scope, shard_ids=args.shard_ids,
        scoring_model=args.scoring_model, model_revision=args.model_revision,
        expected_model_revision=args.expected_model_revision, model_cache_dir=args.model_cache_dir,
        device=args.device, two_gpu_max_memory=args.two_gpu_max_memory,
        per_gpu_max_memory=args.per_gpu_max_memory, cpu_max_memory=args.cpu_max_memory,
        allow_unsupported_gpu_topology=args.allow_unsupported_gpu_topology,
        validation_windows=args.profile_windows,
    )


def execute_pipeline_profile(args: argparse.Namespace, v6: Any) -> int:
    v6_args = build_v6_args(args, v6)
    plan, a02, _ = v6.preflight_inputs(v6_args)
    expected_windows = sum(u["n_expected_windows"] for u in plan.values())
    legacy_rows, _ = v6.read_v2_reference(v6_args)
    keys = list(legacy_rows)[:args.profile_windows]
    roles = {key: "v2-reference" for key in keys}
    audited = sorted({plan[k[0]]["logical_shard"] for k in roles})
    audit = v6.validate_a09_shards(args.a09_root, audited, v6.EXPECTED_A09_CONFIG_FINGERPRINT)
    if any(r["status"] != "PASS" for r in audit):
        raise RuntimeError("A09 shard integrity verification failed")
    records = v6.fetch_sample_records(v6_args, plan, roles)
    print(f"Preflight: universe_windows={expected_windows}, sample_windows={len(records)}, "
          f"unique_units={len({r['code_unit_sha256'] for r in records})}", flush=True)

    runtime = v6.load_gptoss_runtime(v6_args)
    signature = v6.runtime_signature(v6_args, runtime)

    # How many pipeline stages device_map actually created. A depth below this
    # cannot fill the pipeline: with S stages, only min(depth, S) devices can be
    # busy at once, so depth < S bounds the achievable overlap regardless of how
    # much idle time the v6 diagnostic measured.
    stage_devices = sorted({d for d in (runtime.device_map or {}).values() if isinstance(d, int)})
    pipeline_stages = len(stage_devices)
    print(f"Pipeline stages from device_map: {pipeline_stages} (devices={stage_devices})", flush=True)
    if pipeline_stages > 1 and max(args.depths) < pipeline_stages:
        print(f"WARNING: deepest requested depth {max(args.depths)} < {pipeline_stages} stages; "
              "the pipeline cannot be filled at any tested depth", flush=True)

    backend = args.rank_backend
    if backend == "auto":
        profile = v6.load_json(args.v6_profile_summary)
        backend = profile.get("recommended_tie_rule")
        if not profile.get("optimization_candidate_available") or backend not in v6.PROFILE_TIE_RULES:
            raise RuntimeError("v6 profile found no exact tie rule; run v6 MODE=profile first")
        print(f"Resolved rank backend from v6 profile: {backend}", flush=True)
    config = {"batch_size": 1, "max_batch_tokens": args.max_batch_tokens, "rank_backend": backend,
              "rank_tile_tokens": args.rank_tile_tokens, "use_cache": args.use_cache,
              "oom_policy": "abort", "optimization_version": "deferred_sync_pipeline-v1"}

    # Baseline: v6's own engine, unchanged, on the same records. This is both the
    # equivalence reference and the speedup denominator.
    baseline_engine = v6.BatchedRankEngine(runtime, config)
    v6.optimized_window(records[0], a02, baseline_engine)  # warm up outside timing
    baseline: list[dict[str, Any]] = []
    v6.synchronize(runtime.torch)
    baseline_started = time.perf_counter()
    for record in records:
        baseline.append(v6.optimized_window(record, a02, baseline_engine))
    v6.synchronize(runtime.torch)
    baseline_seconds = time.perf_counter() - baseline_started
    baseline_rate = len(records) / baseline_seconds if baseline_seconds else 0.0
    print(f"baseline(v6 BatchedRankEngine) windows={len(records)} seconds={baseline_seconds:.3f} "
          f"rate={baseline_rate:.6f} windows/s", flush=True)

    candidates: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    for depth in args.depths:
        engine = PipelinedRankEngine(runtime, config, v6, depth)
        entry: dict[str, Any] = {"pipeline_depth": depth, "rank_backend": backend}
        try:
            v6.empty_cuda_cache(runtime.torch)
            # Peak memory is per depth: a deeper group keeps more forwards in
            # flight, so its transient allocation is what we want reported.
            for index in range(runtime.torch.cuda.device_count()):
                runtime.torch.cuda.reset_peak_memory_stats(index)
            pipelined: list[dict[str, Any]] = []
            v6.synchronize(runtime.torch)
            started = time.perf_counter()
            for record in records:
                pipelined.append(pipelined_window(record, a02, engine, v6))
            v6.synchronize(runtime.torch)
            seconds = time.perf_counter() - started
            exact = True
            worst = 0.0
            for record, ref, new in zip(records, baseline, pipelined):
                result = compare_exact(ref, new)
                exact = exact and result["exact"]
                worst = max(worst, result["max_abs_difference"])
                for mismatch in result["mismatches"]:
                    comparison_rows.append({
                        "pipeline_depth": depth, "code_unit_sha256": record["code_unit_sha256"],
                        "window_index": int(record["window_index"]), **mismatch})
            rate = len(records) / seconds if seconds else 0.0
            entry.update(
                status="EXACT" if exact else "MISMATCH",
                seconds=seconds, windows_per_second=rate,
                speedup=(rate / baseline_rate) if baseline_rate else None,
                max_abs_difference=worst,
                projected_days=(expected_windows / rate / 86400) if rate else None,
                host_syncs=engine.stats["host_syncs"], flushes=engine.stats["flushes"],
                forwards=engine.stats["forwards"], deepest_group=engine.stats["deepest_group"],
                fills_pipeline=depth >= pipeline_stages,
                # Per device, not just the maximum: with three stages the binding
                # constraint may be the device holding lm_head rather than the
                # first stage, and a deeper group inflates only some of them.
                peak_allocated_gib_per_device=[
                    round(runtime.torch.cuda.max_memory_allocated(i) / 1024 ** 3, 3)
                    for i in range(runtime.torch.cuda.device_count())],
                peak_allocated_gib=max(
                    (runtime.torch.cuda.max_memory_allocated(i) / 1024 ** 3
                     for i in range(runtime.torch.cuda.device_count())), default=None),
            )
        except Exception as error:  # OOM at one depth must not lose the shallower results
            entry.update(status="ERROR", error=f"{type(error).__name__}: {error}",
                         seconds=None, windows_per_second=None, speedup=None,
                         max_abs_difference=None, projected_days=None)
        candidates.append(entry)
        print(f"depth={depth} status={entry['status']} "
              f"rate={entry.get('windows_per_second')} speedup={entry.get('speedup')} "
              f"projected_days={entry.get('projected_days')}", flush=True)

    usable = [c for c in candidates if c["status"] == "EXACT" and (c["speedup"] or 0) > 0]
    best = max(usable, key=lambda c: c["speedup"]) if usable else None
    meets_hard = bool(best and best["projected_days"] is not None
                      and best["projected_days"] <= args.max_production_days)
    meets_preferred = bool(best and best["projected_days"] is not None
                           and best["projected_days"] <= args.preferred_production_days)
    if best is None:
        next_step = "no_exact_pipeline_depth"
        note = ("No pipeline depth reproduced v6 exactly. Deferring synchronization must not "
                "change results; investigate the mismatching components before going further.")
    elif best["pipeline_depth"] == 1 or (best["speedup"] or 0) < args.minimum_useful_speedup:
        tested_filling = [c for c in candidates if c["status"] == "EXACT" and c.get("fills_pipeline")]
        if not tested_filling:
            next_step = "retry_with_deeper_pipeline"
            note = (f"No exact depth reached the {pipeline_stages} pipeline stages this device_map "
                    f"created, so the pipeline was never full. Re-run with depths >= {pipeline_stages} "
                    "before concluding that deferral does not help.")
        else:
            next_step = "pipelining_ineffective"
            note = (f"Best exact depth={best['pipeline_depth']} gives only "
                    f"{best['speedup']:.3f}x, below the {args.minimum_useful_speedup}x worth pursuing, "
                    f"even at depths that fill all {pipeline_stages} stages. Host-side deferral is not "
                    "what is serializing this hardware; re-examine the device-stage diagnostic before "
                    "building the validate/benchmark stages.")
    else:
        next_step = "build_pipeline_validate"
        note = (f"Depth={best['pipeline_depth']} is exact at {best['speedup']:.3f}x "
                f"({best['projected_days']:.2f} days projected). The 25-window validate and "
                "128-window benchmark stages are the next gates; production stays HOLD.")

    payload = {
        "status": "PASS",
        "stage": "pipeline_profile",
        "script_version": SCRIPT_VERSION,
        "completed_utc": v6.utc_now(),
        "v7_script_sha256": v6.sha256_file(Path(__file__).resolve()),
        "v6_script_sha256": v6.sha256_file(args.v6_script),
        "runtime_signature": signature,
        "system_label": args.system_label,
        "rank_backend": backend,
        "pipeline_stages": pipeline_stages,
        "pipeline_stage_devices": stage_devices,
        "depths_filling_pipeline": [d for d in args.depths if d >= pipeline_stages],
        "sample_windows": len(records),
        "sample_unique_units": len({r["code_unit_sha256"] for r in records}),
        "expected_production_windows": expected_windows,
        "baseline_seconds": baseline_seconds,
        "baseline_windows_per_second": baseline_rate,
        "baseline_projected_days": (expected_windows / baseline_rate / 86400) if baseline_rate else None,
        "candidates": candidates,
        "recommended_pipeline_depth": best["pipeline_depth"] if best else None,
        "recommended_speedup": best["speedup"] if best else None,
        "recommended_projected_days": best["projected_days"] if best else None,
        "meets_hard_production_budget": meets_hard,
        "meets_preferred_production_budget": meets_preferred,
        "preferred_production_days": args.preferred_production_days,
        "max_production_days": args.max_production_days,
        "production_ready": False,
        "next_step": next_step,
        "note": note,
        "scope_note": ("v7 pipelines B=1 forwards by deferring host synchronization. No batching, "
                       "no changed arithmetic, no threshold. A sample PASS is not proof of equality "
                       "on every future window."),
        "classification_applied": False,
    }
    v6.atomic_json(payload, args.output_dir / "pipeline_profile_summary.json")
    v6.atomic_json(payload, args.output_dir / "summary.json")
    v6.atomic_csv(candidates, args.output_dir / "pipeline_depth_candidates.csv",
                  ["pipeline_depth", "rank_backend", "status", "fills_pipeline", "seconds",
                   "windows_per_second", "speedup", "projected_days", "max_abs_difference",
                   "host_syncs", "flushes", "forwards", "deepest_group", "peak_allocated_gib",
                   "peak_allocated_gib_per_device", "error"])
    if comparison_rows:
        v6.atomic_csv(comparison_rows, args.output_dir / "pipeline_mismatches.csv",
                      ["pipeline_depth", "code_unit_sha256", "window_index", "field",
                       "reference", "observed"])
    print(f"PIPELINE baseline={baseline_rate:.6f} windows/s "
          f"({payload['baseline_projected_days']:.2f} days)", flush=True)
    print(f"PIPELINE recommended_depth={payload['recommended_pipeline_depth']} "
          f"speedup={payload['recommended_speedup']} "
          f"projected_days={payload['recommended_projected_days']}", flush=True)
    print(f"PIPELINE next_step={next_step}", flush=True)
    print(f"PIPELINE note: {note}", flush=True)
    return 0


def self_test(v6: Any) -> None:
    """CPU-only structural checks. This is NOT a GPU equivalence certification."""
    import torch
    torch.manual_seed(20260723)
    for dtype in (torch.float32, torch.bfloat16):
        for length in (1, 7, 33):
            # Integer-valued logits deliberately create abundant exact ties.
            logits = torch.randint(-4, 5, (1, length, 29)).to(dtype)
            labels = torch.randint(0, 29, (1, length))
            expected = v6.reference_rank_vector(logits, labels, torch)
            got, stats = deferred_argsort_ranks(logits, labels, torch)
            if not torch.equal(expected, got):
                raise AssertionError("Deferred argsort ranks differ from v6")
            if not bool(stats["one_match"].item()) or not bool(stats["finite"].item()):
                raise AssertionError("Deferred argsort guards misreported a valid input")
            for rule in ("count-index-asc", "count-priority"):
                cache: dict[str, Any] = {}
                reference = v6.count_priority_rank_vector(logits, labels, torch, 4, rule, dict(cache), {})
                observed, tie_stats = deferred_count_priority_ranks(
                    logits, labels, torch, 4, rule, dict(cache), v6)
                if not torch.equal(reference, observed):
                    raise AssertionError(f"Deferred {rule} ranks differ from v6")
                if not bool(tie_stats["finite"].item()):
                    raise AssertionError("Deferred tie guard misreported a finite input")
    identical = {"original_log_rank": 1.0, "_component_log_ranks": [1.0, 2.0], "_input_lengths": [3, 4]}
    if not compare_exact(identical, dict(identical))["exact"]:
        raise AssertionError("Exact comparison rejected identical results")
    drifted = dict(identical, _component_log_ranks=[1.0, 2.0 + 1e-12])
    if compare_exact(identical, drifted)["exact"]:
        raise AssertionError("Exact comparison accepted a drifted component")
    print("B01-v7 CPU deferred-rank/comparison self-test: PASS (GPU profiling still required)")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="B01-v7: deferred-synchronization pipelining probe for GPT-OSS historical NPR")
    p.add_argument("--mode", choices=("pipeline_profile",), default="pipeline_profile")
    p.add_argument("--project-root", type=Path, default=Path.cwd())
    p.add_argument("--v6-script", type=Path, default=DEFAULT_V6_SCRIPT)
    p.add_argument("--expected-v6-sha256", default=EXPECTED_V6_SHA256)
    p.add_argument("--v6-profile-summary", type=Path,
                   default=Path("output/snapshot_npr/run-x-b01/v6/profile/profile_summary.json"))
    p.add_argument("--a02-script", type=Path, default=Path("code-detection/score_snapshot_npr.py"))
    p.add_argument("--rank-script", type=Path, default=Path("code-detection/baselines/rank.py"))
    p.add_argument("--a09-root", type=Path, default=Path("output/snapshot_npr/run-x-a09"))
    p.add_argument("--reference-db", type=Path,
                   default=Path("output/snapshot_npr/run-x-b01/smoke/window_scores.sqlite3"))
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--scope", choices=("fun", "cfun", "all"), default="all")
    p.add_argument("--shard-ids", default="all")
    p.add_argument("--scoring-model", default="openai/gpt-oss-120b")
    p.add_argument("--model-revision", default="b5c939de8f754692c1647ca79fbf85e8c1e70f8a")
    p.add_argument("--expected-model-revision", default="b5c939de8f754692c1647ca79fbf85e8c1e70f8a")
    p.add_argument("--model-cache-dir", type=Path, default=Path("~/.cache/huggingface/hub").expanduser())
    p.add_argument("--device", default="cuda")
    p.add_argument("--two-gpu-max-memory", default="42GiB")
    p.add_argument("--per-gpu-max-memory", default="44GiB")
    p.add_argument("--cpu-max-memory", default="128GiB")
    p.add_argument("--system-label", default="unknown-host")
    p.add_argument("--allow-unsupported-gpu-topology", action="store_true")
    p.add_argument("--profile-windows", type=int, default=5)
    p.add_argument("--depths", default="1,2,4,8",
                   help="In-flight B=1 sequences per host synchronization; 1 reproduces v6's cadence")
    p.add_argument("--rank-backend", choices=("auto", "count-priority", "count-index-asc", "argsort"),
                   default="auto")
    p.add_argument("--rank-tile-tokens", type=int, default=32)
    p.add_argument("--max-batch-tokens", type=int, default=2048)
    p.add_argument("--use-cache", choices=("false", "model-default"), default="false")
    p.add_argument("--minimum-useful-speedup", type=float, default=1.15)
    p.add_argument("--preferred-production-days", type=float, default=5.0)
    p.add_argument("--max-production-days", type=float, default=7.0)
    p.add_argument("--self-test-only", action="store_true")
    args = p.parse_args()
    try:
        args.depths = list(dict.fromkeys(int(x.strip()) for x in args.depths.split(",")))
    except ValueError:
        p.error("depths must be comma-separated integers")
    if not args.depths or any(d < 1 for d in args.depths):
        p.error("depths must all be >= 1")
    if args.profile_windows < 1:
        p.error("profile-windows must be positive")
    if args.rank_tile_tokens < 1:
        p.error("rank-tile-tokens must be positive")
    return args


def acquire_lock(output_dir: Path) -> Any:
    output_dir.mkdir(parents=True, exist_ok=True)
    lock = (output_dir / ".b01_v7.lock").open("a")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise RuntimeError(f"Another B01-v7 process owns output directory {output_dir}") from None
    return lock


def main() -> int:
    args = parse_args()
    args.project_root = args.project_root.expanduser().resolve()

    def resolve(path: Path) -> Path:
        path = path.expanduser()
        return path.resolve() if path.is_absolute() else (args.project_root / path).resolve()

    for field in ("v6_script", "v6_profile_summary", "a02_script", "rank_script", "a09_root",
                  "reference_db", "output_dir", "model_cache_dir"):
        setattr(args, field, resolve(getattr(args, field)))
    v6 = load_v6(args.v6_script, args.expected_v6_sha256)
    if args.self_test_only:
        self_test(v6)
        return 0
    # v7 never writes where v2's or v6's artifacts live.
    for protected in (args.reference_db.parent, args.a09_root):
        if args.output_dir == protected or protected in args.output_dir.parents:
            raise RuntimeError(f"Refusing to write inside a read-only input directory: {protected}")
    lock = acquire_lock(args.output_dir)
    started = time.perf_counter()
    try:
        self_test(v6)
        result = execute_pipeline_profile(args, v6)
        print(f"{SCRIPT_VERSION}: mode={args.mode} wall_seconds={time.perf_counter()-started:.3f} "
              f"exit_code={result}")
        return result
    except BaseException as error:
        payload = {"status": "INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "FAIL",
                   "mode": args.mode, "script_version": SCRIPT_VERSION, "production_ready": False,
                   "error_type": type(error).__name__, "error": str(error), "utc": v6.utc_now()}
        v6.atomic_json(payload, args.output_dir / "last_error.json")
        v6.atomic_json(payload, args.output_dir / "summary.json")
        raise
    finally:
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
