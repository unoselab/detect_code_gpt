#!/bin/bash
# 
# ~/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet/gpt-oss/validsyntax_4500_complexity/codesearchnet_gpt-oss_python_merged_4500.csv
# ~/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet/codellama-7b/validsyntax/codesearchnet_codellama-7b_python_merged_4500.csv
# 
set -euo pipefail
PROJECT_ROOT=~/project-workspace/detect_code_gpt
CUDA_DEVICE=0
DATASET=CodeSearchNet

GEN_MODEL="${GEN_MODEL:-codellama-7b}"
GEN_MODEL_HF="${GEN_MODEL_HF:-codellama/CodeLlama-7b-hf}"
WORKSPACE_ROOT=~/project-workspace
CSV_ROOT="${WORKSPACE_ROOT}/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet"
CSV_ROOT_SUB="${CSV_ROOT}/${GEN_MODEL}/validsyntax"
CSV_PATH="${CSV_PATH:-${CSV_ROOT_SUB}/codesearchnet_${GEN_MODEL}_python_merged_4500.csv}"

TIMESTAMP=$(date +%m-%d_%H:%M)
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/main_adapter_${TIMESTAMP}.log"

echo "=== Detection run configuration ==="
echo "  DATASET:        ${DATASET}"
echo "  LOG_FILE:       ${LOG_FILE}"
echo "  CSV_PATH:       ${CSV_PATH}"
echo "===================================="
echo ""

cd "${PROJECT_ROOT}"
mkdir -p "${LOG_DIR}"
cd code-detection

export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"

python main_adapter.py \
    --csv_path "${CSV_PATH}" \
    --base_model_name "${GEN_MODEL_HF}" \
    --output_name "${GEN_MODEL}_4500_refreshed" \
    2>&1 | tee "${LOG_FILE}"


## INTERMEDIATE CHECK: ~100 PAIRS FIRST (~10 MIN) TO CONFIRM SEPARATION HOLDS AT SCALE
# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name "${GEN_MODEL_HF}" \
#     --output_name "${GEN_MODEL}_4500_n5" \
#     --limit 5 \
#     2>&1 | tee "${LOG_FILE}"

## CHECK THE EMPTY HWC AND MGC
# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --count_empty_only    
