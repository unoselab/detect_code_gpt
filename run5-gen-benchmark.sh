#!/bin/bash
# Generates a mixed HWC/MGC localization benchmark from the filtered pair file.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
CODE_SELECTION_DIR="${PROJECT_ROOT}/code-selection"
LOG_DIR="${PROJECT_ROOT}/logs"
OUTPUT_ROOT="${PROJECT_ROOT}/output"
DATASET_NAME="CodeSearchNet"

# GEN_MODEL="CodeLlama-7b-hf"     # CodeLlama reproduction
GEN_MODEL="starcoder2-7b"         # Current: StarCoder2 experiment

# GEN_MAX_NUM="2000"              # CodeLlama generation pool
GEN_MAX_NUM="3000"                # Current: StarCoder2 generation pool

# N_FILTERED="530"                # CodeLlama valid pairs after filtering
N_FILTERED="638"                  # Current: StarCoder2 valid pairs after filtering

GEN_TEMPERATURE="0.2"
DATASET_KEY="${GEN_MODEL}-${GEN_MAX_NUM}-tp${GEN_TEMPERATURE}"
OUTPUT_DIR="${OUTPUT_ROOT}/${DATASET_NAME}/${DATASET_KEY}"

# --- Benchmark identity ---
COMPLEXITY="level1"                 # benchmark difficulty; later: level2, level3, ...
                                    # level1 = prompt + HWC + MGC concatenation
# --- Inputs / outputs ---
INPUT_JSONL="${OUTPUT_DIR}/outputs_${N_FILTERED}_filter.jsonl"
BENCHMARK_OUT_JSONL="${OUTPUT_DIR}/outputs_${N_FILTERED}_benchmark_${COMPLEXITY}.jsonl"

# --- Script ---
GEN_BENCH_SCRIPT="${CODE_SELECTION_DIR}/generate_benchmark.py"
# --- Logging ---
TIMESTAMP=$(date +%m-%d_%H:%M)        # captured at script start
LOG_FILE="${LOG_DIR}/generate_benchmark_${COMPLEXITY}_${TIMESTAMP}.log"
echo "=== Benchmark generation configuration ==="
echo "  COMPLEXITY:    ${COMPLEXITY}"
echo "  INPUT_JSONL:   ${INPUT_JSONL/${PROJECT_ROOT}/PRJ}"
echo "  BENCHMARK_OUT: ${BENCHMARK_OUT_JSONL/${PROJECT_ROOT}/PRJ}"
echo "  LOG_FILE:      ${LOG_FILE/${PROJECT_ROOT}/PRJ}"
echo "=========================================="
echo ""

python "${GEN_BENCH_SCRIPT}" \
    --complexity "${COMPLEXITY}" \
    --input_jsonl "${INPUT_JSONL}" \
    --out_jsonl "${BENCHMARK_OUT_JSONL}" \
    --project_root "${PROJECT_ROOT}" \
    2>&1 | tee "${LOG_FILE}"

# Verify output
if [[ -f "${BENCHMARK_OUT_JSONL}" ]]; then
    n_records=$(wc -l < "${BENCHMARK_OUT_JSONL}")
    echo ""
    echo "[OK] Benchmark written: ${BENCHMARK_OUT_JSONL/${PROJECT_ROOT}/PRJ}"
    echo "  ${n_records} records"
else
    echo ""
    echo "[ERROR] Expected output file was not created:"
    echo "  ${BENCHMARK_OUT_JSONL}"
    exit 1
fi