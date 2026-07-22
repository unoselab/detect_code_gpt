#!/usr/bin/env bash
# Prepare original implementation-body inputs for perturbation-based AGC detection.
#
# Workspace:
#   ~/project-workspace/detect_code_gpt
#
# Versioned delivery file:
#   proc_sh/run-1a-prepare-input-commit-func-v1.sh
#
# Canonical path:
#   proc_sh/run-1a-prepare-input-commit-func.sh
#
# Purpose:
#   Reconnect every approved Python commit-function change event to its original
#   post-commit Git blob and extract the original implementation body while
#   preserving spaces, indentation, line breaks, and source-level style.
#
# Important source policy:
#   - The approved event manifest is read from the DiD workspace.
#   - Existing commit_function_sources artifacts are not detector inputs because
#     they were rendered with ast.unparse().
#   - Python AST is used only to locate and validate the approved function.
#   - The saved detector input is an exact raw source slice.
#
# This step does not load StarCoder2, generate perturbations, compute NPR,
# classify AGC/HWC, aggregate repository-month outcomes, or run DiD.
#
# Main inputs:
#   - run-py-5a-py312 commit-function event manifest
#   - treatment and control Git clones
#
# Main outputs:
#   - event-level input manifest
#   - content-addressed unique implementation-body artifacts
#   - unique-body manifest
#   - Git-blob and repository-month audits
#   - exclusions, checks, summary, and metadata
#
# Optional environment variables:
#   PYTHON_BIN, PY_SCRIPT, INPUT_MANIFEST, TREATMENT_CLONE_DIR,
#   CONTROL_CLONE_DIR, OUTPUT_DIR, QC_DIR, LOG_DIR, EVENT_ID_FILE,
#   MAX_EVENTS, EXPECTED_MANIFEST_ROWS, PROGRESS_EVERY_BLOBS,
#   OVERWRITE_OUTPUT, RUN_SELF_TEST
# 
# Usage:
# PYTHON_BIN=/home/user1-system12/miniconda3/envs/agcparse312/bin/python MAX_EVENTS=10 OUTPUT_DIR=output/commit_function/run-1a/smoke10 OVERWRITE_OUTPUT=1 bash proc_sh/run-1a-prepare-input-commit-func.sh
# 
# PYTHON_BIN=/home/user1-system12/miniconda3/envs/agcparse312/bin/python MAX_EVENTS=100 OUTPUT_DIR=output/commit_function/run-1a/smoke100 OVERWRITE_OUTPUT=1 bash proc_sh/run-1a-prepare-input-commit-func.sh
# 

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/prepare_input_commit_func.py}"

DID_WORKSPACE="${DID_WORKSPACE:-../ai_code_complexity_study_python/ai-code-complexity-study}"
INPUT_MANIFEST="${INPUT_MANIFEST:-${DID_WORKSPACE}/repo_python/run-py-5a-py312/strict/commit_function_detection_manifest.csv}"
TREATMENT_CLONE_DIR="${TREATMENT_CLONE_DIR:-../ai_code_complexity_study_python/treatment-repos}"
CONTROL_CLONE_DIR="${CONTROL_CLONE_DIR:-../ai_code_complexity_study_python/control-repos}"

OUTPUT_DIR="${OUTPUT_DIR:-output/commit_function/run-1a/strict}"
QC_DIR="${QC_DIR:-${OUTPUT_DIR}/qc}"
LOG_DIR="${LOG_DIR:-logs/run-1a}"

EXPECTED_MANIFEST_ROWS="${EXPECTED_MANIFEST_ROWS:-450548}"
PROGRESS_EVERY_BLOBS="${PROGRESS_EVERY_BLOBS:-1000}"
EVENT_ID_FILE="${EVENT_ID_FILE:-}"
MAX_EVENTS="${MAX_EVENTS:-0}"
OVERWRITE_OUTPUT="${OVERWRITE_OUTPUT:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"

TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/run-1a-prepare-input-commit-func-${TIMESTAMP}.log}"

EVENT_OUTPUT="${OUTPUT_DIR}/commit_function_detectcodegpt_input_events.csv"
UNIQUE_BODY_OUTPUT="${OUTPUT_DIR}/commit_function_detectcodegpt_unique_bodies.csv"
BLOB_AUDIT_OUTPUT="${OUTPUT_DIR}/commit_function_detectcodegpt_blob_audit.csv"
REPO_MONTH_AUDIT_OUTPUT="${OUTPUT_DIR}/commit_function_detectcodegpt_repo_month_audit.csv"
EXCLUSION_OUTPUT="${QC_DIR}/commit_function_detectcodegpt_exclusions.csv"
CHECK_OUTPUT="${QC_DIR}/commit_function_detectcodegpt_checks.csv"
SUMMARY_OUTPUT="${QC_DIR}/commit_function_detectcodegpt_summary.json"
METADATA_OUTPUT="${QC_DIR}/commit_function_detectcodegpt_metadata.json"
BODY_ROOT="${OUTPUT_DIR}/function_bodies"

require_file() {
    local path="$1"
    local label="$2"
    if [[ ! -f "${path}" ]]; then
        echo "ERROR: Missing ${label}: ${path}" >&2
        exit 2
    fi
}

require_dir() {
    local path="$1"
    local label="$2"
    if [[ ! -d "${path}" ]]; then
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

require_file "${PY_SCRIPT}" "Python preparation script"
require_file "${INPUT_MANIFEST}" "approved commit-function event manifest"
require_dir "${TREATMENT_CLONE_DIR}" "treatment clone directory"
require_dir "${CONTROL_CLONE_DIR}" "control clone directory"
if [[ -n "${EVENT_ID_FILE}" ]]; then
    require_file "${EVENT_ID_FILE}" "event ID selection file"
fi

read -r PYTHON_MAJOR PYTHON_MINOR PYTHON_MICRO < <(
    "${PYTHON_BIN}" -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)'
)
PYTHON_VERSION="${PYTHON_MAJOR}.${PYTHON_MINOR}.${PYTHON_MICRO}"
if (( PYTHON_MAJOR < 3 || (PYTHON_MAJOR == 3 && PYTHON_MINOR < 12) )); then
    echo "ERROR: Python 3.12 or newer is required; found ${PYTHON_VERSION}." >&2
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
    echo "run-1a execution summary"
    echo "Started:          ${START_TEXT}"
    echo "Completed:        $(date)"
    printf 'Elapsed:          %02d:%02d:%02d\n' "${hours}" "${minutes}" "${seconds}"
    echo "Exit code:        ${exit_code}"
    echo "Python path:      ${PYTHON_BIN}"
    echo "Python version:   ${PYTHON_VERSION}"
    echo "Script path:      ${PY_SCRIPT}"
    echo "Input manifest:   ${INPUT_MANIFEST}"
    echo "Output directory: ${OUTPUT_DIR}"
    echo "QC directory:     ${QC_DIR}"
    echo "Log file:         ${LOG_FILE}"
    echo "============================================================================"
    exit "${exit_code}"
}

trap finish EXIT
exec > >(tee -a "${LOG_FILE}") 2>&1

PY_SCRIPT_SHA="$(sha256_file "${PY_SCRIPT}")"
INPUT_MANIFEST_SHA="$(sha256_file "${INPUT_MANIFEST}")"

cat <<INFO
============================================================================
run-1a: prepare original commit-function implementation-body inputs
Started:                ${START_TEXT}
Workspace:              ${PROJECT_ROOT}
Active conda env:       ${CONDA_DEFAULT_ENV:-<none>}
Python path:            ${PYTHON_BIN}
Python version:         ${PYTHON_VERSION}
Python script:          ${PY_SCRIPT}
Python script SHA:      ${PY_SCRIPT_SHA}
Input manifest:         ${INPUT_MANIFEST}
Input manifest SHA:     ${INPUT_MANIFEST_SHA}
Expected manifest rows: ${EXPECTED_MANIFEST_ROWS}
Treatment clones:       ${TREATMENT_CLONE_DIR}
Control clones:         ${CONTROL_CLONE_DIR}
Event ID file:          ${EVENT_ID_FILE:-<none>}
Maximum selected events:${MAX_EVENTS}
Output directory:       ${OUTPUT_DIR}
Body artifact root:     ${BODY_ROOT}
QC directory:           ${QC_DIR}
Event output:           ${EVENT_OUTPUT}
Unique body output:     ${UNIQUE_BODY_OUTPUT}
Blob audit:             ${BLOB_AUDIT_OUTPUT}
Repository-month audit: ${REPO_MONTH_AUDIT_OUTPUT}
Exclusions:             ${EXCLUSION_OUTPUT}
Checks:                 ${CHECK_OUTPUT}
Summary:                ${SUMMARY_OUTPUT}
Metadata:               ${METADATA_OUTPUT}
Log file:               ${LOG_FILE}
============================================================================
INFO

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"
if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test
fi

command=(
    "${PYTHON_BIN}" "${PY_SCRIPT}"
    --input-manifest "${INPUT_MANIFEST}"
    --treatment-clone-dir "${TREATMENT_CLONE_DIR}"
    --control-clone-dir "${CONTROL_CLONE_DIR}"
    --output-dir "${OUTPUT_DIR}"
    --qc-dir "${QC_DIR}"
    --expected-manifest-rows "${EXPECTED_MANIFEST_ROWS}"
    --progress-every-blobs "${PROGRESS_EVERY_BLOBS}"
    --max-events "${MAX_EVENTS}"
)

if [[ -n "${EVENT_ID_FILE}" ]]; then
    command+=(--event-id-file "${EVENT_ID_FILE}")
fi
if [[ "${OVERWRITE_OUTPUT}" == "1" ]]; then
    command+=(--overwrite-output)
fi

PYTHONUNBUFFERED=1 "${command[@]}"

for required_output in \
    "${EVENT_OUTPUT}" \
    "${UNIQUE_BODY_OUTPUT}" \
    "${BLOB_AUDIT_OUTPUT}" \
    "${REPO_MONTH_AUDIT_OUTPUT}" \
    "${EXCLUSION_OUTPUT}" \
    "${CHECK_OUTPUT}" \
    "${SUMMARY_OUTPUT}" \
    "${METADATA_OUTPUT}"; do
    require_file "${required_output}" "run-1a output"
done
require_dir "${BODY_ROOT}" "implementation-body artifact directory"

read -r STATUS SELECTED PREPARED EXCLUDED UNIQUE_BODIES FAILED_CHECKS < <(
    "${PYTHON_BIN}" - "${SUMMARY_OUTPUT}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as stream:
    summary = json.load(stream)
print(
    summary["status"],
    summary["selected_event_rows"],
    summary["prepared_events"],
    summary["excluded_events"],
    summary["unique_bodies"],
    summary["failed_checks"],
)
PY
)

cat <<INFO

============================================================================
run-1a output verification
Status:                       ${STATUS}
Selected commit-function rows:${SELECTED}
Prepared event inputs:        ${PREPARED}
Excluded event inputs:        ${EXCLUDED}
Unique implementation bodies: ${UNIQUE_BODIES}
Failed QC checks:             ${FAILED_CHECKS}
Event output:                 ${EVENT_OUTPUT}
Unique body output:           ${UNIQUE_BODY_OUTPUT}
Checks:                       ${CHECK_OUTPUT}
Summary:                      ${SUMMARY_OUTPUT}
============================================================================
INFO

if [[ "${STATUS}" != "PASS" && "${STATUS}" != "PASS_WITH_EXCLUSIONS" ]]; then
    echo "ERROR: run-1a completed with failed QC checks." >&2
    exit 1
fi
if [[ "${FAILED_CHECKS}" != "0" ]]; then
    echo "ERROR: run-1a reported failed QC checks." >&2
    exit 1
fi
