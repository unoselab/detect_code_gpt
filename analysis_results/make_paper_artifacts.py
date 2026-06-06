#!/usr/bin/env python3
"""make_paper_artifacts.py

Build paper-ready artifacts (ICSE/FSE style) from one or more main_adapter.py
per-chunk caches (results_cache_main_adapter_*.pkl). NO rescoring / GPU needed.

Outputs:
  1. LaTeX (booktabs):
       - MAIN  : pair-level AUROC by QUARTILE length buckets, with bootstrap 95% CI,
                 one column block per model.
       - APPENDIX: chunk-level AUROC by quartile buckets (mechanism evidence),
                 plus the NPR<1 degenerate rate per bucket.
  2. Figure (matplotlib -> PDF, vector):
       - grouped bar of pair-level AUROC per length bucket per model, with a
         random-baseline line at 0.5 and bootstrap CI whiskers.

Length buckets are DATA-DRIVEN quartiles (per the paper decision). When multiple
models are given, quartile edges are computed on the POOLED min-length / chunk-length
distribution so all models share identical buckets (required for a fair shared table).

Aggregation for pair-level scores matches main_adapter.aggregate_npr.

Usage 1
-----
    python make_paper_artifacts.py \
        --cache "StarCoder2-7B=../logs/results_cache_main_adapter_starcoder2-7b_4500_refreshed.pkl" \
        --aggregate weighted_mean \
        --out-dir ../paper_artifacts
Usage 2
-----
    python make_paper_artifacts.py \
        --cache "StarCoder2-7B=../logs/results_cache_main_adapter_starcoder2-7b_4500_refreshed.pkl" \
        --cache "CodeLlama-7B=../logs/results_cache_main_adapter_codellama-7b_4500_refreshed.pkl" \
        --aggregate weighted_mean \
        --out-dir ../paper_artifacts
"""

import os
import math
import pickle
import argparse
from collections import OrderedDict

import numpy as np

try:
    from sklearn.metrics import roc_auc_score
except Exception as e:  # pragma: no cover
    raise SystemExit("scikit-learn is required: pip install scikit-learn") from e


# ---------------------------------------------------------------------------
# Aggregation (matches main_adapter.aggregate_npr) and length helpers
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
    return sum(c["n_tokens"] for c in chunks
               if (not c["low_conf"]) and (not math.isnan(c["npr"])))


# ---------------------------------------------------------------------------
# Bootstrap AUROC + CI
# ---------------------------------------------------------------------------
def auroc_with_ci(labels, scores, n_boot=2000, seed=0):
    """Return (auroc, lo, hi) with a percentile bootstrap 95% CI.

    labels: 0/1 array; scores: float array (higher => more MGC).
    NaN scores are dropped. Returns (nan, nan, nan) if a class is missing.
    """
    labels = np.asarray(labels, float)
    scores = np.asarray(scores, float)
    m = ~np.isnan(scores)
    labels, scores = labels[m], scores[m]
    if len(set(labels.tolist())) < 2 or len(labels) < 3:
        return float("nan"), float("nan"), float("nan")
    point = float(roc_auc_score(labels, scores))
    rng = np.random.default_rng(seed)
    n = len(labels)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yl, ys = labels[idx], scores[idx]
        if len(set(yl.tolist())) < 2:
            continue
        boots.append(roc_auc_score(yl, ys))
    if not boots:
        return point, float("nan"), float("nan")
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return point, float(lo), float(hi)


# ---------------------------------------------------------------------------
# Quartile bucketing on pooled distributions
# ---------------------------------------------------------------------------
def quartile_edges(values):
    qs = np.percentile(values, [25, 50, 75])
    edges = [0.0, float(qs[0]), float(qs[1]), float(qs[2]), float("inf")]
    labels = [f"$\\leq${qs[0]:.0f}", f"{qs[0]:.0f}--{qs[1]:.0f}",
              f"{qs[1]:.0f}--{qs[2]:.0f}", f">{qs[2]:.0f}"]
    return edges, labels


def bucket_index(n, edges):
    for i in range(len(edges) - 1):
        if edges[i] <= n < edges[i + 1]:
            return i
    return len(edges) - 2


# ---------------------------------------------------------------------------
# Per-model extraction
# ---------------------------------------------------------------------------
def load_model_data(path, aggregate):
    with open(os.path.expanduser(path), "rb") as f:
        results = pickle.load(f)
    pairs = []   # (min_len, hwc_npr, lm_npr)
    chunks = []  # (n_tokens, npr, label)  label 0=HWC 1=MGC
    for r in results:
        h_npr = aggregate_npr(r["human_chunks"], aggregate)
        m_npr = aggregate_npr(r["lm_chunks"], aggregate)
        h_len = body_tokens(r["human_chunks"])
        m_len = body_tokens(r["lm_chunks"])
        if h_len > 0 and m_len > 0:
            pairs.append((min(h_len, m_len), h_npr, m_npr))
        for role, key in ((0, "human_chunks"), (1, "lm_chunks")):
            for c in r[key]:
                if c["low_conf"] or math.isnan(c["npr"]):
                    continue
                chunks.append((c["n_tokens"], c["npr"], role))
    return results, pairs, chunks


def pair_bucket_stats(pairs, edges, n_boot, seed):
    """Per-bucket pair-level AUROC (HWC=0 vs MGC=1) with CI, plus separation."""
    K = len(edges) - 1
    out = []
    for b in range(K):
        rows = [(h, m) for (ln, h, m) in pairs if bucket_index(ln, edges) == b]
        h = np.array([x[0] for x in rows], float)
        m = np.array([x[1] for x in rows], float)
        keep = (~np.isnan(h)) & (~np.isnan(m))
        h, m = h[keep], m[keep]
        n = len(h)
        labels = np.concatenate([np.zeros(n), np.ones(n)])
        scores = np.concatenate([h, m])
        auc, lo, hi = auroc_with_ci(labels, scores, n_boot=n_boot, seed=seed)
        sep = (m.mean() - h.mean()) if n else float("nan")
        out.append({"n": n, "auc": auc, "lo": lo, "hi": hi,
                    "hwc_mean": h.mean() if n else float("nan"),
                    "mgc_mean": m.mean() if n else float("nan"), "sep": sep})
    # overall
    h = np.array([x[1] for x in pairs], float)
    m = np.array([x[2] for x in pairs], float)
    keep = (~np.isnan(h)) & (~np.isnan(m))
    h, m = h[keep], m[keep]
    n = len(h)
    auc, lo, hi = auroc_with_ci(np.concatenate([np.zeros(n), np.ones(n)]),
                                np.concatenate([h, m]), n_boot=n_boot, seed=seed)
    overall = {"n": n, "auc": auc, "lo": lo, "hi": hi}
    return out, overall


def chunk_bucket_stats(chunks, edges, n_boot, seed):
    K = len(edges) - 1
    out = []
    for b in range(K):
        rows = [(npr, role) for (nt, npr, role) in chunks if bucket_index(nt, edges) == b]
        scores = np.array([x[0] for x in rows], float)
        labels = np.array([x[1] for x in rows], float)
        n_h = int((labels == 0).sum())
        n_m = int((labels == 1).sum())
        auc, lo, hi = auroc_with_ci(labels, scores, n_boot=n_boot, seed=seed)
        below1 = 100.0 * np.mean(scores < 1.0) if len(scores) else float("nan")
        out.append({"n_h": n_h, "n_m": n_m, "auc": auc, "lo": lo, "hi": hi, "below1": below1})
    return out


# ---------------------------------------------------------------------------
# LaTeX emitters (booktabs)
# ---------------------------------------------------------------------------
def fmt_ci(d):
    if math.isnan(d["auc"]):
        return "--"
    return f"{d['auc']:.3f}\\,\\tiny[{d['lo']:.3f},{d['hi']:.3f}]"


def latex_main_table(models, bucket_labels, per_model_pair, per_model_overall):
    cols = "l" + "r" + "c" * len(models)
    lines = []
    lines.append("% MAIN: pair-level AUROC by length quartile (bootstrap 95% CI).")
    lines.append("\\begin{table}[t]")
    lines.append("\\centering")
    lines.append("\\caption{DetectCodeGPT (NPR) detection AUROC stratified by function "
                 "body length (whitespace tokens), pair-level. Buckets are quartiles of "
                 "$\\min(\\text{HWC},\\text{MGC})$ body length. Values are AUROC with a "
                 "percentile bootstrap 95\\% CI. AUROC $<0.5$ indicates a sign reversal "
                 "(human code scores higher than machine code).}")
    lines.append("\\label{tab:auroc-by-length}")
    lines.append("\\begin{tabular}{" + cols + "}")
    lines.append("\\toprule")
    header = "Length bucket & \\#pairs & " + " & ".join(models) + " \\\\"
    lines.append(header)
    lines.append("\\midrule")
    # n_pairs is shared across models (same dataset); take from first model.
    first = models[0]
    for i, lab in enumerate(bucket_labels):
        npairs = per_model_pair[first][i]["n"]
        cells = " & ".join(fmt_ci(per_model_pair[mdl][i]) for mdl in models)
        lines.append(f"{lab} & {npairs} & {cells} \\\\")
    lines.append("\\midrule")
    npairs_all = per_model_overall[first]["n"]
    cells_all = " & ".join(fmt_ci(per_model_overall[mdl]) for mdl in models)
    lines.append(f"All & {npairs_all} & {cells_all} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    return "\n".join(lines)


def latex_appendix_table(models, bucket_labels, per_model_chunk):
    # one block of (AUROC, MGC<1%) per model
    cols = "l" + ("rr" * len(models))
    lines = []
    lines.append("% APPENDIX: chunk-level AUROC + degenerate (NPR<1) rate by length quartile.")
    lines.append("\\begin{table}[t]")
    lines.append("\\centering")
    lines.append("\\caption{Chunk-level analysis by chunk length quartile. AUROC pools all "
                 "HWC chunks (label 0) against all MGC chunks (label 1) within a bucket. "
                 "``MGC$<$1\\%'' is the fraction of machine chunks with degenerate NPR $<1$, "
                 "concentrated in the shortest bucket.}")
    lines.append("\\label{tab:chunk-by-length}")
    lines.append("\\begin{tabular}{" + cols + "}")
    lines.append("\\toprule")
    top = "Chunk length & " + " & ".join(
        f"\\multicolumn{{2}}{{c}}{{{m}}}" for m in models) + " \\\\"
    lines.append(top)
    sub = " & " + " & ".join("AUROC & MGC$<$1\\%" for _ in models) + " \\\\"
    lines.append(sub)
    lines.append("\\midrule")
    for i, lab in enumerate(bucket_labels):
        cells = []
        for mdl in models:
            d = per_model_chunk[mdl][i]
            auc = "--" if math.isnan(d["auc"]) else f"{d['auc']:.3f}"
            b1 = "--" if math.isnan(d["below1"]) else f"{d['below1']:.1f}"
            cells.append(f"{auc} & {b1}")
        lines.append(f"{lab} & " + " & ".join(cells) + " \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Figure (matplotlib -> PDF)
# ---------------------------------------------------------------------------
def make_figure(models, bucket_labels, per_model_pair, out_pdf):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    K = len(bucket_labels)
    M = len(models)
    x = np.arange(K)
    width = 0.8 / M
    # colorblind-friendly palette
    palette = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00"]

    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    for j, mdl in enumerate(models):
        aucs = [per_model_pair[mdl][i]["auc"] for i in range(K)]
        los = [per_model_pair[mdl][i]["lo"] for i in range(K)]
        his = [per_model_pair[mdl][i]["hi"] for i in range(K)]
        yerr = np.array([[a - l for a, l in zip(aucs, los)],
                         [h - a for a, h in zip(aucs, his)]])
        ax.bar(x + j * width - 0.4 + width / 2, aucs, width,
               label=mdl, color=palette[j % len(palette)],
               yerr=yerr, capsize=2, error_kw={"linewidth": 0.8})

    ax.axhline(0.5, color="black", linestyle="--", linewidth=1.0)
    ax.text(K - 0.5, 0.51, "random (0.5)", ha="right", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([lab.replace("$\\leq$", "\u2264") for lab in bucket_labels])
    ax.set_xlabel("Function body length (whitespace tokens, quartile buckets)")
    ax.set_ylabel("Detection AUROC")
    ax.set_ylim(0.0, 1.0)
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_pdf, bbox_inches="tight")
    fig.savefig(out_pdf.replace(".pdf", ".png"), dpi=200, bbox_inches="tight")
    print(f"[OK] figure -> {out_pdf} (+ .png)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Build LaTeX tables + figure from caches.")
    ap.add_argument("--cache", action="append", required=True,
                    help="NAME=path to a results_cache pkl. Repeatable for multiple models.")
    ap.add_argument("--aggregate", choices=["weighted_mean", "mean", "max"], default="weighted_mean")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default="paper_artifacts")
    args = ap.parse_args()

    os.makedirs(os.path.expanduser(args.out_dir), exist_ok=True)

    models = OrderedDict()
    for spec in args.cache:
        if "=" not in spec:
            raise SystemExit(f"--cache must be NAME=path, got: {spec}")
        name, path = spec.split("=", 1)
        models[name] = path

    # Load all, pool lengths for shared quartile edges.
    data = {}
    pooled_pair_len, pooled_chunk_len = [], []
    for name, path in models.items():
        _, pairs, chunks = load_model_data(path, args.aggregate)
        data[name] = {"pairs": pairs, "chunks": chunks}
        pooled_pair_len += [ln for (ln, _, _) in pairs]
        pooled_chunk_len += [nt for (nt, _, _) in chunks]
        print(f"[INFO] {name}: {len(pairs)} pairs, {len(chunks)} scored chunks")

    pair_edges, pair_labels = quartile_edges(pooled_pair_len)
    chunk_edges, chunk_labels = quartile_edges(pooled_chunk_len)
    print(f"[INFO] pair-length quartile edges : {pair_edges[1:-1]}")
    print(f"[INFO] chunk-length quartile edges: {chunk_edges[1:-1]}")

    per_model_pair, per_model_overall, per_model_chunk = {}, {}, {}
    for name in models:
        pb, ov = pair_bucket_stats(data[name]["pairs"], pair_edges, args.n_boot, args.seed)
        cb = chunk_bucket_stats(data[name]["chunks"], chunk_edges, args.n_boot, args.seed)
        per_model_pair[name] = pb
        per_model_overall[name] = ov
        per_model_chunk[name] = cb

    model_names = list(models.keys())
    main_tex = latex_main_table(model_names, pair_labels, per_model_pair, per_model_overall)
    appendix_tex = latex_appendix_table(model_names, chunk_labels, per_model_chunk)

    out_dir = os.path.expanduser(args.out_dir)
    with open(os.path.join(out_dir, "table_main_auroc_by_length.tex"), "w") as f:
        f.write(main_tex + "\n")
    with open(os.path.join(out_dir, "table_appendix_chunk_by_length.tex"), "w") as f:
        f.write(appendix_tex + "\n")
    make_figure(model_names, pair_labels, per_model_pair,
                os.path.join(out_dir, "fig_auroc_by_length.pdf"))

    print("\n" + "=" * 72)
    print("MAIN TABLE (also saved to table_main_auroc_by_length.tex)")
    print("=" * 72)
    print(main_tex)
    print("\n" + "=" * 72)
    print("APPENDIX TABLE (also saved to table_appendix_chunk_by_length.tex)")
    print("=" * 72)
    print(appendix_tex)


if __name__ == "__main__":
    main()