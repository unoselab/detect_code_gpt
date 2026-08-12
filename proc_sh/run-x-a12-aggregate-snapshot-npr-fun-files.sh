#!/usr/bin/env bash
# Aggregate finalized A11 FUN NPR scores to historical Python files and repo-month/file rows.
#
# This wrapper is standalone. It was copied from the existing A11 v3 wrapper and then
# adapted for the CPU-only A12 aggregation stage; it does not call any prior shell wrapper.
#
# Versioned delivery files:
#   code-detection/aggregate_snapshot_npr_fun_files-v2.py
#   proc_sh/run-x-a12-aggregate-snapshot-npr-fun-files-v2.sh
#
# Canonical server paths after deployment:
#   code-detection/aggregate_snapshot_npr_fun_files.py
#   proc_sh/run-x-a12-aggregate-snapshot-npr-fun-files.sh
#
# Required inputs:
#   output/snapshot_npr/run-x-a05/python_snapshot_manifest.csv
#   output/snapshot_npr/run-x-a05/python_file_manifest.csv
#   output/snapshot_npr/run-x-a05/python_code_unit_manifest.csv
#   output/snapshot_npr/run-x-a11/results/gpu-{0,1,2}/python_fun_unique_code_unit_npr_scores.csv
#   output/snapshot_npr/run-x-a11/results/gpu-{0,1,2}/python_fun_npr_exclusions.csv
#   output/snapshot_npr/run-x-a11/results/gpu-{0,1,2}/summary.json
#   REPO_MONTH_PANEL_FILE
#       The authoritative 1,954-row Model A repo-month panel. It must contain at least
#       dataset_source, repo_name, time, and latest_commit_effective. A12 uses it to
#       expand one historical snapshot/file NPR to every repo-month represented by that
#       exact snapshot. Month ranges are never inferred from first/last month summaries.
#
# Outputs under output/snapshot_npr/run-x-a12/:
#   python_fun_file_npr_scores.csv
#       One row for every A05 historical Python snapshot/file. Files without regular
#       functions remain present with file_npr_fun_status=no_fun and blank NPR values.
#   python_fun_repo_month_file_npr_scores.csv
#       Final FUN-only repo-month/file dataset requested for downstream threshold and
#       SonarQube file-quality analysis.
#   python_fun_occurrence_exclusions.csv
#       A05 function occurrences whose unique A11 SHA is an expected A11 v3 exclusion.
#   python_fun_aggregation_checks.csv
#   summary.json
#   metadata.json
#
# A12 v2 compatibility fix:
#   A11 v3 normalizes the <=1-token / no-valid-perturbation condition to the
#   exported exclusion class ``insufficient_llm_tokens_for_npr``. A12 v2 consumes
#   that normalized class exactly while keeping all other exclusion checks strict.
#
# Runtime:
#   Python 3.11.x in the detectcodegpt environment. No GPU/model loading is performed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/aggregate_snapshot_npr_fun_files.py}"
A05_ROOT="${A05_ROOT:-output/snapshot_npr/run-x-a05}"
A11_RESULTS_ROOT="${A11_RESULTS_ROOT:-output/snapshot_npr/run-x-a11/results}"
REPO_MONTH_PANEL_FILE="${REPO_MONTH_PANEL_FILE:-../ai_code_complexity_study_python/ai-code-complexity-study/repo_x01/run-x-a05/velocity_did_panel_model_a.csv}"
OUTPUT_DIR="${OUTPUT_DIR:-output/snapshot_npr/run-x-a12}"
LOG_DIR="${LOG_DIR:-logs/run-x-a12}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
STRICT_EXPECTED_COUNTS="${STRICT_EXPECTED_COUNTS:-1}"
EXPECTED_A05_CODE_MANIFEST_SHA256="${EXPECTED_A05_CODE_MANIFEST_SHA256:-1acb3726f5c62e6154672f1aff592973c65a13e58dbfd37f8058560d1a474e6c}"
TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/run-x-a12-v2-aggregate-snapshot-npr-fun-files-${TIMESTAMP}.log}"

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
  "${A05_ROOT}/python_code_unit_manifest.csv"; do
  if [[ ! -f "${required}" ]]; then
    echo "ERROR: Required A05 input not found: ${required}" >&2
    exit 2
  fi
done
for gpu in 0 1 2; do
  for required in \
    "${A11_RESULTS_ROOT}/gpu-${gpu}/python_fun_unique_code_unit_npr_scores.csv" \
    "${A11_RESULTS_ROOT}/gpu-${gpu}/python_fun_npr_exclusions.csv" \
    "${A11_RESULTS_ROOT}/gpu-${gpu}/summary.json"; do
    if [[ ! -f "${required}" ]]; then
      echo "ERROR: Required A11 input not found: ${required}" >&2
      exit 2
    fi
  done
done

PYTHON_VERSION="$(${PYTHON_BIN} -c 'import platform; print(platform.python_version())')"
PYTHON_MAJOR_MINOR="$(${PYTHON_BIN} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "${PYTHON_MAJOR_MINOR}" != "3.11" ]]; then
  echo "ERROR: A12 requires Python 3.11.x; found ${PYTHON_VERSION}" >&2
  exit 2
fi

PY_SCRIPT_SHA256="$(sha256sum "${PY_SCRIPT}" | awk '{print $1}')"
A05_CODE_SHA256="$(sha256sum "${A05_ROOT}/python_code_unit_manifest.csv" | awk '{print $1}')"
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
echo "run-x-a12-v2: aggregate FUN NPR to snapshot/file and repo-month/file"
echo "Started:                         $(date)"
echo "Project root:                    ${PROJECT_ROOT}"
echo "Python:                          $(command -v "${PYTHON_BIN}") (${PYTHON_VERSION})"
echo "Python script:                   ${PY_SCRIPT}"
echo "Python script SHA256:            ${PY_SCRIPT_SHA256}"
echo "A05 root:                        ${A05_ROOT}"
echo "A05 code manifest SHA256:        ${A05_CODE_SHA256}"
echo "A11 results root:                ${A11_RESULTS_ROOT}"
echo "Repo-month panel:                ${REPO_MONTH_PANEL_FILE}"
echo "Repo-month panel SHA256:         ${PANEL_SHA256}"
echo "Output directory:                ${OUTPUT_DIR}"
echo "Scope:                           FUN = primary regular function_body only"
echo "Unique score expansion:          A11 SHA -> every A05 occurrence"
echo "File weighting:                  space-by-token weighted"
echo "Pooled NPR:                      perturbed component / original component"
echo "No-FUN file policy:              missing FUN coverage; NPR remains blank"
echo "Expected A11 exclusions:         propagated; never imputed"
echo "Repo-month mapping:              authoritative panel; no month-range inference"
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
echo "run-x-a12-v2 execution summary"
echo "Started:          $(date -d "@${START_EPOCH}" 2>/dev/null || true)"
echo "Completed:        $(date)"
echo "Elapsed:          ${ELAPSED_TEXT}"
echo "Exit code:        ${EXIT_CODE}"
echo "Output directory: ${OUTPUT_DIR}"
echo "Log file:         ${LOG_FILE}"
if [[ -f "${OUTPUT_DIR}/python_fun_file_npr_scores.csv" ]]; then
  echo "Snapshot/file CSV lines:  $(wc -l < "${OUTPUT_DIR}/python_fun_file_npr_scores.csv")"
fi
if [[ -f "${OUTPUT_DIR}/python_fun_repo_month_file_npr_scores.csv" ]]; then
  echo "Repo-month/file CSV lines: $(wc -l < "${OUTPUT_DIR}/python_fun_repo_month_file_npr_scores.csv")"
fi
echo "============================================================================"

exit "${EXIT_CODE}"
