#!/usr/bin/env bash
# Audit the complete A01 -> A02 -> A03 snapshot NPR measurement pipeline.
#
# Versioned delivery file:
#   proc_sh/run-x-a04-audit-snapshot-npr-v1.sh
#
# Canonical server paths after removing delivery version suffixes:
#   proc_sh/run-x-a04-audit-snapshot-npr.sh
#   code-detection/audit_snapshot_npr.py
#
# This wrapper is standalone. It reuses the validation/logging structure of
# earlier experiment wrappers but does not call any previous shell wrapper.
#
# Inputs:
#   output/snapshot_npr/run-x-a01/
#   output/snapshot_npr/run-x-a02/
#   output/snapshot_npr/run-x-a03/
#
# Outputs:
#   output/snapshot_npr/run-x-a04/qc/
#     python_snapshot_npr_audit_checks.csv
#     python_snapshot_npr_audit_reconciliation.csv
#     python_snapshot_npr_audit_anomalies.csv
#     python_snapshot_npr_audit_summary.json
#     python_snapshot_npr_audit_metadata.json
#
# Python policy:
#   A04 does not AST-parse source snippets and does not load the LLM.
#   Run A04 with Python 3.11.x in the detectcodegpt conda environment.
#   Python 3.12 is reserved for AST source-preparation work such as A01.
#
# Optional environment variables:
#   PROJECT_ROOT, PYTHON_BIN, PY_SCRIPT, RUN_A01_DIR, RUN_A02_DIR, RUN_A03_DIR,
#   OUTPUT_DIR, LOG_DIR, EXPECTED_SNAPSHOTS, REQUIRE_FULL_COVERAGE,
#   OVERWRITE_OUTPUT, RUN_SELF_TEST, TOLERANCE.
#
# Typical prototype run:
#   bash proc_sh/run-x-a04-audit-snapshot-npr.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/audit_snapshot_npr.py}"

RUN_A01_DIR="${RUN_A01_DIR:-output/snapshot_npr/run-x-a01}"
RUN_A02_DIR="${RUN_A02_DIR:-output/snapshot_npr/run-x-a02}"
RUN_A03_DIR="${RUN_A03_DIR:-output/snapshot_npr/run-x-a03}"
OUTPUT_DIR="${OUTPUT_DIR:-output/snapshot_npr/run-x-a04}"
QC_DIR="${QC_DIR:-${OUTPUT_DIR}/qc}"
LOG_DIR="${LOG_DIR:-logs/run-x-a04}"

EXPECTED_SNAPSHOTS="${EXPECTED_SNAPSHOTS:-2}"
REQUIRE_FULL_COVERAGE="${REQUIRE_FULL_COVERAGE:-1}"
OVERWRITE_OUTPUT="${OVERWRITE_OUTPUT:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
TOLERANCE="${TOLERANCE:-1e-12}"

TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/run-x-a04-v1-audit-snapshot-npr-${TIMESTAMP}.log}"

CHECK_OUTPUT="${QC_DIR}/python_snapshot_npr_audit_checks.csv"
RECON_OUTPUT="${QC_DIR}/python_snapshot_npr_audit_reconciliation.csv"
ANOMALY_OUTPUT="${QC_DIR}/python_snapshot_npr_audit_anomalies.csv"
SUMMARY_OUTPUT="${QC_DIR}/python_snapshot_npr_audit_summary.json"
METADATA_OUTPUT="${QC_DIR}/python_snapshot_npr_audit_metadata.json"

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

if [[ "${PYTHON_BIN}" == */* ]]; then
    if [[ ! -x "${PYTHON_BIN}" ]]; then
        echo "ERROR: Python executable is missing or not executable: ${PYTHON_BIN}" >&2
        exit 2
    fi
elif ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "ERROR: Python executable not found: ${PYTHON_BIN}" >&2
    exit 2
fi

require_file "${PY_SCRIPT}" "run-x-a04 Python script"
require_dir "${RUN_A01_DIR}" "A01 output directory"
require_dir "${RUN_A02_DIR}" "A02 output directory"
require_dir "${RUN_A03_DIR}" "A03 output directory"

read -r PYTHON_MAJOR PYTHON_MINOR PYTHON_MICRO < <(
    "${PYTHON_BIN}" -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)'
)
PYTHON_VERSION="${PYTHON_MAJOR}.${PYTHON_MINOR}.${PYTHON_MICRO}"
if (( PYTHON_MAJOR != 3 || PYTHON_MINOR != 11 )); then
    echo "ERROR: run-x-a04 requires Python 3.11.x from the detectcodegpt conda environment; found ${PYTHON_VERSION}." >&2
    echo "ERROR: Python 3.12 is required only for AST-parsing source-preparation stages such as run-x-a01." >&2
    exit 2
fi

"${PYTHON_BIN}" - <<'PY'
import importlib
missing = []
for module_name in ("numpy", "pandas"):
    try:
        importlib.import_module(module_name)
    except Exception as error:
        missing.append(f"{module_name}: {type(error).__name__}: {error}")
if missing:
    raise SystemExit("Missing A04 dependencies: " + "; ".join(missing))
PY

mkdir -p "${LOG_DIR}"
START_EPOCH="$(date +%s)"
START_TEXT="$(date)"
PYTHON_RESOLVED="$("${PYTHON_BIN}" -c 'import sys; print(sys.executable)')"

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
    echo "run-x-a04 execution summary"
    echo "Started:                    ${START_TEXT}"
    echo "Completed:                  $(date)"
    printf 'Elapsed:                    %02d:%02d:%02d\n' "${hours}" "${minutes}" "${seconds}"
    echo "Exit code:                  ${exit_code}"
    echo "Python path:                ${PYTHON_RESOLVED}"
    echo "Python version:             ${PYTHON_VERSION}"
    echo "Python script:              ${PY_SCRIPT}"
    echo "A01 directory:              ${RUN_A01_DIR}"
    echo "A02 directory:              ${RUN_A02_DIR}"
    echo "A03 directory:              ${RUN_A03_DIR}"
    echo "Output directory:           ${OUTPUT_DIR}"
    echo "Log file:                   ${LOG_FILE}"
    echo "============================================================================"
    exit "${exit_code}"
}
trap finish EXIT
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "============================================================================"
echo "run-x-a04: audit snapshot NPR pipeline"
echo "Started:                         ${START_TEXT}"
echo "Workspace:                       ${PROJECT_ROOT}"
echo "Active conda env:                ${CONDA_DEFAULT_ENV:-<none>}"
echo "Python path:                     ${PYTHON_RESOLVED}"
echo "Python version:                  ${PYTHON_VERSION}"
echo "Python script:                   ${PY_SCRIPT}"
echo "A01 directory:                   ${RUN_A01_DIR}"
echo "A02 directory:                   ${RUN_A02_DIR}"
echo "A03 directory:                   ${RUN_A03_DIR}"
echo "Expected snapshots:              ${EXPECTED_SNAPSHOTS}"
echo "Require full coverage:           ${REQUIRE_FULL_COVERAGE}"
echo "Tolerance:                       ${TOLERANCE}"
echo "Output directory:                ${OUTPUT_DIR}"
echo "============================================================================"

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"
echo "Python compile check: PASS"

if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test
fi

if [[ "${OVERWRITE_OUTPUT}" != "1" ]] && [[ -e "${OUTPUT_DIR}" ]]; then
    if find "${OUTPUT_DIR}" -mindepth 1 -maxdepth 3 -type f -print -quit | grep -q .; then
        echo "ERROR: A04 output directory already contains files: ${OUTPUT_DIR}" >&2
        echo "Set OVERWRITE_OUTPUT=1 only after reviewing the existing output." >&2
        exit 2
    fi
fi

ARGS=(
    --a01-dir "${RUN_A01_DIR}"
    --a02-dir "${RUN_A02_DIR}"
    --a03-dir "${RUN_A03_DIR}"
    --output-dir "${OUTPUT_DIR}"
    --expected-snapshots "${EXPECTED_SNAPSHOTS}"
    --tolerance "${TOLERANCE}"
)
if [[ "${REQUIRE_FULL_COVERAGE}" == "1" ]]; then
    ARGS+=(--require-full-coverage)
fi
if [[ "${OVERWRITE_OUTPUT}" == "1" ]]; then
    ARGS+=(--overwrite)
fi

"${PYTHON_BIN}" "${PY_SCRIPT}" "${ARGS[@]}"

for path in \
    "${CHECK_OUTPUT}" \
    "${RECON_OUTPUT}" \
    "${ANOMALY_OUTPUT}" \
    "${SUMMARY_OUTPUT}" \
    "${METADATA_OUTPUT}"; do
    require_file "${path}" "A04 output"
done

"${PYTHON_BIN}" - "${SUMMARY_OUTPUT}" "${CHECK_OUTPUT}" "${ANOMALY_OUTPUT}" <<'PY'
import json
import sys
import pandas as pd

summary_path, checks_path, anomaly_path = sys.argv[1:]
with open(summary_path, "r", encoding="utf-8") as handle:
    summary = json.load(handle)
checks = pd.read_csv(checks_path)
anomalies = pd.read_csv(anomaly_path)

hard_failed = checks[(checks["severity"] == "hard") & (~checks["passed"].astype(bool))]
hard_anomalies = anomalies[anomalies["severity"] == "hard"] if not anomalies.empty else anomalies

print("A04 wrapper validation")
print(f"  status: {summary.get('status')}")
print(f"  audit checks: {len(checks)}")
print(f"  hard checks failed: {len(hard_failed)}")
print(f"  anomaly rows: {len(anomalies)}")
print(f"  hard anomaly rows: {len(hard_anomalies)}")
print(f"  snapshots: {summary.get('snapshots')}")
print(f"  python files: {summary.get('python_files')}")
print(f"  primary occurrences: {summary.get('primary_code_unit_occurrences')}")
print(f"  unique units: {summary.get('unique_primary_code_units')}")
print(f"  windows: {summary.get('window_rows')}")

if summary.get("status") != "PASS":
    raise SystemExit("A04 summary status is not PASS")
if len(hard_failed) != 0:
    raise SystemExit("A04 has failed hard checks")
if len(hard_anomalies) != 0:
    raise SystemExit("A04 has hard anomaly rows")
PY

echo "A04 wrapper validation: PASS"
