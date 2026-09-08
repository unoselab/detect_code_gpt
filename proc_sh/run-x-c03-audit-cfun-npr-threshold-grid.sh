#!/usr/bin/env bash
# Audit the C_FUN file-NPR threshold grid using the frozen C01 pooled SC2-7B threshold.
#
# This wrapper is standalone. It was copied from the validated run-x-c02 threshold-audit
# wrapper, then adapted for C_FUN and cross-checked against the earlier run-x-h01 C_FUN
# threshold-audit design. It does not call or depend on any previous shell wrapper.
#
# Versioned delivery files:
#   code-detection/audit_sc2_cfun_npr_threshold_grid-v1.py
#   proc_sh/run-x-c03-audit-cfun-npr-threshold-grid-v1.sh
#
# Canonical server paths after deployment:
#   code-detection/audit_sc2_cfun_npr_threshold_grid.py
#   proc_sh/run-x-c03-audit-cfun-npr-threshold-grid.sh
#
# Required inputs:
#   output/snapshot_npr/run-x-a15/python_cfun_repo_month_file_npr_scores.csv
#       A15 repo-month/Python-file C_FUN NPR artifact from the same detect_code_gpt workspace.
#   output/snapshot_npr/run-x-a15/summary.json
#       A15 terminal summary. C03 requires run-x-a15-v1 with zero hard QC failures.
#
# C01 threshold provenance:
#   output/commit_function/run-x-c01/npr-sc2-pooled-threshold-v1/sc2_pooled_threshold_specification.json
#   output/commit_function/run-x-c01/npr-sc2-pooled-threshold-v1/qc/sc2_pooled_calibration_summary.json
#   C03 validates C01 model, population, algorithm, and threshold fields before classification.
#
# Historical scorer provenance:
#   output/snapshot_npr/run-x-a15/metadata.json
#   output/snapshot_npr/run-x-a14/results/gpu-{0,1,2}/metadata.json
#   output/snapshot_npr/run-x-a11/results/gpu-{0,1,2}/metadata.json (A13-directed overlap reuse)
#   ~/.cache/huggingface/hub/models--bigcode--starcoder2-7b/refs/main
#   Expected StarCoder2-7B revision: bb9afde76d7945da5745592525db122d4d729eb1
#
# Frozen threshold specification:
#   Primary T: 1.515059 (run-x-c01 pooled five-source SC2-7B calibration)
#   Main grid: T + delta, delta=-0.50,-0.45,...,0,...,+0.45,+0.50
#   Legacy anchor: 1.5183
#   Prior paper primary anchor: 1.571637
#   Decision rule: file_npr_cfun_space_by_token_weighted > threshold
#
# Treatment timing:
#   treatment_group = event_index > 0
#   event_time_normalized = time_index - event_index for treatment repositories
#   absorbing_treated = event_index > 0 and time_index >= event_index
#   Legacy is_treatment/post_event/cursor flags are not used.
#
# Main outputs under output/snapshot_npr/run-x-c03/cfun-threshold-v1/:
#   cfun_npr_threshold_spec.csv
#       Frozen 21-point symmetric grid plus separately named legacy and prior-primary anchors.
#   cfun_npr_threshold_audit.csv
#       Global selected counts/shares for every threshold.
#   cfun_npr_threshold_by_treatment_timing.csv
#       Threshold audit by control, treatment-pre, treatment-post, and treatment-all.
#   cfun_npr_threshold_repo_month_audit.csv
#       One row per threshold x Model A repo-month for pre-SonarQube sample-composition QC.
#   cfun_npr_distribution_summary.csv
#       Continuous C_FUN NPR distribution summaries before any quality outcome is read.
#   cfun_npr_threshold_checks.csv
#   summary.json
#   metadata.json
#
# Important boundary:
#   C01 selected the threshold from detector-benchmark data only. C03 does not read SonarQube
#   or any quality outcome; it transfers the already-frozen C01 threshold to historical C_FUN NPR.
#
# Runtime:
#   Python 3.11.x. CPU only; no model/GPU use.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"
export PROJECT_ROOT

RUN_PREFIX="run-x-c03"
IMPLEMENTATION_VERSION="v1"
RUN_LABEL="${RUN_PREFIX}-${IMPLEMENTATION_VERSION}"
RUN_TS="${RUN_TS:-$(date +%Y%m%d-%H%M%S)}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/audit_sc2_cfun_npr_threshold_grid.py}"
A15_INPUT_FILE="${A15_INPUT_FILE:-output/snapshot_npr/run-x-a15/python_cfun_repo_month_file_npr_scores.csv}"
A15_SUMMARY_FILE="${A15_SUMMARY_FILE:-output/snapshot_npr/run-x-a15/summary.json}"
A15_METADATA_FILE="${A15_METADATA_FILE:-output/snapshot_npr/run-x-a15/metadata.json}"
C01_ROOT="${C01_ROOT:-output/commit_function/run-x-c01/npr-sc2-pooled-threshold-v1}"
C01_THRESHOLD_SPEC_FILE="${C01_THRESHOLD_SPEC_FILE:-${C01_ROOT}/sc2_pooled_threshold_specification.json}"
C01_SUMMARY_FILE="${C01_SUMMARY_FILE:-${C01_ROOT}/qc/sc2_pooled_calibration_summary.json}"
A14_RESULTS_ROOT="${A14_RESULTS_ROOT:-output/snapshot_npr/run-x-a14/results}"
A11_RESULTS_ROOT="${A11_RESULTS_ROOT:-output/snapshot_npr/run-x-a11/results}"
SC2_CACHE_REF_FILE="${SC2_CACHE_REF_FILE:-${HOME}/.cache/huggingface/hub/models--bigcode--starcoder2-7b/refs/main}"
EXPECTED_SC2_MODEL_REVISION="bb9afde76d7945da5745592525db122d4d729eb1"
OUTPUT_DIR="${OUTPUT_DIR:-output/snapshot_npr/run-x-c03/cfun-threshold-v1}"
LOG_DIR="${LOG_DIR:-logs/run-x-c03}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/${RUN_LABEL}-audit-cfun-npr-threshold-grid-${RUN_TS}.log}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
STRICT_EXPECTED_COUNTS="${STRICT_EXPECTED_COUNTS:-1}"

PRIMARY_THRESHOLD="1.515059"
GRID_STEP="0.05"
GRID_RADIUS="0.50"
LEGACY_THRESHOLD="1.5183"
PRIOR_PRIMARY_THRESHOLD="1.571637"

for required_file in "${PY_SCRIPT}" "${A15_INPUT_FILE}" "${A15_SUMMARY_FILE}" "${A15_METADATA_FILE}" "${C01_THRESHOLD_SPEC_FILE}" "${C01_SUMMARY_FILE}" "${SC2_CACHE_REF_FILE}"; do
  if [[ ! -f "${required_file}" ]]; then
    echo "ERROR: required file not found: ${required_file}" >&2
    exit 2
  fi
done

if [[ ! -d "${A14_RESULTS_ROOT}" ]]; then
  echo "ERROR: A14 results root not found: ${A14_RESULTS_ROOT}" >&2
  exit 2
fi
for gpu_index in 0 1 2; do
  if [[ ! -f "${A14_RESULTS_ROOT}/gpu-${gpu_index}/metadata.json" ]]; then
    echo "ERROR: required A14 metadata not found: ${A14_RESULTS_ROOT}/gpu-${gpu_index}/metadata.json" >&2
    exit 2
  fi
done

if [[ ! -d "${A11_RESULTS_ROOT}" ]]; then
  echo "ERROR: A11 results root not found: ${A11_RESULTS_ROOT}" >&2
  exit 2
fi
for gpu_index in 0 1 2; do
  if [[ ! -f "${A11_RESULTS_ROOT}/gpu-${gpu_index}/metadata.json" ]]; then
    echo "ERROR: required A11 metadata not found: ${A11_RESULTS_ROOT}/gpu-${gpu_index}/metadata.json" >&2
    exit 2
  fi
done

SC2_CACHE_REVISION="$(tr -d '[:space:]' < "${SC2_CACHE_REF_FILE}")"
if [[ "${SC2_CACHE_REVISION}" != "${EXPECTED_SC2_MODEL_REVISION}" ]]; then
  echo "ERROR: StarCoder2-7B cache revision mismatch: ${SC2_CACHE_REVISION}" >&2
  echo "Expected: ${EXPECTED_SC2_MODEL_REVISION}" >&2
  exit 2
fi

PYTHON_VERSION="$(${PYTHON_BIN} -c 'import platform; print(platform.python_version())')"
PYTHON_MAJOR_MINOR="$(${PYTHON_BIN} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "${PYTHON_MAJOR_MINOR}" != "3.11" ]]; then
  echo "ERROR: C03 requires Python 3.11.x; found ${PYTHON_VERSION}" >&2
  exit 2
fi

mkdir -p "${OUTPUT_DIR}" "${LOG_DIR}"
PY_SCRIPT_SHA256="$(sha256sum "${PY_SCRIPT}" | awk '{print $1}')"
A15_INPUT_SHA256="$(sha256sum "${A15_INPUT_FILE}" | awk '{print $1}')"
A15_SUMMARY_SHA256="$(sha256sum "${A15_SUMMARY_FILE}" | awk '{print $1}')"
A15_METADATA_SHA256="$(sha256sum "${A15_METADATA_FILE}" | awk '{print $1}')"
C01_THRESHOLD_SPEC_SHA256="$(sha256sum "${C01_THRESHOLD_SPEC_FILE}" | awk '{print $1}')"
C01_SUMMARY_SHA256="$(sha256sum "${C01_SUMMARY_FILE}" | awk '{print $1}')"

exec > >(tee "${LOG_FILE}") 2>&1

START_EPOCH="$(date +%s)"
echo "============================================================================"
echo "${RUN_LABEL}: audit C_FUN file-NPR grid with frozen C01 SC2-7B threshold"
echo "Started:                         $(date)"
echo "Project root:                    ${PROJECT_ROOT}"
echo "Python:                          $(command -v "${PYTHON_BIN}") (${PYTHON_VERSION})"
echo "Python script:                   ${PY_SCRIPT}"
echo "Python script SHA256:            ${PY_SCRIPT_SHA256}"
echo "A15 input:                       ${A15_INPUT_FILE}"
echo "A15 input SHA256:                ${A15_INPUT_SHA256}"
echo "A15 summary:                     ${A15_SUMMARY_FILE}"
echo "A15 summary SHA256:              ${A15_SUMMARY_SHA256}"
echo "A15 metadata:                    ${A15_METADATA_FILE}"
echo "A15 metadata SHA256:             ${A15_METADATA_SHA256}"
echo "C01 threshold spec:              ${C01_THRESHOLD_SPEC_FILE}"
echo "C01 threshold spec SHA256:       ${C01_THRESHOLD_SPEC_SHA256}"
echo "C01 calibration summary:         ${C01_SUMMARY_FILE}"
echo "C01 calibration summary SHA256:  ${C01_SUMMARY_SHA256}"
echo "A14 results root:                ${A14_RESULTS_ROOT}"
echo "A11 reuse results root:          ${A11_RESULTS_ROOT}"
echo "SC2 cache ref file:              ${SC2_CACHE_REF_FILE}"
echo "SC2 cache revision:              ${SC2_CACHE_REVISION}"
echo "Output directory:                ${OUTPUT_DIR}"
echo "Metric:                          file_npr_cfun_space_by_token_weighted"
echo "Primary threshold T:             ${PRIMARY_THRESHOLD} (from run-x-c01)"
echo "Grid:                            T +/- ${GRID_RADIUS} in ${GRID_STEP} increments (21 points)"
echo "Legacy threshold anchor:         ${LEGACY_THRESHOLD}"
echo "Prior paper primary anchor:      ${PRIOR_PRIMARY_THRESHOLD}"
echo "Decision rule:                   NPR > threshold"
echo "Treatment timing:                normalized event_index/time_index; legacy flags ignored"
echo "Quality/SonarQube input:         none"
echo "Strict expected counts:          ${STRICT_EXPECTED_COUNTS}"
echo "Log file:                        ${LOG_FILE}"
echo "============================================================================"

if [[ "${RUN_SELF_TEST}" == "1" ]]; then
  "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test
fi

ARGS=(
  --input-file "${A15_INPUT_FILE}"
  --a15-summary-file "${A15_SUMMARY_FILE}"
  --a15-metadata-file "${A15_METADATA_FILE}"
  --a14-results-root "${A14_RESULTS_ROOT}"
  --c01-threshold-spec-file "${C01_THRESHOLD_SPEC_FILE}"
  --c01-summary-file "${C01_SUMMARY_FILE}"
  --a11-results-root "${A11_RESULTS_ROOT}"
  --sc2-cache-ref-file "${SC2_CACHE_REF_FILE}"
  --output-dir "${OUTPUT_DIR}"
  --primary-threshold "${PRIMARY_THRESHOLD}"
  --grid-step "${GRID_STEP}"
  --grid-radius "${GRID_RADIUS}"
  --legacy-threshold "${LEGACY_THRESHOLD}"
  --prior-primary-threshold "${PRIOR_PRIMARY_THRESHOLD}"
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
echo "${RUN_LABEL} execution summary"
echo "Completed:        $(date)"
echo "Elapsed:          ${ELAPSED_TEXT}"
echo "Exit code:        ${EXIT_CODE}"
echo "Output directory: ${OUTPUT_DIR}"
echo "Log file:         ${LOG_FILE}"
for output_file in \
  cfun_npr_threshold_spec.csv \
  cfun_npr_threshold_audit.csv \
  cfun_npr_threshold_by_treatment_timing.csv \
  cfun_npr_threshold_repo_month_audit.csv \
  cfun_npr_distribution_summary.csv \
  cfun_npr_threshold_checks.csv; do
  if [[ -f "${OUTPUT_DIR}/${output_file}" ]]; then
    echo "${output_file}: $(wc -l < "${OUTPUT_DIR}/${output_file}") lines"
  fi
done
echo "============================================================================"

exit "${EXIT_CODE}"
