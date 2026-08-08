#!/usr/bin/env bash
# Aggregate A02 continuous NPR scores from code units to files and snapshots.
#
# Versioned delivery file:
#   proc_sh/run-x-a03-aggregate-snapshot-npr-v1.sh
#
# Canonical server paths after removing delivery version suffixes:
#   proc_sh/run-x-a03-aggregate-snapshot-npr.sh
#   code-detection/aggregate_snapshot_npr.py
#
# This wrapper is standalone. It follows the existing experiment-wrapper style
# but does not call or depend on any previous shell wrapper.
#
# Inputs:
#   A01 snapshot/file/code-unit manifests
#   A02 occurrence-level code-unit NPR scores and window scores
#
# Outputs:
#   output/snapshot_npr/run-x-a03/
#     python_file_npr_scores.csv
#     python_snapshot_npr_scores.csv
#     qc/python_snapshot_npr_aggregation_reconciliation.csv
#     qc/python_snapshot_npr_aggregation_checks.csv
#     qc/python_snapshot_npr_aggregation_summary.json
#     qc/python_snapshot_npr_aggregation_metadata.json
#
# Methodology:
#   - Primary source units only; diagnostic_overlap units are excluded.
#   - Space-by tokens are the aggregation/coverage coordinate.
#   - Both weighted NPR ratios and pooled numerator/denominator NPR are saved.
#   - LLM-token counts are diagnostics only.
#   - No GPU, model loading, perturbation, or AGC/HWC classification occurs.
#
# Python policy:
#   - A03 performs no AST parsing, so run it with Python 3.11.x in the current
#     detectcodegpt conda environment.
#   - Python 3.12 is reserved for source-snippet AST parsing stages such as A01.
#
# Optional environment variables:
#   PROJECT_ROOT, PYTHON_BIN, PY_SCRIPT, RUN_A01_DIR, RUN_A02_DIR, OUTPUT_DIR,
#   QC_DIR, LOG_DIR, EXPECTED_SNAPSHOTS, REQUIRE_FULL_COVERAGE,
#   OVERWRITE_OUTPUT, RUN_SELF_TEST, TOLERANCE.
#
# Typical prototype run:
#   OVERWRITE_OUTPUT=1 bash proc_sh/run-x-a03-aggregate-snapshot-npr.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/aggregate_snapshot_npr.py}"

RUN_A01_DIR="${RUN_A01_DIR:-output/snapshot_npr/run-x-a01}"
RUN_A02_DIR="${RUN_A02_DIR:-output/snapshot_npr/run-x-a02}"
OUTPUT_DIR="${OUTPUT_DIR:-output/snapshot_npr/run-x-a03}"
QC_DIR="${QC_DIR:-${OUTPUT_DIR}/qc}"
LOG_DIR="${LOG_DIR:-logs/run-x-a03}"

A01_SNAPSHOT_MANIFEST="${A01_SNAPSHOT_MANIFEST:-${RUN_A01_DIR}/python_snapshot_manifest.csv}"
A01_FILE_MANIFEST="${A01_FILE_MANIFEST:-${RUN_A01_DIR}/python_file_manifest.csv}"
A01_CODE_UNIT_MANIFEST="${A01_CODE_UNIT_MANIFEST:-${RUN_A01_DIR}/python_code_unit_manifest.csv}"
A02_CODE_UNIT_SCORES="${A02_CODE_UNIT_SCORES:-${RUN_A02_DIR}/python_code_unit_npr_scores.csv}"
A02_WINDOW_SCORES="${A02_WINDOW_SCORES:-${RUN_A02_DIR}/python_window_npr_scores.csv}"
A02_METADATA="${A02_METADATA:-${RUN_A02_DIR}/qc/python_snapshot_npr_metadata.json}"

EXPECTED_SNAPSHOTS="${EXPECTED_SNAPSHOTS:-2}"
REQUIRE_FULL_COVERAGE="${REQUIRE_FULL_COVERAGE:-1}"
OVERWRITE_OUTPUT="${OVERWRITE_OUTPUT:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
TOLERANCE="${TOLERANCE:-1e-12}"

TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/run-x-a03-v1-aggregate-snapshot-npr-${TIMESTAMP}.log}"

FILE_OUTPUT="${OUTPUT_DIR}/python_file_npr_scores.csv"
SNAPSHOT_OUTPUT="${OUTPUT_DIR}/python_snapshot_npr_scores.csv"
RECON_OUTPUT="${QC_DIR}/python_snapshot_npr_aggregation_reconciliation.csv"
CHECK_OUTPUT="${QC_DIR}/python_snapshot_npr_aggregation_checks.csv"
SUMMARY_OUTPUT="${QC_DIR}/python_snapshot_npr_aggregation_summary.json"
METADATA_OUTPUT="${QC_DIR}/python_snapshot_npr_aggregation_metadata.json"

require_file() {
    local path="$1"
    local label="$2"
    if [[ ! -f "${path}" ]]; then
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

require_file "${PY_SCRIPT}" "run-x-a03 Python script"
require_file "${A01_SNAPSHOT_MANIFEST}" "A01 snapshot manifest"
require_file "${A01_FILE_MANIFEST}" "A01 file manifest"
require_file "${A01_CODE_UNIT_MANIFEST}" "A01 code-unit manifest"
require_file "${A02_CODE_UNIT_SCORES}" "A02 code-unit NPR scores"
require_file "${A02_WINDOW_SCORES}" "A02 window NPR scores"
require_file "${A02_METADATA}" "A02 metadata"

read -r PYTHON_MAJOR PYTHON_MINOR PYTHON_MICRO < <(
    "${PYTHON_BIN}" -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)'
)
PYTHON_VERSION="${PYTHON_MAJOR}.${PYTHON_MINOR}.${PYTHON_MICRO}"
if (( PYTHON_MAJOR != 3 || PYTHON_MINOR != 11 )); then
    echo "ERROR: run-x-a03 requires Python 3.11.x from the detectcodegpt conda environment; found ${PYTHON_VERSION}." >&2
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
    raise SystemExit("Missing A03 dependencies: " + "; ".join(missing))
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
    echo "run-x-a03 execution summary"
    echo "Started:                    ${START_TEXT}"
    echo "Completed:                  $(date)"
    printf 'Elapsed:                    %02d:%02d:%02d\n' "${hours}" "${minutes}" "${seconds}"
    echo "Exit code:                  ${exit_code}"
    echo "Python path:                ${PYTHON_RESOLVED}"
    echo "Python version:             ${PYTHON_VERSION}"
    echo "Python script:              ${PY_SCRIPT}"
    echo "A01 directory:              ${RUN_A01_DIR}"
    echo "A02 directory:              ${RUN_A02_DIR}"
    echo "Output directory:           ${OUTPUT_DIR}"
    echo "Log file:                   ${LOG_FILE}"
    echo "============================================================================"
    exit "${exit_code}"
}
trap finish EXIT
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "============================================================================"
echo "run-x-a03: aggregate snapshot NPR"
echo "Started:                         ${START_TEXT}"
echo "Workspace:                       ${PROJECT_ROOT}"
echo "Active conda env:                ${CONDA_DEFAULT_ENV:-<none>}"
echo "Python path:                     ${PYTHON_RESOLVED}"
echo "Python version:                  ${PYTHON_VERSION}"
echo "Python script:                   ${PY_SCRIPT}"
echo "A01 snapshot manifest:           ${A01_SNAPSHOT_MANIFEST}"
echo "A01 file manifest:               ${A01_FILE_MANIFEST}"
echo "A01 code-unit manifest:          ${A01_CODE_UNIT_MANIFEST}"
echo "A02 code-unit scores:            ${A02_CODE_UNIT_SCORES}"
echo "A02 window scores:               ${A02_WINDOW_SCORES}"
echo "Expected snapshots:              ${EXPECTED_SNAPSHOTS}"
echo "Require full coverage:           ${REQUIRE_FULL_COVERAGE}"
echo "Output directory:                ${OUTPUT_DIR}"
echo "============================================================================"

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"
echo "Python compile check: PASS"

if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test \
        --a01-snapshot-manifest "${A01_SNAPSHOT_MANIFEST}" \
        --a01-file-manifest "${A01_FILE_MANIFEST}" \
        --a01-code-unit-manifest "${A01_CODE_UNIT_MANIFEST}" \
        --a02-code-unit-scores "${A02_CODE_UNIT_SCORES}" \
        --a02-window-scores "${A02_WINDOW_SCORES}" \
        --output-dir "${OUTPUT_DIR}"
fi

if [[ "${OVERWRITE_OUTPUT}" != "1" ]] && [[ -e "${OUTPUT_DIR}" ]]; then
    if find "${OUTPUT_DIR}" -mindepth 1 -maxdepth 2 -type f -print -quit | grep -q .; then
        echo "ERROR: A03 output directory already contains files: ${OUTPUT_DIR}" >&2
        echo "Set OVERWRITE_OUTPUT=1 only after reviewing the existing output." >&2
        exit 2
    fi
fi

ARGS=(
    --a01-snapshot-manifest "${A01_SNAPSHOT_MANIFEST}"
    --a01-file-manifest "${A01_FILE_MANIFEST}"
    --a01-code-unit-manifest "${A01_CODE_UNIT_MANIFEST}"
    --a02-code-unit-scores "${A02_CODE_UNIT_SCORES}"
    --a02-window-scores "${A02_WINDOW_SCORES}"
    --a02-metadata "${A02_METADATA}"
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
    "${FILE_OUTPUT}" \
    "${SNAPSHOT_OUTPUT}" \
    "${RECON_OUTPUT}" \
    "${CHECK_OUTPUT}" \
    "${SUMMARY_OUTPUT}" \
    "${METADATA_OUTPUT}"; do
    require_file "${path}" "A03 output"
done

"${PYTHON_BIN}" - "${SUMMARY_OUTPUT}" "${CHECK_OUTPUT}" "${SNAPSHOT_OUTPUT}" "${EXPECTED_SNAPSHOTS}" <<'PY'
import json
import sys
import pandas as pd

summary_path, checks_path, snapshot_path, expected = sys.argv[1:]
expected = int(expected)
with open(summary_path, "r", encoding="utf-8") as handle:
    summary = json.load(handle)
checks = pd.read_csv(checks_path)
snapshots = pd.read_csv(snapshot_path)

if summary.get("status") != "PASS":
    raise SystemExit(f"A03 summary status is not PASS: {summary.get('status')}")
if int(summary.get("hard_checks_failed", -1)) != 0:
    raise SystemExit(f"A03 reports hard QC failures: {summary.get('hard_checks_failed')}")
if len(snapshots) != expected:
    raise SystemExit(f"A03 snapshot output row count {len(snapshots)} != expected {expected}")
failed = checks[(checks["severity"] == "hard") & (~checks["passed"].astype(bool))]
if not failed.empty:
    raise SystemExit("A03 hard checks failed:\n" + failed.to_string(index=False))
print("Wrapper output validation: PASS")
print(f"Snapshots: {len(snapshots)}")
print(f"Coverage: {summary.get('npr_coverage_ratio')}")
PY

echo "run-x-a03 completed successfully."
