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
DATASET_KEY="${GEN_MODEL}-${GEN_MAX_NUM}-tp${GEN_TEMPERATURE}"
DATA_PATH="${OUTPUT_BASE_DIR}/${DATASET}/${DATASET_KEY}/outputs.txt"

# --- Model identities (HuggingFace IDs) ---
BASE_MODEL_NAME=codellama/CodeLlama-7b-hf
MASK_FILLING_MODEL_NAME=Salesforce/codet5p-770m

# --- Detection hyperparameters (paper-aligned defaults) ---
N_SAMPLES=2000                        # upper bound; actual count = min(N_SAMPLES, post-filter count)
                                      # previous (first pass):  500  → 131 valid after filter
                                      # current (scaled pass):  2000 → ~520 valid after filter
N_PERTURBATION_LIST=50                # k in the paper (number of perturbations per sample)
PCT_WORDS_MASKED=0.5                  # α — random-insert-space probability
PCT_IDENTIFIERS_MASKED=0.75           # paper default
SPAN_LENGTH=2                         # mask span length for MLM-style perturbations
BATCH_SIZE=50
CHUNK_SIZE=10
BASELINES="LRR,DetectGPT,NPR"         # comma-separated, no spaces
PERTURB_TYPE="random-insert-space+newline"   # DetectCodeGPT's strategy
# --- Mode flags ---
DETECTCODEGPT_ONLY=true               # true = skip baselines (~32 min saved). false = full run.
LOAD_CACHED_RESULTS=""                # path to results pickle; "" means run from scratch

# --- Run identity ---
RUN_TAG="n${GEN_MAX_NUM}_run"         # previous: "n500_first_run" / "n500_scaled_run"
                                      # current:  "n2000_run"
OUTPUT_NAME="${GEN_MODEL,,}_csn_t${GEN_TEMPERATURE/./}_${RUN_TAG}"   # lowercased + temp-without-dot
TIMESTAMP=$(date +%m-%d_%H:%M)        # captured at script start; format: MM-DD_HH:MM
LOG_FILE="${LOG_DIR}/detection_${OUTPUT_NAME}_${TIMESTAMP}.log"

# =====================================================================
# Historical results — for reference
# =====================================================================
# Run 1 (n=131 after filter, May 12 16:25-16:41, ~16 min):
#   ROC AUC of logrank:       0.8786
#   ROC AUC of LRR:           0.8412
#   ROC AUC of DetectCodeGPT: 0.8965   (paper target: 0.9095, delta -0.013)
#
# Run 2 (n=~520 after filter, expected ~60 min):
#   TBD — running now
# =====================================================================

# =====================================================================
# Pre-flight checks
# =====================================================================

echo "=== Detection run configuration ==="
echo "  DATASET:        ${DATASET}"
echo "  DATASET_KEY:    ${DATASET_KEY}"
echo "  DATA_PATH:      ${DATA_PATH}"
echo "  BASE_MODEL:     ${BASE_MODEL_NAME}"
echo "  MASK_MODEL:     ${MASK_FILLING_MODEL_NAME}"
echo "  N_SAMPLES:      ${N_SAMPLES}"
echo "  N_PERTURBATIONS:${N_PERTURBATION_LIST}"
echo "  CUDA_DEVICE:    ${CUDA_DEVICE}"
echo "  OUTPUT_NAME:    ${OUTPUT_NAME}"
echo "  LOG_FILE:       ${LOG_FILE}"
echo "===================================="
echo ""

# Verify input data exists before launching a 60-min job
if [[ ! -f "${DATA_PATH}" ]]; then
    echo "ERROR: input file not found:"
    echo "  ${DATA_PATH}"
    echo "Did generation finish? Check OUTPUT_BASE_DIR/DATASET/DATASET_KEY layout."
    exit 1
fi

# Verify code-detection dir exists
if [[ ! -d "${PROJECT_ROOT}/code-detection" ]]; then
    echo "ERROR: ${PROJECT_ROOT}/code-detection does not exist"
    exit 1
fi

# =====================================================================
# Launch
# =====================================================================

cd "${PROJECT_ROOT}"
mkdir -p "${LOG_DIR}"
cd code-detection

export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"

python main.py \
    --dataset "${DATASET}" \
    --dataset_key "${DATASET_KEY}" \
    --data_path "${DATA_PATH}" \
    --base_model_name "${BASE_MODEL_NAME}" \
    --mask_filling_model_name "${MASK_FILLING_MODEL_NAME}" \
    --n_samples "${N_SAMPLES}" \
    --n_perturbation_list "${N_PERTURBATION_LIST}" \
    --pct_words_masked "${PCT_WORDS_MASKED}" \
    --pct_identifiers_masked "${PCT_IDENTIFIERS_MASKED}" \
    --span_length "${SPAN_LENGTH}" \
    --batch_size "${BATCH_SIZE}" \
    --chunk_size "${CHUNK_SIZE}" \
    --baselines "${BASELINES}" \
    --perturb_type "${PERTURB_TYPE}" \
    --output_name "${OUTPUT_NAME}" \
    $([ "${DETECTCODEGPT_ONLY}" = "true" ] && echo "--detectcodegpt_only") \
    $([ -n "${LOAD_CACHED_RESULTS}" ] && echo "--load_cached_results ${LOAD_CACHED_RESULTS}") \
    2>&1 | tee "${LOG_FILE}"