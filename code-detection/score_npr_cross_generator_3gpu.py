#!/usr/bin/env python3
"""score_npr_cross_generator_3gpu.py

Evaluate overlap-window DetectCodeGPT NPR across mixed-code generation sources.

This run-1c0d r158 branch separates two roles that were matched in the original
same-source benchmark:
  - target source: the LLM that generated the AGC examples in the benchmark
  - scoring model: the language model used by DetectCodeGPT NPR

The scoring algorithm is intentionally kept identical to the original
main_mixedcode_benchmark_overlap.py implementation so diagonal cells serve as
reproduction checks and off-diagonal cells measure cross-generator transfer.
The execution optimization loads one scoring model once and reuses it across
all requested target benchmarks. NPR definitions, perturbation count, seeds,
windowing, and weighted aggregation are unchanged.

The script supports either one visible GPU for the smaller scoring models or
multiple visible GPUs for models whose existing DetectCodeGPT loader uses
multi-GPU placement. GPU visibility is controlled by the shell wrapper through
CUDA_VISIBLE_DEVICES; model-loading behavior itself is not reimplemented here.

The benchmark input is expected under:

  mixedcode_benchmarks/<TARGET_SOURCE>/
    type01_110/
      mixed_code_001.py
      mixed_code_001.json
      ...
    ...

Each JSON sidecar contains per-procedure body offsets. The detector input is the
procedure body text extracted from those offsets, consistent with the existing
mixed-code overlap implementation.

Typical r158 usage is through the wrapper:

  SCORING_MODEL_KEY=starcoder2-7b CUDA_DEVICE=0 \
    bash proc_sh/run-1c0d-score-npr-cross-generator.sh

  SCORING_MODEL_KEY=gpt-oss CUDA_DEVICE=0,1,2 \
    bash proc_sh/run-1c0d-score-npr-cross-generator.sh

The per-procedure diagnostic Youden prediction follows sklearn ROC semantics
(score >= threshold). This does not alter the separately calibrated downstream
historical NPR rule.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import pickle
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from npr_overlap_core import (
    ALGORITHM_VERSION, PARTIAL_BODY_POLICY, aggregate_valid_frontier_weighted,
    chunk_literal_space, classify_window_validity, compute_aggregation_weights,
    compute_marginal_token_counts, derive_window_seed, sanitize_window_for_json,
    set_all_seeds, stable_sha256_text, validate_window_accounting,
)

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import torch
from loguru import logger
from tqdm import tqdm

# Reuse existing DetectCodeGPT project code.
from main import perturb_texts, setup_args
from baselines.rank import get_rank, get_ranks
from baselines.utils.preprocessing import preprocess_and_save
from baselines.utils.loadmodel import load_base_model_and_tokenizer


# ---------------------------------------------------------------------------
# Basic token / chunk helpers
# ---------------------------------------------------------------------------

def score_chunk(
    chunk_text: str,
    args: argparse.Namespace,
    model_config: Dict[str, Any],
    k: int,
    seed: int,
) -> Dict[str, Any]:
    """Score one overlap window with deterministic perturbation seeds."""
    set_all_seeds(seed, torch)
    orig_logrank = get_rank(chunk_text, args, model_config, log=True)
    p_texts = perturb_texts([chunk_text for _ in range(k)], args, model_config)
    p_ranks = get_ranks(p_texts, args, model_config, log=True)
    valid = [float(r) for r in p_ranks if math.isfinite(float(r))]
    mean_p = float(np.mean(valid)) if valid else float("nan")
    npr = mean_p / float(orig_logrank) if orig_logrank else float("nan")
    return {
        "npr": float(npr),
        "orig_logrank": float(orig_logrank),
        "mean_p_logrank": float(mean_p),
        "expected_perturbations": int(k),
        "valid_perturbation_scores": int(len(valid)),
    }


def score_body(
    body_text: str,
    args: argparse.Namespace,
    model_config: Dict[str, Any],
    k: int,
    chunk_len: int,
    min_chunk_tokens: int,
    random_seed: int,
) -> List[Dict[str, Any]]:
    """Score one body with v6 overlap-final-window and valid-frontier weighting."""
    if not body_text.strip():
        return []
    body_sha = stable_sha256_text(body_text)
    raw_chunks = chunk_literal_space(body_text, chunk_len)
    marginal_counts = compute_marginal_token_counts(raw_chunks)
    chunks: List[Dict[str, Any]] = []
    for chunk_idx, ((chunk_text, n_tok, start_tok, end_tok), marginal) in enumerate(
        zip(raw_chunks, marginal_counts)
    ):
        seed = derive_window_seed(random_seed, body_sha, chunk_idx)
        low_conf = n_tok < min_chunk_tokens or not chunk_text.strip()
        if low_conf:
            scored = {
                "npr": float("nan"), "orig_logrank": float("nan"),
                "mean_p_logrank": float("nan"), "expected_perturbations": int(k),
                "valid_perturbation_scores": 0,
            }
        else:
            scored = score_chunk(chunk_text, args, model_config, k, seed)
        valid, reason = classify_window_validity(scored)
        chunks.append({
            "chunk_idx": int(chunk_idx),
            "start_token_body": int(start_tok),
            "end_token_body": int(end_tok),
            "n_tokens": int(n_tok),
            "marginal_token_count": int(marginal),
            "window_seed": int(seed),
            "is_last_window": bool(chunk_idx == len(raw_chunks) - 1),
            "overlaps_previous_window": bool(marginal < n_tok),
            "low_conf": bool(low_conf),
            **scored,
            "window_npr_valid": bool(valid),
            "window_npr_invalid_reason": reason,
        })
    weights = compute_aggregation_weights(chunks)
    for chunk, weight in zip(chunks, weights):
        chunk["aggregation_weight_token_count"] = int(weight)
    validate_window_accounting(chunks, len(body_text.split(" ")))
    return [sanitize_window_for_json(chunk) for chunk in chunks]


def aggregate_npr(chunks: List[Dict[str, Any]], method: str) -> float:
    """Aggregate using v6 valid-frontier weighting; mean/max remain diagnostics."""
    valid = [c for c in chunks if bool(c.get("window_npr_valid")) and c.get("npr") is not None]
    if not valid:
        return float("nan")
    if method == "mean":
        return float(np.mean([float(c["npr"]) for c in valid]))
    if method == "max":
        return float(max(float(c["npr"]) for c in valid))
    return aggregate_valid_frontier_weighted(valid)


def n_scored(chunks: List[Dict[str, Any]]) -> int:
    return sum(1 for c in chunks if bool(c.get("window_npr_valid")))


def n_lowconf(chunks: List[Dict[str, Any]]) -> int:
    return sum(1 for c in chunks if bool(c.get("low_conf")))


# ---------------------------------------------------------------------------
# Benchmark loading
# ---------------------------------------------------------------------------

def load_mixedcode_functions(
    benchmark_root: Path,
    limit_files: Optional[int] = None,
    limit_functions: Optional[int] = None,
    only_group: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load all function-body examples from type*/mixed_code_*.json sidecars.

    If ``only_group`` is given (e.g. ``type10_200``), only that type folder is
    loaded and every loaded example's ``benchmark_type`` is forced to the group
    name. This lets you score a single merged group from scratch and is robust
    to sidecars whose stored ``benchmark_type`` differs from the folder they now
    live in (e.g. files merged in from a ``*_new1`` regeneration).
    """
    if not benchmark_root.exists():
        raise FileNotFoundError(f"Benchmark root not found: {benchmark_root}")

    if only_group:
        json_paths = sorted(benchmark_root.glob(f"{only_group}/mixed_code_*.json"))
        if not json_paths:
            available = sorted(p.name for p in benchmark_root.glob("type*") if p.is_dir())
            raise FileNotFoundError(
                f"No mixed_code_*.json found for group '{only_group}' under "
                f"{benchmark_root}. Available groups: {available}"
            )
    else:
        json_paths = sorted(benchmark_root.glob("type*/mixed_code_*.json"))
    if limit_files is not None:
        json_paths = json_paths[:limit_files]

    examples: List[Dict[str, Any]] = []

    for meta_path in json_paths:
        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)

        py_path = meta_path.with_suffix(".py")
        if not py_path.exists():
            # Use filename from JSON as a fallback, in case naming convention changes.
            py_path = meta_path.parent / meta.get("filename", meta_path.name.replace(".json", ".py"))
        if not py_path.exists():
            raise FileNotFoundError(f"Missing .py for {meta_path}: expected {py_path}")

        mixed_code = py_path.read_text(encoding="utf-8")
        # When restricting to a single group, label everything by that group so a
        # merged set (old + new files) aggregates as one bucket.
        benchmark_type = only_group or meta.get("benchmark_type", meta_path.parent.name)
        file_id = meta.get("file_id", None)
        filename = meta.get("filename", py_path.name)
        target_bucket_upper = meta.get("target_bucket_upper", None)

        for fmeta in meta.get("functions", []):
            start = int(fmeta["body_start_char"])
            end = int(fmeta["body_end_char"])
            body_text = mixed_code[start:end]

            examples.append({
                "benchmark_type": benchmark_type,
                "target_bucket_upper": target_bucket_upper,
                "file_id": file_id,
                "filename": filename,
                "meta_path": str(meta_path),
                "py_path": str(py_path),
                "function_id": fmeta.get("function_id"),
                "function_name": fmeta.get("function_name"),
                "role": fmeta.get("role"),
                "is_target": bool(fmeta.get("is_target")),
                "label": 1 if fmeta.get("role") == "AGC" or bool(fmeta.get("is_target")) else 0,
                "source_line_num": fmeta.get("source_line_num"),
                "source_idx": fmeta.get("source_idx"),
                "body_tokens": fmeta.get("body_tokens"),
                "body_tokens_regex": fmeta.get("body_tokens_regex"),
                "body_n_tokens_in_mixed_stream": fmeta.get("body_n_tokens_in_mixed_stream"),
                "function_start_char": fmeta.get("function_start_char"),
                "function_end_char": fmeta.get("function_end_char"),
                "body_start_char": start,
                "body_end_char": end,
                "body_n_chars": fmeta.get("body_n_chars", end - start),
                "body_start_token": fmeta.get("body_start_token"),
                "body_end_token": fmeta.get("body_end_token"),
                "body_text": body_text,
            })

            if limit_functions is not None and len(examples) >= limit_functions:
                return examples

    return examples


def preview_examples(examples: List[Dict[str, Any]], n: int = 3) -> None:
    print("\n" + "=" * 72)
    print("Preview detector inputs: body_text only")
    print("=" * 72)
    for ex in examples[:n]:
        print(
            f"[{ex['benchmark_type']}] {ex['filename']} "
            f"func={ex['function_name']} role={ex['role']} "
            f"body_tokens={ex['body_tokens']} char={ex['body_start_char']}:{ex['body_end_char']}"
        )
        print("-" * 72)
        print(ex["body_text"][:800])
        if len(ex["body_text"]) > 800:
            print("... [truncated]")
        print("-" * 72)


# ---------------------------------------------------------------------------
# Main.py library-arg bridge
# ---------------------------------------------------------------------------

def build_full_args(cli: argparse.Namespace) -> argparse.Namespace:
    """Build a fully-populated args namespace by reusing main.setup_args()."""
    injected = [
        "--base_model_name", cli.base_model_name,
        "--n_perturbation_list", str(cli.n_perturbation),
        "--perturb_type", cli.perturb_type,
        "--pct_words_masked", str(cli.pct_words_masked),
        "--span_length", str(cli.span_length),
        "--chunk_size", str(cli.chunk_size),
        "--n_perturbation_rounds", str(cli.n_perturbation_rounds),
        "--max_len", str(cli.chunk_len),
        "--DEVICE", cli.device,
        "--cache_dir", cli.cache_dir,
        "--output_name", cli.output_name,
    ]
    saved_argv = sys.argv
    try:
        sys.argv = ["main.py"] + injected
        args = setup_args()
    finally:
        sys.argv = saved_argv
    return args


# ---------------------------------------------------------------------------
# Reporting / output
# ---------------------------------------------------------------------------

def safe_float(x: Any) -> str:
    try:
        val = float(x)
    except Exception:
        return "nan"
    if math.isnan(val):
        return "nan"
    return f"{val:.6f}"


def compute_auc(y_true: List[int], y_score: List[float]) -> float:
    from sklearn.metrics import roc_auc_score

    if len(set(y_true)) < 2:
        return float("nan")
    return float(roc_auc_score(y_true, y_score))


def compute_youden(y_true: List[int], y_score: List[float]) -> Tuple[float, float, float, float]:
    """Return threshold, TPR, FPR, J. NaNs if unavailable."""
    from sklearn.metrics import roc_curve

    if len(set(y_true)) < 2:
        return float("nan"), float("nan"), float("nan"), float("nan")
    fpr, tpr, thresholds = roc_curve(y_true, y_score)
    j_stat = tpr - fpr
    best_idx = int(np.argmax(j_stat))
    return float(thresholds[best_idx]), float(tpr[best_idx]), float(fpr[best_idx]), float(j_stat[best_idx])


def report_group_auc(
    results: List[Dict[str, Any]],
    groups: Iterable[str],
    group_field: str = "benchmark_type",
) -> Dict[str, float]:
    """Print and return AUROC for one or more specific groups (buckets).

    ``results`` must already have an aggregated ``npr`` per function body
    (i.e. call this after summarize_and_save, which sets r["npr"]). The
    The target generation source is fixed while this helper summarizes one
    target benchmark, so a "group" here is a benchmark_type bucket such as
    ``type10_200``.
    """
    out: Dict[str, float] = {}
    print("\n" + "=" * 80)
    print(f"Per-group AUROC (group_field={group_field})")
    print("=" * 80)
    for group in groups:
        group = str(group).strip()
        if not group:
            continue
        sub = [
            r for r in results
            if str(r.get(group_field)) == group and not math.isnan(float(r.get("npr", float("nan"))))
        ]
        if not sub:
            print(f"  {group:14s} : no valid scored rows (group not found?)")
            out[group] = float("nan")
            continue

        y_true = [int(r["label"]) for r in sub]
        y_score = [float(r["npr"]) for r in sub]
        n_hwc = sum(1 for t in y_true if t == 0)
        n_agc = sum(1 for t in y_true if t == 1)
        auc = compute_auc(y_true, y_score)
        out[group] = auc
        print(
            f"  {group:14s} : AUROC={auc:.4f}  (n_hwc={n_hwc}, n_agc={n_agc}, "
            f"n_total={len(sub)})"
        )
    print("=" * 80)
    return out


def summarize_and_save(
    results: List[Dict[str, Any]],
    output_csv: Path,
    chunk_csv: Path,
    aggregate_method: str,
) -> None:
    """Aggregate scores, print summary, write function/chunk CSVs."""
    for r in results:
        r["npr"] = aggregate_npr(r["chunks"], aggregate_method)
        r["n_chunks"] = len(r["chunks"])
        r["n_scored_chunks"] = n_scored(r["chunks"])
        r["n_lowconf_chunks"] = n_lowconf(r["chunks"])
        r["n_invalid_chunks"] = r["n_chunks"] - r["n_scored_chunks"]
        r["partial_body_score"] = int(r["n_invalid_chunks"] > 0 and r["n_scored_chunks"] > 0)
        r["valid_npr_token_count"] = sum(int(c.get("aggregation_weight_token_count", 0)) for c in r["chunks"])
        total_tokens = sum(int(c.get("marginal_token_count", 0)) for c in r["chunks"])
        r["invalid_npr_token_count"] = total_tokens - r["valid_npr_token_count"]

    valid = [r for r in results if not math.isnan(r["npr"])]
    dropped = len(results) - len(valid)

    y_true = [int(r["label"]) for r in valid]
    y_score = [float(r["npr"]) for r in valid]

    auc = compute_auc(y_true, y_score) if valid else float("nan")
    thr, tpr, fpr, j = compute_youden(y_true, y_score) if valid else (float("nan"),) * 4

    print("\n" + "=" * 80)
    print(f"DetectCodeGPT NPR on mixed-code benchmark ({aggregate_method} over chunks)")
    print("=" * 80)
    print(f"Total function bodies: {len(results)}")
    print(f"Valid function scores: {len(valid)}")
    print(f"Dropped/no-score:      {dropped}")
    print(f"HWC n:                {sum(1 for r in valid if r['label'] == 0)}")
    print(f"AGC n:                {sum(1 for r in valid if r['label'] == 1)}")
    print(f"Overall AUROC:         {auc:.4f}")
    print(f"Youden threshold:      {thr:.4f}  TPR={tpr:.4f}  FPR={fpr:.4f}  J={j:.4f}")

    # Per-bucket summaries.
    print("\nPer-bucket summary:")
    print("  bucket        n_hwc  n_agc   auc     HWC_mean  AGC_mean")
    print("  " + "-" * 65)
    bucket_rows: List[Dict[str, Any]] = []
    for b in sorted({r["benchmark_type"] for r in valid}):
        br = [r for r in valid if r["benchmark_type"] == b]
        by = [int(r["label"]) for r in br]
        bs = [float(r["npr"]) for r in br]
        b_auc = compute_auc(by, bs)
        hwc = [float(r["npr"]) for r in br if r["label"] == 0]
        agc = [float(r["npr"]) for r in br if r["label"] == 1]
        hwc_mean = float(np.mean(hwc)) if hwc else float("nan")
        agc_mean = float(np.mean(agc)) if agc else float("nan")
        print(f"  {b:12s} {len(hwc):5d} {len(agc):6d}  {b_auc:6.4f}  {hwc_mean:8.4f}  {agc_mean:8.4f}")
        bucket_rows.append({
            "benchmark_type": b,
            "n_hwc": len(hwc),
            "n_agc": len(agc),
            "auc": b_auc,
            "hwc_mean": hwc_mean,
            "agc_mean": agc_mean,
        })

    print("=" * 80)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    chunk_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_csv.open("w", encoding="utf-8") as f:
        cols = [
            "target_source", "scoring_model_key", "scoring_model_name",
            "benchmark_type", "target_bucket_upper", "file_id", "filename",
            "function_id", "function_name", "role", "label", "is_target",
            "source_line_num", "source_idx",
            "body_tokens", "body_tokens_regex", "body_n_tokens_in_mixed_stream",
            "body_start_char", "body_end_char", "body_n_chars",
            "body_start_token", "body_end_token",
            "n_chunks", "n_scored_chunks", "n_lowconf_chunks",
            "n_invalid_chunks", "partial_body_score", "valid_npr_token_count", "invalid_npr_token_count",
            "npr", "predict_agc_youden", "meta_path", "py_path",
        ]
        f.write(",".join(cols) + "\n")
        for r in results:
            # sklearn.metrics.roc_curve reports operating points using score >= threshold.
            # This diagnostic column follows that convention. It does not change the
            # downstream historical NPR rule, which is calibrated and applied separately.
            pred = (not math.isnan(r["npr"])) and (not math.isnan(thr)) and (float(r["npr"]) >= thr)
            vals = [
                r.get("target_source"), r.get("scoring_model_key"), r.get("scoring_model_name"),
                r.get("benchmark_type"), r.get("target_bucket_upper"), r.get("file_id"), r.get("filename"),
                r.get("function_id"), r.get("function_name"), r.get("role"), r.get("label"), int(bool(r.get("is_target"))),
                r.get("source_line_num"), r.get("source_idx"),
                r.get("body_tokens"), r.get("body_tokens_regex"), r.get("body_n_tokens_in_mixed_stream"),
                r.get("body_start_char"), r.get("body_end_char"), r.get("body_n_chars"),
                r.get("body_start_token"), r.get("body_end_token"),
                r.get("n_chunks"), r.get("n_scored_chunks"), r.get("n_lowconf_chunks"),
                r.get("n_invalid_chunks"), r.get("partial_body_score"), r.get("valid_npr_token_count"), r.get("invalid_npr_token_count"),
                safe_float(r.get("npr")), int(pred), r.get("meta_path"), r.get("py_path"),
            ]
            f.write(",".join(json.dumps(v, ensure_ascii=False) if isinstance(v, str) else str(v) for v in vals) + "\n")
    logger.info(f"Saved per-function scores to: {output_csv}")

    with chunk_csv.open("w", encoding="utf-8") as f:
        cols = [
            "target_source", "scoring_model_key", "scoring_model_name",
            "benchmark_type", "file_id", "filename", "function_id", "function_name", "role", "label",
            "chunk_idx", "start_token_body", "end_token_body", "chunk_n_tokens",
            "marginal_token_count", "aggregation_weight_token_count", "window_seed",
            "is_last_window", "overlaps_previous_window", "window_npr_valid",
            "window_npr_invalid_reason", "valid_perturbation_scores",
            "low_conf", "npr", "orig_logrank", "mean_p_logrank",
            "body_tokens", "source_idx",
        ]
        f.write(",".join(cols) + "\n")
        for r in results:
            for c in r["chunks"]:
                vals = [
                    r.get("target_source"), r.get("scoring_model_key"), r.get("scoring_model_name"),
                    r.get("benchmark_type"), r.get("file_id"), r.get("filename"),
                    r.get("function_id"), r.get("function_name"), r.get("role"), r.get("label"),
                    c.get("chunk_idx"), c.get("start_token_body"), c.get("end_token_body"), c.get("n_tokens"),
                    c.get("marginal_token_count"), c.get("aggregation_weight_token_count"), c.get("window_seed"),
                    int(bool(c.get("is_last_window"))), int(bool(c.get("overlaps_previous_window"))),
                    int(bool(c.get("window_npr_valid"))), c.get("window_npr_invalid_reason"),
                    c.get("valid_perturbation_scores"), int(bool(c.get("low_conf"))), safe_float(c.get("npr")),
                    safe_float(c.get("orig_logrank")), safe_float(c.get("mean_p_logrank")),
                    r.get("body_tokens"), r.get("source_idx"),
                ]
                f.write(",".join(json.dumps(v, ensure_ascii=False) if isinstance(v, str) else str(v) for v in vals) + "\n")
    logger.info(f"Saved per-chunk detail to: {chunk_csv}")

    target_source = str(results[0].get("target_source", "")) if results else ""
    scoring_model_key = str(results[0].get("scoring_model_key", "")) if results else ""
    scoring_model_name = str(results[0].get("scoring_model_name", "")) if results else ""

    summary_csv = output_csv.with_name(output_csv.stem + "_bucket_summary.csv")
    with summary_csv.open("w", encoding="utf-8") as f:
        f.write(
            "target_source,scoring_model_key,scoring_model_name,"
            "benchmark_type,n_hwc,n_agc,auc,hwc_mean,agc_mean\n"
        )
        for r in bucket_rows:
            f.write(
                f"{target_source},{scoring_model_key},{scoring_model_name},"
                f"{r['benchmark_type']},{r['n_hwc']},{r['n_agc']},"
                f"{safe_float(r['auc'])},{safe_float(r['hwc_mean'])},{safe_float(r['agc_mean'])}\n"
            )
    logger.info(f"Saved bucket summary to: {summary_csv}")

    overall_summary_csv = output_csv.with_name(output_csv.stem + "_overall_summary.csv")
    with overall_summary_csv.open("w", encoding="utf-8") as f:
        f.write(
            "target_source,scoring_model_key,scoring_model_name,"
            "n_total,n_valid,n_hwc,n_agc,auc,youden_threshold,tpr,fpr,youden_j\n"
        )
        f.write(
            f"{target_source},{scoring_model_key},{scoring_model_name},"
            f"{len(results)},{len(valid)},"
            f"{sum(1 for r in valid if r['label'] == 0)},"
            f"{sum(1 for r in valid if r['label'] == 1)},"
            f"{safe_float(auc)},{safe_float(thr)},{safe_float(tpr)},"
            f"{safe_float(fpr)},{safe_float(j)}\n"
        )
    logger.info(f"Saved overall summary to: {overall_summary_csv}")


# ---------------------------------------------------------------------------
# Multi-target scoring runtime
# ---------------------------------------------------------------------------

SUPPORTED_TARGET_SOURCES = (
    "codellama-7b",
    "starcoder2-7b",
    "starcoder2-15b-instruct-v0.1",
    "gpt-oss",
    "gemma",
)


def parse_target_sources(value: str) -> List[str]:
    """Parse 'all' or a comma-separated target-source list in canonical order."""
    raw = str(value).strip()
    if not raw or raw.lower() == "all":
        return list(SUPPORTED_TARGET_SOURCES)

    requested = [x.strip() for x in raw.split(",") if x.strip()]
    unknown = [x for x in requested if x not in SUPPORTED_TARGET_SOURCES]
    if unknown:
        raise ValueError(
            f"Unsupported target source(s): {unknown}. "
            f"Supported: {list(SUPPORTED_TARGET_SOURCES)}"
        )

    # De-duplicate while preserving the caller's order.
    seen = set()
    ordered: List[str] = []
    for source in requested:
        if source not in seen:
            seen.add(source)
            ordered.append(source)
    return ordered


def validate_benchmark_counts(examples: List[Dict[str, Any]], target_source: str) -> None:
    """Fail fast if a target benchmark is not the expected 300-procedure design."""
    by_bucket: Dict[str, Dict[str, int]] = {}
    for ex in examples:
        b = str(ex["benchmark_type"])
        by_bucket.setdefault(b, {"HWC": 0, "AGC": 0})
        role = str(ex.get("role"))
        by_bucket[b][role] = by_bucket[b].get(role, 0) + 1

    n_hwc = sum(1 for ex in examples if int(ex["label"]) == 0)
    n_agc = sum(1 for ex in examples if int(ex["label"]) == 1)
    print(f"\nTarget benchmark validation: {target_source}")
    for b in sorted(by_bucket):
        print(
            f"  {b}: HWC={by_bucket[b].get('HWC', 0)} "
            f"AGC={by_bucket[b].get('AGC', 0)}"
        )

    if len(examples) != 300 or n_hwc != 150 or n_agc != 150:
        raise RuntimeError(
            f"Benchmark QC failed for {target_source}: "
            f"n_total={len(examples)}, n_hwc={n_hwc}, n_agc={n_agc}; "
            "expected 300 total with 150 HWC and 150 AGC."
        )

    if len(by_bucket) != 10:
        raise RuntimeError(
            f"Benchmark QC failed for {target_source}: expected 10 buckets, "
            f"found {len(by_bucket)}."
        )

    bad_buckets = [
        b for b, counts in by_bucket.items()
        if counts.get("HWC", 0) != 15 or counts.get("AGC", 0) != 15
    ]
    if bad_buckets:
        raise RuntimeError(
            f"Benchmark QC failed for {target_source}: each bucket must contain "
            f"15 HWC and 15 AGC; bad buckets={bad_buckets}."
        )


def build_target_paths(
    output_root: Path,
    scoring_model_key: str,
    target_source: str,
) -> Dict[str, Any]:
    """Return all per-target artifact paths using explicit scorer/target provenance."""
    output_name = f"npr-xgen_score-{scoring_model_key}_target-{target_source}"
    score_csv = output_root / f"npr_scores_{output_name}.csv"
    return {
        "output_name": output_name,
        "score_csv": score_csv,
        "chunk_csv": output_root / f"npr_chunks_{output_name}.csv",
        "cache": output_root / f"results_cache_{output_name}.pkl",
        "bucket_summary": score_csv.with_name(score_csv.stem + "_bucket_summary.csv"),
        "overall_summary": score_csv.with_name(score_csv.stem + "_overall_summary.csv"),
    }


def target_artifacts_complete(paths: Dict[str, Any]) -> bool:
    """A target is complete only when every expected production artifact exists."""
    keys = ("score_csv", "chunk_csv", "cache", "bucket_summary", "overall_summary")
    return all(paths[k].is_file() and paths[k].stat().st_size > 0 for k in keys)


def load_scoring_runtime(cli: argparse.Namespace) -> Tuple[argparse.Namespace, Dict[str, Any]]:
    """Load the NPR scoring model exactly once for all requested target sources."""
    args = build_full_args(cli)
    logger.info(
        f"Before model load: CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')}, "
        f"args.DEVICE={args.DEVICE}"
    )
    cache_dir, _, _ = preprocess_and_save(args)
    model_config: Dict[str, Any] = {"cache_dir": cache_dir}
    logger.info("Loading base scoring model once for the full target-source row...")
    model_config = load_base_model_and_tokenizer(args, model_config)
    logger.info("Base scoring model loaded; reusing it across requested target sources.")
    return args, model_config


def score_examples_with_runtime(
    examples: List[Dict[str, Any]],
    target_source: str,
    cli: argparse.Namespace,
    args: argparse.Namespace,
    model_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Score one target benchmark using an already-loaded scoring model."""
    results: List[Dict[str, Any]] = []
    desc = f"Scoring {target_source} function bodies"
    for ex in tqdm(examples, desc=desc):
        chunks = score_body(
            ex["body_text"],
            args=args,
            model_config=model_config,
            k=cli.n_perturbation,
            chunk_len=cli.chunk_len,
            min_chunk_tokens=cli.min_chunk_tokens,
            random_seed=cli.random_seed,
        )
        r = dict(ex)
        r["target_source"] = target_source
        r["scoring_model_key"] = cli.scoring_model_key
        r["scoring_model_name"] = cli.base_model_name
        r.pop("body_text", None)
        r["chunks"] = chunks
        results.append(r)
    return results


def compute_overall_row(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute the same overall metrics written by summarize_and_save."""
    valid = [r for r in results if not math.isnan(float(r.get("npr", float("nan"))))]
    y_true = [int(r["label"]) for r in valid]
    y_score = [float(r["npr"]) for r in valid]
    auc = compute_auc(y_true, y_score) if valid else float("nan")
    thr, tpr, fpr, j = compute_youden(y_true, y_score) if valid else (float("nan"),) * 4
    return {
        "n_total": len(results),
        "n_valid": len(valid),
        "n_hwc": sum(1 for r in valid if int(r["label"]) == 0),
        "n_agc": sum(1 for r in valid if int(r["label"]) == 1),
        "auc": auc,
        "youden_threshold": thr,
        "tpr": tpr,
        "fpr": fpr,
        "youden_j": j,
    }


def read_existing_overall_summary(path: Path) -> Dict[str, Any]:
    """Read the single data row from an existing overall-summary CSV."""
    import csv

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if len(rows) != 1:
        raise RuntimeError(f"Expected one row in {path}, found {len(rows)}")
    row = rows[0]
    return {
        "n_total": int(row["n_total"]),
        "n_valid": int(row["n_valid"]),
        "n_hwc": int(row["n_hwc"]),
        "n_agc": int(row["n_agc"]),
        "auc": float(row["auc"]),
        "youden_threshold": float(row["youden_threshold"]),
        "tpr": float(row["tpr"]),
        "fpr": float(row["fpr"]),
        "youden_j": float(row["youden_j"]),
    }


def write_row_summary(
    row_summary_csv: Path,
    scoring_model_key: str,
    scoring_model_name: str,
    row_records: List[Dict[str, Any]],
) -> None:
    """Write one compact row summary that can later be combined into the 5 x 5 matrix."""
    row_summary_csv.parent.mkdir(parents=True, exist_ok=True)
    ordered = {r["target_source"]: r for r in row_records}
    with row_summary_csv.open("w", encoding="utf-8") as f:
        f.write(
            "scoring_model_key,scoring_model_name,target_source,status,elapsed_seconds,"
            "n_total,n_valid,n_hwc,n_agc,auc,youden_threshold,tpr,fpr,youden_j\n"
        )
        for target in SUPPORTED_TARGET_SOURCES:
            if target not in ordered:
                continue
            r = ordered[target]
            f.write(
                f"{scoring_model_key},{scoring_model_name},{target},{r['status']},"
                f"{r['elapsed_seconds']:.3f},{r['n_total']},{r['n_valid']},"
                f"{r['n_hwc']},{r['n_agc']},{safe_float(r['auc'])},"
                f"{safe_float(r['youden_threshold'])},{safe_float(r['tpr'])},"
                f"{safe_float(r['fpr'])},{safe_float(r['youden_j'])}\n"
            )
    logger.info(f"Saved scorer-row summary to: {row_summary_csv}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate one NPR scoring model across multiple mixed-code generation "
            "sources on the r158 execution branch while loading the scoring model only once."
        )
    )
    parser.add_argument(
        "--scoring_model_key", required=True,
        help="Short label for the model used to compute NPR scores."
    )
    parser.add_argument(
        "--target_sources", default="all",
        help="'all' or comma-separated generation-source keys."
    )
    parser.add_argument(
        "--benchmark_parent", required=True,
        help="Parent directory containing one benchmark folder per target source."
    )
    parser.add_argument("--base_model_name", type=str, default="bigcode/starcoder2-7b")
    parser.add_argument(
        "--output_root", required=True,
        help="Directory for per-target caches, CSVs, and scorer-row summary."
    )
    parser.add_argument("--n_perturbation", type=int, default=50,
                        help="Perturbed copies per overlap window. Production default: 50.")
    parser.add_argument("--pct_words_masked", type=float, default=0.5)
    parser.add_argument("--span_length", type=int, default=2)
    parser.add_argument(
        "--chunk_size", type=int, default=10,
        help=(
            "Batch size used by perturb_texts. Production default remains 10; "
            "changing this is an execution optimization and should be validated separately."
        )
    )
    parser.add_argument("--n_perturbation_rounds", type=int, default=1)
    parser.add_argument("--perturb_type", type=str, default="random-insert-space+newline")
    parser.add_argument("--chunk_len", type=int, default=128)
    parser.add_argument("--min_chunk_tokens", type=int, default=1)
    parser.add_argument("--aggregate", choices=["weighted_mean", "mean", "max"], default="weighted_mean")
    parser.add_argument("--random_seed", type=int, default=20260723)
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--cache_dir", type=str, default="~/.cache/huggingface/hub")
    parser.add_argument(
        "--skip_existing", action="store_true",
        help="Skip a target only when all five expected production artifacts already exist."
    )
    parser.add_argument(
        "--count_only", action="store_true",
        help="Validate every requested target benchmark and exit before model loading."
    )
    cli = parser.parse_args()

    targets = parse_target_sources(cli.target_sources)
    benchmark_parent = Path(os.path.expanduser(cli.benchmark_parent))
    output_root = Path(os.path.expanduser(cli.output_root))
    output_root.mkdir(parents=True, exist_ok=True)

    # build_full_args expects an output_name attribute. It has no role in the
    # scorer/target artifact names; this row-level value is only for imported
    # DetectCodeGPT setup compatibility.
    cli.output_name = f"npr-xgen-row_score-{cli.scoring_model_key}"

    print("=" * 80)
    print("score_npr_cross_generator_3gpu.py")
    print("=" * 80)
    print(f"scoring_model_key    : {cli.scoring_model_key}")
    print(f"base_model_name      : {cli.base_model_name}")
    print(f"target_sources       : {','.join(targets)}")
    print(f"benchmark_parent     : {benchmark_parent}")
    print(f"output_root          : {output_root}")
    print(f"device               : {cli.device}")
    print(f"chunk_len            : {cli.chunk_len}")
    print(f"chunk_size           : {cli.chunk_size}")
    print(f"aggregate            : {cli.aggregate}")
    print(f"n_perturbation       : {cli.n_perturbation}")
    print(f"random_seed          : {cli.random_seed}")
    print(f"algorithm_version    : {ALGORITHM_VERSION}")
    print(f"partial_body_policy  : {PARTIAL_BODY_POLICY}")
    print(f"perturb_type         : {cli.perturb_type}")
    print(f"skip_existing        : {cli.skip_existing}")
    print("=" * 80)

    # Fail fast on all target datasets before paying the model-loading cost.
    target_roots: Dict[str, Path] = {}
    for target in targets:
        root = benchmark_parent / target
        target_roots[target] = root
        examples = load_mixedcode_functions(root)
        validate_benchmark_counts(examples, target)
        del examples

    if cli.count_only:
        print("\nCount-only validation completed; model was not loaded.")
        return

    pending_targets: List[str] = []
    row_records: List[Dict[str, Any]] = []
    for target in targets:
        paths = build_target_paths(output_root, cli.scoring_model_key, target)
        if cli.skip_existing and target_artifacts_complete(paths):
            metrics = read_existing_overall_summary(paths["overall_summary"])
            row_records.append({
                "target_source": target,
                "status": "SKIPPED_EXISTING",
                "elapsed_seconds": 0.0,
                **metrics,
            })
            logger.info(f"Skipping completed target: {target}")
        else:
            pending_targets.append(target)

    row_summary_csv = output_root / f"npr_xgen_row_summary_score-{cli.scoring_model_key}.csv"
    if row_records:
        write_row_summary(
            row_summary_csv,
            cli.scoring_model_key,
            cli.base_model_name,
            row_records,
        )

    if not pending_targets:
        print("\nAll requested targets are already complete; model was not loaded.")
        return

    args, model_config = load_scoring_runtime(cli)
    row_start = time.perf_counter()

    for target_idx, target in enumerate(pending_targets, start=1):
        target_start = time.perf_counter()
        paths = build_target_paths(output_root, cli.scoring_model_key, target)
        print("\n" + "=" * 80)
        print(
            f"TARGET {target_idx}/{len(pending_targets)}: "
            f"scorer={cli.scoring_model_key} -> source={target}"
        )
        print(f"benchmark_root       : {target_roots[target]}")
        print(f"procedure_score_csv  : {paths['score_csv']}")
        print(f"window_score_csv     : {paths['chunk_csv']}")
        print(f"results_cache        : {paths['cache']}")
        print("=" * 80)

        # Match the original per-cell output-name convention during scoring.
        # The loaded model is retained; only the non-model run label changes.
        cli.output_name = str(paths["output_name"])
        args.output_name = str(paths["output_name"])

        examples = load_mixedcode_functions(target_roots[target])
        results = score_examples_with_runtime(
            examples=examples,
            target_source=target,
            cli=cli,
            args=args,
            model_config=model_config,
        )

        paths["cache"].parent.mkdir(parents=True, exist_ok=True)
        with paths["cache"].open("wb") as f:
            pickle.dump(results, f)
        logger.info(f"Cached per-function chunk results to: {paths['cache']}")

        summarize_and_save(
            results,
            paths["score_csv"],
            paths["chunk_csv"],
            cli.aggregate,
        )
        metrics = compute_overall_row(results)
        elapsed = time.perf_counter() - target_start
        row_records.append({
            "target_source": target,
            "status": "PASS",
            "elapsed_seconds": elapsed,
            **metrics,
        })
        write_row_summary(
            row_summary_csv,
            cli.scoring_model_key,
            cli.base_model_name,
            row_records,
        )

        print(
            f"Completed target {target}: AUROC={metrics['auc']:.6f}, "
            f"valid={metrics['n_valid']}/{metrics['n_total']}, "
            f"elapsed={elapsed:.1f}s"
        )

        # Release target-specific Python objects while preserving the loaded model.
        del results
        del examples
        gc.collect()
        torch.cuda.empty_cache()

    row_elapsed = time.perf_counter() - row_start
    print("\n" + "=" * 80)
    print("NPR cross-generator scorer row completed")
    print(f"scoring_model_key    : {cli.scoring_model_key}")
    print(f"completed targets    : {','.join(pending_targets)}")
    print(f"row elapsed seconds  : {row_elapsed:.1f}")
    print(f"row summary          : {row_summary_csv}")
    print("=" * 80)


if __name__ == "__main__":
    main()
