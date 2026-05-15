#!/usr/bin/env python3
"""
Generate benchmark datasets for mixed HWC/MGC code localization.

Level 1 benchmark:
    mixed_code = prompt + solution + output

Where:
    prompt   = function header + docstring
    solution = HWC, human-written code
    output   = MGC, machine-generated code

The output JSONL stores character-span ground truth so that localization
results from code-detection/main.py can be compared against the true MGC
region.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SUPPORTED_COMPLEXITIES = ["level1"]


# -----------------------------------------------------------------------------
# I/O helpers
# -----------------------------------------------------------------------------

def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no} of {path}: {exc}") from exc
            records.append(record)
    return records


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


# -----------------------------------------------------------------------------
# Span helpers
# -----------------------------------------------------------------------------

def require_string(record: Dict[str, Any], key: str, index: int) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise ValueError(
            f"Record {index} is missing required string field {key!r}. "
            f"Available keys: {sorted(record.keys())}"
        )
    return value


def count_whitespace_tokens(text: str) -> int:
    """Match run_interactive_mode's current rough tokenization purposefully.

    The detector chunks by whitespace tokens. For benchmark metadata, this count
    is informational; character spans remain the source of truth for evaluation.
    """
    return len(re.findall(r"\S+", text))


def token_span_for_char_span(token_matches: List[re.Match[str]], start_char: int, end_char: int) -> Tuple[Optional[int], Optional[int]]:
    """Return token span [start, end) overlapping the character span.

    A region can start or end with whitespace, so this function returns the span
    of non-whitespace tokens that overlap the region. If the region has no
    non-whitespace tokens, returns (None, None).
    """
    overlapping: List[int] = []
    for idx, match in enumerate(token_matches):
        if match.end() <= start_char:
            continue
        if match.start() >= end_char:
            break
        overlapping.append(idx)

    if not overlapping:
        return None, None
    return overlapping[0], overlapping[-1] + 1


def add_token_spans(mixed_code: str, regions: List[Dict[str, Any]]) -> None:
    token_matches = list(re.finditer(r"\S+", mixed_code))
    for region in regions:
        token_start, token_end = token_span_for_char_span(
            token_matches,
            int(region["start_char"]),
            int(region["end_char"]),
        )
        region["start_token"] = token_start
        region["end_token"] = token_end
        region["n_tokens"] = None if token_start is None else token_end - token_start


# -----------------------------------------------------------------------------
# Benchmark builders
# -----------------------------------------------------------------------------

def build_level1_record(record: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Create the easiest benchmark sample.

    Level 1 is direct concatenation:
        prompt + solution(HWC) + output(MGC)

    The MGC target is a single contiguous region at the end of mixed_code.
    """
    prompt = require_string(record, "prompt", index)
    hwc = require_string(record, "solution", index)
    mgc = require_string(record, "output", index)

    prompt_start = 0
    prompt_end = prompt_start + len(prompt)

    hwc_start = prompt_end
    hwc_end = hwc_start + len(hwc)

    mgc_start = hwc_end
    mgc_end = mgc_start + len(mgc)

    mixed_code = prompt + hwc + mgc

    regions: List[Dict[str, Any]] = [
        {
            "label": "prompt",
            "role": "context",
            "source_field": "prompt",
            "start_char": prompt_start,
            "end_char": prompt_end,
            "n_chars": prompt_end - prompt_start,
        },
        {
            "label": "HWC",
            "role": "non_target",
            "source_field": "solution",
            "start_char": hwc_start,
            "end_char": hwc_end,
            "n_chars": hwc_end - hwc_start,
        },
        {
            "label": "MGC",
            "role": "target",
            "source_field": "output",
            "start_char": mgc_start,
            "end_char": mgc_end,
            "n_chars": mgc_end - mgc_start,
        },
    ]
    add_token_spans(mixed_code, regions)

    mixed_record: Dict[str, Any] = {
        "id": index,
        "complexity": "level1",
        "mix_strategy": "prompt_solution_output_concat",
        "description": "Level 1: direct concatenation of prompt + HWC(solution) + MGC(output).",
        "source_line_no": record.get("source_line_no"),
        "filter_index": record.get("filter_index", record.get("index")),
        "prompt": prompt,
        "hwc": hwc,
        "mgc": mgc,
        "mixed_code": mixed_code,
        "regions": regions,
        "target_label": "MGC",
        "target_regions": [region for region in regions if region["label"] == "MGC"],
        "n_chars_total": len(mixed_code),
        "n_tokens_total": count_whitespace_tokens(mixed_code),
    }

    # Preserve useful DetectCodeGPT score metadata if outputs_530_filter.jsonl
    # was created with --include_scores.
    for key in [
        "hwc_npr",
        "mgc_npr",
        "winner",
        "hwc_logrank",
        "mgc_logrank",
        "hwc_perturbed_logrank",
        "mgc_perturbed_logrank",
    ]:
        if key in record:
            mixed_record[key] = record[key]

    return mixed_record


def build_benchmark(records: List[Dict[str, Any]], complexity: str) -> List[Dict[str, Any]]:
    if complexity == "level1":
        return [build_level1_record(record, index=i) for i, record in enumerate(records)]
    raise ValueError(f"Unsupported complexity: {complexity}. Supported values: {SUPPORTED_COMPLEXITIES}")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def resolve_default_output(input_path: Path, complexity: str) -> Path:
    return input_path.with_name(f"outputs_530_benchmark_{complexity}.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate mixed HWC/MGC localization benchmark datasets."
    )
    parser.add_argument(
        "--complexity",
        choices=SUPPORTED_COMPLEXITIES,
        default="level1",
        help="Benchmark complexity level. level1 = prompt + solution(HWC) + output(MGC).",
    )
    parser.add_argument(
        "--input_jsonl",
        default="output/CodeSearchNet/CodeLlama-7b-hf-2000-tp0.2/outputs_530_filter.jsonl",
        help="Input filtered JSONL containing prompt, solution, and output.",
    )
    parser.add_argument(
        "--out_jsonl",
        default=None,
        help="Output benchmark JSONL path. If omitted, uses outputs_530_benchmark_<complexity>.jsonl next to input_jsonl.",
    )
    parser.add_argument(
        "--project_root",
        default=None,
        help="Optional project root path to abbreviate as PRJ in printed output.",
    )
    args = parser.parse_args()

    input_path = Path(args.input_jsonl).expanduser()
    out_path = Path(args.out_jsonl).expanduser() if args.out_jsonl else resolve_default_output(input_path, args.complexity)
    project_root = Path(args.project_root).expanduser().resolve() if args.project_root else None

    def display_path(path: Path) -> str:
        if project_root is None:
            return str(path)
        try:
            resolved_path = path.resolve()
            relative_path = resolved_path.relative_to(project_root)
            return f"PRJ/{relative_path}"
        except ValueError:
            return str(path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input JSONL not found: {display_path(input_path)}")

    records = read_jsonl(input_path)
    benchmark_records = build_benchmark(records, complexity=args.complexity)
    written = write_jsonl(out_path, benchmark_records)

    print(f"Loaded filtered records:   {len(records)}")
    print(f"Benchmark complexity:      {args.complexity}")
    print(f"Mix strategy:              prompt + HWC(solution) + MGC(output)")
    print(f"Wrote benchmark JSONL:     {display_path(out_path)}")
    print(f"Benchmark records:         {written}")


if __name__ == "__main__":
    main()
