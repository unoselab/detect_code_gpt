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


# -----------------------------------------------------------------------------
# Tokenization scheme
# -----------------------------------------------------------------------------

TOKENIZATION_SCHEME = "split_space_v1"
TOKENIZATION_DESCRIPTION = (
    "tokens = text.split(' '). Matches run_interactive_mode in main.py. "
    "Empty tokens from consecutive spaces are preserved. Newlines stay "
    "inside tokens."
)


def count_split_space_tokens(text: str) -> int:
    """Token count under the split_space_v1 scheme."""
    return len(text.split(" "))


def count_whitespace_tokens_regex(text: str) -> int:
    """Informational count using regex non-whitespace runs.

    Different from split_space_v1: this collapses any whitespace run (including
    newlines) and produces no empty tokens. Kept only for the top-level
    'n_tokens_total_regex' field as a sanity-check companion.
    """
    return len(re.findall(r"\S+", text))


# -----------------------------------------------------------------------------
# Region computation — char and token, computed independently
# -----------------------------------------------------------------------------

REGION_SPECS = [
    {"label": "prompt", "role": "context",    "source_field": "prompt"},
    {"label": "HWC",    "role": "non_target", "source_field": "solution"},
    {"label": "MGC",    "role": "target",     "source_field": "output"},
]


def compute_char_regions(parts: List[str]) -> List[Dict[str, Any]]:
    """Cumulative character offsets for each part, in order.

    For parts = [prompt, hwc, mgc], returns three regions whose char spans
    tile [0, len(prompt) + len(hwc) + len(mgc)) without gaps or overlaps.
    """
    regions = []
    cursor = 0
    for spec, part in zip(REGION_SPECS, parts):
        start = cursor
        end = start + len(part)
        regions.append({
            "label": spec["label"],
            "start_char": start,
            "end_char": end,
            "n_chars": end - start,
        })
        cursor = end
    return regions


def compute_token_regions(parts: List[str]) -> List[Dict[str, Any]]:
    """Cumulative split_space_v1 token offsets for each part, in order.

    IMPORTANT: this counts tokens in each part INDEPENDENTLY, then sums.
    This is NOT the same as tokenizing the concatenated string and slicing,
    because concatenation can fuse the last token of one part with the first
    token of the next when there's no whitespace at the boundary.

    We do it this way intentionally — the regions become a clean tiling of
    token indices. Consumers who care about the concatenated-string view
    should tokenize mixed_code themselves; the per-region 'n_tokens_*' fields
    here describe each part's own token count.
    """
    regions = []
    cursor = 0
    for spec, part in zip(REGION_SPECS, parts):
        n_tokens = count_split_space_tokens(part)
        start = cursor
        end = start + n_tokens
        regions.append({
            "label": spec["label"],
            "start_token_split_space_v1": start,
            "end_token_split_space_v1": end,
            "n_tokens_split_space_v1": n_tokens,
        })
        cursor = end
    return regions


def merge_regions(
    char_regions: List[Dict[str, Any]],
    token_regions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Combine the two independent passes into one region list per spec.

    Both lists must be in REGION_SPECS order.
    """
    if len(char_regions) != len(REGION_SPECS) or len(token_regions) != len(REGION_SPECS):
        raise ValueError(
            f"Expected {len(REGION_SPECS)} regions in each pass; "
            f"got char={len(char_regions)}, token={len(token_regions)}"
        )

    merged = []
    for spec, char_r, token_r in zip(REGION_SPECS, char_regions, token_regions):
        if char_r["label"] != spec["label"] or token_r["label"] != spec["label"]:
            raise ValueError(
                f"Region label mismatch: spec={spec['label']!r}, "
                f"char={char_r['label']!r}, token={token_r['label']!r}"
            )
        merged.append({
            "label":         spec["label"],
            "role":          spec["role"],
            "source_field":  spec["source_field"],
            "start_char":    char_r["start_char"],
            "end_char":      char_r["end_char"],
            "n_chars":       char_r["n_chars"],
            "start_token_split_space_v1": token_r["start_token_split_space_v1"],
            "end_token_split_space_v1":   token_r["end_token_split_space_v1"],
            "n_tokens_split_space_v1":    token_r["n_tokens_split_space_v1"],
        })
    return merged


# -----------------------------------------------------------------------------
# Benchmark builders
# -----------------------------------------------------------------------------

def build_level1_record(record: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Create the easiest benchmark sample.

    Level 1 is direct concatenation:
        prompt + solution(HWC) + output(MGC)

    The MGC target is a single contiguous region at the end of mixed_code.
    Char and token regions are computed by two independent passes over the
    three input parts, then merged.
    """
    prompt = require_string(record, "prompt", index)
    hwc    = require_string(record, "solution", index)
    mgc    = require_string(record, "output", index)

    parts = [prompt, hwc, mgc]
    mixed_code = "".join(parts)

    char_regions  = compute_char_regions(parts)
    token_regions = compute_token_regions(parts)
    regions       = merge_regions(char_regions, token_regions)

    mixed_record: Dict[str, Any] = {
        "id":               index,
        "complexity":       "level1",
        "mix_strategy":     "prompt_solution_output_concat",
        "description":      "Level 1: direct concatenation of prompt + HWC(solution) + MGC(output).",
        "tokenization":     TOKENIZATION_SCHEME,
        "source_line_no":   record.get("source_line_no"),
        "filter_index":     record.get("filter_index", record.get("index")),
        "prompt":           prompt,
        "hwc":              hwc,
        "mgc":              mgc,
        "mixed_code":       mixed_code,
        "regions":          regions,
        "target_label":     "MGC",
        "target_regions":   [r for r in regions if r["label"] == "MGC"],
        "n_chars_total":    len(mixed_code),
        "n_tokens_total_split_space_v1": count_split_space_tokens(mixed_code),
        "n_tokens_total_regex":          count_whitespace_tokens_regex(mixed_code),
    }

    # Preserve DetectCodeGPT score metadata when present.
    for key in [
        "hwc_npr", "mgc_npr", "winner",
        "hwc_logrank", "mgc_logrank",
        "hwc_perturbed_logrank", "mgc_perturbed_logrank",
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
