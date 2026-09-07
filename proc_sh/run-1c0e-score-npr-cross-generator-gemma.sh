#!/bin/bash
#
# NPR cross-generator Gemma scorer-row wrapper for Server 173, run-1c0e (revision v2).
#
# This wrapper is a standalone Server-173 adaptation of the existing run-1c0d
# row-scoring wrapper. It does not call or depend on that shell script. It reuses
# the existing Python scorer so the NPR measurement logic remains unchanged.
#
# PURPOSE
#   Run the final cross-generator scorer row with Gemma-4-31B on Server 173.
#   The Python process loads Gemma once across the two visible RTX 6000 Ada GPUs
#   and reuses the loaded model for all five target-generation benchmarks.
#
# PRIMARY INPUTS
#   SCORING_MODEL_KEY  Scoring-model key. Default: gemma.
#   TARGET_SOURCES     "all" or comma-separated generation-source keys.
#                      Default: all five benchmark sources.
#   CUDA_DEVICE        CUDA_VISIBLE_DEVICES value. Default: 0,1.
#
# OPTIONAL INPUTS
#   SCORING_MODEL_NAME Hugging Face model override.
#                      Default for gemma: google/gemma-4-31B-it.
#   BENCHMARK_PARENT   Parent directory containing one benchmark directory per
#                      generation source.
#   OUTPUT_ROOT        Output directory override.
#   PYTHON_BIN         Python executable. Default: python.
#   CHUNK_SIZE         perturb_texts batch size. Default: 10.
#   N_PERTURBATION     Perturbed variants per overlap window. Default: 50.
#   RANDOM_SEED        Deterministic experiment seed. Default: 20260723.
#   SKIP_EXISTING      1 to skip fully completed target cells; 0 to rerun.
#                      Default: 1.
#   COUNT_ONLY         1 to validate all benchmark counts without loading Gemma.
#                      Default: 0.
#
# PYTHON INPUT
#   code-detection/score_npr_cross_generator_3gpu.py
#   Despite the historical filename, this Python implementation is not hard-coded
#   to three GPUs. GPU visibility is supplied by CUDA_VISIBLE_DEVICES, while the
#   existing DetectCodeGPT model loader determines placement from visible GPUs.
#
# OUTPUTS
#   Root: output/commit_function/run-1c0e/npr-cross-generator-v1
#   For each target source:
#     - per-procedure NPR CSV
#     - per-window NPR CSV
#     - per-bucket summary CSV
#     - one-row overall summary CSV
#     - pickle cache of per-procedure window results
#   For the Gemma scorer row:
#     - npr_xgen_row_summary_score-gemma.csv
#   Log:
#     - logs/run-1c0e/run-1c0e-npr-xgen-row_score-gemma-<timestamp>.log
#
# SERVER 173 PRODUCTION COMMAND
#   bash proc_sh/run-1c0e-score-npr-cross-generator-gemma.sh
#
# Equivalent explicit invocation:
#   SCORING_MODEL_KEY=gemma CUDA_DEVICE=0,1 TARGET_SOURCES=all \
#     bash proc_sh/run-1c0e-score-npr-cross-generator-gemma.sh
#

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
PYTHON_SCRIPT="${PROJECT_ROOT}/code-detection/score_npr_cross_generator_3gpu.py"
LOG_DIR="${PROJECT_ROOT}/logs/run-1c0e"
OUTPUT_ROOT="${OUTPUT_ROOT:-${PROJECT_ROOT}/output/commit_function/run-1c0e/npr-cross-generator-v1}"
BENCHMARK_PARENT="${BENCHMARK_PARENT:-${PROJECT_ROOT}/code-selection/mixedcode_benchmarks}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
START_EPOCH="$(date +%s)"
STARTED="$(date)"

# Production defaults for the final scorer row on the two RTX 6000 Ada GPUs.
SCORING_MODEL_KEY="${SCORING_MODEL_KEY:-gemma}"
TARGET_SOURCES="${TARGET_SOURCES:-all}"
CUDA_DEVICE="${CUDA_DEVICE:-0,1}"
CHUNK_SIZE="${CHUNK_SIZE:-10}"
N_PERTURBATION="${N_PERTURBATION:-50}"
RANDOM_SEED="${RANDOM_SEED:-20260723}"
SKIP_EXISTING="${SKIP_EXISTING:-1}"
COUNT_ONLY="${COUNT_ONLY:-0}"

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

DEFAULT_SCORING_MODEL_NAME="$(model_name_for_key "${SCORING_MODEL_KEY}")"
SCORING_MODEL_NAME="${SCORING_MODEL_NAME:-${DEFAULT_SCORING_MODEL_NAME}}"
ROW_NAME="npr-xgen-row_score-${SCORING_MODEL_KEY}"
LOG_FILE="${LOG_DIR}/run-1c0e-${ROW_NAME}-${TIMESTAMP}.log"

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"
mkdir -p "${LOG_DIR}" "${OUTPUT_ROOT}"

PY_ARGS=(
  "${PYTHON_BIN}" -u "${PYTHON_SCRIPT}"
  --scoring_model_key "${SCORING_MODEL_KEY}"
  --target_sources "${TARGET_SOURCES}"
  --benchmark_parent "${BENCHMARK_PARENT}"
  --base_model_name "${SCORING_MODEL_NAME}"
  --output_root "${OUTPUT_ROOT}"
  --chunk_len 128
  --chunk_size "${CHUNK_SIZE}"
  --n_perturbation "${N_PERTURBATION}"
  --random_seed "${RANDOM_SEED}"
  --aggregate weighted_mean
)

if [[ "${SKIP_EXISTING}" == "1" ]]; then
  PY_ARGS+=(--skip_existing)
fi

if [[ "${COUNT_ONLY}" == "1" ]]; then
  PY_ARGS+=(--count_only)
fi

{
  echo "============================================================================"
  echo "run-1c0e v2: NPR cross-generator Gemma scorer-row evaluation on Server 173"
  echo "Started:                         ${STARTED}"
  echo "Workspace:                       ${PROJECT_ROOT}"
  echo "Active conda env:                ${CONDA_DEFAULT_ENV:-unknown}"
  echo "Python path:                     $(command -v "${PYTHON_BIN}")"
  echo "Python version:                  $("${PYTHON_BIN}" --version 2>&1)"
  echo "Python script:                   ${PYTHON_SCRIPT}"
  echo "Python script SHA:               $(sha256sum "${PYTHON_SCRIPT}" | awk '{print $1}')"
  echo "Scoring-model key:               ${SCORING_MODEL_KEY}"
  echo "Scoring model:                   ${SCORING_MODEL_NAME}"
  echo "Target generation sources:       ${TARGET_SOURCES}"
  echo "Benchmark parent:                ${BENCHMARK_PARENT}"
  echo "CUDA_VISIBLE_DEVICES:            ${CUDA_VISIBLE_DEVICES}"
  echo "Host:                            $(hostname)"
  echo "GPU inventory:"
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv,noheader || true
  else
    echo "nvidia-smi unavailable"
  fi
  echo "Algorithm:                       overlap_final_full_window_valid_frontier_weighting-v1"
  echo "Partial-body policy:             any_valid_window_partial_success_full_windows-v2"
  echo "Window size:                     128"
  echo "Perturbations/window:            ${N_PERTURBATION}"
  echo "Perturbation batch size:         ${CHUNK_SIZE}"
  echo "Random seed:                     ${RANDOM_SEED}"
  echo "Skip completed targets:          ${SKIP_EXISTING}"
  echo "Count-only mode:                 ${COUNT_ONLY}"
  echo "Output directory:                ${OUTPUT_ROOT}"
  echo "Row summary:                     ${OUTPUT_ROOT}/npr_xgen_row_summary_score-${SCORING_MODEL_KEY}.csv"
  echo "Log file:                        ${LOG_FILE}"
  echo "============================================================================"

  test -f "${PYTHON_SCRIPT}"
  test -d "${BENCHMARK_PARENT}"

  cd "${PROJECT_ROOT}/code-detection"
  "${PY_ARGS[@]}"

  END_EPOCH="$(date +%s)"
  echo "============================================================================"
  echo "Completed:                       $(date)"
  echo "Elapsed seconds:                 $((END_EPOCH - START_EPOCH))"
  echo "Status:                          PASS"
  echo "============================================================================"
} 2>&1 | tee "${LOG_FILE}"
