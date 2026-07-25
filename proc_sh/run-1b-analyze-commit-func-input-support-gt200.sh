#!/usr/bin/env bash
# Prepare the versioned gt200 eligibility artifacts before NPR scoring.
#
# Workspace:
#   ~/project-workspace/detect_code_gpt
#
# Script:
#   proc_sh/run-1b-analyze-commit-func-input-support-gt200.sh
#
# Purpose:
#   Analyze the completed run-1a outputs for the exact gt200 rule
#   (literal-space tokens >= 201) before StarCoder2-7B scoring by:
#   - reconciling prepared and excluded commit-function events,
#   - auditing all explicit input-preparation exclusions,
#   - characterizing implementation-body size support,
#   - measuring the gt200 eligibility rule by cohort and period,
#   - verifying content-addressed body artifacts, and
#   - estimating the perturbation-scoring workload.
#
# This wrapper is standalone. It reuses the execution and validation structure
# of run-1a but does not call run-1a or another experiment shell wrapper.
#
# This step does not load StarCoder2, generate perturbations, calculate NPR,
# classify AGC/HWC, aggregate final repository-month outcomes, or run DiD.
#
# Main inputs:
#   output/commit_function/run-1a/strict/
#     commit_function_detectcodegpt_input_events.csv
#     commit_function_detectcodegpt_unique_bodies.csv
#     function_bodies/
#     qc/commit_function_detectcodegpt_exclusions.csv
#     qc/commit_function_detectcodegpt_summary.json
#   matched repository-month panel from the DiD workspace
#
# Main outputs:
#   output/commit_function/run-1b/gt200/
#     exclusion audit tables
#     event-level and unique-body size distributions
#     eligibility support tables
#     scoring-cost estimates
#     one-row gt200 support CSV
#     frozen gt200 scoring specification
#     QC checks, summary, metadata, and artifact errors
#
# Optional environment variables:
#   PYTHON_BIN, PY_SCRIPT, RUN1A_DIR, INPUT_EVENTS, INPUT_UNIQUE_BODIES,
#   INPUT_EXCLUSIONS, INPUT_SUMMARY, INPUT_PANEL, BODY_ARTIFACT_BASE,
#   OUTPUT_DIR, QC_DIR, LOG_DIR, NAMED_MINIMUM_TOKEN_SPECS,
#   PRIMARY_SPEC, WINDOW_SIZE,
#   PERTURBATIONS_PER_WINDOW, SCORING_MODEL, AGC_THRESHOLD, RANDOM_SEED,
#   MEASURED_WINDOWS_PER_SECOND, ESTIMATED_CACHE_BYTES_PER_WINDOW,
#   EXPECTED_TOTAL_EVENTS, EXPECTED_PREPARED_EVENTS,
#   EXPECTED_EXCLUDED_EVENTS, EXPECTED_UNIQUE_BODIES,
#   EXPECTED_ELIGIBLE_BODIES, EXPECTED_TOTAL_WINDOWS,
#   VERIFY_BODY_ARTIFACTS, FREEZE_SPECIFICATION, OVERWRITE_OUTPUT,
#   RUN_SELF_TEST
#
# Usage:
#   OVERWRITE_OUTPUT=1 bash proc_sh/run-1b-analyze-commit-func-input-support-gt200.sh
#
# This wrapper is independent. It does not call the original run-1b wrapper
# and it does not modify output/commit_function/run-1b/strict.


set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/analyze_commit_function_input_support-gt200.py}"

RUN1A_DIR="${RUN1A_DIR:-output/commit_function/run-1a/strict}"
INPUT_EVENTS="${INPUT_EVENTS:-${RUN1A_DIR}/commit_function_detectcodegpt_input_events.csv}"
INPUT_UNIQUE_BODIES="${INPUT_UNIQUE_BODIES:-${RUN1A_DIR}/commit_function_detectcodegpt_unique_bodies.csv}"
INPUT_EXCLUSIONS="${INPUT_EXCLUSIONS:-${RUN1A_DIR}/qc/commit_function_detectcodegpt_exclusions.csv}"
INPUT_SUMMARY="${INPUT_SUMMARY:-${RUN1A_DIR}/qc/commit_function_detectcodegpt_summary.json}"
BODY_ARTIFACT_BASE="${BODY_ARTIFACT_BASE:-${RUN1A_DIR}}"

DID_WORKSPACE="${DID_WORKSPACE:-../ai_code_complexity_study_python/ai-code-complexity-study}"
INPUT_PANEL="${INPUT_PANEL:-${DID_WORKSPACE}/repo_python/run-py-4a/strict/panel_event_monthly_agc_changed_block_py.csv}"

OUTPUT_DIR="${OUTPUT_DIR:-output/commit_function/run-1b/gt200}"
QC_DIR="${QC_DIR:-${OUTPUT_DIR}/qc}"
LOG_DIR="${LOG_DIR:-logs/run-1b/gt200}"

MINIMUM_TOKEN_THRESHOLDS=""
NAMED_MINIMUM_TOKEN_SPECS="${NAMED_MINIMUM_TOKEN_SPECS:-gt200:201}"
BOUNDED_TOKEN_RANGES=""
PRIMARY_SPEC="${PRIMARY_SPEC:-gt200}"
WINDOW_SIZE="${WINDOW_SIZE:-128}"
PERTURBATIONS_PER_WINDOW="${PERTURBATIONS_PER_WINDOW:-50}"
SCORING_MODEL="${SCORING_MODEL:-bigcode/starcoder2-7b}"
AGC_THRESHOLD="${AGC_THRESHOLD:-1.5183}"
RANDOM_SEED="${RANDOM_SEED:-20260723}"
MEASURED_WINDOWS_PER_SECOND="${MEASURED_WINDOWS_PER_SECOND:-0}"
ESTIMATED_CACHE_BYTES_PER_WINDOW="${ESTIMATED_CACHE_BYTES_PER_WINDOW:-0}"

EXPECTED_TOTAL_EVENTS="${EXPECTED_TOTAL_EVENTS:-450548}"
EXPECTED_PREPARED_EVENTS="${EXPECTED_PREPARED_EVENTS:-449547}"
EXPECTED_EXCLUDED_EVENTS="${EXPECTED_EXCLUDED_EVENTS:-1001}"
EXPECTED_UNIQUE_BODIES="${EXPECTED_UNIQUE_BODIES:-343192}"

VERIFY_BODY_ARTIFACTS="${VERIFY_BODY_ARTIFACTS:-1}"
FREEZE_SPECIFICATION="${FREEZE_SPECIFICATION:-1}"
OVERWRITE_OUTPUT="${OVERWRITE_OUTPUT:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"

TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/run-1b-analyze-commit-func-input-support-gt200-${TIMESTAMP}.log}"

EXPECTED_SPEC_NAME="${EXPECTED_SPEC_NAME:-gt200}"
EXPECTED_MINIMUM_TOKENS="${EXPECTED_MINIMUM_TOKENS:-201}"
EXPECTED_ELIGIBLE_BODIES="${EXPECTED_ELIGIBLE_BODIES:-154150}"
EXPECTED_TOTAL_WINDOWS="${EXPECTED_TOTAL_WINDOWS:-1025732}"
EXPECTED_SPECIFICATIONS="${EXPECTED_SPECIFICATIONS:-1}"
EXPECTED_ARTIFACT_ERRORS="${EXPECTED_ARTIFACT_ERRORS:-0}"

EXCLUSION_SUMMARY="${OUTPUT_DIR}/commit_function_input_exclusion_summary.csv"
EXCLUSIONS_ENRICHED="${OUTPUT_DIR}/commit_function_input_exclusions_enriched.csv"
EVENT_SIZE_DISTRIBUTION="${OUTPUT_DIR}/commit_function_body_size_distribution_events.csv"
BODY_SIZE_DISTRIBUTION="${OUTPUT_DIR}/commit_function_body_size_distribution_unique_bodies.csv"
ELIGIBILITY_SUPPORT="${OUTPUT_DIR}/commit_function_body_eligibility_support.csv"
ELIGIBILITY_BY_COHORT="${OUTPUT_DIR}/commit_function_body_eligibility_by_cohort.csv"
ELIGIBILITY_BY_PERIOD="${OUTPUT_DIR}/commit_function_body_eligibility_by_period.csv"
ELIGIBILITY_BY_FUNCTION="${OUTPUT_DIR}/commit_function_body_eligibility_by_function_category.csv"
ELIGIBILITY_BY_CHANGE="${OUTPUT_DIR}/commit_function_body_eligibility_by_change_type.csv"
SCORING_COST="${OUTPUT_DIR}/commit_function_npr_scoring_cost_estimates.csv"
CHECK_OUTPUT="${QC_DIR}/commit_function_input_support_checks.csv"
ARTIFACT_ERROR_OUTPUT="${QC_DIR}/commit_function_body_artifact_errors.csv"
SUMMARY_OUTPUT="${QC_DIR}/commit_function_input_support_summary.json"
METADATA_OUTPUT="${QC_DIR}/commit_function_input_support_metadata.json"

if [[ "${FREEZE_SPECIFICATION}" == "1" ]]; then
    SPEC_OUTPUT="${OUTPUT_DIR}/commit_function_detectcodegpt_scoring_spec.json"
else
    SPEC_OUTPUT="${OUTPUT_DIR}/commit_function_detectcodegpt_candidate_scoring_spec.json"
fi

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

require_file "${PY_SCRIPT}" "Python input-support script"
require_file "${INPUT_EVENTS}" "run-1a event output"
require_file "${INPUT_UNIQUE_BODIES}" "run-1a unique-body output"
require_file "${INPUT_EXCLUSIONS}" "run-1a exclusion output"
require_file "${INPUT_SUMMARY}" "run-1a summary"
require_file "${INPUT_PANEL}" "matched repository-month panel"
require_dir "${BODY_ARTIFACT_BASE}" "run-1a body artifact base"

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
    echo "run-1b gt200 execution summary"
    echo "Started:          ${START_TEXT}"
    echo "Completed:        $(date)"
    printf 'Elapsed:          %02d:%02d:%02d\n' "${hours}" "${minutes}" "${seconds}"
    echo "Exit code:        ${exit_code}"
    echo "Python path:      ${PYTHON_BIN}"
    echo "Python version:   ${PYTHON_VERSION}"
    echo "Script path:      ${PY_SCRIPT}"
    echo "Input run-1a dir: ${RUN1A_DIR}"
    echo "Input panel:      ${INPUT_PANEL}"
    echo "Output directory: ${OUTPUT_DIR}"
    echo "QC directory:     ${QC_DIR}"
    echo "Log file:         ${LOG_FILE}"
    echo "============================================================================"
    exit "${exit_code}"
}

trap finish EXIT
exec > >(tee -a "${LOG_FILE}") 2>&1

PY_SCRIPT_SHA="$(sha256_file "${PY_SCRIPT}")"
INPUT_EVENTS_SHA="$(sha256_file "${INPUT_EVENTS}")"
INPUT_UNIQUE_BODIES_SHA="$(sha256_file "${INPUT_UNIQUE_BODIES}")"
INPUT_EXCLUSIONS_SHA="$(sha256_file "${INPUT_EXCLUSIONS}")"
INPUT_SUMMARY_SHA="$(sha256_file "${INPUT_SUMMARY}")"
INPUT_PANEL_SHA="$(sha256_file "${INPUT_PANEL}")"

cat <<INFO
============================================================================
run-1b gt200: prepare perturbation-detector input support
Started:                         ${START_TEXT}
Workspace:                       ${PROJECT_ROOT}
Active conda env:                ${CONDA_DEFAULT_ENV:-<none>}
Python path:                     ${PYTHON_BIN}
Python version:                  ${PYTHON_VERSION}
Python script:                   ${PY_SCRIPT}
Python script SHA:               ${PY_SCRIPT_SHA}
Input events:                    ${INPUT_EVENTS}
Input events SHA:                ${INPUT_EVENTS_SHA}
Input unique bodies:             ${INPUT_UNIQUE_BODIES}
Input unique bodies SHA:         ${INPUT_UNIQUE_BODIES_SHA}
Input exclusions:                ${INPUT_EXCLUSIONS}
Input exclusions SHA:            ${INPUT_EXCLUSIONS_SHA}
Input run-1a summary:            ${INPUT_SUMMARY}
Input run-1a summary SHA:        ${INPUT_SUMMARY_SHA}
Matched panel:                   ${INPUT_PANEL}
Matched panel SHA:               ${INPUT_PANEL_SHA}
Body artifact base:              ${BODY_ARTIFACT_BASE}
Minimum token thresholds:        ${MINIMUM_TOKEN_THRESHOLDS}
Named minimum-token specs:       ${NAMED_MINIMUM_TOKEN_SPECS}
Bounded token ranges:            ${BOUNDED_TOKEN_RANGES:-<none>}
Primary specification:           ${PRIMARY_SPEC}
Window size:                     ${WINDOW_SIZE}
Perturbations per window:        ${PERTURBATIONS_PER_WINDOW}
Scoring model:                   ${SCORING_MODEL}
AGC threshold:                   ${AGC_THRESHOLD}
Random seed:                     ${RANDOM_SEED}
Measured windows per second:     ${MEASURED_WINDOWS_PER_SECOND}
Estimated cache bytes/window:    ${ESTIMATED_CACHE_BYTES_PER_WINDOW}
Verify body artifacts:           ${VERIFY_BODY_ARTIFACTS}
Freeze specification:            ${FREEZE_SPECIFICATION}
Expected total events:           ${EXPECTED_TOTAL_EVENTS}
Expected prepared events:        ${EXPECTED_PREPARED_EVENTS}
Expected excluded events:        ${EXPECTED_EXCLUDED_EVENTS}
Expected unique bodies:          ${EXPECTED_UNIQUE_BODIES}
Expected gt200 bodies:            ${EXPECTED_ELIGIBLE_BODIES}
Expected gt200 windows:           ${EXPECTED_TOTAL_WINDOWS}
Output directory:                ${OUTPUT_DIR}
QC directory:                    ${QC_DIR}
Specification output:            ${SPEC_OUTPUT}
Log file:                        ${LOG_FILE}
============================================================================
INFO

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"
if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test
fi

command=(
    "${PYTHON_BIN}" "${PY_SCRIPT}"
    --input-events "${INPUT_EVENTS}"
    --input-unique-bodies "${INPUT_UNIQUE_BODIES}"
    --input-exclusions "${INPUT_EXCLUSIONS}"
    --input-summary "${INPUT_SUMMARY}"
    --input-panel "${INPUT_PANEL}"
    --body-artifact-base "${BODY_ARTIFACT_BASE}"
    --output-dir "${OUTPUT_DIR}"
    --qc-dir "${QC_DIR}"
    --minimum-token-thresholds "${MINIMUM_TOKEN_THRESHOLDS}"
    --named-minimum-token-specs "${NAMED_MINIMUM_TOKEN_SPECS}"
    --bounded-token-ranges "${BOUNDED_TOKEN_RANGES}"
    --primary-spec "${PRIMARY_SPEC}"
    --no-include-all-positive
    --window-size "${WINDOW_SIZE}"
    --perturbations-per-window "${PERTURBATIONS_PER_WINDOW}"
    --scoring-model "${SCORING_MODEL}"
    --agc-threshold "${AGC_THRESHOLD}"
    --random-seed "${RANDOM_SEED}"
    --measured-windows-per-second "${MEASURED_WINDOWS_PER_SECOND}"
    --estimated-cache-bytes-per-window "${ESTIMATED_CACHE_BYTES_PER_WINDOW}"
    --expected-total-events "${EXPECTED_TOTAL_EVENTS}"
    --expected-prepared-events "${EXPECTED_PREPARED_EVENTS}"
    --expected-excluded-events "${EXPECTED_EXCLUDED_EVENTS}"
    --expected-unique-bodies "${EXPECTED_UNIQUE_BODIES}"
)

if [[ "${VERIFY_BODY_ARTIFACTS}" == "1" ]]; then
    command+=(--verify-body-artifacts)
else
    command+=(--no-verify-body-artifacts)
fi
if [[ "${FREEZE_SPECIFICATION}" == "1" ]]; then
    command+=(--freeze-specification)
fi
if [[ "${OVERWRITE_OUTPUT}" == "1" ]]; then
    command+=(--overwrite-output)
fi

PYTHONUNBUFFERED=1 "${command[@]}"

for required_output in \
    "${EXCLUSION_SUMMARY}" \
    "${EXCLUSIONS_ENRICHED}" \
    "${EVENT_SIZE_DISTRIBUTION}" \
    "${BODY_SIZE_DISTRIBUTION}" \
    "${ELIGIBILITY_SUPPORT}" \
    "${ELIGIBILITY_BY_COHORT}" \
    "${ELIGIBILITY_BY_PERIOD}" \
    "${ELIGIBILITY_BY_FUNCTION}" \
    "${ELIGIBILITY_BY_CHANGE}" \
    "${SCORING_COST}" \
    "${CHECK_OUTPUT}" \
    "${ARTIFACT_ERROR_OUTPUT}" \
    "${SUMMARY_OUTPUT}" \
    "${METADATA_OUTPUT}" \
    "${SPEC_OUTPUT}"; do
    require_file "${required_output}" "run-1b output"
done

read -r STATUS TOTAL PREPARED EXCLUDED UNIQUE_BODIES PANEL_MONTHS EVENT_MONTHS SPECS FAILED_CHECKS < <(
    "${PYTHON_BIN}" - "${SUMMARY_OUTPUT}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as stream:
    summary = json.load(stream)
print(
    summary["status"],
    summary["total_event_rows"],
    summary["prepared_event_rows"],
    summary["explicit_exclusion_rows"],
    summary["unique_body_rows"],
    summary["total_panel_repository_months"],
    summary["prepared_event_positive_repository_months"],
    summary["eligibility_specifications"],
    summary["failed_checks"],
)
PY
)

cat <<INFO

============================================================================
run-1b output verification
Status:                         ${STATUS}
Total run-1a event rows:        ${TOTAL}
Prepared event rows:            ${PREPARED}
Explicit exclusion rows:        ${EXCLUDED}
Unique implementation bodies:   ${UNIQUE_BODIES}
Complete panel repo-months:      ${PANEL_MONTHS}
Event-positive repo-months:      ${EVENT_MONTHS}
Eligibility specifications:     ${SPECS}
Failed QC checks:                ${FAILED_CHECKS}
Eligibility support:             ${ELIGIBILITY_SUPPORT}
Scoring cost estimates:          ${SCORING_COST}
Checks:                           ${CHECK_OUTPUT}
Summary:                          ${SUMMARY_OUTPUT}
Specification:                    ${SPEC_OUTPUT}
============================================================================
INFO

if [[ "${STATUS}" != "PASS" ]]; then
    echo "ERROR: run-1b completed with failed QC checks." >&2
    exit 1
fi
if [[ "${FAILED_CHECKS}" != "0" ]]; then
    echo "ERROR: run-1b reported failed QC checks." >&2
    exit 1
fi

read -r \
    OBSERVED_SPEC_NAME \
    OBSERVED_MINIMUM_TOKENS \
    OBSERVED_MAXIMUM_TOKENS \
    OBSERVED_ELIGIBLE_BODIES \
    OBSERVED_TOTAL_WINDOWS \
    OBSERVED_SUPPORT_ROWS \
    OBSERVED_ARTIFACT_ERRORS \
    OBSERVED_PRIMARY_SPEC \
    OBSERVED_SPEC_COUNT < <(
    "${PYTHON_BIN}" - \
        "${ELIGIBILITY_SUPPORT}" \
        "${ARTIFACT_ERROR_OUTPUT}" \
        "${SPEC_OUTPUT}" <<'PY'
import csv
import json
import sys

support_path, artifact_error_path, specification_path = sys.argv[1:4]

with open(support_path, "r", encoding="utf-8", newline="") as stream:
    support_rows = list(csv.DictReader(stream))
if len(support_rows) != 1:
    row = {}
else:
    row = support_rows[0]

with open(artifact_error_path, "r", encoding="utf-8", newline="") as stream:
    artifact_error_rows = list(csv.DictReader(stream))

with open(specification_path, "r", encoding="utf-8") as stream:
    specification = json.load(stream)

maximum = str(row.get("maximum_literal_space_tokens", "")).strip()
print(
    row.get("spec_name", "<missing>"),
    row.get("minimum_literal_space_tokens", "<missing>"),
    maximum if maximum else "NONE",
    row.get("eligible_unique_bodies", "<missing>"),
    row.get("total_windows", "<missing>"),
    len(support_rows),
    len(artifact_error_rows),
    specification.get("primary_spec", "<missing>"),
    len(specification.get("eligibility_specifications", [])),
)
PY
)

cat <<INFO

============================================================================
gt200 boundary and workload verification
Specification name:             ${OBSERVED_SPEC_NAME}
Minimum literal-space tokens:   ${OBSERVED_MINIMUM_TOKENS}
Maximum literal-space tokens:   ${OBSERVED_MAXIMUM_TOKENS}
Eligible unique bodies:         ${OBSERVED_ELIGIBLE_BODIES}
Total windows:                  ${OBSERVED_TOTAL_WINDOWS}
Support rows:                   ${OBSERVED_SUPPORT_ROWS}
Artifact error rows:            ${OBSERVED_ARTIFACT_ERRORS}
Frozen primary specification:   ${OBSERVED_PRIMARY_SPEC}
Frozen specification count:     ${OBSERVED_SPEC_COUNT}
============================================================================
INFO

if [[ "${SPECS}" != "${EXPECTED_SPECIFICATIONS}" ]]; then
    echo "ERROR: Expected ${EXPECTED_SPECIFICATIONS} eligibility specification; found ${SPECS}." >&2
    exit 1
fi
if [[ "${OBSERVED_SPEC_NAME}" != "${EXPECTED_SPEC_NAME}" ]]; then
    echo "ERROR: Expected specification ${EXPECTED_SPEC_NAME}; found ${OBSERVED_SPEC_NAME}." >&2
    exit 1
fi
if [[ "${OBSERVED_MINIMUM_TOKENS}" != "${EXPECTED_MINIMUM_TOKENS}" ]]; then
    echo "ERROR: Expected minimum ${EXPECTED_MINIMUM_TOKENS}; found ${OBSERVED_MINIMUM_TOKENS}." >&2
    exit 1
fi
if [[ "${OBSERVED_MAXIMUM_TOKENS}" != "NONE" ]]; then
    echo "ERROR: gt200 must not have a maximum token boundary." >&2
    exit 1
fi
if [[ "${OBSERVED_ELIGIBLE_BODIES}" != "${EXPECTED_ELIGIBLE_BODIES}" ]]; then
    echo "ERROR: Expected ${EXPECTED_ELIGIBLE_BODIES} gt200 bodies; found ${OBSERVED_ELIGIBLE_BODIES}." >&2
    exit 1
fi
if [[ "${OBSERVED_TOTAL_WINDOWS}" != "${EXPECTED_TOTAL_WINDOWS}" ]]; then
    echo "ERROR: Expected ${EXPECTED_TOTAL_WINDOWS} gt200 windows; found ${OBSERVED_TOTAL_WINDOWS}." >&2
    exit 1
fi
if [[ "${OBSERVED_SUPPORT_ROWS}" != "${EXPECTED_SPECIFICATIONS}" ]]; then
    echo "ERROR: Expected a one-row gt200 support CSV; found ${OBSERVED_SUPPORT_ROWS} rows." >&2
    exit 1
fi
if [[ "${OBSERVED_ARTIFACT_ERRORS}" != "${EXPECTED_ARTIFACT_ERRORS}" ]]; then
    echo "ERROR: Expected no artifact errors; found ${OBSERVED_ARTIFACT_ERRORS}." >&2
    exit 1
fi
if [[ "${OBSERVED_PRIMARY_SPEC}" != "${EXPECTED_SPEC_NAME}" ]]; then
    echo "ERROR: Frozen primary specification is ${OBSERVED_PRIMARY_SPEC}, not ${EXPECTED_SPEC_NAME}." >&2
    exit 1
fi
if [[ "${OBSERVED_SPEC_COUNT}" != "${EXPECTED_SPECIFICATIONS}" ]]; then
    echo "ERROR: Frozen specification JSON must contain exactly one specification." >&2
    exit 1
fi

echo "gt200 verification: PASS"
