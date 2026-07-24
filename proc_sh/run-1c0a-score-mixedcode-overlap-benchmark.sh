#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
PYTHON_SCRIPT="${PROJECT_ROOT}/code-detection/main_mixedcode_benchmark_overlap.py"
LOG_DIR="${PROJECT_ROOT}/logs/run-1c0a"
OUTPUT_ROOT="${PROJECT_ROOT}/output/commit_function/run-1c0a/mixedcode-overlap-v1"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
START_EPOCH="$(date +%s)"
STARTED="$(date)"

CUDA_DEVICE="${CUDA_DEVICE:-0}"
GEN_MODEL="${GEN_MODEL:-starcoder2-7b}"
BASE_MODEL_NAME="${BASE_MODEL_NAME:-bigcode/starcoder2-7b}"
BENCHMARK_ROOT="${BENCHMARK_ROOT:-${PROJECT_ROOT}/code-selection/mixedcode_benchmarks/${GEN_MODEL}}"
OUTPUT_NAME="${OUTPUT_NAME:-mixedcode_${GEN_MODEL}_50files_overlap-v1}"
LOG_FILE="${LOG_DIR}/run-1c0a-${OUTPUT_NAME}-${TIMESTAMP}.log"
RESULTS_CACHE="${OUTPUT_ROOT}/results_cache_main_mixedcode_benchmark_${OUTPUT_NAME}.pkl"
OUTPUT_CSV="${OUTPUT_ROOT}/npr_scores_main_mixedcode_benchmark_${OUTPUT_NAME}.csv"
CHUNK_CSV="${OUTPUT_ROOT}/npr_chunks_main_mixedcode_benchmark_${OUTPUT_NAME}.csv"

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"
mkdir -p "${LOG_DIR}" "${OUTPUT_ROOT}"

{
  echo "============================================================================"
  echo "run-1c0a: Table 2 mixed-code overlap-window benchmark"
  echo "Started:                         ${STARTED}"
  echo "Workspace:                       ${PROJECT_ROOT}"
  echo "Active conda env:                ${CONDA_DEFAULT_ENV:-unknown}"
  echo "Python path:                     $(command -v "${PYTHON_BIN}")"
  echo "Python version:                  $("${PYTHON_BIN}" --version 2>&1)"
  echo "Python script:                   ${PYTHON_SCRIPT}"
  echo "Python script SHA:               $(sha256sum "${PYTHON_SCRIPT}" | awk '{print $1}')"
  echo "Benchmark root:                  ${BENCHMARK_ROOT}"
  echo "Benchmark JSON files:            $(find "${BENCHMARK_ROOT}" -name 'mixed_code_*.json' | wc -l)"
  echo "Benchmark Python files:          $(find "${BENCHMARK_ROOT}" -name 'mixed_code_*.py' | wc -l)"
  echo "Base model:                      ${BASE_MODEL_NAME}"
  echo "CUDA_VISIBLE_DEVICES:            ${CUDA_VISIBLE_DEVICES}"
  echo "PYTHONUNBUFFERED:                ${PYTHONUNBUFFERED}"
  echo "Algorithm:                       overlap_final_full_window_valid_frontier_weighting-v1"
  echo "Partial-body policy:             any_valid_window_partial_success_full_windows-v2"
  echo "Window size:                     128"
  echo "Perturbations/window:            50"
  echo "Random seed:                     20260723"
  echo "Output directory:                ${OUTPUT_ROOT}"
  echo "Results cache:                   ${RESULTS_CACHE}"
  echo "Function score CSV:              ${OUTPUT_CSV}"
  echo "Window score CSV:                ${CHUNK_CSV}"
  echo "Log file:                        ${LOG_FILE}"
  echo "============================================================================"

  test -f "${PYTHON_SCRIPT}"
  test -d "${BENCHMARK_ROOT}"

  cd "${PROJECT_ROOT}/code-detection"

  echo "[STEP 1] Count-only benchmark validation"
  "${PYTHON_BIN}" -u "${PYTHON_SCRIPT}" \
    --benchmark_root "${BENCHMARK_ROOT}" \
    --count_only

  echo "[STEP 2] Full 300-body overlap benchmark"
  "${PYTHON_BIN}" -u "${PYTHON_SCRIPT}" \
    --benchmark_root "${BENCHMARK_ROOT}" \
    --base_model_name "${BASE_MODEL_NAME}" \
    --output_name "${OUTPUT_NAME}" \
    --output_csv "${OUTPUT_CSV}" \
    --chunk_csv "${CHUNK_CSV}" \
    --results_cache "${RESULTS_CACHE}" \
    --chunk_len 128 \
    --n_perturbation 50 \
    --random_seed 20260723 \
    --aggregate weighted_mean

  END_EPOCH="$(date +%s)"
  echo "============================================================================"
  echo "Completed:                       $(date)"
  echo "Elapsed seconds:                 $((END_EPOCH - START_EPOCH))"
  echo "Status:                          PASS"
  echo "============================================================================"
} 2>&1 | tee "${LOG_FILE}"
