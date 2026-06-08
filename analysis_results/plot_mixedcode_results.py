#!/usr/bin/env python3
"""Collect mixed-code benchmark outputs and create paper-ready artifacts.

Expected input files in ``logs/``::

    npr_scores_main_mixedcode_benchmark_mixedcode_<MODEL>*50files.csv
    npr_scores_main_mixedcode_benchmark_mixedcode*<MODEL>*50files_bucket_summary.csv
    npr_chunks_main_mixedcode_benchmark_mixedcode*<MODEL>*50files.csv
    results_cache_main_mixedcode_benchmark_mixedcode*<MODEL>_50files.pkl

Outputs::

    mixedcode_bucket_summary_combined.csv
    mixedcode_overall_summary.csv
    fig_mixedcode_auc_by_bucket.{png,pdf}
    fig_mixedcode_overall_auc.{png,pdf}
    fig_mixedcode_npr_gap_by_bucket.{png,pdf}
    table_mixedcode_overall.tex
    table_mixedcode_auc_by_bucket.tex
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

MODEL_MAP = {
    "codellama-7b": ("CL7B", "CodeLlama-7B"),
    "starcoder2-7b": ("SC7B", "StarCoder2-7B"),
    "starcoder2-15b-instruct-v0.1": ("SC15B", "StarCoder2-15B"),
    "gpt-oss": ("GO120B", "GPT-OSS-120B"),
    "gemma": ("Gemma", "Gemma"),
}

MODEL_ORDER = ["CL7B", "SC7B", "SC15B", "GO120B", "Gemma"]

BUCKET_LABELS = {
    "type01_110": "100--110",
    "type02_120": "111--120",
    "type03_130": "121--130",
    "type04_140": "131--140",
    "type05_150": "141--150",
    "type06_160": "151--160",
    "type07_170": "161--170",
    "type08_180": "171--180",
    "type09_190": "181--190",
    "type10_200": "191--200",
}

BUCKET_ORDER = list(BUCKET_LABELS.keys())


# --------------------------------------------------------------------------- #
# Parsing / loading helpers
# --------------------------------------------------------------------------- #

def infer_model_from_path(path: Path) -> Tuple[str, str, str]:
    """Return ``(model_key, short_name, long_name)`` from a result filename."""
    name = path.name

    # Match the longer StarCoder2-15B key before starcoder2-7b.
    for key in sorted(MODEL_MAP, key=len, reverse=True):
        if key in name:
            short_name, long_name = MODEL_MAP[key]
            return key, short_name, long_name

    raise ValueError(f"Could not infer model from filename: {path}")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from column names but preserve original spelling."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def find_column(
    df: pd.DataFrame,
    candidates: List[str],
    required: bool = True,
) -> Optional[str]:
    """Return the first matching column name (case-insensitive)."""
    lower_to_original = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_to_original:
            return lower_to_original[cand.lower()]
    if required:
        raise KeyError(
            f"Could not find any of columns {candidates}; "
            f"available={list(df.columns)}"
        )
    return None


def bucket_sort_key(bucket: str) -> int:
    """Sort buckets by their canonical order, falling back to the type index."""
    if bucket in BUCKET_ORDER:
        return BUCKET_ORDER.index(bucket)
    m = re.search(r"type(\d+)_", str(bucket))
    if m:
        return int(m.group(1)) - 1
    return 999


def load_bucket_summary(path: Path) -> pd.DataFrame:
    """Load one ``*_bucket_summary.csv`` and normalize to a common schema."""
    model_key, model, model_long = infer_model_from_path(path)
    df = normalize_columns(pd.read_csv(path))

    bucket_col = find_column(df, ["bucket", "benchmark_type", "type"])
    auc_col = find_column(df, ["auc", "auroc", "AUC", "AUROC"])
    n_hwc_col = find_column(df, ["n_hwc", "HWC", "hwc_n", "n_human"], required=False)
    n_agc_col = find_column(
        df, ["n_agc", "AGC", "MGC", "agc_n", "mgc_n", "n_lm"], required=False
    )
    hwc_mean_col = find_column(
        df, ["HWC_mean", "hwc_mean", "human_mean"], required=False
    )
    agc_mean_col = find_column(
        df, ["AGC_mean", "MGC_mean", "agc_mean", "mgc_mean", "lm_mean"], required=False
    )

    # Anchor to df.index so scalar metadata broadcasts across every row.
    # Building on an empty frame would assign 0-length scalar columns that
    # silently backfill to NaN once a real Series column is added.
    out = pd.DataFrame(index=df.index)
    out["model_key"] = model_key
    out["model"] = model
    out["model_long"] = model_long
    out["bucket"] = df[bucket_col].astype(str)
    out["bucket_label"] = out["bucket"].map(BUCKET_LABELS).fillna(out["bucket"])
    out["bucket_order"] = out["bucket"].map(bucket_sort_key)
    out["auc"] = pd.to_numeric(df[auc_col], errors="coerce")

    out["n_hwc"] = pd.to_numeric(df[n_hwc_col], errors="coerce") if n_hwc_col else np.nan
    out["n_agc"] = pd.to_numeric(df[n_agc_col], errors="coerce") if n_agc_col else np.nan
    out["hwc_mean"] = (
        pd.to_numeric(df[hwc_mean_col], errors="coerce") if hwc_mean_col else np.nan
    )
    out["agc_mean"] = (
        pd.to_numeric(df[agc_mean_col], errors="coerce") if agc_mean_col else np.nan
    )
    out["npr_gap"] = out["agc_mean"] - out["hwc_mean"]
    out["source_file"] = str(path)

    return out


def role_to_label(value: str) -> int:
    """Map a role/label string to a binary class (1 = machine, 0 = human)."""
    v = str(value).strip().lower()
    if v in {"agc", "mgc", "lm", "machine", "machine-generated", "generated", "1"}:
        return 1
    if v in {"hwc", "human", "human-written", "0"}:
        return 0
    raise ValueError(f"Unknown role/label value: {value!r}")


def load_score_csv(path: Path) -> pd.DataFrame:
    """Load one per-function score CSV and normalize for overall AUROC."""
    model_key, model, model_long = infer_model_from_path(path)
    df = normalize_columns(pd.read_csv(path))

    # Your mixed-code score CSV has both:
    #   role  = HWC / AGC
    #   label = 0 / 1
    label_col = find_column(df, ["label", "is_target"], required=False)
    role_col = find_column(df, ["role", "truth", "class", "gold", "target"], required=False)
    score_col = find_column(df, ["npr", "NPR"], required=True)
    bucket_col = find_column(df, ["benchmark_type", "bucket", "type"], required=False)

    # Anchor to df.index (see load_bucket_summary) so the scalar model
    # metadata is present on every row instead of backfilling to NaN.
    out = pd.DataFrame(index=df.index)
    out["model_key"] = model_key
    out["model"] = model
    out["model_long"] = model_long

    if label_col is not None:
        out["y_true"] = pd.to_numeric(df[label_col], errors="coerce").astype("Int64")
        out["role"] = df[role_col].astype(str) if role_col is not None else out["y_true"].map({0: "HWC", 1: "AGC"})
        y_source = label_col
    elif role_col is not None:
        out["role"] = df[role_col].astype(str)
        out["y_true"] = out["role"].map(role_to_label).astype("Int64")
        y_source = role_col
    else:
        raise KeyError(
            f"Could not find label or role column in {path}. "
            f"Available columns: {list(df.columns)}"
        )

    out["npr"] = pd.to_numeric(df[score_col], errors="coerce")
    out["bucket"] = df[bucket_col].astype(str) if bucket_col else ""
    out["source_file"] = str(path)

    before = len(out)
    out = out.dropna(subset=["y_true", "npr"]).reset_index(drop=True)
    out["y_true"] = out["y_true"].astype(int)
    after = len(out)

    print(
        f"[LOAD SCORE] {path.name}: rows={before}, valid={after}, "
        f"y_true_col={y_source}, score_col={score_col}, bucket_col={bucket_col}"
    )

    if after == 0:
        print("[WARNING] No valid rows after parsing.")
        print("Columns:", list(df.columns))
        print(df.head(3).to_string(index=False))

    return out


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #

def compute_overall(score_df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-model overall AUROC and Youden-optimal operating point."""
    if score_df.empty:
        raise ValueError(
            "No valid per-function score rows were loaded. "
            "Check load_score_csv() and CSV column parsing."
        )

    required_cols = {"model", "y_true", "npr"}
    missing = required_cols - set(score_df.columns)
    if missing:
        raise KeyError(
            f"score_df is missing required columns: {sorted(missing)}. "
            f"Available columns: {list(score_df.columns)}"
        )

    rows = []

    for model, g in score_df.groupby("model", sort=False):
        g = g.dropna(subset=["npr"])
        y_true = g["y_true"].to_numpy(dtype=int)
        y_score = g["npr"].to_numpy(dtype=float)

        if len(np.unique(y_true)) < 2:
            auc = np.nan
            threshold = np.nan
            tpr_best = np.nan
            fpr_best = np.nan
            j_best = np.nan
        else:
            auc = roc_auc_score(y_true, y_score)
            fpr, tpr, thresholds = roc_curve(y_true, y_score)
            j = tpr - fpr
            best = int(np.argmax(j))
            threshold = thresholds[best]
            tpr_best = tpr[best]
            fpr_best = fpr[best]
            j_best = j[best]

        rows.append(
            {
                "model": model,
                "model_long": g["model_long"].iloc[0],
                "model_key": g["model_key"].iloc[0],
                "n_total": len(g),
                "n_hwc": int((g["y_true"] == 0).sum()),
                "n_agc": int((g["y_true"] == 1).sum()),
                "overall_auc": auc,
                "youden_threshold": threshold,
                "tpr": tpr_best,
                "fpr": fpr_best,
                "youden_j": j_best,
                "hwc_mean": float(g.loc[g["y_true"] == 0, "npr"].mean()),
                "agc_mean": float(g.loc[g["y_true"] == 1, "npr"].mean()),
                "npr_gap": float(
                    g.loc[g["y_true"] == 1, "npr"].mean()
                    - g.loc[g["y_true"] == 0, "npr"].mean()
                ),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError(
            "compute_overall() produced no per-model rows. This usually means "
            "the 'model' column is empty/NaN, so groupby('model') dropped every "
            f"row. Distinct model values seen: {score_df['model'].unique().tolist()}"
        )
    out["model_order"] = out["model"].map(
        lambda m: MODEL_ORDER.index(m) if m in MODEL_ORDER else 999
    )
    out = (
        out.sort_values("model_order")
        .drop(columns=["model_order"])
        .reset_index(drop=True)
    )
    return out


# --------------------------------------------------------------------------- #
# LaTeX tables
# --------------------------------------------------------------------------- #

def save_table_overall(overall: pd.DataFrame, out_path: Path) -> None:
    """Write the overall-performance LaTeX table."""
    df = overall.copy()
    lines = [
        "% Mixed-code benchmark overall performance.",
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Mixed-code benchmark performance across LLMs.}",
        r"\label{tab:mixedcode-overall}",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Model & AUROC & Thr. & TPR & FPR & $\Delta$NPR \\",
        r"\midrule",
    ]
    for _, r in df.iterrows():
        lines.append(
            f"{r['model']} & {r['overall_auc']:.3f} & {r['youden_threshold']:.3f} & "
            f"{r['tpr']:.3f} & {r['fpr']:.3f} & {r['npr_gap']:.3f} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_table_bucket_auc(bucket_df: pd.DataFrame, out_path: Path) -> None:
    """Write the per-bucket AUROC LaTeX table."""
    pivot = (
        bucket_df.pivot_table(
            index=["bucket_order", "bucket_label"],
            columns="model",
            values="auc",
            aggfunc="first",
        )
        .reset_index()
        .sort_values("bucket_order")
    )
    models = [m for m in MODEL_ORDER if m in pivot.columns]

    lines = [
        "% Mixed-code benchmark AUROC by body-length bucket.",
        r"\begin{table}[t]",
        r"\centering\scriptsize",
        r"\caption{Mixed-code benchmark AUROC by implementation-body length bucket.}",
        r"\label{tab:mixedcode-auroc-by-bucket}",
        r"\begin{tabular}{l" + "r" * len(models) + "}",
        r"\toprule",
        "Body length & " + " & ".join(models) + r" \\",
        r"\midrule",
    ]
    for _, r in pivot.iterrows():
        vals = [f"{float(r[m]):.3f}" if pd.notna(r[m]) else "--" for m in models]
        lines.append(f"{r['bucket_label']} & " + " & ".join(vals) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #

def plot_auc_by_bucket(bucket_df: pd.DataFrame, out_dir: Path) -> None:
    """Line plot of detection AUROC across body-length buckets, per model."""
    plt.figure(figsize=(8.8, 4.2))

    for model in MODEL_ORDER:
        g = bucket_df[bucket_df["model"] == model].sort_values("bucket_order")
        if g.empty:
            continue
        plt.plot(g["bucket_label"], g["auc"], marker="o", linewidth=2, label=model)

    plt.axhline(0.5, linestyle="--", linewidth=1.2, color="black")
    plt.text(9.0, 0.515, "random", ha="right", va="bottom", fontsize=9)
    plt.xlabel("Implementation-body length bucket (whitespace tokens)")
    plt.ylabel("Detection AUROC")
    plt.ylim(0.60, 1.01)
    plt.xticks(rotation=35, ha="right")
    plt.legend(
        ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.18)
    )
    plt.tight_layout()

    for ext in ["png", "pdf"]:
        plt.savefig(
            out_dir / f"fig_mixedcode_auc_by_bucket.{ext}",
            dpi=300,
            bbox_inches="tight",
        )
    plt.close()


def plot_overall_auc(overall: pd.DataFrame, out_dir: Path) -> None:
    """Bar chart of overall AUROC per model."""
    overall = overall.copy()
    overall["model_order"] = overall["model"].map(
        lambda m: MODEL_ORDER.index(m) if m in MODEL_ORDER else 999
    )
    overall = overall.sort_values("model_order")

    plt.figure(figsize=(5.6, 3.8))
    bars = plt.bar(overall["model"], overall["overall_auc"])
    plt.axhline(0.5, linestyle="--", linewidth=1.2, color="black")
    plt.ylabel("Overall AUROC")
    plt.xlabel("Model")
    plt.ylim(0.50, 1.00)

    for bar, val in zip(bars, overall["overall_auc"]):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.012,
            f"{val:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    plt.tight_layout()
    for ext in ["png", "pdf"]:
        plt.savefig(
            out_dir / f"fig_mixedcode_overall_auc.{ext}",
            dpi=300,
            bbox_inches="tight",
        )
    plt.close()


def plot_npr_gap_by_bucket(bucket_df: pd.DataFrame, out_dir: Path) -> None:
    """Line plot of the mean NPR gap (AGC - HWC) across buckets, per model."""
    plt.figure(figsize=(8.8, 4.2))

    for model in MODEL_ORDER:
        g = bucket_df[bucket_df["model"] == model].sort_values("bucket_order")
        if g.empty or g["npr_gap"].isna().all():
            continue
        plt.plot(g["bucket_label"], g["npr_gap"], marker="o", linewidth=2, label=model)

    plt.axhline(0.0, linestyle="--", linewidth=1.2, color="black")
    plt.xlabel("Implementation-body length bucket (whitespace tokens)")
    plt.ylabel("Mean NPR gap (AGC $-$ HWC)")
    plt.xticks(rotation=35, ha="right")
    plt.legend(
        ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.18)
    )
    plt.tight_layout()

    for ext in ["png", "pdf"]:
        plt.savefig(
            out_dir / f"fig_mixedcode_npr_gap_by_bucket.{ext}",
            dpi=300,
            bbox_inches="tight",
        )
    plt.close()


# --------------------------------------------------------------------------- #
# Discovery / CLI
# --------------------------------------------------------------------------- #

def list_discovered_files(logs_dir: Path) -> None:
    """Print every result file matched by the expected glob patterns."""
    patterns = [
        "npr_scores_main_mixedcode_benchmark_mixedcode_*_50files.csv",
        "npr_scores_main_mixedcode_benchmark_mixedcode_*_50files_bucket_summary.csv",
        "npr_chunks_main_mixedcode_benchmark_mixedcode_*_50files.csv",
        "results_cache_main_mixedcode_benchmark_mixedcode_*_50files.pkl",
    ]

    print("=" * 80)
    print("Discovered mixed-code result files")
    print("=" * 80)
    for pattern in patterns:
        files = sorted(logs_dir.glob(pattern))
        print(f"\n[{pattern}]")
        if not files:
            print("  none")
        for p in files:
            print(f"  {p}")
    print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--logs_dir",
        default="../logs",
        help="Directory containing mixed-code CSV/PKL results.",
    )
    parser.add_argument(
        "--out_dir",
        default="../figure/mixedcode",
        help="Directory for combined CSVs, tables, and figures.",
    )
    parser.add_argument(
        "--list_only",
        action="store_true",
        help="Only list discovered CSV/PKL files and exit.",
    )
    parser.add_argument(
        "--include_gemma",
        action="store_true",
        help="Include Gemma if result files are present.",
    )
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir).expanduser()
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not logs_dir.exists():
        raise FileNotFoundError(f"logs_dir does not exist: {logs_dir}")

    list_discovered_files(logs_dir)
    if args.list_only:
        return

    bucket_files = sorted(
        logs_dir.glob(
            "npr_scores_main_mixedcode_benchmark_mixedcode_*_50files_bucket_summary.csv"
        )
    )
    score_files = sorted(
        p
        for p in logs_dir.glob(
            "npr_scores_main_mixedcode_benchmark_mixedcode_*_50files.csv"
        )
        if not p.name.endswith("_bucket_summary.csv")
    )

    if not args.include_gemma:
        bucket_files = [p for p in bucket_files if "gemma" not in p.name.lower()]
        score_files = [p for p in score_files if "gemma" not in p.name.lower()]

    if not bucket_files:
        raise FileNotFoundError("No bucket-summary CSV files found.")
    if not score_files:
        raise FileNotFoundError("No per-function score CSV files found.")

    bucket_df = pd.concat(
        [load_bucket_summary(p) for p in bucket_files], ignore_index=True
    )
    score_df = pd.concat([load_score_csv(p) for p in score_files], ignore_index=True)

    # Keep the known model order.
    bucket_df["model_order"] = bucket_df["model"].map(
        lambda m: MODEL_ORDER.index(m) if m in MODEL_ORDER else 999
    )
    bucket_df = (
        bucket_df.sort_values(["model_order", "bucket_order"])
        .drop(columns=["model_order"])
        .reset_index(drop=True)
    )

    overall = compute_overall(score_df)

    bucket_csv = out_dir / "mixedcode_bucket_summary_combined.csv"
    overall_csv = out_dir / "mixedcode_overall_summary.csv"
    bucket_df.to_csv(bucket_csv, index=False)
    overall.to_csv(overall_csv, index=False)

    save_table_overall(overall, out_dir / "table_mixedcode_overall.tex")
    save_table_bucket_auc(bucket_df, out_dir / "table_mixedcode_auc_by_bucket.tex")

    plot_auc_by_bucket(bucket_df, out_dir)
    plot_overall_auc(overall, out_dir)
    plot_npr_gap_by_bucket(bucket_df, out_dir)

    print()
    print("=" * 80)
    print("Saved mixed-code paper artifacts")
    print("=" * 80)
    print(f"Combined bucket CSV: {bucket_csv}")
    print(f"Overall CSV:         {overall_csv}")
    print(f"LaTeX overall:       {out_dir / 'table_mixedcode_overall.tex'}")
    print(f"LaTeX bucket AUC:    {out_dir / 'table_mixedcode_auc_by_bucket.tex'}")
    print(f"Figure:              {out_dir / 'fig_mixedcode_auc_by_bucket.png'}")
    print(f"Figure:              {out_dir / 'fig_mixedcode_overall_auc.png'}")
    print(f"Figure:              {out_dir / 'fig_mixedcode_npr_gap_by_bucket.png'}")
    print("=" * 80)

    print()
    print("Overall summary:")
    print(
        overall[
            ["model", "n_total", "overall_auc", "youden_threshold", "tpr", "fpr", "npr_gap"]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()