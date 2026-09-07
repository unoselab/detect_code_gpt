#!/bin/bash
set -euo pipefail

# run-1c0g v1
#
# Purpose
# -------
# Record the pooled threshold calibration used after run-1c0f selects
# GPT-OSS-120B as the NPR scoring model.
#
# Inputs
# ------
# 1. INPUT_ROOT:
#    Directory containing exactly the five per-procedure GPT-OSS scorer files:
#      npr_scores_npr-xgen_score-gpt-oss_target-codellama-7b.csv
#      npr_scores_npr-xgen_score-gpt-oss_target-starcoder2-7b.csv
#      npr_scores_npr-xgen_score-gpt-oss_target-starcoder2-15b-instruct-v0.1.csv
#      npr_scores_npr-xgen_score-gpt-oss_target-gpt-oss.csv
#      npr_scores_npr-xgen_score-gpt-oss_target-gemma.csv
#    Each file must contain 300 procedures: 150 HWC and 150 AGC.
#
# 2. SELECTION_SUMMARY:
#    run-1c0f point_estimates.csv. The Python analysis verifies that GPT-OSS
#    is the unique scoring model selected by observed minimax regret.
#
# Outputs
# -------
# OUTPUT_DIR contains:
#   npr_pooled_input_manifest.csv
#   npr_pooled_threshold_candidates.csv
#   npr_pooled_calibrated_predictions.csv
#   npr_pooled_overall_metrics.csv
#   npr_pooled_source_metrics.csv
#   npr_pooled_threshold_specification.json
#   methodology.txt
#   qc/npr_pooled_threshold_checks.csv
#   qc/npr_pooled_threshold_summary.json
#
# The expected reproducibility target is tau=1.545529. This value is used only
# as a QC assertion after the threshold has been recomputed from the inputs; it
# does not participate in threshold selection.

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

# Use the versioned development filename by default. If the project follows the
# server convention of removing the version suffix, the unversioned filename is
# accepted automatically.
PYTHON_SCRIPT="${PYTHON_SCRIPT:-${PROJECT_ROOT}/code-detection/calibrate_npr_cross_generator_threshold-v1.py}"
if [[ ! -f "${PYTHON_SCRIPT}" && -f "${PROJECT_ROOT}/code-detection/calibrate_npr_cross_generator_threshold.py" ]]; then
  PYTHON_SCRIPT="${PROJECT_ROOT}/code-detection/calibrate_npr_cross_generator_threshold.py"
fi

INPUT_ROOT="${INPUT_ROOT:-${PROJECT_ROOT}/output/commit_function/run-1c0d/npr-cross-generator-v1}"
SELECTION_SUMMARY="${SELECTION_SUMMARY:-${PROJECT_ROOT}/output/commit_function/run-1c0f/npr-cross-generator-selection-v2/point_estimates.csv}"
OUTPUT_DIR="${OUTPUT_DIR:-${PROJECT_ROOT}/output/commit_function/run-1c0g/npr-cross-generator-threshold-v1}"
EXPECTED_THRESHOLD="${EXPECTED_THRESHOLD:-1.545529}"
THRESHOLD_TOLERANCE="${THRESHOLD_TOLERANCE:-1e-12}"
LOG_DIR="${PROJECT_ROOT}/logs/run-1c0g"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_DIR}/run-1c0g-calibrate-npr-cross-generator-threshold-${TIMESTAMP}.log"
START_EPOCH="$(date +%s)"

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
mkdir -p "${LOG_DIR}" "${OUTPUT_DIR}"

# Fail before analysis if any required provenance input is missing.
test -f "${PYTHON_SCRIPT}"
test -d "${INPUT_ROOT}"
test -f "${SELECTION_SUMMARY}"

{
  echo "============================================================================"
  echo "run-1c0g v1: pooled cross-generator NPR threshold calibration"
  echo "Started:                         $(date)"
  echo "Workspace:                       ${PROJECT_ROOT}"
  echo "Host:                            $(hostname -f 2>/dev/null || hostname)"
  echo "Active conda env:                ${CONDA_DEFAULT_ENV:-unknown}"
  echo "Python path:                     $(command -v "${PYTHON_BIN}")"
  echo "Python version:                  $("${PYTHON_BIN}" --version 2>&1)"
  echo "Python script:                   ${PYTHON_SCRIPT}"
  echo "Python script SHA:               $(sha256sum "${PYTHON_SCRIPT}" | awk '{print $1}')"
  echo "Input score root:                ${INPUT_ROOT}"
  echo "Selection summary:               ${SELECTION_SUMMARY}"
  echo "Selection summary SHA:           $(sha256sum "${SELECTION_SUMMARY}" | awk '{print $1}')"
  echo "Expected threshold QC:           ${EXPECTED_THRESHOLD}"
  echo "Threshold tolerance:             ${THRESHOLD_TOLERANCE}"
  echo "Output directory:                ${OUTPUT_DIR}"
  echo "Log file:                        ${LOG_FILE}"
  echo "Decision rule:                   NPR_proc > tau"
  echo "Calibration sample:              5 sources x 300 procedures = 1,500"
  echo "Class balance:                   750 HWC / 750 AGC"
  echo "============================================================================"
} 2>&1 | tee "${LOG_FILE}"

set +e
"${PYTHON_BIN}" -u "${PYTHON_SCRIPT}" \
  --input-root "${INPUT_ROOT}" \
  --selection-summary "${SELECTION_SUMMARY}" \
  --output-dir "${OUTPUT_DIR}" \
  --expected-threshold "${EXPECTED_THRESHOLD}" \
  --threshold-tolerance "${THRESHOLD_TOLERANCE}" \
  2>&1 | tee -a "${LOG_FILE}"
PY_EXIT="${PIPESTATUS[0]}"
set -e

END_EPOCH="$(date +%s)"
{
  echo "============================================================================"
  echo "Completed:                       $(date)"
  echo "Elapsed seconds:                 $((END_EPOCH - START_EPOCH))"
  echo "Exit code:                       ${PY_EXIT}"
  if [[ "${PY_EXIT}" -eq 0 ]]; then
    echo "Status:                          PASS"
  else
    echo "Status:                          FAIL"
  fi
  echo "============================================================================"
} 2>&1 | tee -a "${LOG_FILE}"

exit "${PY_EXIT}"
