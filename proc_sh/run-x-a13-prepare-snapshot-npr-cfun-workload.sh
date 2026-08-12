#!/usr/bin/env bash
# Prepare the C_FUN NPR workload, audit exact A11 FUN-score reuse, and build the
# deterministic 3-GPU A14 scoring plan on R158.
#
# This wrapper is standalone. It was created by first copying the existing A10
# audit wrapper and then adapting that control/provenance structure for A13. It
# does not call A10, A11, or any earlier shell wrapper.
#
# Versioned delivery files:
#   code-detection/prepare_snapshot_npr_cfun_workload-v1.py
#   proc_sh/run-x-a13-prepare-snapshot-npr-cfun-workload-v1.sh
#
# Canonical server paths after deployment:
#   code-detection/prepare_snapshot_npr_cfun_workload.py
#   proc_sh/run-x-a13-prepare-snapshot-npr-cfun-workload.sh
#
# Required inputs:
#   output/snapshot_npr/run-x-a09/plan/summary.json
#       Frozen A09 perturbation-plan provenance.
#   output/snapshot_npr/run-x-a09/plan/unique_primary_units.csv
#       Authoritative unique primary-unit membership and window counts. A13
#       selects C_FUN and requires method_body membership.
#   output/snapshot_npr/run-x-a10/summary.json
#       Frozen merged-shard audit and category workload totals. In particular,
#       C_FUN must reconcile to 567,557 windows.
#   output/snapshot_npr/run-x-a11/results/gpu-{0,1,2}/summary.json
#   output/snapshot_npr/run-x-a11/results/gpu-{0,1,2}/window_scores.sqlite3
#   output/snapshot_npr/run-x-a11/results/gpu-{0,1,2}/python_fun_unique_code_unit_npr_scores.csv
#   output/snapshot_npr/run-x-a11/results/gpu-{0,1,2}/python_fun_npr_exclusions.csv
#       Finalized A11 FUN production artifacts. When a unique content SHA has
#       both FUN and C_FUN membership, A13 reuses the frozen A11 score or the
#       frozen expected exclusion instead of scheduling duplicate GPU scoring.
#
# Outputs under output/snapshot_npr/run-x-a13:
#   python_cfun_workload_units.csv
#       Complete unique C_FUN membership universe with A11-reuse/A14-new status.
#   python_cfun_reuse_from_a11.csv
#       C_FUN units whose identical SHA was already attempted in A11 FUN.
#   python_cfun_new_scoring_units.csv
#       C_FUN-only units that require new A14 GPU scoring.
#   cfun_new_gpu_lpt_plan.csv
#       Whole-logical-shard deterministic 3-GPU plan for the A14-only workload.
#   cfun_new_gpu_summary.csv
#       Per-GPU new unit/window/perturbation totals.
#   checks.csv
#       Hard provenance/accounting gates.
#   summary.json
#       Compact A13 result and A14 workload sizes.
#   metadata.json
#       Input SHA-256 values and frozen methodological provenance.
#
# A13 is CPU-only. It does not load StarCoder2, regenerate perturbations, score
# NPR, classify AGC/HWC, or modify A09/A10/A11 artifacts.
#
# Recommended command on R158:
#   bash proc_sh/run-x-a13-prepare-snapshot-npr-cfun-workload.sh
#
# Optional environment variables:
#   PROJECT_ROOT, PYTHON_BIN, PY_SCRIPT, A09_ROOT, A10_ROOT, A11_ROOT,
#   OUTPUT_ROOT, LOG_DIR, RUN_SELF_TEST, TIMESTAMP, LOG_FILE.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

RUN_PREFIX="run-x-a13"
PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/prepare_snapshot_npr_cfun_workload.py}"
A09_ROOT="${A09_ROOT:-output/snapshot_npr/run-x-a09}"
A10_ROOT="${A10_ROOT:-output/snapshot_npr/run-x-a10}"
A11_ROOT="${A11_ROOT:-output/snapshot_npr/run-x-a11}"
OUTPUT_ROOT="${OUTPUT_ROOT:-output/snapshot_npr/run-x-a13}"
LOG_DIR="${LOG_DIR:-logs/run-x-a13}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"

TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/${RUN_PREFIX}-v1-prepare-cfun-${TIMESTAMP}.log}"

require_file() {
    local path="$1"
    local label="$2"
    if [[ ! -f "${path}" ]]; then
        echo "ERROR: Missing ${label}: ${path}" >&2
        exit 2
    fi
}

if [[ "${PYTHON_BIN}" == */* ]]; then
    [[ -x "${PYTHON_BIN}" ]] || { echo "ERROR: Python executable unavailable: ${PYTHON_BIN}" >&2; exit 2; }
elif ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "ERROR: Python executable unavailable: ${PYTHON_BIN}" >&2
    exit 2
fi

require_file "${PY_SCRIPT}" "canonical A13 Python script"
require_file "${A09_ROOT}/plan/summary.json" "A09 plan summary"
require_file "${A09_ROOT}/plan/unique_primary_units.csv" "A09 unique primary-unit plan"
require_file "${A10_ROOT}/summary.json" "A10 merged audit summary"
for gpu_index in 0 1 2; do
    worker="${A11_ROOT}/results/gpu-${gpu_index}"
    require_file "${worker}/summary.json" "A11 GPU${gpu_index} finalized summary"
    require_file "${worker}/window_scores.sqlite3" "A11 GPU${gpu_index} checkpoint database"
    require_file "${worker}/python_fun_unique_code_unit_npr_scores.csv" "A11 GPU${gpu_index} unique FUN scores"
    require_file "${worker}/python_fun_npr_exclusions.csv" "A11 GPU${gpu_index} expected exclusions"
done

mkdir -p "${LOG_DIR}" "${OUTPUT_ROOT}"
START_EPOCH="$(date +%s)"
START_TEXT="$(date)"

finish() {
    local exit_code=$?
    local end_epoch elapsed
    end_epoch="$(date +%s)"
    elapsed=$((end_epoch - START_EPOCH))
    echo
    echo "============================================================================"
    echo "run-x-a13-v1 execution summary"
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
    echo "ERROR: A13 requires the DetectCodeGPT Python 3.11 runtime; got ${PYTHON_VERSION}." >&2
    exit 2
fi

PY_SHA="$(sha256sum "${PY_SCRIPT}" | awk '{print $1}')"
A09_SUMMARY_SHA="$(sha256sum "${A09_ROOT}/plan/summary.json" | awk '{print $1}')"
A09_UNITS_SHA="$(sha256sum "${A09_ROOT}/plan/unique_primary_units.csv" | awk '{print $1}')"
A10_SUMMARY_SHA="$(sha256sum "${A10_ROOT}/summary.json" | awk '{print $1}')"

A11_GPU0_SUMMARY_SHA="$(sha256sum "${A11_ROOT}/results/gpu-0/summary.json" | awk '{print $1}')"
A11_GPU1_SUMMARY_SHA="$(sha256sum "${A11_ROOT}/results/gpu-1/summary.json" | awk '{print $1}')"
A11_GPU2_SUMMARY_SHA="$(sha256sum "${A11_ROOT}/results/gpu-2/summary.json" | awk '{print $1}')"
A11_GPU0_DB_SHA="$(sha256sum "${A11_ROOT}/results/gpu-0/window_scores.sqlite3" | awk '{print $1}')"
A11_GPU1_DB_SHA="$(sha256sum "${A11_ROOT}/results/gpu-1/window_scores.sqlite3" | awk '{print $1}')"
A11_GPU2_DB_SHA="$(sha256sum "${A11_ROOT}/results/gpu-2/window_scores.sqlite3" | awk '{print $1}')"
A11_GPU0_UNIQUE_SHA="$(sha256sum "${A11_ROOT}/results/gpu-0/python_fun_unique_code_unit_npr_scores.csv" | awk '{print $1}')"
A11_GPU1_UNIQUE_SHA="$(sha256sum "${A11_ROOT}/results/gpu-1/python_fun_unique_code_unit_npr_scores.csv" | awk '{print $1}')"
A11_GPU2_UNIQUE_SHA="$(sha256sum "${A11_ROOT}/results/gpu-2/python_fun_unique_code_unit_npr_scores.csv" | awk '{print $1}')"
A11_GPU0_EXCLUSION_SHA="$(sha256sum "${A11_ROOT}/results/gpu-0/python_fun_npr_exclusions.csv" | awk '{print $1}')"
A11_GPU1_EXCLUSION_SHA="$(sha256sum "${A11_ROOT}/results/gpu-1/python_fun_npr_exclusions.csv" | awk '{print $1}')"
A11_GPU2_EXCLUSION_SHA="$(sha256sum "${A11_ROOT}/results/gpu-2/python_fun_npr_exclusions.csv" | awk '{print $1}')"

echo "============================================================================"
echo "run-x-a13-v1: prepare C_FUN workload and audit exact A11 FUN-score reuse"
echo "Started:                         ${START_TEXT}"
echo "Project root:                    ${PROJECT_ROOT}"
echo "Python:                          ${PYTHON_RESOLVED} (${PYTHON_VERSION})"
echo "Python script:                   ${PY_SCRIPT}"
echo "Python script SHA256:            ${PY_SHA}"
echo "A09 root:                        ${A09_ROOT}"
echo "A09 summary SHA256:              ${A09_SUMMARY_SHA}"
echo "A09 unique-unit plan SHA256:     ${A09_UNITS_SHA}"
echo "A10 root:                        ${A10_ROOT}"
echo "A10 summary SHA256:              ${A10_SUMMARY_SHA}"
echo "A11 root:                        ${A11_ROOT}"
echo "A11 GPU0 summary SHA256:         ${A11_GPU0_SUMMARY_SHA}"
echo "A11 GPU1 summary SHA256:         ${A11_GPU1_SUMMARY_SHA}"
echo "A11 GPU2 summary SHA256:         ${A11_GPU2_SUMMARY_SHA}"
echo "A11 GPU0 database SHA256:        ${A11_GPU0_DB_SHA}"
echo "A11 GPU1 database SHA256:        ${A11_GPU1_DB_SHA}"
echo "A11 GPU2 database SHA256:        ${A11_GPU2_DB_SHA}"
echo "A11 GPU0 unique-score SHA256:    ${A11_GPU0_UNIQUE_SHA}"
echo "A11 GPU1 unique-score SHA256:    ${A11_GPU1_UNIQUE_SHA}"
echo "A11 GPU2 unique-score SHA256:    ${A11_GPU2_UNIQUE_SHA}"
echo "A11 GPU0 exclusion SHA256:       ${A11_GPU0_EXCLUSION_SHA}"
echo "A11 GPU1 exclusion SHA256:       ${A11_GPU1_EXCLUSION_SHA}"
echo "A11 GPU2 exclusion SHA256:       ${A11_GPU2_EXCLUSION_SHA}"
echo "Output root:                     ${OUTPUT_ROOT}"
echo "Category:                        C_FUN"
echo "Required code-unit type:         method_body"
echo "A11 reuse key:                   code_unit_sha256"
echo "A14 assignment policy:           deterministic_lpt_by_new_cfun_windows"
echo "Expected total C_FUN windows:    567557"
echo "Model loading:                   disabled"
echo "NPR scoring:                     disabled"
echo "Perturbation regeneration:       disabled"
echo "Classification:                  disabled"
echo "Log file:                        ${LOG_FILE}"
echo "============================================================================"

if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    echo
    echo "** Step 1: Run A13 structural self-test"
    echo "----------------------------------------------------------------------------"
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test-only --run-self-test 1
fi

echo
echo "** Step 2: Compile A13 Python program"
echo "----------------------------------------------------------------------------"
"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"

echo
echo "** Step 3: Build C_FUN reuse audit and A14 workload"
echo "----------------------------------------------------------------------------"
"${PYTHON_BIN}" "${PY_SCRIPT}" \
    --project-root "${PROJECT_ROOT}" \
    --a09-root "${A09_ROOT}" \
    --a10-root "${A10_ROOT}" \
    --a11-root "${A11_ROOT}" \
    --output-root "${OUTPUT_ROOT}" \
    --run-self-test 0

echo
echo "** Step 4: Verify A13 outputs"
echo "----------------------------------------------------------------------------"
for output_name in \
    python_cfun_workload_units.csv \
    python_cfun_reuse_from_a11.csv \
    python_cfun_new_scoring_units.csv \
    cfun_new_gpu_lpt_plan.csv \
    cfun_new_gpu_summary.csv \
    checks.csv \
    summary.json \
    metadata.json; do
    require_file "${OUTPUT_ROOT}/${output_name}" "A13 output ${output_name}"
done

"${PYTHON_BIN}" - "${OUTPUT_ROOT}/summary.json" "${OUTPUT_ROOT}/checks.csv" <<'PY'
import csv
import json
import sys
from pathlib import Path

summary_path = Path(sys.argv[1])
checks_path = Path(sys.argv[2])
summary = json.loads(summary_path.read_text(encoding="utf-8"))
with checks_path.open("r", encoding="utf-8", newline="") as stream:
    checks = list(csv.DictReader(stream))
failed = [row for row in checks if str(row.get("passed", "")).lower() not in {"true", "1"}]
if summary.get("status") != "PASS" or failed:
    raise SystemExit(
        f"A13 verification failed: status={summary.get('status')} failed_checks={len(failed)}"
    )
print("A13 output verification: PASS")
print(f"C_FUN unique-unit memberships:  {summary['cfun_unique_unit_memberships']}")
print(f"C_FUN windows:                  {summary['cfun_windows']}")
print(f"C_FUN/FUN overlap units:        {summary['cfun_fun_overlap_unique_units']}")
print(f"C_FUN/FUN overlap windows:      {summary['cfun_fun_overlap_windows']}")
print(f"A11 finite scores reused:       {summary['a11_reuse_finite_units']}")
print(f"A11 expected exclusions reused: {summary['a11_reuse_expected_exclusion_units']}")
print(f"A14 new unique units:           {summary['a14_new_unique_units']}")
print(f"A14 new windows:                {summary['a14_new_windows']}")
print(f"A14 new perturbations:          {summary['a14_new_perturbations']}")
print(f"A14 GPU window loads:           {summary['a14_gpu_window_loads']}")
print(f"Failed checks:                  {summary['failed_checks']}")
PY
