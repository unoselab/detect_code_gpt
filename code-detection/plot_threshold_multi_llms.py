#!/usr/bin/env python3
"""
Figure 1: Threshold sensitivity per LLM.

Two-panel side-by-side figure for cross-LLM comparison:
  - Left:  F1 vs Threshold, one line per LLM (at fixed truth_ratio)
  - Right: Precision-Recall trajectory, one line per LLM

Each LLM gets:
  - A distinct color (fixed across all paper figures via LLM_COLORS)
  - Peak-F1 marker (filled circle)
  - High-precision marker (filled triangle, where precision first crosses target)
  - Dashed vertical line for classification threshold (left panel only)

Usage:
    python plot_fig1_threshold_per_llm.py \\
        --csv logs/benchmark_results_codellama.csv \\
        --csv logs/benchmark_results_starcoder2.csv \\
        --label "CodeLlama-7B" --label "StarCoder2-7B" \\
        --classification_threshold 1.3875 --classification_threshold 1.6470 \\
        --truth_ratio 0.5 \\
        --high_precision_target 0.80 \\
        --output_image logs/fig1_threshold_per_llm.png
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np

from evaluate_benchmark import (
    confusion_at_threshold,
    is_scorable,
    load_chunks,
    metrics_from_confusion,
)

# -----------------------------------------------------------------------------
# Fixed conventions across all paper figures
# -----------------------------------------------------------------------------

LLM_COLORS = {
    "CodeLlama-7B":        "#1f77b4",  # blue
    "StarCoder2-7B":       "#d62728",  # red
    "Qwen2.5-Coder-7B":    "#2ca02c",  # green
    "DeepSeek-Coder-6.7B": "#ff7f0e",  # orange
    "Codestral-22B":       "#9467bd",  # purple
    "CodeGen2-7B":         "#8c564b",  # brown
}
FALLBACK_COLORS = ["#e377c2", "#bcbd22", "#17becf", "#7f7f7f"]

DEFAULT_THRESHOLD_RANGE = (1.0, 2.0)
DEFAULT_THRESHOLD_STEP = 0.005   # fine enough that peak-finding is accurate


def color_for_label(label: str, fallback_idx: int) -> str:
    if label in LLM_COLORS:
        return LLM_COLORS[label]
    return FALLBACK_COLORS[fallback_idx % len(FALLBACK_COLORS)]


# -----------------------------------------------------------------------------
# Sweep computation per LLM
# -----------------------------------------------------------------------------

def sweep_metrics(
    chunks: List[Dict],
    truth_ratio: float,
    thresholds: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Compute precision, recall, F1 across threshold range."""
    p = np.zeros_like(thresholds)
    r = np.zeros_like(thresholds)
    f1 = np.zeros_like(thresholds)
    for i, t in enumerate(thresholds):
        conf = confusion_at_threshold(chunks, float(t), truth_ratio)
        m = metrics_from_confusion(conf)
        p[i] = m["precision"]
        r[i] = m["recall"]
        f1[i] = m["f1"]
    return {"precision": p, "recall": r, "f1": f1}


def find_high_precision_threshold(
    thresholds: np.ndarray,
    precisions: np.ndarray,
    target: float,
) -> Optional[int]:
    """Lowest threshold index where precision >= target. Returns None if unreachable."""
    above = np.where(precisions >= target)[0]
    if above.size == 0:
        return None
    return int(above[0])


# -----------------------------------------------------------------------------
# Plotting
# -----------------------------------------------------------------------------

def plot_left_panel_f1_vs_threshold(
    ax: plt.Axes,
    sweeps: Dict[str, Dict],
    thresholds: np.ndarray,
    label_to_color: Dict[str, str],
    label_to_class_thresh: Dict[str, Optional[float]],
    show_annotations: bool,
) -> None:
    """Left panel: F1 vs threshold, one line per LLM."""
    for label, data in sweeps.items():
        color = label_to_color[label]
        f1 = data["f1"]

        # F1 curve
        ax.plot(thresholds, f1, color=color, linewidth=2.0, label=label, zorder=2)

        # Peak F1 marker
        peak_idx = int(np.argmax(f1))
        peak_t = float(thresholds[peak_idx])
        peak_f1 = float(f1[peak_idx])
        ax.plot(peak_t, peak_f1, "o",
                color=color, markersize=7,
                markeredgecolor="black", markeredgewidth=0.8,
                zorder=3)

        if show_annotations:
            ax.annotate(
                f"({peak_t:.2f}, {peak_f1:.2f})",
                xy=(peak_t, peak_f1),
                xytext=(8, 8), textcoords="offset points",
                fontsize=8.5, color=color, weight="bold",
            )

        # Classification threshold reference (dashed, matching color)
        ct = label_to_class_thresh.get(label)
        if ct is not None:
            ax.axvline(ct, color=color, linestyle="--", alpha=0.55, linewidth=1.0, zorder=1)

    ax.set_xlabel("NPR threshold")
    ax.set_ylabel("F1")
    ax.set_title("F1 vs NPR threshold (per LLM)")
    ax.set_xlim(thresholds.min(), thresholds.max())
    ax.set_ylim(0.0, 1.0)
    ax.grid(True, alpha=0.3, linewidth=0.5)
    ax.legend(loc="best", fontsize=9, framealpha=0.9)


def plot_right_panel_pr_curve(
    ax: plt.Axes,
    sweeps: Dict[str, Dict],
    thresholds: np.ndarray,
    label_to_color: Dict[str, str],
    high_precision_target: float,
    show_annotations: bool,
) -> None:
    """Right panel: Precision vs Recall trajectory, one line per LLM."""

    # Horizontal reference line at the high-precision target
    ax.axhline(high_precision_target, color="gray", linestyle="--",
               alpha=0.4, linewidth=0.9, zorder=1,
               label=f"P = {high_precision_target:.2f}")

    for label, data in sweeps.items():
        color = label_to_color[label]
        precision = data["precision"]
        recall = data["recall"]
        f1 = data["f1"]

        # PR curve
        ax.plot(recall, precision, color=color, linewidth=2.0, label=label, zorder=2)

        # Peak-F1 point
        peak_idx = int(np.argmax(f1))
        ax.plot(recall[peak_idx], precision[peak_idx], "o",
                color=color, markersize=7,
                markeredgecolor="black", markeredgewidth=0.8, zorder=3)

        # High-precision point (where precision >= target, with highest recall)
        hp_idx = find_high_precision_threshold(thresholds, precision, high_precision_target)
        if hp_idx is not None:
            ax.plot(recall[hp_idx], precision[hp_idx], "^",
                    color=color, markersize=9,
                    markeredgecolor="black", markeredgewidth=0.8, zorder=3)

        if show_annotations:
            # Peak F1 annotation
            ax.annotate(
                f"F1: ({recall[peak_idx]:.2f}, {precision[peak_idx]:.2f})",
                xy=(recall[peak_idx], precision[peak_idx]),
                xytext=(8, -12), textcoords="offset points",
                fontsize=8.5, color=color, weight="bold",
            )
            # High-precision annotation
            if hp_idx is not None:
                ax.annotate(
                    f"HP: ({recall[hp_idx]:.2f}, {precision[hp_idx]:.2f})",
                    xy=(recall[hp_idx], precision[hp_idx]),
                    xytext=(8, 8), textcoords="offset points",
                    fontsize=8.5, color=color, weight="bold",
                )

    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall trajectory (per LLM)")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.grid(True, alpha=0.3, linewidth=0.5)
    ax.legend(loc="lower left", fontsize=9, framealpha=0.9)


def make_figure(
    csv_paths: List[Path],
    labels: List[str],
    classification_thresholds: List[Optional[float]],
    truth_ratio: float,
    threshold_range: tuple,
    threshold_step: float,
    high_precision_target: float,
    output_path: Path,
    n_samples: Optional[int],
) -> None:
    # Per-LLM sweeps
    thresholds = np.arange(threshold_range[0], threshold_range[1] + 1e-9, threshold_step)
    sweeps: Dict[str, Dict] = {}
    label_to_color: Dict[str, str] = {}
    label_to_class_thresh: Dict[str, Optional[float]] = {}

    for i, (csv_path, label, ct) in enumerate(zip(csv_paths, labels, classification_thresholds)):
        chunks = load_chunks(csv_path)
        # Optional: subset to first N records for parity across LLMs
        if n_samples is not None:
            keep_record_ids = sorted({c["record_id"] for c in chunks})[:n_samples]
            keep_set = set(keep_record_ids)
            chunks = [c for c in chunks if c["record_id"] in keep_set]
        sweeps[label] = sweep_metrics(chunks, truth_ratio, thresholds)
        label_to_color[label] = color_for_label(label, i)
        label_to_class_thresh[label] = ct

    # Annotation strategy: on-curve for ≤3 LLMs
    show_annotations = len(labels) <= 3

    # Figure
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(11, 4.5))
    fig.suptitle(
        f"Per-LLM Threshold Sensitivity  (truth_ratio = {truth_ratio:.2f}, "
        f"high-precision target = {high_precision_target:.2f})",
        fontsize=11, y=1.0,
    )

    plot_left_panel_f1_vs_threshold(
        ax_left, sweeps, thresholds,
        label_to_color, label_to_class_thresh, show_annotations,
    )
    plot_right_panel_pr_curve(
        ax_right, sweeps, thresholds,
        label_to_color, high_precision_target, show_annotations,
    )

    plt.tight_layout(rect=(0, 0, 1, 0.96))
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    print(f"Wrote {output_path}")

    # Print per-LLM summary for reference / paper table
    print()
    print("=" * 78)
    print("Per-LLM operating points (truth_ratio = {:.2f})".format(truth_ratio))
    print("=" * 78)
    print(f"  {'LLM':<24}  {'best_F1':>8}  {'τ_F1':>6}  {'τ_HP':>6}  "
          f"{'P@HP':>6}  {'R@HP':>6}  {'τ_class':>8}")
    print("  " + "-" * 76)
    for label, data in sweeps.items():
        f1 = data["f1"]
        peak_idx = int(np.argmax(f1))
        peak_t = thresholds[peak_idx]
        peak_f1 = f1[peak_idx]
        hp_idx = find_high_precision_threshold(thresholds, data["precision"], high_precision_target)
        if hp_idx is not None:
            hp_t = thresholds[hp_idx]
            hp_p = data["precision"][hp_idx]
            hp_r = data["recall"][hp_idx]
        else:
            hp_t = hp_p = hp_r = float("nan")
        ct = label_to_class_thresh[label]
        ct_str = f"{ct:.4f}" if ct is not None else "      —"
        print(f"  {label:<24}  {peak_f1:>8.4f}  {peak_t:>6.3f}  {hp_t:>6.3f}  "
              f"{hp_p:>6.3f}  {hp_r:>6.3f}  {ct_str:>8}")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot Figure 1: per-LLM threshold sensitivity (F1 + PR trajectory).",
    )
    parser.add_argument("--csv", type=str, action="append", required=True,
                        help="Path to a benchmark_results CSV. Repeatable.")
    parser.add_argument("--label", type=str, action="append", required=True,
                        help="Label for the corresponding --csv. Repeatable.")
    parser.add_argument("--classification_threshold", type=float, action="append",
                        default=None,
                        help="Classification threshold per LLM (from Youden's J on whole-snippet). "
                             "Repeatable; pass once per --csv, in matching order. "
                             "Pass 'nan' or omit to skip for a specific LLM.")
    parser.add_argument("--truth_ratio", type=float, default=0.5,
                        help="Truth ratio for ground-truth labeling (default 0.5).")
    parser.add_argument("--threshold_min", type=float, default=DEFAULT_THRESHOLD_RANGE[0])
    parser.add_argument("--threshold_max", type=float, default=DEFAULT_THRESHOLD_RANGE[1])
    parser.add_argument("--threshold_step", type=float, default=DEFAULT_THRESHOLD_STEP)
    parser.add_argument("--high_precision_target", type=float, default=0.80,
                        help="Target precision for high-precision operating point.")
    parser.add_argument("--n_samples", type=int, default=None,
                        help="If set, restrict each CSV to its first N records (parity).")
    parser.add_argument("--output_image", type=str, default="logs/fig1_threshold_per_llm.png")
    args = parser.parse_args()

    if len(args.csv) != len(args.label):
        raise SystemExit(f"Number of --csv ({len(args.csv)}) must equal --label ({len(args.label)})")

    if args.classification_threshold is None:
        classification_thresholds = [None] * len(args.csv)
    else:
        if len(args.classification_threshold) != len(args.csv):
            raise SystemExit(
                f"Number of --classification_threshold ({len(args.classification_threshold)}) "
                f"must equal --csv ({len(args.csv)})"
            )
        classification_thresholds = [
            None if (ct is None or (isinstance(ct, float) and ct != ct))
            else ct
            for ct in args.classification_threshold
        ]

    csv_paths = [Path(p).expanduser() for p in args.csv]
    for p in csv_paths:
        if not p.is_file():
            raise SystemExit(f"CSV not found: {p}")

    output_path = Path(args.output_image).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    make_figure(
        csv_paths=csv_paths,
        labels=args.label,
        classification_thresholds=classification_thresholds,
        truth_ratio=args.truth_ratio,
        threshold_range=(args.threshold_min, args.threshold_max),
        threshold_step=args.threshold_step,
        high_precision_target=args.high_precision_target,
        output_path=output_path,
        n_samples=args.n_samples,
    )


if __name__ == "__main__":
    main()