#!/usr/bin/env bash
# Validate A07 cross-GPU NPR benchmark outputs and derive measured worker weights.
#
# Versioned delivery file:
#   proc_sh/run-x-a08-validate-cross-gpu-npr-benchmark-v1.sh
#
# Canonical server paths after removing delivery version suffixes:
#   proc_sh/run-x-a08-validate-cross-gpu-npr-benchmark.sh
#   code-detection/validate_cross_gpu_npr_benchmark.py
#
# Inputs:
#   output/snapshot_npr/run-x-a07/results/s173-ada0/
#     benchmark_summary.json
#     benchmark_window_scores.csv
#     benchmark_unique_scores.csv
#   output/snapshot_npr/run-x-a07/results/r158-a6000-0/
#     benchmark_summary.json
#     benchmark_window_scores.csv
#     benchmark_unique_scores.csv
#
# Outputs:
#   output/snapshot_npr/run-x-a08/
#     cross_gpu_benchmark_checks.csv
#     cross_gpu_window_numeric_differences.csv
#     cross_gpu_unique_numeric_differences.csv
#     measured_worker_capacity_plan.csv
#     cross_gpu_benchmark_validation_summary.json
#
# This wrapper is standalone. It does not call A07 or A02 shell wrappers and it
# does not load any model. Both A07 result directories must already exist in the
# local workspace. No server-to-server communication is used during A08.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/validate_cross_gpu_npr_benchmark.py}"
REFERENCE_DIR="${REFERENCE_DIR:-output/snapshot_npr/run-x-a07/results/s173-ada0}"
CANDIDATE_DIR="${CANDIDATE_DIR:-output/snapshot_npr/run-x-a07/results/r158-a6000-0}"
OUTPUT_DIR="${OUTPUT_DIR:-output/snapshot_npr/run-x-a08}"
LOG_DIR="${LOG_DIR:-logs/run-x-a08}"
NUMERIC_ABS_TOL="${NUMERIC_ABS_TOL:-1e-4}"
NUMERIC_REL_TOL="${NUMERIC_REL_TOL:-1e-4}"
PRODUCTION_WINDOWS="${PRODUCTION_WINDOWS:-1113866}"
OVERWRITE="${OVERWRITE:-1}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/run-x-a08-v1-validate-cross-gpu-npr-benchmark-${TIMESTAMP}.log}"

require_file() {
    local path="$1"
    local label="$2"
    if [[ ! -f "${path}" ]]; then
        echo "ERROR: Missing ${label}: ${path}" >&2
        exit 2
    fi
}

sha256_file() {
    sha256sum "$1" | awk '{print $1}'
}

require_file "${PY_SCRIPT}" "A08 Python script"
for path in \
    "${REFERENCE_DIR}/benchmark_summary.json" \
    "${REFERENCE_DIR}/benchmark_window_scores.csv" \
    "${REFERENCE_DIR}/benchmark_unique_scores.csv" \
    "${CANDIDATE_DIR}/benchmark_summary.json" \
    "${CANDIDATE_DIR}/benchmark_window_scores.csv" \
    "${CANDIDATE_DIR}/benchmark_unique_scores.csv"; do
    require_file "${path}" "A07 benchmark comparison input"
done

if [[ "${PYTHON_BIN}" == */* ]]; then
    [[ -x "${PYTHON_BIN}" ]] || { echo "ERROR: Python executable is not executable: ${PYTHON_BIN}" >&2; exit 2; }
else
    command -v "${PYTHON_BIN}" >/dev/null 2>&1 || { echo "ERROR: Python executable not found: ${PYTHON_BIN}" >&2; exit 2; }
fi

read -r PYTHON_MAJOR PYTHON_MINOR PYTHON_MICRO < <(
    "${PYTHON_BIN}" -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)'
)
PYTHON_VERSION="${PYTHON_MAJOR}.${PYTHON_MINOR}.${PYTHON_MICRO}"
PYTHON_RESOLVED="$("${PYTHON_BIN}" -c 'import sys; print(sys.executable)')"

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
    echo "run-x-a08-v1 execution summary"
    echo "Started:          ${START_TEXT}"
    echo "Completed:        $(date)"
    printf 'Elapsed:          %02d:%02d:%02d\n' "${hours}" "${minutes}" "${seconds}"
    echo "Exit code:        ${exit_code}"
    echo "Python:           ${PYTHON_RESOLVED} (${PYTHON_VERSION})"
    echo "Reference dir:    ${REFERENCE_DIR}"
    echo "Candidate dir:    ${CANDIDATE_DIR}"
    echo "Output directory: ${OUTPUT_DIR}"
    echo "Log file:         ${LOG_FILE}"
    echo "============================================================================"
    exit "${exit_code}"
}
trap finish EXIT
exec > >(tee -a "${LOG_FILE}") 2>&1

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"
if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test
fi

cat <<INFO
============================================================================
run-x-a08-v1: validate cross-GPU NPR benchmark and measured worker weights
Started:                         ${START_TEXT}
Project root:                    ${PROJECT_ROOT}
Python:                          ${PYTHON_RESOLVED} (${PYTHON_VERSION})
Python script:                   ${PY_SCRIPT}
Python script SHA256:            $(sha256_file "${PY_SCRIPT}")
Reference A07 directory:         ${REFERENCE_DIR}
Candidate A07 directory:         ${CANDIDATE_DIR}
Output directory:                ${OUTPUT_DIR}
Numeric absolute tolerance:      ${NUMERIC_ABS_TOL}
Numeric relative tolerance:      ${NUMERIC_REL_TOL}
Production expected windows:     ${PRODUCTION_WINDOWS}
Model loading:                   disabled
GPU use:                         disabled
Server communication at runtime: none
Log file:                        ${LOG_FILE}
============================================================================
INFO

ARGS=(
    --reference-dir "${REFERENCE_DIR}"
    --candidate-dir "${CANDIDATE_DIR}"
    --output-dir "${OUTPUT_DIR}"
    --numeric-abs-tolerance "${NUMERIC_ABS_TOL}"
    --numeric-rel-tolerance "${NUMERIC_REL_TOL}"
    --production-windows "${PRODUCTION_WINDOWS}"
)
if [[ "${OVERWRITE}" == "1" ]]; then
    ARGS+=(--overwrite)
fi

"${PYTHON_BIN}" "${PY_SCRIPT}" "${ARGS[@]}"

if [[ -f "${OUTPUT_DIR}/cross_gpu_benchmark_validation_summary.json" ]]; then
    echo
    echo "Validation summary:"
    cat "${OUTPUT_DIR}/cross_gpu_benchmark_validation_summary.json"
fi

if [[ -f "${OUTPUT_DIR}/measured_worker_capacity_plan.csv" ]]; then
    echo
    echo "Measured worker capacity plan:"
    cat "${OUTPUT_DIR}/measured_worker_capacity_plan.csv"
fi
