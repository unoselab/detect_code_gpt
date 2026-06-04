#!/usr/bin/env python3
"""analyze_by_length.py

Stratified AUROC analysis by token length, reusing the per-chunk cache produced
by main_adapter.py (results_cache_main_adapter_*.pkl). NO rescoring / GPU needed.

It answers two different questions:

  (1) PAIR-LEVEL  -- "Does detection work better on longer functions?"
      Each (HWC, MGC) pair gets one aggregate NPR per side; the pair is bucketed
      by min(HWC body tokens, MGC body tokens); AUROC is computed within each
      length bucket over the aggregated pair scores.

  (2) CHUNK-LEVEL -- "At a given chunk length, does NPR separate human vs machine?"
      Every scored chunk is pooled by its own token count; within each bucket we
      compute AUROC of HWC chunks (label 0) vs MGC chunks (label 1). This directly
      tests the hypothesis that short chunks are noisy (NPR<1 degenerates).

Buckets: both a FIXED scheme (<20, 20-60, 60-128, >128) and DATA-DRIVEN quartiles
are reported, so a skewed length distribution can't hide in a single scheme.

AUROC is computed with the project's own get_roc_metrics (reused), which expects
two equal-length lists and filters NaNs pairwise; for the chunk-level (unpaired)
case we fall back to sklearn.roc_auc_score on the pooled labels.

Usage
-----
    python analyze_by_length.py \
        --cache ../logs/results_cache_main_adapter_starcoder2-7b_4500.pkl \
        --aggregate weighted_mean
"""

import os
import sys
import math
import pickle
import argparse

import numpy as np
from loguru import logger
from sklearn.metrics import roc_auc_score

# Reuse the project's paired AUROC (same function main.py / main_adapter.py use).
from baselines.utils.run_baseline import get_roc_metrics


# ---------------------------------------------------------------------------
# Aggregation (must match main_adapter.aggregate_npr exactly)
# ---------------------------------------------------------------------------
def aggregate_npr(chunks, method):
    valid = [c for c in chunks if (not c["low_conf"]) and (not math.isnan(c["npr"]))]
    if not valid:
        return float("nan")
    if method == "mean":
        return float(np.mean([c["npr"] for c in valid]))
    if method == "max":
        return float(max(c["npr"] for c in valid))
    wsum = sum(c["npr"] * c["n_tokens"] for c in valid)
    tsum = sum(c["n_tokens"] for c in valid)
    return wsum / tsum if tsum else float("nan")


def body_tokens(chunks):
    """Total scored body length = sum of token counts over scorable chunks."""
    return sum(c["n_tokens"] for c in chunks
               if (not c["low_conf"]) and (not math.isnan(c["npr"])))


# ---------------------------------------------------------------------------
# Bucketing
# ---------------------------------------------------------------------------
FIXED_EDGES = [0, 20, 60, 128, float("inf")]
FIXED_LABELS = ["<20", "20-60", "60-128", ">128"]


def fixed_bucket(n):
    for i in range(len(FIXED_EDGES) - 1):
        if FIXED_EDGES[i] <= n < FIXED_EDGES[i + 1]:
            return FIXED_LABELS[i]
    return FIXED_LABELS[-1]


def quartile_edges(values):
    """Return 4 quartile bucket edges + human-readable labels from observed values."""
    qs = np.percentile(values, [25, 50, 75])
    edges = [0, qs[0], qs[1], qs[2], float("inf")]
    labels = [f"<={qs[0]:.0f}", f"{qs[0]:.0f}-{qs[1]:.0f}",
              f"{qs[1]:.0f}-{qs[2]:.0f}", f">{qs[2]:.0f}"]
    return edges, labels


def bucket_by_edges(n, edges, labels):
    for i in range(len(edges) - 1):
        if edges[i] <= n < edges[i + 1]:
            return labels[i]
    return labels[-1]


# ---------------------------------------------------------------------------
# AUROC helpers
# ---------------------------------------------------------------------------
def paired_auroc(real, samp):
    """Project-style paired AUROC; real/samp must be equal length (NaNs dropped here)."""
    real = np.asarray(real, float)
    samp = np.asarray(samp, float)
    keep = (~np.isnan(real)) & (~np.isnan(samp))
    real, samp = real[keep], samp[keep]
    if len(real) < 2:
        return float("nan"), len(real)
    # both classes identical-length -> safe for get_roc_metrics
    _, _, auc = get_roc_metrics(list(real), list(samp))
    return auc, len(real)


def pooled_auroc(hwc_scores, mgc_scores):
    """Unpaired AUROC over pooled chunk scores (HWC=0, MGC=1)."""
    hwc = [x for x in hwc_scores if not math.isnan(x)]
    mgc = [x for x in mgc_scores if not math.isnan(x)]
    if len(hwc) < 1 or len(mgc) < 1 or (len(hwc) + len(mgc)) < 3:
        return float("nan"), len(hwc), len(mgc)
    y = [0] * len(hwc) + [1] * len(mgc)
    s = hwc + mgc
    if len(set(y)) < 2:
        return float("nan"), len(hwc), len(mgc)
    return float(roc_auc_score(y, s)), len(hwc), len(mgc)


def pct_below_one(scores):
    s = [x for x in scores if not math.isnan(x)]
    if not s:
        return float("nan")
    return 100.0 * sum(1 for x in s if x < 1.0) / len(s)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_pair_table(results, aggregate, edges, labels, title):
    print()
    print("=" * 78)
    print(f"PAIR-LEVEL AUROC by min(HWC,MGC) body tokens  [{title}]  agg={aggregate}")
    print("=" * 78)
    print(f"{'bucket':>12} | {'n_pairs':>8} | {'AUROC':>7} | "
          f"{'HWC mean':>9} | {'MGC mean':>9} | {'sep':>7}")
    print("-" * 78)

    # bucket pairs by min body length
    buckets = {lab: {"real": [], "samp": []} for lab in labels}
    for r in results:
        h_npr = aggregate_npr(r["human_chunks"], aggregate)
        m_npr = aggregate_npr(r["lm_chunks"], aggregate)
        h_len = body_tokens(r["human_chunks"])
        m_len = body_tokens(r["lm_chunks"])
        n_min = min(h_len, m_len)
        lab = bucket_by_edges(n_min, edges, labels)
        buckets[lab]["real"].append(h_npr)
        buckets[lab]["samp"].append(m_npr)

    all_real, all_samp = [], []
    for lab in labels:
        real, samp = buckets[lab]["real"], buckets[lab]["samp"]
        all_real += real
        all_samp += samp
        auc, n = paired_auroc(real, samp)
        rv = np.array([x for x in real if not math.isnan(x)])
        sv = np.array([x for x in samp if not math.isnan(x)])
        hm = rv.mean() if len(rv) else float("nan")
        mm = sv.mean() if len(sv) else float("nan")
        sep = (mm - hm) if (len(rv) and len(sv)) else float("nan")
        print(f"{lab:>12} | {n:>8} | {auc:>7.4f} | "
              f"{hm:>9.4f} | {mm:>9.4f} | {sep:>7.4f}")
    auc_all, n_all = paired_auroc(all_real, all_samp)
    print("-" * 78)
    print(f"{'ALL':>12} | {n_all:>8} | {auc_all:>7.4f} |")


def print_chunk_table(results, edges, labels, title):
    print()
    print("=" * 78)
    print(f"CHUNK-LEVEL AUROC by chunk token count  [{title}]")
    print("=" * 78)
    print(f"{'bucket':>12} | {'HWC ch':>7} | {'MGC ch':>7} | {'AUROC':>7} | "
          f"{'HWC<1%':>7} | {'MGC<1%':>7}")
    print("-" * 78)

    buckets = {lab: {"hwc": [], "mgc": []} for lab in labels}
    for r in results:
        for role, key in (("hwc", "human_chunks"), ("mgc", "lm_chunks")):
            for c in r[key]:
                if c["low_conf"] or math.isnan(c["npr"]):
                    continue
                lab = bucket_by_edges(c["n_tokens"], edges, labels)
                buckets[lab][role].append(c["npr"])

    all_h, all_m = [], []
    for lab in labels:
        hwc, mgc = buckets[lab]["hwc"], buckets[lab]["mgc"]
        all_h += hwc
        all_m += mgc
        auc, nh, nm = pooled_auroc(hwc, mgc)
        print(f"{lab:>12} | {nh:>7} | {nm:>7} | {auc:>7.4f} | "
              f"{pct_below_one(hwc):>6.1f}% | {pct_below_one(mgc):>6.1f}%")
    auc_all, nh, nm = pooled_auroc(all_h, all_m)
    print("-" * 78)
    print(f"{'ALL':>12} | {nh:>7} | {nm:>7} | {auc_all:>7.4f} | "
          f"{pct_below_one(all_h):>6.1f}% | {pct_below_one(all_m):>6.1f}%")


def main():
    ap = argparse.ArgumentParser(description="Stratified AUROC by token length from a main_adapter cache.")
    ap.add_argument("--cache", required=True, help="Path to results_cache_main_adapter_*.pkl")
    ap.add_argument("--aggregate", choices=["weighted_mean", "mean", "max"],
                    default="weighted_mean", help="Pair-level aggregation method.")
    args = ap.parse_args()

    cache = os.path.expanduser(args.cache)
    with open(cache, "rb") as f:
        results = pickle.load(f)
    logger.info(f"Loaded {len(results)} pair results from {cache}")

    # ---- data-driven quartile edges from the two length distributions ----
    pair_min_lens, chunk_lens = [], []
    for r in results:
        h_len = body_tokens(r["human_chunks"])
        m_len = body_tokens(r["lm_chunks"])
        if h_len > 0 and m_len > 0:
            pair_min_lens.append(min(h_len, m_len))
        for key in ("human_chunks", "lm_chunks"):
            for c in r[key]:
                if not c["low_conf"] and not math.isnan(c["npr"]):
                    chunk_lens.append(c["n_tokens"])

    logger.info(f"Pair min-length: median={np.median(pair_min_lens):.0f}, "
                f"p25={np.percentile(pair_min_lens,25):.0f}, "
                f"p75={np.percentile(pair_min_lens,75):.0f}, max={max(pair_min_lens)}")
    logger.info(f"Chunk length: median={np.median(chunk_lens):.0f}, "
                f"p25={np.percentile(chunk_lens,25):.0f}, "
                f"p75={np.percentile(chunk_lens,75):.0f}, max={max(chunk_lens)}")

    # ===== PAIR-LEVEL =====
    print_pair_table(results, args.aggregate, FIXED_EDGES, FIXED_LABELS, "fixed edges")
    pe, pl = quartile_edges(pair_min_lens)
    print_pair_table(results, args.aggregate, pe, pl, "quartiles")

    # ===== CHUNK-LEVEL =====
    print_chunk_table(results, FIXED_EDGES, FIXED_LABELS, "fixed edges")
    ce, cl = quartile_edges(chunk_lens)
    print_chunk_table(results, ce, cl, "quartiles")

    print()
    logger.info("Done. Read the chunk-level <20 bucket + the HWC<1%/MGC<1% columns "
                "to confirm whether short chunks are the noise source.")


if __name__ == "__main__":
    main()