#!/bin/bash
# 
# ~/project-workspace/ai-detector/src/code-analyzer-tree-sitter/data_codesearchnet/starcoder2-15b/validsyntax_4500_complexity/codesearchnet_starcoder2-15b-instruct-v0.1_python_merged_4500.csv
# 
set -euo pipefail
PROJECT_ROOT=~/project-workspace/detect_code_gpt
CUDA_DEVICE=0
DATASET=CodeSearchNet

GEN_MODEL="${GEN_MODEL:-starcoder2-15b}"
GEN_MODEL_HF="${GEN_MODEL_HF:-bigcode/starcoder2-15b-instruct-v0.1}"
WORKSPACE_ROOT=~/project-workspace
CSV_ROOT="${WORKSPACE_ROOT}/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet"
CSV_ROOT_SUB="${CSV_ROOT}/${GEN_MODEL}/validsyntax_4500_complexity"
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

# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name "${GEN_MODEL_HF}" \
#     --output_name "${GEN_MODEL}_4500" \
#     2>&1 | tee "${LOG_FILE}"

# intermediate check: ~100 pairs first (~10 min) to confirm separation holds at scale
python main_adapter.py \
    --csv_path "${CSV_PATH}" \
    --base_model_name "${GEN_MODEL_HF}" \
    --output_name "${GEN_MODEL}_4500_n3" \
    --limit 3 \
    2>&1 | tee "${LOG_FILE}"
