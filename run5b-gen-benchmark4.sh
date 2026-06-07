#!/usr/bin/env bash
set -euo pipefail

# ~/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet/codellama-7b/validsyntax_4500_complexity/codesearchnet_codellama-7b_python_merged_4500.csv

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

CODE_SELECTION_DIR="${PROJECT_ROOT}/code-selection"
LOG_DIR="${PROJECT_ROOT}/logs"
OUTPUT_ROOT="${PROJECT_ROOT}/output"
INPUT_DATA_ROOT="${HOME}/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet"

GEN_MODEL="${GEN_MODEL:-codellama-7b}"
FILES_PER_TYPE="${FILES_PER_TYPE:-5}"
SEED="${SEED:-0}"

INPUT_CSV="${INPUT_DATA_ROOT}/${GEN_MODEL}/validsyntax_4500_complexity/codesearchnet_${GEN_MODEL}_python_merged_4500.csv"
OUTPUT_DIR="${CODE_SELECTION_DIR}/mixedcode_benchmarks/${GEN_MODEL}"

TIMESTAMP="$(date +%m-%d_%H-%M)"
LOG_FILE="${LOG_DIR}/generate_mixedcode_${GEN_MODEL}_${TIMESTAMP}.log"

mkdir -p "${LOG_DIR}"

# cd ~/project-workspace/detect_code_gpt/code-selection

# python analyze_func_size.py \
#   --input_csv ~/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet/starcoder2-7b/validsyntax_4500_complexity/codesearchnet_starcoder2-7b_python_merged_4500.csv \
#   --out_dir ./size_analysis/starcoder2-7b \
#   --files_per_type 100

{
  echo "=== Mixed-code benchmark generation ==="
  echo "  PROJECT_ROOT:       ${PROJECT_ROOT}"
  echo "  CODE_SELECTION_DIR: ${CODE_SELECTION_DIR}"
  echo "  LOG_DIR:            ${LOG_DIR}"
  echo "  OUTPUT_ROOT:        ${OUTPUT_ROOT}"
  echo "  GEN_MODEL:          ${GEN_MODEL}"
  echo "  INPUT_CSV:          ${INPUT_CSV}"
  echo "  OUTPUT_DIR:         ${OUTPUT_DIR}"
  echo "  FILES_PER_TYPE:     ${FILES_PER_TYPE}"
  echo "  SEED:               ${SEED}"
  echo "  LOG_FILE:           ${LOG_FILE}"
  echo "======================================="
  echo ""

  test -d "${CODE_SELECTION_DIR}" || { echo "Missing code-selection dir: ${CODE_SELECTION_DIR}"; exit 1; }
  test -f "${CODE_SELECTION_DIR}/generate_mixedcode_benchmark.py" || { echo "Missing generate_mixedcode_benchmark.py"; exit 1; }
  test -f "${INPUT_CSV}" || { echo "Missing input CSV: ${INPUT_CSV}"; exit 1; }

  cd "${CODE_SELECTION_DIR}"

  echo "[RUN] python generate_mixedcode_benchmark.py \\"
  echo "        --input_csv \"${INPUT_CSV}\" \\"
  echo "        --out_dir \"${OUTPUT_DIR}\" \\"
  echo "        --files_per_type \"${FILES_PER_TYPE}\" \\"
  echo "        --seed \"${SEED}\""
  echo ""

  python generate_mixedcode_benchmark.py \
    --input_csv "${INPUT_CSV}" \
    --out_dir "${OUTPUT_DIR}" \
    --files_per_type "${FILES_PER_TYPE}" \
    --seed "${SEED}"

} 2>&1 | tee "${LOG_FILE}"