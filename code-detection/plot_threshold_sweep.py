#!/usr/bin/env python3
"""
Plot detection metrics as a function of NPR threshold, parameterized by truth_ratio.

Produces a 2x2 figure:
    top-left:    precision vs threshold
    top-right:   recall vs threshold
    bottom-left: F1 vs threshold (with peak markers)
    bottom-right: precision-recall curve

Each subplot has one line per truth_ratio in --truth_ratios.

Usage:
    python code-detection/plot_threshold_sweep.py --threshold_min 1.0 --threshold_max 2.0    
    python plot_threshold_sweep.py
    python plot_threshold_sweep.py --truth_ratios 0.3 0.5 0.7 0.9
    python plot_threshold_sweep.py --output_image my_chart.png
    python plot_threshold_sweep.py --output_image my_chart.svg
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np

from evaluate_benchmark import (
    confusion_at_threshold,
    DEFAULT_CSV,
    is_scorable,
    load_chunks,
    metrics_from_confusion,
)


# -----------------------------------------------------------------------------
# Defaults
# -----------------------------------------------------------------------------

DEFAULT_TRUTH_RATIOS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

# Threshold sweep: dense enough for smooth curves, sparse enough to be fast.
DEFAULT_THRESHOLD_RANGE = (1.05, 1.65)
DEFAULT_THRESHOLD_STEP = 0.01

# Reference thresholds to mark on charts
LEGACY_YOUDEN_THRESHOLD = 1.3875
RECOMMENDED_THRESHOLD = 1.25
HIGH_CONF_THRESHOLD = 1.60


# -----------------------------------------------------------------------------
# Sweep computation
# -----------------------------------------------------------------------------

def sweep_thresholds(
    chunks: List[Dict[str, Any]],
    truth_ratio: float,
    thresholds: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Compute precision/recall/F1/accuracy across the threshold range."""
    p = np.zeros_like(thresholds)
    r = np.zeros_like(thresholds)
    f1 = np.zeros_like(thresholds)
    acc = np.zeros_like(thresholds)

    for i, t in enumerate(thresholds):
        conf = confusion_at_threshold(chunks, float(t), truth_ratio)
        m = metrics_from_confusion(conf)
        p[i] = m["precision"]
        r[i] = m["recall"]
        f1[i] = m["f1"]
        acc[i] = m["accuracy"]

    return {"precision": p, "recall": r, "f1": f1, "accuracy": acc}


# -----------------------------------------------------------------------------
# Plotting helpers
# -----------------------------------------------------------------------------

def _add_reference_lines(ax: plt.Axes, *, vertical: bool = True) -> None:
    """Add dashed vertical reference lines for known thresholds."""
    if vertical:
        ax.axvline(LEGACY_YOUDEN_THRESHOLD, color="gray", linestyle="--",
                   alpha=0.5, linewidth=0.9,
                   label=f"Youden's J ({LEGACY_YOUDEN_THRESHOLD:.4f})")
        ax.axvline(RECOMMENDED_THRESHOLD, color="black", linestyle=":",
                   alpha=0.7, linewidth=1.1,
                   label=f"Recalibrated ({RECOMMENDED_THRESHOLD:.2f})")
        ax.axvline(HIGH_CONF_THRESHOLD, color="darkred", linestyle=":",
                   alpha=0.5, linewidth=0.9,
                   label=f"High-confidence ({HIGH_CONF_THRESHOLD:.2f})")


def _color_for_ratio(idx: int, total: int) -> tuple:
    """Pick a color from a perceptually-uniform colormap."""
    return plt.cm.viridis(idx / max(total - 1, 1))


def plot_metric_subplot(
    ax: plt.Axes,
    thresholds: np.ndarray,
    sweeps: Dict[float, Dict[str, np.ndarray]],
    metric: str,
    title: str,
    show_legend: bool = False,
    mark_peaks: bool = False,
) -> None:
    """One subplot: metric vs threshold, one line per truth_ratio."""
    n_ratios = len(sweeps)
    for i, (ratio, data) in enumerate(sweeps.items()):
        color = _color_for_ratio(i, n_ratios)
        ax.plot(thresholds, data[metric], color=color, linewidth=1.6,
                label=f"truth_ratio={ratio:.1f}")
        if mark_peaks:
            peak_idx = int(np.argmax(data[metric]))
            ax.plot(thresholds[peak_idx], data[metric][peak_idx],
                    "o", color=color, markersize=5,
                    markeredgecolor="black", markeredgewidth=0.5)

    _add_reference_lines(ax, vertical=True)
    ax.set_xlabel("NPR threshold")
    ax.set_ylabel(metric.capitalize())
    ax.set_title(title)
    ax.set_xlim(thresholds.min(), thresholds.max())
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3, linewidth=0.5)

    if show_legend:
        ax.legend(loc="best", fontsize=7.5, ncol=1, framealpha=0.85)


def plot_pr_curve(
    ax: plt.Axes,
    sweeps: Dict[float, Dict[str, np.ndarray]],
) -> None:
    """Precision-recall curve, parameterized by threshold."""
    n_ratios = len(sweeps)
    for i, (ratio, data) in enumerate(sweeps.items()):
        color = _color_for_ratio(i, n_ratios)
        ax.plot(data["recall"], data["precision"],
                color=color, linewidth=1.6,
                label=f"truth_ratio={ratio:.1f}")
        # Mark peak F1 point
        f1 = data["f1"]
        peak_idx = int(np.argmax(f1))
        ax.plot(data["recall"][peak_idx], data["precision"][peak_idx],
                "o", color=color, markersize=5,
                markeredgecolor="black", markeredgewidth=0.5)

    # Reference: random baseline (precision = positive rate, varies by truth_ratio,
    # but we show approximate 0.5 as the always-predict-positive line).
    ax.plot([0, 1], [0.5, 0.5], color="gray", linestyle="--",
            alpha=0.3, linewidth=0.9, label="random baseline (~0.5)")

    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall Curve  (peak F1 marked per line)")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3, linewidth=0.5)


def subset_chunks_by_n_samples(chunks: List[Dict[str, Any]], n_samples: int | None) -> List[Dict[str, Any]]:
    """Keep all chunks belonging to the first n unique record_id values."""
    if n_samples is None:
        return chunks

    selected_record_ids = []
    seen = set()

    for c in chunks:
        rid = c.get("record_id")
        if rid not in seen:
            seen.add(rid)
            selected_record_ids.append(rid)
        if len(selected_record_ids) >= n_samples:
            break

    selected_set = set(selected_record_ids)
    return [c for c in chunks if c.get("record_id") in selected_set]


# -----------------------------------------------------------------------------
# Top-level plot
# -----------------------------------------------------------------------------

def make_figure(
    chunks: List[Dict[str, Any]],
    truth_ratios: List[float],
    threshold_range: Tuple[float, float],
    threshold_step: float,
    output_path: Path,
) -> None:
    thresholds = np.arange(threshold_range[0], threshold_range[1] + 1e-9,
                            threshold_step)
    sweeps = {
        ratio: sweep_thresholds(chunks, ratio, thresholds)
        for ratio in truth_ratios
    }

    fig, axs = plt.subplots(2, 2, figsize=(13, 10))
    fig.suptitle(
        "DetectCodeGPT Localization Benchmark — Metrics vs NPR Threshold\n"
        f"({sum(1 for c in chunks if is_scorable(c))} scorable chunks)",
        fontsize=12, y=0.995,
    )

    plot_metric_subplot(axs[0, 0], thresholds, sweeps, "precision",
                        title="Precision vs Threshold", show_legend=False)
    plot_metric_subplot(axs[0, 1], thresholds, sweeps, "recall",
                        title="Recall vs Threshold", show_legend=False)
    plot_metric_subplot(axs[1, 0], thresholds, sweeps, "f1",
                        title="F1 vs Threshold  (peak marked per line)",
                        show_legend=True, mark_peaks=True)
    plot_pr_curve(axs[1, 1], sweeps)

    plt.tight_layout(rect=(0, 0, 1, 0.97))
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Wrote {output_path}")

    # Also print the best-F1 summary per truth_ratio
    print()
    print("Best-F1 summary per truth_ratio:")
    print(f"  {'truth_ratio':>12}  {'best_thresh':>11}  {'best_F1':>8}  "
          f"{'precision':>9}  {'recall':>7}")
    print("  " + "-" * 60)
    for ratio, data in sweeps.items():
        peak_idx = int(np.argmax(data["f1"]))
        print(f"  {ratio:>12.2f}  {thresholds[peak_idx]:>11.4f}  "
              f"{data['f1'][peak_idx]:>8.4f}  "
              f"{data['precision'][peak_idx]:>9.4f}  "
              f"{data['recall'][peak_idx]:>7.4f}")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot threshold-vs-metrics trajectories with one line per truth_ratio."
    )
    parser.add_argument("--csv", type=str, default=str(DEFAULT_CSV),
                        help="Path to benchmark_results CSV.")
    parser.add_argument("--n_samples", type=int, default=None,
                    help="Use only the first N benchmark records, keeping all chunks for those records.")
    parser.add_argument("--truth_ratios", type=float, nargs="+",
                        default=DEFAULT_TRUTH_RATIOS,
                        help="Truth ratios to plot as separate lines.")
    parser.add_argument("--threshold_min", type=float,
                        default=DEFAULT_THRESHOLD_RANGE[0])
    parser.add_argument("--threshold_max", type=float,
                        default=DEFAULT_THRESHOLD_RANGE[1])
    parser.add_argument("--threshold_step", type=float,
                        default=DEFAULT_THRESHOLD_STEP)
    parser.add_argument("--output_image", type=str,
                        default="logs/threshold_sweep.png",
                        help="Output path (.png, .svg, .pdf supported).")
    args = parser.parse_args()

    csv_path = Path(args.csv).expanduser()
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")

    chunks = load_chunks(csv_path)
    chunks = subset_chunks_by_n_samples(chunks, args.n_samples)
    
    output_path = Path(args.output_image).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    make_figure(
        chunks=chunks,
        truth_ratios=args.truth_ratios,
        threshold_range=(args.threshold_min, args.threshold_max),
        threshold_step=args.threshold_step,
        output_path=output_path,
    )


if __name__ == "__main__":
    main()