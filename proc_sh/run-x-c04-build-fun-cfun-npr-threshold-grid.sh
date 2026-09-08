#!/usr/bin/env bash
# Build the combined FUN+C_FUN historical NPR measurement and audit the frozen C01 threshold grid.
#
# This wrapper is standalone. It reuses the validated logic of the previous combined I01/I02
# pipeline but does not call or depend on those shell scripts.
#
# Inputs:
#   - A12 FUN repo-month/file continuous NPR artifact and summary.
#   - A15 C_FUN repo-month/file continuous NPR artifact and summary.
#   - C02 FUN threshold-audit summary and C03 C_FUN threshold-audit summary for branch provenance.
#   - C01 pooled StarCoder2-7B threshold specification and calibration summary.
#
# Outputs:
#   - Combined continuous FUN+C_FUN repo-month/file NPR artifact.
#   - Primary/sensitivity/anchor threshold audit tables.
#   - Treatment-timing and repo-month audit tables.
#   - Distribution, QC, summary, and metadata artifacts.
#
# Scientific policy:
#   - Primary metric is token-weighted recomputation across FUN and C_FUN continuous NPR values.
#   - Do not union the binary C02/C03 selections.
#   - No cross-category SHA deduplication.
#   - No-coverage remains missing, never zero.
#   - Primary decision rule is strict NPR > 1.515059.
#   - 1.5183 and 1.571637 are audit anchors only.
#   - No SonarQube or quality outcome is consumed.
#   - Every threshold is hard-reconciled across treatment strata and repo-month rows.
#   - Exact NPR equality at all audited thresholds is hard-checked.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/build_sc2_fun_cfun_npr_threshold_grid.py}"

A12_ROOT="${A12_ROOT:-output/snapshot_npr/run-x-a12}"
A15_ROOT="${A15_ROOT:-output/snapshot_npr/run-x-a15}"
C02_ROOT="${C02_ROOT:-output/snapshot_npr/run-x-c02/fun-threshold-v3}"
C03_ROOT="${C03_ROOT:-output/snapshot_npr/run-x-c03/cfun-threshold-v1}"
C01_ROOT="${C01_ROOT:-output/commit_function/run-x-c01/npr-sc2-pooled-threshold-v1}"
OUTPUT_DIR="${OUTPUT_DIR:-output/snapshot_npr/run-x-c04/fun-cfun-threshold-v2}"
LOG_DIR="${LOG_DIR:-logs/run-x-c04}"
OVERWRITE="${OVERWRITE:-0}"

A12_INPUT="${A12_ROOT}/python_fun_repo_month_file_npr_scores.csv"
A12_SUMMARY="${A12_ROOT}/summary.json"
A15_INPUT="${A15_ROOT}/python_cfun_repo_month_file_npr_scores.csv"
A15_SUMMARY="${A15_ROOT}/summary.json"
C02_SUMMARY="${C02_ROOT}/summary.json"
C03_SUMMARY="${C03_ROOT}/summary.json"
C01_SPEC="${C01_ROOT}/sc2_pooled_threshold_specification.json"
C01_SUMMARY="${C01_ROOT}/qc/sc2_pooled_calibration_summary.json"

PRIMARY_THRESHOLD="${PRIMARY_THRESHOLD:-1.515059}"
GRID_STEP="${GRID_STEP:-0.05}"
GRID_RADIUS="${GRID_RADIUS:-0.50}"
LEGACY_THRESHOLD="${LEGACY_THRESHOLD:-1.5183}"
PRIOR_PRIMARY_THRESHOLD="${PRIOR_PRIMARY_THRESHOLD:-1.571637}"

for path in "${PY_SCRIPT}" "${A12_INPUT}" "${A12_SUMMARY}" "${A15_INPUT}" "${A15_SUMMARY}" \
            "${C02_SUMMARY}" "${C03_SUMMARY}" "${C01_SPEC}" "${C01_SUMMARY}"; do
  if [[ ! -f "${path}" ]]; then
    echo "ERROR: required input does not exist: ${path}" >&2
    exit 2
  fi
done

if [[ -e "${OUTPUT_DIR}" && "${OVERWRITE}" != "1" ]]; then
  echo "ERROR: output directory already exists: ${OUTPUT_DIR}" >&2
  echo "Set OVERWRITE=1 only when intentionally rerunning this exact experiment version." >&2
  exit 2
fi

if [[ "${OVERWRITE}" == "1" ]]; then
  rm -rf "${OUTPUT_DIR}"
fi
mkdir -p "${OUTPUT_DIR}" "${LOG_DIR}"

STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_DIR}/run-x-c04-v2-build-fun-cfun-npr-threshold-grid-${STAMP}.log"
START_EPOCH="$(date +%s)"

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

{
  echo "============================================================================"
  echo "run-x-c04-v2: build combined FUN+C_FUN NPR and audit frozen C01 threshold"
  echo "Started:                         $(date)"
  echo "Project root:                    ${PROJECT_ROOT}"
  echo "Python:                          $(command -v "${PYTHON_BIN}") ($("${PYTHON_BIN}" --version 2>&1))"
  echo "Python script:                   ${PY_SCRIPT}"
  echo "Python script SHA256:            $(sha256_file "${PY_SCRIPT}")"
  echo "A12 input:                       ${A12_INPUT}"
  echo "A12 input SHA256:                $(sha256_file "${A12_INPUT}")"
  echo "A15 input:                       ${A15_INPUT}"
  echo "A15 input SHA256:                $(sha256_file "${A15_INPUT}")"
  echo "C02 summary:                     ${C02_SUMMARY}"
  echo "C03 summary:                     ${C03_SUMMARY}"
  echo "C01 threshold spec:              ${C01_SPEC}"
  echo "Output directory:                ${OUTPUT_DIR}"
  echo "Combined metric:                 file_npr_fun_cfun_space_by_token_weighted"
  echo "Combination weighting:           scored space-by-token counts"
  echo "Primary threshold T:             ${PRIMARY_THRESHOLD} (from run-x-c01)"
  echo "Grid:                            T +/- ${GRID_RADIUS} in ${GRID_STEP} increments (21 points)"
  echo "Legacy threshold anchor:         ${LEGACY_THRESHOLD}"
  echo "Prior paper primary anchor:      ${PRIOR_PRIMARY_THRESHOLD}"
  echo "Decision rule:                   NPR > threshold"
  echo "Quality/SonarQube input:         none"
  echo "Strict expected counts:          1"
  echo "Log file:                        ${LOG_FILE}"
  echo "============================================================================"

  "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test

  "${PYTHON_BIN}" "${PY_SCRIPT}" \
    --a12-input "${A12_INPUT}" \
    --a12-summary "${A12_SUMMARY}" \
    --a15-input "${A15_INPUT}" \
    --a15-summary "${A15_SUMMARY}" \
    --c02-summary "${C02_SUMMARY}" \
    --c03-summary "${C03_SUMMARY}" \
    --c01-spec "${C01_SPEC}" \
    --c01-summary "${C01_SUMMARY}" \
    --output-dir "${OUTPUT_DIR}" \
    --primary-threshold "${PRIMARY_THRESHOLD}" \
    --grid-step "${GRID_STEP}" \
    --grid-radius "${GRID_RADIUS}" \
    --legacy-threshold "${LEGACY_THRESHOLD}" \
    --prior-primary-threshold "${PRIOR_PRIMARY_THRESHOLD}" \
    --strict-expected-counts

  echo
  echo "============================================================================"
  echo "run-x-c04-v2 execution summary"
  echo "Completed:        $(date)"
  END_EPOCH="$(date +%s)"
  ELAPSED="$((END_EPOCH - START_EPOCH))"
  printf 'Elapsed:          %02d:%02d:%02d\n' "$((ELAPSED/3600))" "$(((ELAPSED%3600)/60))" "$((ELAPSED%60))"
  echo "Exit code:        0"
  echo "Output directory: ${OUTPUT_DIR}"
  echo "Log file:         ${LOG_FILE}"
  for file in \
    python_fun_cfun_repo_month_file_npr_scores.csv \
    fun_cfun_npr_threshold_spec.csv \
    fun_cfun_npr_threshold_audit.csv \
    fun_cfun_npr_threshold_by_treatment_timing.csv \
    fun_cfun_npr_threshold_repo_month_audit.csv \
    fun_cfun_npr_distribution_summary.csv \
    fun_cfun_npr_threshold_checks.csv; do
    if [[ -f "${OUTPUT_DIR}/${file}" ]]; then
      echo "${file}: $(wc -l < "${OUTPUT_DIR}/${file}") lines"
    fi
  done
  echo "============================================================================"
} 2>&1 | tee "${LOG_FILE}"
