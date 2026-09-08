#!/bin/bash
#
# run-x-c01: pooled five-source NPR threshold calibration for StarCoder2-7B.
#
# PURPOSE
#   Calibrate the conference-time fallback NPR scorer after GPT-OSS-120B was
#   found computationally impractical for exhaustive historical scoring.
#   StarCoder2-7B is the second-ranked minimax-regret NPR scorer and has the
#   highest same-generator AUROC in the completed 5x5 cross-generator study.
#
# SCIENTIFIC INPUT
#   Five completed per-procedure score CSVs from the StarCoder2-7B scorer row:
#     codellama-7b
#     starcoder2-7b
#     starcoder2-15b-instruct-v0.1
#     gpt-oss
#     gemma
#   Each source contributes exactly 300 procedures (150 HWC + 150 AGC).
#
# SCIENTIFIC OUTPUT
#   A single pooled threshold using the established strict rule:
#     AGC iff NPR_proc > tau
#   Candidate selection order:
#     1. maximum Youden's J
#     2. maximum balanced accuracy
#     3. smallest threshold
#
# IMPORTANT
#   - This wrapper does not call any older shell script.
#   - No language model is loaded; this is a CPU-only calibration analysis.
#   - Existing cross-generator NPR scores are read without modification.
#   - The prior SC2 threshold 1.571637 is used only as a non-blocking
#     same-source reproduction audit; it cannot influence pooled tau selection.
#
# INPUT OVERRIDES
#   PYTHON_BIN           Python executable. Default: python
#   INPUT_ROOT           Directory containing the five SC2 scorer CSVs.
#   OUTPUT_ROOT          New run-x-c01 output directory.
#   OVERWRITE            1 to replace an existing OUTPUT_ROOT; default 0.
#   REFERENCE_THRESHOLD  Prior same-source SC2 threshold for audit only.
#   REFERENCE_TOLERANCE  Audit tolerance; default 1e-6.
#
# OUTPUTS
#   sc2_pooled_threshold_candidates.csv
#   sc2_pooled_calibrated_predictions.csv
#   sc2_pooled_overall_metrics.csv
#   sc2_pooled_source_metrics.csv
#   sc2_pooled_source_bucket_metrics.csv
#   sc2_pooled_bucket_metrics.csv
#   sc2_pooled_threshold_specification.json
#   input_manifest.csv
#   qc/sc2_pooled_calibration_checks.csv
#   qc/sc2_pooled_calibration_summary.json
#
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
PYTHON_SCRIPT="${PROJECT_ROOT}/code-detection/calibrate_npr_sc2_pooled_threshold.py"
INPUT_ROOT="${INPUT_ROOT:-${PROJECT_ROOT}/output/commit_function/run-1c0d/npr-cross-generator-v1}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${PROJECT_ROOT}/output/commit_function/run-x-c01/npr-sc2-pooled-threshold-v1}"
LOG_DIR="${PROJECT_ROOT}/logs/run-x-c01"
OVERWRITE="${OVERWRITE:-0}"
REFERENCE_THRESHOLD="${REFERENCE_THRESHOLD:-1.571637}"
REFERENCE_TOLERANCE="${REFERENCE_TOLERANCE:-1e-6}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_DIR}/run-x-c01-calibrate-npr-sc2-pooled-threshold-${TIMESTAMP}.log"

TARGET_SOURCES=(
  "codellama-7b"
  "starcoder2-7b"
  "starcoder2-15b-instruct-v0.1"
  "gpt-oss"
  "gemma"
)

mkdir -p "${LOG_DIR}"

if [[ ! -f "${PYTHON_SCRIPT}" ]]; then
  echo "ERROR: missing Python script: ${PYTHON_SCRIPT}" >&2
  exit 2
fi

if [[ ! -d "${INPUT_ROOT}" ]]; then
  echo "ERROR: missing input directory: ${INPUT_ROOT}" >&2
  exit 2
fi

for target in "${TARGET_SOURCES[@]}"; do
  score_file="${INPUT_ROOT}/npr_scores_npr-xgen_score-starcoder2-7b_target-${target}.csv"
  if [[ ! -s "${score_file}" ]]; then
    echo "ERROR: missing or empty required input: ${score_file}" >&2
    exit 2
  fi
done

if [[ -d "${OUTPUT_ROOT}" ]] && [[ -n "$(find "${OUTPUT_ROOT}" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  if [[ "${OVERWRITE}" != "1" ]]; then
    echo "ERROR: output directory is not empty: ${OUTPUT_ROOT}" >&2
    echo "Set OVERWRITE=1 only if you intentionally want to replace this c01 output." >&2
    exit 2
  fi
  rm -rf "${OUTPUT_ROOT}"
fi
mkdir -p "${OUTPUT_ROOT}"

START_EPOCH="$(date +%s)"
STARTED="$(date)"

{
  echo "============================================================================"
  echo "run-x-c01-v1: SC2-7B pooled five-source NPR threshold calibration"
  echo "Project root:                    ${PROJECT_ROOT}"
  echo "Python:                          $(command -v "${PYTHON_BIN}") ($(${PYTHON_BIN} --version 2>&1))"
  echo "Active conda env:                ${CONDA_DEFAULT_ENV:-<none>}"
  echo "Python script:                   ${PYTHON_SCRIPT}"
  echo "Python script SHA256:            $(sha256sum "${PYTHON_SCRIPT}" | awk '{print $1}')"
  echo "Input root:                      ${INPUT_ROOT}"
  echo "Output root:                     ${OUTPUT_ROOT}"
  echo "Scoring model:                   bigcode/starcoder2-7b"
  echo "Calibration population:         5 sources x 300 = 1500 procedures"
  echo "Class balance:                   750 HWC / 750 AGC"
  echo "Decision rule:                   strict NPR_proc > tau"
  echo "Threshold objective:             max Youden J -> max balanced accuracy -> smaller tau"
  echo "Prior SC2 tau reference:         ${REFERENCE_THRESHOLD} (audit only)"
  echo "Reference tolerance:             ${REFERENCE_TOLERANCE}"
  echo "Model loading / GPU use:         none"
  echo "Log file:                        ${LOG_FILE}"
  echo "============================================================================"

  "${PYTHON_BIN}" "${PYTHON_SCRIPT}" \
    --input-root "${INPUT_ROOT}" \
    --output-dir "${OUTPUT_ROOT}" \
    --reference-same-source-threshold "${REFERENCE_THRESHOLD}" \
    --reference-threshold-tolerance "${REFERENCE_TOLERANCE}"
} 2>&1 | tee "${LOG_FILE}"
STATUS=${PIPESTATUS[0]}

END_EPOCH="$(date +%s)"
ELAPSED="$((END_EPOCH - START_EPOCH))"

{
  echo
  echo "============================================================================"
  echo "run-x-c01-v1 execution summary"
  echo "Started:          ${STARTED}"
  echo "Completed:        $(date)"
  printf 'Elapsed:          %02d:%02d:%02d\n' "$((ELAPSED/3600))" "$(((ELAPSED%3600)/60))" "$((ELAPSED%60))"
  echo "Exit code:        ${STATUS}"
  echo "Output directory: ${OUTPUT_ROOT}"
  echo "Summary:          ${OUTPUT_ROOT}/qc/sc2_pooled_calibration_summary.json"
  echo "Specification:    ${OUTPUT_ROOT}/sc2_pooled_threshold_specification.json"
  echo "Log file:         ${LOG_FILE}"
  echo "============================================================================"
} | tee -a "${LOG_FILE}"

exit "${STATUS}"
