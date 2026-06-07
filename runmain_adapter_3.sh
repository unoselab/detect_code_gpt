#!/bin/bash
# 
# ~/project-workspace/ai-detector/src/code-analyzer-tree-sitter/data_codesearchnet/starcoder2-15b/validsyntax_4500_complexity/codesearchnet_starcoder2-15b-instruct-v0.1_python_merged_4500.csv
# 
set -euo pipefail
PROJECT_ROOT=~/project-workspace/detect_code_gpt
CUDA_DEVICE=0
DATASET=CodeSearchNet

GEN_MODEL="${GEN_MODEL:-starcoder2-15b-instruct-v0.1}"
GEN_MODEL_HF="${GEN_MODEL_HF:-bigcode/starcoder2-15b-instruct-v0.1}"
WORKSPACE_ROOT=~/project-workspace
CSV_ROOT="${WORKSPACE_ROOT}/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet"
CSV_ROOT_SUB="${CSV_ROOT}/${GEN_MODEL}/validsyntax_4500_complexity"
CSV_PATH="${CSV_PATH:-${CSV_ROOT_SUB}/codesearchnet_${GEN_MODEL}_python_merged_4500.csv}"

TIMESTAMP=$(date +%m-%d_%H-%M)
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/main_adapter_${TIMESTAMP}.log"

# /home/user1-selab3/project-workspaces/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet/starcoder2-15b-instruct-v0.1/validsyntax_4500_complexity/codesearchnet_starcoder2-15b-instruct-v0.1_python_merged_4500.csv
echo "=== Detection run configuration ==="
echo "  DATASET:        ${DATASET}"
echo "  GEN_MODEL:      ${GEN_MODEL}"
echo "  GEN_MODEL_HF:   ${GEN_MODEL_HF}"
echo "  CUDA_DEVICE:    ${CUDA_DEVICE}"
echo "  LOG_FILE:       ${LOG_FILE}"
echo "  CSV_PATH:       ${CSV_PATH}"
echo "  PROJECT_ROOT:   ${PROJECT_ROOT}"
echo "===================================="
echo ""

test -d "${PROJECT_ROOT}/code-detection" || { echo "Missing code-detection dir"; exit 1; }
test -f "${PROJECT_ROOT}/code-detection/main_adapter.py" || { echo "Missing main_adapter.py"; exit 1; }
test -f "${CSV_PATH}" || { echo "Missing CSV: ${CSV_PATH}"; exit 1; }

cd "${PROJECT_ROOT}"
mkdir -p "${LOG_DIR}"
cd code-detection

export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"

## INTERMEDIATE CHECK
# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name "${GEN_MODEL_HF}" \
#     --output_name "${GEN_MODEL}_4500_n5" \
#     --limit 5 \
#     2>&1 | tee "${LOG_FILE}"

## CHECK THE EMPTY HWC AND MGC
# python main_adapter.py \
#     --csv_path ${CSV_PATH} \
#     --count_empty_only    

## FULL RUN 
python main_adapter.py \
    --csv_path "${CSV_PATH}" \
    --base_model_name "${GEN_MODEL_HF}" \
    --output_name "${GEN_MODEL}_4500" \
    2>&1 | tee "${LOG_FILE}"

