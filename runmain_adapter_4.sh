#!/bin/bash
set -euo pipefail
PROJECT_ROOT=~/project-workspace/detect_code_gpt
CUDA_DEVICE=0
DATASET=CodeSearchNet

GEN_MODEL="${GEN_MODEL:-gpt-oss}"
# GEN_MODEL_HF="${GEN_MODEL_HF:-bigcode/gpt-oss}"
WORKSPACE_ROOT=~/project-workspace
CSV_ROOT="${WORKSPACE_ROOT}/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet"
# CSV_ROOT_SUB="${CSV_ROOT}/${GEN_MODEL}/validsyntax_4500_complexity"
CSV_ROOT_SUB="${CSV_ROOT}/${GEN_MODEL}/validsyntax" # 4500
CSV_PATH="${CSV_PATH:-${CSV_ROOT_SUB}/codesearchnet_gpt-oss_python_merged_4500.csv}"

TIMESTAMP=$(date +%m-%d_%H:%M)
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/main_adapter_${TIMESTAMP}.log"

# /home/user1-system11/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet/gpt-oss/validsyntax_4500_complexity/codesearchnet_gpt-oss_python_merged_4500.csv
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
# partial run
python main_adapter.py \
    --csv_path "${CSV_PATH}" \
    --base_model_name "${GEN_MODEL_HF}" \
    --output_name "${GEN_MODEL}_4500_refreshed_n100" \
    --limit 100 \
    2>&1 | tee "${LOG_FILE}"

# check the empty HWC and MGC
# python main_adapter.py \
#     --csv_path ${CSV_PATH} \
#     --count_empty_only    

# echo "${CSV_PATH}"
# echo "/home/user1-system11/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet/gpt-oss/validsyntax/codesearchnet_gpt-oss_python_merged_4500.csv"

# Testing --min_chunk_tokens 10
# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name "${GEN_MODEL_HF}" \
#     --output_name "${GEN_MODEL}_4500_n100" \
#     --min_chunk_tokens 10 --limit 100 \
#     2>&1 | tee "${LOG_FILE}"

# # Testing --min_chunk_tokens 5 - ROC AUC of DetectCodeGPT (NPR): 0.5721
# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name "${GEN_MODEL_HF}" \
#     --output_name "${GEN_MODEL}_4500_n100" \
#     --min_chunk_tokens 5 --limit 100 \
#     2>&1 | tee "${LOG_FILE}"

# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name "${GEN_MODEL_HF}" \
#     --output_name "${GEN_MODEL}_4500" \
#     2>&1 | tee "${LOG_FILE}"

# intermediate check: ~100 pairs first (~10 min) to confirm separation holds at scale
# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name bigcode/gpt-oss \
#     --output_name starcoder2_4500_n100 \
#     --limit 100 \
#     2>&1 | tee "${LOG_FILE}"
