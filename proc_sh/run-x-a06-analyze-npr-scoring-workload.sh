#!/usr/bin/env bash
# Analyze the full A05 output before starting expensive A02 GPU scoring.
#
# Inputs:
#   output/snapshot_npr/run-x-a05/python_code_unit_manifest.csv
#
# Outputs:
#   output/snapshot_npr/run-x-a06/
#     npr_scoring_workload_summary.json
#     npr_scoring_unique_unit_workload.csv
#     npr_scoring_worker_assignment.csv
#     npr_scoring_worker_summary.csv
#     npr_scoring_window_buckets.csv
#     npr_scoring_top_units.csv
#
# The default logical workers reflect the currently available GPUs:
#   Server 173: GPU 0, GPU 1
#   Server R158: GPU 0, GPU 1, GPU 2
#
# Default capacity weights are equal. Do not invent hardware speed ratios.
# After a small real benchmark on both GPU types, rerun with measured relative
# throughput weights through WORKER_CAPACITY_WEIGHTS, for example "1.4,1.4,1,1,1".
#
# This stage performs no model loading and no NPR scoring.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/analyze_npr_scoring_workload.py}"
INPUT_MANIFEST="${INPUT_MANIFEST:-output/snapshot_npr/run-x-a05/python_code_unit_manifest.csv}"
OUTPUT_DIR="${OUTPUT_DIR:-output/snapshot_npr/run-x-a06}"
LOG_DIR="${LOG_DIR:-logs/run-x-a06}"
WINDOW_SIZE="${WINDOW_SIZE:-128}"
PERTURBATIONS_PER_WINDOW="${PERTURBATIONS_PER_WINDOW:-50}"
CHUNKSIZE="${CHUNKSIZE:-100000}"
WORKER_NAMES="${WORKER_NAMES:-s173-gpu0,s173-gpu1,r158-gpu0,r158-gpu1,r158-gpu2}"
WORKER_CAPACITY_WEIGHTS="${WORKER_CAPACITY_WEIGHTS:-}"
TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/run-x-a06-v1-analyze-npr-scoring-workload-${TIMESTAMP}.log}"

if [[ "${PYTHON_BIN}" == */* ]]; then
    [[ -x "${PYTHON_BIN}" ]] || { echo "ERROR: Python executable not found: ${PYTHON_BIN}" >&2; exit 2; }
else
    command -v "${PYTHON_BIN}" >/dev/null 2>&1 || { echo "ERROR: Python executable not found: ${PYTHON_BIN}" >&2; exit 2; }
fi
[[ -f "${PY_SCRIPT}" ]] || { echo "ERROR: Missing Python script: ${PY_SCRIPT}" >&2; exit 2; }
[[ -f "${INPUT_MANIFEST}" ]] || { echo "ERROR: Missing A05 code-unit manifest: ${INPUT_MANIFEST}" >&2; exit 2; }

mkdir -p "${LOG_DIR}" "${OUTPUT_DIR}"
START_EPOCH="$(date +%s)"
START_TEXT="$(date)"
exec > >(tee -a "${LOG_FILE}") 2>&1

PYTHON_RESOLVED="$("${PYTHON_BIN}" -c 'import sys; print(sys.executable)')"
PYTHON_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
PY_SCRIPT_SHA="$(sha256sum "${PY_SCRIPT}" | awk '{print $1}')"
INPUT_SHA="$(sha256sum "${INPUT_MANIFEST}" | awk '{print $1}')"

cat <<INFO
============================================================================
run-x-a06-v1: analyze full NPR scoring workload
Started:                       ${START_TEXT}
Project root:                  ${PROJECT_ROOT}
Python:                        ${PYTHON_RESOLVED} (${PYTHON_VERSION})
Python script:                 ${PY_SCRIPT}
Python script SHA256:          ${PY_SCRIPT_SHA}
Input manifest:                ${INPUT_MANIFEST}
Input manifest SHA256:         ${INPUT_SHA}
Output directory:              ${OUTPUT_DIR}
Window size:                   ${WINDOW_SIZE}
Perturbations per window:      ${PERTURBATIONS_PER_WINDOW}
Chunk size:                    ${CHUNKSIZE}
Worker names:                  ${WORKER_NAMES}
Worker capacity weights:       ${WORKER_CAPACITY_WEIGHTS:-<equal>}
Model loading:                 disabled
NPR scoring:                   disabled
Log file:                      ${LOG_FILE}
============================================================================
INFO

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"
"${PYTHON_BIN}" "${PY_SCRIPT}" --self-test

COMMAND=(
    "${PYTHON_BIN}" "${PY_SCRIPT}"
    --input-code-unit-manifest "${INPUT_MANIFEST}"
    --output-dir "${OUTPUT_DIR}"
    --window-size "${WINDOW_SIZE}"
    --perturbations-per-window "${PERTURBATIONS_PER_WINDOW}"
    --chunksize "${CHUNKSIZE}"
    --worker-names "${WORKER_NAMES}"
)
if [[ -n "${WORKER_CAPACITY_WEIGHTS}" ]]; then
    COMMAND+=(--worker-capacity-weights "${WORKER_CAPACITY_WEIGHTS}")
fi
"${COMMAND[@]}"

for path in \
    "${OUTPUT_DIR}/npr_scoring_workload_summary.json" \
    "${OUTPUT_DIR}/npr_scoring_unique_unit_workload.csv" \
    "${OUTPUT_DIR}/npr_scoring_worker_assignment.csv" \
    "${OUTPUT_DIR}/npr_scoring_worker_summary.csv" \
    "${OUTPUT_DIR}/npr_scoring_window_buckets.csv" \
    "${OUTPUT_DIR}/npr_scoring_top_units.csv"; do
    [[ -f "${path}" ]] || { echo "ERROR: Missing expected output: ${path}" >&2; exit 3; }
done

cat "${OUTPUT_DIR}/npr_scoring_workload_summary.json"
echo
cat "${OUTPUT_DIR}/npr_scoring_worker_summary.csv"
echo
cat "${OUTPUT_DIR}/npr_scoring_window_buckets.csv"

END_EPOCH="$(date +%s)"
ELAPSED=$((END_EPOCH - START_EPOCH))
printf '\nCompleted: %s\nElapsed: %02d:%02d:%02d\n' "$(date)" "$((ELAPSED / 3600))" "$(((ELAPSED % 3600) / 60))" "$((ELAPSED % 60))"
echo "Log file: ${LOG_FILE}"
