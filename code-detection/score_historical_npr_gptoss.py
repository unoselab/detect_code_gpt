#!/usr/bin/env python3
"""Score historical Python procedure windows with GPT-OSS-120B NPR.

run-x-b01 replaces the historical StarCoder2-7B NPR scoring stage while preserving
its measurement semantics:

* A09's frozen 128 literal-space-token windows are reused exactly.
* A09's ordered 50 perturbations per window are reused exactly; they are never
  regenerated during production scoring.
* Window NPR is mean perturbed log-rank divided by original log-rank.
* Procedure NPR uses the frozen valid-frontier marginal-coverage weighting from A02.
* No HWC/AGC classification or thresholding occurs in this stage.

The selected historical universe is the union of A09 FUN and C_FUN memberships.
This is important because downstream longitudinal analysis uses regular functions,
class methods, and their joint RF+CM scope. FUN/C_FUN overlap content is scored once
and retained with both memberships.

This script is intentionally standalone with respect to previous shell wrappers. It
reuses the frozen A02 Python measurement helpers and the existing DetectCodeGPT rank
implementation, but loads GPT-OSS-120B directly so the new experiment does not depend
on the old StarCoder-specific one-GPU A11/A14 runtime guards.

V5 execution changes and safety gates
-------------------------------------
- MODE=validate compares the existing v2 smoke keys and all 51 scalar components
  against newly computed sequential rank.py references, then tests batch sizes.
- MODE=benchmark samples windows uniformly across the planned universe, plus
  separately reported stress cases. It repeats numerical comparisons and measures
  throughput without same-logits audit overhead. It does not score production.
- MODE=run requires a matching production_approval.json: >=100 uniform windows,
  passing numerical checks, and projected scoring time within the explicit budget.
- Outputs are isolated under run-x-b01/v5. The v2 checkpoint is read-only.
- Count-based ranks use the ORIGINAL full-sequence argsort on observed-token ties.
- BF16 batched logits can differ; no automatic tolerance relaxation is permitted.
- B01 still does not classify procedures or apply any downstream threshold.
- A sample PASS is not proof of equality on every future historical window.

Versioned delivery filename:
    code-detection/score_historical_npr_gptoss-v5.py
Canonical server filename after deployment:
    code-detection/score_historical_npr_gptoss.py
"""

from __future__ import annotations

import argparse
import gc
import random
import traceback
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Iterator, Sequence

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

SCRIPT_VERSION = "run-x-b01-v5"
SCORING_MODEL = "openai/gpt-oss-120b"
WINDOW_SIZE = 128
PERTURBATIONS_PER_WINDOW = 50
RANDOM_SEED = 20260723
PERTURBATION_TYPE = "random-insert-space+newline"
AGGREGATION_POLICY = "valid_frontier_space_by_token_weighting_with_component_retention"
WINDOW_POLICY = "128_space_by_tokens_final_full_window_shifted_backward_with_overlap"

EXPECTED_A02_SHA256 = "57e0781a406d992fb045335a79b1cb97e5c0557de9582603401f6d402ef528a0"
EXPECTED_A09_CONFIG_FINGERPRINT = "3f78c8c43aaa014cd0f5e1a5d1c2df7d4269deb55c4c999e4483d08a324dd9bb"
EXPECTED_A05_MANIFEST_SHA256 = "1acb3726f5c62e6154672f1aff592973c65a13e58dbfd37f8058560d1a474e6c"

EXPECTED_SCOPE_COUNTS = {
    "fun": {"units": 105_635, "windows": 307_600},
    "cfun": {"units": 195_193, "windows": 567_557},
    "all": {"units": 300_825, "windows": 875_154},
}
EXPECTED_OVERLAP_UNITS = 3
EXPECTED_OVERLAP_WINDOWS = 3

WINDOW_COLUMNS = [
    "scoring_fingerprint",
    "code_unit_sha256",
    "code_unit_relative_path",
    "code_unit_types",
    "unit_groups",
    "fun_membership",
    "cfun_membership",
    "logical_shard",
    "window_index",
    "window_space_by_start",
    "window_space_by_end",
    "window_space_by_token_count",
    "window_marginal_space_by_token_count",
    "window_aggregation_weight_space_by_tokens",
    "original_llm_token_count",
    "perturbed_llm_token_count_min",
    "perturbed_llm_token_count_mean",
    "perturbed_llm_token_count_max",
    "reported_model_context_limit",
    "original_log_rank",
    "mean_perturbed_log_rank",
    "window_npr",
    "window_npr_valid",
    "window_npr_invalid_reason",
    "expected_perturbations",
    "valid_perturbation_scores",
    "scoring_error_type",
    "scoring_error_message",
    "scoring_seconds",
]

UNIT_COLUMNS = [
    "scoring_fingerprint",
    "code_unit_sha256",
    "code_unit_relative_path",
    "code_unit_types",
    "unit_groups",
    "fun_membership",
    "cfun_membership",
    "logical_shard",
    "space_by_tokens_total",
    "n_expected_windows",
    "n_attempted_windows",
    "n_valid_npr_windows",
    "n_invalid_npr_windows",
    "space_by_tokens_scored",
    "npr_coverage_ratio",
    "original_llm_tokens_all_windows",
    "original_llm_tokens_valid_windows",
    "code_unit_npr_space_by_token_weighted",
    "code_unit_original_log_rank_weighted",
    "code_unit_mean_perturbed_log_rank_weighted",
    "code_unit_npr_pooled_components",
    "partial_code_unit_score",
    "status",
]

CHECK_COLUMNS = ["check_name", "passed", "observed", "expected", "note"]
FAILURE_COLUMNS = [
    "code_unit_sha256", "window_index", "logical_shard", "scoring_error_type",
    "scoring_error_message",
]
EXCLUSION_COLUMNS = [
    "code_unit_sha256", "window_index", "logical_shard", "window_npr_invalid_reason",
    "original_llm_token_count", "reported_model_context_limit", "original_log_rank",
    "valid_perturbation_scores",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def ordered_text_digest(texts: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for text in texts:
        encoded = text.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def atomic_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    temp.replace(path)


def atomic_csv(rows: Iterable[dict[str, Any]], path: Path, fieldnames: Sequence[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})
            count += 1
    temp.replace(path)
    return count


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    note: str = "",
) -> None:
    checks.append({
        "check_name": name,
        "passed": int(bool(passed)),
        "observed": observed,
        "expected": expected,
        "note": note,
    })


def parse_shard_ids(spec: str) -> set[int] | None:
    text = spec.strip().lower()
    if text in {"", "all"}:
        return None
    result: set[int] = set()
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            left, right = token.split("-", 1)
            start, end = int(left), int(right)
            if start > end:
                raise ValueError(f"Invalid shard range: {token}")
            result.update(range(start, end + 1))
        else:
            result.add(int(token))
    if not result:
        raise ValueError("No shard IDs selected")
    if min(result) < 0 or max(result) > 95:
        raise ValueError(f"Shard IDs must be in 0..95; got {sorted(result)}")
    return result


def split_groups(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    return {item.strip() for item in str(value or "").split(",") if item.strip()}


def scope_matches(groups: set[str], scope: str) -> bool:
    if scope == "fun":
        return "FUN" in groups
    if scope == "cfun":
        return "C_FUN" in groups
    return bool(groups & {"FUN", "C_FUN"})


def shard_paths(a09_root: Path, shard_id: int) -> tuple[Path, Path]:
    return (
        a09_root / "shards" / f"shard-{shard_id:03d}-of-096.jsonl.gz",
        a09_root / "shards" / f"shard-{shard_id:03d}-of-096.summary.json",
    )


def read_selected_unit_plan(
    path: Path,
    scope: str,
    selected_shards: set[int] | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "code_unit_sha256", "code_unit_relative_path", "space_by_token_count",
            "expected_windows", "code_unit_types", "unit_groups", "logical_shard",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"A09 unique unit plan missing columns: {sorted(missing)}")
        for row in reader:
            shard = int(row["logical_shard"])
            if selected_shards is not None and shard not in selected_shards:
                continue
            groups = split_groups(row["unit_groups"])
            if not scope_matches(groups, scope):
                continue
            sha = str(row["code_unit_sha256"])
            if sha in result:
                raise ValueError(f"Duplicate code-unit SHA in A09 plan: {sha}")
            result[sha] = {
                "code_unit_sha256": sha,
                "code_unit_relative_path": str(row["code_unit_relative_path"]),
                "space_by_tokens_total": int(row["space_by_token_count"]),
                "n_expected_windows": int(row["expected_windows"]),
                "code_unit_types": str(row["code_unit_types"]),
                "unit_groups": str(row["unit_groups"]),
                "fun_membership": int("FUN" in groups),
                "cfun_membership": int("C_FUN" in groups),
                "logical_shard": shard,
            }
    return result


def validate_a09_shards(
    a09_root: Path,
    shard_ids: Sequence[int],
    expected_fingerprint: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for shard_id in shard_ids:
        data_path, summary_path = shard_paths(a09_root, shard_id)
        errors: list[str] = []
        summary: dict[str, Any] = {}
        if not data_path.is_file():
            errors.append("missing_data_shard")
        if not summary_path.is_file():
            errors.append("missing_summary_shard")
        if not errors:
            summary = load_json(summary_path)
            if summary.get("status") != "PASS":
                errors.append("summary_status_not_PASS")
            if str(summary.get("config_fingerprint")) != expected_fingerprint:
                errors.append("config_fingerprint_mismatch")
            if int(summary.get("logical_shard", -1)) != shard_id:
                errors.append("logical_shard_mismatch")
            if data_path.stat().st_size != int(summary.get("gzip_bytes", -1)):
                errors.append("gzip_size_mismatch")
            if sha256_file(data_path) != str(summary.get("gzip_sha256")):
                errors.append("gzip_sha256_mismatch")
        rows.append({
            "logical_shard": shard_id,
            "data_path": str(data_path),
            "summary_path": str(summary_path),
            "status": "PASS" if not errors else "FAIL",
            "error_messages": ";".join(errors),
        })
    return rows


def iter_selected_records(
    path: Path,
    selected_shas: set[str],
) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            sha = str(record.get("code_unit_sha256", ""))
            if sha in selected_shas:
                yield record


@dataclass
class RuntimeBundle:
    args: Any
    model_config: dict[str, Any]
    torch: Any
    get_rank: Any
    get_ranks: Any
    model_load_seconds: float
    gpu_names: list[str]
    gpu_memory_gib: list[float]
    reported_model_context_limit: int | None
    model_revision: str
    device_map: dict[str, Any] | None


def positive_context_value(value: Any) -> int | None:
    try:
        numeric = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if numeric <= 0 or numeric >= 10**12:
        return None
    return numeric


def load_gptoss_runtime(args: argparse.Namespace) -> RuntimeBundle:
    import torch
    import transformers

    # Load the exact repository rank implementation whose SHA-256 is recorded in
    # B01 provenance. The repository layout places it under code-detection/baselines,
    # not at PROJECT_ROOT/baselines. Loading by absolute path also prevents an
    # unrelated installed package named "baselines" from shadowing this source.
    rank_module = load_module(args.rank_script, "run_x_b01_rank")
    get_rank = rank_module.get_rank
    get_ranks = rank_module.get_ranks

    if not torch.cuda.is_available():
        raise RuntimeError("GPT-OSS scoring requires CUDA; torch.cuda.is_available() is false")

    n_gpu = int(torch.cuda.device_count())
    gpu_names = [str(torch.cuda.get_device_name(i)) for i in range(n_gpu)]
    gpu_memory_gib = [float(torch.cuda.get_device_properties(i).total_memory / 1024**3) for i in range(n_gpu)]

    two_large_gpus = n_gpu == 2 and min(gpu_memory_gib) >= 47.0
    three_or_more = n_gpu >= 3
    if not (two_large_gpus or three_or_more or args.allow_unsupported_gpu_topology):
        raise RuntimeError(
            "GPT-OSS-120B B01 expects either 2 visible GPUs with >=47 GiB each "
            "(Server 173) or >=3 visible GPUs (r158-style). "
            f"Got n_gpu={n_gpu}, memory_gib={[round(x, 1) for x in gpu_memory_gib]}, "
            f"CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')}"
        )

    max_memory: dict[Any, str] = {}
    if two_large_gpus:
        for i in range(n_gpu):
            max_memory[i] = args.two_gpu_max_memory
    elif three_or_more:
        for i in range(n_gpu):
            max_memory[i] = args.per_gpu_max_memory
    else:
        for i, mem in enumerate(gpu_memory_gib):
            max_memory[i] = f"{max(1, int(mem - 5))}GiB"
    max_memory["cpu"] = args.cpu_max_memory

    print(f"CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')}")
    print(f"torch.cuda.device_count()={n_gpu}")
    print(f"Visible GPUs={gpu_names}")
    print(f"Visible GPU memory GiB={[round(x, 1) for x in gpu_memory_gib]}")
    print(f"GPT-OSS max_memory={max_memory}")
    if args.model_revision:
        print(f"Requested model revision={args.model_revision}")

    started = time.perf_counter()
    model = transformers.AutoModelForCausalLM.from_pretrained(
        args.scoring_model,
        revision=args.model_revision or None,
        cache_dir=str(args.model_cache_dir),
        torch_dtype="auto",
        device_map="auto",
        max_memory=max_memory,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        args.scoring_model,
        revision=args.model_revision or None,
        cache_dir=str(args.model_cache_dir),
        trust_remote_code=True,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    model.eval()
    model_load_seconds = time.perf_counter() - started

    revision = str(getattr(model.config, "_commit_hash", "") or "")
    if args.expected_model_revision and revision != args.expected_model_revision:
        raise RuntimeError(
            f"Model revision mismatch: observed={revision!r}, expected={args.expected_model_revision!r}"
        )

    tokenizer_limit = positive_context_value(getattr(tokenizer, "model_max_length", None))
    context_fields: list[int] = []
    for field in ("max_position_embeddings", "n_positions", "max_sequence_length", "seq_length"):
        value = positive_context_value(getattr(model.config, field, None))
        if value is not None:
            context_fields.append(value)
    candidates = list(context_fields)
    if tokenizer_limit is not None:
        candidates.append(tokenizer_limit)
    reported_context = min(candidates) if candidates else None

    device_map = getattr(model, "hf_device_map", None)
    rank_args = SimpleNamespace(DEVICE=args.device)
    return RuntimeBundle(
        args=rank_args,
        model_config={"base_model": model, "base_tokenizer": tokenizer},
        torch=torch,
        get_rank=get_rank,
        get_ranks=get_ranks,
        model_load_seconds=float(model_load_seconds),
        gpu_names=gpu_names,
        gpu_memory_gib=gpu_memory_gib,
        reported_model_context_limit=reported_context,
        model_revision=revision,
        device_map=device_map if isinstance(device_map, dict) else None,
    )


def score_prepared_window(record: dict[str, Any], a02: Any, runtime: RuntimeBundle) -> dict[str, Any]:
    seed = int(record["window_seed"])
    a02.set_all_seeds(seed, runtime.torch)
    started = time.perf_counter()
    tokenizer = runtime.model_config["base_tokenizer"]
    original_text = str(record["original_text"])
    perturbations_raw = record.get("perturbations")
    if not isinstance(perturbations_raw, list):
        raise ValueError("A09 record perturbations is not a list")
    perturbations = [str(value) for value in perturbations_raw]

    original_llm_tokens: int | None = None
    perturbed_lengths: list[int] = []
    try:
        original_llm_tokens = a02.tokenizer_input_length(tokenizer, original_text)
        if (
            runtime.reported_model_context_limit is not None
            and original_llm_tokens > runtime.reported_model_context_limit
        ):
            return {
                "original_llm_token_count": original_llm_tokens,
                "perturbed_llm_token_count_min": None,
                "perturbed_llm_token_count_mean": None,
                "perturbed_llm_token_count_max": None,
                "original_log_rank": None,
                "mean_perturbed_log_rank": None,
                "window_npr": None,
                "expected_perturbations": PERTURBATIONS_PER_WINDOW,
                "valid_perturbation_scores": 0,
                "deterministic_exclusion_reason": "model_context_exceeded",
                "scoring_error_type": None,
                "scoring_error_message": None,
                "scoring_seconds": float(time.perf_counter() - started),
            }

        original_log_rank = runtime.get_rank(original_text, runtime.args, runtime.model_config, log=True)
        perturbed_lengths = a02.tokenizer_lengths(tokenizer, perturbations)
        perturbed_ranks = runtime.get_ranks(perturbations, runtime.args, runtime.model_config, log=True)
        valid_ranks = [float(value) for value in perturbed_ranks if a02.sanitize_float(value) is not None]
        mean_perturbed = float(sum(valid_ranks) / len(valid_ranks)) if valid_ranks else None
        window_npr = None
        if mean_perturbed is not None and a02.sanitize_float(original_log_rank) not in (None, 0.0):
            window_npr = float(mean_perturbed / float(original_log_rank))
        return {
            "original_llm_token_count": original_llm_tokens,
            "perturbed_llm_token_count_min": min(perturbed_lengths) if perturbed_lengths else None,
            "perturbed_llm_token_count_mean": (sum(perturbed_lengths) / len(perturbed_lengths)) if perturbed_lengths else None,
            "perturbed_llm_token_count_max": max(perturbed_lengths) if perturbed_lengths else None,
            "original_log_rank": a02.sanitize_float(original_log_rank),
            "_component_log_ranks": [a02.sanitize_float(value) for value in [original_log_rank] + list(perturbed_ranks)],
            "_input_lengths": [original_llm_tokens] + perturbed_lengths,
            "mean_perturbed_log_rank": mean_perturbed,
            "window_npr": window_npr,
            "expected_perturbations": PERTURBATIONS_PER_WINDOW,
            "valid_perturbation_scores": len(valid_ranks),
            "deterministic_exclusion_reason": None,
            "scoring_error_type": None,
            "scoring_error_message": None,
            "scoring_seconds": float(time.perf_counter() - started),
        }
    except Exception as error:
        return {
            "original_llm_token_count": original_llm_tokens,
            "perturbed_llm_token_count_min": min(perturbed_lengths) if perturbed_lengths else None,
            "perturbed_llm_token_count_mean": (sum(perturbed_lengths) / len(perturbed_lengths)) if perturbed_lengths else None,
            "perturbed_llm_token_count_max": max(perturbed_lengths) if perturbed_lengths else None,
            "original_log_rank": None,
            "mean_perturbed_log_rank": None,
            "window_npr": None,
            "expected_perturbations": PERTURBATIONS_PER_WINDOW,
            "valid_perturbation_scores": 0,
            "deterministic_exclusion_reason": None,
            "scoring_error_type": type(error).__name__,
            "scoring_error_message": str(error)[:2000],
            "scoring_seconds": float(time.perf_counter() - started),
        }


def make_window_row(
    record: dict[str, Any],
    unit: dict[str, Any],
    scored: dict[str, Any],
    a02: Any,
    scoring_fingerprint: str,
    reported_context: int | None,
) -> dict[str, Any]:
    deterministic_reason = scored.get("deterministic_exclusion_reason")
    if deterministic_reason:
        valid, reason = False, deterministic_reason
    else:
        valid, reason = a02.classify_window_validity(scored)

    start = int(record["window_space_by_start"])
    end = int(record["window_space_by_end"])
    marginal = int(record.get("window_marginal_space_by_token_count", end - start))
    return {
        "scoring_fingerprint": scoring_fingerprint,
        "code_unit_sha256": unit["code_unit_sha256"],
        "code_unit_relative_path": unit["code_unit_relative_path"],
        "code_unit_types": unit["code_unit_types"],
        "unit_groups": unit["unit_groups"],
        "fun_membership": unit["fun_membership"],
        "cfun_membership": unit["cfun_membership"],
        "logical_shard": int(record["logical_shard"]),
        "window_index": int(record["window_index"]),
        "window_space_by_start": start,
        "window_space_by_end": end,
        "window_space_by_token_count": int(record.get("window_space_by_token_count", end - start)),
        "window_marginal_space_by_token_count": marginal,
        "window_aggregation_weight_space_by_tokens": 0,
        "original_llm_token_count": scored.get("original_llm_token_count"),
        "perturbed_llm_token_count_min": scored.get("perturbed_llm_token_count_min"),
        "perturbed_llm_token_count_mean": scored.get("perturbed_llm_token_count_mean"),
        "perturbed_llm_token_count_max": scored.get("perturbed_llm_token_count_max"),
        "reported_model_context_limit": reported_context,
        "original_log_rank": a02.sanitize_float(scored.get("original_log_rank")),
        "mean_perturbed_log_rank": a02.sanitize_float(scored.get("mean_perturbed_log_rank")),
        "window_npr": a02.sanitize_float(scored.get("window_npr")),
        "window_npr_valid": int(bool(valid)),
        "window_npr_invalid_reason": reason,
        "expected_perturbations": int(scored.get("expected_perturbations", PERTURBATIONS_PER_WINDOW)),
        "valid_perturbation_scores": int(scored.get("valid_perturbation_scores", 0)),
        "scoring_error_type": scored.get("scoring_error_type"),
        "scoring_error_message": scored.get("scoring_error_message"),
        "scoring_seconds": float(scored.get("scoring_seconds", 0.0)),
    }


def open_database(path: Path, overwrite: bool) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    columns_sql = ",\n".join(
        f"{name} TEXT" if name in {
            "scoring_fingerprint", "code_unit_sha256", "code_unit_relative_path", "code_unit_types",
            "unit_groups", "window_npr_invalid_reason", "scoring_error_type", "scoring_error_message"
        } else f"{name} REAL"
        for name in WINDOW_COLUMNS
    )
    conn.execute(f"CREATE TABLE IF NOT EXISTS window_scores ({columns_sql}, PRIMARY KEY(code_unit_sha256, window_index))")
    conn.execute("CREATE TABLE IF NOT EXISTS run_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()
    return conn


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM run_meta WHERE key=?", (key,)).fetchone()
    return None if row is None else str(row[0])


def set_meta(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES(?,?)", (key, str(value)))
    conn.commit()


def load_completed_keys(conn: sqlite3.Connection) -> set[tuple[str, int]]:
    return {
        (str(row[0]), int(row[1]))
        for row in conn.execute("SELECT code_unit_sha256, window_index FROM window_scores")
    }


def insert_window(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    placeholders = ",".join("?" for _ in WINDOW_COLUMNS)
    conn.execute(
        f"INSERT OR REPLACE INTO window_scores ({','.join(WINDOW_COLUMNS)}) VALUES ({placeholders})",
        [row.get(column) for column in WINDOW_COLUMNS],
    )
    conn.commit()


def sqlite_window_rows(conn: sqlite3.Connection) -> Iterator[dict[str, Any]]:
    query = f"SELECT {','.join(WINDOW_COLUMNS)} FROM window_scores ORDER BY logical_shard, code_unit_sha256, window_index"
    for row in conn.execute(query):
        yield dict(row)


def aggregate_units(
    window_rows: list[dict[str, Any]],
    unit_plan: dict[str, dict[str, Any]],
    a02: Any,
    scoring_fingerprint: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows_by_sha: dict[str, list[dict[str, Any]]] = {}
    for row in window_rows:
        rows_by_sha.setdefault(str(row["code_unit_sha256"]), []).append(row)

    unit_rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for sha, unit in sorted(unit_plan.items(), key=lambda item: (item[1]["logical_shard"], item[0])):
        window_rows = sorted(rows_by_sha.get(sha, []), key=lambda row: int(row["window_index"]))
        for row in window_rows:
            if not bool(int(row["window_npr_valid"])):
                exclusions.append({column: row.get(column) for column in EXCLUSION_COLUMNS})
        if not window_rows:
            continue
        n_valid = sum(int(row["window_npr_valid"]) for row in window_rows)
        original_all = sum(int(row["original_llm_token_count"] or 0) for row in window_rows)
        original_valid = sum(
            int(row["original_llm_token_count"] or 0)
            for row in window_rows if int(row["window_npr_valid"])
        )
        base = {
            "scoring_fingerprint": scoring_fingerprint,
            **unit,
            "n_attempted_windows": len(window_rows),
            "n_valid_npr_windows": n_valid,
            "n_invalid_npr_windows": len(window_rows) - n_valid,
            "original_llm_tokens_all_windows": original_all,
            "original_llm_tokens_valid_windows": original_valid,
        }
        try:
            aggregate = a02.aggregate_code_unit(window_rows, int(unit["space_by_tokens_total"]))
            base.update(aggregate)
            base["partial_code_unit_score"] = int(len(window_rows) != int(unit["n_expected_windows"]) or n_valid != len(window_rows))
            base["status"] = "partial" if base["partial_code_unit_score"] else "scored"
        except a02.AllWindowsInvalidError:
            base.update({
                "space_by_tokens_scored": 0,
                "npr_coverage_ratio": 0.0,
                "code_unit_npr_space_by_token_weighted": None,
                "code_unit_original_log_rank_weighted": None,
                "code_unit_mean_perturbed_log_rank_weighted": None,
                "code_unit_npr_pooled_components": None,
                "partial_code_unit_score": 1,
                "status": "all_windows_invalid",
            })
        unit_rows.append(base)
    return unit_rows, exclusions


def write_progress(
    path: Path,
    started: float,
    newly_scored: int,
    database_windows: int,
    expected_windows: int,
    last_shard: int | None,
    last_sha: str | None,
    last_window: int | None,
) -> None:
    elapsed = max(1e-9, time.perf_counter() - started)
    atomic_json({
        "script_version": SCRIPT_VERSION,
        "updated_utc": utc_now(),
        "newly_scored_windows_this_invocation": newly_scored,
        "database_windows": database_windows,
        "expected_selected_windows": expected_windows,
        "new_scoring_rate_windows_per_second": newly_scored / elapsed,
        "last_logical_shard": last_shard,
        "last_code_unit_sha256": last_sha,
        "last_window_index": last_window,
    }, path)


def run_self_test(a02_path: Path) -> None:
    assert parse_shard_ids("all") is None
    assert parse_shard_ids("0,2-4") == {0, 2, 3, 4}
    assert scope_matches({"FUN"}, "all")
    assert scope_matches({"C_FUN"}, "all")
    assert scope_matches({"FUN", "C_FUN"}, "fun")
    a02 = load_module(a02_path, "run_x_b01_a02_selftest")
    rows = [
        {"window_npr_valid": 1, "window_space_by_start": 0, "window_space_by_end": 3,
         "window_npr": 1.2, "original_log_rank": 2.0, "mean_perturbed_log_rank": 2.4},
        {"window_npr_valid": 1, "window_space_by_start": 2, "window_space_by_end": 5,
         "window_npr": 1.4, "original_log_rank": 2.0, "mean_perturbed_log_rank": 2.8},
    ]
    out = a02.aggregate_code_unit(rows, 5)
    assert math.isclose(out["code_unit_npr_space_by_token_weighted"], 1.28, abs_tol=1e-12)
    assert out["space_by_tokens_scored"] == 5
    print("score_historical_npr_gptoss self-test: PASS")



# V4 keeps the model, tokenizer, A09 texts, and A02 aggregation unchanged.
# Only execution is optimized. Validation is a prerequisite, not an assertion of
# universal bitwise equality: batch GEMMs can change floating-point rounding.
OPTIMIZATION_VERSION = "single_sequence_exact_tie_rank_profile-v1"
PROFILE_TIE_RULES = ("count-index-asc", "count-index-desc", "count-priority")
DEFAULT_MODEL_REVISION = "b5c939de8f754692c1647ca79fbf85e8c1e70f8a"
EXPECTED_RANK_SHA256 = "fc2bc8d7baab11841f07765f97a0a19d5cf51ca62b49335be3065a06dae03bcd"


class EquivalenceError(RuntimeError):
    """A proposed execution path did not reproduce the reference measurement."""


def synchronize(torch: Any) -> None:
    if torch.cuda.is_available():
        for index in range(torch.cuda.device_count()):
            torch.cuda.synchronize(index)


def empty_cuda_cache(torch: Any) -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def reference_rank_vector(logits: Any, labels: Any, torch: Any) -> Any:
    """Reproduce rank.py on an unpadded [1, L-1, V] tensor, including ties.

    Do not replace this with stable sorting or an arbitrary tied-token order.
    Keeping the full per-sequence shape also avoids selecting a different sort
    algorithm solely because only the tied rows were gathered.
    """
    matches = (logits.argsort(-1, descending=True) == labels.unsqueeze(-1)).nonzero()
    if matches.ndim != 2 or matches.shape[1] != 3:
        raise RuntimeError("Unexpected reference rank tensor dimensions")
    positions = matches[:, -2]
    if len(positions) != labels.numel() or not torch.equal(
        positions, torch.arange(labels.numel(), device=positions.device)
    ):
        raise RuntimeError("Expected exactly one rank for each next-token label")
    return matches[:, -1] + 1


def count_safe_rank_vector(
    logits: Any, labels: Any, torch: Any, tile_tokens: int,
    stats: dict[str, Any], verify_same_logits: bool = False,
) -> Any:
    """Count strictly greater logits; use the original full sort if ties exist.

    Count-only rank is exact only when the observed token has a unique logit.
    For ANY observed-token tie in a sequence, sort that entire real sequence
    with the original argsort semantics. BF16 ties are not silently redefined.
    Tiles bound comparison temporary memory without casting/quantizing logits.
    """
    n = int(labels.numel())
    if n == 0:
        return torch.empty(0, dtype=torch.int64, device=logits.device)
    counts, tied = [], []
    for start in range(0, n, tile_tokens):
        values = logits[:, start:start + tile_tokens, :]
        target = labels[:, start:start + tile_tokens].unsqueeze(-1)
        if not bool(torch.isfinite(values).all().item()):
            raise RuntimeError("Non-finite model logits; do not assign a count-based rank")
        observed = values.gather(-1, target)
        counts.append((values > observed).sum(-1).reshape(-1) + 1)
        tied.append((values == observed).sum(-1).reshape(-1) > 1)
    result = torch.cat(counts)
    tie_mask = torch.cat(tied)
    n_ties = int(tie_mask.sum().item())
    stats["ranked_tokens"] += n
    stats["observed_token_ties"] += n_ties
    old = None
    if n_ties:
        stats["full_sequence_tie_fallbacks"] += 1
        stats["argsort_sequences"] += 1
        old = reference_rank_vector(logits, labels, torch)
        # Returning all reference ranks (rather than changing tie convention)
        # exactly retains the original result for this same logits tensor.
        result = old
    if verify_same_logits:
        if old is None:
            old = reference_rank_vector(logits, labels, torch)
        mismatch = int((result != old).sum().item())
        stats["same_logits_tokens_checked"] += n
        stats["same_logits_rank_mismatches"] += mismatch
        if mismatch:
            raise EquivalenceError(f"Same-logits rank mismatch: {mismatch}/{n}")
    return result



def build_global_tie_priority(logits: Any, torch: Any) -> Any:
    """Learn one candidate tie precedence from legacy argsort on an all-equal row.

    This is a HYPOTHESIS about the current CUDA sort implementation, not a semantic
    assumption. MODE=profile must prove zero integer-rank mismatches on real logits
    before this priority can be used by validation or production.
    """
    vocab = int(logits.shape[-1])
    equal_row = torch.zeros((1, 1, vocab), dtype=logits.dtype, device=logits.device)
    order = equal_row.argsort(-1, descending=True)[0, 0]
    priority = torch.empty(vocab, dtype=torch.int64, device=logits.device)
    priority[order] = torch.arange(vocab, dtype=torch.int64, device=logits.device)
    return priority


def tie_priority_vector(vocab: int, rule: str, logits: Any, torch: Any, cache: dict[str, Any]) -> Any:
    key = f"{rule}:{vocab}:{logits.dtype}:{logits.device}"
    if key in cache:
        return cache[key]
    if rule == "count-index-asc":
        priority = torch.arange(vocab, dtype=torch.int64, device=logits.device)
    elif rule == "count-index-desc":
        priority = torch.arange(vocab - 1, -1, -1, dtype=torch.int64, device=logits.device)
    elif rule == "count-priority":
        priority = build_global_tie_priority(logits, torch)
    else:
        raise ValueError(f"Unsupported exact-tie rule: {rule}")
    cache[key] = priority
    return priority


def count_priority_rank_vector(
    logits: Any, labels: Any, torch: Any, tile_tokens: int, rule: str,
    priority_cache: dict[str, Any], stats: dict[str, Any] | None = None,
) -> Any:
    """O(V) rank candidate with explicit tie precedence; no full sort per row.

    rank = number(logit > observed) + number(equal-logit tokens with higher
    candidate tie precedence than the observed token) + 1.

    The rule is NEVER assumed exact. v5 profile/validation must establish zero
    mismatches against the unchanged rank.py argsort semantics on real data.
    """
    n = int(labels.numel())
    if n == 0:
        return torch.empty(0, dtype=torch.int64, device=logits.device)
    vocab = int(logits.shape[-1])
    priority = tie_priority_vector(vocab, rule, logits, torch, priority_cache)
    out = []
    tie_positions = 0
    max_tie_group = 1
    for start in range(0, n, tile_tokens):
        values = logits[:, start:start + tile_tokens, :]
        target = labels[:, start:start + tile_tokens].unsqueeze(-1)
        if not bool(torch.isfinite(values).all().item()):
            raise RuntimeError("Non-finite model logits; exact-tie rank is undefined")
        observed = values.gather(-1, target)
        equal = values == observed
        equal_counts = equal.sum(-1)
        tie_positions += int((equal_counts > 1).sum().item())
        max_tie_group = max(max_tie_group, int(equal_counts.max().item()))
        target_priority = priority[labels[:, start:start + tile_tokens]].unsqueeze(-1)
        before = equal & (priority.view(1, 1, -1) < target_priority)
        rank = (values > observed).sum(-1) + before.sum(-1) + 1
        out.append(rank.reshape(-1).to(torch.int64))
    if stats is not None:
        stats["ranked_tokens"] = stats.get("ranked_tokens", 0) + n
        stats["observed_token_ties"] = stats.get("observed_token_ties", 0) + tie_positions
        stats["max_observed_tie_group"] = max(stats.get("max_observed_tie_group", 1), max_tie_group)
    return torch.cat(out)


def encode_exact_texts(tokenizer: Any, texts: Sequence[str], torch: Any) -> list[dict[str, Any]]:
    """Use the SAME single-text tokenizer call as rank.py, without truncation.

    Individual encodings avoid tokenizer batch heuristics, preserve special
    tokens, and permit strict, explicit right-padding only at model input time.
    The original and all 50 perturbations retain their original list order.
    """
    encoded = []
    for text in texts:
        item = tokenizer(text, return_tensors="pt")
        keys = set(item.keys()) - {"token_type_ids"}
        if not keys <= {"input_ids", "attention_mask"}:
            raise RuntimeError(f"Unsupported tokenizer fields: {sorted(keys)}")
        ids = item["input_ids"].detach().cpu()
        mask = item.get("attention_mask", torch.ones_like(ids)).detach().cpu()
        if ids.ndim != 2 or ids.shape[0] != 1 or mask.shape != ids.shape:
            raise RuntimeError("Unexpected tokenizer input shape")
        if not bool((mask == 1).all().item()):
            raise RuntimeError("Single-text reference encoding contains masked real tokens")
        encoded.append({"input_ids": ids, "attention_mask": mask,
                        "length": int(ids.shape[1])})
    return encoded


class BatchedRankEngine:
    """Full next-token-vocabulary teacher forcing; no generation or top-k API.

    The denominator/original text is always evaluated separately. Only the
    ordered perturbation list is batched. OOM splitting changes batch capacity,
    not source content, window length, or perturbation count. A singleton OOM
    remains a hard failure, never a valid NPR or a statistical exclusion.
    """

    def __init__(self, runtime: RuntimeBundle, config: dict[str, Any], audit: bool = False):
        self.runtime, self.config, self.audit = runtime, dict(config), audit
        self.priority_cache: dict[str, Any] = {}
        self.stats: dict[str, Any] = {
            "forward_batches": 0, "sequences": 0, "real_input_tokens": 0,
            "padded_input_tokens": 0, "ranked_tokens": 0, "observed_token_ties": 0,
            "full_sequence_tie_fallbacks": 0, "argsort_sequences": 0,
            "same_logits_tokens_checked": 0, "same_logits_rank_mismatches": 0,
            "max_observed_tie_group": 1,
            "oom_splits": 0, "batch_sizes": {},
        }

    def _forward_batch(self, items: Sequence[dict[str, Any]]) -> list[float]:
        torch = self.runtime.torch
        model = self.runtime.model_config["base_model"]
        tokenizer = self.runtime.model_config["base_tokenizer"]
        lengths = [int(x["length"]) for x in items]
        max_len = max(lengths)
        if max_len < 2:
            return [float("nan")] * len(items)
        if tokenizer.pad_token_id is None and len(set(lengths)) > 1:
            raise RuntimeError("A padding token is required for variable-length batches")
        pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0
        ids = torch.full((len(items), max_len), int(pad_id), dtype=torch.long)
        mask = torch.zeros_like(ids)
        for i, item in enumerate(items):
            ids[i, :lengths[i]] = item["input_ids"][0]
            mask[i, :lengths[i]] = item["attention_mask"][0]
        # Match the legacy input device; Accelerate handles layer transfers.
        ids, mask = ids.to(self.runtime.args.DEVICE), mask.to(self.runtime.args.DEVICE)
        kwargs = {"input_ids": ids, "attention_mask": mask}
        if self.config["use_cache"] == "false":
            kwargs["use_cache"] = False
        with torch.no_grad():
            output = model(**kwargs)
            logits = output.logits
            del output
            if logits.ndim != 3 or tuple(logits.shape[:2]) != tuple(ids.shape):
                raise RuntimeError("Model must return all next-token logits, not logits_to_keep/top-k")
            labels = ids.to(logits.device)
            ranks_per_text = []
            for i, length in enumerate(lengths):
                if length < 2:
                    ranks_per_text.append(float("nan"))
                    continue
                # Remove padded positions before ranking/reduction. Legitimate
                # EOS tokens are NOT masked based on their token ID.
                real_logits = logits[i:i + 1, :length - 1, :]
                real_labels = labels[i:i + 1, 1:length]
                backend = self.config["rank_backend"]
                if backend == "argsort":
                    if not bool(torch.isfinite(real_logits).all().item()):
                        raise RuntimeError("Non-finite model logits")
                    ranks = reference_rank_vector(real_logits, real_labels, torch)
                    self.stats["argsort_sequences"] += 1
                    self.stats["ranked_tokens"] += length - 1
                elif backend == "count-safe":
                    ranks = count_safe_rank_vector(
                        real_logits, real_labels, torch, self.config["rank_tile_tokens"],
                        self.stats, self.audit,
                    )
                elif backend in PROFILE_TIE_RULES:
                    ranks = count_priority_rank_vector(
                        real_logits, real_labels, torch, self.config["rank_tile_tokens"],
                        backend, self.priority_cache, self.stats,
                    )
                    if self.audit:
                        old = reference_rank_vector(real_logits, real_labels, torch)
                        mismatch = int((ranks != old).sum().item())
                        self.stats["same_logits_tokens_checked"] += int(real_labels.numel())
                        self.stats["same_logits_rank_mismatches"] += mismatch
                        if mismatch:
                            raise EquivalenceError(f"Same-logits exact-tie rank mismatch: {mismatch}/{real_labels.numel()}")
                else:
                    raise RuntimeError(f"Unsupported rank backend: {backend}")
                ranks_per_text.append(float(torch.log(ranks.float()).float().mean().item()))
            del logits
        self.stats["forward_batches"] += 1
        self.stats["sequences"] += len(items)
        self.stats["real_input_tokens"] += sum(lengths)
        self.stats["padded_input_tokens"] += len(items) * max_len
        b = str(len(items))
        self.stats["batch_sizes"][b] = self.stats["batch_sizes"].get(b, 0) + 1
        return ranks_per_text

    def _safe_batch(self, items: Sequence[dict[str, Any]]) -> list[float]:
        torch = self.runtime.torch
        split_needed = False
        try:
            return self._forward_batch(items)
        except torch.cuda.OutOfMemoryError as error:
            if len(items) <= 1 or self.config["oom_policy"] == "abort":
                raise
            # Free tensors retained by the unwound traceback before retrying.
            traceback.clear_frames(error.__traceback__)
            split_needed = True
        if split_needed:
            self.stats["oom_splits"] += 1
            empty_cuda_cache(torch)
            middle = len(items) // 2
            return self._safe_batch(items[:middle]) + self._safe_batch(items[middle:])
        raise RuntimeError("Unreachable batch retry state")

    def score_items(self, items: Sequence[dict[str, Any]]) -> list[float]:
        result = []
        start = 0
        capacity = self.config["batch_size"]
        token_budget = self.config["max_batch_tokens"]
        while start < len(items):
            stop = start + 1
            longest = int(items[start]["length"])
            while stop < len(items) and stop - start < capacity:
                new_longest = max(longest, int(items[stop]["length"]))
                if token_budget and (stop - start + 1) * new_longest > token_budget:
                    break
                longest = new_longest
                stop += 1
            result.extend(self._safe_batch(items[start:stop]))
            start = stop
        return result



def profile_single_text(text: str, runtime: RuntimeBundle, tile_tokens: int,
                        priority_cache: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Profile one legacy B=1 teacher-forcing score and audit tie-rule hypotheses.

    GPU synchronization is deliberate here: MODE=profile measures stage attribution,
    not production throughput. Source text is never written to disk.
    """
    torch = runtime.torch
    tokenizer = runtime.model_config["base_tokenizer"]
    model = runtime.model_config["base_model"]

    t0 = time.perf_counter()
    tokenized = tokenizer(text, return_tensors="pt")
    tokenized.pop("token_type_ids", None)
    tokenize_s = time.perf_counter() - t0

    synchronize(torch)
    t0 = time.perf_counter()
    tokenized = tokenized.to(runtime.args.DEVICE)
    synchronize(torch)
    h2d_s = time.perf_counter() - t0

    synchronize(torch)
    t0 = time.perf_counter()
    with torch.no_grad():
        output = model(**tokenized)
        logits = output.logits[:, :-1]
        labels = tokenized.input_ids[:, 1:].to(logits.device)
        del output
    synchronize(torch)
    forward_s = time.perf_counter() - t0

    synchronize(torch)
    t0 = time.perf_counter()
    reference = reference_rank_vector(logits, labels, torch)
    synchronize(torch)
    argsort_s = time.perf_counter() - t0

    synchronize(torch)
    t0 = time.perf_counter()
    score = float(torch.log(reference.float()).float().mean().item())
    synchronize(torch)
    reduction_s = time.perf_counter() - t0

    rule_rows = []
    for rule in PROFILE_TIE_RULES:
        local_stats: dict[str, Any] = {}
        synchronize(torch)
        t0 = time.perf_counter()
        candidate = count_priority_rank_vector(
            logits, labels, torch, tile_tokens, rule, priority_cache, local_stats
        )
        synchronize(torch)
        rule_seconds = time.perf_counter() - t0
        mismatches = int((candidate != reference).sum().item())
        rule_rows.append({
            "rule": rule,
            "ranked_tokens": int(reference.numel()),
            "integer_rank_mismatches": mismatches,
            "candidate_rank_seconds": rule_seconds,
            "legacy_argsort_seconds": argsort_s,
            "observed_token_ties": int(local_stats.get("observed_token_ties", 0)),
            "max_observed_tie_group": int(local_stats.get("max_observed_tie_group", 1)),
        })

    row = {
        "llm_tokens": int(tokenized.input_ids.shape[1]),
        "ranked_tokens": int(reference.numel()),
        "tokenize_seconds": tokenize_s,
        "h2d_seconds": h2d_s,
        "forward_seconds": forward_s,
        "legacy_argsort_seconds": argsort_s,
        "reduction_seconds": reduction_s,
        # Unchanged rank.py contains time.sleep(0.01) once per sequence.
        "legacy_sleep_seconds": 0.01,
        "legacy_profiled_total_seconds": tokenize_s + h2d_s + forward_s + argsort_s + reduction_s + 0.01,
        "legacy_log_rank": score,
    }
    del logits, labels, reference, tokenized
    return row, rule_rows


def execute_profile(args: argparse.Namespace, plan: dict[str, dict[str, Any]], a02: Any,
                    runtime: RuntimeBundle, signature: dict[str, Any], records: list[dict[str, Any]]) -> int:
    """Attribute the 81-day baseline and test exact O(V) tie-order hypotheses."""
    # Warm up the unchanged legacy path outside timing.
    warmup_reference = float(runtime.get_rank(records[0]["original_text"], runtime.args, runtime.model_config, log=True))
    priority_cache: dict[str, Any] = {}
    stage_rows: list[dict[str, Any]] = []
    rule_rows: list[dict[str, Any]] = []
    sequence_index = 0
    for wi, record in enumerate(records):
        texts = [record["original_text"]] + list(record["perturbations"])
        for component_index, text in enumerate(texts):
            stage, rules = profile_single_text(text, runtime, args.rank_tile_tokens, priority_cache)
            component = "original" if component_index == 0 else f"perturbation_{component_index:02d}"
            common = {
                "sequence_index": sequence_index,
                "code_unit_sha256": record["code_unit_sha256"],
                "window_index": int(record["window_index"]),
                "logical_shard": int(record["logical_shard"]),
                "component": component,
            }
            stage_rows.append(common | stage)
            for rule in rules:
                rule_rows.append(common | rule)
            sequence_index += 1
        print(f"profile windows={wi+1}/{len(records)} sequences={sequence_index}", flush=True)

    if not stage_rows or not equivalent_number(warmup_reference, stage_rows[0]["legacy_log_rank"], args.atol, args.rtol):
        observed = stage_rows[0]["legacy_log_rank"] if stage_rows else None
        raise EquivalenceError(f"Profile reproduction differs from unchanged rank.py: reference={warmup_reference}, observed={observed}")

    stage_cols = ["sequence_index", "code_unit_sha256", "window_index", "logical_shard", "component",
                  "llm_tokens", "ranked_tokens", "tokenize_seconds", "h2d_seconds", "forward_seconds",
                  "legacy_argsort_seconds", "reduction_seconds", "legacy_sleep_seconds",
                  "legacy_profiled_total_seconds", "legacy_log_rank"]
    rule_cols = ["sequence_index", "code_unit_sha256", "window_index", "logical_shard", "component", "rule",
                 "ranked_tokens", "integer_rank_mismatches", "candidate_rank_seconds", "legacy_argsort_seconds",
                 "observed_token_ties", "max_observed_tie_group"]
    atomic_csv(stage_rows, args.output_dir / "profile_stage_timings.csv", stage_cols)
    atomic_csv(rule_rows, args.output_dir / "tie_rule_details.csv", rule_cols)

    totals = {field: sum(float(r[field]) for r in stage_rows) for field in
              ("tokenize_seconds", "h2d_seconds", "forward_seconds", "legacy_argsort_seconds",
               "reduction_seconds", "legacy_sleep_seconds", "legacy_profiled_total_seconds")}
    total = totals["legacy_profiled_total_seconds"]
    rule_summary = []
    for rule in PROFILE_TIE_RULES:
        rows = [r for r in rule_rows if r["rule"] == rule]
        mismatches = sum(int(r["integer_rank_mismatches"]) for r in rows)
        ranked = sum(int(r["ranked_tokens"]) for r in rows)
        seconds = sum(float(r["candidate_rank_seconds"]) for r in rows)
        legacy_rank_seconds = sum(float(r["legacy_argsort_seconds"]) for r in rows)
        exact = mismatches == 0 and ranked > 0
        rule_summary.append({
            "rule": rule, "status": "EXACT" if exact else "MISMATCH",
            "sequences": len(rows), "ranked_tokens": ranked,
            "integer_rank_mismatches": mismatches,
            "mismatch_fraction": mismatches / ranked if ranked else None,
            "candidate_rank_seconds": seconds,
            "legacy_argsort_seconds": legacy_rank_seconds,
            "rank_stage_speedup": legacy_rank_seconds / seconds if seconds else None,
            "observed_token_ties": sum(int(r["observed_token_ties"]) for r in rows),
            "max_observed_tie_group": max((int(r["max_observed_tie_group"]) for r in rows), default=1),
        })
    atomic_csv(rule_summary, args.output_dir / "tie_rule_summary.csv", list(rule_summary[0]))
    exact = [r for r in rule_summary if r["status"] == "EXACT"]
    recommended = max(exact, key=lambda r: r["rank_stage_speedup"] or 0.0) if exact else None

    expected_windows = sum(u["n_expected_windows"] for u in plan.values())
    # Rank-only Amdahl ceiling assumes legacy argsort becomes free but all other measured
    # work is unchanged. This is intentionally a ceiling, not a runtime promise.
    no_rank_total = max(1e-12, total - totals["legacy_argsort_seconds"])
    rank_only_ceiling = total / no_rank_total
    profiled_windows_per_second = len(records) / total if total else 0.0
    legacy_eta_days = expected_windows / profiled_windows_per_second / 86400 if profiled_windows_per_second else None
    no_rank_rate = len(records) / no_rank_total if no_rank_total else 0.0
    no_rank_eta_days = expected_windows / no_rank_rate / 86400 if no_rank_rate else None
    required_rate_7d = expected_windows / (args.max_production_days * 86400)
    required_rate_5d = expected_windows / (args.preferred_production_days * 86400)

    payload = {
        "status": "PASS",
        "stage": "profile",
        "script_version": SCRIPT_VERSION,
        "completed_utc": utc_now(),
        "runtime_signature": signature,
        "sample_windows": len(records),
        "sample_sequences": len(stage_rows),
        "sample_unique_units": len({r["code_unit_sha256"] for r in records}),
        "rank_py_reproduction_reference": warmup_reference,
        "rank_py_reproduction_profiled": stage_rows[0]["legacy_log_rank"],
        "rank_py_reproduction_abs_difference": abs(stage_rows[0]["legacy_log_rank"] - warmup_reference),
        "stage_totals_seconds": totals,
        "stage_fraction": {k: (v / total if total else None) for k, v in totals.items() if k != "legacy_profiled_total_seconds"},
        "tie_rules": rule_summary,
        "exact_non_sort_rules": [r["rule"] for r in exact],
        "recommended_tie_rule": recommended["rule"] if recommended else None,
        "recommended_rank_stage_speedup": recommended["rank_stage_speedup"] if recommended else None,
        "optimization_candidate_available": bool(recommended),
        "profiled_legacy_windows_per_second": profiled_windows_per_second,
        "profiled_legacy_eta_days": legacy_eta_days,
        "rank_only_amdahl_speedup_ceiling": rank_only_ceiling,
        "rank_only_amdahl_eta_days_ceiling": no_rank_eta_days,
        "preferred_production_days": args.preferred_production_days,
        "max_production_days": args.max_production_days,
        "required_windows_per_second_preferred": required_rate_5d,
        "required_windows_per_second_hard": required_rate_7d,
        "production_ready": False,
        "next_step": "validate" if recommended else "new_optimization_required",
        "note": "Profile uses synchronized B=1 stages. Candidate tie rules are hypotheses and are eligible only with zero integer-rank mismatches on the same real logits."
    }
    atomic_json(payload, args.output_dir / "profile_summary.json")
    atomic_json(payload, args.output_dir / "summary.json")
    print("PROFILE stage fractions: " + " ".join(
        f"{k.replace('_seconds','')}={100*v/total:.1f}%" for k, v in totals.items()
        if k != "legacy_profiled_total_seconds"), flush=True)
    for row in rule_summary:
        print(f"tie-rule={row['rule']} status={row['status']} mismatches={row['integer_rank_mismatches']} "
              f"rank_stage_speedup={row['rank_stage_speedup']:.3f}", flush=True)
    print(f"PROFILE rank-only Amdahl ceiling={rank_only_ceiling:.3f}x eta_if_argsort_free={no_rank_eta_days:.2f} days", flush=True)
    print(f"PROFILE exact_non_sort_rules={payload['exact_non_sort_rules']} next_step={payload['next_step']}", flush=True)
    return 0


def validate_record(record: dict[str, Any], unit: dict[str, Any], a09_fingerprint: str) -> None:
    key = f"{unit['code_unit_sha256']}/{record.get('window_index')}"
    if str(record.get("config_fingerprint")) != a09_fingerprint:
        raise RuntimeError(f"A09 fingerprint mismatch: {key}")
    perturbations = record.get("perturbations")
    if (not isinstance(perturbations, list) or len(perturbations) != 50
            or int(record.get("perturbation_count", -1)) != 50
            or not all(isinstance(x, str) for x in perturbations)):
        raise RuntimeError(f"Expected exactly 50 ordered string perturbations: {key}")
    if ordered_text_digest(perturbations) != str(record.get("perturbations_ordered_sha256")):
        raise RuntimeError(f"A09 perturbation digest mismatch: {key}")
    if not isinstance(record.get("original_text"), str):
        raise RuntimeError(f"Missing original text: {key}")
    if "window_text_sha256" in record:
        actual = hashlib.sha256(record["original_text"].encode("utf-8")).hexdigest()
        if actual != record["window_text_sha256"]:
            raise RuntimeError(f"A09 original window hash mismatch: {key}")
    index = int(record["window_index"])
    if not 0 <= index < int(unit["n_expected_windows"]):
        raise RuntimeError(f"Out-of-range window index: {key}")
    if int(record["logical_shard"]) != unit["logical_shard"]:
        raise RuntimeError(f"Logical shard mismatch: {key}")


def optimized_window(record: dict[str, Any], a02: Any, engine: BatchedRankEngine) -> dict[str, Any]:
    runtime, torch = engine.runtime, engine.runtime.torch
    a02.set_all_seeds(int(record["window_seed"]), torch)
    synchronize(torch)
    started = time.perf_counter()
    items = encode_exact_texts(runtime.model_config["base_tokenizer"],
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
        # Do not add an optimized-only truncation or perturbed-context exclusion.
        # The v2 reference only pre-excludes an overflowing ORIGINAL window.
        original = engine._safe_batch(items[:1])[0]
        perturbed = engine.score_items(items[1:])
        finite = [float(x) for x in perturbed if a02.sanitize_float(x) is not None]
        mean = sum(finite) / len(finite) if finite else None
        value = mean / original if mean is not None and a02.sanitize_float(original) not in (None, 0.0) else None
        base.update(original_log_rank=a02.sanitize_float(original),
                    mean_perturbed_log_rank=mean, window_npr=value,
                    valid_perturbation_scores=len(finite),
                    _component_log_ranks=[a02.sanitize_float(x) for x in [original] + perturbed],
                    _input_lengths=lengths)
    synchronize(torch)
    base["scoring_seconds"] = time.perf_counter() - started
    return base


def equivalent_number(a: Any, b: Any, atol: float, rtol: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        af, bf = float(a), float(b)
    except (ValueError, TypeError):
        return False
    if not (math.isfinite(af) and math.isfinite(bf)):
        return False
    return abs(af - bf) <= atol + rtol * abs(af)


def comparison_row(candidate: str, sha: str, window: int, field: str,
                   reference: Any, observed: Any, atol: float, rtol: float) -> dict[str, Any]:
    finite = reference is not None and observed is not None
    return {"candidate": candidate, "code_unit_sha256": sha, "window_index": window,
            "field": field, "reference": reference, "observed": observed,
            "abs_difference": abs(float(observed) - float(reference)) if finite else None,
            "allowed_difference": atol + rtol * abs(float(reference)) if reference is not None else None,
            "passed": int(equivalent_number(reference, observed, atol, rtol))}


COMPARISON_COLUMNS = ["candidate", "code_unit_sha256", "window_index", "field", "reference",
                      "observed", "abs_difference", "allowed_difference", "passed"]


def compare_scored(candidate: str, record: dict[str, Any], ref: dict[str, Any],
                   new: dict[str, Any], a02: Any, atol: float, rtol: float) -> list[dict[str, Any]]:
    sha, index = record["code_unit_sha256"], int(record["window_index"])
    out = []
    for field in ("original_log_rank", "mean_perturbed_log_rank", "window_npr"):
        out.append(comparison_row(candidate, sha, index, field, a02.sanitize_float(ref.get(field)),
                                  a02.sanitize_float(new.get(field)), atol, rtol))
    rlist, nlist = ref.get("_component_log_ranks", []), new.get("_component_log_ranks", [])
    if len(rlist) != len(nlist):
        raise EquivalenceError("Different number of per-perturbation reference scores")
    for i, (r, n) in enumerate(zip(rlist, nlist)):
        out.append(comparison_row(candidate, sha, index,
                                  "original_component" if i == 0 else f"perturbation_{i:02d}",
                                  a02.sanitize_float(r), a02.sanitize_float(n), atol, rtol))
    for field in ("original_llm_token_count", "valid_perturbation_scores", "expected_perturbations"):
        out.append(comparison_row(candidate, sha, index, field, ref.get(field), new.get(field), 0, 0))
    if ref.get("_input_lengths"):
        ref_lengths, new_lengths = ref["_input_lengths"], new.get("_input_lengths", [])
        out.append({"candidate": candidate, "code_unit_sha256": sha, "window_index": index,
                    "field": "all_51_tokenized_lengths", "reference": str(ref_lengths), "observed": str(new_lengths),
                    "abs_difference": None, "allowed_difference": None,
                    "passed": int(ref_lengths == new_lengths)})
    ref_valid = (False, ref["deterministic_exclusion_reason"]) if ref.get("deterministic_exclusion_reason") else a02.classify_window_validity(ref)
    new_valid = (False, new["deterministic_exclusion_reason"]) if new.get("deterministic_exclusion_reason") else a02.classify_window_validity(new)
    out.append({"candidate": candidate, "code_unit_sha256": sha, "window_index": index,
                "field": "validity_and_reason", "reference": str(ref_valid), "observed": str(new_valid),
                "abs_difference": None, "allowed_difference": None,
                "passed": int(ref_valid == new_valid)})
    return out


def execution_config(args: argparse.Namespace, batch_size: int | None = None) -> dict[str, Any]:
    return {"optimization_version": OPTIMIZATION_VERSION,
            "batch_size": args.batch_size if batch_size is None else batch_size,
            "max_batch_tokens": args.max_batch_tokens, "rank_backend": args.rank_backend,
            "rank_tile_tokens": args.rank_tile_tokens, "use_cache": args.use_cache,
            "oom_policy": args.oom_policy}


def candidate_id(config: dict[str, Any]) -> str:
    return f"{config['rank_backend']}-b{config['batch_size']}-{stable_json_hash(config)[:10]}"


def runtime_signature(args: argparse.Namespace, runtime: RuntimeBundle) -> dict[str, Any]:
    import importlib.metadata as md
    versions = {}
    for name in ("torch", "transformers", "accelerate", "triton", "kernels", "tokenizers", "safetensors"):
        try:
            versions[name] = md.version(name)
        except md.PackageNotFoundError:
            versions[name] = "unavailable"
    model, tokenizer = runtime.model_config["base_model"], runtime.model_config["base_tokenizer"]
    quant = getattr(model.config, "quantization_config", None)
    if hasattr(quant, "to_dict"):
        quant = quant.to_dict()
    return {"script_sha256": sha256_file(Path(__file__).resolve()),
            "a02_sha256": sha256_file(args.a02_script),
            "rank_sha256": sha256_file(args.rank_script),
            "a09_config_fingerprint": EXPECTED_A09_CONFIG_FINGERPRINT,
            "unit_plan_sha256": sha256_file(args.a09_root / "plan" / "unique_primary_units.csv"),
            "scoring_model": args.scoring_model, "model_revision": runtime.model_revision,
            "packages": versions, "cuda_runtime": str(runtime.torch.version.cuda),
            "gpu_names": runtime.gpu_names, "device_map": runtime.device_map,
            "dtype": str(getattr(model, "dtype", "unknown")), "quantization_config": quant,
            "attention_implementation": getattr(model.config, "_attn_implementation", None),
            "model_use_cache_default": getattr(model.config, "use_cache", None),
            "tokenizer_class": type(tokenizer).__name__, "pad_token_id": tokenizer.pad_token_id,
            "eos_token_id": tokenizer.eos_token_id,
            "cudnn_version": runtime.torch.backends.cudnn.version(),
            "allow_tf32_matmul": bool(runtime.torch.backends.cuda.matmul.allow_tf32),
            "allow_tf32_cudnn": bool(runtime.torch.backends.cudnn.allow_tf32),
            "float32_matmul_precision": runtime.torch.get_float32_matmul_precision(),
            "deterministic_algorithms": runtime.torch.are_deterministic_algorithms_enabled(),
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "numeric_environment": {k: os.environ.get(k) for k in (
                "CUBLAS_WORKSPACE_CONFIG", "NVIDIA_TF32_OVERRIDE", "TORCH_ALLOW_TF32_CUBLAS_OVERRIDE")}}


def reset_peak_memory(torch: Any) -> None:
    if torch.cuda.is_available():
        synchronize(torch)
        for index in range(torch.cuda.device_count()):
            torch.cuda.reset_peak_memory_stats(index)


def memory_snapshot(torch: Any) -> list[dict[str, Any]]:
    out = []
    if torch.cuda.is_available():
        for index in range(torch.cuda.device_count()):
            free, total = torch.cuda.mem_get_info(index)
            out.append({"gpu": index, "peak_allocated_gib": torch.cuda.max_memory_allocated(index) / 1024**3,
                        "peak_reserved_gib": torch.cuda.max_memory_reserved(index) / 1024**3,
                        "free_gib": free / 1024**3, "total_gib": total / 1024**3})
    return out



def read_v2_reference(args: argparse.Namespace) -> tuple[dict[tuple[str, int], dict[str, Any]], dict[str, Any]]:
    path = args.reference_db
    if not path.is_file():
        raise FileNotFoundError(f"Missing read-only v2 smoke checkpoint: {path}")
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        meta = {str(r[0]): str(r[1]) for r in conn.execute("SELECT key,value FROM run_meta")}
        if meta.get("script_version") != "run-x-b01-v2" or meta.get("scoring_model") != SCORING_MODEL:
            raise RuntimeError("Reference must be the B01-v2 GPT-OSS checkpoint")
        if meta.get("model_revision") != args.model_revision:
            raise RuntimeError("Requested model revision differs from the v2 reference")
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM window_scores ORDER BY logical_shard,code_unit_sha256,window_index LIMIT ?",
            (args.validation_windows,))]
        if len(rows) < args.validation_windows:
            raise RuntimeError(f"Need {args.validation_windows} v2 reference windows; found {len(rows)}")
        if any(r.get("scoring_error_type") or int(r["window_npr_valid"]) != 1 for r in rows):
            raise RuntimeError("Initial v2 equivalence sample must contain valid, error-free scores")
        return {(str(r["code_unit_sha256"]), int(r["window_index"])): r for r in rows}, meta
    finally:
        conn.close()


def representative_keys(unit_plan: dict[str, dict[str, Any]], size: int, seed: int) -> dict[tuple[str, int], str]:
    """Uniform sampling over WINDOWS, plus deterministic scope/length stress cases.

    Uniform-window timings, not stress-case timings, define the ETA. Sampling
    units uniformly would bias a window-throughput projection toward short units.
    Source identities come only from the existing plan; no source is re-extracted.
    """
    ordered = sorted(unit_plan.items(), key=lambda x: (x[1]["logical_shard"], x[0]))
    total = sum(int(u["n_expected_windows"]) for _, u in ordered)
    if size > total:
        raise ValueError(f"Requested {size} windows from a {total}-window scope")
    offsets = sorted(random.Random(seed).sample(range(total), size))
    chosen: dict[tuple[str, int], str] = {}
    cursor = 0
    offset_index = 0
    for sha, unit in ordered:
        end = cursor + int(unit["n_expected_windows"])
        while offset_index < len(offsets) and offsets[offset_index] < end:
            chosen[(sha, offsets[offset_index] - cursor)] = "uniform"
            offset_index += 1
        cursor = end
    # Add longest/shortest procedure cases for both semantic scopes. These are
    # stress tests, NOT proof of worst-case tokenizer length or universal safety.
    for member in ("fun_membership", "cfun_membership"):
        candidates = [(sha, u) for sha, u in ordered if u[member]]
        if not candidates:
            continue
        by_length = sorted(candidates, key=lambda x: (int(x[1]["space_by_tokens_total"]), x[0]))
        for sha, unit in (by_length[0], by_length[-1]):
            key = (sha, int(unit["n_expected_windows"]) - 1)
            chosen.setdefault(key, "stress")
    return chosen


def fetch_sample_records(args: argparse.Namespace, plan: dict[str, dict[str, Any]],
                         roles: dict[tuple[str, int], str]) -> list[dict[str, Any]]:
    found = {}
    by_shard: dict[int, set[tuple[str, int]]] = {}
    for key in roles:
        if key[0] not in plan:
            raise RuntimeError(f"Reference key outside the selected scope: {key}")
        by_shard.setdefault(plan[key[0]]["logical_shard"], set()).add(key)
    for shard, keys in sorted(by_shard.items()):
        path, _ = shard_paths(args.a09_root, shard)
        shas = {key[0] for key in keys}
        for record in iter_selected_records(path, shas):
            key = (str(record["code_unit_sha256"]), int(record["window_index"]))
            if key not in keys:
                continue
            if key in found:
                raise RuntimeError(f"Duplicate A09 sample key: {key}")
            record["logical_shard"] = shard
            validate_record(record, plan[key[0]], EXPECTED_A09_CONFIG_FINGERPRINT)
            record["_sampling_role"] = roles[key]
            found[key] = record
            if keys <= found.keys():
                break
    if found.keys() != roles.keys():
        raise RuntimeError(f"A09 sample keys missing: {len(roles.keys() - found.keys())}")
    return sorted(found.values(), key=lambda r: (r["logical_shard"], r["code_unit_sha256"], int(r["window_index"])))


def compare_unit_aggregates(candidate: str, records: list[dict[str, Any]], reference: list[dict[str, Any]],
                            observed: list[dict[str, Any]], plan: dict[str, dict[str, Any]],
                            a02: Any, atol: float, rtol: float) -> list[dict[str, Any]]:
    # A partial sample aggregate is explicitly identified; it is not claimed to
    # be a full-procedure equivalence check if some windows were not sampled.
    ref_rows = [make_window_row(r, plan[r["code_unit_sha256"]], s, a02, "reference", None)
                for r, s in zip(records, reference)]
    new_rows = [make_window_row(r, plan[r["code_unit_sha256"]], s, a02, "candidate", None)
                for r, s in zip(records, observed)]
    ref_units, _ = aggregate_units(ref_rows, plan, a02, "reference")
    new_units, _ = aggregate_units(new_rows, plan, a02, "candidate")
    indexed = {r["code_unit_sha256"]: r for r in new_units}
    comparisons = []
    for ref in ref_units:
        sha = ref["code_unit_sha256"]
        new = indexed[sha]
        fields = ("code_unit_npr_space_by_token_weighted", "code_unit_original_log_rank_weighted",
                  "code_unit_mean_perturbed_log_rank_weighted", "code_unit_npr_pooled_components",
                  "npr_coverage_ratio", "space_by_tokens_scored", "n_attempted_windows", "n_valid_npr_windows")
        for field in fields:
            row = comparison_row(candidate, sha, -1, field, ref.get(field), new.get(field), atol, rtol)
            row["sampled_windows"] = ref["n_attempted_windows"]
            row["expected_unit_windows"] = ref["n_expected_windows"]
            row["complete_unit_sample"] = int(ref["n_attempted_windows"] == ref["n_expected_windows"])
            comparisons.append(row)
    return comparisons


def sample_manifest(records: Sequence[dict[str, Any]], scored: Sequence[dict[str, Any]],
                    plan: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for record, score in zip(records, scored):
        unit = plan[record["code_unit_sha256"]]
        out.append({"code_unit_sha256": record["code_unit_sha256"],
                    "window_index": int(record["window_index"]), "logical_shard": record["logical_shard"],
                    "sampling_role": record["_sampling_role"], "unit_groups": unit["unit_groups"],
                    "expected_unit_windows": unit["n_expected_windows"],
                    "space_by_tokens_total": unit["space_by_tokens_total"],
                    "original_llm_token_count": score.get("original_llm_token_count"),
                    "perturbed_llm_token_count_min": score.get("perturbed_llm_token_count_min"),
                    "perturbed_llm_token_count_max": score.get("perturbed_llm_token_count_max"),
                    "perturbations_ordered_sha256": record["perturbations_ordered_sha256"]})
    return out


def reference_sample(args: argparse.Namespace, records: list[dict[str, Any]], a02: Any,
                     runtime: RuntimeBundle, legacy_rows: dict[tuple[str, int], dict[str, Any]] | None
                     ) -> list[dict[str, Any]]:
    refs, cached_comparisons = [], []
    for i, record in enumerate(records):
        # The reference calls the unchanged rank.py (51 sequential forwards).
        synchronize(runtime.torch)
        result = score_prepared_window(record, a02, runtime)
        synchronize(runtime.torch)
        if result.get("scoring_error_type"):
            raise RuntimeError(f"Sequential reference failed at {record['code_unit_sha256']}/{record['window_index']}: "
                               f"{result['scoring_error_type']}: {result['scoring_error_message']}")
        refs.append(result)
        key = (record["code_unit_sha256"], int(record["window_index"]))
        if legacy_rows is not None:
            for field in ("original_log_rank", "mean_perturbed_log_rank", "window_npr"):
                cached_comparisons.append(comparison_row("legacy-v2", key[0], key[1], field,
                                                         legacy_rows[key].get(field), result.get(field),
                                                         args.atol, args.rtol))
        if (i + 1) % args.progress_every_windows == 0 or i + 1 == len(records):
            print(f"reference windows={i+1}/{len(records)} sequential_seconds="
                  f"{sum(r['scoring_seconds'] for r in refs):.3f}", flush=True)
    # Save all 51 scalar components, but never copy historical source strings.
    with gzip.open(args.output_dir / "reference_components.jsonl.gz", "wt", encoding="utf-8") as stream:
        for record, ref in zip(records, refs):
            payload = {"code_unit_sha256": record["code_unit_sha256"], "window_index": record["window_index"],
                       "logical_shard": record["logical_shard"], "scores": ref}
            stream.write(json.dumps(payload, allow_nan=False, sort_keys=True) + "\n")
    if cached_comparisons:
        atomic_csv(cached_comparisons, args.output_dir / "legacy_v2_comparison.csv", COMPARISON_COLUMNS)
        failures = sum(not r["passed"] for r in cached_comparisons)
        if failures:
            raise EquivalenceError(f"Current sequential reference differs from v2 on {failures} checks; inspect legacy_v2_comparison.csv")
    return refs


def run_candidate(args: argparse.Namespace, config: dict[str, Any], records: list[dict[str, Any]],
                  refs: list[dict[str, Any]], plan: dict[str, dict[str, Any]], a02: Any,
                  runtime: RuntimeBundle, audit: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    name = candidate_id(config)
    engine = BatchedRankEngine(runtime, config, audit=audit)
    comparisons, scores = [], []
    error_text = ""
    empty_cuda_cache(runtime.torch)
    reset_peak_memory(runtime.torch)
    # Warm up once using real prepared input. Never include it in throughput.
    try:
        optimized_window(records[0], a02, BatchedRankEngine(runtime, config, audit=False))
        for i, (record, ref) in enumerate(zip(records, refs)):
            result = optimized_window(record, a02, engine)
            scores.append(result)
            comparisons.extend(compare_scored(name, record, ref, result, a02, args.atol, args.rtol))
            if (i + 1) % args.progress_every_windows == 0 or i + 1 == len(records):
                print(f"candidate={name} windows={i+1}/{len(records)} mismatches="
                      f"{sum(not c['passed'] for c in comparisons)}", flush=True)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        error_text = f"{type(error).__name__}: {error}"
        traceback.clear_frames(error.__traceback__)
        empty_cuda_cache(runtime.torch)
        print(f"candidate={name} failed: {error_text}", flush=True)
    unit_comparisons = []
    if len(scores) == len(records):
        unit_comparisons = compare_unit_aggregates(name, records, refs, scores, plan, a02, args.atol, args.rtol)
    atomic_csv(comparisons, args.output_dir / f"{name}_component_comparison.csv", COMPARISON_COLUMNS)
    atomic_csv(unit_comparisons, args.output_dir / f"{name}_aggregate_comparison.csv",
               COMPARISON_COLUMNS + ["sampled_windows", "expected_unit_windows", "complete_unit_sample"])
    failed = sum(not c["passed"] for c in comparisons + unit_comparisons)
    differences = [float(c["abs_difference"]) for c in comparisons if c["abs_difference"] is not None]
    seconds = sum(r["scoring_seconds"] for r in scores)
    ref_seconds = sum(r["scoring_seconds"] for r in refs)
    passed = not error_text and len(scores) == len(records) and failed == 0 and engine.stats["same_logits_rank_mismatches"] == 0
    summary = {"candidate": name, "config": config, "status": "PASS" if passed else "FAIL",
               "windows_checked": len(scores), "component_and_aggregate_failed_checks": failed,
               "max_scalar_abs_difference": max(differences, default=0.0),
               "comparison_checks": len(comparisons) + len(unit_comparisons),
               "bitwise_equal_scalar_checks": sum(c["abs_difference"] == 0 for c in comparisons if c["abs_difference"] is not None),
               "measured_scoring_seconds": seconds, "reference_scoring_seconds": ref_seconds,
               "measured_windows_per_second": len(scores) / seconds if seconds else 0.0,
               "speedup_over_reference": ref_seconds / seconds if seconds and len(scores) == len(records) else None,
               "includes_same_logits_audit_overhead": audit, "counters": engine.stats,
               "peak_memory": memory_snapshot(runtime.torch), "error": error_text}
    print(f"candidate={name} status={summary['status']} speedup={summary['speedup_over_reference']} "
          f"audit={audit} ties={engine.stats['observed_token_ties']} "
          f"tie_fallback_sequences={engine.stats['full_sequence_tie_fallbacks']}", flush=True)
    return summary, scores


def execute_validation(args: argparse.Namespace, plan: dict[str, dict[str, Any]], a02: Any,
                       runtime: RuntimeBundle, signature: dict[str, Any],
                       records: list[dict[str, Any]], legacy_rows: dict[tuple[str, int], dict[str, Any]]) -> int:
    # GPU/model imports, original rank, and tokenizer warmup are outside timing.
    runtime.get_rank(records[0]["original_text"], runtime.args, runtime.model_config, log=True)
    refs = reference_sample(args, records, a02, runtime, legacy_rows)
    manifest = sample_manifest(records, refs, plan)
    atomic_csv(manifest, args.output_dir / "validation_sample.csv", list(manifest[0]))
    candidates = []
    for batch in args.batch_sizes:
        result, _ = run_candidate(args, execution_config(args, batch), records, refs, plan, a02, runtime, audit=True)
        candidates.append(result)
    passed = [r for r in candidates if r["status"] == "PASS"]
    recommended = max(passed, key=lambda r: r["measured_windows_per_second"]) if passed else None
    payload = {"status": "PASS" if passed else "FAIL", "script_version": SCRIPT_VERSION,
               "stage": "validation", "completed_utc": utc_now(), "runtime_signature": signature,
               "reference_database": str(args.reference_db), "reference_database_sha256": sha256_file(args.reference_db),
               "sample_windows": len(records), "sample_unique_units": len({r['code_unit_sha256'] for r in records}),
               "sample_shards": sorted({r["logical_shard"] for r in records}),
               "atol": args.atol, "rtol": args.rtol, "candidates": candidates,
               "recommended_candidate": recommended["candidate"] if recommended else None,
               "recommended_config": recommended["config"] if recommended else None,
               "production_ready": False,
               "profile_summary_sha256": sha256_file(args.profile_summary),
               "note": "B=1 end-to-end equivalence after exact same-logits tie-rule profiling. A representative benchmark and runtime gate are still required."}
    atomic_json(payload, args.output_dir / "validation_summary.json")
    atomic_json(payload, args.output_dir / "summary.json")
    print(f"VALIDATION {payload['status']}: passing_candidates={len(passed)}/{len(candidates)}, "
          f"distinct_units={payload['sample_unique_units']}. Production remains HOLD.")
    return 0 if passed else 1


def validate_approval_signature(approval: dict[str, Any], signature: dict[str, Any]) -> None:
    if stable_json_hash(approval.get("runtime_signature")) != stable_json_hash(signature):
        expected = approval.get("runtime_signature", {})
        changed = sorted(k for k in signature.keys() | expected.keys() if expected.get(k) != signature.get(k))
        raise RuntimeError(f"Approval/runtime mismatch in {changed}. Revalidate; do not reuse scores across execution environments.")


def execute_benchmark(args: argparse.Namespace, plan: dict[str, dict[str, Any]], a02: Any,
                      runtime: RuntimeBundle, signature: dict[str, Any], records: list[dict[str, Any]]) -> int:
    validation = load_json(args.validation_summary)
    if validation.get("status") != "PASS":
        raise RuntimeError("Representative benchmark requires a passing validation_summary.json")
    validate_approval_signature(validation, signature)
    passed = [r for r in validation["candidates"] if r["status"] == "PASS"]
    if args.candidate:
        passed = [r for r in passed if r["candidate"] == args.candidate]
    else:
        passed = [r for r in passed if r["candidate"] == validation["recommended_candidate"]]
    if len(passed) != 1:
        raise RuntimeError("Requested benchmark candidate is not uniquely approved by validation")
    config = passed[0]["config"]
    if args.atol != validation["atol"] or args.rtol != validation["rtol"]:
        raise RuntimeError("Benchmark tolerances must match validation")
    runtime.get_rank(records[0]["original_text"], runtime.args, runtime.model_config, log=True)
    refs = reference_sample(args, records, a02, runtime, legacy_rows=None)
    manifest = sample_manifest(records, refs, plan)
    atomic_csv(manifest, args.output_dir / "benchmark_sample.csv", list(manifest[0]))
    # Every sampled window is compared to all 51 sequential reference components.
    # Rank implementation was also checked on identical logits during validation.
    result, scored = run_candidate(args, config, records, refs, plan, a02, runtime, audit=False)
    uniform_pairs = [(record, ref, new) for record, ref, new in zip(records, refs, scored)
                     if record["_sampling_role"] == "uniform"]
    uniform_seconds = sum(new["scoring_seconds"] for _, _, new in uniform_pairs)
    uniform_reference_seconds = sum(ref["scoring_seconds"] for _, ref, _ in uniform_pairs)
    n_uniform = len(uniform_pairs)
    expected_windows = sum(u["n_expected_windows"] for u in plan.values())
    rate = n_uniform / uniform_seconds if uniform_seconds else 0.0
    eta_days = expected_windows / rate / 86400 if rate > 0 else None
    expected_uniform = sum(r["_sampling_role"] == "uniform" for r in records)
    ready = (result["status"] == "PASS" and n_uniform == expected_uniform and n_uniform >= 100
             and eta_days is not None and eta_days <= args.max_production_days)
    payload = {"status": result["status"], "script_version": SCRIPT_VERSION, "stage": "benchmark",
               "completed_utc": utc_now(), "runtime_signature": signature, "candidate": result,
               "execution_config": config, "scope": args.scope, "shard_ids": args.shard_ids,
               "sampling_policy": "uniform_without_replacement_over_planned_windows_plus_excluded_from_ETA_stress_cases",
               "uniform_sample_windows": n_uniform, "total_sample_windows": len(records),
               "sample_unique_units": len({r['code_unit_sha256'] for r in records}),
               "sample_shards": sorted({r["logical_shard"] for r in records}),
               "uniform_scoring_seconds": uniform_seconds, "uniform_reference_seconds": uniform_reference_seconds,
               "uniform_windows_per_second": rate,
               "uniform_speedup": uniform_reference_seconds / uniform_seconds if uniform_seconds else None,
               "expected_production_windows": expected_windows, "projected_scoring_days": eta_days,
               "preferred_production_days": args.preferred_production_days,
               "max_production_days": args.max_production_days,
               "conference_runtime_class": ("PREFERRED" if eta_days is not None and eta_days <= args.preferred_production_days else
                                            "ACCEPTABLE" if eta_days is not None and eta_days <= args.max_production_days else "HOLD"),
               "production_ready": ready,
               "atol": args.atol, "rtol": args.rtol,
               "validation_summary_sha256": sha256_file(args.validation_summary),
               "note": "ETA excludes future I/O, checkpoints, retries, and interruptions; it is not a completion-time guarantee."}
    atomic_json(payload, args.output_dir / "benchmark_summary.json")
    atomic_json(payload, args.output_dir / "summary.json")
    timing_rows = [{"code_unit_sha256": r["code_unit_sha256"], "window_index": r["window_index"],
                    "logical_shard": r["logical_shard"], "sampling_role": r["_sampling_role"],
                    "reference_seconds": ref["scoring_seconds"], "optimized_seconds": new["scoring_seconds"],
                    "original_llm_tokens": new["original_llm_token_count"],
                    "max_perturbed_llm_tokens": new["perturbed_llm_token_count_max"]}
                   for r, ref, new in zip(records, refs, scored)]
    atomic_csv(timing_rows, args.output_dir / "benchmark_window_timings.csv",
               ["code_unit_sha256", "window_index", "logical_shard", "sampling_role", "reference_seconds",
                "optimized_seconds", "original_llm_tokens", "max_perturbed_llm_tokens"])
    if ready:
        atomic_json(payload, args.output_dir / "production_approval.json")
    print(f"BENCHMARK {result['status']}: rate={rate:.6f} windows/s, projected_days={eta_days}, "
          f"budget_days={args.max_production_days}; production={'APPROVED' if ready else 'HOLD'}")
    return 0 if result["status"] == "PASS" else 1


def allowed_exclusion(row: dict[str, Any]) -> bool:
    if row.get("scoring_error_type"):
        return False
    reason = row.get("window_npr_invalid_reason")
    return (reason in {"model_context_exceeded", "zero_original_log_rank"}
            or (reason == "no_valid_perturbation_scores" and int(row.get("original_llm_token_count") or 0) <= 1))


def export_production(conn: sqlite3.Connection, args: argparse.Namespace, plan: dict[str, dict[str, Any]],
                      a02: Any, fingerprint: str, expected: int, checks: list[dict[str, Any]]) -> dict[str, Any]:
    windows = list(sqlite_window_rows(conn))
    units, exclusions = aggregate_units(windows, plan, a02, fingerprint)
    # Same CSV schema as v2; execution provenance lives in metadata/fingerprint.
    atomic_csv(windows, args.output_dir / "python_historical_gptoss_window_npr_scores.csv", WINDOW_COLUMNS)
    atomic_csv(units, args.output_dir / "python_historical_gptoss_unique_code_unit_npr_scores.csv", UNIT_COLUMNS)
    atomic_csv((u for u in units if u["fun_membership"]), args.output_dir / "python_fun_unique_code_unit_npr_scores.csv", UNIT_COLUMNS)
    atomic_csv((u for u in units if u["cfun_membership"]), args.output_dir / "python_cfun_unique_code_unit_npr_scores.csv", UNIT_COLUMNS)
    atomic_csv(exclusions, args.output_dir / "python_historical_gptoss_npr_exclusions.csv", EXCLUSION_COLUMNS)
    failures = [r for r in windows if r.get("scoring_error_type")]
    atomic_csv(failures, args.output_dir / "python_historical_gptoss_npr_failures.csv", FAILURE_COLUMNS)
    unexpected_invalid = [r for r in windows if not int(r["window_npr_valid"]) and not allowed_exclusion(r)]
    add_check(checks, "database_windows_complete", len(windows) == expected, len(windows), expected)
    add_check(checks, "all_selected_units_attempted", len(units) == len(plan), len(units), len(plan))
    add_check(checks, "unexpected_invalid_windows", not unexpected_invalid, len(unexpected_invalid), 0)
    add_check(checks, "scoring_errors", not failures, len(failures), 0)
    add_check(checks, "window_fingerprints", all(r["scoring_fingerprint"] == fingerprint for r in windows),
              sum(r["scoring_fingerprint"] != fingerprint for r in windows), 0)
    atomic_csv(checks, args.output_dir / "checks.csv", CHECK_COLUMNS)
    bad = sum(not r["passed"] for r in checks)
    return {"status": "PASS" if not bad else "FAIL", "failed_checks": bad,
            "database_windows": len(windows), "valid_npr_windows": sum(int(r["window_npr_valid"]) for r in windows),
            "invalid_npr_windows": sum(not int(r["window_npr_valid"]) for r in windows),
            "scoring_errors": len(failures), "unexpected_invalid_windows": len(unexpected_invalid),
            "exported_unique_code_units": len(units),
            "partial_unique_code_units": sum(int(u["partial_code_unit_score"]) for u in units),
            "all_windows_invalid_units": sum(u["status"] == "all_windows_invalid" for u in units)}



def online_equivalence_audit(args: argparse.Namespace, record: dict[str, Any], scored: dict[str, Any],
                             runtime: RuntimeBundle, a02: Any, config: dict[str, Any]) -> None:
    """Recheck a sparse deterministic set during production; drift stops the run."""
    reference = score_prepared_window(record, a02, runtime)
    if reference.get("scoring_error_type"):
        raise EquivalenceError(f"Online sequential reference failed: {reference['scoring_error_message']}")
    rows = compare_scored(candidate_id(config), record, reference, scored, a02, args.atol, args.rtol)
    path = args.output_dir / "online_equivalence_checks.csv"
    exists = path.is_file() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COMPARISON_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())
    if any(not r["passed"] for r in rows):
        raise EquivalenceError("Online equivalence failure; inspect online_equivalence_checks.csv before resuming")


def execute_production(args: argparse.Namespace, plan: dict[str, dict[str, Any]], a02: Any,
                       runtime: RuntimeBundle | None, signature: dict[str, Any] | None,
                       checks: list[dict[str, Any]]) -> int:
    expected = sum(u["n_expected_windows"] for u in plan.values())
    db_path = args.output_dir / "window_scores.sqlite3"
    if args.mode == "finalize":
        if not db_path.is_file():
            raise FileNotFoundError("Finalize requires the existing v5 production checkpoint")
        conn = open_database(db_path, False)
        fp = get_meta(conn, "scoring_fingerprint")
        if get_meta(conn, "script_version") != SCRIPT_VERSION:
            raise RuntimeError("Refusing to finalize a non-v5 checkpoint")
        signature = json.loads(get_meta(conn, "runtime_signature") or "null")
        config = json.loads(get_meta(conn, "execution_config") or "null")
    else:
        approval = load_json(args.approval)
        if approval.get("status") != "PASS" or not approval.get("production_ready"):
            raise RuntimeError("Production is HOLD: need an approved representative benchmark")
        if float(approval.get("projected_scoring_days", float("inf"))) > args.max_production_days:
            raise RuntimeError("Approved runtime estimate exceeds the current operational budget; production HOLD")
        validate_approval_signature(approval, signature)
        if sha256_file(args.validation_summary) != approval["validation_summary_sha256"]:
            raise RuntimeError("Validation changed after the benchmark; repeat the benchmark")
        if args.scope != approval["scope"] or args.shard_ids != approval["shard_ids"]:
            raise RuntimeError("Production scope/shards must match the approved workload")
        config = approval["execution_config"]
        fp = stable_json_hash({"runtime_signature": signature, "execution": config,
                               "scope": args.scope, "shard_ids": args.shard_ids,
                               "aggregation_policy": AGGREGATION_POLICY, "window_policy": WINDOW_POLICY,
                               "audit_every_windows": args.audit_every_windows})
        conn = open_database(db_path, args.overwrite)
        old = get_meta(conn, "scoring_fingerprint")
        if old and old != fp:
            conn.close()
            raise RuntimeError("Incompatible v5 checkpoint; choose a different OUTPUT_DIR, never reuse v2 scores")
        if not old:
            for k, v in {"scoring_fingerprint": fp, "model_revision": runtime.model_revision,
                         "scoring_model": args.scoring_model, "script_version": SCRIPT_VERSION,
                         "scope": args.scope, "shard_ids": args.shard_ids,
                         "execution_config": json.dumps(config, sort_keys=True),
                         "runtime_signature": json.dumps(signature, sort_keys=True)}.items():
                set_meta(conn, k, v)
    if get_meta(conn, "scope") != args.scope or get_meta(conn, "shard_ids") != args.shard_ids:
        conn.close()
        raise RuntimeError("Checkpoint scope/shard mismatch")
    if signature is None or signature.get("a02_sha256") != sha256_file(args.a02_script):
        raise RuntimeError("Finalize/production A02 source mismatch")
    if signature.get("unit_plan_sha256") != sha256_file(args.a09_root / "plan" / "unique_primary_units.csv"):
        raise RuntimeError("Finalize/production input plan changed")
    if args.mode == "run" and args.retry_error_windows:
        conn.execute("DELETE FROM window_scores WHERE scoring_error_type IS NOT NULL")
        conn.commit()
    completed = load_completed_keys(conn)
    for sha, index in completed:
        if sha not in plan or not 0 <= index < plan[sha]["n_expected_windows"]:
            raise RuntimeError("Checkpoint contains a key outside the current workload")
    reused = len(completed)
    new = 0
    audited_windows = 0
    last_shard = last_index = None
    last_sha = None
    started = time.perf_counter()
    interrupted = None
    engine = BatchedRankEngine(runtime, config) if runtime is not None else None
    try:
        if args.mode == "run":
            for shard in sorted({u["logical_shard"] for u in plan.values()}):
                path, _ = shard_paths(args.a09_root, shard)
                shard_shas = {sha for sha, u in plan.items() if u["logical_shard"] == shard}
                if all((sha, i) in completed for sha in shard_shas for i in range(plan[sha]["n_expected_windows"])):
                    continue
                for record in iter_selected_records(path, shard_shas):
                    sha, index = str(record["code_unit_sha256"]), int(record["window_index"])
                    key = (sha, index)
                    if key in completed:
                        continue
                    record["logical_shard"] = shard
                    validate_record(record, plan[sha], EXPECTED_A09_CONFIG_FINGERPRINT)
                    last_shard, last_sha, last_index = shard, sha, index
                    try:
                        scored = optimized_window(record, a02, engine)
                        key_hash = int(hashlib.sha256(f"{sha}:{index}".encode("ascii")).hexdigest()[:16], 16)
                        if new == 0 or key_hash % args.audit_every_windows == 0:
                            online_equivalence_audit(args, record, scored, runtime, a02, config)
                            audited_windows += 1
                    except Exception as error:
                        # Record the failed key, preserve all earlier commits,
                        # and stop instead of burning days on repeated errors.
                        scored = {"scoring_error_type": type(error).__name__,
                                  "scoring_error_message": str(error)[:2000], "scoring_seconds": 0}
                        row = make_window_row(record, plan[sha], scored, a02, fp, runtime.reported_model_context_limit)
                        insert_window(conn, row)
                        raise
                    row = make_window_row(record, plan[sha], scored, a02, fp, runtime.reported_model_context_limit)
                    insert_window(conn, row)
                    if not row["window_npr_valid"] and not allowed_exclusion(row):
                        raise RuntimeError(f"Unexpected invalid score at {sha}/{index}; investigate before resume")
                    completed.add(key)
                    new += 1
                    if new % args.progress_every_windows == 0:
                        write_progress(args.output_dir / "progress.json", started, new, len(completed), expected,
                                       last_shard, last_sha, last_index)
                        rate = new / max(1e-9, time.perf_counter() - started)
                        print(f"progress new={new} db={len(completed)} expected={expected} shard={shard:03d} "
                              f"rate={rate:.6f} windows/s eta_days={(expected-len(completed))/max(rate,1e-9)/86400:.3f}", flush=True)
    except BaseException as error:
        interrupted = error
    metrics = export_production(conn, args, plan, a02, fp, expected, checks)
    if interrupted is not None:
        metrics["status"] = "INTERRUPTED" if isinstance(interrupted, KeyboardInterrupt) else "FAIL"
        metrics["error"] = f"{type(interrupted).__name__}: {interrupted}"
    payload = {**metrics, "script_version": SCRIPT_VERSION, "stage": args.mode, "completed_utc": utc_now(),
               "runtime_signature": signature, "execution_config": config, "scoring_fingerprint": fp,
               "model_revision": signature["model_revision"], "scope": args.scope, "shard_ids": args.shard_ids,
               "selected_unique_code_units": len(plan), "expected_selected_windows": expected,
               "checkpoint_rows_reused_at_start": reused, "newly_scored_windows_this_invocation": new,
               "elapsed_scoring_and_export_seconds": time.perf_counter() - started,
               "counters_this_invocation": engine.stats if engine else None,
               "online_audited_windows_this_invocation": audited_windows,
               "audit_every_windows": args.audit_every_windows,
               "classification_applied": False}
    atomic_json(payload, args.output_dir / "summary.json")
    atomic_json(payload, args.output_dir / "metadata.json")
    write_progress(args.output_dir / "progress.json", started, new, metrics["database_windows"], expected,
                   last_shard, last_sha, last_index)
    conn.close()
    print(f"PRODUCTION {metrics['status']}: windows={metrics['database_windows']}/{expected}, "
          f"errors={metrics['scoring_errors']}, checks_failed={metrics['failed_checks']}")
    if interrupted is not None:
        raise interrupted
    return 0 if metrics["status"] == "PASS" else 1



def v5_self_test(a02_path: Path) -> None:
    """CPU structural tests. This is NOT a GPT-OSS/GPU equivalence certification."""
    run_self_test(a02_path)
    import torch
    torch.manual_seed(20260723)
    for dtype in (torch.float32, torch.bfloat16):
        for length in (1, 7, 33):
            # Integer-valued logits deliberately create abundant exact ties.
            logits = torch.randint(-4, 5, (1, length, 29)).to(dtype)
            labels = torch.randint(0, 29, (1, length))
            stats = {"ranked_tokens": 0, "observed_token_ties": 0, "full_sequence_tie_fallbacks": 0,
                     "argsort_sequences": 0, "same_logits_tokens_checked": 0, "same_logits_rank_mismatches": 0}
            actual = count_safe_rank_vector(logits, labels, torch, 4, stats, True)
            expected = reference_rank_vector(logits, labels, torch)
            if not torch.equal(actual, expected):
                raise AssertionError("Tie-safe rank differs from original argsort")
    logits = torch.arange(53, dtype=torch.float32).reshape(1, 1, 53).expand(1, 8, 53)
    labels = torch.randint(0, 53, (1, 8))
    stats = {"ranked_tokens": 0, "observed_token_ties": 0, "full_sequence_tie_fallbacks": 0,
             "argsort_sequences": 0, "same_logits_tokens_checked": 0, "same_logits_rank_mismatches": 0}
    count_safe_rank_vector(logits, labels, torch, 3, stats, True)
    if stats["full_sequence_tie_fallbacks"] != 0:
        raise AssertionError("Tie-free test unexpectedly required a sort")
    if equivalent_number(1.0, 1.001, 1e-6, 1e-6):
        raise AssertionError("Numerical gate accepted a large drift")
    if not equivalent_number(None, None, 1e-6, 1e-6):
        raise AssertionError("Exclusion comparison failed")
    toy_plan = {
        "a": {"n_expected_windows": 1, "logical_shard": 0, "space_by_tokens_total": 10,
              "fun_membership": 1, "cfun_membership": 0},
        "b": {"n_expected_windows": 10, "logical_shard": 1, "space_by_tokens_total": 1200,
              "fun_membership": 0, "cfun_membership": 1},
    }
    sampled = representative_keys(toy_plan, 5, 123)
    if sum(role == "uniform" for role in sampled.values()) != 5:
        raise AssertionError("Window sampling cardinality is wrong")
    # The learned global priority must reproduce the legacy all-equal row by construction.
    equal_logits = torch.zeros((1, 3, 17), dtype=torch.float32)
    equal_labels = torch.tensor([[0, 8, 16]], dtype=torch.long)
    cache: dict[str, Any] = {}
    ref_equal = reference_rank_vector(equal_logits, equal_labels, torch)
    got_equal = count_priority_rank_vector(equal_logits, equal_labels, torch, 2, "count-priority", cache, {})
    if not torch.equal(ref_equal, got_equal):
        raise AssertionError("Global tie-priority self-test failed on all-equal logits")
    print("B01-v5 CPU rank/tie/aggregation/sampling self-test: PASS (GPU profiling still required)")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="B01-v5: exact-tie profiling and single-sequence GPT-OSS NPR optimization")
    p.add_argument("--mode", choices=("smoke", "profile", "validate", "benchmark", "run", "finalize"), default="profile")
    p.add_argument("--project-root", type=Path, default=Path.cwd())
    p.add_argument("--a02-script", type=Path, default=Path("code-detection/score_snapshot_npr.py"))
    p.add_argument("--rank-script", type=Path, default=Path("code-detection/baselines/rank.py"))
    p.add_argument("--a09-root", type=Path, default=Path("output/snapshot_npr/run-x-a09"))
    p.add_argument("--a10-root", type=Path, default=Path("output/snapshot_npr/run-x-a10"))
    p.add_argument("--a13-root", type=Path, default=Path("output/snapshot_npr/run-x-a13"))
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--reference-db", type=Path, default=Path("output/snapshot_npr/run-x-b01/smoke/window_scores.sqlite3"))
    p.add_argument("--profile-summary", type=Path, default=Path("output/snapshot_npr/run-x-b01/v5/profile/profile_summary.json"))
    p.add_argument("--validation-summary", type=Path, default=Path("output/snapshot_npr/run-x-b01/v5/validation/validation_summary.json"))
    p.add_argument("--approval", type=Path, default=Path("output/snapshot_npr/run-x-b01/v5/benchmark/production_approval.json"))
    p.add_argument("--scope", choices=("fun", "cfun", "all"), default="all")
    p.add_argument("--shard-ids", default="all")
    p.add_argument("--scoring-model", default=SCORING_MODEL)
    p.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    p.add_argument("--expected-model-revision", default=DEFAULT_MODEL_REVISION)
    p.add_argument("--model-cache-dir", type=Path, default=Path("~/.cache/huggingface/hub").expanduser())
    p.add_argument("--device", default="cuda")
    p.add_argument("--two-gpu-max-memory", default="42GiB")
    p.add_argument("--per-gpu-max-memory", default="44GiB")
    p.add_argument("--cpu-max-memory", default="128GiB")
    p.add_argument("--system-label", default="unknown-host")
    p.add_argument("--allow-unsupported-gpu-topology", action="store_true")
    p.add_argument("--profile-windows", type=int, default=5)
    p.add_argument("--validation-windows", type=int, default=25)
    p.add_argument("--benchmark-windows", type=int, default=128)
    p.add_argument("--sampling-seed", type=int, default=20260723)
    p.add_argument("--batch-sizes", default="1", help="v5 exact-equivalence candidates; batch size >1 is intentionally forbidden")
    p.add_argument("--batch-size", type=int, default=1, help=argparse.SUPPRESS)
    p.add_argument("--candidate", default="", help="A passing candidate ID from validation_summary.json; default is its recommendation")
    p.add_argument("--max-batch-tokens", type=int, default=2048, help="B*max(length) cap, not truncation; longer singletons are preserved")
    p.add_argument("--rank-backend", choices=("auto", "count-priority", "count-index-asc", "count-index-desc", "count-safe", "argsort"), default="auto")
    p.add_argument("--rank-tile-tokens", type=int, default=32)
    p.add_argument("--use-cache", choices=("false", "model-default"), default="false")
    p.add_argument("--oom-policy", choices=("split", "abort"), default="split")
    p.add_argument("--atol", type=float, default=1e-6)
    p.add_argument("--rtol", type=float, default=1e-6)
    p.add_argument("--preferred-production-days", type=float, default=5.0)
    p.add_argument("--max-production-days", type=float, default=7.0)
    p.add_argument("--audit-every-windows", type=int, default=1000,
                   help="Production: deterministic key-hash 1/N sequential checks, plus first new window")
    p.add_argument("--progress-every-windows", type=int, default=5)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--retry-error-windows", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--self-test-only", action="store_true")
    args = p.parse_args()
    args.mode = "profile" if args.mode == "smoke" else args.mode
    try:
        args.batch_sizes = list(dict.fromkeys(int(x.strip()) for x in args.batch_sizes.split(",")))
    except ValueError:
        p.error("batch-sizes must be positive comma-separated integers")
    if not args.batch_sizes or any(x != 1 for x in args.batch_sizes):
        p.error("v5 requires batch-sizes=1; v4 established batch>1 numerical drift for GPT-OSS")
    for field in ("profile_windows", "validation_windows", "benchmark_windows", "rank_tile_tokens", "progress_every_windows", "audit_every_windows"):
        if getattr(args, field) < 1:
            p.error(f"{field} must be positive")
    if args.profile_windows > args.validation_windows:
        p.error("profile-windows must be <= validation-windows because profile draws from the v2 validation reference set")
    if args.max_batch_tokens < 0:
        p.error("max-batch-tokens must be zero (unlimited) or positive")
    if not 0 <= args.atol <= 1e-6 or not 0 <= args.rtol <= 1e-6:
        p.error("v5 does not relax equivalence tolerances above 1e-6; investigate drift instead")
    if not math.isfinite(args.preferred_production_days) or args.preferred_production_days <= 0:
        p.error("preferred-production-days must be a finite positive target")
    if not math.isfinite(args.max_production_days) or args.max_production_days <= 0:
        p.error("max-production-days must be a finite positive budget")
    if args.preferred_production_days > args.max_production_days:
        p.error("preferred-production-days must be <= max-production-days")
    if args.scoring_model != SCORING_MODEL:
        p.error("This experiment is specifically openai/gpt-oss-120b")
    if not args.model_revision or args.expected_model_revision != args.model_revision:
        p.error("Pin the same nonempty model and expected revisions")
    if args.mode == "finalize" and args.overwrite:
        p.error("Finalize never overwrites the checkpoint")
    return args


def resolve(project_root: Path, path: Path) -> Path:
    path = path.expanduser()
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def protect_output(args: argparse.Namespace) -> Any:
    """Lock the output directory and protect v2/A09 artifacts before any writes."""
    import fcntl
    out = args.output_dir
    if out == args.reference_db.parent or out in args.reference_db.parent.parents:
        raise RuntimeError("Refusing to write in/above the v2 reference directory")
    if out == args.a09_root or args.a09_root in out.parents or out in args.a09_root.parents:
        raise RuntimeError("Refusing to use an A09 input directory as output")
    db = out / "window_scores.sqlite3"
    if db.is_file():
        conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
        try:
            version = get_meta(conn, "script_version")
            if version != SCRIPT_VERSION:
                raise RuntimeError("Existing output checkpoint is not v5; it will NOT be overwritten")
        finally:
            conn.close()
    out.mkdir(parents=True, exist_ok=True)
    lock = (out / ".b01_v5.lock").open("a")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise RuntimeError(f"Another B01 process owns output directory {out}") from None
    return lock


def preflight_inputs(args: argparse.Namespace) -> tuple[dict[str, dict[str, Any]], Any, list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    for path, digest, label in ((args.a02_script, EXPECTED_A02_SHA256, "A02"),
                                (args.rank_script, EXPECTED_RANK_SHA256, "rank.py")):
        if not path.is_file():
            raise FileNotFoundError(f"Missing {label}: {path}")
        actual = sha256_file(path)
        add_check(checks, f"{label}_sha256", actual == digest, actual, digest)
        if actual != digest:
            raise RuntimeError(f"{label} SHA-256 changed; refusing scientific baseline drift")
    summary = load_json(args.a09_root / "plan" / "summary.json")
    for field, expected in (("status", "PASS"), ("config_fingerprint", EXPECTED_A09_CONFIG_FINGERPRINT),
                             ("input_manifest_sha256", EXPECTED_A05_MANIFEST_SHA256)):
        if summary.get(field) != expected:
            raise RuntimeError(f"A09 {field} mismatch")
        add_check(checks, f"a09_{field}", True, summary[field], expected)
    selected_shards = parse_shard_ids(args.shard_ids)
    plan = read_selected_unit_plan(args.a09_root / "plan" / "unique_primary_units.csv", args.scope, selected_shards)
    if not plan or any(u["n_expected_windows"] < 1 for u in plan.values()):
        raise RuntimeError("Empty or malformed selected scoring universe")
    if selected_shards is None:
        counts = EXPECTED_SCOPE_COUNTS[args.scope]
        if len(plan) != counts["units"] or sum(u["n_expected_windows"] for u in plan.values()) != counts["windows"]:
            raise RuntimeError("Full-scope unit/window counts differ from the frozen historical universe")
        if args.scope == "all":
            if (sum(u["fun_membership"] for u in plan.values()) != EXPECTED_SCOPE_COUNTS["fun"]["units"]
                    or sum(u["cfun_membership"] for u in plan.values()) != EXPECTED_SCOPE_COUNTS["cfun"]["units"]
                    or sum(u["fun_membership"] and u["cfun_membership"] for u in plan.values()) != EXPECTED_OVERLAP_UNITS):
                raise RuntimeError("FUN/C_FUN membership/overlap accounting changed")
    return plan, load_module(args.a02_script, "run_x_b01_v5_a02"), checks


def main() -> int:
    args = parse_args()
    args.project_root = args.project_root.expanduser().resolve()
    for field in ("a02_script", "rank_script", "a09_root", "a10_root", "a13_root", "output_dir",
                  "reference_db", "profile_summary", "validation_summary", "approval", "model_cache_dir"):
        setattr(args, field, resolve(args.project_root, getattr(args, field)))
    if args.self_test_only:
        v5_self_test(args.a02_script)
        return 0
    if args.mode in ("validate", "benchmark", "run") and args.rank_backend == "auto":
        if not args.profile_summary.is_file():
            raise FileNotFoundError("Run MODE=profile first; missing profile_summary.json")
        profile = load_json(args.profile_summary)
        selected = profile.get("recommended_tie_rule")
        if not profile.get("optimization_candidate_available") or selected not in PROFILE_TIE_RULES:
            raise RuntimeError("Profile found no exact non-sort tie rule; production optimization remains HOLD")
        args.rank_backend = selected
        print(f"Resolved rank backend from profile: {args.rank_backend}", flush=True)
    if args.mode == "run":
        if not args.approval.is_file() or not load_json(args.approval).get("production_ready"):
            raise RuntimeError("Production HOLD: run validation and a >=100-window representative benchmark first")
    if args.mode == "validate" and not args.profile_summary.is_file():
        raise FileNotFoundError("Run MODE=profile first; missing profile_summary.json")
    if args.mode == "benchmark" and not args.validation_summary.is_file():
        raise FileNotFoundError("Run MODE=validate first; missing validation_summary.json")
    lock = protect_output(args)
    started = time.perf_counter()
    # Invalidate only this stage's prior approval, never a v2 checkpoint.
    if args.mode in ("profile", "validate", "benchmark"):
        stage_summary = ("profile_summary.json" if args.mode == "profile" else
                         "validation_summary.json" if args.mode == "validate" else "benchmark_summary.json")
        atomic_json({"status": "RUNNING", "production_ready": False, "script_version": SCRIPT_VERSION},
                    args.output_dir / stage_summary)
        (args.output_dir / "production_approval.json").unlink(missing_ok=True)
    try:
        plan, a02, checks = preflight_inputs(args)
        legacy_rows = None
        records: list[dict[str, Any]] = []
        if args.mode in ("profile", "validate"):
            legacy_rows, _ = read_v2_reference(args)
            keys = list(legacy_rows)
            if args.mode == "profile":
                if args.profile_windows > len(keys):
                    raise RuntimeError(f"PROFILE_WINDOWS={args.profile_windows} exceeds available v2 reference windows={len(keys)}")
                if args.profile_windows == 1:
                    keys = [keys[len(keys) // 2]]
                else:
                    positions = [round(i * (len(keys) - 1) / (args.profile_windows - 1)) for i in range(args.profile_windows)]
                    keys = [keys[i] for i in positions]
                legacy_rows = {k: legacy_rows[k] for k in keys}
            roles = {key: "v2-reference" for key in keys}
        elif args.mode == "benchmark":
            validation = load_json(args.validation_summary)
            if validation.get("status") != "PASS" or validation.get("sample_windows", 0) < 25:
                raise RuntimeError("Need a successful >=25-window validation before benchmark")
            roles = representative_keys(plan, args.benchmark_windows, args.sampling_seed)
        else:
            roles = {}
        audited_shards = sorted({plan[k[0]]["logical_shard"] for k in roles} if roles
                                else {u["logical_shard"] for u in plan.values()})
        print(f"Preflight: mode={args.mode}, universe_units={len(plan)}, universe_windows="
              f"{sum(u['n_expected_windows'] for u in plan.values())}, audited_shards={len(audited_shards)}", flush=True)
        audit = validate_a09_shards(args.a09_root, audited_shards, EXPECTED_A09_CONFIG_FINGERPRINT)
        atomic_csv(audit, args.output_dir / "assigned_shard_audit.csv",
                   ["logical_shard", "data_path", "summary_path", "status", "error_messages"])
        if any(r["status"] != "PASS" for r in audit):
            raise RuntimeError("A09 shard integrity verification failed")
        if roles:
            records = fetch_sample_records(args, plan, roles)
            print(f"Sample: windows={len(records)}, unique_units={len({r['code_unit_sha256'] for r in records})}, "
                  f"shards={len(audited_shards)} (partial unit aggregates are explicitly marked)", flush=True)
        runtime, signature = None, None
        if args.mode != "finalize":
            runtime = load_gptoss_runtime(args)
            signature = runtime_signature(args, runtime)
            atomic_json({"script_version": SCRIPT_VERSION, "runtime_signature": signature,
                         "system_label": args.system_label, "mode": args.mode,
                         "rank_script": str(args.rank_script), "a02_script": str(args.a02_script),
                         "output_dir": str(args.output_dir), "classification_applied": False},
                        args.output_dir / "runtime_metadata.json")
        if args.mode == "profile":
            result = execute_profile(args, plan, a02, runtime, signature, records)
        elif args.mode == "validate":
            result = execute_validation(args, plan, a02, runtime, signature, records, legacy_rows)
        elif args.mode == "benchmark":
            result = execute_benchmark(args, plan, a02, runtime, signature, records)
        else:
            result = execute_production(args, plan, a02, runtime, signature, checks)
        print(f"{SCRIPT_VERSION}: mode={args.mode} wall_seconds={time.perf_counter()-started:.3f} exit_code={result}")
        return result
    except BaseException as error:
        payload = {"status": "INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "FAIL",
                   "mode": args.mode, "script_version": SCRIPT_VERSION, "production_ready": False,
                   "error_type": type(error).__name__, "error": str(error), "utc": utc_now()}
        atomic_json(payload, args.output_dir / "last_error.json")
        if args.mode in ("profile", "validate", "benchmark"):
            stage_summary = ("profile_summary.json" if args.mode == "profile" else
                             "validation_summary.json" if args.mode == "validate" else "benchmark_summary.json")
            atomic_json(payload, args.output_dir / stage_summary)
        raise
    finally:
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
