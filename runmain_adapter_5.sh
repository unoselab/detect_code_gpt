#!/bin/bash
set -euo pipefail

# =============================================================================
# runmain_adapter_5.sh
# -----------------------------------------------------------------------------
# DetectCodeGPT adapter run for the repaired Gemma CodeSearchNet 4500-pair
# complexity-selected dataset.
#
# Based on runmain_adapter_4.sh, but switches from GPT-OSS to Gemma:
#   - generated-data label / directory: gemma
#   - base HF model: google/gemma-4-31B-it
#   - CSV split dir: validsyntax_4500_complexity
#   - CSV file: codesearchnet_gemma_python_merged_4500.csv
#
# Important for Gemma 31B:
#   - loadmodel.py must route Gemma through device_map="auto"
#     and must NOT call base_model.to(cuda) after loading.
#   - this wrapper exposes low-cost smoke-test knobs so you can test model
#     loading and scoring before running the full k=50 job.
#
# Example full run:
#   bash runmain_adapter_5.sh
#
# Example smoke test:
#   LIMIT=50 bash runmain_adapter_5.sh
#
# Lower-cost smoke test after Gemma OOM loader patch:
#   LIMIT=5 N_PERTURBATION=5 CHUNK_SIZE=2 bash runmain_adapter_5.sh
# =============================================================================

PROJECT_ROOT="${PROJECT_ROOT:-${HOME}/project-workspace/detect_code_gpt}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-${HOME}/project-workspace}"
CUDA_DEVICE="${CUDA_DEVICE:-0,1,2}"
DATASET="${DATASET:-CodeSearchNet}"

# NRP managed model name is `gemma`; the corresponding pinned HF model is
# google/gemma-4-31B-it. main_adapter.py should receive the HF model id.
GEN_MODEL="${GEN_MODEL:-gemma}"
GEN_MODEL_HF="${GEN_MODEL_HF:-google/gemma-4-31B-it}"

CSV_ROOT="${CSV_ROOT:-${WORKSPACE_ROOT}/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet}"
CSV_SPLIT_DIR="${CSV_SPLIT_DIR:-validsyntax_4500_complexity}"
CSV_ROOT_SUB="${CSV_ROOT}/${GEN_MODEL}/${CSV_SPLIT_DIR}"
CSV_PATH="${CSV_PATH:-${CSV_ROOT_SUB}/codesearchnet_${GEN_MODEL}_python_merged_4500.csv}"

OUTPUT_NAME="${OUTPUT_NAME:-${GEN_MODEL}_4500_complexity_refreshed}"
LIMIT="${LIMIT:-}"
MIN_CHUNK_TOKENS="${MIN_CHUNK_TOKENS:-}"

# Optional runtime/scoring controls. Defaults preserve main_adapter.py behavior.
N_PERTURBATION="${N_PERTURBATION:-}"
CHUNK_SIZE="${CHUNK_SIZE:-}"
CHUNK_LEN="${CHUNK_LEN:-}"
AGGREGATE="${AGGREGATE:-}"
DEVICE="${DEVICE:-cuda}"
CACHE_DIR="${CACHE_DIR:-${HOME}/.cache/huggingface/hub}"

# Optional output/cache controls.
OUTPUT_CSV="${OUTPUT_CSV:-}"
CHUNK_CSV="${CHUNK_CSV:-}"
RESULTS_CACHE="${RESULTS_CACHE:-}"
LOAD_CACHED_RESULTS="${LOAD_CACHED_RESULTS:-}"

# Fast diagnostic modes supported by main_adapter.py.
PREVIEW="${PREVIEW:-0}"
COUNT_EMPTY_ONLY="${COUNT_EMPTY_ONLY:-0}"
NO_STRIP_BODY="${NO_STRIP_BODY:-0}"

# CUDA memory allocator guard. This helps fragmentation but does not replace
# the required Gemma multi-GPU loader patch in loadmodel.py.
PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"

TIMESTAMP="$(date +%m-%d_%H%M)"
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/main_adapter_${OUTPUT_NAME}_${TIMESTAMP}.log}"

EXTRA_ARGS=()
if [ -n "${LIMIT}" ]; then
  EXTRA_ARGS+=(--limit "${LIMIT}")
fi
if [ -n "${MIN_CHUNK_TOKENS}" ]; then
  EXTRA_ARGS+=(--min_chunk_tokens "${MIN_CHUNK_TOKENS}")
fi
if [ -n "${N_PERTURBATION}" ]; then
  EXTRA_ARGS+=(--n_perturbation "${N_PERTURBATION}")
fi
if [ -n "${CHUNK_SIZE}" ]; then
  EXTRA_ARGS+=(--chunk_size "${CHUNK_SIZE}")
fi
if [ -n "${CHUNK_LEN}" ]; then
  EXTRA_ARGS+=(--chunk_len "${CHUNK_LEN}")
fi
if [ -n "${AGGREGATE}" ]; then
  EXTRA_ARGS+=(--aggregate "${AGGREGATE}")
fi
if [ -n "${OUTPUT_CSV}" ]; then
  EXTRA_ARGS+=(--output_csv "${OUTPUT_CSV}")
fi
if [ -n "${CHUNK_CSV}" ]; then
  EXTRA_ARGS+=(--chunk_csv "${CHUNK_CSV}")
fi
if [ -n "${RESULTS_CACHE}" ]; then
  EXTRA_ARGS+=(--results_cache "${RESULTS_CACHE}")
fi
if [ -n "${LOAD_CACHED_RESULTS}" ]; then
  EXTRA_ARGS+=(--load_cached_results "${LOAD_CACHED_RESULTS}")
fi
if [ "${PREVIEW}" = "1" ]; then
  EXTRA_ARGS+=(--preview)
fi
if [ "${COUNT_EMPTY_ONLY}" = "1" ]; then
  EXTRA_ARGS+=(--count_empty_only)
fi
if [ "${NO_STRIP_BODY}" = "1" ]; then
  EXTRA_ARGS+=(--no-strip_body)
fi

mkdir -p "${LOG_DIR}"

{
  echo "=== Detection run configuration ==="
  echo "  DATASET:                ${DATASET}"
  echo "  GEN_MODEL:              ${GEN_MODEL}"
  echo "  GEN_MODEL_HF:           ${GEN_MODEL_HF}"
  echo "  CUDA_DEVICE:            ${CUDA_DEVICE}"
  echo "  DEVICE:                 ${DEVICE}"
  echo "  CSV_SPLIT_DIR:          ${CSV_SPLIT_DIR}"
  echo "  CSV_PATH:               ${CSV_PATH}"
  echo "  OUTPUT_NAME:            ${OUTPUT_NAME}"
  echo "  LIMIT:                  ${LIMIT:-<none>}"
  echo "  N_PERTURBATION:         ${N_PERTURBATION:-<default>}"
  echo "  CHUNK_SIZE:             ${CHUNK_SIZE:-<default>}"
  echo "  CHUNK_LEN:              ${CHUNK_LEN:-<default>}"
  echo "  MIN_CHUNK_TOKENS:       ${MIN_CHUNK_TOKENS:-<default>}"
  echo "  AGGREGATE:              ${AGGREGATE:-<default>}"
  echo "  PREVIEW:                ${PREVIEW}"
  echo "  COUNT_EMPTY_ONLY:       ${COUNT_EMPTY_ONLY}"
  echo "  NO_STRIP_BODY:          ${NO_STRIP_BODY}"
  echo "  CACHE_DIR:              ${CACHE_DIR}"
  echo "  PYTORCH_CUDA_ALLOC_CONF:${PYTORCH_CUDA_ALLOC_CONF}"
  echo "  LOG_FILE:               ${LOG_FILE}"
  echo "===================================="
  echo ""
} | tee "${LOG_FILE}"

test -d "${PROJECT_ROOT}/code-detection" || { echo "Missing code-detection dir: ${PROJECT_ROOT}/code-detection" | tee -a "${LOG_FILE}"; exit 1; }
test -f "${PROJECT_ROOT}/code-detection/main_adapter.py" || { echo "Missing main_adapter.py: ${PROJECT_ROOT}/code-detection/main_adapter.py" | tee -a "${LOG_FILE}"; exit 1; }
test -f "${CSV_PATH}" || { echo "Missing CSV: ${CSV_PATH}" | tee -a "${LOG_FILE}"; exit 1; }

cd "${PROJECT_ROOT}/code-detection"
export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"
export PYTORCH_CUDA_ALLOC_CONF
export TOKENIZERS_PARALLELISM

python main_adapter.py \
  --csv_path "${CSV_PATH}" \
  --base_model_name "${GEN_MODEL_HF}" \
  --output_name "${OUTPUT_NAME}" \
  --device "${DEVICE}" \
  --cache_dir "${CACHE_DIR}" \
  "${EXTRA_ARGS[@]}" \
  2>&1 | tee -a "${LOG_FILE}"