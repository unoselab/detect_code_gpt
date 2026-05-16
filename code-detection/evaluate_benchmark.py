#!/usr/bin/env python3
"""
Evaluate per-chunk benchmark CSV at different NPR thresholds.

Reads the CSV produced by run_batch_benchmark (in main.py) and reports:
  - Confusion matrix, precision, recall, F1 at user-given thresholds
  - Best-F1 threshold found by sweep
  - Per-record breakdown to spot pathological cases

Usage:
    python evaluate_benchmark.py
    python evaluate_benchmark.py --csv /path/to/results.csv
    python evaluate_benchmark.py --thresholds 1.20 1.30 1.3875 1.50 1.60
    python evaluate_benchmark.py --truth_ratio 0.8   # stricter "is MGC"
    python evaluate_benchmark.py --per_record
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------------------------------------------------------
# Defaults
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path("~/project-workspace/detect_code_gpt").expanduser()
DEFAULT_CSV = (PROJECT_ROOT / "logs" /
               "benchmark_results_benchmark_level1_codellama-7b-hf.csv")

DEFAULT_THRESHOLDS = [1.10, 1.15, 1.20, 1.25, 1.30, 1.35, 1.3875, 1.45, 1.50, 1.55, 1.60]


# -----------------------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------------------

def load_chunks(csv_path: Path) -> List[Dict[str, Any]]:
    """Load CSV rows, coercing types. Returns list of chunk dicts.

    Rows with low_conf=1 are kept (caller decides whether to use them).
    NaN NPR values become Python float('nan').
    """
    rows = []
    with csv_path.open("r") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {}
            for k, v in raw.items():
                if v == "":
                    row[k] = None
                    continue
                # Try int first, then float, else keep as string
                if k in ("record_id", "chunk_idx", "start_token", "end_token",
                         "chunk_n_tokens", "low_conf", "mgc_n_tokens",
                         "n_chunk_tokens_in_mgc", "overlaps_mgc_by_tokens",
                         "source_line_no", "predict_mgc_youden",
                         "predict_mgc_highconf"):
                    try:
                        row[k] = int(v)
                    except ValueError:
                        row[k] = None
                elif k in ("npr", "orig_logrank", "mean_p_logrank",
                           "intersect_ratio_chunk", "intersect_ratio_mgc"):
                    try:
                        row[k] = float(v)
                    except ValueError:
                        row[k] = float("nan")
                else:
                    row[k] = v
            rows.append(row)
    return rows


# -----------------------------------------------------------------------------
# Metric computation
# -----------------------------------------------------------------------------

def is_scorable(chunk: Dict[str, Any]) -> bool:
    """Return True if this chunk can contribute to metrics.

    Excludes low_conf chunks (whose NPR is NaN and therefore unpredictable).
    """
    if chunk.get("low_conf"):
        return False
    npr = chunk.get("npr")
    if npr is None or math.isnan(npr):
        return False
    return True


def truth_label(chunk: Dict[str, Any], truth_ratio: float = 0.5) -> bool:
    """Return True if this chunk should be considered MGC ground truth.

    truth_ratio is the minimum intersect_ratio_chunk for a chunk to count as MGC.
    Default 0.5 matches what was stored in overlaps_mgc_by_tokens.
    """
    return chunk["intersect_ratio_chunk"] > truth_ratio


def confusion_at_threshold(chunks: List[Dict[str, Any]],
                           threshold: float,
                           truth_ratio: float = 0.5) -> Dict[str, int]:
    """Compute TP/FP/FN/TN counts at a given NPR threshold."""
    tp = fp = fn = tn = 0
    for c in chunks:
        if not is_scorable(c):
            continue
        predicted = c["npr"] > threshold
        truth = truth_label(c, truth_ratio)
        if predicted and truth:
            tp += 1
        elif predicted and not truth:
            fp += 1
        elif not predicted and truth:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def metrics_from_confusion(conf: Dict[str, int]) -> Dict[str, float]:
    """Compute precision/recall/F1/accuracy from a confusion dict."""
    tp, fp, fn, tn = conf["tp"], conf["fp"], conf["fn"], conf["tn"]
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    acc = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0
    return {"precision": p, "recall": r, "f1": f1, "accuracy": acc}


# -----------------------------------------------------------------------------
# Output formatters
# -----------------------------------------------------------------------------

def format_single_threshold(threshold: float, conf: Dict[str, int],
                             metrics: Dict[str, float]) -> str:
    total = sum(conf.values())
    return (
        f"  threshold = {threshold:.4f}  (n_scorable = {total})\n"
        f"    Confusion: TP={conf['tp']:>3}  FP={conf['fp']:>3}  "
        f"FN={conf['fn']:>3}  TN={conf['tn']:>3}\n"
        f"    Precision: {metrics['precision']:.4f}  "
        f"Recall: {metrics['recall']:.4f}  "
        f"F1: {metrics['f1']:.4f}  "
        f"Accuracy: {metrics['accuracy']:.4f}"
    )


def format_threshold_sweep(chunks: List[Dict[str, Any]],
                            thresholds: List[float],
                            truth_ratio: float = 0.5) -> str:
    lines = []
    lines.append(f"  {'threshold':>10}  {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4}  "
                 f"{'precision':>9}  {'recall':>7}  {'F1':>7}  {'accuracy':>8}")
    lines.append("  " + "-" * 78)
    for t in thresholds:
        conf = confusion_at_threshold(chunks, t, truth_ratio)
        m = metrics_from_confusion(conf)
        lines.append(
            f"  {t:>10.4f}  {conf['tp']:>4} {conf['fp']:>4} "
            f"{conf['fn']:>4} {conf['tn']:>4}  "
            f"{m['precision']:>9.4f}  {m['recall']:>7.4f}  "
            f"{m['f1']:>7.4f}  {m['accuracy']:>8.4f}"
        )
    return "\n".join(lines)


def find_best_f1_threshold(chunks: List[Dict[str, Any]],
                            truth_ratio: float = 0.5,
                            n_candidates: int = 200) -> Tuple[float, Dict[str, int], Dict[str, float]]:
    """Sweep many thresholds, return the one maximizing F1."""
    scorable = [c for c in chunks if is_scorable(c)]
    if not scorable:
        return 0.0, {"tp": 0, "fp": 0, "fn": 0, "tn": 0}, {"precision": 0, "recall": 0, "f1": 0, "accuracy": 0}

    nprs = [c["npr"] for c in scorable]
    lo, hi = min(nprs), max(nprs)
    if lo == hi:
        return lo, {"tp": 0, "fp": 0, "fn": 0, "tn": 0}, {"precision": 0, "recall": 0, "f1": 0, "accuracy": 0}

    best_f1 = -1.0
    best_t = lo
    best_conf = best_m = None
    for i in range(n_candidates + 1):
        t = lo + (hi - lo) * i / n_candidates
        conf = confusion_at_threshold(scorable, t, truth_ratio)
        m = metrics_from_confusion(conf)
        if m["f1"] > best_f1:
            best_f1 = m["f1"]
            best_t = t
            best_conf = conf
            best_m = m
    return best_t, best_conf, best_m


def per_record_summary(chunks: List[Dict[str, Any]],
                        threshold: float,
                        truth_ratio: float = 0.5) -> List[Dict[str, Any]]:
    """One row per record: precision/recall/F1 within that record."""
    by_record = defaultdict(list)
    for c in chunks:
        by_record[c["record_id"]].append(c)
    out = []
    for rid in sorted(by_record.keys()):
        conf = confusion_at_threshold(by_record[rid], threshold, truth_ratio)
        m = metrics_from_confusion(conf)
        n_chunks = len(by_record[rid])
        out.append({
            "record_id": rid,
            "n_chunks": n_chunks,
            "tp": conf["tp"], "fp": conf["fp"], "fn": conf["fn"], "tn": conf["tn"],
            "precision": m["precision"], "recall": m["recall"], "f1": m["f1"],
        })
    return out


def format_per_record_summary(records: List[Dict[str, Any]],
                                top_n_worst: int = 10) -> str:
    """Show top-N worst records (lowest F1 with at least one MGC chunk)."""
    has_truth = [r for r in records if r["tp"] + r["fn"] > 0]
    if not has_truth:
        return "  No records have ground-truth MGC chunks (intersect_ratio_chunk > truth_ratio)."

    sorted_recs = sorted(has_truth, key=lambda r: (r["f1"], -r["fn"]))

    lines = []
    lines.append(f"  Bottom {min(top_n_worst, len(sorted_recs))} records by F1 "
                 f"(of {len(has_truth)} with any true MGC):")
    lines.append(f"  {'record':>6}  {'n_chunks':>8}  {'TP':>3} {'FP':>3} {'FN':>3} {'TN':>3}  "
                 f"{'precision':>9}  {'recall':>7}  {'F1':>7}")
    lines.append("  " + "-" * 70)
    for r in sorted_recs[:top_n_worst]:
        lines.append(
            f"  {r['record_id']:>6}  {r['n_chunks']:>8}  "
            f"{r['tp']:>3} {r['fp']:>3} {r['fn']:>3} {r['tn']:>3}  "
            f"{r['precision']:>9.4f}  {r['recall']:>7.4f}  {r['f1']:>7.4f}"
        )
    n_perfect = sum(1 for r in has_truth if r["f1"] == 1.0)
    n_total_failure = sum(1 for r in has_truth if r["f1"] == 0.0)
    lines.append("")
    lines.append(f"  Records with F1=1.0: {n_perfect} / {len(has_truth)}")
    lines.append(f"  Records with F1=0.0: {n_total_failure} / {len(has_truth)}")
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate per-chunk benchmark CSV at various NPR thresholds."
    )
    parser.add_argument("--csv", type=str, default=str(DEFAULT_CSV),
                        help="Path to benchmark_results CSV.")
    parser.add_argument("--thresholds", type=float, nargs="+", default=DEFAULT_THRESHOLDS,
                        help="NPR thresholds to evaluate.")
    parser.add_argument("--truth_ratio", type=float, default=0.5,
                        help="Minimum intersect_ratio_chunk for a chunk to be MGC ground truth.")
    parser.add_argument("--per_record", action="store_true",
                        help="Also show per-record breakdown at best-F1 threshold.")
    parser.add_argument("--top_n_worst", type=int, default=10,
                        help="How many worst-F1 records to show in --per_record output.")
    args = parser.parse_args()

    csv_path = Path(args.csv).expanduser()
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")

    chunks = load_chunks(csv_path)
    n_total = len(chunks)
    n_low_conf = sum(1 for c in chunks if c.get("low_conf"))
    n_scorable = sum(1 for c in chunks if is_scorable(c))
    n_truth_pos = sum(1 for c in chunks if is_scorable(c) and truth_label(c, args.truth_ratio))

    print("=" * 78)
    print(f"  Benchmark Evaluation: {csv_path}")
    print("=" * 78)
    print(f"  Total chunks:              {n_total}")
    print(f"  Low-confidence (excluded): {n_low_conf}")
    print(f"  Scorable chunks:           {n_scorable}")
    print(f"  Truth-positive chunks:     {n_truth_pos}  "
          f"(intersect_ratio_chunk > {args.truth_ratio})")
    print(f"  Truth-negative chunks:     {n_scorable - n_truth_pos}")
    print()

    # --- Threshold sweep ---
    print("Threshold sweep:")
    print(format_threshold_sweep(chunks, args.thresholds, args.truth_ratio))
    print()

    # --- Best-F1 threshold ---
    best_t, best_conf, best_m = find_best_f1_threshold(chunks, args.truth_ratio)
    print("Best F1 from sweep over [min(NPR), max(NPR)]:")
    print(format_single_threshold(best_t, best_conf, best_m))
    print()

    # --- Per-record summary (optional) ---
    if args.per_record:
        print(f"Per-record breakdown at best-F1 threshold ({best_t:.4f}):")
        records = per_record_summary(chunks, best_t, args.truth_ratio)
        print(format_per_record_summary(records, args.top_n_worst))
        print()


if __name__ == "__main__":
    main()