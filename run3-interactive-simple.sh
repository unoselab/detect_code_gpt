#!/bin/bash
# Run this script from inside a tmux session
# Detection Phase — DetectCodeGPT scoring
# Edit the variables below to change model / dataset / sample count.

set -euo pipefail

# =====================================================================
# Configuration — edit these for each run
# =====================================================================

# --- Project paths ---
PROJECT_ROOT=~/project-workspace/detect_code_gpt
OUTPUT_BASE_DIR="${PROJECT_ROOT}/output"
LOG_DIR="${PROJECT_ROOT}/logs"

# --- GPU selection (must be set BEFORE any python import torch) ---
CUDA_DEVICE=0

# --- Dataset / generation identity ---
DATASET=CodeSearchNet
GEN_MODEL=CodeLlama-7b-hf            # short name used in dataset_key
GEN_MAX_NUM=2000                      # how many samples generate.py produced
                                      # previous (n=131 valid): 500
                                      # current (n~520 valid):   2000
GEN_TEMPERATURE=0.2                   # generation temperature

# --- Model identities (HuggingFace IDs) ---
BASE_MODEL_NAME=codellama/CodeLlama-7b-hf

# --- Detection hyperparameters (paper-aligned defaults) ---
N_PERTURBATION_LIST=50                # k in the paper (number of perturbations per sample)
SPAN_LENGTH=2                         # mask span length for MLM-style perturbations
BATCH_SIZE=50
CHUNK_SIZE=10
PERTURB_TYPE="random-insert-space+newline"   # DetectCodeGPT's strategy

TIMESTAMP=$(date +%m-%d_%H:%M)        # captured at script start; format: MM-DD_HH:MM
LOG_FILE="${LOG_DIR}/detection_interactive_${TIMESTAMP}.log"

echo "=== Detection run configuration ==="
echo "  BASE_MODEL:     ${BASE_MODEL_NAME}"
echo "  N_PERTURBATIONS:${N_PERTURBATION_LIST}"
echo "  CUDA_DEVICE:    ${CUDA_DEVICE}"
echo "  LOG_FILE:       ${LOG_FILE}"
echo "===================================="
echo ""

# =====================================================================
# Launch
# =====================================================================

cd "${PROJECT_ROOT}"
mkdir -p "${LOG_DIR}"
cd code-detection

export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"

python main.py \
    --interactive \
    --threshold 1.6 \
    --base_model_name "${BASE_MODEL_NAME}" \
    --n_perturbation_list "${N_PERTURBATION_LIST}" \
    --span_length "${SPAN_LENGTH}" \
    --batch_size "${BATCH_SIZE}" \
    --chunk_size "${CHUNK_SIZE}" \
    --perturb_type "${PERTURB_TYPE}" \
    2>&1 | tee "${LOG_FILE}"

