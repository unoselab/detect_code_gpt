#!/usr/bin/env python3
"""main_v2.py

CSV-driven DetectCodeGPT NPR + AUROC, reusing the existing project code.

Pipeline
--------
1. Load (human, lm) pairs from the merged CSV (positional argument).
2. For each snippet compute NPR using perturb_type 'random-insert-space+newline':
       NPR(x) = mean(perturbed log-rank) / original log-rank
   - original log-rank  -> reuses baselines.rank.get_rank
   - perturbations      -> reuses main.perturb_texts
   - perturbed log-rank -> reuses baselines.rank.get_ranks
3. AUROC over HWC (label 0) vs MGC (label 1) NPR scores:
   - reuses baselines.utils.run_baseline.get_roc_metrics

Nothing is reimplemented. The scoring (base) model is loaded exactly like
main.py's interactive / batch_benchmark modes. The mask-filling model is NOT
loaded, because perturb_type 'random-insert-space+newline' never calls it.

Usage
-----
    # full run (slow: GPU forward passes on every snippet)
    python main_v2.py merged_4500.csv --base_model_name bigcode/starcoder2-7b

    # quick smoke test
    python main_v2.py merged_4500.csv --limit 5 --preview

    # re-run AUROC / thresholds without rescoring
    python main_v2.py merged_4500.csv --load_cached_results ../logs/results_cache_main_v2_<name>.pkl
"""

import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import sys
import re
import math
import pickle
import argparse

import numpy as np
import pandas as pd
from tqdm import tqdm
from loguru import logger
import torch

# ---------------------------------------------------------------------------
# Reuse existing project code (do NOT reimplement any of this).
# Importing main.py also runs its module-level setup, which is harmless here.
# ---------------------------------------------------------------------------
from main import perturb_texts, setup_args
from baselines.rank import get_rank, get_ranks
from baselines.utils.run_baseline import get_roc_metrics
from baselines.utils.preprocessing import preprocess_and_save
from baselines.utils.loadmodel import load_base_model_and_tokenizer


# idx format guaranteed by the dataset: "line<NUM>_human" / "line<NUM>_lm"
LINE_ID_PATTERN = re.compile(r"^line(\d+)_(human|lm)$")


def load_pairs(csv_path):
    """Read the merged CSV and return a list of (line_num, human_code, lm_code).

    Uses a real CSV parser (the `code` field is multi-line). Enforces the
    dataset contract: even row count, adjacent rows form a pair, first is
    *_human, second is *_lm, both share the same lineX.
    """
    df = pd.read_csv(csv_path, usecols=["idx", "code", "label"])
    assert len(df) % 2 == 0, f"Expected an even row count, got {len(df)}"

    pairs = []
    for i in range(0, len(df), 2):
        human_row = df.iloc[i]
        lm_row = df.iloc[i + 1]

        h_match = LINE_ID_PATTERN.match(str(human_row["idx"]))
        l_match = LINE_ID_PATTERN.match(str(lm_row["idx"]))
        assert h_match and l_match, f"Unexpected idx format at rows {i}, {i + 1}"

        h_num, h_type = h_match.groups()
        l_num, l_type = l_match.groups()
        assert h_num == l_num, f"Pair line mismatch at row {i}: {h_num} vs {l_num}"
        assert h_type == "human" and l_type == "lm", f"Pair order wrong at row {i}"
        assert human_row["label"] == "human" and lm_row["label"] == "lm", \
            f"Label/idx disagreement at row {i}"

        pairs.append((int(h_num), human_row["code"], lm_row["code"]))

    logger.info(f"Loaded {len(pairs)} valid (human, lm) pairs from {csv_path}")
    return pairs


def build_full_args(cli):
    """Reuse main.setup_args() to obtain a fully-populated args namespace.

    We inject argv so that every field consumed by preprocess_and_save,
    load_base_model_and_tokenizer, get_rank, get_ranks, and perturb_texts
    keeps main.py's defaults; we only set the few flags that matter here.
    """
    injected = [
        "--base_model_name",        cli.base_model_name,
        "--n_perturbation_list",    str(cli.n_perturbation),
        "--perturb_type",           "random-insert-space+newline",
        "--pct_words_masked",       str(cli.pct_words_masked),
        "--span_length",            str(cli.span_length),
        "--chunk_size",             str(cli.chunk_size),
        "--n_perturbation_rounds",  str(cli.n_perturbation_rounds),
        "--DEVICE",                 cli.device,
        "--cache_dir",              cli.cache_dir,
        "--output_name",            cli.output_name,
    ]
    saved_argv = sys.argv
    try:
        sys.argv = ["main.py"] + injected
        args = setup_args()
    finally:
        sys.argv = saved_argv
    return args


def compute_npr(code, args, model_config, k):
    """NPR for a single snippet, reusing get_rank / perturb_texts / get_ranks.

    Returns (npr, original_logrank, mean_perturbed_logrank).
    """
    orig_logrank = get_rank(code, args, model_config, log=True)

    copies = [code for _ in range(k)]
    p_texts = perturb_texts(copies, args, model_config)
    p_ranks = get_ranks(p_texts, args, model_config, log=True)

    valid = [r for r in p_ranks if not math.isnan(r)]
    mean_p_logrank = float(np.mean(valid)) if valid else float("nan")
    npr = mean_p_logrank / orig_logrank if orig_logrank else float("nan")
    return npr, orig_logrank, mean_p_logrank


def report_and_save(results, csv_path):
    """Print AUROC + summary stats + Youden's J threshold, and write a CSV."""
    real = np.array([r["human_npr"] for r in results], dtype=float)  # HWC, label 0
    samp = np.array([r["lm_npr"]    for r in results], dtype=float)  # MGC, label 1

    # Drop NaNs independently; get_roc_metrics builds its own labels per list.
    real_v = real[~np.isnan(real)]
    samp_v = samp[~np.isnan(samp)]
    n_nan = (len(real) - len(real_v)) + (len(samp) - len(samp_v))
    if n_nan:
        logger.warning(f"Dropped {n_nan} NaN NPR value(s) before AUROC")

    if len(real_v) == 0 or len(samp_v) == 0:
        logger.error("No valid NPR scores in one of the classes; cannot compute AUROC.")
        return float("nan")

    # ----- AUROC (reused) -----
    _, _, roc_auc = get_roc_metrics(list(real_v), list(samp_v))

    # ----- summary statistics -----
    print()
    print("=" * 72)
    print(f"DetectCodeGPT NPR scores (HWC n={len(real_v)}, MGC n={len(samp_v)})")
    print("=" * 72)
    print(f"HWC (human): mean={real_v.mean():.4f}  std={real_v.std():.4f}  "
          f"median={np.median(real_v):.4f}  min={real_v.min():.4f}  max={real_v.max():.4f}")
    print(f"MGC (lm):    mean={samp_v.mean():.4f}  std={samp_v.std():.4f}  "
          f"median={np.median(samp_v):.4f}  min={samp_v.min():.4f}  max={samp_v.max():.4f}")
    print(f"Mean separation (MGC - HWC): {samp_v.mean() - real_v.mean():.4f}")

    # ----- percentile candidates -----
    print()
    for label, arr in [("HWC", real_v), ("MGC", samp_v)]:
        p = np.percentile(arr, [5, 25, 50, 75, 95])
        print(f"  {label} percentiles: 5%={p[0]:.4f}  25%={p[1]:.4f}  "
              f"50%={p[2]:.4f}  75%={p[3]:.4f}  95%={p[4]:.4f}")

    # ----- Youden's J optimal threshold -----
    from sklearn.metrics import roc_curve
    y_true = np.concatenate([np.zeros_like(real_v), np.ones_like(samp_v)])
    y_score = np.concatenate([real_v, samp_v])
    fpr, tpr, thresholds = roc_curve(y_true, y_score)
    j_stat = tpr - fpr
    best = int(np.argmax(j_stat))
    print()
    print(f"Youden's J optimal threshold: {thresholds[best]:.4f}  "
          f"(TPR={tpr[best]:.4f}, FPR={fpr[best]:.4f}, J={j_stat[best]:.4f})")
    print(f"  decision rule: NPR > {thresholds[best]:.4f}  =>  predict MGC, else HWC")

    print()
    print("=" * 72)
    print(f"ROC AUC of DetectCodeGPT (NPR): {roc_auc:.4f}")
    print("=" * 72)

    # ----- per-pair CSV -----
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    with open(csv_path, "w") as f:
        f.write("line_num,human_npr,lm_npr,winner,"
                "human_logrank,lm_logrank,"
                "human_perturbed_logrank,lm_perturbed_logrank\n")
        for r in results:
            winner = "MGC" if (r["lm_npr"] > r["human_npr"]) else "HWC"
            f.write(f"{r['line_num']},{r['human_npr']:.6f},{r['lm_npr']:.6f},{winner},"
                    f"{r['human_logrank']:.6f},{r['lm_logrank']:.6f},"
                    f"{r['human_perturbed_logrank']:.6f},{r['lm_perturbed_logrank']:.6f}\n")
    print()
    logger.info(f"Saved per-pair NPR scores to: {csv_path}")
    return roc_auc


def main():
    parser = argparse.ArgumentParser(
        description="Compute DetectCodeGPT NPR + AUROC from a (human, lm) pairs CSV "
                    "using the random-insert-space+newline perturbation strategy."
    )
    parser.add_argument("--csv_path", help="Path to the merged pairs CSV",required=True)
    parser.add_argument("--base_model_name", type=str, default="bigcode/starcoder2-7b",
                        help="HuggingFace ID of the scoring model. Default: bigcode/starcoder2-7b")
    parser.add_argument("--n_perturbation", type=int, default=50,
                        help="Perturbed copies per snippet (k). Default: 50")
    parser.add_argument("--pct_words_masked", type=float, default=0.5)
    parser.add_argument("--span_length", type=int, default=2)
    parser.add_argument("--chunk_size", type=int, default=10,
                        help="Even number; controls the per-chunk space/newline 50:50 split. Default: 10")
    parser.add_argument("--n_perturbation_rounds", type=int, default=1)
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--cache_dir", type=str, default="~/.cache/huggingface/hub")
    parser.add_argument("--output_name", type=str, default="main_v2")
    parser.add_argument("--output_csv", type=str, default=None,
                        help="Per-pair CSV path. Default: ../logs/npr_scores_main_v2_<output_name>.csv")
    parser.add_argument("--results_cache", type=str, default=None,
                        help="Pickle path to write NPR results. "
                             "Default: ../logs/results_cache_main_v2_<output_name>.pkl")
    parser.add_argument("--load_cached_results", type=str, default=None,
                        help="Skip ALL scoring; load NPR results from this pickle and "
                             "recompute AUROC / thresholds / CSV (~1 sec).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only the first N pairs (debugging).")
    parser.add_argument("--preview", action="store_true",
                        help="Print a one-line NPR verdict per pair as it is scored.")
    cli = parser.parse_args()

    csv_path = os.path.expanduser(cli.csv_path)
    out_csv = os.path.expanduser(
        cli.output_csv or f"../logs/npr_scores_main_v2_{cli.output_name}.csv"
    )

    # -----------------------------------------------------------------
    # Fast path: reuse cached NPR results, skip all scoring.
    # -----------------------------------------------------------------
    if cli.load_cached_results is not None:
        cache = os.path.expanduser(cli.load_cached_results)
        logger.info(f"Loading cached NPR results from {cache} -- skipping scoring")
        with open(cache, "rb") as f:
            results = pickle.load(f)
        logger.info(f"Loaded {len(results)} cached pair results")
        report_and_save(results, out_csv)
        return

    # -----------------------------------------------------------------
    # Normal path: load data, load scoring model, score, report.
    # -----------------------------------------------------------------
    pairs = load_pairs(csv_path)
    if cli.limit is not None:
        pairs = pairs[:cli.limit]
        logger.info(f"Limited to the first {len(pairs)} pairs")

    args = build_full_args(cli)
    logger.info(
        f"Config: scoring_model={cli.base_model_name}, perturb_type={args.perturb_type}, "
        f"k={cli.n_perturbation}, pct_words_masked={args.pct_words_masked}, "
        f"span/mean={args.span_length}, chunk_size={args.chunk_size}"
    )

    # Load the base scoring model only (same as main.py interactive/batch modes).
    cache_dir, _, _ = preprocess_and_save(args)
    model_config = {"cache_dir": cache_dir}
    logger.info("Loading base scoring model...")
    model_config = load_base_model_and_tokenizer(args, model_config)

    # Score every pair.
    results = []
    for line_num, human_code, lm_code in tqdm(pairs, desc="Scoring pairs"):
        h_npr, h_lr, h_plr = compute_npr(human_code, args, model_config, cli.n_perturbation)
        l_npr, l_lr, l_plr = compute_npr(lm_code, args, model_config, cli.n_perturbation)
        results.append({
            "line_num":                 line_num,
            "human_npr":                h_npr,
            "human_logrank":            h_lr,
            "human_perturbed_logrank":  h_plr,
            "lm_npr":                   l_npr,
            "lm_logrank":               l_lr,
            "lm_perturbed_logrank":     l_plr,
        })
        if cli.preview:
            winner = "MGC" if l_npr > h_npr else "HWC"
            print(f"  line{line_num}: HWC_NPR={h_npr:.4f}  MGC_NPR={l_npr:.4f}  -> {winner}")
        if len(results) % 200 == 0:
            torch.cuda.empty_cache()

    torch.cuda.empty_cache()

    # Cache NPR results (tiny: just numbers) for fast re-analysis.
    cache_path = os.path.expanduser(
        cli.results_cache or f"../logs/results_cache_main_v2_{cli.output_name}.pkl"
    )
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(results, f)
    logger.info(f"Cached NPR results to {cache_path}")
    logger.info(f"To re-run AUROC without rescoring: --load_cached_results {cache_path}")

    report_and_save(results, out_csv)


if __name__ == "__main__":
    main()