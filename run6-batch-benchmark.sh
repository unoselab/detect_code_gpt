#!/bin/bash
# Run DetectCodeGPT across the level1 benchmark JSONL, scoring 128-token chunks
# and measuring positional MGC overlap. Outputs per-chunk CSV + pickle cache.

set -euo pipefail

# =====================================================================
# Configuration
# =====================================================================

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
OUTPUT_ROOT="${PROJECT_ROOT}/output"

CUDA_DEVICE=0
DATASET_NAME="CodeSearchNet"

# GEN_MODEL="CodeLlama-7b-hf"     # Historical: CodeLlama reproduction
GEN_MODEL="starcoder2-7b"         # Current: StarCoder2 experiment

# GEN_MAX_NUM="2000"              # Historical: CodeLlama generation pool
GEN_MAX_NUM="3000"                # Current: StarCoder2 generation pool

GEN_TEMPERATURE="0.2"

# N_FILTERED="530"                # Historical: CodeLlama valid pairs after filtering
N_FILTERED="638"                  # Current: StarCoder2 valid pairs after filtering

DATASET_KEY="${GEN_MODEL}-${GEN_MAX_NUM}-tp${GEN_TEMPERATURE}"
COMPLEXITY="level1"

# BASE_MODEL_NAME="codellama/CodeLlama-7b-hf"  # Historical: CodeLlama scorer
BASE_MODEL_NAME="bigcode/starcoder2-7b"        # Current: StarCoder2 scorer

N_PERTURBATIONS=50
MAX_LEN=128

# THRESHOLD_YOUDEN=1.3875     # CodeLlama
# THRESHOLD_HIGH=1.60         # CodeLlama
# StarCoder2 classification Youden threshold from n=638 run.
# Final localization threshold should still be selected by threshold sweep later.
THRESHOLD_YOUDEN=1.6390
THRESHOLD_HIGH=1.80

LOAD_CACHED=""  # Set to a pickle path to skip scoring

DATA_DIR="${OUTPUT_ROOT}/${DATASET_NAME}/${DATASET_KEY}"
BENCHMARK_JSONL="${DATA_DIR}/outputs_${N_FILTERED}_benchmark_${COMPLEXITY}.jsonl"
OUTPUTS_TXT="${DATA_DIR}/outputs.txt"

OUTPUT_NAME="benchmark_${COMPLEXITY}_${GEN_MODEL,,}"
TIMESTAMP=$(date +%m-%d_%H:%M)
LOG_FILE="${LOG_DIR}/${OUTPUT_NAME}_${TIMESTAMP}.log"

# =====================================================================
# Pre-flight
# =====================================================================

echo "=== Batch benchmark configuration ==="
echo "  BENCHMARK_JSONL:  ${BENCHMARK_JSONL/${PROJECT_ROOT}/PRJ}"
echo "  OUTPUTS_TXT:      ${OUTPUTS_TXT/${PROJECT_ROOT}/PRJ}"
echo "  BASE_MODEL:       ${BASE_MODEL_NAME}"
echo "  N_PERTURBATIONS:  ${N_PERTURBATIONS}"
echo "  MAX_LEN:          ${MAX_LEN}"
echo "  THRESHOLD_YOUDEN: ${THRESHOLD_YOUDEN}"
echo "  THRESHOLD_HIGH:   ${THRESHOLD_HIGH}"
echo "  CUDA_DEVICE:      ${CUDA_DEVICE}"
echo "  OUTPUT_NAME:      ${OUTPUT_NAME}"
echo "  LOG_FILE:         ${LOG_FILE/${PROJECT_ROOT}/PRJ}"
[[ -n "${LOAD_CACHED}" ]] && echo "  LOAD_CACHED:      ${LOAD_CACHED/${PROJECT_ROOT}/PRJ}"
echo "====================================="
echo ""

for required_file in "${BENCHMARK_JSONL}" "${OUTPUTS_TXT}"; do
    if [[ ! -f "${required_file}" ]]; then
        echo "ERROR: required file not found:"
        echo "  ${required_file}"
        exit 1
    fi
done

cd "${PROJECT_ROOT}"
mkdir -p "${LOG_DIR}"
cd code-detection

export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"

LOAD_FLAG=""
if [[ -n "${LOAD_CACHED}" ]]; then
    LOAD_FLAG="--load_benchmark_results ${LOAD_CACHED}"
fi

python main.py \
    --batch_benchmark \
    --benchmark_jsonl "${BENCHMARK_JSONL}" \
    --outputs_txt_path "${OUTPUTS_TXT}" \
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