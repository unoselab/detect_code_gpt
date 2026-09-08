#!/usr/bin/env bash
# Join frozen C04 combined FUN+C_FUN NPR measurements to historical file-level SonarQube issue stock.
#
# This wrapper is standalone. It was created by copying the validated C04 wrapper structure and
# adapting it to the historical I03 file-quality burden logic. It does not call or depend on any
# existing shell wrapper.
#
# Inputs:
#   - C04 v2 continuous combined FUN+C_FUN repo-month/file NPR artifact.
#   - C04 v2 summary and hard-QC table for detector-provenance validation.
#   - Frozen B05 unresolved Python-file SonarQube issue artifacts from the sibling
#     ai-code-complexity-study workspace.
#
# Outputs:
#   - C04 repo-month/file universe with unresolved SonarQube issue-stock columns appended.
#   - Snapshot-level reconciliation audit against authoritative B05 totals.
#   - Explicit list of B05 issue-bearing Python files outside the frozen C04/A05 file universe.
#   - QC, summary, and metadata artifacts.
#
# Scientific policy:
#   - Preserve C04 continuous metric file_npr_fun_cfun_space_by_token_weighted.
#   - Do not apply the 1.515059 threshold in C05; threshold aggregation remains downstream.
#   - Join on snapshot_id == snapshot_key and relative_path == component_path.
#   - B05 issue-bearing paths outside C04 are explicit scope exclusions, never silent drops.
#   - A C04 file with no matching B05 issue row has zero unresolved issue stock.
#   - No SonarQube rescan is performed.
#   - No GPU or LLM model is loaded.
#   - Density is deferred because file-level SonarQube NCLOC is not part of this join.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/build_sc2_fun_cfun_npr_file_quality_burden.py}"

C04_ROOT="${C04_ROOT:-output/snapshot_npr/run-x-c04/fun-cfun-threshold-v2}"
AI_COMPLEXITY_ROOT="${AI_COMPLEXITY_ROOT:-${PROJECT_ROOT}/../ai_code_complexity_study_python/ai-code-complexity-study}"
B05_ROOT="${B05_ROOT:-${AI_COMPLEXITY_ROOT}/repo_x01/run-x-b05}"
OUTPUT_DIR="${OUTPUT_DIR:-output/snapshot_npr/run-x-c05/file-quality-burden-v1}"
LOG_DIR="${LOG_DIR:-logs/run-x-c05}"
OVERWRITE="${OVERWRITE:-0}"

C04_FILE="${C04_ROOT}/python_fun_cfun_repo_month_file_npr_scores.csv"
C04_SUMMARY="${C04_ROOT}/summary.json"
C04_CHECKS="${C04_ROOT}/fun_cfun_npr_threshold_checks.csv"

B05_RAW_ISSUES="${B05_ROOT}/python_sonarqube_issues.csv.gz"
B05_SNAPSHOT_COUNTS="${B05_ROOT}/python_sonarqube_issue_snapshot_counts.csv"
B05_QC="${B05_ROOT}/python_sonarqube_issue_qc.csv"
B05_SUMMARY="${B05_ROOT}/python_sonarqube_issue_summary.csv"

for path in "${PY_SCRIPT}" "${C04_FILE}" "${C04_SUMMARY}" "${C04_CHECKS}" \
            "${B05_RAW_ISSUES}" "${B05_SNAPSHOT_COUNTS}" "${B05_QC}" "${B05_SUMMARY}"; do
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
LOG_FILE="${LOG_DIR}/run-x-c05-v1-build-fun-cfun-npr-file-quality-burden-${STAMP}.log"
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
  echo "run-x-c05-v1: join C04 FUN+C_FUN NPR to frozen B05 file-level SonarQube burden"
  echo "Started:                         $(date)"
  echo "Project root:                    ${PROJECT_ROOT}"
  echo "Python:                          $(command -v "${PYTHON_BIN}") ($("${PYTHON_BIN}" --version 2>&1))"
  echo "Python script:                   ${PY_SCRIPT}"
  echo "Python script SHA256:            $(sha256_file "${PY_SCRIPT}")"
  echo "C04 continuous input:            ${C04_FILE}"
  echo "C04 input SHA256:                $(sha256_file "${C04_FILE}")"
  echo "C04 summary:                     ${C04_SUMMARY}"
  echo "C04 summary SHA256:              $(sha256_file "${C04_SUMMARY}")"
  echo "C04 hard-QC table:               ${C04_CHECKS}"
  echo "B05 raw issues:                  ${B05_RAW_ISSUES}"
  echo "B05 raw issues SHA256:           $(sha256_file "${B05_RAW_ISSUES}")"
  echo "B05 snapshot counts:             ${B05_SNAPSHOT_COUNTS}"
  echo "B05 snapshot counts SHA256:      $(sha256_file "${B05_SNAPSHOT_COUNTS}")"
  echo "B05 QC:                          ${B05_QC}"
  echo "B05 QC SHA256:                   $(sha256_file "${B05_QC}")"
  echo "B05 summary:                     ${B05_SUMMARY}"
  echo "B05 summary SHA256:              $(sha256_file "${B05_SUMMARY}")"
  echo "Output directory:                ${OUTPUT_DIR}"
  echo "NPR metric preserved:            file_npr_fun_cfun_space_by_token_weighted"
  echo "Primary threshold provenance:    1.515059 from C04/C01; NOT applied in C05"
  echo "Quality scope:                   unresolved Python-file SonarQube issue stock"
  echo "Join keys:                       snapshot_id + relative_path"
  echo "SonarQube rescan:                 none"
  echo "GPU/LLM scoring:                  none"
  echo "Density:                         deferred until file-level NCLOC is available"
  echo "Strict expected counts:          1"
  echo "Log file:                        ${LOG_FILE}"
  echo "============================================================================"

  "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test
  "${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"

  "${PYTHON_BIN}" "${PY_SCRIPT}" \
    --c04-file "${C04_FILE}" \
    --c04-summary-file "${C04_SUMMARY}" \
    --c04-checks-file "${C04_CHECKS}" \
    --b05-raw-issues-file "${B05_RAW_ISSUES}" \
    --b05-snapshot-counts-file "${B05_SNAPSHOT_COUNTS}" \
    --b05-qc-file "${B05_QC}" \
    --b05-summary-file "${B05_SUMMARY}" \
    --output-dir "${OUTPUT_DIR}" \
    --strict-expected-counts

  echo
  echo "============================================================================"
  echo "run-x-c05-v1 execution summary"
  echo "Completed:        $(date)"
  END_EPOCH="$(date +%s)"
  ELAPSED="$((END_EPOCH - START_EPOCH))"
  printf 'Elapsed:          %02d:%02d:%02d\n' "$((ELAPSED/3600))" "$(((ELAPSED%3600)/60))" "$((ELAPSED%60))"
  echo "Exit code:        0"
  echo "Output directory: ${OUTPUT_DIR}"
  echo "Log file:         ${LOG_FILE}"
  for file in \
    python_fun_cfun_file_quality_burden.csv.gz \
    python_fun_cfun_file_quality_snapshot_audit.csv \
    python_sonarqube_issue_files_outside_c04.csv \
    python_fun_cfun_file_quality_checks.csv \
    python_fun_cfun_file_quality_summary.csv \
    summary.json \
    metadata.json; do
    if [[ -f "${OUTPUT_DIR}/${file}" ]]; then
      if [[ "${file}" == *.gz ]]; then
        echo "${file}: $(gzip -cd "${OUTPUT_DIR}/${file}" | wc -l) lines"
      else
        echo "${file}: $(wc -l < "${OUTPUT_DIR}/${file}") lines"
      fi
    fi
  done
  echo "============================================================================"
} 2>&1 | tee "${LOG_FILE}"
