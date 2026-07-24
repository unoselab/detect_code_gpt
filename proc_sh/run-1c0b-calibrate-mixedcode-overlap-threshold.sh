#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
PYTHON_SCRIPT="${PROJECT_ROOT}/code-detection/calibrate_mixedcode_overlap_threshold.py"
INPUT_SCORES="${INPUT_SCORES:-${PROJECT_ROOT}/output/commit_function/run-1c0a/mixedcode-overlap-v1/npr_scores_main_mixedcode_benchmark_mixedcode_starcoder2-7b_50files_overlap-v1.csv}"
OUTPUT_DIR="${OUTPUT_DIR:-${PROJECT_ROOT}/output/commit_function/run-1c0b/mixedcode-overlap-threshold-v1}"
LOG_DIR="${PROJECT_ROOT}/logs/run-1c0b"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_DIR}/run-1c0b-calibrate-mixedcode-overlap-threshold-${TIMESTAMP}.log"
START_EPOCH="$(date +%s)"

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
mkdir -p "${LOG_DIR}" "${OUTPUT_DIR}"

{
  echo "============================================================================"
  echo "run-1c0b: calibrate overlap-window NPR threshold"
  echo "Started:                         $(date)"
  echo "Workspace:                       ${PROJECT_ROOT}"
  echo "Active conda env:                ${CONDA_DEFAULT_ENV:-unknown}"
  echo "Python path:                     $(command -v "${PYTHON_BIN}")"
  echo "Python version:                  $("${PYTHON_BIN}" --version 2>&1)"
  echo "Python script:                   ${PYTHON_SCRIPT}"
  echo "Python script SHA:               $(sha256sum "${PYTHON_SCRIPT}" | awk '{print $1}')"
  echo "Input score CSV:                 ${INPUT_SCORES}"
  echo "Input score SHA:                 $(sha256sum "${INPUT_SCORES}" | awk '{print $1}')"
  echo "Output directory:                ${OUTPUT_DIR}"
  echo "Log file:                        ${LOG_FILE}"
  echo "============================================================================"

  test -f "${PYTHON_SCRIPT}"
  test -f "${INPUT_SCORES}"

  "${PYTHON_BIN}" -u "${PYTHON_SCRIPT}" \
    --input-scores "${INPUT_SCORES}" \
    --output-dir "${OUTPUT_DIR}"

  END_EPOCH="$(date +%s)"
  echo "============================================================================"
  echo "Completed:                       $(date)"
  echo "Elapsed seconds:                 $((END_EPOCH - START_EPOCH))"
  echo "Status:                          PASS"
  echo "============================================================================"
} 2>&1 | tee "${LOG_FILE}"
