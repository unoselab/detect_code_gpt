#!/usr/bin/env python3
"""
Create outputs_530_filter.jsonl from:
  1) output/CodeSearchNet/CodeLlama-7b-hf-2000-tp0.2/outputs.txt
  2) logs/npr_scores_codellama-7b-hf_csn_t02_n2000_run.csv

The CSV's source_line_no column identifies which original line in outputs.txt survived
DetectCodeGPT filtering. Each selected JSONL row keeps:
  - prompt
  - output    (MGC: machine-generated CodeLlama continuation)
  - solution  (HWC: human-written CodeSearchNet solution)

Optional score metadata can be included with --include_scores.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on {path}:{line_no + 1}: {e}") from e

            missing = {"prompt", "output", "solution"} - obj.keys()
            if missing:
                raise ValueError(f"Missing keys {sorted(missing)} on {path}:{line_no + 1}")

            records.append(obj)
    return records


def read_filter_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise ValueError(f"CSV is empty: {path}")

    if "source_line_no" not in rows[0]:
        raise ValueError(
            "CSV must contain source_line_no. The CSV row index is only the post-filter index "
            "and cannot safely map back to outputs.txt."
        )

    return rows


def build_filtered_jsonl(
    outputs_records: List[Dict[str, Any]],
    csv_rows: List[Dict[str, str]],
    include_scores: bool = False,
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    seen_source_lines = set()

    for csv_row_pos, row in enumerate(csv_rows):
        try:
            source_line_no = int(row["source_line_no"])
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Invalid source_line_no at CSV row {csv_row_pos + 2}: {row.get('source_line_no')!r}"
            ) from e

        if source_line_no < 0 or source_line_no >= len(outputs_records):
            raise IndexError(
                f"source_line_no {source_line_no} at CSV row {csv_row_pos + 2} is outside "
                f"outputs.txt range 0..{len(outputs_records) - 1}"
            )

        if source_line_no in seen_source_lines:
            raise ValueError(f"Duplicate source_line_no in CSV: {source_line_no}")
        seen_source_lines.add(source_line_no)

        src = outputs_records[source_line_no]
        out: Dict[str, Any] = {
            "prompt": src["prompt"],
            "output": src["output"],      # MGC
            "solution": src["solution"],  # HWC
        }

        if include_scores:
            out.update(
                {
                    "source_line_no": source_line_no,
                    "filter_index": int(row["index"]) if row.get("index", "").isdigit() else csv_row_pos,
                    "hwc_npr": float(row["hwc_npr"]),
                    "mgc_npr": float(row["mgc_npr"]),
                    "winner": row["winner"],
                }
            )

        filtered.append(out)

    return filtered


def write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for obj in records:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create outputs_530_filter.jsonl using source_line_no from DetectCodeGPT NPR CSV."
    )
    parser.add_argument(
        "--outputs_txt",
        default="output/CodeSearchNet/CodeLlama-7b-hf-2000-tp0.2/outputs.txt",
        help="Path to the original 2000-line generation JSONL file.",
    )
    parser.add_argument(
        "--npr_csv",
        default="logs/npr_scores_codellama-7b-hf_csn_t02_n2000_run.csv",
        help="Path to NPR CSV containing source_line_no for the 530 filtered pairs.",
    )
    parser.add_argument(
        "--out_jsonl",
        default="outputs_530_filter.jsonl",
        help="Output filtered JSONL path.",
    )
    parser.add_argument(
        "--include_scores",
        action="store_true",
        help="Also include source_line_no, filter_index, HWC/MGC NPR scores, and winner.",
    )
    args = parser.parse_args()

    outputs_path = Path(args.outputs_txt).expanduser()
    csv_path = Path(args.npr_csv).expanduser()
    out_path = Path(args.out_jsonl).expanduser()

    if not outputs_path.exists():
        raise FileNotFoundError(f"outputs.txt not found: {outputs_path}")
    if not csv_path.exists():
        raise FileNotFoundError(f"NPR CSV not found: {csv_path}")

    outputs_records = read_jsonl(outputs_path)
    csv_rows = read_filter_csv(csv_path)
    filtered = build_filtered_jsonl(outputs_records, csv_rows, include_scores=args.include_scores)
    write_jsonl(out_path, filtered)

    print(f"Loaded outputs.txt records: {len(outputs_records)}")
    print(f"Loaded filtered CSV rows:  {len(csv_rows)}")
    print(f"Wrote filtered JSONL:      {out_path}")
    print(f"Filtered JSONL records:    {len(filtered)}")

    if len(filtered) != 530:
        print(f"WARNING: expected 530 records, but wrote {len(filtered)} records.")


if __name__ == "__main__":
    main()
