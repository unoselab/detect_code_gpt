#!/bin/bash
#
# NPR cross-generator evaluation wrapper.
#
# Development filenames use a version suffix. Before running on the server,
# remove "-v1" from both filenames:
#   proc_sh/run-1c0c-score-npr-cross-generator.sh
#   code-detection/score_npr_cross_generator.py
#
# PURPOSE
#   Evaluate one cell of a 5 x 5 NPR cross-generator matrix while keeping the
#   original overlap-window NPR scoring logic unchanged.
#
# INPUTS
#   TARGET_SOURCE      Short benchmark generation-source key.
#   SCORING_MODEL_KEY  Short NPR scoring-model key.
#   SCORING_MODEL_NAME Optional Hugging Face model override.
#   CUDA_DEVICE        CUDA_VISIBLE_DEVICES value. Default: 0.
#   BENCHMARK_ROOT     Optional benchmark-root override.
#   OUTPUT_NAME        Optional output-name override.
#
# SUPPORTED KEYS
#   codellama-7b
#   starcoder2-7b
#   starcoder2-15b-instruct-v0.1
#   gpt-oss
#   gemma
#
# OUTPUTS
#   Per-procedure NPR CSV
#   Per-window NPR CSV
#   Per-bucket summary CSV
#   Overall one-row summary CSV
#   Pickle cache of per-procedure window results
#   Execution log
#
# EXAMPLES
#   Cross-generator cell: SC2-7B scorer -> CodeLlama-generated benchmark
#   TARGET_SOURCE=codellama-7b SCORING_MODEL_KEY=starcoder2-7b CUDA_DEVICE=0 \
#     bash proc_sh/run-1c0c-score-npr-cross-generator.sh
#
#   Diagonal reproduction cell: SC2-7B scorer -> SC2-7B-generated benchmark
#   TARGET_SOURCE=starcoder2-7b SCORING_MODEL_KEY=starcoder2-7b CUDA_DEVICE=0 \
#     bash proc_sh/run-1c0c-score-npr-cross-generator.sh
#
#   GPT-OSS scorer normally requires the environment used for GPT-OSS scoring.
#   TARGET_SOURCE=codellama-7b SCORING_MODEL_KEY=gpt-oss CUDA_DEVICE=0,1,2 \
#     bash proc_sh/run-1c0c-score-npr-cross-generator.sh
#
#   Gemma scorer normally requires the environment used for Gemma scoring.
#   TARGET_SOURCE=starcoder2-7b SCORING_MODEL_KEY=gemma CUDA_DEVICE=0,1,2 \
#     bash proc_sh/run-1c0c-score-npr-cross-generator.sh
#

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
PYTHON_SCRIPT="${PROJECT_ROOT}/code-detection/score_npr_cross_generator.py"
LOG_DIR="${PROJECT_ROOT}/logs/run-1c0c"
OUTPUT_ROOT="${PROJECT_ROOT}/output/commit_function/run-1c0c/npr-cross-generator-v1"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
START_EPOCH="$(date +%s)"
STARTED="$(date)"

TARGET_SOURCE="${TARGET_SOURCE:-starcoder2-7b}"
SCORING_MODEL_KEY="${SCORING_MODEL_KEY:-starcoder2-7b}"
CUDA_DEVICE="${CUDA_DEVICE:-0}"

model_name_for_key() {
  case "$1" in
    codellama-7b)
      printf '%s\n' 'codellama/CodeLlama-7b-hf'
      ;;
    starcoder2-7b)
      printf '%s\n' 'bigcode/starcoder2-7b'
      ;;
    starcoder2-15b-instruct-v0.1)
      printf '%s\n' 'bigcode/starcoder2-15b-instruct-v0.1'
      ;;
    gpt-oss)
      printf '%s\n' 'openai/gpt-oss-120b'
      ;;
    gemma)
      printf '%s\n' 'google/gemma-4-31B-it'
      ;;
    *)
      echo "ERROR: unsupported SCORING_MODEL_KEY: $1" >&2
      exit 2
      ;;
  esac
}

validate_source_key() {
  case "$1" in
    codellama-7b|starcoder2-7b|starcoder2-15b-instruct-v0.1|gpt-oss|gemma)
      ;;
    *)
      echo "ERROR: unsupported TARGET_SOURCE: $1" >&2
      exit 2
      ;;
  esac
}

validate_source_key "${TARGET_SOURCE}"
DEFAULT_SCORING_MODEL_NAME="$(model_name_for_key "${SCORING_MODEL_KEY}")"
SCORING_MODEL_NAME="${SCORING_MODEL_NAME:-${DEFAULT_SCORING_MODEL_NAME}}"
BENCHMARK_ROOT="${BENCHMARK_ROOT:-${PROJECT_ROOT}/code-selection/mixedcode_benchmarks/${TARGET_SOURCE}}"
OUTPUT_NAME="${OUTPUT_NAME:-npr-xgen_score-${SCORING_MODEL_KEY}_target-${TARGET_SOURCE}}"
LOG_FILE="${LOG_DIR}/run-1c0c-${OUTPUT_NAME}-${TIMESTAMP}.log"
RESULTS_CACHE="${OUTPUT_ROOT}/results_cache_${OUTPUT_NAME}.pkl"
OUTPUT_CSV="${OUTPUT_ROOT}/npr_scores_${OUTPUT_NAME}.csv"
CHUNK_CSV="${OUTPUT_ROOT}/npr_chunks_${OUTPUT_NAME}.csv"

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"
mkdir -p "${LOG_DIR}" "${OUTPUT_ROOT}"

{
  echo "============================================================================"
  echo "run-1c0c: NPR cross-generator evaluation"
  echo "Started:                         ${STARTED}"
  echo "Workspace:                       ${PROJECT_ROOT}"
  echo "Active conda env:                ${CONDA_DEFAULT_ENV:-unknown}"
  echo "Python path:                     $(command -v "${PYTHON_BIN}")"
  echo "Python version:                  $("${PYTHON_BIN}" --version 2>&1)"
  echo "Python script:                   ${PYTHON_SCRIPT}"
  echo "Python script SHA:               $(sha256sum "${PYTHON_SCRIPT}" | awk '{print $1}')"
  echo "Target generation source:        ${TARGET_SOURCE}"
  echo "Benchmark root:                  ${BENCHMARK_ROOT}"
  echo "Benchmark JSON files:            $(find "${BENCHMARK_ROOT}" -name 'mixed_code_*.json' | wc -l)"
  echo "Benchmark Python files:          $(find "${BENCHMARK_ROOT}" -name 'mixed_code_*.py' | wc -l)"
  echo "NPR scoring-model key:           ${SCORING_MODEL_KEY}"
  echo "NPR scoring model:               ${SCORING_MODEL_NAME}"
  echo "CUDA_VISIBLE_DEVICES:            ${CUDA_VISIBLE_DEVICES}"
  echo "Algorithm:                       overlap_final_full_window_valid_frontier_weighting-v1"
  echo "Partial-body policy:             any_valid_window_partial_success_full_windows-v2"
  echo "Window size:                     128"
  echo "Perturbations/window:            50"
  echo "Random seed:                     20260723"
  echo "Output directory:                ${OUTPUT_ROOT}"
  echo "Results cache:                   ${RESULTS_CACHE}"
  echo "Procedure score CSV:             ${OUTPUT_CSV}"
  echo "Window score CSV:                ${CHUNK_CSV}"
  echo "Log file:                        ${LOG_FILE}"
  echo "============================================================================"

  test -f "${PYTHON_SCRIPT}"
  test -d "${BENCHMARK_ROOT}"

  cd "${PROJECT_ROOT}/code-detection"

  echo "[STEP 1] Count-only benchmark validation"
  "${PYTHON_BIN}" -u "${PYTHON_SCRIPT}" \
    --target_source "${TARGET_SOURCE}" \
    --scoring_model_key "${SCORING_MODEL_KEY}" \
    --benchmark_root "${BENCHMARK_ROOT}" \
    --base_model_name "${SCORING_MODEL_NAME}" \
    --count_only

  echo "[STEP 2] Full 300-procedure overlap benchmark"
  "${PYTHON_BIN}" -u "${PYTHON_SCRIPT}" \
    --target_source "${TARGET_SOURCE}" \
    --scoring_model_key "${SCORING_MODEL_KEY}" \
    --benchmark_root "${BENCHMARK_ROOT}" \
    --base_model_name "${SCORING_MODEL_NAME}" \
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
