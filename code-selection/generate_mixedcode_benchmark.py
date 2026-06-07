#!/usr/bin/env python3
"""
generate_mixedcode_benchmark.py

Generate length-controlled mixed-code localization benchmarks from merged
HWC/AGC CSV files.

Input CSV format:
    idx,code,label
    line1_human,"def ...",human
    line1_lm,"def ...",lm
    line10_human,"def ...",human
    line10_lm,"def ...",lm

Output structure:
    mixedcode_benchmarks/
      type01_110/
        mixed_code_001.py
        mixed_code_001.json
        ...
      type02_120/
        mixed_code_001.py
        mixed_code_001.json
        ...

Each generated .py file contains six top-level functions:
    - 3 HWC functions
    - 3 AGC functions

Each function body length is controlled by the type bucket:
    type01_110: 100 <= body_tokens <= 110
    type02_120: 110 <  body_tokens <= 120
    ...
    type10_200: 190 <  body_tokens <= 200

Ground-truth labels and spans are stored only in the sidecar .json file, not in
comments inside the .py file, so the benchmark input remains clean code.
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
DEFAULT_TARGETS = [110, 120, 130, 140, 150, 160, 170, 180, 190, 200]
TOKENIZATION_SCHEME = "split_space_v1"
TOKENIZATION_DESCRIPTION = (
    "tokens = text.split(' '). Empty tokens from repeated literal spaces are "
    "preserved; newlines remain inside tokens. This matches the project "
    "whitespace-token convention used for body chunking."
)


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
class FunctionCandidate:
    source_line_num: int
    source_idx: str
    role: str  # HWC or AGC
    prompt: str
    body: str
    body_tokens: int
    full_function: str


# ---------------------------------------------------------------------------
# Tokenization helpers
# ---------------------------------------------------------------------------

def count_split_space_tokens(text: str) -> int:
    return len(text.split(" "))


def count_regex_tokens(text: str) -> int:
    return len(re.findall(r"\S+", text))


def token_spans_split_space(text: str) -> List[Tuple[int, int]]:
    """Return [start_char, end_char) spans under text.split(' ')."""
    spans: List[Tuple[int, int]] = []
    cursor = 0
    for tok in text.split(" "):
        start = cursor
        end = start + len(tok)
        spans.append((start, end))
        cursor = end + 1
    return spans


def assign_token_span_for_char_span(
    token_spans: Sequence[Tuple[int, int]],
    start_char: int,
    end_char: int,
) -> Tuple[int, int, int]:
    """Assign tokens by token-start position to a char span.

    Returns (start_token, end_token, n_tokens). Token spans are half-open.
    """
    indices = [
        i for i, (s, _e) in enumerate(token_spans)
        if start_char <= s < end_char
    ]
    if not indices:
        return 0, 0, 0
    return indices[0], indices[-1] + 1, len(indices)


def assert_no_token_crosses_boundary(
    text: str,
    boundaries: Sequence[int],
    context: str,
) -> None:
    """Fail if a split_space_v1 token crosses a region/function boundary."""
    spans = token_spans_split_space(text)
    crossing = []
    for tok_idx, (start, end) in enumerate(spans):
        for boundary in boundaries:
            if start < boundary < end:
                crossing.append({
                    "token_idx": tok_idx,
                    "token_start": start,
                    "token_end": end,
                    "boundary": boundary,
                    "token_preview": text[start:end][:80],
                })
    if crossing:
        raise ValueError(
            f"split_space_v1 token crosses a boundary in {context}; "
            f"examples={crossing[:3]}"
        )


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def load_pairs_from_csv(csv_path: Path) -> List[PairRecord]:
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
                raise ValueError(f"Unexpected idx format at row {row_no}: {idx!r}")

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
    """Return prompt and scorable body.

    prompt = def/class header + leading docstring if present.
    body   = remaining body statements.

    This mirrors the body-only logic used by main_adapter.py, while preserving
    the prompt so mixed benchmark files remain valid complete functions.
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


def make_split_space_safe_function_block(raw_func: str, is_first: bool, is_last: bool) -> str:
    """
    Build a valid Python function block whose boundaries are safe under
    split_space_v1 = text.split(" ").

    The key idea:
      - Non-final functions end with a literal space.
      - Blank lines before the next function belong to the next function block.
      - Therefore a token like "\\n\\ndef" starts exactly at the next region,
        rather than crossing from the previous region into the next one.
    """
    prefix = "" if is_first else "\n\n"
    core = raw_func.rstrip("\n")
    suffix = "\n" if is_last else " "
    return prefix + core + suffix


# ---------------------------------------------------------------------------
# Candidate creation
# ---------------------------------------------------------------------------

def make_function_candidate(
    source_line_num: int,
    source_idx: str,
    role: str,
    code: str,
    prompt_override: Optional[str] = None,
) -> Tuple[Optional[FunctionCandidate], str]:
    split = split_prompt_and_body(code)
    if split.reason != "ok":
        return None, f"split_{split.reason}"

    prompt = prompt_override if prompt_override is not None else split.prompt
    body = split.body
    if not body.strip():
        return None, "empty_body"

    full_function = prompt + body
    if not parses_ok(full_function):
        return None, "parse_fail"

    n_tokens = count_split_space_tokens(body)
    return FunctionCandidate(
        source_line_num=source_line_num,
        source_idx=source_idx,
        role=role,
        prompt=prompt,
        body=body,
        body_tokens=n_tokens,
        full_function=full_function,
    ), "ok"


def collect_candidates(
    pairs: Iterable[PairRecord],
    require_lm_with_human_prompt: bool = True,
) -> Tuple[List[FunctionCandidate], Dict[str, int]]:
    candidates: List[FunctionCandidate] = []
    skip_counts: Dict[str, int] = {}

    for pair in pairs:
        h_split = split_prompt_and_body(pair.human_code)
        if h_split.reason != "ok":
            skip_counts[f"human_{h_split.reason}"] = skip_counts.get(f"human_{h_split.reason}", 0) + 1
            continue

        h_cand, h_reason = make_function_candidate(
            pair.line_num, pair.human_idx, "HWC", pair.human_code
        )
        if h_cand is None:
            skip_counts[f"human_{h_reason}"] = skip_counts.get(f"human_{h_reason}", 0) + 1
        else:
            candidates.append(h_cand)

        lm_prompt_override = h_split.prompt if require_lm_with_human_prompt else None
        l_cand, l_reason = make_function_candidate(
            pair.line_num, pair.lm_idx, "AGC", pair.lm_code, prompt_override=lm_prompt_override
        )
        if l_cand is None:
            skip_counts[f"lm_{l_reason}"] = skip_counts.get(f"lm_{l_reason}", 0) + 1
        else:
            candidates.append(l_cand)

    return candidates, skip_counts


def bucket_bounds_for_target(target: int, width: int) -> Tuple[int, int]:
    lower = target - width
    upper = target
    return lower, upper


def in_bucket(n_tokens: int, target: int, width: int, first_bucket_inclusive: bool = True) -> bool:
    lower, upper = bucket_bounds_for_target(target, width)
    if first_bucket_inclusive:
        return lower <= n_tokens <= upper
    return lower < n_tokens <= upper


# ---------------------------------------------------------------------------
# Mixed file construction
# ---------------------------------------------------------------------------

def make_safe_unique_function_text(
    cand: FunctionCandidate,
    file_id: int,
    function_id: int,
) -> Tuple[str, str]:
    """Rename the top-level function to avoid duplicate names within a file.

    Returns (new_function_text, new_name).
    """
    code = cand.prompt + cand.body
    try:
        tree = ast.parse(code if code.endswith("\n") else code + "\n")
        node = first_top_level_def_or_class(tree)
        old_name = getattr(node, "name", None) if node is not None else None
    except SyntaxError:
        old_name = None

    prefix = cand.role.lower()
    new_name = f"{prefix}_mixed_{file_id:03d}_{function_id:02d}"

    if old_name:
        pattern = re.compile(rf"^(\s*(?:async\s+def|def|class)\s+){re.escape(old_name)}\b", re.MULTILINE)
        new_code, n = pattern.subn(rf"\1{new_name}", code, count=1)
        if n == 1:
            return new_code, new_name

    # Fallback: keep original if rename fails. Caller will parse-check file.
    return code, old_name or new_name


def build_mixed_file_record(
    selected: Sequence[FunctionCandidate],
    target: int,
    bucket_width: int,
    type_name: str,
    file_id: int,
) -> Tuple[str, Dict[str, Any]]:
    if len(selected) != 6:
        raise ValueError(f"Expected 6 functions, got {len(selected)}")
    if sum(1 for c in selected if c.role == "HWC") != 3:
        raise ValueError("Expected exactly 3 HWC functions")
    if sum(1 for c in selected if c.role == "AGC") != 3:
        raise ValueError("Expected exactly 3 AGC functions")

    chunks: List[str] = []
    functions_meta: List[Dict[str, Any]] = []
    cursor = 0

    for i, cand in enumerate(selected, start=1):
        raw_func, func_name = make_safe_unique_function_text(cand, file_id=file_id, function_id=i)
        func_text = make_split_space_safe_function_block(
            raw_func,
            is_first=(i == 1),
            is_last=(i == len(selected)),
        )
        start_char = cursor
        end_char = start_char + len(func_text)

        # Body span within this function after renaming.
        split = split_prompt_and_body(func_text)
        if split.reason != "ok":
            raise ValueError(f"Split failed after renaming: {split.reason}")
        body_start_rel = len(split.prompt)
        body_end_rel = body_start_rel + len(split.body)
        body_start_char = start_char + body_start_rel
        body_end_char = start_char + body_end_rel

        chunks.append(func_text)
        cursor = end_char

        functions_meta.append({
            "function_id": i,
            "function_name": func_name,
            "role": cand.role,
            "is_target": cand.role == "AGC",
            "source_line_num": cand.source_line_num,
            "source_idx": cand.source_idx,
            "body_tokens": cand.body_tokens,
            "body_tokens_regex": count_regex_tokens(cand.body),
            "function_start_char": start_char,
            "function_end_char": end_char,
            "body_start_char": body_start_char,
            "body_end_char": body_end_char,
            "body_n_chars": body_end_char - body_start_char,
        })

    mixed_code = "".join(chunks)
    if not parses_ok(mixed_code):
        raise ValueError(f"Generated mixed file does not parse: {type_name}/mixed_code_{file_id:03d}.py")

    boundaries = [m["function_end_char"] for m in functions_meta[:-1]]
    assert_no_token_crosses_boundary(mixed_code, boundaries, context=f"{type_name}/mixed_code_{file_id:03d}.py")

    token_spans = token_spans_split_space(mixed_code)
    for m in functions_meta:
        s, e, n = assign_token_span_for_char_span(token_spans, m["function_start_char"], m["function_end_char"])
        bs, be, bn = assign_token_span_for_char_span(token_spans, m["body_start_char"], m["body_end_char"])
        m["function_start_token"] = s
        m["function_end_token"] = e
        m["function_n_tokens"] = n
        m["body_start_token"] = bs
        m["body_end_token"] = be
        m["body_n_tokens_in_mixed_stream"] = bn

    target_regions = [m for m in functions_meta if m["is_target"]]

    metadata = {
        "file_id": file_id,
        "filename": f"mixed_code_{file_id:03d}.py",
        "benchmark_type": type_name,
        "target_bucket_upper": target,
        "bucket_width": bucket_width,
        "bucket_lower_exclusive_except_type01": target - bucket_width,
        "bucket_description": (
            f"type01 uses {target - bucket_width} <= tokens <= {target}; "
            f"later types use lower < tokens <= upper."
        ),
        "n_functions": len(functions_meta),
        "n_hwc_functions": 3,
        "n_agc_functions": 3,
        "tokenization": TOKENIZATION_SCHEME,
        "tokenization_description": TOKENIZATION_DESCRIPTION,
        "n_chars_total": len(mixed_code),
        "n_tokens_total": count_split_space_tokens(mixed_code),
        "functions": functions_meta,
        "target_regions": target_regions,
    }
    return mixed_code, metadata


def chunk_into_files(
    hwc: List[FunctionCandidate],
    agc: List[FunctionCandidate],
    files_per_type: int,
    rng: random.Random,
) -> List[List[FunctionCandidate]]:
    n_possible = min(len(hwc) // 3, len(agc) // 3)
    n_files = n_possible if files_per_type <= 0 else min(files_per_type, n_possible)

    files: List[List[FunctionCandidate]] = []
    for file_idx in range(n_files):
        h_group = hwc[file_idx * 3:(file_idx + 1) * 3]
        a_group = agc[file_idx * 3:(file_idx + 1) * 3]
        selected = list(h_group) + list(a_group)
        rng.shuffle(selected)
        files.append(selected)
    return files


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(text)


def write_manifest(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    fieldnames = [
        "benchmark_type", "target", "token_range", "n_hwc_candidates",
        "n_agc_candidates", "n_files", "out_dir",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_targets(s: str) -> List[int]:
    xs = [int(x.strip()) for x in s.split(",") if x.strip()]
    if not xs:
        raise argparse.ArgumentTypeError("At least one target is required")
    return xs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate 6-function mixed-code benchmark .py files with JSON ground truth."
    )
    parser.add_argument("--input_csv", required=True, help="Merged HWC/AGC CSV with idx,code,label")
    parser.add_argument("--out_dir", required=True, help="Output benchmark root directory")
    parser.add_argument(
        "--targets",
        type=parse_targets,
        default=DEFAULT_TARGETS,
        help="Comma-separated bucket upper bounds. Default: 110,120,...,200",
    )
    parser.add_argument("--bucket_width", type=int, default=10, help="Token bucket width. Default: 10")
    parser.add_argument(
        "--files_per_type",
        type=int,
        default=0,
        help="Number of mixed_code_*.py files per type. 0 = maximum possible.",
    )
    parser.add_argument("--seed", type=int, default=0, help="Random seed")
    parser.add_argument("--no_shuffle_candidates", action="store_true", help="Do not shuffle candidate pools")
    parser.add_argument(
        "--allow_reuse_across_types",
        action="store_true",
        help="Allow the same source function to appear in multiple type buckets. Normally unnecessary because buckets do not overlap.",
    )
    parser.add_argument(
        "--keep_lm_prompt",
        action="store_true",
        help="Use the LM row's own prompt instead of replacing it with the human prompt. Default uses human prompt for AGC body.",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv).expanduser()
    out_root = Path(args.out_dir).expanduser()
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")
    if args.bucket_width <= 0:
        raise ValueError("--bucket_width must be positive")

    rng = random.Random(args.seed)

    print("=" * 80)
    print("generate_mixedcode_benchmark.py")
    print("=" * 80)
    print(f"input_csv      : {input_csv}")
    print(f"out_dir        : {out_root}")
    print(f"targets        : {args.targets}")
    print(f"bucket_width   : {args.bucket_width}")
    print(f"files_per_type : {args.files_per_type if args.files_per_type > 0 else 'max'}")
    print(f"seed           : {args.seed}")
    print("=" * 80)

    pairs = load_pairs_from_csv(input_csv)
    print(f"Loaded pairs   : {len(pairs)}")

    candidates, skip_counts = collect_candidates(
        pairs,
        require_lm_with_human_prompt=not args.keep_lm_prompt,
    )
    print(f"Candidates     : {len(candidates)}")
    if skip_counts:
        print("Skipped:")
        for k, v in sorted(skip_counts.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {k:35s} {v}")

    if not args.no_shuffle_candidates:
        rng.shuffle(candidates)

    used_keys = set()
    manifest_rows: List[Dict[str, Any]] = []

    for type_idx, target in enumerate(args.targets, start=1):
        type_name = f"type{type_idx:02d}_{target}"
        lower = target - args.bucket_width
        token_range = f"{lower}-{target}" if type_idx == 1 else f"{lower + 1}-{target}"
        type_dir = out_root / type_name
        type_dir.mkdir(parents=True, exist_ok=True)

        hwc_pool: List[FunctionCandidate] = []
        agc_pool: List[FunctionCandidate] = []

        for c in candidates:
            key = (c.role, c.source_idx)
            if not args.allow_reuse_across_types and key in used_keys:
                continue
            ok = in_bucket(c.body_tokens, target, args.bucket_width, first_bucket_inclusive=(type_idx == 1))
            if not ok:
                continue
            if c.role == "HWC":
                hwc_pool.append(c)
            else:
                agc_pool.append(c)

        if not args.no_shuffle_candidates:
            rng.shuffle(hwc_pool)
            rng.shuffle(agc_pool)

        file_groups = chunk_into_files(hwc_pool, agc_pool, args.files_per_type, rng)

        written = 0
        for file_id, selected in enumerate(file_groups, start=1):
            try:
                mixed_code, meta = build_mixed_file_record(
                    selected=selected,
                    target=target,
                    bucket_width=args.bucket_width,
                    type_name=type_name,
                    file_id=file_id,
                )
            except ValueError as exc:
                print(f"[WARN] skipped {type_name}/mixed_code_{file_id:03d}: {exc}")
                continue

            py_path = type_dir / f"mixed_code_{file_id:03d}.py"
            json_path = type_dir / f"mixed_code_{file_id:03d}.json"
            write_text(py_path, mixed_code)
            write_json(json_path, meta)
            written += 1

            if not args.allow_reuse_across_types:
                for c in selected:
                    used_keys.add((c.role, c.source_idx))

        try:
            home_path = Path.home()
            generalized_out_dir = Path("~") / type_dir.relative_to(home_path)
        except ValueError:
            generalized_out_dir = type_dir

        manifest_rows.append({
            "benchmark_type": type_name,
            "target": target,
            "token_range": token_range,
            "n_hwc_candidates": len(hwc_pool),
            "n_agc_candidates": len(agc_pool),
            "n_files": written,
            "out_dir": str(generalized_out_dir),
        })

        # manifest_rows.append({
        #     "benchmark_type": type_name,
        #     "target": target,
        #     "token_range": token_range,
        #     "n_hwc_candidates": len(hwc_pool),
        #     "n_agc_candidates": len(agc_pool),
        #     "n_files": written,
        #     "out_dir": str(type_dir.relative_to(out_root.parent)),
        # })

        print(
            f"{type_name}: token_range={token_range}, "
            f"HWC candidates={len(hwc_pool)}, AGC candidates={len(agc_pool)}, "
            f"files={written}, out={type_dir}"
        )

    manifest_path = out_root / "manifest.csv"
    write_manifest(manifest_path, manifest_rows)
    print(f"Manifest       : {manifest_path}")
    print("=" * 80)
    print("Done")
    print("=" * 80)


if __name__ == "__main__":
    main()
