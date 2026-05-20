#!/bin/bash
# Run this script from inside a tmux session
# Generation Phase — StarCoder2-7B on CodeSearchNet at T=0.2
#                  - CodeLlama-7B-HF for the first evaluation
# Scaled run: 2000 samples (target ~500 after filter pass rate)

set -euo pipefail

cd ~/project-workspace/detect_code_gpt

mkdir -p logs

export CUDA_VISIBLE_DEVICES=0

# =====================================================================
# Configuration
# =====================================================================

DATASET_NAME="CodeSearchNet"
GEN_MODEL="starcoder2-7b"
GEN_MODEL_HF="bigcode/starcoder2-7b"
# The FIRST EVALUATION
# GEN_MODEL_HF="codellama/CodeLlama-7b-hf"

# GEN_MAX_NUM=2000      # ColdLlama used 2000
                        # StarCoder needed 3000
GEN_MAX_NUM=3000
GEN_TEMPERATURE=0.2
# GEN_MAX_LENGTH=128    # Original value
GEN_MAX_LENGTH=512      # 512 used to generate more valid MGC for ai-detector (icse '25)
GEN_BATCH_SIZE=1

LOG_FILE="logs/generate_${GEN_MODEL}_csn_t02_n${GEN_MAX_NUM}.log"

# =====================================================================
# Run
# =====================================================================

echo "=== Generation configuration ==="
echo "  Dataset:        ${DATASET_NAME}"
echo "  HF model:       ${GEN_MODEL_HF}"
echo "  Model label:    ${GEN_MODEL}"
echo "  Max samples:    ${GEN_MAX_NUM}"
echo "  Temperature:    ${GEN_TEMPERATURE}"
echo "  Max length:     ${GEN_MAX_LENGTH}"
echo "  Batch size:     ${GEN_BATCH_SIZE}"
echo "  CUDA device:    ${CUDA_VISIBLE_DEVICES}"
echo "  Log file:       ${LOG_FILE}"
echo "================================"
echo ""

python code-generation/generate.py \
    --path "data/${DATASET_NAME}" \
    --model_name "${GEN_MODEL_HF}" \
    --max_num "${GEN_MAX_NUM}" \
    --temperature "${GEN_TEMPERATURE}" \
    --max_length "${GEN_MAX_LENGTH}" \
    --batch_size "${GEN_BATCH_SIZE}" \
    2>&1 | tee "${LOG_FILE}"