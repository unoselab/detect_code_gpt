#!/usr/bin/env bash
# Aggregate finalized C_FUN NPR measurements to historical Python files and repo-month/file rows.
#
# This wrapper is standalone. It was created by first copying the existing A12 FUN aggregation
# wrapper and then adapting its input validation, provenance checks, output paths, and comments
# for the A15 C_FUN aggregation stage. It does not call A12 or any other existing shell wrapper.
#
# Versioned delivery files:
#   code-detection/aggregate_snapshot_npr_cfun_files-v1.py
#   proc_sh/run-x-a15-aggregate-snapshot-npr-cfun-v1.sh
#
# Optional canonical server paths after deployment:
#   code-detection/aggregate_snapshot_npr_cfun_files.py
#   proc_sh/run-x-a15-aggregate-snapshot-npr-cfun.sh
#
# Scientific scope:
#   - C_FUN = A05 primary method_body occurrences.
#   - A14 contributes the newly scored C_FUN SHA values.
#   - A13 is authoritative for the three C_FUN/FUN overlap SHA memberships reused from A11.
#   - A11 finite reuse and expected exclusions are propagated exactly as directed by A13.
#   - File NPR remains continuous. This stage does not apply NPR thresholds or AGC/HWC labels.
#   - Files without C_FUN coverage remain present with blank C_FUN NPR values, never zero.
#   - Repo-month expansion uses the authoritative Model A panel; month ranges are not inferred.
#
# Required inputs:
#   output/snapshot_npr/run-x-a05/python_snapshot_manifest.csv
#   output/snapshot_npr/run-x-a05/python_file_manifest.csv
#   output/snapshot_npr/run-x-a05/python_code_unit_manifest.csv
#
#   output/snapshot_npr/run-x-a13/summary.json
#   output/snapshot_npr/run-x-a13/python_cfun_workload_units.csv
#   output/snapshot_npr/run-x-a13/python_cfun_reuse_from_a11.csv
#
#   output/snapshot_npr/run-x-a14/results/gpu-{0,1,2}/python_cfun_new_unique_code_unit_npr_scores.csv
#   output/snapshot_npr/run-x-a14/results/gpu-{0,1,2}/python_cfun_new_npr_exclusions.csv
#   output/snapshot_npr/run-x-a14/results/gpu-{0,1,2}/summary.json
#
#   output/snapshot_npr/run-x-a11/results/gpu-{0,1,2}/python_fun_unique_code_unit_npr_scores.csv
#   output/snapshot_npr/run-x-a11/results/gpu-{0,1,2}/python_fun_npr_exclusions.csv
#   output/snapshot_npr/run-x-a11/results/gpu-{0,1,2}/summary.json
#
#   REPO_MONTH_PANEL_FILE
#       The authoritative 1,954-row Model A repo-month panel. It must contain at least
#       dataset_source, repo_name, time, and latest_commit_effective. A15 maps each exact
#       historical snapshot to every represented repo-month without inferring month ranges.
#
# Outputs under output/snapshot_npr/run-x-a15/:
#   python_cfun_file_npr_scores.csv
#       One row for every A05 historical Python snapshot/file. Files without class methods
#       remain present with file_npr_cfun_status=no_cfun and blank NPR values.
#   python_cfun_repo_month_file_npr_scores.csv
#       Continuous C_FUN NPR expanded to the authoritative repo-month/file universe.
#   python_cfun_occurrence_exclusions.csv
#       Historical C_FUN occurrences whose unique SHA has an expected A11/A14 exclusion.
#   python_cfun_reuse_from_a11_occurrences.csv
#       Occurrence-level audit for the three A13-directed C_FUN/FUN SHA reuses from A11.
#   python_cfun_aggregation_checks.csv
#   summary.json
#   metadata.json
#
# Runtime:
#   Python 3.11.x in the detectcodegpt environment. No GPU or model loading is performed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/aggregate_snapshot_npr_cfun_files.py}"
A05_ROOT="${A05_ROOT:-output/snapshot_npr/run-x-a05}"
A11_RESULTS_ROOT="${A11_RESULTS_ROOT:-output/snapshot_npr/run-x-a11/results}"
A13_ROOT="${A13_ROOT:-output/snapshot_npr/run-x-a13}"
A14_RESULTS_ROOT="${A14_RESULTS_ROOT:-output/snapshot_npr/run-x-a14/results}"
REPO_MONTH_PANEL_FILE="${REPO_MONTH_PANEL_FILE:-../ai_code_complexity_study_python/ai-code-complexity-study/repo_x01/run-x-a05/velocity_did_panel_model_a.csv}"
OUTPUT_DIR="${OUTPUT_DIR:-output/snapshot_npr/run-x-a15}"
LOG_DIR="${LOG_DIR:-logs/run-x-a15}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
STRICT_EXPECTED_COUNTS="${STRICT_EXPECTED_COUNTS:-1}"
EXPECTED_A05_CODE_MANIFEST_SHA256="${EXPECTED_A05_CODE_MANIFEST_SHA256:-1acb3726f5c62e6154672f1aff592973c65a13e58dbfd37f8058560d1a474e6c}"
TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/run-x-a15-v1-aggregate-snapshot-npr-cfun-${TIMESTAMP}.log}"

mkdir -p "${OUTPUT_DIR}" "${LOG_DIR}"

if [[ ! -f "${PY_SCRIPT}" ]]; then
  echo "ERROR: Python script not found: ${PY_SCRIPT}" >&2
  exit 2
fi
if [[ ! -f "${REPO_MONTH_PANEL_FILE}" ]]; then
  echo "ERROR: Authoritative repo-month panel not found: ${REPO_MONTH_PANEL_FILE}" >&2
  echo "Set REPO_MONTH_PANEL_FILE to the 1,954-row velocity_did_panel_model_a.csv path." >&2
  exit 2
fi

for required in \
  "${A05_ROOT}/python_snapshot_manifest.csv" \
  "${A05_ROOT}/python_file_manifest.csv" \
  "${A05_ROOT}/python_code_unit_manifest.csv" \
  "${A13_ROOT}/summary.json" \
  "${A13_ROOT}/python_cfun_workload_units.csv" \
  "${A13_ROOT}/python_cfun_reuse_from_a11.csv"; do
  if [[ ! -f "${required}" ]]; then
    echo "ERROR: Required A05/A13 input not found: ${required}" >&2
    exit 2
  fi
done

for gpu in 0 1 2; do
  for required in \
    "${A14_RESULTS_ROOT}/gpu-${gpu}/python_cfun_new_unique_code_unit_npr_scores.csv" \
    "${A14_RESULTS_ROOT}/gpu-${gpu}/python_cfun_new_npr_exclusions.csv" \
    "${A14_RESULTS_ROOT}/gpu-${gpu}/summary.json" \
    "${A11_RESULTS_ROOT}/gpu-${gpu}/python_fun_unique_code_unit_npr_scores.csv" \
    "${A11_RESULTS_ROOT}/gpu-${gpu}/python_fun_npr_exclusions.csv" \
    "${A11_RESULTS_ROOT}/gpu-${gpu}/summary.json"; do
    if [[ ! -f "${required}" ]]; then
      echo "ERROR: Required A11/A14 input not found: ${required}" >&2
      exit 2
    fi
  done
done

PYTHON_VERSION="$(${PYTHON_BIN} -c 'import platform; print(platform.python_version())')"
PYTHON_MAJOR_MINOR="$(${PYTHON_BIN} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "${PYTHON_MAJOR_MINOR}" != "3.11" ]]; then
  echo "ERROR: A15 requires Python 3.11.x; found ${PYTHON_VERSION}" >&2
  exit 2
fi

PY_SCRIPT_SHA256="$(sha256sum "${PY_SCRIPT}" | awk '{print $1}')"
A05_CODE_SHA256="$(sha256sum "${A05_ROOT}/python_code_unit_manifest.csv" | awk '{print $1}')"
A13_SUMMARY_SHA256="$(sha256sum "${A13_ROOT}/summary.json" | awk '{print $1}')"
A13_REUSE_SHA256="$(sha256sum "${A13_ROOT}/python_cfun_reuse_from_a11.csv" | awk '{print $1}')"
PANEL_SHA256="$(sha256sum "${REPO_MONTH_PANEL_FILE}" | awk '{print $1}')"

if [[ "${A05_CODE_SHA256}" != "${EXPECTED_A05_CODE_MANIFEST_SHA256}" ]]; then
  echo "ERROR: A05 code-unit manifest SHA256 mismatch." >&2
  echo "Observed: ${A05_CODE_SHA256}" >&2
  echo "Expected: ${EXPECTED_A05_CODE_MANIFEST_SHA256}" >&2
  exit 2
fi

exec > >(tee "${LOG_FILE}") 2>&1

START_EPOCH="$(date +%s)"
echo "============================================================================"
echo "run-x-a15-v1: aggregate C_FUN NPR to snapshot/file and repo-month/file"
echo "Started:                         $(date)"
echo "Project root:                    ${PROJECT_ROOT}"
echo "Python:                          $(command -v "${PYTHON_BIN}") (${PYTHON_VERSION})"
echo "Python script:                   ${PY_SCRIPT}"
echo "Python script SHA256:            ${PY_SCRIPT_SHA256}"
echo "A05 root:                        ${A05_ROOT}"
echo "A05 code manifest SHA256:        ${A05_CODE_SHA256}"
echo "A11 results root:                ${A11_RESULTS_ROOT}"
echo "A13 root:                        ${A13_ROOT}"
echo "A13 summary SHA256:              ${A13_SUMMARY_SHA256}"
echo "A13 reuse-plan SHA256:           ${A13_REUSE_SHA256}"
echo "A14 results root:                ${A14_RESULTS_ROOT}"
echo "Repo-month panel:                ${REPO_MONTH_PANEL_FILE}"
echo "Repo-month panel SHA256:         ${PANEL_SHA256}"
echo "Output directory:                ${OUTPUT_DIR}"
echo "Scope:                           C_FUN = primary method_body occurrences"
echo "Unique score sources:            A14 new scores + A13-directed A11 reuse"
echo "File weighting:                  space-by-token weighted"
echo "Pooled NPR:                      perturbed component / original component"
echo "No-C_FUN file policy:            missing C_FUN coverage; NPR remains blank"
echo "Expected exclusions:             propagated; never imputed"
echo "Multi-membership policy:         membership inclusion; no exact CSV-string equality"
echo "Repo-month mapping:              authoritative panel; no month-range inference"
echo "Threshold/classification:        disabled"
echo "GPU/model usage:                 none"
echo "Strict expected counts:          ${STRICT_EXPECTED_COUNTS}"
echo "Log file:                        ${LOG_FILE}"
echo "============================================================================"

if [[ "${RUN_SELF_TEST}" == "1" ]]; then
  "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test
fi

ARGS=(
  --a05-root "${A05_ROOT}"
  --a11-results-root "${A11_RESULTS_ROOT}"
  --a13-root "${A13_ROOT}"
  --a14-results-root "${A14_RESULTS_ROOT}"
  --repo-month-panel-file "${REPO_MONTH_PANEL_FILE}"
  --output-dir "${OUTPUT_DIR}"
  --expected-a05-code-manifest-sha256 "${EXPECTED_A05_CODE_MANIFEST_SHA256}"
)
if [[ "${STRICT_EXPECTED_COUNTS}" == "1" ]]; then
  ARGS+=(--strict-expected-counts)
fi

set +e
"${PYTHON_BIN}" "${PY_SCRIPT}" "${ARGS[@]}"
EXIT_CODE=$?
set -e

END_EPOCH="$(date +%s)"
ELAPSED=$((END_EPOCH - START_EPOCH))
printf -v ELAPSED_TEXT '%02d:%02d:%02d' $((ELAPSED / 3600)) $(((ELAPSED % 3600) / 60)) $((ELAPSED % 60))

echo
echo "============================================================================"
echo "run-x-a15-v1 execution summary"
echo "Started epoch:    ${START_EPOCH}"
echo "Completed:        $(date)"
echo "Elapsed:          ${ELAPSED_TEXT}"
echo "Exit code:        ${EXIT_CODE}"
echo "Output directory: ${OUTPUT_DIR}"
echo "Log file:         ${LOG_FILE}"
if [[ -f "${OUTPUT_DIR}/python_cfun_file_npr_scores.csv" ]]; then
  echo "Snapshot/file CSV lines:           $(wc -l < "${OUTPUT_DIR}/python_cfun_file_npr_scores.csv")"
fi
if [[ -f "${OUTPUT_DIR}/python_cfun_repo_month_file_npr_scores.csv" ]]; then
  echo "Repo-month/file CSV lines:         $(wc -l < "${OUTPUT_DIR}/python_cfun_repo_month_file_npr_scores.csv")"
fi
if [[ -f "${OUTPUT_DIR}/python_cfun_occurrence_exclusions.csv" ]]; then
  echo "Occurrence exclusion CSV lines:    $(wc -l < "${OUTPUT_DIR}/python_cfun_occurrence_exclusions.csv")"
fi
if [[ -f "${OUTPUT_DIR}/python_cfun_reuse_from_a11_occurrences.csv" ]]; then
  echo "A11 reuse occurrence CSV lines:    $(wc -l < "${OUTPUT_DIR}/python_cfun_reuse_from_a11_occurrences.csv")"
fi
if [[ -f "${OUTPUT_DIR}/summary.json" ]]; then
  echo "Final status:                      $(${PYTHON_BIN} -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${OUTPUT_DIR}/summary.json")"
fi
echo "============================================================================"

exit "${EXIT_CODE}"
