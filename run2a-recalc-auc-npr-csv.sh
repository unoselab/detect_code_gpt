#!/bin/bash
# Recalculate AUROC from NPR CSV files.
# Includes paired comparison with prompt-alignment safety check.

set -euo pipefail

PROJECT_ROOT=~/project-workspace/detect_code_gpt
DATASET="CodeSearchNet"

LOG_DIR="${PROJECT_ROOT}/logs"
OUTPUT_DIR="${PROJECT_ROOT}/output/${DATASET}"
SCRIPT_PATH="${PROJECT_ROOT}/code-detection/recalc_auc_from_npr_csv_v2.py"
N_FIXED_SAMPLES=530

# =====================================================================
# Model/run identities
# =====================================================================
PRIMARY_MODEL="starcoder2-7b"
PRIMARY_GEN_MAX_NUM=3000
PRIMARY_TEMPERATURE=0.2
PRIMARY_RUN_TAG="n3000_run"

PAIR_MODEL="CodeLlama-7b-hf"
PAIR_GEN_MAX_NUM=2000
PAIR_TEMPERATURE=0.2
PAIR_RUN_TAG="n2000_run"

# =====================================================================
PRIMARY_DATASET_KEY="${PRIMARY_MODEL}-${PRIMARY_GEN_MAX_NUM}-tp${PRIMARY_TEMPERATURE}"
PAIR_DATASET_KEY="${PAIR_MODEL}-${PAIR_GEN_MAX_NUM}-tp${PAIR_TEMPERATURE}"

PRIMARY_OUTPUT_NAME="${PRIMARY_MODEL,,}_csn_t${PRIMARY_TEMPERATURE/./}_${PRIMARY_RUN_TAG}"
PAIR_OUTPUT_NAME="${PAIR_MODEL,,}_csn_t${PAIR_TEMPERATURE/./}_${PAIR_RUN_TAG}"

PRIMARY_CSV="${LOG_DIR}/npr_scores_${PRIMARY_OUTPUT_NAME}.csv"
PAIR_CSV="${LOG_DIR}/npr_scores_${PAIR_OUTPUT_NAME}.csv"

PRIMARY_OUTPUTS="${OUTPUT_DIR}/${PRIMARY_DATASET_KEY}/outputs.txt"
PAIR_OUTPUTS="${OUTPUT_DIR}/${PAIR_DATASET_KEY}/outputs.txt"

echo "=== Recalculate AUROC from NPR CSV ==="
echo "  N of Fixed Samples:  ${N_FIXED_SAMPLES}"
echo "  Primary CSV:         ${PRIMARY_CSV/${PROJECT_ROOT}/PRJ}"
echo "  Pair CSV:            ${PAIR_CSV/${PROJECT_ROOT}/PRJ}"
echo "  Primary outputs:     ${PRIMARY_OUTPUTS/${PROJECT_ROOT}/PRJ}"
echo "  Pair outputs:        ${PAIR_OUTPUTS/${PROJECT_ROOT}/PRJ}"
echo "  Script:              ${SCRIPT_PATH/${PROJECT_ROOT}/PRJ}"
echo "======================================"
echo ""

# =====================================================================
cd "${PROJECT_ROOT}"

# First N_FIXED_SAMPLES in source order
python "${SCRIPT_PATH}" --csv "${PRIMARY_CSV}" --n "${N_FIXED_SAMPLES}"

python "${SCRIPT_PATH}" \
    --csv "${PRIMARY_CSV}"         --pair_csv "${PAIR_CSV}" \
    --outputs "${PRIMARY_OUTPUTS}" --pair_outputs "${PAIR_OUTPUTS}"