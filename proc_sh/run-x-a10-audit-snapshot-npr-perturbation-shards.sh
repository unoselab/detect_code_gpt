#!/usr/bin/env bash
# Audit merged A09 deterministic perturbation shards before FUN NPR scoring.
#
# This wrapper was derived from the existing A09 wrapper structure but is
# standalone: it does not call A09 or any earlier shell wrapper.
#
# Versioned delivery files:
#   code-detection/audit_snapshot_npr_perturbation_shards-v1.py
#   proc_sh/run-x-a10-audit-snapshot-npr-perturbation-shards-v1.sh
#
# Canonical server paths after deployment:
#   code-detection/audit_snapshot_npr_perturbation_shards.py
#   proc_sh/run-x-a10-audit-snapshot-npr-perturbation-shards.sh
#
# Inputs:
#   output/snapshot_npr/run-x-a09/plan/summary.json
#   output/snapshot_npr/run-x-a09/shards/shard-000-of-096.jsonl.gz ... 095
#   output/snapshot_npr/run-x-a09/shards/shard-000-of-096.summary.json ... 095
#
# Outputs:
#   output/snapshot_npr/run-x-a10/summary.json
#   output/snapshot_npr/run-x-a10/checks.csv
#   output/snapshot_npr/run-x-a10/failures.csv
#   output/snapshot_npr/run-x-a10/shard_audit.csv
#   output/snapshot_npr/run-x-a10/group_workload_summary.csv
#   output/snapshot_npr/run-x-a10/fun_gpu_mod3_plan.csv
#   output/snapshot_npr/run-x-a10/fun_gpu_lpt_plan.csv
#
# The audit streams every merged gzip shard, verifies its recorded gzip and
# canonical JSONL SHA-256 values, reconciles unit/window/perturbation totals,
# validates deterministic shard/window-seed placement, and measures exact
# FUN/C_FUN/BLOCK workloads. It does not load StarCoder2 or compute NPR.
#
# Recommended command on R158 after all 96 shards have been merged:
#   bash proc_sh/run-x-a10-audit-snapshot-npr-perturbation-shards.sh
#
# Optional environment variables:
#   PROJECT_ROOT, PYTHON_BIN, PY_SCRIPT, A09_ROOT, OUTPUT_ROOT,
#   DATA_SHARDS, PREP_WORKERS, WINDOW_SIZE, PERTURBATIONS_PER_WINDOW,
#   RANDOM_SEED, EXPECTED_A09_VERSION, EXPECTED_INPUT_SHA256,
#   EXPECTED_UNIQUE_UNITS, EXPECTED_WINDOWS, EXPECTED_PERTURBATIONS,
#   SAMPLE_RECORDS_PER_SHARD, RUN_SELF_TEST,
#   LOG_DIR, TIMESTAMP, LOG_FILE

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

RUN_PREFIX="run-x-a10"
PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/audit_snapshot_npr_perturbation_shards.py}"
A09_ROOT="${A09_ROOT:-output/snapshot_npr/run-x-a09}"
OUTPUT_ROOT="${OUTPUT_ROOT:-output/snapshot_npr/run-x-a10}"
DATA_SHARDS="${DATA_SHARDS:-96}"
PREP_WORKERS="${PREP_WORKERS:-2}"
WINDOW_SIZE="${WINDOW_SIZE:-128}"
PERTURBATIONS_PER_WINDOW="${PERTURBATIONS_PER_WINDOW:-50}"
RANDOM_SEED="${RANDOM_SEED:-20260723}"
EXPECTED_A09_VERSION="${EXPECTED_A09_VERSION:-run-x-a09-v3}"
EXPECTED_INPUT_SHA256="${EXPECTED_INPUT_SHA256:-1acb3726f5c62e6154672f1aff592973c65a13e58dbfd37f8058560d1a474e6c}"
EXPECTED_UNIQUE_UNITS="${EXPECTED_UNIQUE_UNITS:-419220}"
EXPECTED_WINDOWS="${EXPECTED_WINDOWS:-1113866}"
EXPECTED_PERTURBATIONS="${EXPECTED_PERTURBATIONS:-55693300}"
SAMPLE_RECORDS_PER_SHARD="${SAMPLE_RECORDS_PER_SHARD:-2}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"

LOG_DIR="${LOG_DIR:-logs/run-x-a10}"
TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/${RUN_PREFIX}-v1-audit-${TIMESTAMP}.log}"

if [[ "${PYTHON_BIN}" == */* ]]; then
    [[ -x "${PYTHON_BIN}" ]] || { echo "ERROR: Python executable is unavailable: ${PYTHON_BIN}" >&2; exit 2; }
elif ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "ERROR: Python executable is unavailable: ${PYTHON_BIN}" >&2
    exit 2
fi

[[ -f "${PY_SCRIPT}" ]] || {
    echo "ERROR: Missing canonical A10 Python script: ${PY_SCRIPT}" >&2
    echo "Deploy the versioned delivery file as code-detection/audit_snapshot_npr_perturbation_shards.py first." >&2
    exit 2
}
[[ -f "${A09_ROOT}/plan/summary.json" ]] || { echo "ERROR: Missing A09 plan summary." >&2; exit 2; }
[[ -d "${A09_ROOT}/shards" ]] || { echo "ERROR: Missing A09 shard directory." >&2; exit 2; }

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
    echo "run-x-a10-v1 execution summary"
    echo "Started:          ${START_TEXT}"
    echo "Completed:        $(date)"
    printf 'Elapsed:          %02d:%02d:%02d\n' "$((elapsed / 3600))" "$(((elapsed % 3600) / 60))" "$((elapsed % 60))"
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
    echo "ERROR: A10 is frozen to the DetectCodeGPT Python 3.11 runtime; got ${PYTHON_VERSION}." >&2
    exit 2
fi

DATA_COUNT="$(find "${A09_ROOT}/shards" -maxdepth 1 -name 'shard-*-of-096.jsonl.gz' -type f | wc -l)"
SUMMARY_COUNT="$(find "${A09_ROOT}/shards" -maxdepth 1 -name 'shard-*-of-096.summary.json' -type f | wc -l)"

echo "============================================================================"
echo "run-x-a10-v1: merged A09 perturbation audit and FUN scoring plan"
echo "Started:                         ${START_TEXT}"
echo "Project root:                    ${PROJECT_ROOT}"
echo "Python:                          ${PYTHON_RESOLVED} (${PYTHON_VERSION})"
echo "Python script:                   ${PY_SCRIPT}"
echo "A09 root:                        ${A09_ROOT}"
echo "Output root:                     ${OUTPUT_ROOT}"
echo "Observed data shards:            ${DATA_COUNT}"
echo "Observed summary shards:         ${SUMMARY_COUNT}"
echo "Expected logical shards:         ${DATA_SHARDS}"
echo "Expected unique units:           ${EXPECTED_UNIQUE_UNITS}"
echo "Expected windows:                ${EXPECTED_WINDOWS}"
echo "Expected perturbations:          ${EXPECTED_PERTURBATIONS}"
echo "Expected A09 script version:     ${EXPECTED_A09_VERSION}"
echo "Random seed:                     ${RANDOM_SEED}"
echo "Model loading:                   disabled"
echo "NPR scoring:                     disabled"
echo "Classification:                  disabled"
echo "Log file:                        ${LOG_FILE}"
echo "============================================================================"

"${PYTHON_BIN}" "${PY_SCRIPT}" \
    --project-root "${PROJECT_ROOT}" \
    --a09-root "${A09_ROOT}" \
    --output-root "${OUTPUT_ROOT}" \
    --data-shards "${DATA_SHARDS}" \
    --prep-workers "${PREP_WORKERS}" \
    --window-size "${WINDOW_SIZE}" \
    --perturbations-per-window "${PERTURBATIONS_PER_WINDOW}" \
    --random-seed "${RANDOM_SEED}" \
    --expected-a09-version "${EXPECTED_A09_VERSION}" \
    --expected-input-sha256 "${EXPECTED_INPUT_SHA256}" \
    --expected-unique-units "${EXPECTED_UNIQUE_UNITS}" \
    --expected-windows "${EXPECTED_WINDOWS}" \
    --expected-perturbations "${EXPECTED_PERTURBATIONS}" \
    --sample-records-per-shard "${SAMPLE_RECORDS_PER_SHARD}" \
    --run-self-test "${RUN_SELF_TEST}"
