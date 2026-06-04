#!/usr/bin/env python3
"""main_adapter.py

CSV-driven DetectCodeGPT NPR + AUROC, reusing the existing project code.

What changed vs. the first version
-----------------------------------
To align with the project's calibration regime (generate_data + batch_benchmark):
  1. STRIP prompt + docstring, score the function BODY only.
     - The CSV `code` is `prompt + body`; the prompt (signature + docstring) is
       human in any realistic scenario and dilutes / false-positives the NPR
       signal (see main.py run_batch_benchmark, lines ~647-651). We drop the
       first top-level def/class signature and its leading docstring, keeping
       only the body, then score that.
  2. CHUNK the body into 128-"token" windows and AGGREGATE (no front-128 loss).
     - Tokenization for chunking is whitespace split (text.split(" ")), exactly
       like main.py's batch_benchmark. Chunks shorter than --min_chunk_tokens
       (default 20) are low-confidence and excluded from scoring + aggregation.
     - Per-chunk NPR = mean(perturbed log-rank) / original log-rank, computed
       with the reused get_rank / perturb_texts / get_ranks.
     - A snippet's score is the aggregate over its scored chunks
       (--aggregate weighted_mean | mean | max; default weighted_mean).

Reused project code (NOT reimplemented):
  - main.perturb_texts, main.setup_args
  - baselines.rank.get_rank / get_ranks
  - baselines.utils.run_baseline.get_roc_metrics
  - baselines.utils.preprocessing.preprocess_and_save
  - baselines.utils.loadmodel.load_base_model_and_tokenizer

Per-chunk results are cached, so --load_cached_results lets you re-aggregate
(e.g. try a different --aggregate) and recompute AUROC in ~1 sec without rescoring.

Usage
-----
    python main_adapter.py --csv_path merged_4500.csv \
        --base_model_name bigcode/starcoder2-7b --output_name starcoder2_4500_body

    python main_adapter.py --csv_path merged_4500.csv --limit 5 --preview

    python main_adapter.py --csv_path merged_4500.csv \
        --load_cached_results ../logs/results_cache_main_adapter_<name>.pkl \
        --aggregate max
"""

import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import sys
import re
import ast
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
# ---------------------------------------------------------------------------
from main import perturb_texts, setup_args
from baselines.rank import get_rank, get_ranks
from baselines.utils.run_baseline import get_roc_metrics
from baselines.utils.preprocessing import preprocess_and_save
from baselines.utils.loadmodel import load_base_model_and_tokenizer


# idx format guaranteed by the dataset: "line<NUM>_human" / "line<NUM>_lm"
LINE_ID_PATTERN = re.compile(r"^line(\d+)_(human|lm)$")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_pairs(csv_path):
    """Read the merged CSV and return a list of (line_num, human_code, lm_code)."""
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


# ---------------------------------------------------------------------------
# Body extraction (strip prompt signature + docstring)
# ---------------------------------------------------------------------------
def strip_to_body(code):
    """Drop the first top-level def/class signature and its leading docstring.

    Returns (body_text, reason). body_text == "" means nothing scorable remains.
    Original indentation is preserved on purpose: the perturbation operates on
    whitespace, so we must not alter it here.
    """
    src = code if code.endswith("\n") else code + "\n"
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return code, "unparseable_fallback_whole"  # score as-is rather than lose it

    node = next(
        (n for n in tree.body
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))),
        None,
    )
    if node is None:
        return code, "no_def_fallback_whole"

    body = node.body
    # Drop a leading docstring expression if present.
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(getattr(body[0], "value", None), ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]

    if not body:
        return "", "empty_body"

    start_line = body[0].lineno  # 1-based line of the first real statement
    lines = src.splitlines()
    body_text = "\n".join(lines[start_line - 1:]).rstrip("\n")
    return body_text, "ok"


# ---------------------------------------------------------------------------
# Chunking (whitespace tokenization, exactly like main.py batch_benchmark)
# ---------------------------------------------------------------------------
def chunk_whitespace(text, chunk_len):
    """Split into 128-token windows by whitespace; return list of (chunk_text, n_tokens)."""
    toks = text.split(" ")
    out = []
    for start in range(0, len(toks), chunk_len):
        ct = toks[start:start + chunk_len]
        out.append((" ".join(ct), len(ct)))
    return out


# ---------------------------------------------------------------------------
# Scoring (reused get_rank / perturb_texts / get_ranks)
# ---------------------------------------------------------------------------
def score_chunk(chunk_text, args, model_config, k):
    """Per-chunk NPR = mean(perturbed log-rank) / original log-rank."""
    orig_logrank = get_rank(chunk_text, args, model_config, log=True)
    p_texts = perturb_texts([chunk_text for _ in range(k)], args, model_config)
    p_ranks = get_ranks(p_texts, args, model_config, log=True)
    valid = [r for r in p_ranks if not math.isnan(r)]
    mean_p = float(np.mean(valid)) if valid else float("nan")
    npr = mean_p / orig_logrank if orig_logrank else float("nan")
    return npr, orig_logrank, mean_p


def score_snippet(code, args, model_config, k, chunk_len, min_chunk_tokens, strip):
    """Strip to body, chunk, score each chunk. Returns (list_of_chunk_dicts, reason)."""
    if strip:
        body, reason = strip_to_body(code)
    else:
        body, reason = code, "no_strip"

    chunks = []
    if not body.strip():
        return chunks, reason  # empty body -> no scorable chunks

    for n_tok_chunk in chunk_whitespace(body, chunk_len):
        chunk_text, n_tok = n_tok_chunk
        if n_tok < min_chunk_tokens:
            chunks.append({"npr": float("nan"), "orig_logrank": float("nan"),
                           "mean_p_logrank": float("nan"), "n_tokens": n_tok,
                           "low_conf": True})
            continue
        npr, orig_lr, mean_p = score_chunk(chunk_text, args, model_config, k)
        chunks.append({"npr": npr, "orig_logrank": orig_lr,
                       "mean_p_logrank": mean_p, "n_tokens": n_tok,
                       "low_conf": False})
    return chunks, reason


# ---------------------------------------------------------------------------
# Aggregation (snippet-level score from per-chunk NPRs)
# ---------------------------------------------------------------------------
def aggregate_npr(chunks, method):
    """Aggregate scored chunks into one snippet NPR. NaN if no scorable chunk."""
    valid = [c for c in chunks if (not c["low_conf"]) and (not math.isnan(c["npr"]))]
    if not valid:
        return float("nan")
    if method == "mean":
        return float(np.mean([c["npr"] for c in valid]))
    if method == "max":
        return float(max(c["npr"] for c in valid))
    # weighted_mean (default): weight each chunk by its token count
    wsum = sum(c["npr"] * c["n_tokens"] for c in valid)
    tsum = sum(c["n_tokens"] for c in valid)
    return wsum / tsum if tsum else float("nan")


def n_scored(chunks):
    return sum(1 for c in chunks if (not c["low_conf"]) and (not math.isnan(c["npr"])))


def n_lowconf(chunks):
    return sum(1 for c in chunks if c["low_conf"])


# ---------------------------------------------------------------------------
# Args (reuse main.setup_args for a fully-populated namespace)
# ---------------------------------------------------------------------------
def build_full_args(cli):
    injected = [
        "--base_model_name",        cli.base_model_name,
        "--n_perturbation_list",    str(cli.n_perturbation),
        "--perturb_type",           "random-insert-space+newline",
        "--pct_words_masked",       str(cli.pct_words_masked),
        "--span_length",            str(cli.span_length),
        "--chunk_size",             str(cli.chunk_size),
        "--n_perturbation_rounds",  str(cli.n_perturbation_rounds),
        "--max_len",                str(cli.chunk_len),
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


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def report_and_save(results, csv_path, chunk_csv_path, aggregate_method):
    """Aggregate, print AUROC + stats + Youden's J, write per-pair and per-chunk CSVs."""
    real, samp = [], []  # HWC (label 0), MGC (label 1)
    for r in results:
        real.append(aggregate_npr(r["human_chunks"], aggregate_method))
        samp.append(aggregate_npr(r["lm_chunks"], aggregate_method))
    real = np.array(real, dtype=float)
    samp = np.array(samp, dtype=float)

    # NOTE: baselines.get_roc_metrics zips real_preds/sample_preds BY INDEX, so
    # the two lists must stay aligned and equal-length. Drop NaNs PAIRWISE:
    # if either side of a pair is NaN, exclude the whole pair.
    keep = (~np.isnan(real)) & (~np.isnan(samp))
    n_dropped = int((~keep).sum())
    n_human_only = int((np.isnan(samp) & ~np.isnan(real)).sum())  # MGC body too short
    n_lm_only = int((np.isnan(real) & ~np.isnan(samp)).sum())     # HWC body too short
    real_v = real[keep]
    samp_v = samp[keep]
    if n_dropped:
        logger.warning(
            f"Dropped {n_dropped} pair(s) before AUROC where a body had no scorable "
            f"chunk (MGC-empty: {n_human_only}, HWC-empty: {n_lm_only})"
        )

    if len(real_v) == 0:
        logger.error("No valid (human, lm) pairs remain; cannot compute AUROC.")
        return float("nan")

    _, _, roc_auc = get_roc_metrics(list(real_v), list(samp_v))

    print()
    print("=" * 72)
    print(f"DetectCodeGPT NPR  (body-only, {aggregate_method} over 128-tok chunks)")
    print(f"  HWC n={len(real_v)}, MGC n={len(samp_v)}")
    print("=" * 72)
    print(f"HWC (human): mean={real_v.mean():.4f}  std={real_v.std():.4f}  "
          f"median={np.median(real_v):.4f}  min={real_v.min():.4f}  max={real_v.max():.4f}")
    print(f"MGC (lm):    mean={samp_v.mean():.4f}  std={samp_v.std():.4f}  "
          f"median={np.median(samp_v):.4f}  min={samp_v.min():.4f}  max={samp_v.max():.4f}")
    print(f"Mean separation (MGC - HWC): {samp_v.mean() - real_v.mean():.4f}")

    print()
    for label, arr in [("HWC", real_v), ("MGC", samp_v)]:
        p = np.percentile(arr, [5, 25, 50, 75, 95])
        print(f"  {label} percentiles: 5%={p[0]:.4f}  25%={p[1]:.4f}  "
              f"50%={p[2]:.4f}  75%={p[3]:.4f}  95%={p[4]:.4f}")

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

    # ----- per-pair aggregate CSV -----
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    with open(csv_path, "w") as f:
        f.write("line_num,human_npr,lm_npr,winner,"
                "human_n_chunks_scored,lm_n_chunks_scored,"
                "human_n_lowconf,lm_n_lowconf\n")
        for r, hn, ln in zip(results, real, samp):
            winner = "MGC" if (ln > hn) else "HWC"
            f.write(f"{r['line_num']},{hn:.6f},{ln:.6f},{winner},"
                    f"{n_scored(r['human_chunks'])},{n_scored(r['lm_chunks'])},"
                    f"{n_lowconf(r['human_chunks'])},{n_lowconf(r['lm_chunks'])}\n")
    logger.info(f"Saved per-pair NPR scores to: {csv_path}")

    # ----- per-chunk detail CSV -----
    os.makedirs(os.path.dirname(chunk_csv_path) or ".", exist_ok=True)
    with open(chunk_csv_path, "w") as f:
        f.write("line_num,role,chunk_idx,n_tokens,low_conf,npr,orig_logrank,mean_p_logrank\n")
        for r in results:
            for role, chunks in (("human", r["human_chunks"]), ("lm", r["lm_chunks"])):
                for ci, c in enumerate(chunks):
                    f.write(f"{r['line_num']},{role},{ci},{c['n_tokens']},"
                            f"{int(c['low_conf'])},{c['npr']:.6f},"
                            f"{c['orig_logrank']:.6f},{c['mean_p_logrank']:.6f}\n")
    logger.info(f"Saved per-chunk detail to: {chunk_csv_path}")
    return roc_auc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Body-only, chunk-aggregated DetectCodeGPT NPR + AUROC from a "
                    "(human, lm) pairs CSV (random-insert-space+newline perturbation)."
    )
    parser.add_argument("--csv_path", required=True, help="Path to the merged pairs CSV")
    parser.add_argument("--base_model_name", type=str, default="bigcode/starcoder2-7b")
    parser.add_argument("--n_perturbation", type=int, default=50, help="Perturbed copies per chunk (k).")
    parser.add_argument("--pct_words_masked", type=float, default=0.5)
    parser.add_argument("--span_length", type=int, default=2)
    parser.add_argument("--chunk_size", type=int, default=10,
                        help="perturb_texts batch chunk (even; controls space/newline split).")
    parser.add_argument("--n_perturbation_rounds", type=int, default=1)
    # --- new: body extraction + chunk aggregation ---
    parser.add_argument("--strip_body", action=argparse.BooleanOptionalAction, default=True,
                        help="Strip prompt signature + docstring, score body only. "
                             "Use --no-strip_body to score the whole CSV code.")
    parser.add_argument("--chunk_len", type=int, default=128,
                        help="Whitespace-token window size per chunk. Default: 128")
    parser.add_argument("--min_chunk_tokens", type=int, default=20,
                        help="Chunks below this are low-confidence and not scored. Default: 20")
    parser.add_argument("--aggregate", choices=["weighted_mean", "mean", "max"],
                        default="weighted_mean",
                        help="How to aggregate per-chunk NPR into one snippet score.")
    # --- io / runtime ---
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--cache_dir", type=str, default="~/.cache/huggingface/hub")
    parser.add_argument("--output_name", type=str, default="main_adapter")
    parser.add_argument("--output_csv", type=str, default=None)
    parser.add_argument("--chunk_csv", type=str, default=None)
    parser.add_argument("--results_cache", type=str, default=None)
    parser.add_argument("--load_cached_results", type=str, default=None,
                        help="Skip scoring; load cached per-chunk results and re-aggregate.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--preview", action="store_true")
    cli = parser.parse_args()

    out_csv = os.path.expanduser(
        cli.output_csv or f"../logs/npr_scores_main_adapter_{cli.output_name}.csv")
    chunk_csv = os.path.expanduser(
        cli.chunk_csv or f"../logs/npr_chunks_main_adapter_{cli.output_name}.csv")

    # --- fast path: re-aggregate cached per-chunk results ---
    if cli.load_cached_results is not None:
        cache = os.path.expanduser(cli.load_cached_results)
        logger.info(f"Loading cached per-chunk results from {cache} -- skipping scoring")
        with open(cache, "rb") as f:
            results = pickle.load(f)
        logger.info(f"Loaded {len(results)} cached pair results; "
                    f"aggregate={cli.aggregate}")
        report_and_save(results, out_csv, chunk_csv, cli.aggregate)
        return

    # --- normal path ---
    csv_path = os.path.expanduser(cli.csv_path)
    pairs = load_pairs(csv_path)
    if cli.limit is not None:
        pairs = pairs[:cli.limit]
        logger.info(f"Limited to the first {len(pairs)} pairs")

    args = build_full_args(cli)
    logger.info(
        f"Config: scoring_model={cli.base_model_name}, strip_body={cli.strip_body}, "
        f"chunk_len={cli.chunk_len}, min_chunk_tokens={cli.min_chunk_tokens}, "
        f"aggregate={cli.aggregate}, k={cli.n_perturbation}, "
        f"perturb_type={args.perturb_type}, chunk_size(perturb)={args.chunk_size}"
    )

    cache_dir, _, _ = preprocess_and_save(args)
    model_config = {"cache_dir": cache_dir}
    logger.info("Loading base scoring model...")
    model_config = load_base_model_and_tokenizer(args, model_config)

    reasons = {}
    results = []
    for line_num, human_code, lm_code in tqdm(pairs, desc="Scoring pairs"):
        h_chunks, h_reason = score_snippet(human_code, args, model_config,
                                           cli.n_perturbation, cli.chunk_len,
                                           cli.min_chunk_tokens, cli.strip_body)
        l_chunks, l_reason = score_snippet(lm_code, args, model_config,
                                           cli.n_perturbation, cli.chunk_len,
                                           cli.min_chunk_tokens, cli.strip_body)
        reasons[h_reason] = reasons.get(h_reason, 0) + 1
        reasons[l_reason] = reasons.get(l_reason, 0) + 1
        results.append({
            "line_num": line_num,
            "human_chunks": h_chunks,
            "lm_chunks": l_chunks,
        })
        if cli.preview:
            hn = aggregate_npr(h_chunks, cli.aggregate)
            ln = aggregate_npr(l_chunks, cli.aggregate)
            winner = "MGC" if ln > hn else "HWC"
            print(f"  line{line_num}: HWC={hn:.4f}({n_scored(h_chunks)}ch)  "
                  f"MGC={ln:.4f}({n_scored(l_chunks)}ch)  -> {winner}")
        if len(results) % 200 == 0:
            torch.cuda.empty_cache()

    torch.cuda.empty_cache()
    logger.info(f"Body-extraction outcomes (per snippet): {reasons}")

    cache_path = os.path.expanduser(
        cli.results_cache or f"../logs/results_cache_main_adapter_{cli.output_name}.pkl")
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(results, f)
    logger.info(f"Cached per-chunk results to {cache_path}")
    logger.info(f"To re-aggregate without rescoring: --load_cached_results {cache_path}")

    report_and_save(results, out_csv, chunk_csv, cli.aggregate)


if __name__ == "__main__":
    main()