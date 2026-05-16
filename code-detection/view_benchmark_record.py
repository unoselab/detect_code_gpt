#!/usr/bin/env python3
"""
Debugger / viewer for batch-benchmark per-chunk results.

Given a record_id, displays every chunk of that record with:
  - NPR score and predictions (Youden / high-conf)
  - Token-level MGC overlap (positional ground truth)
  - The actual chunk source code, with MGC region highlighted

Usage:
    python view_benchmark_record.py --record_id 5
    python view_benchmark_record.py --record_id 5 --verbose
    python view_benchmark_record.py --record_id 5 --csv /path/to/results.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


# -----------------------------------------------------------------------------
# Defaults — adjust if your layout differs
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path("~/project-workspace/detect_code_gpt").expanduser()
DEFAULT_CSV = (PROJECT_ROOT / "logs" /
               "benchmark_results_benchmark_level1_codellama-7b-hf.csv")
DEFAULT_JSONL = (PROJECT_ROOT / "output" / "CodeSearchNet" /
                 "CodeLlama-7b-hf-2000-tp0.2" /
                 "outputs_530_benchmark_level1.jsonl")


# -----------------------------------------------------------------------------
# I/O
# -----------------------------------------------------------------------------

def load_chunks_for_record(csv_path: Path, record_id: int) -> List[Dict[str, Any]]:
    """Read the per-chunk CSV and return rows for the given record_id."""
    chunks = []
    with csv_path.open("r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["record_id"]) != record_id:
                continue
            # Coerce numerics
            for k in ("chunk_idx", "start_token", "end_token", "chunk_n_tokens",
                      "low_conf", "mgc_n_tokens", "n_chunk_tokens_in_mgc",
                      "overlaps_mgc_by_tokens", "source_line_no",
                      "predict_mgc_youden", "predict_mgc_highconf"):
                if k in row and row[k] != "":
                    try:
                        row[k] = int(row[k])
                    except ValueError:
                        pass
            for k in ("npr", "orig_logrank", "mean_p_logrank",
                      "intersect_ratio_chunk", "intersect_ratio_mgc"):
                if k in row and row[k] != "":
                    try:
                        row[k] = float(row[k])
                    except ValueError:
                        pass
            chunks.append(row)
    return chunks


def load_benchmark_record(jsonl_path: Path, record_id: int) -> Optional[Dict[str, Any]]:
    """Read the benchmark JSONL and return the record with the given id."""
    with jsonl_path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("id") == record_id:
                return rec
    return None


# -----------------------------------------------------------------------------
# Display helpers
# -----------------------------------------------------------------------------

def verdict_label(chunk: Dict[str, Any], threshold_youden: float = 1.3875,
                  threshold_high: float = 1.60) -> str:
    """Return a short verdict string with confidence."""
    if chunk.get("low_conf"):
        return "LOW-CONF (skipped)"
    npr = chunk.get("npr")
    if npr is None or (isinstance(npr, float) and npr != npr):  # NaN
        return "UNSCORABLE"
    if chunk.get("predict_mgc_highconf"):
        return f"MGC ★ HIGH    (NPR={npr:.4f} > {threshold_high})"
    if chunk.get("predict_mgc_youden"):
        return f"MGC   warn    (NPR={npr:.4f} > {threshold_youden})"
    return f"HWC           (NPR={npr:.4f})"


def truth_label(chunk: Dict[str, Any]) -> str:
    """Return ground-truth label based on token-level MGC overlap."""
    ratio = chunk.get("intersect_ratio_chunk", 0.0)
    if ratio == 0.0:
        return "PURE HWC"
    elif ratio == 1.0:
        return "PURE MGC"
    else:
        return f"MIXED ({100 * ratio:.0f}% MGC)"


def correctness_label(chunk: Dict[str, Any], use_high_conf: bool = False) -> str:
    """TP / FP / FN / TN based on prediction vs overlap."""
    if chunk.get("low_conf"):
        return "  -  "
    predicted = (chunk["predict_mgc_highconf"] if use_high_conf
                 else chunk["predict_mgc_youden"])
    truth = chunk["overlaps_mgc_by_tokens"]
    if predicted and truth:
        return "TP ✓"
    if predicted and not truth:
        return "FP ✗"
    if not predicted and truth:
        return "FN ✗"
    return "TN ✓"


def reconstruct_chunk_text(record: Dict[str, Any], chunk: Dict[str, Any]) -> str:
    """Reconstruct the chunk's source from the record using token indices.

    The chunk_idx and start_token/end_token are relative to hwc + mgc
    (not the full mixed_code which includes prompt).
    """
    scored_text = record["hwc"] + record["mgc"]
    all_tokens = scored_text.split(" ")
    start = chunk["start_token"]
    end = chunk["end_token"]
    return " ".join(all_tokens[start:end])


def annotate_chunk_with_mgc_boundary(record: Dict[str, Any],
                                      chunk: Dict[str, Any]) -> str:
    """Show the chunk's source with a visible marker where MGC begins (if it falls inside).

    Returns the chunk text with a marker line inserted at the HWC→MGC boundary.
    """
    chunk_text = reconstruct_chunk_text(record, chunk)
    hwc_len_chars = len(record["hwc"])

    scored_text = record["hwc"] + record["mgc"]
    all_tokens = scored_text.split(" ")

    # Find which token within this chunk crosses the HWC→MGC char boundary
    cursor = 0
    boundary_chunk_token_idx = None
    for global_tok_idx in range(chunk["start_token"]):
        cursor += len(all_tokens[global_tok_idx]) + 1
    chunk_token_start_char = cursor

    for offset, tok in enumerate(all_tokens[chunk["start_token"]:chunk["end_token"]]):
        if cursor >= hwc_len_chars:
            boundary_chunk_token_idx = offset
            break
        cursor += len(tok) + 1
    else:
        # No boundary inside this chunk — it's entirely HWC or entirely MGC
        return chunk_text

    if boundary_chunk_token_idx == 0:
        return f">>> [MGC starts at chunk start] <<<\n{chunk_text}"

    # Insert a marker at the boundary
    chunk_tokens = all_tokens[chunk["start_token"]:chunk["end_token"]]
    before = " ".join(chunk_tokens[:boundary_chunk_token_idx])
    after = " ".join(chunk_tokens[boundary_chunk_token_idx:])
    return f"{before}\n>>> [HWC|MGC boundary — token #{boundary_chunk_token_idx} of chunk] <<<\n{after}"


# -----------------------------------------------------------------------------
# Output modes
# -----------------------------------------------------------------------------

def print_record_header(record: Dict[str, Any], chunks: List[Dict[str, Any]]) -> None:
    print("=" * 78)
    print(f"  RECORD {record['id']}  (source_line_no={record.get('source_line_no')})")
    print("=" * 78)

    hwc_len = len(record["hwc"])
    mgc_len = len(record["mgc"])
    total_len = hwc_len + mgc_len

    # Approximate token counts under split_space_v1
    scored_text = record["hwc"] + record["mgc"]
    all_tokens = scored_text.split(" ")
    n_tokens_total = len(all_tokens)

    print(f"  Scored input: hwc + mgc  ({total_len} chars, ~{n_tokens_total} tokens)")
    print(f"  HWC: {hwc_len} chars (chars 0-{hwc_len - 1})")
    print(f"  MGC: {mgc_len} chars (chars {hwc_len}-{total_len - 1})")
    print(f"  Chunks: {len(chunks)}")

    # Quick stats from existing prediction columns
    n_tp = sum(1 for c in chunks
               if not c.get("low_conf") and c.get("predict_mgc_youden")
               and c.get("overlaps_mgc_by_tokens"))
    n_fp = sum(1 for c in chunks
               if not c.get("low_conf") and c.get("predict_mgc_youden")
               and not c.get("overlaps_mgc_by_tokens"))
    n_fn = sum(1 for c in chunks
               if not c.get("low_conf") and not c.get("predict_mgc_youden")
               and c.get("overlaps_mgc_by_tokens"))
    n_tn = sum(1 for c in chunks
               if not c.get("low_conf") and not c.get("predict_mgc_youden")
               and not c.get("overlaps_mgc_by_tokens"))
    print(f"  At Youden's J: TP={n_tp}  FP={n_fp}  FN={n_fn}  TN={n_tn}")
    print()


def print_compact(record: Dict[str, Any], chunks: List[Dict[str, Any]]) -> None:
    """One line per chunk."""
    print(f"  {'ci':>3} {'tokens':>14} {'len':>4}   {'NPR':>7}  {'mgc%':>6}  "
          f"{'pred (Youden)':<32}  {'TRUTH':<20}  {'  ':<4}")
    print("  " + "-" * 102)
    for c in chunks:
        ci = c["chunk_idx"]
        tok_range = f"{c['start_token']:>4}..{c['end_token']:<4}"
        n_tok = c["chunk_n_tokens"]
        npr = c.get("npr", float("nan"))
        npr_s = f"{npr:>7.4f}" if isinstance(npr, float) and npr == npr else "    nan"
        ratio = 100 * c.get("intersect_ratio_chunk", 0.0)
        pred = verdict_label(c)
        truth = truth_label(c)
        corr = correctness_label(c)
        print(f"  {ci:>3} {tok_range:>14} {n_tok:>4}   {npr_s}  {ratio:>5.1f}%  "
              f"{pred:<32}  {truth:<20}  {corr:<4}")
    print()


def print_verbose(record: Dict[str, Any], chunks: List[Dict[str, Any]]) -> None:
    """Full source per chunk."""
    for c in chunks:
        ci = c["chunk_idx"]
        print("-" * 78)
        print(f"  CHUNK {ci}  (tokens {c['start_token']}..{c['end_token']}, "
              f"{c['chunk_n_tokens']} tokens)")
        print("-" * 78)
        print(f"  Detection: {verdict_label(c)}")
        print(f"  Truth:     {truth_label(c)}  "
              f"(intersect_ratio_chunk={c.get('intersect_ratio_chunk', 0):.4f}, "
              f"intersect_ratio_mgc={c.get('intersect_ratio_mgc', 0):.4f})")
        print(f"  Result:    {correctness_label(c)} (at Youden's J)")
        if c.get("low_conf"):
            print(f"  Note:      Skipped (chunk size {c['chunk_n_tokens']} < 20 tokens)")
        print()
        annotated = annotate_chunk_with_mgc_boundary(record, c)
        for line in annotated.split("\n"):
            print(f"  | {line}")
        print()


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect per-chunk benchmark results for one record_id."
    )
    parser.add_argument("--record_id", type=int, required=True,
                        help="The record_id to inspect.")
    parser.add_argument("--csv", type=str, default=str(DEFAULT_CSV),
                        help="Path to benchmark_results CSV.")
    parser.add_argument("--jsonl", type=str, default=str(DEFAULT_JSONL),
                        help="Path to benchmark JSONL (for source reconstruction).")
    parser.add_argument("--verbose", action="store_true",
                        help="Show full chunk source with MGC boundary markers.")
    args = parser.parse_args()

    csv_path = Path(args.csv).expanduser()
    jsonl_path = Path(args.jsonl).expanduser()

    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")
    if not jsonl_path.is_file():
        raise SystemExit(f"JSONL not found: {jsonl_path}")

    chunks = load_chunks_for_record(csv_path, args.record_id)
    if not chunks:
        raise SystemExit(f"No chunks found for record_id={args.record_id} in {csv_path}")

    record = load_benchmark_record(jsonl_path, args.record_id)
    if record is None:
        raise SystemExit(f"Record {args.record_id} not found in {jsonl_path}")

    chunks.sort(key=lambda c: c["chunk_idx"])

    print_record_header(record, chunks)
    if args.verbose:
        print_verbose(record, chunks)
    else:
        print_compact(record, chunks)


if __name__ == "__main__":
    main()