#!/usr/bin/env bash

set -euo pipefail

# ============================================================
# run-x-a05 v1: Prepare full historical snapshot NPR inputs
# ============================================================
#
# Delivery naming:
#   proc_sh/run-x-a05-prepare-full-snapshot-npr-inputs-v1.sh
#   code-detection/prepare_full_snapshot_npr_inputs-v1.py
#
# Canonical server naming after removing -v<num>:
#   proc_sh/run-x-a05-prepare-full-snapshot-npr-inputs.sh
#   code-detection/prepare_full_snapshot_npr_inputs.py
#
# Purpose:
#   Expand the validated two-snapshot A01 source-preparation logic to the frozen
#   1,496-snapshot Model C manifest without permanently storing full repository
#   snapshot trees.
#
# Workflow:
#   1. Validate and freeze the Model C snapshot manifest.
#   2. Validate the historical commit in the manifest-provided local clone.
#   3. Create one detached temporary Git worktree on /mnt/samsung850ev.
#   4. Add local snapshot metadata containing the stable quality-pipeline key.
#   5. Invoke the already-validated canonical A01 extractor for one snapshot.
#   6. Promote content-addressed raw code-unit artifacts to the persistent store.
#   7. Retain per-snapshot manifests/QC for resume and remove the full worktree.
#   8. Consolidate successful chunks into A01-compatible global manifests.
#
# Important:
#   - A05 uses Python 3.12+ because the reused A01 extractor performs AST parsing.
#   - A05 does not score NPR and does not create 128-token windows.
#   - A05 does not classify AGC/HWC.
#   - Main treatment/control clone checkouts are never changed.
#   - Tracked .py symlinks are not followed; such snapshots are unresolved for
#     manual review rather than reading outside the temporary worktree.
#
# Required existing server files:
#   code-detection/prepare_snapshot_npr_inputs.py
#   code-detection/prepare_full_snapshot_npr_inputs.py
#
# Primary input:
#   /home/user1-system12/project-workspace/ai_code_complexity_study_python/
#     ai-code-complexity-study/repo_x01/run-x-a05/
#     velocity_did_model_c_snapshot_manifest.csv
#
# Persistent A01-compatible outputs:
#   output/snapshot_npr/run-x-a05/python_snapshot_manifest.csv
#   output/snapshot_npr/run-x-a05/python_file_manifest.csv
#   output/snapshot_npr/run-x-a05/python_code_unit_manifest.csv
#   output/snapshot_npr/run-x-a05/code_units/<sha-prefix>/<sha256>.txt
#
# Resume/provenance outputs:
#   output/snapshot_npr/run-x-a05/snapshot_status.csv
#   output/snapshot_npr/run-x-a05/snapshot_chunks/<snapshot_key>/...
#   output/snapshot_npr/run-x-a05/provenance/velocity_did_model_c_snapshot_manifest.csv
#
# A01-compatible QC outputs:
#   output/snapshot_npr/run-x-a05/qc/python_snapshot_input_checks.csv
#   output/snapshot_npr/run-x-a05/qc/python_snapshot_input_exclusions.csv
#   output/snapshot_npr/run-x-a05/qc/python_snapshot_input_summary.json
#   output/snapshot_npr/run-x-a05/qc/python_snapshot_input_metadata.json
#
# A05 driver QC outputs:
#   output/snapshot_npr/run-x-a05/qc/python_full_snapshot_driver_checks.csv
#   output/snapshot_npr/run-x-a05/qc/python_full_snapshot_driver_unresolved.csv
#   output/snapshot_npr/run-x-a05/qc/python_full_snapshot_driver_summary.json
#   output/snapshot_npr/run-x-a05/qc/python_full_snapshot_driver_metadata.json
#
# Recommended preflight:
#   DRY_RUN=1 bash proc_sh/run-x-a05-prepare-full-snapshot-npr-inputs.sh
#
# Small real smoke run:
#   LIMIT=2 bash proc_sh/run-x-a05-prepare-full-snapshot-npr-inputs.sh
#
# Full run / resume:
#   bash proc_sh/run-x-a05-prepare-full-snapshot-npr-inputs.sh
#
# Optional environment overrides:
#   PROJECT_ROOT
#   PYTHON_BIN
#   PY_SCRIPT
#   A01_SCRIPT
#   INPUT_MANIFEST_FILE
#   OUTPUT_DIR
#   QC_DIR
#   WORKTREE_ROOT
#   LOG_DIR
#   LOG_FILE
#   START_ORDER
#   LIMIT
#   DATASET_SOURCE=treatment|control|empty
#   REPO_NAME=owner/repo|empty
#   ANALYSIS_AGAIN=0|1
#   OVERWRITE_OUTPUT=0|1
#   DRY_RUN=0|1
#   FAIL_ON_UNRESOLVED=0|1
#   STRICT_EXPECTED_COUNTS=0|1
#   REQUIRE_PYTHON_FILE_COUNT_MATCH=0|1
#   SKIP_SELF_TEST=0|1
#   GIT_TIMEOUT_SECONDS
#   A01_TIMEOUT_SECONDS
#   PROGRESS_EVERY
#   PROGRESS_EVERY_FILES
#   MIN_FREE_GB
#   EXPECTED_INPUT_SHA256
#   LOG_LEVEL
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"
export PROJECT_ROOT

RUN_PREFIX="run-x-a05"
IMPLEMENTATION_VERSION="v1"
RUN_LABEL="${RUN_PREFIX}-${IMPLEMENTATION_VERSION}"
RUN_TS="${RUN_TS:-$(date +%Y%m%d-%H%M%S)}"

PYTHON_BIN="${PYTHON_BIN:-/home/user1-system12/miniconda3/envs/agcparse312/bin/python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/prepare_full_snapshot_npr_inputs.py}"
A01_SCRIPT="${A01_SCRIPT:-code-detection/prepare_snapshot_npr_inputs.py}"

INPUT_MANIFEST_FILE="${INPUT_MANIFEST_FILE:-/home/user1-system12/project-workspace/ai_code_complexity_study_python/ai-code-complexity-study/repo_x01/run-x-a05/velocity_did_model_c_snapshot_manifest.csv}"
EXPECTED_INPUT_SHA256="${EXPECTED_INPUT_SHA256:-0f730c56479dc7cc04b4e3ffb6e2d763c30d2017967712e3903926b8e024c51c}"

OUTPUT_DIR="${OUTPUT_DIR:-output/snapshot_npr/${RUN_PREFIX}}"
QC_DIR="${QC_DIR:-${OUTPUT_DIR}/qc}"
WORKTREE_ROOT="${WORKTREE_ROOT:-/mnt/samsung850ev/project-workspace/tmp/npr-full-worktrees}"
LOG_DIR="${LOG_DIR:-logs/${RUN_PREFIX}}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/${RUN_LABEL}-prepare-full-snapshot-npr-inputs-${RUN_TS}.log}"

STATUS_OUTPUT="${STATUS_OUTPUT:-${OUTPUT_DIR}/snapshot_status.csv}"
UNRESOLVED_OUTPUT="${UNRESOLVED_OUTPUT:-${QC_DIR}/python_full_snapshot_driver_unresolved.csv}"
DRIVER_CHECKS_OUTPUT="${DRIVER_CHECKS_OUTPUT:-${QC_DIR}/python_full_snapshot_driver_checks.csv}"
DRIVER_SUMMARY_OUTPUT="${DRIVER_SUMMARY_OUTPUT:-${QC_DIR}/python_full_snapshot_driver_summary.json}"
DRIVER_METADATA_OUTPUT="${DRIVER_METADATA_OUTPUT:-${QC_DIR}/python_full_snapshot_driver_metadata.json}"

START_ORDER="${START_ORDER:-1}"
LIMIT="${LIMIT:-0}"
DATASET_SOURCE="${DATASET_SOURCE:-}"
REPO_NAME="${REPO_NAME:-}"
ANALYSIS_AGAIN="${ANALYSIS_AGAIN:-0}"
OVERWRITE_OUTPUT="${OVERWRITE_OUTPUT:-0}"
DRY_RUN="${DRY_RUN:-0}"
FAIL_ON_UNRESOLVED="${FAIL_ON_UNRESOLVED:-0}"
STRICT_EXPECTED_COUNTS="${STRICT_EXPECTED_COUNTS:-1}"
REQUIRE_PYTHON_FILE_COUNT_MATCH="${REQUIRE_PYTHON_FILE_COUNT_MATCH:-1}"
SKIP_SELF_TEST="${SKIP_SELF_TEST:-0}"
GIT_TIMEOUT_SECONDS="${GIT_TIMEOUT_SECONDS:-300}"
A01_TIMEOUT_SECONDS="${A01_TIMEOUT_SECONDS:-3600}"
PROGRESS_EVERY="${PROGRESS_EVERY:-25}"
PROGRESS_EVERY_FILES="${PROGRESS_EVERY_FILES:-500}"
MIN_FREE_GB="${MIN_FREE_GB:-20}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

EXPECTED_SNAPSHOTS="${EXPECTED_SNAPSHOTS:-1496}"
EXPECTED_TREATMENT_SNAPSHOTS="${EXPECTED_TREATMENT_SNAPSHOTS:-790}"
EXPECTED_CONTROL_SNAPSHOTS="${EXPECTED_CONTROL_SNAPSHOTS:-706}"
EXPECTED_REPO_MONTH_ROWS="${EXPECTED_REPO_MONTH_ROWS:-1954}"
EXPECTED_TREATMENT_REPO_MONTH_ROWS="${EXPECTED_TREATMENT_REPO_MONTH_ROWS:-914}"
EXPECTED_CONTROL_REPO_MONTH_ROWS="${EXPECTED_CONTROL_REPO_MONTH_ROWS:-1040}"
EXPECTED_REPOSITORIES="${EXPECTED_REPOSITORIES:-167}"
EXPECTED_TREATMENT_REPOSITORIES="${EXPECTED_TREATMENT_REPOSITORIES:-63}"
EXPECTED_CONTROL_REPOSITORIES="${EXPECTED_CONTROL_REPOSITORIES:-104}"

require_file() {
    local path="$1"
    local label="$2"
    if [[ ! -f "${path}" ]]; then
        echo "ERROR: Missing ${label}: ${path}" >&2
        exit 2
    fi
}

validate_nonnegative_integer() {
    local value="$1"
    local label="$2"
    if [[ ! "${value}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: ${label} must be a non-negative integer. Got: ${value}" >&2
        exit 2
    fi
}

validate_bool01() {
    local value="$1"
    local label="$2"
    case "${value}" in
        0|1) ;;
        *)
            echo "ERROR: ${label} must be 0 or 1. Got: ${value}" >&2
            exit 2
            ;;
    esac
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

require_file "${PY_SCRIPT}" "A05 Python implementation"
require_file "${A01_SCRIPT}" "canonical A01 Python implementation"
require_file "${INPUT_MANIFEST_FILE}" "frozen Model C snapshot manifest"

for numeric in \
    START_ORDER LIMIT GIT_TIMEOUT_SECONDS A01_TIMEOUT_SECONDS PROGRESS_EVERY \
    PROGRESS_EVERY_FILES EXPECTED_SNAPSHOTS EXPECTED_TREATMENT_SNAPSHOTS \
    EXPECTED_CONTROL_SNAPSHOTS EXPECTED_REPO_MONTH_ROWS \
    EXPECTED_TREATMENT_REPO_MONTH_ROWS EXPECTED_CONTROL_REPO_MONTH_ROWS \
    EXPECTED_REPOSITORIES EXPECTED_TREATMENT_REPOSITORIES \
    EXPECTED_CONTROL_REPOSITORIES; do
    validate_nonnegative_integer "${!numeric}" "${numeric}"
done
if [[ "${START_ORDER}" -lt 1 ]]; then
    echo "ERROR: START_ORDER must be at least 1." >&2
    exit 2
fi

for boolean in ANALYSIS_AGAIN OVERWRITE_OUTPUT DRY_RUN FAIL_ON_UNRESOLVED \
    STRICT_EXPECTED_COUNTS REQUIRE_PYTHON_FILE_COUNT_MATCH SKIP_SELF_TEST; do
    validate_bool01 "${!boolean}" "${boolean}"
done

if [[ -n "${DATASET_SOURCE}" && "${DATASET_SOURCE}" != "treatment" && "${DATASET_SOURCE}" != "control" ]]; then
    echo "ERROR: DATASET_SOURCE must be treatment, control, or empty." >&2
    exit 2
fi

if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git is required but was not found in PATH." >&2
    exit 2
fi

read -r PYTHON_MAJOR PYTHON_MINOR PYTHON_MICRO < <(
    "${PYTHON_BIN}" -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)'
)
PYTHON_VERSION="${PYTHON_MAJOR}.${PYTHON_MINOR}.${PYTHON_MICRO}"
if (( PYTHON_MAJOR < 3 || (PYTHON_MAJOR == 3 && PYTHON_MINOR < 12) )); then
    echo "ERROR: A05/A01 AST extraction requires Python 3.12 or newer; found ${PYTHON_VERSION}." >&2
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
    echo "${RUN_LABEL} execution summary"
    echo "Started:          ${START_TEXT}"
    echo "Completed:        $(date)"
    printf 'Elapsed:          %02d:%02d:%02d\n' "${hours}" "${minutes}" "${seconds}"
    echo "Exit code:        ${exit_code}"
    echo "Python:           ${PYTHON_BIN} (${PYTHON_VERSION})"
    echo "Output directory: ${OUTPUT_DIR}"
    echo "Worktree root:    ${WORKTREE_ROOT}"
    echo "Log file:         ${LOG_FILE}"
    echo "============================================================================"
    exit "${exit_code}"
}
trap finish EXIT
exec > >(tee -a "${LOG_FILE}") 2>&1

PY_SCRIPT_SHA256="$(sha256sum "${PY_SCRIPT}" | awk '{print $1}')"
A01_SCRIPT_SHA256="$(sha256sum "${A01_SCRIPT}" | awk '{print $1}')"
INPUT_SHA256="$(sha256sum "${INPUT_MANIFEST_FILE}" | awk '{print $1}')"

cat <<INFO
============================================================================
${RUN_LABEL}: prepare full historical snapshot NPR inputs
Started:                         ${START_TEXT}
Project root:                    ${PROJECT_ROOT}
Active conda env:                ${CONDA_DEFAULT_ENV:-<none>}
AST Python:                      ${PYTHON_BIN} (${PYTHON_VERSION})
Implementation version:          ${IMPLEMENTATION_VERSION}
A05 Python script:               ${PY_SCRIPT}
A05 Python SHA256:               ${PY_SCRIPT_SHA256}
Reused canonical A01 script:     ${A01_SCRIPT}
A01 Python SHA256:               ${A01_SCRIPT_SHA256}
Input manifest:                  ${INPUT_MANIFEST_FILE}
Input manifest SHA256:           ${INPUT_SHA256}
Expected input SHA256:           ${EXPECTED_INPUT_SHA256:-<not-enforced>}
Output directory:                ${OUTPUT_DIR}
QC directory:                    ${QC_DIR}
Temporary worktree root:         ${WORKTREE_ROOT}
Persistent full worktrees:       no
Snapshot status output:          ${STATUS_OUTPUT}
Unresolved output:               ${UNRESOLVED_OUTPUT}
Start order:                     ${START_ORDER}
Limit:                           ${LIMIT}
Dataset-source filter:           ${DATASET_SOURCE:-<all>}
Repository filter:               ${REPO_NAME:-<all>}
Analysis again:                  ${ANALYSIS_AGAIN}
Overwrite output:                ${OVERWRITE_OUTPUT}
Dry run:                         ${DRY_RUN}
Fail on unresolved:              ${FAIL_ON_UNRESOLVED}
Strict expected counts:          ${STRICT_EXPECTED_COUNTS}
Require Python file count match: ${REQUIRE_PYTHON_FILE_COUNT_MATCH}
Minimum free GB:                 ${MIN_FREE_GB}
Expected snapshots:              ${EXPECTED_SNAPSHOTS}
Expected treatment/control:      ${EXPECTED_TREATMENT_SNAPSHOTS}/${EXPECTED_CONTROL_SNAPSHOTS}
Expected repo-month coverage:    ${EXPECTED_REPO_MONTH_ROWS}
Expected repositories:           ${EXPECTED_REPOSITORIES}
Log file:                        ${LOG_FILE}
============================================================================
INFO

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}" "${A01_SCRIPT}"
echo "Python compile: PASS"

if [[ "${SKIP_SELF_TEST}" == "0" ]]; then
    echo
    echo "** Step 1: Internal self-tests"
    echo "------------------------------------------------------------"
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test \
        --input-manifest-file "${INPUT_MANIFEST_FILE}" \
        --a01-script "${A01_SCRIPT}" \
        --python-bin "${PYTHON_BIN}" \
        --output-dir "${OUTPUT_DIR}" \
        --qc-dir "${QC_DIR}" \
        --worktree-root "${WORKTREE_ROOT}" \
        --status-output "${STATUS_OUTPUT}" \
        --unresolved-output "${UNRESOLVED_OUTPUT}" \
        --driver-checks-output "${DRIVER_CHECKS_OUTPUT}" \
        --driver-summary-output "${DRIVER_SUMMARY_OUTPUT}" \
        --driver-metadata-output "${DRIVER_METADATA_OUTPUT}"
    "${PYTHON_BIN}" "${A01_SCRIPT}" --self-test
fi

COMMAND=(
    "${PYTHON_BIN}"
    "${PY_SCRIPT}"
    --input-manifest-file "${INPUT_MANIFEST_FILE}"
    --a01-script "${A01_SCRIPT}"
    --python-bin "${PYTHON_BIN}"
    --output-dir "${OUTPUT_DIR}"
    --qc-dir "${QC_DIR}"
    --worktree-root "${WORKTREE_ROOT}"
    --status-output "${STATUS_OUTPUT}"
    --unresolved-output "${UNRESOLVED_OUTPUT}"
    --driver-checks-output "${DRIVER_CHECKS_OUTPUT}"
    --driver-summary-output "${DRIVER_SUMMARY_OUTPUT}"
    --driver-metadata-output "${DRIVER_METADATA_OUTPUT}"
    --git-timeout-seconds "${GIT_TIMEOUT_SECONDS}"
    --a01-timeout-seconds "${A01_TIMEOUT_SECONDS}"
    --progress-every "${PROGRESS_EVERY}"
    --progress-every-files "${PROGRESS_EVERY_FILES}"
    --start-order "${START_ORDER}"
    --limit "${LIMIT}"
    --min-free-gb "${MIN_FREE_GB}"
    --expected-snapshots "${EXPECTED_SNAPSHOTS}"
    --expected-treatment-snapshots "${EXPECTED_TREATMENT_SNAPSHOTS}"
    --expected-control-snapshots "${EXPECTED_CONTROL_SNAPSHOTS}"
    --expected-repo-month-rows "${EXPECTED_REPO_MONTH_ROWS}"
    --expected-treatment-repo-month-rows "${EXPECTED_TREATMENT_REPO_MONTH_ROWS}"
    --expected-control-repo-month-rows "${EXPECTED_CONTROL_REPO_MONTH_ROWS}"
    --expected-repositories "${EXPECTED_REPOSITORIES}"
    --expected-treatment-repositories "${EXPECTED_TREATMENT_REPOSITORIES}"
    --expected-control-repositories "${EXPECTED_CONTROL_REPOSITORIES}"
    --expected-input-sha256 "${EXPECTED_INPUT_SHA256}"
    --log-level "${LOG_LEVEL}"
)

if [[ -n "${DATASET_SOURCE}" ]]; then
    COMMAND+=(--dataset-source "${DATASET_SOURCE}")
fi
if [[ -n "${REPO_NAME}" ]]; then
    COMMAND+=(--repo-name "${REPO_NAME}")
fi
if [[ "${ANALYSIS_AGAIN}" == "1" ]]; then
    COMMAND+=(--analysis-again)
fi
if [[ "${OVERWRITE_OUTPUT}" == "1" ]]; then
    COMMAND+=(--overwrite-output)
fi
if [[ "${DRY_RUN}" == "1" ]]; then
    COMMAND+=(--dry-run)
fi
if [[ "${FAIL_ON_UNRESOLVED}" == "1" ]]; then
    COMMAND+=(--fail-on-unresolved)
fi
if [[ "${STRICT_EXPECTED_COUNTS}" == "1" ]]; then
    COMMAND+=(--strict-expected-counts)
fi
if [[ "${REQUIRE_PYTHON_FILE_COUNT_MATCH}" == "1" ]]; then
    COMMAND+=(--require-python-file-count-match)
fi

printf '\n** Step 2: Full-snapshot A01 preparation\n'
printf '%s\n' '------------------------------------------------------------'
printf 'Command:'
printf ' %q' "${COMMAND[@]}"
printf '\n\n'
"${COMMAND[@]}"

if [[ "${DRY_RUN}" == "1" ]]; then
    echo "Dry run completed; no A01 extraction outputs were expected."
    exit 0
fi

for required_output in \
    "${OUTPUT_DIR}/python_snapshot_manifest.csv" \
    "${OUTPUT_DIR}/python_file_manifest.csv" \
    "${OUTPUT_DIR}/python_code_unit_manifest.csv" \
    "${QC_DIR}/python_snapshot_input_checks.csv" \
    "${QC_DIR}/python_snapshot_input_exclusions.csv" \
    "${QC_DIR}/python_snapshot_input_summary.json" \
    "${QC_DIR}/python_snapshot_input_metadata.json" \
    "${STATUS_OUTPUT}" \
    "${UNRESOLVED_OUTPUT}" \
    "${DRIVER_CHECKS_OUTPUT}" \
    "${DRIVER_SUMMARY_OUTPUT}" \
    "${DRIVER_METADATA_OUTPUT}"; do
    if [[ ! -f "${required_output}" ]]; then
        echo "ERROR: expected output was not created: ${required_output}" >&2
        exit 1
    fi
done

printf '\n** Step 3: Output summary\n'
printf '%s\n' '------------------------------------------------------------'
wc -l \
    "${OUTPUT_DIR}/python_snapshot_manifest.csv" \
    "${OUTPUT_DIR}/python_file_manifest.csv" \
    "${OUTPUT_DIR}/python_code_unit_manifest.csv" \
    "${STATUS_OUTPUT}" \
    "${UNRESOLVED_OUTPUT}"
echo
cat "${DRIVER_SUMMARY_OUTPUT}"
echo
echo "Driver checks:"
cat "${DRIVER_CHECKS_OUTPUT}"
echo
echo "A01-compatible summary:"
cat "${QC_DIR}/python_snapshot_input_summary.json"
echo
echo "Unresolved preview:"
head -n 11 "${UNRESOLVED_OUTPUT}" || true

echo
echo "Next full scoring command after A05 reaches complete coverage:"
echo "RUN_A01_DIR=${OUTPUT_DIR} bash proc_sh/run-x-a02-score-snapshot-npr.sh"
