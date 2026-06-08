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
# Example full run:
#   bash runmain_adapter_5.sh
#
# Example smoke test:
#   LIMIT=50 bash runmain_adapter_5.sh
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

mkdir -p "${LOG_DIR}"

{
  echo "=== Detection run configuration ==="
  echo "  DATASET:          ${DATASET}"
  echo "  GEN_MODEL:        ${GEN_MODEL}"
  echo "  GEN_MODEL_HF:     ${GEN_MODEL_HF}"
  echo "  CUDA_DEVICE:      ${CUDA_DEVICE}"
  echo "  CSV_SPLIT_DIR:    ${CSV_SPLIT_DIR}"
  echo "  CSV_PATH:         ${CSV_PATH}"
  echo "  OUTPUT_NAME:      ${OUTPUT_NAME}"
  echo "  LIMIT:            ${LIMIT:-<none>}"
  echo "  MIN_CHUNK_TOKENS: ${MIN_CHUNK_TOKENS:-<default>}"
  echo "  LOG_FILE:         ${LOG_FILE}"
  echo "===================================="
  echo ""
} | tee "${LOG_FILE}"

test -d "${PROJECT_ROOT}/code-detection" || { echo "Missing code-detection dir: ${PROJECT_ROOT}/code-detection" | tee -a "${LOG_FILE}"; exit 1; }
test -f "${PROJECT_ROOT}/code-detection/main_adapter.py" || { echo "Missing main_adapter.py: ${PROJECT_ROOT}/code-detection/main_adapter.py" | tee -a "${LOG_FILE}"; exit 1; }
test -f "${CSV_PATH}" || { echo "Missing CSV: ${CSV_PATH}" | tee -a "${LOG_FILE}"; exit 1; }

cd "${PROJECT_ROOT}/code-detection"
export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"

python main_adapter.py \
  --csv_path "${CSV_PATH}" \
  --base_model_name "${GEN_MODEL_HF}" \
  --output_name "${OUTPUT_NAME}" \
  "${EXTRA_ARGS[@]}" \
  2>&1 | tee -a "${LOG_FILE}"
