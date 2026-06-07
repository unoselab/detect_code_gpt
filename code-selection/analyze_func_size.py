#!/usr/bin/env python3
"""
Analyze HWC/AGC function-size distribution in merged CSV files.

Input CSV format:
    idx,code,label
    line1_human,"def ...",human
    line1_lm,"def ...",lm

Outputs:
  1. func_size_rows.csv
     Per-row function size information.

  2. func_size_pairs.csv
     Per-pair HWC/AGC body sizes.

  3. func_size_bucket_counts.csv
     Counts per target benchmark bucket.

  4. func_size_summary.txt
     Human-readable summary.

Default benchmark buckets:
  type01_110: 100 < = tokens <= 110
  type02_120: 110 < tokens <= 120
  ...
  type10_200: 190 < tokens <= 200

For type01, lower bound is inclusive:
  100 <= tokens <= 110

Tokenization:
  split_space_v1 = text.split(" ")
"""

from __future__ import annotations

import argparse
import ast
import csv
import math
import re
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any, Dict, List, Optional, Tuple


LINE_ID_RE = re.compile(r"^line(\d+)_(human|lm)$")


# ---------------------------------------------------------------------
# Token / AST helpers
# ---------------------------------------------------------------------

def count_split_space_tokens(text: str) -> int:
    if text is None:
        return 0
    if text == "":
        return 0
    return len(text.split(" "))


def count_regex_tokens(text: str) -> int:
    if not text:
        return 0
    return len(re.findall(r"\S+", text))


def count_lines(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines())


def first_top_level_def_or_class(tree: ast.AST) -> Optional[ast.AST]:
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return node
    return None


def split_prompt_and_body(code: str) -> Tuple[str, str, str]:
    """
    Return (prompt, body, reason).

    prompt = signature + leading docstring/comment area before the first real body stmt
    body   = remaining implementation body

    This is analysis-oriented and mirrors our body-only scoring convention.
    """
    src = code if code.endswith("\n") else code + "\n"
    lines = src.splitlines(keepends=True)

    try:
        tree = ast.parse(src)
    except SyntaxError:
        return "", code, "parse_fail"

    node = first_top_level_def_or_class(tree)
    if node is None:
        return "", code, "no_def_or_class"

    body_nodes = list(getattr(node, "body", []))
    if not body_nodes:
        return src, "", "empty_ast_body"

    real_body_nodes = body_nodes

    # Remove leading docstring from body, but keep it in prompt.
    if (
        body_nodes
        and isinstance(body_nodes[0], ast.Expr)
        and isinstance(getattr(body_nodes[0], "value", None), ast.Constant)
        and isinstance(body_nodes[0].value.value, str)
    ):
        real_body_nodes = body_nodes[1:]

    if not real_body_nodes:
        return src, "", "docstring_only_body"

    body_start_line = real_body_nodes[0].lineno  # 1-based
    prompt = "".join(lines[: body_start_line - 1])
    body = "".join(lines[body_start_line - 1:])

    if not body.strip():
        return prompt, body, "empty_body"

    return prompt, body, "ok"


def parse_idx(idx: str) -> Tuple[int, str]:
    m = LINE_ID_RE.match(idx)
    if not m:
        raise ValueError(f"Unexpected idx format: {idx!r}")
    line_num = int(m.group(1))
    role = m.group(2)
    return line_num, role


# ---------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------

def percentile(values: List[float], p: float) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - k) + xs[hi] * (k - lo)


def summarize(values: List[int]) -> Dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "mean": "",
            "std": "",
            "min": "",
            "p05": "",
            "p25": "",
            "median": "",
            "p75": "",
            "p95": "",
            "max": "",
        }

    out = {
        "n": len(values),
        "mean": f"{mean(values):.2f}",
        "std": f"{stdev(values):.2f}" if len(values) > 1 else "0.00",
        "min": min(values),
        "p05": f"{percentile(values, 0.05):.1f}",
        "p25": f"{percentile(values, 0.25):.1f}",
        "median": f"{median(values):.1f}",
        "p75": f"{percentile(values, 0.75):.1f}",
        "p95": f"{percentile(values, 0.95):.1f}",
        "max": max(values),
    }
    return out


def bucket_for_tokens(n: int, targets: List[int]) -> Optional[str]:
    """
    Default:
      type01_110: 100 <= n <= 110
      type02_120: 110 < n <= 120
      ...
    """
    prev = targets[0] - 10
    for i, upper in enumerate(targets, start=1):
        lower = upper - 10
        if i == 1:
            if lower <= n <= upper:
                return f"type{i:02d}_{upper}"
        else:
            if lower < n <= upper:
                return f"type{i:02d}_{upper}"
        prev = upper
    return None


def bucket_range_label(type_idx: int, upper: int) -> str:
    lower = upper - 10
    if type_idx == 1:
        return f"{lower}-{upper}"
    return f"{lower + 1}-{upper}"


# ---------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------

def read_rows(input_csv: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    with input_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"idx", "code", "label"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV must contain {sorted(required)}; got {reader.fieldnames}")

        for csv_row_no, row in enumerate(reader, start=2):
            idx = row["idx"]
            code = row["code"]
            label = row["label"]

            line_num, role = parse_idx(idx)
            expected_label = "human" if role == "human" else "lm"
            if label != expected_label:
                raise ValueError(
                    f"Label mismatch at CSV row {csv_row_no}: "
                    f"idx={idx!r}, label={label!r}, expected={expected_label!r}"
                )

            prompt, body, reason = split_prompt_and_body(code)

            rows.append({
                "csv_row_no": csv_row_no,
                "idx": idx,
                "line_num": line_num,
                "role": role,
                "label": label,
                "parse_reason": reason,
                "full_tokens_split_space": count_split_space_tokens(code),
                "full_tokens_regex": count_regex_tokens(code),
                "body_tokens_split_space": count_split_space_tokens(body),
                "body_tokens_regex": count_regex_tokens(body),
                "prompt_tokens_split_space": count_split_space_tokens(prompt),
                "full_chars": len(code),
                "body_chars": len(body),
                "prompt_chars": len(prompt),
                "full_lines": count_lines(code),
                "body_lines": count_lines(body),
                "prompt_lines": count_lines(prompt),
            })

    return rows


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_pair_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_line: Dict[int, Dict[str, Dict[str, Any]]] = {}

    for r in rows:
        by_line.setdefault(r["line_num"], {})[r["role"]] = r

    pair_rows: List[Dict[str, Any]] = []
    for line_num in sorted(by_line):
        item = by_line[line_num]
        h = item.get("human")
        m = item.get("lm")
        if h is None or m is None:
            continue

        htok = int(h["body_tokens_split_space"])
        mtok = int(m["body_tokens_split_space"])

        pair_rows.append({
            "line_num": line_num,
            "human_idx": h["idx"],
            "lm_idx": m["idx"],
            "human_parse_reason": h["parse_reason"],
            "lm_parse_reason": m["parse_reason"],
            "hwc_body_tokens": htok,
            "agc_body_tokens": mtok,
            "min_body_tokens": min(htok, mtok),
            "max_body_tokens": max(htok, mtok),
            "abs_diff_body_tokens": abs(htok - mtok),
            "both_parse_ok": int(h["parse_reason"] == "ok" and m["parse_reason"] == "ok"),
        })

    return pair_rows


def build_bucket_rows(rows: List[Dict[str, Any]], targets: List[int], files_per_type: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    for i, upper in enumerate(targets, start=1):
        bucket_name = f"type{i:02d}_{upper}"
        range_label = bucket_range_label(i, upper)

        h_ok = []
        m_ok = []
        h_all = []
        m_all = []

        for r in rows:
            n = int(r["body_tokens_split_space"])
            if bucket_for_tokens(n, targets) != bucket_name:
                continue

            if r["role"] == "human":
                h_all.append(r)
                if r["parse_reason"] == "ok":
                    h_ok.append(r)
            else:
                m_all.append(r)
                if r["parse_reason"] == "ok":
                    m_ok.append(r)

        # One mixed file needs 3 HWC and 3 AGC functions.
        possible_files = min(len(h_ok) // 3, len(m_ok) // 3)
        capped_files = min(possible_files, files_per_type) if files_per_type > 0 else possible_files

        out.append({
            "benchmark_type": bucket_name,
            "body_token_range": range_label,
            "hwc_all": len(h_all),
            "agc_all": len(m_all),
            "hwc_parse_ok": len(h_ok),
            "agc_parse_ok": len(m_ok),
            "possible_mixed_files_3hwc_3agc": possible_files,
            "capped_by_files_per_type": capped_files,
        })

    return out


def write_summary_txt(
    path: Path,
    input_csv: Path,
    rows: List[Dict[str, Any]],
    pair_rows: List[Dict[str, Any]],
    bucket_rows: List[Dict[str, Any]],
) -> None:
    human_body = [
        int(r["body_tokens_split_space"])
        for r in rows
        if r["role"] == "human" and r["parse_reason"] == "ok"
    ]
    agc_body = [
        int(r["body_tokens_split_space"])
        for r in rows
        if r["role"] == "lm" and r["parse_reason"] == "ok"
    ]
    min_pair = [
        int(r["min_body_tokens"])
        for r in pair_rows
        if int(r["both_parse_ok"]) == 1
    ]

    parse_counts: Dict[str, int] = {}
    for r in rows:
        key = f"{r['role']}:{r['parse_reason']}"
        parse_counts[key] = parse_counts.get(key, 0) + 1

    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("Function size analysis")
    lines.append("=" * 80)
    lines.append(f"Input CSV: {input_csv}")
    lines.append(f"Rows:      {len(rows)}")
    lines.append(f"Pairs:     {len(pair_rows)}")
    lines.append("")
    lines.append("Parse outcomes:")
    for k, v in sorted(parse_counts.items()):
        lines.append(f"  {k:30s} {v}")
    lines.append("")

    for name, vals in [
        ("HWC body tokens", human_body),
        ("AGC body tokens", agc_body),
        ("Pair min(HWC, AGC) body tokens", min_pair),
    ]:
        s = summarize(vals)
        lines.append(name)
        lines.append(
            f"  n={s['n']} mean={s['mean']} std={s['std']} "
            f"min={s['min']} p25={s['p25']} median={s['median']} "
            f"p75={s['p75']} p95={s['p95']} max={s['max']}"
        )
        lines.append("")

    lines.append("Benchmark bucket capacity, assuming 3 HWC + 3 AGC per mixed file:")
    for r in bucket_rows:
        lines.append(
            f"  {r['benchmark_type']:10s} range={r['body_token_range']:8s} "
            f"HWC_ok={r['hwc_parse_ok']:4d} AGC_ok={r['agc_parse_ok']:4d} "
            f"possible_files={r['possible_mixed_files_3hwc_3agc']:4d}"
        )
    lines.append("")
    lines.append("=" * 80)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def parse_targets(s: str) -> List[int]:
    xs = [int(x.strip()) for x in s.split(",") if x.strip()]
    if not xs:
        raise argparse.ArgumentTypeError("targets cannot be empty")
    if xs != sorted(xs):
        raise argparse.ArgumentTypeError("targets must be sorted ascending")
    return xs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze HWC/AGC function body-size distribution in merged CSV."
    )
    parser.add_argument("--input_csv", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument(
        "--targets",
        type=parse_targets,
        default=parse_targets("110,120,130,140,150,160,170,180,190,200"),
        help="Upper bounds for benchmark buckets.",
    )
    parser.add_argument(
        "--files_per_type",
        type=int,
        default=100,
        help="Used only to report capped possible files.",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv).expanduser()
    out_dir = Path(args.out_dir).expanduser()

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    out_dir.mkdir(parents=True, exist_ok=True)

    rows = read_rows(input_csv)
    pair_rows = build_pair_rows(rows)
    bucket_rows = build_bucket_rows(rows, args.targets, args.files_per_type)

    row_fields = [
        "csv_row_no",
        "idx",
        "line_num",
        "role",
        "label",
        "parse_reason",
        "full_tokens_split_space",
        "full_tokens_regex",
        "body_tokens_split_space",
        "body_tokens_regex",
        "prompt_tokens_split_space",
        "full_chars",
        "body_chars",
        "prompt_chars",
        "full_lines",
        "body_lines",
        "prompt_lines",
    ]

    pair_fields = [
        "line_num",
        "human_idx",
        "lm_idx",
        "human_parse_reason",
        "lm_parse_reason",
        "hwc_body_tokens",
        "agc_body_tokens",
        "min_body_tokens",
        "max_body_tokens",
        "abs_diff_body_tokens",
        "both_parse_ok",
    ]

    bucket_fields = [
        "benchmark_type",
        "body_token_range",
        "hwc_all",
        "agc_all",
        "hwc_parse_ok",
        "agc_parse_ok",
        "possible_mixed_files_3hwc_3agc",
        "capped_by_files_per_type",
    ]

    rows_csv = out_dir / "func_size_rows.csv"
    pairs_csv = out_dir / "func_size_pairs.csv"
    buckets_csv = out_dir / "func_size_bucket_counts.csv"
    summary_txt = out_dir / "func_size_summary.txt"

    write_csv(rows_csv, rows, row_fields)
    write_csv(pairs_csv, pair_rows, pair_fields)
    write_csv(buckets_csv, bucket_rows, bucket_fields)
    write_summary_txt(summary_txt, input_csv, rows, pair_rows, bucket_rows)

    print("=" * 80)
    print("analyze_func_size.py")
    print("=" * 80)
    print(f"input_csv  : {input_csv}")
    print(f"out_dir    : {out_dir}")
    print(f"rows       : {len(rows)}")
    print(f"pairs      : {len(pair_rows)}")
    print("")
    print(f"Wrote: {rows_csv}")
    print(f"Wrote: {pairs_csv}")
    print(f"Wrote: {buckets_csv}")
    print(f"Wrote: {summary_txt}")
    print("")
    print("Bucket capacity, assuming 3 HWC + 3 AGC per mixed file:")
    for r in bucket_rows:
        print(
            f"  {r['benchmark_type']:10s} range={r['body_token_range']:8s} "
            f"HWC_ok={r['hwc_parse_ok']:4d} AGC_ok={r['agc_parse_ok']:4d} "
            f"possible_files={r['possible_mixed_files_3hwc_3agc']:4d} "
            f"capped={r['capped_by_files_per_type']:4d}"
        )
    print("=" * 80)


if __name__ == "__main__":
    main()