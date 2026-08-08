#!/usr/bin/env bash

set -euo pipefail

# ============================================================
# run-x-a01 v1: Prepare raw Python snapshot inputs for NPR
# ============================================================
#
# Delivery naming:
#   proc_sh/run-x-a01-prepare-snapshot-npr-inputs-v1.sh
#   code-detection/prepare_snapshot_npr_inputs-v1.py
#
# Canonical server naming after removing the version suffix:
#   proc_sh/run-x-a01-prepare-snapshot-npr-inputs.sh
#   code-detection/prepare_snapshot_npr_inputs.py
#
# The wrapper intentionally calls the canonical Python filename because both
# delivery files have their -v<num> suffix removed before server execution.
#
# Purpose:
#   Traverse materialized historical Python snapshots and prepare exact raw
#   source slices for later NPR scoring. This stage creates function/method
#   implementation bodies plus function-outside module/class blocks.
#
# Source policy:
#   - Read .py files directly from the materialized snapshot tree.
#   - Use Python AST only to locate scopes and source boundaries.
#   - Never use ast.unparse() for detector input.
#   - Preserve comments, blank lines, repeated spaces, indentation, and original
#     line endings within every selected raw-source slice.
#   - Remove leading module/class/function docstrings from implementation input.
#   - Keep overlapping nested definitions only as diagnostic_overlap records.
#   - Do not calculate NPR or AGC/HWC labels in A01.
#
# Inputs:
#   SNAPSHOT_ROOT
#     Root containing the materialized snapshot directories.
#
#   SNAPSHOT_MANIFEST
#     Optional source snapshot manifest. The default points to the Model C
#     manifest used to create the historical snapshot sample. If it exists,
#     A01 uses it only for stable provenance metadata; snapshot source files are
#     still read from SNAPSHOT_ROOT.
#
# Main outputs:
#   output/snapshot_npr/run-x-a01/python_snapshot_manifest.csv
#   output/snapshot_npr/run-x-a01/python_file_manifest.csv
#   output/snapshot_npr/run-x-a01/python_code_unit_manifest.csv
#   output/snapshot_npr/run-x-a01/code_units/<sha-prefix>/<sha256>.txt
#
# QC outputs:
#   output/snapshot_npr/run-x-a01/qc/python_snapshot_input_checks.csv
#   output/snapshot_npr/run-x-a01/qc/python_snapshot_input_exclusions.csv
#   output/snapshot_npr/run-x-a01/qc/python_snapshot_input_summary.json
#   output/snapshot_npr/run-x-a01/qc/python_snapshot_input_metadata.json
#
# Optional environment overrides:
#   PROJECT_ROOT
#   PYTHON_BIN
#   PY_SCRIPT
#   SNAPSHOT_ROOT
#   SNAPSHOT_MANIFEST
#   OUTPUT_DIR
#   QC_DIR
#   LOG_DIR
#   LOG_FILE
#   EXPECTED_SNAPSHOTS
#   PROGRESS_EVERY_FILES
#   OVERWRITE_OUTPUT=0|1
#   RUN_SELF_TEST=0|1
#   REQUIRE_COMPLETE_METADATA=0|1
#
# Prototype run:
#   OVERWRITE_OUTPUT=1 bash proc_sh/run-x-a01-prepare-snapshot-npr-inputs.sh
#
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"
export PROJECT_ROOT

RUN_PREFIX="run-x-a01"
IMPLEMENTATION_VERSION="v1"
RUN_LABEL="${RUN_PREFIX}-${IMPLEMENTATION_VERSION}"
RUN_TS="${RUN_TS:-$(date +%Y%m%d-%H%M%S)}"

PYTHON_BIN="${PYTHON_BIN:-/home/user1-system12/miniconda3/envs/agcparse312/bin/python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/prepare_snapshot_npr_inputs.py}"

SNAPSHOT_ROOT="${SNAPSHOT_ROOT:-/mnt/samsung850ev/project-workspace/tmp/python-snapshot-samples}"
DEFAULT_SNAPSHOT_MANIFEST="/home/user1-system12/project-workspace/ai_code_complexity_study_python/ai-code-complexity-study/repo_x01/run-x-a05/velocity_did_model_c_snapshot_manifest.csv"
SNAPSHOT_MANIFEST="${SNAPSHOT_MANIFEST:-${DEFAULT_SNAPSHOT_MANIFEST}}"

OUTPUT_DIR="${OUTPUT_DIR:-output/snapshot_npr/${RUN_PREFIX}}"
QC_DIR="${QC_DIR:-${OUTPUT_DIR}/qc}"
LOG_DIR="${LOG_DIR:-logs/${RUN_PREFIX}}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/${RUN_LABEL}-prepare-snapshot-npr-inputs-${RUN_TS}.log}"

EXPECTED_SNAPSHOTS="${EXPECTED_SNAPSHOTS:-2}"
PROGRESS_EVERY_FILES="${PROGRESS_EVERY_FILES:-100}"
OVERWRITE_OUTPUT="${OVERWRITE_OUTPUT:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
REQUIRE_COMPLETE_METADATA="${REQUIRE_COMPLETE_METADATA:-0}"

SNAPSHOT_OUTPUT="${OUTPUT_DIR}/python_snapshot_manifest.csv"
FILE_OUTPUT="${OUTPUT_DIR}/python_file_manifest.csv"
CODE_UNIT_OUTPUT="${OUTPUT_DIR}/python_code_unit_manifest.csv"
CODE_UNIT_ROOT="${OUTPUT_DIR}/code_units"
CHECK_OUTPUT="${QC_DIR}/python_snapshot_input_checks.csv"
EXCLUSION_OUTPUT="${QC_DIR}/python_snapshot_input_exclusions.csv"
SUMMARY_OUTPUT="${QC_DIR}/python_snapshot_input_summary.json"
METADATA_OUTPUT="${QC_DIR}/python_snapshot_input_metadata.json"

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

require_file "${PY_SCRIPT}" "A01 Python implementation"
require_dir "${SNAPSHOT_ROOT}" "snapshot root"
validate_nonnegative_integer "${EXPECTED_SNAPSHOTS}" "EXPECTED_SNAPSHOTS"
validate_nonnegative_integer "${PROGRESS_EVERY_FILES}" "PROGRESS_EVERY_FILES"
validate_bool01 "${OVERWRITE_OUTPUT}" "OVERWRITE_OUTPUT"
validate_bool01 "${RUN_SELF_TEST}" "RUN_SELF_TEST"
validate_bool01 "${REQUIRE_COMPLETE_METADATA}" "REQUIRE_COMPLETE_METADATA"

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
    echo "${RUN_LABEL} execution summary"
    echo "Started:          ${START_TEXT}"
    echo "Completed:        $(date)"
    printf 'Elapsed:          %02d:%02d:%02d\n' "${hours}" "${minutes}" "${seconds}"
    echo "Exit code:        ${exit_code}"
    echo "Python path:      ${PYTHON_BIN}"
    echo "Python version:   ${PYTHON_VERSION}"
    echo "Script path:      ${PY_SCRIPT}"
    echo "Snapshot root:    ${SNAPSHOT_ROOT}"
    echo "Output directory: ${OUTPUT_DIR}"
    echo "QC directory:     ${QC_DIR}"
    echo "Log file:         ${LOG_FILE}"
    echo "============================================================================"
    exit "${exit_code}"
}
trap finish EXIT

exec > >(tee -a "${LOG_FILE}") 2>&1

PY_SCRIPT_SHA256="$(sha256_file "${PY_SCRIPT}")"
SNAPSHOT_MANIFEST_ARG=()
SNAPSHOT_MANIFEST_SHA256="<not-used>"
if [[ -n "${SNAPSHOT_MANIFEST}" && -f "${SNAPSHOT_MANIFEST}" ]]; then
    SNAPSHOT_MANIFEST_ARG=(--snapshot-manifest "${SNAPSHOT_MANIFEST}")
    SNAPSHOT_MANIFEST_SHA256="$(sha256_file "${SNAPSHOT_MANIFEST}")"
elif [[ -n "${SNAPSHOT_MANIFEST}" ]]; then
    echo "WARNING: Snapshot provenance manifest not found; continuing with materialized-directory metadata only: ${SNAPSHOT_MANIFEST}"
fi

cat <<INFO
============================================================================
${RUN_LABEL}: prepare raw Python snapshot inputs for NPR
Started:                       ${START_TEXT}
Project root:                  ${PROJECT_ROOT}
Active conda env:              ${CONDA_DEFAULT_ENV:-<none>}
Python:                        ${PYTHON_BIN} (${PYTHON_VERSION})
Implementation version:        ${IMPLEMENTATION_VERSION}
Python script:                 ${PY_SCRIPT}
Python script SHA256:          ${PY_SCRIPT_SHA256}
Snapshot root:                 ${SNAPSHOT_ROOT}
Snapshot provenance manifest: ${SNAPSHOT_MANIFEST:-<none>}
Snapshot manifest SHA256:      ${SNAPSHOT_MANIFEST_SHA256}
Expected snapshots:            ${EXPECTED_SNAPSHOTS}
Progress every files:          ${PROGRESS_EVERY_FILES}
Overwrite output:              ${OVERWRITE_OUTPUT}
Run self-test:                 ${RUN_SELF_TEST}
Require complete metadata:     ${REQUIRE_COMPLETE_METADATA}
Snapshot output:               ${SNAPSHOT_OUTPUT}
File output:                   ${FILE_OUTPUT}
Code-unit output:              ${CODE_UNIT_OUTPUT}
Code-unit artifact root:       ${CODE_UNIT_ROOT}
Checks output:                 ${CHECK_OUTPUT}
Exclusions output:             ${EXCLUSION_OUTPUT}
Summary output:                ${SUMMARY_OUTPUT}
Metadata output:               ${METADATA_OUTPUT}
Log file:                      ${LOG_FILE}
============================================================================
INFO

# Structural validation before touching experiment outputs.
"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"
if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test
fi

COMMAND=(
    "${PYTHON_BIN}"
    "${PY_SCRIPT}"
    --snapshot-root "${SNAPSHOT_ROOT}"
    --output-dir "${OUTPUT_DIR}"
    --qc-dir "${QC_DIR}"
    --expected-snapshots "${EXPECTED_SNAPSHOTS}"
    --progress-every-files "${PROGRESS_EVERY_FILES}"
)

if (( ${#SNAPSHOT_MANIFEST_ARG[@]} > 0 )); then
    COMMAND+=("${SNAPSHOT_MANIFEST_ARG[@]}")
fi
if [[ "${OVERWRITE_OUTPUT}" == "1" ]]; then
    COMMAND+=(--overwrite-output)
fi
if [[ "${REQUIRE_COMPLETE_METADATA}" == "1" ]]; then
    COMMAND+=(--require-complete-metadata)
fi

printf 'Command:'
printf ' %q' "${COMMAND[@]}"
printf '\n'

PYTHONUNBUFFERED=1 "${COMMAND[@]}"

for required_output in \
    "${SNAPSHOT_OUTPUT}" \
    "${FILE_OUTPUT}" \
    "${CODE_UNIT_OUTPUT}" \
    "${CHECK_OUTPUT}" \
    "${EXCLUSION_OUTPUT}" \
    "${SUMMARY_OUTPUT}" \
    "${METADATA_OUTPUT}"; do
    require_file "${required_output}" "${RUN_PREFIX} output"
done
require_dir "${CODE_UNIT_ROOT}" "code-unit artifact directory"

read -r STATUS SNAPSHOTS COMPLETE_METADATA PY_FILES PREPARED_FILES EXCLUDED_FILES PRIMARY_UNITS DIAGNOSTIC_UNITS FAILED_CHECKS WARNING_CHECKS < <(
    "${PYTHON_BIN}" - "${SUMMARY_OUTPUT}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as stream:
    summary = json.load(stream)

print(
    summary["status"],
    summary["snapshots_discovered"],
    summary["snapshots_with_complete_metadata"],
    summary["python_files_discovered"],
    summary["python_files_prepared"],
    summary["python_files_excluded"],
    summary["primary_code_units"],
    summary["diagnostic_overlap_units"],
    summary["failed_checks"],
    summary["warning_checks"],
)
PY
)

cat <<INFO

============================================================================
${RUN_LABEL} output verification
Status:                       ${STATUS}
Snapshots discovered:         ${SNAPSHOTS}
Snapshots complete metadata:  ${COMPLETE_METADATA}
Python files discovered:      ${PY_FILES}
Python files prepared:        ${PREPARED_FILES}
Python files excluded:        ${EXCLUDED_FILES}
Primary code units:           ${PRIMARY_UNITS}
Diagnostic overlap units:     ${DIAGNOSTIC_UNITS}
Failed hard QC checks:        ${FAILED_CHECKS}
Failed warning QC checks:     ${WARNING_CHECKS}
Snapshot manifest:            ${SNAPSHOT_OUTPUT}
File manifest:                ${FILE_OUTPUT}
Code-unit manifest:           ${CODE_UNIT_OUTPUT}
Checks:                       ${CHECK_OUTPUT}
Exclusions:                   ${EXCLUSION_OUTPUT}
Summary:                      ${SUMMARY_OUTPUT}
Metadata:                     ${METADATA_OUTPUT}
============================================================================
INFO

if [[ "${STATUS}" != "PASS" && "${STATUS}" != "PASS_WITH_EXCLUSIONS" ]]; then
    echo "ERROR: ${RUN_PREFIX} completed with non-passing status: ${STATUS}" >&2
    exit 1
fi
if [[ "${FAILED_CHECKS}" != "0" ]]; then
    echo "ERROR: ${RUN_PREFIX} reported failed hard QC checks: ${FAILED_CHECKS}" >&2
    exit 1
fi
if [[ "${EXPECTED_SNAPSHOTS}" != "0" && "${SNAPSHOTS}" != "${EXPECTED_SNAPSHOTS}" ]]; then
    echo "ERROR: Expected ${EXPECTED_SNAPSHOTS} snapshots but summary reports ${SNAPSHOTS}." >&2
    exit 1
fi
