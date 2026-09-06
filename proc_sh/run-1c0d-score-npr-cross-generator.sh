#!/bin/bash
#
# NPR cross-generator evaluation wrapper for r158, run-1c0d (revision v1).
#
# Server filenames for this r158 branch are intentionally conflict-free:
#   proc_sh/run-1c0d-score-npr-cross-generator.sh
#   code-detection/score_npr_cross_generator_3gpu.py
# The ZIP filename carries the revision suffix (v1); server filenames remain stable.
#
# PURPOSE
#   Evaluate one NPR scoring-model row across multiple AGC generation sources.
#   The Python process loads the scoring model once and reuses it across all
#   requested target benchmarks. This changes execution orchestration only;
#   NPR scoring definitions remain the same as the original run-1c0a design. The run-1c0d branch is isolated from the 173-side run-1c0c branch to avoid merge conflicts.
#
# REQUIRED / PRIMARY INPUTS
#   SCORING_MODEL_KEY  NPR scoring-model key. Default: starcoder2-7b.
#   TARGET_SOURCES     "all" or comma-separated generation-source keys.
#                      Default: all five benchmark sources.
#   CUDA_DEVICE        CUDA_VISIBLE_DEVICES value. Default: 0.
#
# OPTIONAL INPUTS
#   SCORING_MODEL_NAME Hugging Face model override.
#   BENCHMARK_PARENT   Parent containing one benchmark directory per source.
#   OUTPUT_ROOT        Output directory override.
#   PYTHON_BIN         Python executable. Default: python.
#   CHUNK_SIZE         perturb_texts batch size. Default: 10.
#   N_PERTURBATION     Perturbed variants per overlap window. Default: 50.
#   RANDOM_SEED        Deterministic experiment seed. Default: 20260723.
#   SKIP_EXISTING      1 to skip fully completed target cells; 0 to rerun.
#                      Default: 1.
#   COUNT_ONLY         1 to validate benchmark counts without loading a model.
#                      Default: 0.
#
# SUPPORTED SOURCE / SCORER KEYS
#   codellama-7b
#   starcoder2-7b
#   starcoder2-15b-instruct-v0.1
#   gpt-oss
#   gemma
#
# OUTPUTS
#   For each target source:
#     - per-procedure NPR CSV
#     - per-window NPR CSV
#     - per-bucket summary CSV
#     - one-row overall summary CSV
#     - pickle cache of per-procedure window results
#   For the scoring-model row:
#     - npr_xgen_row_summary_score-<SCORING_MODEL_KEY>.csv
#   One execution log is written for the full scoring-model row.
#
# R158 EXAMPLES
#   Small scorers can use one A6000 each. Large scorers can expose all three GPUs.
#   CUDA_DEVICE only controls visibility; model-loading behavior remains the existing
#   DetectCodeGPT implementation so the NPR definition is unchanged.
#   SC2-7B scorer on GPU 0, all five targets:
#     SCORING_MODEL_KEY=starcoder2-7b CUDA_DEVICE=0 \
#       bash proc_sh/run-1c0d-score-npr-cross-generator.sh
#
#   CodeLlama-7B scorer on GPU 1, all five targets:
#     SCORING_MODEL_KEY=codellama-7b CUDA_DEVICE=1 \
#       bash proc_sh/run-1c0d-score-npr-cross-generator.sh
#
#   SC2-15B scorer on GPU 2, all five targets:
#     SCORING_MODEL_KEY=starcoder2-15b-instruct-v0.1 CUDA_DEVICE=2 \
#       bash proc_sh/run-1c0d-score-npr-cross-generator.sh
#
#   GPT-OSS or Gemma using all three visible GPUs, after the smaller rows finish:
#     SCORING_MODEL_KEY=gpt-oss CUDA_DEVICE=0,1,2 \
#       bash proc_sh/run-1c0d-score-npr-cross-generator.sh
#
#     SCORING_MODEL_KEY=gemma CUDA_DEVICE=0,1,2 \
#       bash proc_sh/run-1c0d-score-npr-cross-generator.sh
#

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
PYTHON_SCRIPT="${PROJECT_ROOT}/code-detection/score_npr_cross_generator_3gpu.py"
LOG_DIR="${PROJECT_ROOT}/logs/run-1c0d"
OUTPUT_ROOT="${OUTPUT_ROOT:-${PROJECT_ROOT}/output/commit_function/run-1c0d/npr-cross-generator-v1}"
BENCHMARK_PARENT="${BENCHMARK_PARENT:-${PROJECT_ROOT}/code-selection/mixedcode_benchmarks}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
START_EPOCH="$(date +%s)"
STARTED="$(date)"

SCORING_MODEL_KEY="${SCORING_MODEL_KEY:-starcoder2-7b}"
TARGET_SOURCES="${TARGET_SOURCES:-all}"
CUDA_DEVICE="${CUDA_DEVICE:-0}"
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
LOG_FILE="${LOG_DIR}/run-1c0d-${ROW_NAME}-${TIMESTAMP}.log"

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
  echo "run-1c0d v1: NPR cross-generator scorer-row evaluation on r158"
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
