#!/usr/bin/env bash
# Analyze repository-level concentration in perturbation-detector eligibility.
#
# Workspace:
#   ~/project-workspace/detect_code_gpt
#
# Versioned delivery file:
#   proc_sh/run-1b2-analyze-commit-func-input-support-by-repo-v1.sh
#
# Canonical path:
#   proc_sh/run-1b2-analyze-commit-func-input-support-by-repo.sh
#
# Purpose:
#   Determine whether treatment-control differences in implementation-body
#   eligibility retention are broadly distributed across repositories or are
#   driven by a small number of high-volume repositories.
#
# This wrapper is standalone. It reuses the execution, logging, validation,
# and output-verification structure of run-1b but does not call run-1b or any
# other experiment shell wrapper.
#
# This step does not load StarCoder2, generate perturbations, calculate NPR,
# classify AGC/HWC, aggregate repository-month outcomes, or run DiD.
#
# Main inputs:
#   output/commit_function/run-1a/strict/
#     commit_function_detectcodegpt_input_events.csv
#   output/commit_function/run-1b/strict/
#     commit_function_body_eligibility_support.csv
#     commit_function_detectcodegpt_scoring_spec.json
#
# Main outputs:
#   output/commit_function/run-1b2/strict/
#     commit_function_eligibility_by_repository.csv
#     commit_function_repository_retention_summary.csv
#     commit_function_repository_concentration_summary.csv
#     commit_function_retention_gap_leave_top_repos_out.csv
#     commit_function_zero_eligible_repositories.csv
#     qc/commit_function_repository_support_checks.csv
#     qc/commit_function_repository_support_summary.json
#     qc/commit_function_repository_support_metadata.json
#
# Optional environment variables:
#   PROJECT_ROOT, PYTHON_BIN, PY_SCRIPT, RUN1A_DIR, RUN1B_DIR,
#   INPUT_EVENTS, INPUT_SUPPORT, INPUT_SPECIFICATION, ANALYSIS_SPECS,
#   TOP_N_VALUES, EXPECTED_PREPARED_EVENTS, EXPECTED_DATASET_SOURCES,
#   OUTPUT_DIR, QC_DIR, LOG_DIR, OVERWRITE_OUTPUT, RUN_SELF_TEST
# 
# Usage:
#   PYTHON_BIN=/home/user1-system12/miniconda3/envs/agcparse312/bin/python OVERWRITE_OUTPUT=1 bash proc_sh/run-1b2-analyze-commit-func-input-support-by-repo.sh
# 
# 

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/analyze_commit_function_input_support_by_repo.py}"

RUN1A_DIR="${RUN1A_DIR:-output/commit_function/run-1a/strict}"
RUN1B_DIR="${RUN1B_DIR:-output/commit_function/run-1b/strict}"
INPUT_EVENTS="${INPUT_EVENTS:-${RUN1A_DIR}/commit_function_detectcodegpt_input_events.csv}"
INPUT_SUPPORT="${INPUT_SUPPORT:-${RUN1B_DIR}/commit_function_body_eligibility_support.csv}"
INPUT_SPECIFICATION="${INPUT_SPECIFICATION:-${RUN1B_DIR}/commit_function_detectcodegpt_scoring_spec.json}"

ANALYSIS_SPECS="${ANALYSIS_SPECS:-min100,range100_200}"
TOP_N_VALUES="${TOP_N_VALUES:-1,5,10}"
EXPECTED_PREPARED_EVENTS="${EXPECTED_PREPARED_EVENTS:-449547}"
EXPECTED_DATASET_SOURCES="${EXPECTED_DATASET_SOURCES:-treatment,control}"

OUTPUT_DIR="${OUTPUT_DIR:-output/commit_function/run-1b2/strict}"
QC_DIR="${QC_DIR:-${OUTPUT_DIR}/qc}"
LOG_DIR="${LOG_DIR:-logs/run-1b2}"
OVERWRITE_OUTPUT="${OVERWRITE_OUTPUT:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"

TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/run-1b2-analyze-commit-func-input-support-by-repo-${TIMESTAMP}.log}"

REPOSITORY_TABLE="${OUTPUT_DIR}/commit_function_eligibility_by_repository.csv"
RETENTION_SUMMARY="${OUTPUT_DIR}/commit_function_repository_retention_summary.csv"
CONCENTRATION_SUMMARY="${OUTPUT_DIR}/commit_function_repository_concentration_summary.csv"
LEAVE_TOP_OUT="${OUTPUT_DIR}/commit_function_retention_gap_leave_top_repos_out.csv"
ZERO_ELIGIBLE="${OUTPUT_DIR}/commit_function_zero_eligible_repositories.csv"
CHECK_OUTPUT="${QC_DIR}/commit_function_repository_support_checks.csv"
SUMMARY_OUTPUT="${QC_DIR}/commit_function_repository_support_summary.json"
METADATA_OUTPUT="${QC_DIR}/commit_function_repository_support_metadata.json"

require_file() {
    local path="$1"
    local label="$2"
    if [[ ! -f "${path}" ]]; then
        echo "ERROR: Missing ${label}: ${path}" >&2
        exit 2
    fi
}

sha256_file() {
    local path="$1"
    sha256sum "${path}" | awk '{print $1}'
}

if [[ "${PYTHON_BIN}" == */* ]]; then
    if [[ ! -x "${PYTHON_BIN}" ]]; then
        echo "ERROR: Python executable is missing or not executable: ${PYTHON_BIN}" >&2
        exit 2
    fi
elif ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "ERROR: Python executable not found: ${PYTHON_BIN}" >&2
    exit 2
fi

require_file "${PY_SCRIPT}" "run-1b2 Python script"
require_file "${INPUT_EVENTS}" "run-1a prepared-event source"
require_file "${INPUT_SUPPORT}" "run-1b eligibility support"
require_file "${INPUT_SPECIFICATION}" "run-1b specification"

read -r PYTHON_MAJOR PYTHON_MINOR PYTHON_MICRO < <(
    "${PYTHON_BIN}" -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)'
)
PYTHON_VERSION="${PYTHON_MAJOR}.${PYTHON_MINOR}.${PYTHON_MICRO}"
if (( PYTHON_MAJOR < 3 || (PYTHON_MAJOR == 3 && PYTHON_MINOR < 10) )); then
    echo "ERROR: Python 3.10 or newer is required; found ${PYTHON_VERSION}." >&2
    exit 2
fi

mkdir -p "${LOG_DIR}"
START_EPOCH="$(date +%s)"
START_TEXT="$(date)"

finish() {
    local exit_code=$?
    local end_epoch elapsed hours minutes seconds
    end_epoch="$(date +%s)"
    elapsed=$((end_epoch - START_EPOCH))
    hours=$((elapsed / 3600))
    minutes=$(((elapsed % 3600) / 60))
    seconds=$((elapsed % 60))

    echo
    echo "============================================================================"
    echo "run-1b2 execution summary"
    echo "Started:               ${START_TEXT}"
    echo "Completed:             $(date)"
    printf 'Elapsed:               %02d:%02d:%02d\n' "${hours}" "${minutes}" "${seconds}"
    echo "Exit code:             ${exit_code}"
    echo "Python path:           ${PYTHON_BIN}"
    echo "Python version:        ${PYTHON_VERSION}"
    echo "Script path:           ${PY_SCRIPT}"
    echo "Input events:          ${INPUT_EVENTS}"
    echo "Input support:         ${INPUT_SUPPORT}"
    echo "Input specification:   ${INPUT_SPECIFICATION}"
    echo "Output directory:      ${OUTPUT_DIR}"
    echo "QC directory:          ${QC_DIR}"
    echo "Log file:              ${LOG_FILE}"
    echo "============================================================================"
    exit "${exit_code}"
}

trap finish EXIT
exec > >(tee -a "${LOG_FILE}") 2>&1

PY_SCRIPT_SHA="$(sha256_file "${PY_SCRIPT}")"
INPUT_EVENTS_SHA="$(sha256_file "${INPUT_EVENTS}")"
INPUT_SUPPORT_SHA="$(sha256_file "${INPUT_SUPPORT}")"
INPUT_SPECIFICATION_SHA="$(sha256_file "${INPUT_SPECIFICATION}")"

cat <<INFO
============================================================================
run-1b2: analyze repository-level detector eligibility concentration
Started:                       ${START_TEXT}
Workspace:                     ${PROJECT_ROOT}
Active conda env:              ${CONDA_DEFAULT_ENV:-<none>}
Python path:                   ${PYTHON_BIN}
Python version:                ${PYTHON_VERSION}
Python script:                 ${PY_SCRIPT}
Python script SHA:             ${PY_SCRIPT_SHA}
Input events:                  ${INPUT_EVENTS}
Input events SHA:              ${INPUT_EVENTS_SHA}
Input run-1b support:          ${INPUT_SUPPORT}
Input run-1b support SHA:      ${INPUT_SUPPORT_SHA}
Input specification:          ${INPUT_SPECIFICATION}
Input specification SHA:      ${INPUT_SPECIFICATION_SHA}
Analysis specifications:      ${ANALYSIS_SPECS}
Top-N values:                 ${TOP_N_VALUES}
Expected prepared events:     ${EXPECTED_PREPARED_EVENTS}
Expected dataset sources:     ${EXPECTED_DATASET_SOURCES}
Output directory:             ${OUTPUT_DIR}
QC directory:                 ${QC_DIR}
Log file:                     ${LOG_FILE}
Overwrite output:             ${OVERWRITE_OUTPUT}
Run self-test:                ${RUN_SELF_TEST}
============================================================================
INFO

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"

if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test
fi

if [[ -d "${OUTPUT_DIR}" ]] && [[ -n "$(find "${OUTPUT_DIR}" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]] && [[ "${OVERWRITE_OUTPUT}" != "1" ]]; then
    echo "ERROR: Output directory is not empty: ${OUTPUT_DIR}" >&2
    echo "Set OVERWRITE_OUTPUT=1 only after confirming that replacement is intended." >&2
    exit 2
fi

COMMAND=(
    "${PYTHON_BIN}" "${PY_SCRIPT}"
    --input-events "${INPUT_EVENTS}"
    --input-support "${INPUT_SUPPORT}"
    --input-specification "${INPUT_SPECIFICATION}"
    --analysis-specs "${ANALYSIS_SPECS}"
    --top-n-values "${TOP_N_VALUES}"
    --expected-prepared-events "${EXPECTED_PREPARED_EVENTS}"
    --expected-dataset-sources "${EXPECTED_DATASET_SOURCES}"
    --output-dir "${OUTPUT_DIR}"
    --qc-dir "${QC_DIR}"
)

if [[ "${OVERWRITE_OUTPUT}" == "1" ]]; then
    COMMAND+=(--overwrite-output)
fi

"${COMMAND[@]}"

for expected_file in \
    "${REPOSITORY_TABLE}" \
    "${RETENTION_SUMMARY}" \
    "${CONCENTRATION_SUMMARY}" \
    "${LEAVE_TOP_OUT}" \
    "${ZERO_ELIGIBLE}" \
    "${CHECK_OUTPUT}" \
    "${SUMMARY_OUTPUT}" \
    "${METADATA_OUTPUT}"; do
    if [[ ! -f "${expected_file}" ]]; then
        echo "ERROR: Missing expected output: ${expected_file}" >&2
        exit 3
    fi
done

read -r STATUS FAILED_CHECKS PREPARED_EVENTS REPOSITORIES SPEC_COUNT < <(
    "${PYTHON_BIN}" - "${SUMMARY_OUTPUT}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as stream:
    summary = json.load(stream)

print(
    summary["status"],
    summary["failed_checks"],
    summary["prepared_event_rows"],
    summary["repositories"],
    len(summary["analysis_specifications"]),
)
PY
)

if [[ "${STATUS}" != "PASS" ]] || [[ "${FAILED_CHECKS}" != "0" ]]; then
    echo "ERROR: run-1b2 QC failed: status=${STATUS}, failed_checks=${FAILED_CHECKS}" >&2
    exit 4
fi

REPOSITORY_ROWS=$(( $(wc -l < "${REPOSITORY_TABLE}") - 1 ))
LEAVE_TOP_ROWS=$(( $(wc -l < "${LEAVE_TOP_OUT}") - 1 ))
ZERO_ELIGIBLE_ROWS=$(( $(wc -l < "${ZERO_ELIGIBLE}") - 1 ))

cat <<INFO

============================================================================
run-1b2 output verification
Status:                         ${STATUS}
Prepared event rows:            ${PREPARED_EVENTS}
Repositories:                   ${REPOSITORIES}
Specifications:                 ${SPEC_COUNT}
Repository/spec rows:           ${REPOSITORY_ROWS}
Leave-top-out rows:             ${LEAVE_TOP_ROWS}
Zero-eligible repository rows:  ${ZERO_ELIGIBLE_ROWS}
Failed QC checks:               ${FAILED_CHECKS}
Repository table:               ${REPOSITORY_TABLE}
Retention summary:              ${RETENTION_SUMMARY}
Concentration summary:          ${CONCENTRATION_SUMMARY}
Leave-top-out analysis:         ${LEAVE_TOP_OUT}
Zero-eligible repositories:     ${ZERO_ELIGIBLE}
Checks:                         ${CHECK_OUTPUT}
Summary:                        ${SUMMARY_OUTPUT}
Metadata:                       ${METADATA_OUTPUT}
============================================================================
INFO
