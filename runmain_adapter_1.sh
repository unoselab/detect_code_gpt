#!/bin/bash
set -euo pipefail
PROJECT_ROOT=~/project-workspace/detect_code_gpt
CUDA_DEVICE=0
DATASET=CodeSearchNet

GEN_MODEL="${GEN_MODEL:-starcoder2-7b}"
GEN_MODEL_HF="${GEN_MODEL_HF:-bigcode/starcoder2-7b}"
WORKSPACE_ROOT=/home/user1-system12/project-workspace
CSV_ROOT="${WORKSPACE_ROOT}/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet"
CSV_ROOT_SUB="${CSV_ROOT}/${GEN_MODEL}/validsyntax_4500_complexity"
CSV_PATH="${CSV_PATH:-${CSV_ROOT_SUB}/codesearchnet_starcoder2-7b_python_merged_4500.csv}"

TIMESTAMP=$(date +%m-%d_%H:%M)
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/main_v2_${TIMESTAMP}.log"

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
    --output_name "${GEN_MODEL}_4500" \
    2>&1 | tee "${LOG_FILE}"

# intermediate check: ~100 pairs first (~10 min) to confirm separation holds at scale
# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name bigcode/starcoder2-7b \
#     --output_name starcoder2_4500_n100 \
#     --limit 100 \
#     2>&1 | tee "${LOG_FILE}"
