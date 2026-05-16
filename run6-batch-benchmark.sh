#!/bin/bash
# Run DetectCodeGPT against the level1 benchmark, producing per-chunk NPR scores.

set -euo pipefail

# =====================================================================
# Configuration
# =====================================================================

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
OUTPUT_ROOT="${PROJECT_ROOT}/output"

CUDA_DEVICE=0
DATASET_NAME="CodeSearchNet"
GEN_MODEL="CodeLlama-7b-hf"
GEN_MAX_NUM="2000"
GEN_TEMPERATURE="0.2"
DATASET_KEY="${GEN_MODEL}-${GEN_MAX_NUM}-tp${GEN_TEMPERATURE}"
COMPLEXITY="level1"

BASE_MODEL_NAME="codellama/CodeLlama-7b-hf"
N_PERTURBATIONS=50
MAX_LEN=128
THRESHOLD_YOUDEN=1.3875
THRESHOLD_HIGH=1.60

# Toggle: set to a pickle path to skip scoring and just regenerate CSV/metrics
LOAD_CACHED=""

BENCHMARK_JSONL="${OUTPUT_ROOT}/${DATASET_NAME}/${DATASET_KEY}/outputs_530_benchmark_${COMPLEXITY}.jsonl"
OUTPUT_NAME="benchmark_${COMPLEXITY}_${GEN_MODEL,,}"
TIMESTAMP=$(date +%m-%d_%H:%M)
LOG_FILE="${LOG_DIR}/${OUTPUT_NAME}_${TIMESTAMP}.log"

# =====================================================================
# Pre-flight
# =====================================================================

echo "=== Batch benchmark configuration ==="
echo "  BENCHMARK_JSONL:  ${BENCHMARK_JSONL/${PROJECT_ROOT}/PRJ}"
echo "  BASE_MODEL:       ${BASE_MODEL_NAME}"
echo "  N_PERTURBATIONS:  ${N_PERTURBATIONS}"
echo "  MAX_LEN:          ${MAX_LEN}"
echo "  CUDA_DEVICE:      ${CUDA_DEVICE}"
echo "  OUTPUT_NAME:      ${OUTPUT_NAME}"
echo "  LOG_FILE:         ${LOG_FILE/${PROJECT_ROOT}/PRJ}"
[[ -n "${LOAD_CACHED}" ]] && echo "  LOAD_CACHED:      ${LOAD_CACHED}"
echo "===================================="
echo ""

if [[ ! -f "${BENCHMARK_JSONL}" ]]; then
    echo "ERROR: benchmark JSONL not found:"
    echo "  ${BENCHMARK_JSONL}"
    exit 1
fi

cd "${PROJECT_ROOT}"
mkdir -p "${LOG_DIR}"
cd code-detection

export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"

LOAD_FLAG=""
if [[ -n "${LOAD_CACHED}" ]]; then
    LOAD_FLAG="--load_benchmark_results ${LOAD_CACHED}"
fi

# Quick way: head the benchmark JSONL to a temp file
head -10 "${BENCHMARK_JSONL}" > ~/Desktop/benchmark_test.jsonl
# Then run with --benchmark_jsonl /tmp/benchmark_test.jsonl
# --benchmark_jsonl "${BENCHMARK_JSONL}" \

python main.py \
    --batch_benchmark \
    --benchmark_jsonl "/home/user1-system12/Desktop/benchmark_test.jsonl" \
    --base_model_name "${BASE_MODEL_NAME}" \
    --n_perturbation_list "${N_PERTURBATIONS}" \
    --max_len "${MAX_LEN}" \
    --threshold "${THRESHOLD_HIGH}" \
    --threshold_youden "${THRESHOLD_YOUDEN}" \
    --output_name "${OUTPUT_NAME}" \
    --pct_words_masked 0.5 \
    --pct_identifiers_masked 0.75 \
    --span_length 2 \
    --batch_size 50 \
    --chunk_size 10 \
    --baselines "LRR,DetectGPT,NPR" \
    --perturb_type "random-insert-space+newline" \
    ${LOAD_FLAG} \
    2>&1 | tee "${LOG_FILE}"