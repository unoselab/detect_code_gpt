#!/usr/bin/env python3
"""
Recompute DetectCodeGPT ROC AUC on a subset of the NPR-scores CSV.

Use case: get an apples-to-apples comparison number when one model's filter
yielded more valid samples than another's. Cut to the smaller model's size
and re-run AUROC for direct comparison.

Usage:
    # First 530 in source order
    python recompute_auroc_subset.py --csv logs/npr_scores_starcoder2-7b_csn_t02_n3000_run.csv --n 530

    # Paired intersection with a second CSV
    python recompute_auroc_subset.py --csv logs/npr_scores_starcoder2-7b_csn_t02_n3000_run.csv \
        --pair_csv logs/npr_scores_codellama-7b-hf_csn_t02_n2000_run.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve


# -----------------------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------------------

def load_npr_csv(path: Path) -> List[dict]:
    """Load an npr_scores CSV. Each row has hwc_npr and mgc_npr per source sample."""
    rows = []
    with path.open("r") as f:
        for raw in csv.DictReader(f):
            try:
                rows.append({
                    "index": int(raw["index"]),
                    "source_line_no": int(raw["source_line_no"]),
                    "hwc_npr": float(raw["hwc_npr"]),
                    "mgc_npr": float(raw["mgc_npr"]),
                    "winner": raw["winner"],
                })
            except (ValueError, KeyError) as e:
                print(f"Skipping malformed row: {raw!r} ({e})")
    return rows




def load_prompts(path: Path) -> dict[int, str]:
    """Load prompts from outputs.txt, keyed by zero-based line number."""
    prompts = {}
    with path.open("r") as f:
        for line_no, line in enumerate(f):
            if line.strip():
                prompts[line_no] = json.loads(line)["prompt"]
    return prompts


def verify_prompt_alignment(outputs_a: Path, outputs_b: Path, rows_a: List[dict], rows_b: List[dict]) -> None:
    """Fail loudly if paired source_line_no values do not point to identical prompts."""
    prompts_a = load_prompts(outputs_a)
    prompts_b = load_prompts(outputs_b)

    sln_a = {r["source_line_no"] for r in rows_a}
    sln_b = {r["source_line_no"] for r in rows_b}
    common = sorted(sln_a & sln_b)

    missing = [s for s in common if s not in prompts_a or s not in prompts_b]
    mismatched = [s for s in common if s in prompts_a and s in prompts_b and prompts_a[s] != prompts_b[s]]

    print("\nPrompt-alignment safety check")
    print(f"  outputs A rows:      {len(prompts_a)}")
    print(f"  outputs B rows:      {len(prompts_b)}")
    print(f"  paired source lines: {len(common)}")
    print(f"  missing prompts:     {len(missing)}")
    print(f"  prompt mismatches:   {len(mismatched)}")

    if missing or mismatched:
        print("\nFirst problematic source_line_no values:")
        for s in (missing + mismatched)[:10]:
            print(f"  {s}")
        raise SystemExit(
            "Prompt alignment failed. Do not trust paired AUROC until the two outputs.txt "
            "files are verified to share identical prompts at paired source_line_no values."
        )

# -----------------------------------------------------------------------------
# Subsetting strategies
# -----------------------------------------------------------------------------

def first_n(rows: List[dict], n: int) -> List[dict]:
    """Take the first n rows in source order (already sorted by source_line_no)."""
    rows_sorted = sorted(rows, key=lambda r: r["source_line_no"])
    return rows_sorted[:n]


def random_n(rows: List[dict], n: int, seed: int) -> List[dict]:
    """Random subset of n rows with reproducible seed."""
    rng = np.random.default_rng(seed)
    indices = rng.choice(len(rows), size=min(n, len(rows)), replace=False)
    return [rows[i] for i in sorted(indices)]


def paired_intersection(rows_a: List[dict], rows_b: List[dict]) -> Tuple[List[dict], List[dict]]:
    """Keep only rows where both CSVs share the same source_line_no.

    Returns (subset_a, subset_b) aligned on source_line_no.
    """
    sln_a = {r["source_line_no"]: r for r in rows_a}
    sln_b = {r["source_line_no"]: r for r in rows_b}
    common = sorted(set(sln_a.keys()) & set(sln_b.keys()))
    return [sln_a[s] for s in common], [sln_b[s] for s in common]


# -----------------------------------------------------------------------------
# AUROC
# -----------------------------------------------------------------------------

def compute_auroc(rows: List[dict]) -> Tuple[float, float, dict]:
    """Compute DetectCodeGPT AUROC from HWC vs MGC NPR scores.

    Returns (auroc, optimal_threshold, metrics_dict).
    """
    hwc_nprs = np.array([r["hwc_npr"] for r in rows])
    mgc_nprs = np.array([r["mgc_npr"] for r in rows])

    # Labels: 1 = MGC, 0 = HWC; scores = NPR (higher → more likely MGC)
    labels = np.concatenate([np.zeros(len(hwc_nprs)), np.ones(len(mgc_nprs))])
    scores = np.concatenate([hwc_nprs, mgc_nprs])

    auroc = roc_auc_score(labels, scores)

    # Youden's J for the optimal threshold
    fpr, tpr, thresholds = roc_curve(labels, scores)
    j_scores = tpr - fpr
    j_idx = int(np.argmax(j_scores))
    best_thresh = float(thresholds[j_idx])

    return auroc, best_thresh, {
        "n_samples": len(rows),
        "n_filtered_nans": int(np.sum(np.isnan(scores))),
        "hwc_mean": float(np.mean(hwc_nprs)),
        "hwc_std": float(np.std(hwc_nprs)),
        "mgc_mean": float(np.mean(mgc_nprs)),
        "mgc_std": float(np.std(mgc_nprs)),
        "tpr_at_best": float(tpr[j_idx]),
        "fpr_at_best": float(fpr[j_idx]),
        "youden_j": float(j_scores[j_idx]),
    }


def format_report(label: str, auroc: float, threshold: float, metrics: dict) -> str:
    return (
        f"\n{'=' * 72}\n"
        f"  {label}\n"
        f"{'=' * 72}\n"
        f"  n = {metrics['n_samples']}\n"
        f"  HWC NPR: mean = {metrics['hwc_mean']:.4f}, std = {metrics['hwc_std']:.4f}\n"
        f"  MGC NPR: mean = {metrics['mgc_mean']:.4f}, std = {metrics['mgc_std']:.4f}\n"
        f"  Mean separation: {metrics['mgc_mean'] - metrics['hwc_mean']:.4f}\n"
        f"  ROC AUC of DetectCodeGPT: {auroc:.6f}\n"
        f"  Youden's J optimal threshold: {threshold:.4f}\n"
        f"  At optimal threshold:  TPR = {metrics['tpr_at_best']:.4f}, "
        f"FPR = {metrics['fpr_at_best']:.4f}, J = {metrics['youden_j']:.4f}\n"
    )


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recompute DetectCodeGPT ROC AUC on a subset of an NPR scores CSV."
    )
    parser.add_argument("--csv", type=str, required=True,
                        help="Path to NPR scores CSV.")
    parser.add_argument("--n", type=int, default=None,
                        help="Subset size. If omitted and no --pair_csv, uses full CSV.")
    parser.add_argument("--strategy", choices=["first", "random"], default="first",
                        help="Subsetting strategy (only used if --n is given).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (only used if --strategy random).")
    parser.add_argument("--pair_csv", type=str, default=None,
                        help="Optional second CSV; if given, restrict both to "
                             "shared source_line_no.")
    parser.add_argument("--outputs", type=str, default=None,
                        help="outputs.txt corresponding to --csv. Required with --pair_csv "
                             "for prompt-alignment safety check.")
    parser.add_argument("--pair_outputs", type=str, default=None,
                        help="outputs.txt corresponding to --pair_csv. Required with --pair_csv "
                             "for prompt-alignment safety check.")
    args = parser.parse_args()

    csv_path = Path(args.csv).expanduser()
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")

    rows = load_npr_csv(csv_path)
    print(f"\nLoaded {len(rows)} rows from {csv_path.name}")

    # Full-set AUROC (always shown as baseline)
    auroc_full, thresh_full, metrics_full = compute_auroc(rows)
    print(format_report(f"FULL CSV ({csv_path.name})", auroc_full, thresh_full, metrics_full))

    # Subset modes
    if args.pair_csv:
        pair_path = Path(args.pair_csv).expanduser()
        if not pair_path.is_file():
            raise SystemExit(f"Pair CSV not found: {pair_path}")
        pair_rows = load_npr_csv(pair_path)
        print(f"Loaded {len(pair_rows)} rows from {pair_path.name} (for pairing)")

        if not args.outputs or not args.pair_outputs:
            raise SystemExit(
                "For safe paired assessment, pass both --outputs and --pair_outputs "
                "so the script can verify identical prompts at paired source_line_no values."
            )
        outputs_path = Path(args.outputs).expanduser()
        pair_outputs_path = Path(args.pair_outputs).expanduser()
        if not outputs_path.is_file():
            raise SystemExit(f"outputs.txt not found: {outputs_path}")
        if not pair_outputs_path.is_file():
            raise SystemExit(f"pair outputs.txt not found: {pair_outputs_path}")
        verify_prompt_alignment(outputs_path, pair_outputs_path, rows, pair_rows)

        sub_a, sub_b = paired_intersection(rows, pair_rows)
        print(f"Paired intersection: {len(sub_a)} samples in common\n")

        auroc_a, thresh_a, metrics_a = compute_auroc(sub_a)
        auroc_b, thresh_b, metrics_b = compute_auroc(sub_b)
        print(format_report(f"PAIRED SUBSET: {csv_path.name}", auroc_a, thresh_a, metrics_a))
        print(format_report(f"PAIRED SUBSET: {pair_path.name}", auroc_b, thresh_b, metrics_b))

    elif args.n is not None:
        if args.strategy == "first":
            subset = first_n(rows, args.n)
            label = f"FIRST {args.n} (source order)"
        else:  # random
            subset = random_n(rows, args.n, args.seed)
            label = f"RANDOM {args.n} (seed={args.seed})"
        auroc_sub, thresh_sub, metrics_sub = compute_auroc(subset)
        print(format_report(label, auroc_sub, thresh_sub, metrics_sub))


if __name__ == "__main__":
    main()