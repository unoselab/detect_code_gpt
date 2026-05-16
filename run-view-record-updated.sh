#!/usr/bin/env bash
# Show one benchmark record and display each token chunk with MGC overlap metadata.
# Usage:
#   ./run-view-record.sh [record_id] [chunk_size]
# Example:
#   ./run-view-record.sh 6 128

set -euo pipefail

RECORD_ID="${1:-0}"
CHUNK_SIZE="${2:-128}"

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/project-workspace/detect_code_gpt}"
BENCHMARK_JSONL="${BENCHMARK_JSONL:-$PROJECT_ROOT/output/CodeSearchNet/CodeLlama-7b-hf-2000-tp0.2/outputs_530_benchmark_level1.jsonl}"

if [[ ! -f "$BENCHMARK_JSONL" ]]; then
    echo "ERROR: benchmark JSONL not found:" >&2
    echo "  $BENCHMARK_JSONL" >&2
    echo "Set BENCHMARK_JSONL=/path/to/file.jsonl or PROJECT_ROOT=/path/to/detect_code_gpt" >&2
    exit 1
fi

python - "$BENCHMARK_JSONL" "$RECORD_ID" "$CHUNK_SIZE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
record_id = int(sys.argv[2])
chunk_size = int(sys.argv[3])


def split_space_token_spans(text):
    """Return [(token, char_start, char_end)] using the same tokenization as split(' ')."""
    tokens = text.split(" ")
    spans = []
    pos = 0
    for tok in tokens:
        start = pos
        end = start + len(tok)
        spans.append((tok, start, end))
        # split(' ') consumes exactly one delimiter between tokens.
        # This mirrors the benchmark/chunk calibration logic.
        pos = end + 1
    return spans


def find_record():
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if int(r.get("id", -1)) == record_id:
                return r
    return None


r = find_record()
if r is None:
    print(f"ERROR: record_id={record_id} not found in {path}", file=sys.stderr)
    sys.exit(1)

mixed_code = r["mixed_code"]
mgc_text = r.get("output") or r.get("mgc") or r.get("MGC")
if mgc_text is None:
    # Fallback: try region text if present.
    for region in r.get("regions", []):
        if region.get("label") == "MGC" and "text" in region:
            mgc_text = region["text"]
            break

if mgc_text is None:
    print("ERROR: cannot find MGC text in this record. Expected key 'output' or MGC region text.", file=sys.stderr)
    sys.exit(1)

mgc_char_start = mixed_code.find(mgc_text)
if mgc_char_start < 0:
    print("ERROR: MGC text was not found as a substring of mixed_code.", file=sys.stderr)
    print("This indicates an upstream benchmark-generation or text-normalization mismatch.", file=sys.stderr)
    sys.exit(1)
mgc_char_end = mgc_char_start + len(mgc_text)

token_spans = split_space_token_spans(mixed_code)
all_tokens = [t for t, _, _ in token_spans]
mgc_token_indices = [
    i for i, (_, start, end) in enumerate(token_spans)
    if start >= mgc_char_start and end <= mgc_char_end
]
mgc_n_tokens = len(mgc_token_indices)

source_line_no = r.get("source_line_no", "NA")
print("=" * 88)
print(f"Record {record_id} | source_line_no={source_line_no} | chunk_size={chunk_size}")
print(f"Benchmark: {path}")
print(f"Total tokens: {len(all_tokens)}")
print(f"MGC chars: [{mgc_char_start}, {mgc_char_end}) | MGC tokens: {mgc_n_tokens}")
print("=" * 88)

# Optional: show stored region metadata if available.
if r.get("regions"):
    print("\n[Stored regions]")
    for region in r["regions"]:
        label = region.get("label", "?")
        s_tok = region.get("start_token", "?")
        e_tok = region.get("end_token", "?")
        s_chr = region.get("start_char", "?")
        e_chr = region.get("end_char", "?")
        print(f"  {label:>6}: tokens [{s_tok}, {e_tok}) | chars [{s_chr}, {e_chr})")

print("\n[Chunks]")
for chunk_idx, start_tok in enumerate(range(0, len(all_tokens), chunk_size)):
    end_tok = min(start_tok + chunk_size, len(all_tokens))
    chunk_tokens = all_tokens[start_tok:end_tok]
    chunk_n_tokens = len(chunk_tokens)

    n_chunk_tokens_in_mgc = sum(1 for i in range(start_tok, end_tok) if i in set(mgc_token_indices))
    intersect_ratio_chunk = n_chunk_tokens_in_mgc / chunk_n_tokens if chunk_n_tokens else 0.0
    intersect_ratio_mgc = n_chunk_tokens_in_mgc / mgc_n_tokens if mgc_n_tokens else 0.0
    overlaps_mgc_by_tokens = int(intersect_ratio_chunk >= 0.5)

    print("\n" + "-" * 88)
    print(
        f"Chunk {chunk_idx} | tokens [{start_tok}, {end_tok}) | n={chunk_n_tokens} | "
        f"MGC tokens in chunk={n_chunk_tokens_in_mgc}/{chunk_n_tokens} | "
        f"ratio_chunk={intersect_ratio_chunk:.4f} | ratio_mgc={intersect_ratio_mgc:.4f} | "
        f"overlaps_mgc_by_tokens={overlaps_mgc_by_tokens}"
    )
    print("-" * 88)
    print(" ".join(chunk_tokens))

if "mixed_code_annotated" in r:
    print("\n" + "=" * 88)
    print("[Full annotated mixed_code]")
    print("=" * 88)
    print(r["mixed_code_annotated"])
PY
