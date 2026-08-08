#!/usr/bin/env bash
# Prepare or run the deterministic A07 cross-GPU NPR benchmark.
#
# Versioned delivery file:
#   proc_sh/run-x-a07-benchmark-snapshot-npr-gpu-v1.sh
#
# Canonical server paths after removing delivery version suffixes:
#   proc_sh/run-x-a07-benchmark-snapshot-npr-gpu.sh
#   code-detection/benchmark_snapshot_npr_gpu.py
#
# This wrapper is standalone and does not call the existing A02 shell wrapper.
# The Python benchmark imports the canonical A02 Python implementation directly
# so that windowing, perturbation, rank, NPR, and model-loading logic are reused
# without duplicating or changing the measurement semantics.
#
# MODE=prepare inputs (run once on Server 173):
#   output/snapshot_npr/run-x-a06/npr_scoring_unique_unit_workload.csv
#   output/snapshot_npr/run-x-a05/code_units/<prefix>/<sha>.txt
#
# MODE=prepare outputs:
#   output/snapshot_npr/run-x-a07/benchmark_bundle/
#     benchmark_units.csv
#     benchmark_bucket_summary.csv
#     benchmark_bundle_metadata.json
#     code_units/<prefix>/<sha>.txt
#   output/snapshot_npr/run-x-a07/run-x-a07-benchmark-bundle.tar.gz
#
# The tarball is copied to Server R158 before benchmark scoring starts. Both
# systems then run independently. They do not need to communicate while scoring.
#
# MODE=run inputs (on each server):
#   benchmark_bundle/ prepared above
#   code-detection/score_snapshot_npr.py
#   DetectCodeGPT model/runtime dependencies in Python 3.11
#
# MODE=run outputs:
#   output/snapshot_npr/run-x-a07/results/<SYSTEM_LABEL>/
#     benchmark_unique_scores.csv
#     benchmark_window_scores.csv
#     benchmark_failures.csv
#     benchmark_artifact_errors.csv
#     benchmark_summary.json
#
# Important:
#   - Use one visible GPU per invocation.
#   - Do not run production A02 yet.
#   - For the architecture comparison, use the same benchmark bundle on both
#     systems and GPU 0 on each system first.
#   - Production sharding will be prepared offline after measured throughput is
#     available; no cross-server scheduler or shared filesystem is assumed.
# 
# MODE=prepare OVERWRITE=1 bash proc_sh/run-x-a07-benchmark-snapshot-npr-gpu.sh
# 

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

MODE="${MODE:-prepare}"
PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/benchmark_snapshot_npr_gpu.py}"
A02_SCRIPT="${A02_SCRIPT:-code-detection/score_snapshot_npr.py}"

A06_UNIQUE_WORKLOAD="${A06_UNIQUE_WORKLOAD:-output/snapshot_npr/run-x-a06/npr_scoring_unique_unit_workload.csv}"
ARTIFACT_BASE="${ARTIFACT_BASE:-output/snapshot_npr/run-x-a05}"
A07_ROOT="${A07_ROOT:-output/snapshot_npr/run-x-a07}"
BUNDLE_DIR="${BUNDLE_DIR:-${A07_ROOT}/benchmark_bundle}"
BUNDLE_TAR="${BUNDLE_TAR:-${A07_ROOT}/run-x-a07-benchmark-bundle.tar.gz}"
SYSTEM_LABEL="${SYSTEM_LABEL:-$(hostname | tr '.:' '__')}"
OUTPUT_DIR="${OUTPUT_DIR:-${A07_ROOT}/results/${SYSTEM_LABEL}}"
LOG_DIR="${LOG_DIR:-logs/run-x-a07}"
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-${HOME}/.cache/huggingface/hub}"

SCORING_MODEL="${SCORING_MODEL:-bigcode/starcoder2-7b}"
WINDOW_SIZE="${WINDOW_SIZE:-128}"
PERTURBATIONS_PER_WINDOW="${PERTURBATIONS_PER_WINDOW:-50}"
PERTURBATION_TYPE="${PERTURBATION_TYPE:-random-insert-space+newline}"
RANDOM_SEED="${RANDOM_SEED:-20260723}"
PCT_WORDS_MASKED="${PCT_WORDS_MASKED:-0.5}"
SPAN_LENGTH="${SPAN_LENGTH:-2}"
PERTURBATION_CHUNK_SIZE="${PERTURBATION_CHUNK_SIZE:-10}"
N_PERTURBATION_ROUNDS="${N_PERTURBATION_ROUNDS:-1}"
DETECTOR_LOG_LEVEL="${DETECTOR_LOG_LEVEL:-WARNING}"

CUDA_DEVICE="${CUDA_DEVICE:-0}"
OVERWRITE="${OVERWRITE:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/run-x-a07-v1-${MODE}-${SYSTEM_LABEL}-${TIMESTAMP}.log}"

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

if [[ "${MODE}" != "prepare" && "${MODE}" != "run" ]]; then
    echo "ERROR: MODE must be prepare or run; found ${MODE}." >&2
    exit 2
fi

require_file "${PY_SCRIPT}" "A07 Python script"
if [[ "${MODE}" == "prepare" ]]; then
    require_file "${A06_UNIQUE_WORKLOAD}" "A06 unique-unit workload"
else
    require_file "${A02_SCRIPT}" "canonical A02 Python script"
    require_file "${BUNDLE_DIR}/benchmark_units.csv" "benchmark bundle manifest"
    require_file "${BUNDLE_DIR}/benchmark_bundle_metadata.json" "benchmark bundle metadata"
fi

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

# The run mode reuses A02 and therefore requires the DetectCodeGPT Python 3.11
# runtime. Prepare mode only reads/copies CSV and text artifacts, but using the
# same environment keeps deployment simple and reproducible.
if [[ "${MODE}" == "run" ]] && (( PYTHON_MAJOR != 3 || PYTHON_MINOR != 11 )); then
    echo "ERROR: MODE=run requires Python 3.11.x; found ${PYTHON_VERSION}." >&2
    exit 2
fi

mkdir -p "${LOG_DIR}" "${A07_ROOT}"
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
    echo "run-x-a07-v1 execution summary"
    echo "Mode:             ${MODE}"
    echo "System label:     ${SYSTEM_LABEL}"
    echo "Started:          ${START_TEXT}"
    echo "Completed:        $(date)"
    printf 'Elapsed:          %02d:%02d:%02d\n' "${hours}" "${minutes}" "${seconds}"
    echo "Exit code:        ${exit_code}"
    echo "Python:           ${PYTHON_RESOLVED} (${PYTHON_VERSION})"
    echo "Bundle directory: ${BUNDLE_DIR}"
    echo "Output directory: ${OUTPUT_DIR}"
    echo "Log file:         ${LOG_FILE}"
    echo "============================================================================"
    exit "${exit_code}"
}
trap finish EXIT
exec > >(tee -a "${LOG_FILE}") 2>&1

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"
if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --mode "${MODE}" --self-test
fi

cat <<INFO
============================================================================
run-x-a07-v1: deterministic cross-GPU NPR benchmark
Started:                         ${START_TEXT}
Mode:                            ${MODE}
Project root:                    ${PROJECT_ROOT}
System label:                    ${SYSTEM_LABEL}
Python:                          ${PYTHON_RESOLVED} (${PYTHON_VERSION})
Python script:                   ${PY_SCRIPT}
Python script SHA256:            $(sha256_file "${PY_SCRIPT}")
Canonical A02 script:            ${A02_SCRIPT}
A06 unique workload:             ${A06_UNIQUE_WORKLOAD}
A05 artifact base:               ${ARTIFACT_BASE}
Benchmark bundle:                ${BUNDLE_DIR}
Benchmark bundle tar:            ${BUNDLE_TAR}
Output directory:                ${OUTPUT_DIR}
Scoring model:                   ${SCORING_MODEL}
Window size:                     ${WINDOW_SIZE}
Perturbations per window:        ${PERTURBATIONS_PER_WINDOW}
Random seed:                     ${RANDOM_SEED}
CUDA device requested:           ${CUDA_DEVICE}
Server communication at runtime: none
Log file:                        ${LOG_FILE}
============================================================================
INFO

COMMON_ARGS=(
    --mode "${MODE}"
    --project-root "${PROJECT_ROOT}"
    --a06-unique-workload "${A06_UNIQUE_WORKLOAD}"
    --artifact-base "${ARTIFACT_BASE}"
    --bundle-dir "${BUNDLE_DIR}"
    --a02-script "${A02_SCRIPT}"
    --output-dir "${OUTPUT_DIR}"
    --system-label "${SYSTEM_LABEL}"
    --scoring-model "${SCORING_MODEL}"
    --window-size "${WINDOW_SIZE}"
    --perturbations-per-window "${PERTURBATIONS_PER_WINDOW}"
    --perturbation-type "${PERTURBATION_TYPE}"
    --random-seed "${RANDOM_SEED}"
    --pct-words-masked "${PCT_WORDS_MASKED}"
    --span-length "${SPAN_LENGTH}"
    --perturbation-chunk-size "${PERTURBATION_CHUNK_SIZE}"
    --n-perturbation-rounds "${N_PERTURBATION_ROUNDS}"
    --model-cache-dir "${MODEL_CACHE_DIR}"
    --detector-log-level "${DETECTOR_LOG_LEVEL}"
)
if [[ "${OVERWRITE}" == "1" ]]; then
    COMMON_ARGS+=(--overwrite)
fi

if [[ "${MODE}" == "prepare" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" "${COMMON_ARGS[@]}"
    rm -f "${BUNDLE_TAR}"
    tar -czf "${BUNDLE_TAR}" -C "${A07_ROOT}" "$(basename "${BUNDLE_DIR}")"
    echo "Benchmark bundle tar created: ${BUNDLE_TAR}"
    echo "Benchmark bundle tar SHA256: $(sha256_file "${BUNDLE_TAR}")"
else
    export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"
    export TOKENIZERS_PARALLELISM="false"
    "${PYTHON_BIN}" - <<'PYCUDA'
import torch
if not torch.cuda.is_available():
    raise SystemExit("CUDA is not available in the selected Python environment.")
print(f"CUDA visible device count: {torch.cuda.device_count()}")
print(f"CUDA device 0: {torch.cuda.get_device_name(0)}")
print(f"CUDA memory bytes: {torch.cuda.get_device_properties(0).total_memory}")
PYCUDA
    "${PYTHON_BIN}" "${PY_SCRIPT}" "${COMMON_ARGS[@]}"
fi
