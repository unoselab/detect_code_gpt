#!/usr/bin/env python3
"""main_v2.py

Step 1 of a CSV-driven evaluation pipeline (NPR / AUROC come later).

What it does
------------
1. Takes the merged pairs CSV as a command-line argument.
2. Builds (human, lm) pairs following the dataset contract:
   adjacent rows, first is `lineX_human`, second is `lineX_lm`.
3. Produces k perturbed copies of each snippet using DetectCodeGPT's
   'random-insert-space+newline' strategy -- the same strategy used in
   our project and in the paper
   (2025 ICSE "Between Lines of Code: Unraveling the Distinct Patterns
    of Machine and Human Programmers").

Design note: it does NOT reimplement perturbation. It reuses
`perturb_texts` from the existing `main.py`. For perturb_type
'random-insert-space+newline', `perturb_texts_()` returns before any
mask-filling-model call, so no GPU / scoring model is required here and
`model_config={}` is sufficient.

Usage
-----
    python main_v2.py codesearchnet_starcoder2-7b_python_merged_4500.csv
    python main_v2.py data.csv --n_perturbation 50 --limit 5 --preview
"""

import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import re
import argparse
from argparse import Namespace

import pandas as pd
from loguru import logger

# Reuse the project's perturbation pipeline instead of writing our own.
# Importing main.py also runs its module-level setup (e.g. CUDA_VISIBLE_DEVICES),
# which is harmless for the perturbation-only path used here.
from main import perturb_texts


# idx format guaranteed by the dataset: "line<NUM>_human" / "line<NUM>_lm"
LINE_ID_PATTERN = re.compile(r"^line(\d+)_(human|lm)$")


def load_pairs(csv_path):
    """Read the merged CSV and return a list of (line_num, human_code, lm_code).

    Uses a real CSV parser (the `code` field is multi-line, so manual
    line-splitting would corrupt rows). Enforces the dataset contract:
    even row count, every two adjacent rows form one pair, first is *_human,
    second is *_lm, and both share the same lineX.
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


def build_perturb_args(n_perturbation_rounds, pct_words_masked, span_length, chunk_size):
    """Minimal args Namespace required by main.perturb_texts for this perturb_type.

    Only the fields actually read on the 'random-insert-space+newline' path are
    populated. `span_length` doubles as the Poisson mean for inserted spaces.
    `mask_filling_model_name` is only checked for the substring '11b'.
    """
    return Namespace(
        perturb_type="random-insert-space+newline",
        pct_words_masked=pct_words_masked,
        span_length=span_length,
        chunk_size=chunk_size,
        n_perturbation_rounds=n_perturbation_rounds,
        mask_filling_model_name="Salesforce/codet5p-770m",
    )


def perturb_snippet(code, args, k):
    """Return k perturbed copies of a single snippet via the reused pipeline.

    Perturbing the k identical copies together keeps the space/newline split
    balanced per snippet (each chunk is split 50/50 inside perturb_texts_).
    """
    copies = [code for _ in range(k)]
    return perturb_texts(copies, args, model_config={})


def main():
    parser = argparse.ArgumentParser(
        description="Perturb (human, lm) code pairs from a CSV using "
                    "DetectCodeGPT's random-insert-space+newline strategy."
    )
    parser.add_argument("--csv_path", help="Path to the merged pairs CSV")
    parser.add_argument("--n_perturbation", type=int, default=50,
                        help="Number of perturbed copies per snippet (k). Default: 50")
    parser.add_argument("--pct_words_masked", type=float, default=0.5,
                        help="Insertion probability per token/line. Default: 0.5")
    parser.add_argument("--span_length", type=int, default=2,
                        help="Poisson mean for inserted spaces. Default: 2")
    parser.add_argument("--chunk_size", type=int, default=10,
                        help="Batch chunk size used inside perturb_texts. Default: 10")
    parser.add_argument("--n_perturbation_rounds", type=int, default=1,
                        help="How many perturbation rounds to apply. Default: 1")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only the first N pairs (debugging).")
    parser.add_argument("--preview", action="store_true",
                        help="Print original vs first perturbed copy for each pair.")
    cli = parser.parse_args()

    csv_path = os.path.expanduser(cli.csv_path)
    pairs = load_pairs(csv_path)
    if cli.limit is not None:
        pairs = pairs[:cli.limit]
        logger.info(f"Limited to the first {len(pairs)} pairs")

    args = build_perturb_args(
        n_perturbation_rounds=cli.n_perturbation_rounds,
        pct_words_masked=cli.pct_words_masked,
        span_length=cli.span_length,
        chunk_size=cli.chunk_size,
    )
    logger.info(
        f"Perturbation config: type={args.perturb_type}, k={cli.n_perturbation}, "
        f"pct_words_masked={args.pct_words_masked}, span/mean={args.span_length}, "
        f"chunk_size={args.chunk_size}, rounds={args.n_perturbation_rounds}"
    )

    # For each pair, perturb the human (HWC, label=0) and lm (MGC, label=1) code.
    # The lists below are the hook the later NPR / AUROC step will consume.
    for line_num, human_code, lm_code in pairs:
        perturbed_human = perturb_snippet(human_code, args, cli.n_perturbation)
        perturbed_lm = perturb_snippet(lm_code, args, cli.n_perturbation)

        if cli.preview:
            print("=" * 72)
            print(f"line{line_num}  "
                  f"(human: {len(perturbed_human)} perturbed, "
                  f"lm: {len(perturbed_lm)} perturbed)")
            print("-" * 72)
            print("[HUMAN] original:")
            print(human_code)
            print("\n[HUMAN] perturbed copy #1:")
            print(perturbed_human[0])

            print("[LM] original:")
            print(lm_code)
            print("\n[LM] perturbed copy #1:")
            print(perturbed_lm[0])
            print()

    logger.info("Done. (NPR / AUROC computation will consume these perturbations "
                "in the next step.)")


if __name__ == "__main__":
    main()