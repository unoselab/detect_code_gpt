#!/usr/bin/env python3
"""
find_validsyntax_mgc.py
=======================

Validate/salvage StarCoder2 CodeSearchNet MGC outputs and export AI-Detector
pipeline CSVs.

This script combines two steps:
  1. syntax-check raw MGC and conservative trimmed/salvaged MGC;
  2. export paired HWC/MGC samples in the AI-Detector raw input format.

Expected input JSONL fields per line:
  - prompt:   function header + docstring prefix
  - output:   model-generated continuation/body
  - solution: human-written continuation/body
  - optional metadata such as source_line_no, filter_index, hwc_npr, mgc_npr

Generated AI-Detector CSV format:
  idx,code,label
  <sample_id>_human,<prompt+solution>,human
  <sample_id>_lm,<prompt+clean_output>,lm

Example, from detect_code_gpt repo root:
  python code-generation/find_validsyntax_mgc.py \
    --input output/CodeSearchNet/starcoder2-7b-3000-tp0.2/outputs-512token.txt \
    --ai-detector-data-temp /home/user1-system12/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_temp1 \
    --n-small 400 \
    --n-large 2300
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import textwrap
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


DEFAULT_INPUT = Path("output/CodeSearchNet/starcoder2-7b-3000-tp0.2/outputs-512token.txt")
DEFAULT_AI_DETECTOR_DATA_TEMP = Path(
    "/home/user1-system12/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_temp1"
)
DEFAULT_PREFIX = "codesearchnet_starcoder2-7b_python"


@dataclass
class SyntaxResult:
    ok: bool
    error: str = ""


@dataclass
class ProcessedSample:
    sample_id: str
    jsonl_line: int
    source_line_no: str
    filter_index: str
    status: str
    raw_mgc_ok: bool
    clean_mgc_ok: bool
    hwc_ok: bool
    raw_mgc_error: str
    clean_mgc_error: str
    hwc_error: str
    raw_output_len: int
    clean_output_len: int
    prompt_len: int
    solution_len: int
    hwc_npr: str
    mgc_npr: str
    winner: str
    prompt: str
    solution: str
    raw_output: str
    clean_output: str
    hwc_code: str
    mgc_code: str


def normalize_newlines(s: Any) -> str:
    """Return a string with normalized newlines."""
    return str(s or "").replace("\r\n", "\n").replace("\r", "\n")


def clean_output(output: str) -> str:
    """
    Conservatively trim over-generation after the intended function body.

    This does not rewrite/repair code logic. It only removes obvious text that
    belongs to a later file, README, markdown block, or next function/class.
    """
    s = normalize_newlines(output)

    # Hard stop: model continues into repository/file context.
    s = s.split("<file_sep>", 1)[0]

    # Hard stop: markdown/prose tail.
    s = s.split("```", 1)[0]

    # Cut when a next top-level definition/class or dangling definition appears.
    # These patterns address examples such as "\n\ndef" and "\n    def".
    patterns = [
        r"\n\n(?=def\s+\w+\s*\()",          # next top-level def
        r"\n\n(?=async\s+def\s+\w+\s*\()",  # next top-level async def
        r"\n\n(?=class\s+\w+)",             # next top-level class
        r"\n\s{4}def\s*$",                  # dangling indented "def"
        r"\n\s{4}async\s+def\s*$",
        r"\n\s{4}class\s*$",
        r"\n\s*def\s*$",                    # dangling top-level "def"
        r"\n\s*async\s+def\s*$",
        r"\n\s*class\s*$",
    ]

    cut = len(s)
    for pat in patterns:
        m = re.search(pat, s)
        if m:
            cut = min(cut, m.start())

    return s[:cut].rstrip() + "\n"


def compose_code(prompt: str, continuation: str) -> str:
    """Combine prompt and continuation, then dedent for module-level parsing."""
    return textwrap.dedent(normalize_newlines(prompt) + normalize_newlines(continuation)).strip() + "\n"


def syntax_check(code: str) -> SyntaxResult:
    try:
        ast.parse(code)
        return SyntaxResult(True, "")
    except SyntaxError as e:
        return SyntaxResult(False, f"{e.msg} at line {e.lineno}")
    except Exception as e:  # defensive; ast.parse normally raises SyntaxError
        return SyntaxResult(False, f"{type(e).__name__}: {e}")


def make_sample_id(obj: Dict[str, Any], line_no: int) -> str:
    """Build a stable unique id that is safe for AI-Detector idx values."""
    parts: List[str] = []
    if obj.get("source_line_no", "") != "":
        parts.append(f"src{obj['source_line_no']}")
    if obj.get("filter_index", "") != "":
        parts.append(f"f{obj['filter_index']}")
    parts.append(f"line{line_no}")
    return "_".join(parts)


def process_obj(obj: Dict[str, Any], line_no: int) -> ProcessedSample:
    prompt = normalize_newlines(obj.get("prompt", ""))
    solution = normalize_newlines(obj.get("solution", ""))
    raw_output = normalize_newlines(obj.get("output", ""))
    clean = clean_output(raw_output)

    raw_mgc_code = compose_code(prompt, raw_output)
    clean_mgc_code = compose_code(prompt, clean)
    hwc_code = compose_code(prompt, solution)

    raw_res = syntax_check(raw_mgc_code)
    clean_res = syntax_check(clean_mgc_code)
    hwc_res = syntax_check(hwc_code)

    if raw_res.ok:
        status = "raw_valid"
        # Prefer the conservative cleaned output when it still parses. This
        # removes over-generation even for raw-valid multi-function outputs.
        selected_output = clean if clean_res.ok else raw_output
        selected_code = clean_mgc_code if clean_res.ok else raw_mgc_code
    elif clean_res.ok:
        status = "salvaged_valid"
        selected_output = clean
        selected_code = clean_mgc_code
    else:
        status = "invalid"
        selected_output = clean
        selected_code = clean_mgc_code

    return ProcessedSample(
        sample_id=make_sample_id(obj, line_no),
        jsonl_line=line_no,
        source_line_no=str(obj.get("source_line_no", "")),
        filter_index=str(obj.get("filter_index", "")),
        status=status,
        raw_mgc_ok=raw_res.ok,
        clean_mgc_ok=clean_res.ok,
        hwc_ok=hwc_res.ok,
        raw_mgc_error=raw_res.error,
        clean_mgc_error=clean_res.error,
        hwc_error=hwc_res.error,
        raw_output_len=len(raw_output),
        clean_output_len=len(selected_output),
        prompt_len=len(prompt),
        solution_len=len(solution),
        hwc_npr=str(obj.get("hwc_npr", "")),
        mgc_npr=str(obj.get("mgc_npr", "")),
        winner=str(obj.get("winner", "")),
        prompt=prompt,
        solution=solution,
        raw_output=raw_output,
        clean_output=selected_output,
        hwc_code=hwc_code,
        mgc_code=selected_code,
    )


def iter_jsonl(path: Path) -> Iterable[Tuple[int, Optional[Dict[str, Any]], str]]:
    """Yield (line_no, object-or-None, parse_error)."""
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                yield line_no, json.loads(line), ""
            except json.JSONDecodeError as e:
                yield line_no, None, f"JSONDecodeError: {e}"


def write_jsonl(samples: List[ProcessedSample], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(asdict(sample), ensure_ascii=False) + "\n")


def write_pipeline_csv(df: pd.DataFrame, out_path: Path) -> pd.DataFrame:
    rows: List[Dict[str, str]] = []

    for _, r in df.iterrows():
        sid = r["sample_id"]
        rows.append({"idx": f"{sid}_human", "code": r["hwc_code"], "label": "human"})
        rows.append({"idx": f"{sid}_lm", "code": r["mgc_code"], "label": "lm"})

    out_df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)

    print(f"wrote: {out_path}")
    print(f"  shape: {out_df.shape}")
    print(f"  labels: {out_df['label'].value_counts().to_dict()}")
    return out_df


def summarize(samples: List[ProcessedSample], json_errors: List[Tuple[int, str]]) -> None:
    total = len(samples) + len(json_errors)
    mgc_valid = [s for s in samples if s.status in {"raw_valid", "salvaged_valid"}]
    paired_valid = [s for s in mgc_valid if s.hwc_ok]
    invalid = [s for s in samples if s.status == "invalid"]

    print("=" * 72)
    print("Syntax / salvage summary")
    print("=" * 72)
    print(f"total_lines:       {total}")
    print(f"json_errors:       {len(json_errors)}")
    print(f"mgc_valid_total:   {len(mgc_valid)}")
    print(f"raw_valid:         {sum(1 for s in samples if s.status == 'raw_valid')}")
    print(f"salvaged_valid:    {sum(1 for s in samples if s.status == 'salvaged_valid')}")
    print(f"mgc_invalid:       {len(invalid)}")
    print(f"paired_valid:      {len(paired_valid)}")
    print(f"mgc_valid_rate:    {len(mgc_valid) / max(total, 1):.4f}")
    print(f"paired_valid_rate: {len(paired_valid) / max(total, 1):.4f}")

    error_counts = Counter(s.clean_mgc_error.split(" at line ")[0] for s in invalid)
    if error_counts:
        print("\nTop clean MGC syntax errors:")
        for err, n in error_counts.most_common(20):
            print(f"  {n:5d}  {err}")

    hwc_error_counts = Counter(s.hwc_error.split(" at line ")[0] for s in mgc_valid if not s.hwc_ok)
    if hwc_error_counts:
        print("\nTop HWC syntax errors among MGC-valid samples:")
        for err, n in hwc_error_counts.most_common(20):
            print(f"  {n:5d}  {err}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate/salvage StarCoder2 MGC and export AI-Detector CSVs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input JSONL/TXT file.")
    parser.add_argument(
        "--ai-detector-data-temp",
        type=Path,
        default=Path(__import__("os").environ.get("AI_DETECTOR_DATA_TEMP", str(DEFAULT_AI_DETECTOR_DATA_TEMP))),
        help="AI-Detector data_temp1 directory for pipeline CSV outputs.",
    )
    parser.add_argument("--prefix", default=DEFAULT_PREFIX, help="Output filename prefix.")
    parser.add_argument("--n-small", type=int, default=400, help="Option A pair count.")
    parser.add_argument("--n-large", type=int, default=2300, help="Option B pair count.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling.")
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Directory for JSONL reports and metadata. Default: <input_parent>/ai_detector_export_metadata.",
    )
    parser.add_argument(
        "--allow-replacement",
        action="store_true",
        help="Allow sampling with replacement if fewer than --n-large paired-valid samples exist.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    if not input_path.exists():
        print(f"[ERROR] input not found: {input_path}", file=sys.stderr)
        return 2

    report_dir = args.report_dir or (input_path.parent / "ai_detector_export_metadata")
    report_dir.mkdir(parents=True, exist_ok=True)

    samples: List[ProcessedSample] = []
    json_errors: List[Tuple[int, str]] = []

    for line_no, obj, json_error in iter_jsonl(input_path):
        if obj is None:
            json_errors.append((line_no, json_error))
            continue
        samples.append(process_obj(obj, line_no))

    summarize(samples, json_errors)

    mgc_valid = [s for s in samples if s.status in {"raw_valid", "salvaged_valid"}]
    mgc_invalid = [s for s in samples if s.status == "invalid"]
    paired_valid = [s for s in mgc_valid if s.hwc_ok]

    write_jsonl(mgc_valid, report_dir / "valid_mgc_salvaged.jsonl")
    write_jsonl(mgc_invalid, report_dir / "invalid_mgc_salvaged.jsonl")

    if json_errors:
        pd.DataFrame(json_errors, columns=["jsonl_line", "error"]).to_csv(
            report_dir / "json_decode_errors.csv", index=False
        )

    df = pd.DataFrame(asdict(s) for s in paired_valid)
    if df.empty:
        print("[ERROR] no paired-valid samples available.", file=sys.stderr)
        return 3

    df.to_csv(report_dir / f"{args.prefix}_all_paired_valid_metadata.csv", index=False)

    if len(df) < args.n_large and not args.allow_replacement:
        print(
            f"[ERROR] Need at least {args.n_large} paired-valid samples, found {len(df)}. "
            f"Use --allow-replacement or lower --n-large.",
            file=sys.stderr,
        )
        return 4

    replace = len(df) < args.n_large
    df_large = df.sample(n=args.n_large, random_state=args.seed, replace=replace).reset_index(drop=True)
    df_small = df_large.sample(n=args.n_small, random_state=args.seed, replace=False).reset_index(drop=True)

    out_small = args.ai_detector_data_temp / f"{args.prefix}_merged.csv"
    out_large = args.ai_detector_data_temp / f"{args.prefix}_merged_{args.n_large}.csv"

    print("\n" + "=" * 72)
    print("Writing AI-Detector pipeline CSVs")
    print("=" * 72)
    write_pipeline_csv(df_small, out_small)
    write_pipeline_csv(df_large, out_large)

    meta_small = report_dir / f"{args.prefix}_{args.n_small}_metadata.csv"
    meta_large = report_dir / f"{args.prefix}_{args.n_large}_metadata.csv"
    df_small.to_csv(meta_small, index=False)
    df_large.to_csv(meta_large, index=False)

    print("\nmetadata:")
    print(f"  {meta_small}")
    print(f"  {meta_large}")
    print(f"  {report_dir / f'{args.prefix}_all_paired_valid_metadata.csv'}")
    print("\nnext:")
    print("  cd /home/user1-system12/project-workspace/ai_detector")
    print("  bash src/run1-ast-generator.sh baseline")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
