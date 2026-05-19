#!/usr/bin/env python3
"""
Per-LLM threshold-sensitivity plots — one metric per PNG.

Produces four separate PNG files for composition via LaTeX \subfigure:
  - F1 vs NPR threshold
  - Precision vs NPR threshold
  - Recall vs NPR threshold
  - Precision-Recall trajectory

Each plot overlays one line per LLM. Designed for 2x2 grid composition in
LaTeX (each figure ~3.4 inches square at \\textwidth in sigconf two-column).

Usage:
    python plot_threshold_multi_llms.py \\
        --csv logs/results_codellama.csv \\
        --csv logs/results_starcoder2.csv \\
        --label "CodeLlama-7B" --label "StarCoder2-7B" \\
        --truth_ratio 0.5 \\
        --n_samples 530 \\
        --output_image logs/threshold_f1.png \\
        --output_image logs/threshold_preci.png \\
        --output_image logs/threshold_recall.png \\
        --output_image logs/preci_recall.png

The four --output_image flags must appear in this order:
    f1, precision, recall, pr
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from evaluate_benchmark import (
    confusion_at_threshold,
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
DEFAULT_THRESHOLD_STEP = 0.005

# Positional mapping for --output_image flags
METRIC_ORDER = ["f1", "precision", "recall", "pr"]

# Annotation offsets — used per-LLM-index to avoid overlap (5 LLMs supported)
ANNOTATION_OFFSETS = [
    (8, 10),
    (8, -16),
    (-90, 10),
    (-90, -16),
    (8, 30),
]


def color_for_label(label: str, fallback_idx: int) -> str:
    return LLM_COLORS.get(label, FALLBACK_COLORS[fallback_idx % len(FALLBACK_COLORS)])


# -----------------------------------------------------------------------------
# Sweep computation per LLM
# -----------------------------------------------------------------------------

def sweep_metrics(
    chunks: List[Dict],
    truth_ratio: float,
    thresholds: np.ndarray,
) -> Dict[str, np.ndarray]:
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
    thresholds: np.ndarray, precisions: np.ndarray, target: float
) -> Optional[int]:
    above = np.where(precisions >= target)[0]
    return int(above[0]) if above.size > 0 else None


# -----------------------------------------------------------------------------
# Per-metric plotting (each produces one PNG)
# -----------------------------------------------------------------------------

def _style_panel(ax: plt.Axes, xlabel: str, ylabel: str, title: str,
                 x_range: tuple, y_range: tuple = (0.0, 1.0)) -> None:
    """Consistent styling across all panels."""
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xlim(x_range)
    ax.set_ylim(y_range)
    ax.grid(True, alpha=0.3, linewidth=0.5)


def plot_f1_panel(
    ax: plt.Axes,
    sweeps: Dict[str, Dict],
    thresholds: np.ndarray,
    label_to_color: Dict[str, str],
    show_annotations: bool,
    show_mean: bool = True,
) -> None:
    # Panel-specific offsets to avoid overlap near the F1 peaks.
    f1_annotation_offsets = [
        (-5, 20),    # CodeLlama: above/left
        (36, 8),   # StarCoder2: right/below
        (-80, 18),
        (16, -42),
    ]
    for idx, (label, data) in enumerate(sweeps.items()):
        color = label_to_color[label]
        f1 = data["f1"]
        ax.plot(thresholds, f1, color=color, linewidth=2.0, label=label, zorder=2)

        peak_idx = int(np.argmax(f1))
        peak_t, peak_f1 = float(thresholds[peak_idx]), float(f1[peak_idx])

        ax.plot(
            peak_t, peak_f1, "o",
            color=color,
            markersize=7,
            markeredgecolor="black",
            markeredgewidth=0.8,
            zorder=3,
        )

        if show_annotations:
            offset_x, offset_y = f1_annotation_offsets[idx % len(f1_annotation_offsets)]
            ax.annotate(
                f"({peak_t:.2f}, {peak_f1:.2f})",
                xy=(peak_t, peak_f1),
                xytext=(offset_x, offset_y),
                textcoords="offset points",
                fontsize=8.5,
                color=color,
                weight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75),
                arrowprops=dict(arrowstyle="-", color=color, lw=0.8, alpha=0.7),
                zorder=6,
            )

    if show_mean and len(sweeps) >= 2:
        mean_info = compute_mean_f1_curve(sweeps, thresholds)
        mean_f1 = mean_info["mean_f1"]
        tau_balanced = mean_info["tau_balanced"]
        best_mean_f1 = mean_info["best_mean_f1"]

        ax.plot(
            thresholds,
            mean_f1,
            color="black",
            linewidth=2.8,
            linestyle="--",
            label="Mean F1",
            zorder=4,
        )

        ax.plot(
            tau_balanced,
            best_mean_f1,
            "D",
            color="black",
            markersize=7,
            markeredgecolor="white",
            markeredgewidth=0.8,
            zorder=5,
        )

        if show_annotations:
            ax.annotate(
                f"mean peak\n({tau_balanced:.2f}, {best_mean_f1:.2f})",
                xy=(tau_balanced, best_mean_f1),
                xytext=(-18, -55),
                textcoords="offset points",
                fontsize=8.3,
                color="black",
                weight="bold",
                bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.80),
                arrowprops=dict(arrowstyle="-", color="black", lw=0.8, alpha=0.7),
                zorder=6,
            )

    _style_panel(
        ax,
        "Threshold",
        "F1",
        "F1 vs Threshold",
        (thresholds.min(), thresholds.max()),
    )
    ax.legend(loc="best", fontsize=9, framealpha=0.9)


def plot_precision_panel(
    ax: plt.Axes,
    sweeps: Dict[str, Dict],
    thresholds: np.ndarray,
    label_to_color: Dict[str, str],
    high_precision_target: Optional[float],
) -> None:
    if high_precision_target is not None:
        ax.axhline(high_precision_target, color="gray", linestyle="--",
                   alpha=0.4, linewidth=0.9, zorder=1,
                   label=f"P = {high_precision_target:.2f}")
    for label, data in sweeps.items():
        color = label_to_color[label]
        ax.plot(thresholds, data["precision"], color=color, linewidth=2.0,
                label=label, zorder=2)
    _style_panel(ax, "Threshold", "Precision", "Precision vs Threshold",
                 (thresholds.min(), thresholds.max()))
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9)


def plot_recall_panel(
    ax: plt.Axes,
    sweeps: Dict[str, Dict],
    thresholds: np.ndarray,
    label_to_color: Dict[str, str],
) -> None:
    for label, data in sweeps.items():
        color = label_to_color[label]
        ax.plot(thresholds, data["recall"], color=color, linewidth=2.0,
                label=label, zorder=2)
    _style_panel(ax, "NPR threshold", "Recall", "Recall vs NPR threshold",
                 (thresholds.min(), thresholds.max()))
    ax.legend(loc="lower left", fontsize=9, framealpha=0.9)


def plot_pr_panel(
    ax: plt.Axes,
    sweeps: Dict[str, Dict],
    thresholds: np.ndarray,
    label_to_color: Dict[str, str],
    high_precision_target: Optional[float],
    show_annotations: bool,
) -> None:
    if high_precision_target is not None:
        ax.axhline(high_precision_target, color="gray", linestyle="--",
                   alpha=0.4, linewidth=0.9, zorder=1,
                   label=f"P = {high_precision_target:.2f}")
    for idx, (label, data) in enumerate(sweeps.items()):
        color = label_to_color[label]
        precision, recall, f1 = data["precision"], data["recall"], data["f1"]
        ax.plot(recall, precision, color=color, linewidth=2.0,
                label=label, zorder=2)
        # peak F1 dot
        peak_idx = int(np.argmax(f1))
        ax.plot(recall[peak_idx], precision[peak_idx], "o",
                color=color, markersize=7,
                markeredgecolor="black", markeredgewidth=0.8, zorder=3)
        # high-precision triangle
        if high_precision_target is not None:
            hp_idx = find_high_precision_threshold(thresholds, precision,
                                                    high_precision_target)
            if hp_idx is not None:
                ax.plot(recall[hp_idx], precision[hp_idx], "^",
                        color=color, markersize=9,
                        markeredgecolor="black", markeredgewidth=0.8, zorder=3)
                if show_annotations:
                    # offset_x, offset_y = ANNOTATION_OFFSETS[idx % len(ANNOTATION_OFFSETS)]
                    pr_annotation_offsets = [
                        (-48, -18),   # CodeLlama: move blue label downward/right
                        (8, 0),      # StarCoder2: move red label upward/right
                        (-90, -18),
                        (-90, 18),
                    ]
                    offset_x, offset_y = pr_annotation_offsets[idx % len(pr_annotation_offsets)]
                    
                    ax.annotate(
                        f"({recall[hp_idx]:.2f}, {precision[hp_idx]:.2f})",
                        xy=(recall[hp_idx], precision[hp_idx]),
                        xytext=(offset_x, offset_y), textcoords="offset points",
                        fontsize=8.5, color=color, weight="bold",
                    )
    _style_panel(ax, "Recall", "Precision", "Precision-Recall trajectory",
                 (0.0, 1.0), (0.0, 1.0))
    # ax.legend(loc="lower left", fontsize=9, framealpha=0.9)
    # Add legend entries for line colors and marker meanings.
    handles, labels = ax.get_legend_handles_labels()

    marker_handles = [
        Line2D(
            [0], [0],
            marker="o",
            color="none",
            markerfacecolor="gray",
            markeredgecolor="black",
            markersize=7,
            label="Best F1"
        ),
        Line2D(
            [0], [0],
            marker="^",
            color="none",
            markerfacecolor="gray",
            markeredgecolor="black",
            markersize=9,
            label=f"High precision point"
        ),
    ]

    ax.legend(
        handles + marker_handles,
        labels + ["Best F1", "High precision point"],
        loc="lower left",
        fontsize=9,
        framealpha=0.9,
    )


# -----------------------------------------------------------------------------
# Per-PNG dispatcher
# -----------------------------------------------------------------------------

def save_one_panel(
    metric: str,
    output_path: Path,
    sweeps: Dict[str, Dict],
    thresholds: np.ndarray,
    label_to_color: Dict[str, str],
    high_precision_target: Optional[float],
    show_annotations: bool,
    figsize: tuple = (5.0, 4.0),
) -> None:
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    if metric == "f1":
        plot_f1_panel(
            ax,
            sweeps,
            thresholds,
            label_to_color,
            show_annotations,
            show_mean=True,
        )
    elif metric == "precision":
        plot_precision_panel(ax, sweeps, thresholds, label_to_color, high_precision_target)
    elif metric == "recall":
        plot_recall_panel(ax, sweeps, thresholds, label_to_color)
    elif metric == "pr":
        plot_pr_panel(ax, sweeps, thresholds, label_to_color,
                       high_precision_target, show_annotations)
    else:
        raise ValueError(f"Unknown metric: {metric}")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {output_path}")


def compute_mean_f1_curve(
    sweeps: Dict[str, Dict],
    thresholds: np.ndarray,
) -> Dict[str, object]:
    """Compute the balanced cross-LLM operating point.

    Each LLM receives equal weight, regardless of chunk count.
    """
    f1_curves = np.vstack([data["f1"] for data in sweeps.values()])
    precision_curves = np.vstack([data["precision"] for data in sweeps.values()])
    recall_curves = np.vstack([data["recall"] for data in sweeps.values()])

    mean_f1 = np.mean(f1_curves, axis=0)
    mean_precision = np.mean(precision_curves, axis=0)
    mean_recall = np.mean(recall_curves, axis=0)

    best_idx = int(np.argmax(mean_f1))

    return {
        "mean_f1": mean_f1,
        "mean_precision": mean_precision,
        "mean_recall": mean_recall,
        "best_idx": best_idx,
        "tau_balanced": float(thresholds[best_idx]),
        "best_mean_f1": float(mean_f1[best_idx]),
        "mean_precision_at_tau": float(mean_precision[best_idx]),
        "mean_recall_at_tau": float(mean_recall[best_idx]),
    }
    
    
def compute_cross_llm_high_precision_threshold(
    sweeps: Dict[str, Dict],
    thresholds: np.ndarray,
    target: float,
) -> Optional[Dict[str, object]]:
    """Find the lowest threshold where every LLM reaches precision >= target."""
    precision_curves = np.vstack([data["precision"] for data in sweeps.values()])
    min_precision = np.min(precision_curves, axis=0)

    valid = np.where(min_precision >= target)[0]
    if valid.size == 0:
        return None

    hp_idx = int(valid[0])
    return {
        "hp_idx": hp_idx,
        "tau_hp_cross_llm": float(thresholds[hp_idx]),
        "min_precision": float(min_precision[hp_idx]),
    }
        

# -----------------------------------------------------------------------------
# Main pipeline
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Per-LLM threshold sweep — one metric per PNG for LaTeX subfigure composition."
    )
    parser.add_argument("--csv", type=str, action="append", required=True,
                        help="Path to a benchmark_results CSV. Repeatable.")
    parser.add_argument("--label", type=str, action="append", required=True,
                        help="Label for the corresponding --csv. Repeatable.")
    parser.add_argument("--output_image", type=str, action="append", required=True,
                        help=f"Output PNG. Must be repeated exactly 4 times. "
                             f"Positional order: {METRIC_ORDER}.")
    parser.add_argument("--truth_ratio", type=float, default=0.5)
    parser.add_argument("--threshold_min", type=float, default=DEFAULT_THRESHOLD_RANGE[0])
    parser.add_argument("--threshold_max", type=float, default=DEFAULT_THRESHOLD_RANGE[1])
    parser.add_argument("--threshold_step", type=float, default=DEFAULT_THRESHOLD_STEP)
    parser.add_argument("--high_precision_target", type=float, default=None,
                        help="If set, overlay P=target reference line and mark "
                             "high-precision operating points on the PR panel.")
    parser.add_argument("--n_samples", type=int, default=None,
                        help="If set, restrict each CSV to its first N records.")
    args = parser.parse_args()

    # --- Validate inputs ---
    if len(args.csv) != len(args.label):
        raise SystemExit(f"Number of --csv ({len(args.csv)}) must equal --label ({len(args.label)})")
    if len(args.output_image) != len(METRIC_ORDER):
        raise SystemExit(
            f"Expected exactly {len(METRIC_ORDER)} --output_image flags "
            f"(one each for: {METRIC_ORDER}); got {len(args.output_image)}."
        )

    # --- Load and sweep per LLM ---
    csv_paths = [Path(p).expanduser() for p in args.csv]
    for p in csv_paths:
        if not p.is_file():
            raise SystemExit(f"CSV not found: {p}")

    thresholds = np.arange(args.threshold_min, args.threshold_max + 1e-9,
                            args.threshold_step)
    sweeps: Dict[str, Dict] = {}
    label_to_color: Dict[str, str] = {}
    for i, (csv_path, label) in enumerate(zip(csv_paths, args.label)):
        chunks = load_chunks(csv_path)
        if args.n_samples is not None:
            keep_record_ids = sorted({c["record_id"] for c in chunks})[:args.n_samples]
            keep_set = set(keep_record_ids)
            chunks = [c for c in chunks if c["record_id"] in keep_set]
        sweeps[label] = sweep_metrics(chunks, args.truth_ratio, thresholds)
        label_to_color[label] = color_for_label(label, i)

    # --- Per-metric save ---
    show_annotations = len(args.label) <= 3
    print(f"\nWriting {len(METRIC_ORDER)} panels:")
    for metric, output_path_str in zip(METRIC_ORDER, args.output_image):
        output_path = Path(output_path_str).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_one_panel(
            metric=metric,
            output_path=output_path,
            sweeps=sweeps,
            thresholds=thresholds,
            label_to_color=label_to_color,
            high_precision_target=args.high_precision_target,
            show_annotations=show_annotations,
        )

    # --- Summary ---
    print()
    print("=" * 78)
    print(f"Per-LLM operating points (truth_ratio = {args.truth_ratio:.2f})")
    print("=" * 78)
    print(f"  {'LLM':<24}  {'best_F1':>8}  {'τ_F1':>6}  {'τ_HP':>6}  "
          f"{'P@HP':>6}  {'R@HP':>6}")
    print("  " + "-" * 68)
    for label, data in sweeps.items():
        f1 = data["f1"]
        peak_idx = int(np.argmax(f1))
        peak_t, peak_f1 = thresholds[peak_idx], f1[peak_idx]
        if args.high_precision_target is not None:
            hp_idx = find_high_precision_threshold(
                thresholds, data["precision"], args.high_precision_target
            )
            if hp_idx is not None:
                hp_t = thresholds[hp_idx]
                hp_p = data["precision"][hp_idx]
                hp_r = data["recall"][hp_idx]
            else:
                hp_t = hp_p = hp_r = float("nan")
        else:
            hp_t = hp_p = hp_r = float("nan")
        print(f"  {label:<24}  {peak_f1:>8.4f}  {peak_t:>6.3f}  {hp_t:>6.3f}  "
              f"{hp_p:>6.3f}  {hp_r:>6.3f}")

    if len(sweeps) >= 2:
        mean_info = compute_mean_f1_curve(sweeps, thresholds)
        idx = mean_info["best_idx"]

        print()
        print("=" * 78)
        print("Cross-LLM balanced operating point")
        print("=" * 78)
        print(f"  τ_balanced = {mean_info['tau_balanced']:.3f}")
        print(f"  mean F1    = {mean_info['best_mean_f1']:.4f}")
        print(f"  mean P     = {mean_info['mean_precision_at_tau']:.4f}")
        print(f"  mean R     = {mean_info['mean_recall_at_tau']:.4f}")

        print()
        print("  Per-LLM metrics at τ_balanced:")
        print(f"    {'LLM':<24}  {'P':>8}  {'R':>8}  {'F1':>8}")
        print("    " + "-" * 50)

        for label, data in sweeps.items():
            print(
                f"    {label:<24}  "
                f"{data['precision'][idx]:>8.4f}  "
                f"{data['recall'][idx]:>8.4f}  "
                f"{data['f1'][idx]:>8.4f}"
            )

    if args.high_precision_target is not None and len(sweeps) >= 2:
        hp_info = compute_cross_llm_high_precision_threshold(
            sweeps,
            thresholds,
            args.high_precision_target,
        )

        print()
        print("=" * 78)
        print(f"Cross-LLM high-precision operating point "
            f"(P >= {args.high_precision_target:.2f})")
        print("=" * 78)

        if hp_info is None:
            print("  No threshold satisfies the precision floor for all LLMs.")
        else:
            idx = hp_info["hp_idx"]
            print(f"  τ_HP,cross = {hp_info['tau_hp_cross_llm']:.3f}")
            print(f"  min P      = {hp_info['min_precision']:.4f}")

            print()
            print("  Per-LLM precision/recall at τ_HP,cross:")
            for label, data in sweeps.items():
                print(
                    f"    {label:<24} "
                    f"P = {data['precision'][idx]:.4f}, "
                    f"R = {data['recall'][idx]:.4f}"
                )


if __name__ == "__main__":
    main()