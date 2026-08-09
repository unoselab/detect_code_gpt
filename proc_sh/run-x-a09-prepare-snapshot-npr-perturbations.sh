#!/usr/bin/env bash
# Prepare deterministic NPR perturbation shards before homogeneous GPU scoring.
#
# Versioned delivery files:
#   code-detection/prepare_snapshot_npr_perturbations.py
#   proc_sh/run-x-a09-prepare-snapshot-npr-perturbations.sh
#
# Canonical server paths after validation/deployment:
#   code-detection/prepare_snapshot_npr_perturbations.py
#   proc_sh/run-x-a09-prepare-snapshot-npr-perturbations.sh
#
# IMPORTANT:
#   This wrapper is standalone. It does not call A05/A06/A07/A08 shell wrappers.
#   It reads A05 artifacts directly and invokes only the canonical A09 Python
#   implementation. The Python implementation contains an explicit copy of the
#   validated random space/newline perturbation algorithm and verifies that copy
#   against project main.py in MODE=verify.
#
# Purpose:
#   1. Read the completed A05 primary code-unit manifest.
#   2. Deduplicate globally by code_unit_sha256.
#   3. Preserve FUN/C_FUN/BLOCK membership for later staged scoring.
#   4. Build the same 128 literal-space-token windows used by A02.
#   5. Generate 50 deterministic perturbations for every unique window.
#   6. Store original windows and ordered perturbations in deterministic gzip
#      JSONL logical shards with SHA-256 provenance.
#   7. Split preparation across two servers without runtime communication.
#
# This step does NOT:
#   - load StarCoder2,
#   - calculate original or perturbed log-rank,
#   - calculate NPR,
#   - apply an NPR threshold,
#   - classify AGC/HWC,
#   - run SonarQube,
#   - aggregate to file/snapshot/repo-month outcomes, or
#   - run DiD.
#
# Input:
#   output/snapshot_npr/run-x-a05/python_code_unit_manifest.csv
#   output/snapshot_npr/run-x-a05/code_units/...
#
# Main outputs:
#   output/snapshot_npr/run-x-a09/plan/
#     unique_primary_units.csv
#     logical_shard_plan.csv
#     checks.csv
#     summary.json
#
#   output/snapshot_npr/run-x-a09/shards/
#     shard-000-of-096.jsonl.gz
#     shard-000-of-096.summary.json
#     ...
#
#   output/snapshot_npr/run-x-a09/workers/<WORKER_LABEL>/
#     verification_perturbation_digests.csv   (MODE=verify)
#     verification_summary.json               (MODE=verify)
#     prepared_shards.csv                     (MODE=prepare)
#     worker_summary.json                     (MODE=prepare)
#
# Logical-shard policy:
#   DATA_SHARDS defaults to 96, which is divisible by both 2 and 3.
#   Preparation worker ownership: logical_shard % 2 == WORKER_INDEX.
#   Future R158 GPU ownership can use: logical_shard % 3 == GPU_INDEX.
#
# Recommended execution sequence:
#
#   A. Cross-server verification FIRST (same deterministic sample on both):
#      On Server 173:
#        MODE=verify WORKER_LABEL=s173 bash proc_sh/run-x-a09-prepare-snapshot-npr-perturbations.sh
#      On R158:
#        MODE=verify WORKER_LABEL=r158 bash proc_sh/run-x-a09-prepare-snapshot-npr-perturbations.sh
#      Compare verification_overall_sha256. They must be exactly identical.
#
#   B. Small storage/throughput smoke test:
#      On Server 173:
#        MODE=prepare WORKER_LABEL=s173 WORKER_INDEX=0 MAX_UNITS_PER_SHARD=2 OVERWRITE_OUTPUT=1 \
#          bash proc_sh/run-x-a09-prepare-snapshot-npr-perturbations.sh
#      On R158:
#        MODE=prepare WORKER_LABEL=r158 WORKER_INDEX=1 MAX_UNITS_PER_SHARD=2 OVERWRITE_OUTPUT=1 \
#          bash proc_sh/run-x-a09-prepare-snapshot-npr-perturbations.sh
#
#   C. Full preparation only after verification/smoke outputs are reviewed:
#      Server 173: WORKER_INDEX=0
#      R158:       WORKER_INDEX=1
#      Do NOT set MAX_UNITS_PER_SHARD for the full run.
#      Do NOT set OVERWRITE_OUTPUT=1 when resuming completed logical shards.
#
# Optional environment variables:
#   PROJECT_ROOT, PYTHON_BIN, PY_SCRIPT, MODE,
#   INPUT_MANIFEST, ARTIFACT_BASE, OUTPUT_ROOT,
#   WORKER_LABEL, WORKER_INDEX, NUM_WORKERS, DATA_SHARDS,
#   PROCESSES, MANIFEST_CHUNKSIZE, VERIFY_WINDOWS, MAX_UNITS_PER_SHARD,
#   GZIP_LEVEL, OVERWRITE_OUTPUT, RUN_SELF_TEST,
#   EXPECTED_INPUT_SHA256, EXPECTED_PRIMARY_OCCURRENCES,
#   EXPECTED_UNIQUE_UNITS, EXPECTED_WINDOWS,
#   SCORING_MODEL, SCORING_MODEL_REVISION,
#   LOG_DIR, TIMESTAMP, LOG_FILE

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

RUN_PREFIX="run-x-a09"
RUN_NAME="prepare-snapshot-npr-perturbations"

PYTHON_BIN="${PYTHON_BIN:-python}"
# The versioned delivery wrapper intentionally invokes the canonical unversioned
# Python filename used after deployment on each server.
PY_SCRIPT="${PY_SCRIPT:-code-detection/prepare_snapshot_npr_perturbations.py}"
# The original DetectCodeGPT implementation is a verification-only oracle.
# Production preparation deliberately does not import or call it.
REFERENCE_MAIN="${REFERENCE_MAIN:-code-detection/main.py}"

MODE="${MODE:-verify}"
INPUT_MANIFEST="${INPUT_MANIFEST:-output/snapshot_npr/run-x-a05/python_code_unit_manifest.csv}"
ARTIFACT_BASE="${ARTIFACT_BASE:-output/snapshot_npr/run-x-a05}"
OUTPUT_ROOT="${OUTPUT_ROOT:-output/snapshot_npr/run-x-a09}"

WORKER_LABEL="${WORKER_LABEL:-$(hostname -s)}"
NUM_WORKERS="${NUM_WORKERS:-2}"
DATA_SHARDS="${DATA_SHARDS:-96}"
PROCESSES="${PROCESSES:-8}"
MANIFEST_CHUNKSIZE="${MANIFEST_CHUNKSIZE:-100000}"
VERIFY_WINDOWS="${VERIFY_WINDOWS:-8}"
MAX_UNITS_PER_SHARD="${MAX_UNITS_PER_SHARD:-}"
GZIP_LEVEL="${GZIP_LEVEL:-3}"
OVERWRITE_OUTPUT="${OVERWRITE_OUTPUT:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"

EXPECTED_INPUT_SHA256="${EXPECTED_INPUT_SHA256:-1acb3726f5c62e6154672f1aff592973c65a13e58dbfd37f8058560d1a474e6c}"
EXPECTED_PRIMARY_OCCURRENCES="${EXPECTED_PRIMARY_OCCURRENCES:-3480000}"
EXPECTED_UNIQUE_UNITS="${EXPECTED_UNIQUE_UNITS:-419220}"
EXPECTED_WINDOWS="${EXPECTED_WINDOWS:-1113866}"

SCORING_MODEL="${SCORING_MODEL:-bigcode/starcoder2-7b}"
SCORING_MODEL_REVISION="${SCORING_MODEL_REVISION:-bb9afde76d7945da5745592525db122d4d729eb1}"

LOG_DIR="${LOG_DIR:-logs/run-x-a09}"
TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/${RUN_PREFIX}-v3-${MODE}-${WORKER_LABEL}-${TIMESTAMP}.log}"

if [[ "${MODE}" != "plan" && "${MODE}" != "verify" && "${MODE}" != "prepare" ]]; then
    echo "ERROR: MODE must be plan, verify, or prepare; got ${MODE}" >&2
    exit 2
fi

if [[ "${MODE}" == "prepare" ]]; then
    if [[ -z "${WORKER_INDEX+x}" || -z "${WORKER_INDEX:-}" ]]; then
        echo "ERROR: MODE=prepare requires explicit WORKER_INDEX=0 on Server 173 or WORKER_INDEX=1 on R158." >&2
        exit 2
    fi
else
    WORKER_INDEX="${WORKER_INDEX:-0}"
fi

if ! [[ "${WORKER_INDEX}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: WORKER_INDEX must be a non-negative integer." >&2
    exit 2
fi
if ! [[ "${NUM_WORKERS}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: NUM_WORKERS must be a positive integer." >&2
    exit 2
fi
if ! [[ "${DATA_SHARDS}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: DATA_SHARDS must be a positive integer." >&2
    exit 2
fi
if (( DATA_SHARDS % 6 != 0 )); then
    echo "ERROR: DATA_SHARDS must be divisible by 6; got ${DATA_SHARDS}." >&2
    exit 2
fi
if ! [[ "${PROCESSES}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: PROCESSES must be a positive integer." >&2
    exit 2
fi
if [[ -n "${MAX_UNITS_PER_SHARD}" ]] && ! [[ "${MAX_UNITS_PER_SHARD}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: MAX_UNITS_PER_SHARD must be empty or a positive integer." >&2
    exit 2
fi

if [[ "${PYTHON_BIN}" == */* ]]; then
    [[ -x "${PYTHON_BIN}" ]] || {
        echo "ERROR: Python executable is unavailable: ${PYTHON_BIN}" >&2
        exit 2
    }
elif ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "ERROR: Python executable is unavailable: ${PYTHON_BIN}" >&2
    exit 2
fi

[[ -f "${PY_SCRIPT}" ]] || {
    echo "ERROR: Missing canonical A09 Python script: ${PY_SCRIPT}" >&2
    echo "Deploy the versioned delivery file as code-detection/prepare_snapshot_npr_perturbations.py first." >&2
    exit 2
}
[[ -f "${INPUT_MANIFEST}" ]] || {
    echo "ERROR: Missing A05 code-unit manifest: ${INPUT_MANIFEST}" >&2
    exit 2
}
[[ -d "${ARTIFACT_BASE}" ]] || {
    echo "ERROR: Missing A05 artifact base: ${ARTIFACT_BASE}" >&2
    exit 2
}
if [[ "${MODE}" == "verify" ]]; then
    [[ -f "${REFERENCE_MAIN}" ]] || {
        echo "ERROR: Missing DetectCodeGPT reference main.py required only for MODE=verify: ${REFERENCE_MAIN}" >&2
        exit 2
    }
fi

mkdir -p "${LOG_DIR}"
START_EPOCH="$(date +%s)"
START_TEXT="$(date)"

finish() {
    local exit_code=$?
    local end_epoch elapsed
    end_epoch="$(date +%s)"
    elapsed=$((end_epoch - START_EPOCH))
    echo
    echo "============================================================================"
    echo "run-x-a09-v2 execution summary"
    echo "Mode:             ${MODE}"
    echo "Worker label:     ${WORKER_LABEL}"
    echo "Worker index:     ${WORKER_INDEX}"
    echo "Started:          ${START_TEXT}"
    echo "Completed:        $(date)"
    printf 'Elapsed:          %02d:%02d:%02d\n' \
        "$((elapsed / 3600))" "$(((elapsed % 3600) / 60))" "$((elapsed % 60))"
    echo "Exit code:        ${exit_code}"
    echo "Output root:      ${OUTPUT_ROOT}"
    echo "Log file:         ${LOG_FILE}"
    echo "============================================================================"
    exit "${exit_code}"
}
trap finish EXIT
exec > >(tee -a "${LOG_FILE}") 2>&1

PYTHON_RESOLVED="$("${PYTHON_BIN}" -c 'import sys; print(sys.executable)')"
PYTHON_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(sys.version.split()[0])')"
PYTHON_MINOR="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

if [[ "${PYTHON_MINOR}" != "3.11" ]]; then
    echo "ERROR: A09 perturbation preparation is frozen to the DetectCodeGPT Python 3.11 runtime; got ${PYTHON_VERSION}." >&2
    exit 2
fi

sha256_file() {
    sha256sum "$1" | awk '{print $1}'
}

INPUT_SHA="$(sha256_file "${INPUT_MANIFEST}")"
REFERENCE_MAIN_SHA="not-required"
if [[ -f "${REFERENCE_MAIN}" ]]; then
    REFERENCE_MAIN_SHA="$(sha256_file "${REFERENCE_MAIN}")"
fi
if [[ "${INPUT_SHA}" != "${EXPECTED_INPUT_SHA256}" ]]; then
    echo "ERROR: A05 manifest SHA mismatch." >&2
    echo "Observed: ${INPUT_SHA}" >&2
    echo "Expected: ${EXPECTED_INPUT_SHA256}" >&2
    exit 3
fi

cat <<INFO
============================================================================
run-x-a09-v2: deterministic two-server NPR perturbation preparation
Started:                         ${START_TEXT}
Mode:                            ${MODE}
Project root:                    ${PROJECT_ROOT}
Python:                          ${PYTHON_RESOLVED} (${PYTHON_VERSION})
Python script:                   ${PY_SCRIPT}
Python script SHA256:            $(sha256_file "${PY_SCRIPT}")
Reference main.py:               ${REFERENCE_MAIN}
Reference main.py SHA256:        ${REFERENCE_MAIN_SHA}
Reference A02 script:            code-detection/score_snapshot_npr.py
A05 manifest:                    ${INPUT_MANIFEST}
A05 manifest SHA256:             ${INPUT_SHA}
A05 artifact base:               ${ARTIFACT_BASE}
Output root:                     ${OUTPUT_ROOT}
Worker label:                    ${WORKER_LABEL}
Worker index:                    ${WORKER_INDEX}
Preparation workers:             ${NUM_WORKERS}
Logical data shards:             ${DATA_SHARDS}
Processes:                       ${PROCESSES}
Window size:                     128
Perturbations per window:        50
Perturbation type:               random-insert-space+newline
Random seed:                     20260723
Expected primary occurrences:    ${EXPECTED_PRIMARY_OCCURRENCES}
Expected unique units:           ${EXPECTED_UNIQUE_UNITS}
Expected unique windows:         ${EXPECTED_WINDOWS}
Intended scoring model:          ${SCORING_MODEL}
Intended model revision:         ${SCORING_MODEL_REVISION}
Model loading:                   disabled
NPR scoring:                     disabled
Classification:                  disabled
Server communication at runtime: none
Log file:                        ${LOG_FILE}
============================================================================
INFO

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"

if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test --mode plan --project-root "${PROJECT_ROOT}" \
        --input-manifest "${INPUT_MANIFEST}" --artifact-base "${ARTIFACT_BASE}" \
        --output-root "${OUTPUT_ROOT}" --expected-input-sha256 "${EXPECTED_INPUT_SHA256}" \
        --expected-primary-occurrences "${EXPECTED_PRIMARY_OCCURRENCES}" \
        --expected-unique-units "${EXPECTED_UNIQUE_UNITS}" --expected-windows "${EXPECTED_WINDOWS}" \
        --data-shards "${DATA_SHARDS}" --num-workers "${NUM_WORKERS}" \
        --scoring-model "${SCORING_MODEL}" --scoring-model-revision "${SCORING_MODEL_REVISION}"
fi

COMMAND=(
    "${PYTHON_BIN}" "${PY_SCRIPT}"
    --mode "${MODE}"
    --project-root "${PROJECT_ROOT}"
    --reference-main "${REFERENCE_MAIN}"
    --input-manifest "${INPUT_MANIFEST}"
    --artifact-base "${ARTIFACT_BASE}"
    --output-root "${OUTPUT_ROOT}"
    --worker-label "${WORKER_LABEL}"
    --worker-index "${WORKER_INDEX}"
    --num-workers "${NUM_WORKERS}"
    --data-shards "${DATA_SHARDS}"
    --processes "${PROCESSES}"
    --manifest-chunksize "${MANIFEST_CHUNKSIZE}"
    --verify-windows "${VERIFY_WINDOWS}"
    --gzip-level "${GZIP_LEVEL}"
    --expected-input-sha256 "${EXPECTED_INPUT_SHA256}"
    --expected-primary-occurrences "${EXPECTED_PRIMARY_OCCURRENCES}"
    --expected-unique-units "${EXPECTED_UNIQUE_UNITS}"
    --expected-windows "${EXPECTED_WINDOWS}"
    --scoring-model "${SCORING_MODEL}"
    --scoring-model-revision "${SCORING_MODEL_REVISION}"
)

if [[ -n "${MAX_UNITS_PER_SHARD}" ]]; then
    COMMAND+=(--max-units-per-shard "${MAX_UNITS_PER_SHARD}")
fi
if [[ "${OVERWRITE_OUTPUT}" == "1" ]]; then
    COMMAND+=(--overwrite)
fi

"${COMMAND[@]}"

echo "run-x-a09-v2 verification: PASS"
