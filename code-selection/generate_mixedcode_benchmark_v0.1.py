#!/usr/bin/env python3
"""
generate_mixedcode_benchmark.py

Build length-controlled mixed-code localization benchmarks from the new merged CSV
format:

    idx,code,label
    line1_human,"def ...",human
    line1_lm,"def ...",lm
    line10_human,"def ...",human
    line10_lm,"def ...",lm

For each matched HWC/AGC pair:
  - extract prompt = function signature + leading docstring/comment block
  - extract HWC body from the human row
  - extract AGC body from the lm row
  - validate non-empty and syntactically valid bodies
  - select samples whose HWC/AGC body lengths match target token sizes
  - construct mixed_code = prompt + HWC body + AGC body
  - write char/token ground-truth regions for localization evaluation

Default targets:
  100,110,120,130,140,150,160,170,180,190,200

Note: this is 11 target sizes. If you want exactly 10 benchmark types, pass
      --targets 100,110,120,130,140,150,160,170,180,200
   or --targets 100,110,120,130,140,150,160,170,180,190

Tokenization:
  split_space_v1 = text.split(" ")
This matches the whitespace chunking convention used by the current
main_adapter.py / DetectCodeGPT adaptation.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


LINE_ID_PATTERN = re.compile(r"^line(\d+)_(human|lm)$")

TOKENIZATION_SCHEME = "split_space_v1"
TOKENIZATION_DESCRIPTION = (
    "tokens = text.split(' '). Empty tokens from repeated spaces are preserved; "
    "newlines remain inside tokens. This matches the project whitespace-token "
    "chunking convention."
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PairRecord:
    line_num: int
    human_idx: str
    lm_idx: str
    human_code: str
    lm_code: str


@dataclass(frozen=True)
class SplitCode:
    prompt: str
    body: str
    reason: str


@dataclass(frozen=True)
class Candidate:
    pair: PairRecord
    human_split: SplitCode
    lm_split: SplitCode
    hwc_tokens: int
    agc_tokens: int


# ---------------------------------------------------------------------------
# Tokenization and region helpers
# ---------------------------------------------------------------------------

def count_split_space_tokens(text: str) -> int:
    """Token count under split_space_v1."""
    return len(text.split(" "))


def token_starts_split_space(text: str) -> List[int]:
    """Return start character offset for each token under text.split(' ')."""
    tokens = text.split(" ")
    starts: List[int] = []
    cursor = 0
    for token in tokens:
        starts.append(cursor)
        cursor += len(token) + 1
    return starts


def ensure_trailing_newline(text: str) -> str:
    if not text:
        return text
    return text if text.endswith("\n") else text + "\n"


def compute_char_regions(parts: List[Tuple[str, str, str]]) -> List[Dict[str, Any]]:
    """
    parts: list of (label, role, text)
    Returns regions that tile mixed_code in character offsets.
    """
    regions: List[Dict[str, Any]] = []
    cursor = 0
    for label, role, text in parts:
        start = cursor
        end = start + len(text)
        regions.append({
            "label": label,
            "role": role,
            "start_char": start,
            "end_char": end,
            "n_chars": end - start,
        })
        cursor = end
    return regions


def compute_token_regions(mixed_code: str, char_regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Tokenize mixed_code once using split_space_v1, then assign each token to the
    region containing its start character.

    This follows the earlier benchmark-generator idea: token spans partition
    the same token stream that the detector sees.
    """
    starts = token_starts_split_space(mixed_code)
    counts = [0 for _ in char_regions]

    for tok_start in starts:
        assigned = False
        for i, region in enumerate(char_regions):
            if region["start_char"] <= tok_start < region["end_char"]:
                counts[i] += 1
                assigned = True
                break
        if not assigned:
            # Trailing empty token after final whitespace belongs to the last region.
            counts[-1] += 1

    token_regions: List[Dict[str, Any]] = []
    cursor = 0
    for region, n_tokens in zip(char_regions, counts):
        start = cursor
        end = start + n_tokens
        token_regions.append({
            "label": region["label"],
            "role": region["role"],
            "start_token": start,
            "end_token": end,
            "n_tokens": n_tokens,
        })
        cursor = end

    return token_regions


def merge_regions(
    char_regions: List[Dict[str, Any]],
    token_regions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for c, t in zip(char_regions, token_regions):
        if c["label"] != t["label"]:
            raise ValueError(f"Region mismatch: char={c['label']} token={t['label']}")
        merged.append({
            "label": c["label"],
            "role": c["role"],
            "start_char": c["start_char"],
            "end_char": c["end_char"],
            "n_chars": c["n_chars"],
            "start_token": t["start_token"],
            "end_token": t["end_token"],
            "n_tokens": t["n_tokens"],
        })
    return merged


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def load_pairs_from_csv(csv_path: Path) -> List[PairRecord]:
    """
    Load merged CSV and return matched human/lm pairs sorted by line number.

    Expected rows:
      lineX_human, code, human
      lineX_lm,    code, lm
    """
    by_line: Dict[int, Dict[str, Dict[str, str]]] = {}

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"idx", "code", "label"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(
                f"CSV must contain columns {sorted(required)}; got {reader.fieldnames}"
            )

        for row_no, row in enumerate(reader, start=2):
            idx = str(row["idx"])
            label = str(row["label"])
            code = row["code"]

            m = LINE_ID_PATTERN.match(idx)
            if not m:
                raise ValueError(f"Unexpected idx format at CSV row {row_no}: {idx!r}")

            line_s, role = m.groups()
            line_num = int(line_s)

            expected_label = "human" if role == "human" else "lm"
            if label != expected_label:
                raise ValueError(
                    f"Label mismatch at row {row_no}: idx={idx!r}, "
                    f"label={label!r}, expected={expected_label!r}"
                )

            by_line.setdefault(line_num, {})[role] = {
                "idx": idx,
                "code": code,
                "label": label,
            }

    pairs: List[PairRecord] = []
    for line_num in sorted(by_line):
        roles = by_line[line_num]
        if "human" not in roles or "lm" not in roles:
            raise ValueError(f"Missing human/lm pair for line{line_num}")

        pairs.append(PairRecord(
            line_num=line_num,
            human_idx=roles["human"]["idx"],
            lm_idx=roles["lm"]["idx"],
            human_code=roles["human"]["code"],
            lm_code=roles["lm"]["code"],
        ))

    return pairs


# ---------------------------------------------------------------------------
# Prompt/body extraction
# ---------------------------------------------------------------------------

def first_top_level_def_or_class(tree: ast.AST) -> Optional[ast.AST]:
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return node
    return None


def split_prompt_and_body(code: str) -> SplitCode:
    """
    Split full code into:
      prompt = first def/class header + leading docstring, if any
      body   = remaining body statements

    This mirrors the body-only logic used for NPR scoring, but returns both
    prompt and body so we can construct mixed code with ground-truth spans.
    """
    src = code if code.endswith("\n") else code + "\n"
    lines = src.splitlines(keepends=True)

    try:
        tree = ast.parse(src)
    except SyntaxError:
        return SplitCode(prompt="", body=code, reason="unparseable")

    node = first_top_level_def_or_class(tree)
    if node is None:
        return SplitCode(prompt="", body=code, reason="no_def_or_class")

    body_nodes = list(getattr(node, "body", []))
    if not body_nodes:
        return SplitCode(prompt=src, body="", reason="empty_ast_body")

    # Remove leading docstring from scorable body, but keep it in prompt.
    real_body_nodes = body_nodes
    if (
        body_nodes
        and isinstance(body_nodes[0], ast.Expr)
        and isinstance(getattr(body_nodes[0], "value", None), ast.Constant)
        and isinstance(body_nodes[0].value.value, str)
    ):
        real_body_nodes = body_nodes[1:]

    if not real_body_nodes:
        return SplitCode(prompt=src, body="", reason="docstring_only_body")

    body_start_line = real_body_nodes[0].lineno  # 1-based
    prompt = "".join(lines[:body_start_line - 1])
    body = "".join(lines[body_start_line - 1:]).rstrip("\n")

    if not prompt.strip():
        return SplitCode(prompt="", body=body, reason="empty_prompt")
    if not body.strip():
        return SplitCode(prompt=prompt, body="", reason="empty_body")

    return SplitCode(prompt=prompt, body=body, reason="ok")


def parses_ok(code: str) -> bool:
    try:
        ast.parse(code if code.endswith("\n") else code + "\n")
        return True
    except SyntaxError:
        return False


# ---------------------------------------------------------------------------
# Candidate filtering
# ---------------------------------------------------------------------------

def in_centered_window(n_tokens: int, target: int, tolerance: int) -> bool:
    return (target - tolerance) <= n_tokens <= (target + tolerance)


def in_bucket_window(n_tokens: int, target: int, bucket_width: int) -> bool:
    return target <= n_tokens < (target + bucket_width)


def candidate_for_pair(
    pair: PairRecord,
    require_same_prompt: bool = False,
) -> Tuple[Optional[Candidate], str]:
    """
    Extract and validate a candidate. This checks syntax/non-empty only.
    Length filtering happens later per benchmark type.
    """
    h = split_prompt_and_body(pair.human_code)
    m = split_prompt_and_body(pair.lm_code)

    if h.reason != "ok":
        return None, f"human_split_{h.reason}"
    if m.reason != "ok":
        return None, f"lm_split_{m.reason}"

    if not h.body.strip():
        return None, "human_empty_body"
    if not m.body.strip():
        return None, "lm_empty_body"

    # Optional prompt equality check. We keep this off by default because small
    # formatting differences in docstrings should not necessarily invalidate a pair.
    if require_same_prompt and h.prompt.strip() != m.prompt.strip():
        return None, "prompt_mismatch"

    # Use the human prompt as the shared context for mixed code construction.
    if not parses_ok(h.prompt + ensure_trailing_newline(h.body)):
        return None, "human_full_parse_fail"

    if not parses_ok(h.prompt + ensure_trailing_newline(m.body)):
        return None, "lm_body_with_human_prompt_parse_fail"

    hwc_tokens = count_split_space_tokens(h.body)
    agc_tokens = count_split_space_tokens(m.body)

    return Candidate(
        pair=pair,
        human_split=h,
        lm_split=m,
        hwc_tokens=hwc_tokens,
        agc_tokens=agc_tokens,
    ), "ok"


def candidate_matches_target(
    c: Candidate,
    target: int,
    tolerance: int,
    selection_mode: str,
    bucket_width: int,
) -> bool:
    if selection_mode == "centered":
        return (
            in_centered_window(c.hwc_tokens, target, tolerance)
            and in_centered_window(c.agc_tokens, target, tolerance)
        )
    if selection_mode == "bucket":
        return (
            in_bucket_window(c.hwc_tokens, target, bucket_width)
            and in_bucket_window(c.agc_tokens, target, bucket_width)
        )
    raise ValueError(f"Unknown selection_mode: {selection_mode}")


# ---------------------------------------------------------------------------
# Mixed-code construction
# ---------------------------------------------------------------------------

def build_mixed_record(
    c: Candidate,
    benchmark_type: str,
    target: int,
    tolerance: int,
    selection_mode: str,
    bucket_width: int,
    benchmark_id: int,
    mix_strategy: str = "prompt_hwc_agc_concat",
) -> Dict[str, Any]:
    """
    Build one mixed-code record.

    Level-1 style:
      mixed_code = prompt + HWC body + AGC body

    AGC is the target region.
    """
    prompt_part = ensure_trailing_newline(c.human_split.prompt)
    hwc_part = ensure_trailing_newline(c.human_split.body)
    agc_part = ensure_trailing_newline(c.lm_split.body)

    parts = [
        ("prompt", "context", prompt_part),
        ("HWC", "non_target", hwc_part),
        ("AGC", "target", agc_part),
    ]

    mixed_code = "".join(part for _, _, part in parts)

    if not parses_ok(mixed_code):
        raise ValueError(f"Mixed code parse failed for line{c.pair.line_num}")

    char_regions = compute_char_regions(parts)
    token_regions = compute_token_regions(mixed_code, char_regions)
    regions = merge_regions(char_regions, token_regions)

    target_regions = [r for r in regions if r["label"] == "AGC"]
    if len(target_regions) != 1:
        raise ValueError("Expected exactly one AGC target region")

    region_by_label = {r["label"]: r for r in regions}

    return {
        "benchmark_id": benchmark_id,
        "benchmark_type": benchmark_type,
        "source_line_num": c.pair.line_num,
        "human_idx": c.pair.human_idx,
        "lm_idx": c.pair.lm_idx,
        "mix_strategy": mix_strategy,
        "tokenization": TOKENIZATION_SCHEME,
        "target_tokens": target,
        "selection_mode": selection_mode,
        "tolerance": tolerance,
        "bucket_width": bucket_width,
        "hwc_body_tokens": c.hwc_tokens,
        "agc_body_tokens": c.agc_tokens,
        "n_tokens_total": count_split_space_tokens(mixed_code),
        "n_chars_total": len(mixed_code),

        # Code fields
        "mixed_code": mixed_code,
        "prompt": prompt_part,
        "hwc_body": hwc_part,
        "agc_body": agc_part,

        # JSON region fields for robust downstream use
        "regions_json": json.dumps(regions, ensure_ascii=False),
        "target_regions_json": json.dumps(target_regions, ensure_ascii=False),

        # Flattened span fields for easy CSV analysis
        "prompt_start_char": region_by_label["prompt"]["start_char"],
        "prompt_end_char": region_by_label["prompt"]["end_char"],
        "prompt_start_token": region_by_label["prompt"]["start_token"],
        "prompt_end_token": region_by_label["prompt"]["end_token"],

        "hwc_start_char": region_by_label["HWC"]["start_char"],
        "hwc_end_char": region_by_label["HWC"]["end_char"],
        "hwc_start_token": region_by_label["HWC"]["start_token"],
        "hwc_end_token": region_by_label["HWC"]["end_token"],

        "agc_start_char": region_by_label["AGC"]["start_char"],
        "agc_end_char": region_by_label["AGC"]["end_char"],
        "agc_start_token": region_by_label["AGC"]["start_token"],
        "agc_end_token": region_by_label["AGC"]["end_token"],
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

FIELDNAMES = [
    "benchmark_id",
    "benchmark_type",
    "source_line_num",
    "human_idx",
    "lm_idx",
    "mix_strategy",
    "tokenization",
    "target_tokens",
    "selection_mode",
    "tolerance",
    "bucket_width",
    "hwc_body_tokens",
    "agc_body_tokens",
    "n_tokens_total",
    "n_chars_total",
    "mixed_code",
    "prompt",
    "hwc_body",
    "agc_body",
    "regions_json",
    "target_regions_json",
    "prompt_start_char",
    "prompt_end_char",
    "prompt_start_token",
    "prompt_end_token",
    "hwc_start_char",
    "hwc_end_char",
    "hwc_start_token",
    "hwc_end_token",
    "agc_start_char",
    "agc_end_char",
    "agc_start_token",
    "agc_end_token",
]


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=FIELDNAMES,
            quoting=csv.QUOTE_ALL,
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_manifest(path: Path, manifest_rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "benchmark_type",
        "target_tokens",
        "selection_mode",
        "tolerance",
        "bucket_width",
        "n_records",
        "out_csv",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in manifest_rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_targets(s: str) -> List[int]:
    targets = [int(x.strip()) for x in s.split(",") if x.strip()]
    if not targets:
        raise argparse.ArgumentTypeError("At least one target must be provided.")
    if any(t <= 0 for t in targets):
        raise argparse.ArgumentTypeError("Targets must be positive integers.")
    return targets


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate length-controlled mixed-code localization benchmarks from merged HWC/AGC CSV."
    )
    parser.add_argument(
        "--input_csv",
        required=True,
        help="Merged CSV with idx,code,label rows: lineX_human and lineX_lm.",
    )
    parser.add_argument(
        "--out_dir",
        required=True,
        help="Output directory for generated mixed-code benchmark CSV files.",
    )
    parser.add_argument(
        "--targets",
        type=parse_targets,
        default=parse_targets("100,110,120,130,140,150,160,170,180,190,200"),
        help=(
            "Comma-separated target body token sizes. Default is "
            "100,110,...,200, which yields 11 benchmark types."
        ),
    )
    parser.add_argument(
        "--selection_mode",
        choices=["centered", "bucket"],
        default="centered",
        help=(
            "centered: accept target +/- tolerance. "
            "bucket: accept [target, target+bucket_width)."
        ),
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=5,
        help="Centered-window tolerance. Used only when --selection_mode centered.",
    )
    parser.add_argument(
        "--bucket_width",
        type=int,
        default=10,
        help="Bucket width. Used only when --selection_mode bucket.",
    )
    parser.add_argument(
        "--max_per_type",
        type=int,
        default=0,
        help="Maximum records per benchmark type. 0 means no limit.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed used when shuffling candidates.",
    )
    parser.add_argument(
        "--no_shuffle",
        action="store_true",
        help="Do not shuffle candidates before selecting samples.",
    )
    parser.add_argument(
        "--unique_pairs",
        action="store_true",
        help="Do not reuse the same source line across benchmark types.",
    )
    parser.add_argument(
        "--require_same_prompt",
        action="store_true",
        help="Require extracted human and lm prompts to match after stripping whitespace.",
    )
    parser.add_argument(
        "--write_combined",
        action="store_true",
        help="Also write one combined CSV containing all benchmark types.",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv).expanduser()
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    if args.selection_mode == "centered" and args.tolerance < 0:
        raise ValueError("--tolerance must be >= 0")
    if args.selection_mode == "bucket" and args.bucket_width <= 0:
        raise ValueError("--bucket_width must be > 0")

    print("=" * 80)
    print("generate_mixedcode_benchmark.py")
    print("=" * 80)
    print(f"input_csv        : {input_csv}")
    print(f"out_dir          : {out_dir}")
    print(f"targets          : {args.targets}")
    print(f"selection_mode   : {args.selection_mode}")
    print(f"tolerance        : {args.tolerance}")
    print(f"bucket_width     : {args.bucket_width}")
    print(f"max_per_type     : {args.max_per_type}")
    print(f"unique_pairs     : {args.unique_pairs}")
    print(f"tokenization     : {TOKENIZATION_SCHEME}")
    print("=" * 80)

    pairs = load_pairs_from_csv(input_csv)
    print(f"Loaded pairs     : {len(pairs)}")

    candidates: List[Candidate] = []
    skip_counts: Dict[str, int] = {}

    for pair in pairs:
        c, reason = candidate_for_pair(pair, require_same_prompt=args.require_same_prompt)
        if c is None:
            skip_counts[reason] = skip_counts.get(reason, 0) + 1
            continue
        candidates.append(c)

    print(f"Valid candidates : {len(candidates)}")
    if skip_counts:
        print("Skipped candidates:")
        for reason, count in sorted(skip_counts.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {reason:40s} {count}")

    if not args.no_shuffle:
        rng = random.Random(args.seed)
        rng.shuffle(candidates)

    used_lines = set()
    all_rows: List[Dict[str, Any]] = []
    manifest_rows: List[Dict[str, Any]] = []

    for type_idx, target in enumerate(args.targets, start=1):
        benchmark_type = f"type{type_idx:02d}"
        rows: List[Dict[str, Any]] = []

        for c in candidates:
            if args.unique_pairs and c.pair.line_num in used_lines:
                continue

            if not candidate_matches_target(
                c,
                target=target,
                tolerance=args.tolerance,
                selection_mode=args.selection_mode,
                bucket_width=args.bucket_width,
            ):
                continue

            try:
                row = build_mixed_record(
                    c,
                    benchmark_type=benchmark_type,
                    target=target,
                    tolerance=args.tolerance,
                    selection_mode=args.selection_mode,
                    bucket_width=args.bucket_width,
                    benchmark_id=len(rows),
                )
            except ValueError:
                # Extremely rare: both individual bodies parse, but concatenated mixed code fails.
                continue

            rows.append(row)
            if args.unique_pairs:
                used_lines.add(c.pair.line_num)

            if args.max_per_type > 0 and len(rows) >= args.max_per_type:
                break

        out_csv = out_dir / f"{benchmark_type}_agc{target}_hwc{target}.csv"
        write_csv(out_csv, rows)
        all_rows.extend(rows)

        manifest_rows.append({
            "benchmark_type": benchmark_type,
            "target_tokens": target,
            "selection_mode": args.selection_mode,
            "tolerance": args.tolerance,
            "bucket_width": args.bucket_width,
            "n_records": len(rows),
            "out_csv": str(out_csv),
        })

        print(
            f"{benchmark_type}: target={target:3d}, "
            f"records={len(rows):5d}, out={out_csv}"
        )

    manifest_path = out_dir / "manifest.csv"
    write_manifest(manifest_path, manifest_rows)
    print(f"Manifest         : {manifest_path}")

    if args.write_combined:
        combined_path = out_dir / "mixedcode_all_types.csv"
        write_csv(combined_path, all_rows)
        print(f"Combined CSV     : {combined_path}")
        print(f"Combined records : {len(all_rows)}")

    print("=" * 80)
    print("Done")
    print("=" * 80)


if __name__ == "__main__":
    main()