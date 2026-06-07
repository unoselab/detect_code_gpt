#!/bin/bash

set -euo pipefail

# =====================================================================
# Configuration
# =====================================================================

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
OUTPUT_ROOT="${PROJECT_ROOT}/output"
TIMESTAMP=$(date +%m-%d_%H-%M)

CUDA_DEVICE="${CUDA_DEVICE:-0}"
DATASET_NAME="${DATASET_NAME:-CodeSearchNet}"
GEN_MODEL="${GEN_MODEL:-starcoder2-7b}"
BASE_MODEL_NAME="${BASE_MODEL_NAME:-bigcode/starcoder2-7b}"
OUTPUT_NAME="${OUTPUT_NAME:-mixedcode_${GEN_MODEL}_count_only}"

LOG_FILE="${LOG_DIR}/${OUTPUT_NAME}_${TIMESTAMP}.log"

BENCHMARK_ROOT="../code-selection/mixedcode_benchmarks/${GEN_MODEL}"

mkdir -p "${LOG_DIR}" "${OUTPUT_ROOT}"

{
  echo "=== Mixed-code benchmark detection configuration ==="
  echo "  PROJECT_ROOT:      ${PROJECT_ROOT}"
  echo "  LOG_DIR:           ${LOG_DIR}"
  echo "  OUTPUT_ROOT:       ${OUTPUT_ROOT}"
  echo "  DATASET_NAME:      ${DATASET_NAME}"
  echo "  GEN_MODEL:         ${GEN_MODEL}"
  echo "  BASE_MODEL_NAME:   ${BASE_MODEL_NAME}"
  echo "  CUDA_DEVICE:       ${CUDA_DEVICE}"
  echo "  OUTPUT_NAME:       ${OUTPUT_NAME}"
  echo "  LOG_FILE:          ${LOG_FILE}"
  echo "  BENCHMARK_ROOT:    ${BENCHMARK_ROOT}"
  echo "==============================================="
  echo ""

  cd "${PROJECT_ROOT}/code-detection"

  echo "[CHECK] Current directory:"
  pwd
  echo ""

  echo "[CHECK] main_mixedcode_benchmark.py:"
  test -f main_mixedcode_benchmark.py || { echo "Missing main_mixedcode_benchmark.py"; exit 1; }
  ls -lh main_mixedcode_benchmark.py
  echo ""

  echo "[CHECK] Benchmark root:"
  test -d "${BENCHMARK_ROOT}" || { echo "Missing benchmark root: ${BENCHMARK_ROOT}"; exit 1; }
  find "${BENCHMARK_ROOT}" -name "mixed_code_*.py" | wc -l
  find "${BENCHMARK_ROOT}" -name "mixed_code_*.json" | wc -l
  echo ""

#   echo "=== FIRST DO A COUNT-ONLY CHECK ==="
#   echo "[RUN] python main_mixedcode_benchmark.py \\"
#   echo "        --benchmark_root \"${BENCHMARK_ROOT}\" \\"
#   echo "        --count_only"
#   echo ""

#   python main_mixedcode_benchmark.py \
#     --benchmark_root "${BENCHMARK_ROOT}" \
#     --count_only

#   ## SMALL SMOKE
#   echo ""
#   echo "=== SMALL SMOKE RUN ==="
#   echo "[RUN] CUDA_VISIBLE_DEVICES=${CUDA_DEVICE} python main_mixedcode_benchmark.py \\"
#   echo "        --benchmark_root \"${BENCHMARK_ROOT}\" \\"
#   echo "        --base_model_name \"${BASE_MODEL_NAME}\" \\"
#   echo "        --output_name mixedcode_${GEN_MODEL}_smoke \\"
#   echo "        --limit_functions 6 \\"
#   echo "        --preview"
#   echo ""
  
#   CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}" python main_mixedcode_benchmark.py \
#     --benchmark_root "${BENCHMARK_ROOT}" \
#     --base_model_name "${BASE_MODEL_NAME}" \
#     --output_name "mixedcode_${GEN_MODEL}_smoke" \
#     --limit_functions 6 \
#     --preview

  ## FULL RUN
  echo ""
  echo "=== FULL RUN ==="
  echo "[RUN] CUDA_VISIBLE_DEVICES=${CUDA_DEVICE} python main_mixedcode_benchmark.py \\"
  echo "        --benchmark_root \"${BENCHMARK_ROOT}\" \\"
  echo "        --base_model_name \"${BASE_MODEL_NAME}\" \\"
  echo "        --output_name mixedcode_${GEN_MODEL}_50files"
  echo ""
  
  CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}" python main_mixedcode_benchmark.py \
    --benchmark_root "${BENCHMARK_ROOT}" \
    --base_model_name "${BASE_MODEL_NAME}" \
    --output_name "mixedcode_${GEN_MODEL}_50files"

} 2>&1 | tee "${LOG_FILE}"