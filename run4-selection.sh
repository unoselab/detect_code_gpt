#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Create the filtered 530-pair benchmark JSONL file.
#
# Input:
#   1. outputs.txt
#      - 2000 raw CodeLlama generations
#      - fields: prompt, output, solution
#
#   2. npr_scores_*.csv
#      - 530 filtered DetectCodeGPT samples
#      - uses source_line_no to map back to outputs.txt
#
# Output:
#   outputs_530_filter.jsonl
#      - fields: prompt, output, solution
#      - output   = MGC
#      - solution = HWC
# ============================================================

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

CODE_SELECTION_DIR="${PROJECT_ROOT}/code-selection"
LOG_DIR="${PROJECT_ROOT}/logs"
OUTPUT_ROOT="${PROJECT_ROOT}/output"

DATASET_NAME="CodeSearchNet"
GEN_MODEL="CodeLlama-7b-hf"
GEN_MAX_NUM="2000"
GEN_TEMPERATURE="0.2"

DATASET_KEY="${GEN_MODEL}-${GEN_MAX_NUM}-tp${GEN_TEMPERATURE}"
RUN_NAME="codellama-7b-hf_csn_t02_n2000_run"

# -----------------------------
# Files
# -----------------------------
SELECTION_SCRIPT="${CODE_SELECTION_DIR}/create_outputs_530_filter.py"

OUTPUT_DIR="${OUTPUT_ROOT}/${DATASET_NAME}/${DATASET_KEY}"

OUTPUTS_TXT="${OUTPUT_DIR}/outputs.txt"
NPR_CSV="${LOG_DIR}/npr_scores_${RUN_NAME}.csv"
OUT_JSONL="${OUTPUT_DIR}/outputs_530_filter.jsonl"

mkdir -p "${OUTPUT_DIR}"

echo "============================================================"
echo "OUTPUTS_TXT:      ${OUTPUTS_TXT}"
echo "NPR_CSV:          ${NPR_CSV}"
echo "OUT_JSONL:        ${OUT_JSONL}"
echo "============================================================"

python "${SELECTION_SCRIPT}" \
--outputs_txt "${OUTPUTS_TXT}" \
--npr_csv "${NPR_CSV}" \
--out_jsonl "${OUT_JSONL}" \
--include_scores

echo "============================================================"
echo "Filtered benchmark written to:"
echo "${OUT_JSONL}"
echo "============================================================"