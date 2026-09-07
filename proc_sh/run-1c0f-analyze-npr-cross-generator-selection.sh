#!/usr/bin/env bash
# run-1c0f: NPR cross-generator scoring-model selection analysis.
#
# Purpose
# -------
# Reconstruct the 5 x 5 NPR AUROC matrix, quantify uncertainty with a
# length-stratified mixed-authorship-file cluster bootstrap, evaluate
# same-generator and cross-generator transfer performance, and apply the
# minimax-regret criterion used for downstream scoring-model selection.
#
# Required inputs
# ---------------
# INPUT_ROOTS
#   Colon-separated directories containing the current cross-generator
#   per-procedure score CSVs. Across these roots, all 25 scorer x target cells
#   must be present exactly once (or be byte/numerically equivalent duplicates).
#
#   Recommended consolidated layout on the analysis host:
#     output/commit_function/run-1c0d/npr-cross-generator-v1
#       - CodeLlama-7B row
#       - StarCoder2-7B row
#       - StarCoder2-15B row
#       - GPT-OSS-120B row
#     output/commit_function/run-1c0e/npr-cross-generator-v1
#       - Gemma4-31B row
#
# Optional input
# --------------
# LEGACY_GEMMA_SCORE_CSV
#   Earlier Gemma same-generator per-procedure NPR score CSV. When present, the
#   Python analysis compares it with the current Gemma diagonal result as a
#   reproducibility audit. It is not used in the primary selection criterion.
#
# Outputs
# -------
# OUTPUT_ROOT receives the AUROC matrix, point estimates, bootstrap summaries,
# minimax-regret results, pairwise comparisons, Pareto diagnostics, Gemma audit,
# methodology, metadata, and a concise candidate-selection summary.
#
# Development/deployment naming
# -----------------------------
# This delivered wrapper has a -v2 suffix. Before execution on the server,
# remove the suffix from both files:
#   run-1c0f-analyze-npr-cross-generator-selection.sh
#   analyze_npr_cross_generator_selection.py
# The wrapper intentionally references the unversioned server Python filename.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python}"
PYTHON_SCRIPT="${PROJECT_ROOT}/code-detection/analyze_npr_cross_generator_selection.py"

INPUT_ROOTS="${INPUT_ROOTS:-${PROJECT_ROOT}/output/commit_function/run-1c0d/npr-cross-generator-v1:${PROJECT_ROOT}/output/commit_function/run-1c0e/npr-cross-generator-v1}"
LEGACY_GEMMA_SCORE_NAME="npr_scores_main_mixedcode_benchmark_mixedcode_gemma-4-31b_50files_overlap-v1.csv"
LEGACY_GEMMA_EXPLICIT=0
if [[ -n "${LEGACY_GEMMA_SCORE_CSV+x}" ]]; then
    LEGACY_GEMMA_EXPLICIT=1
else
    LEGACY_GEMMA_SCORE_CSV="${PROJECT_ROOT}/output/commit_function/run-1c0a/mixedcode-overlap-v1/${LEGACY_GEMMA_SCORE_NAME}"
fi
OUTPUT_ROOT="${OUTPUT_ROOT:-${PROJECT_ROOT}/output/commit_function/run-1c0f/npr-cross-generator-selection-v2}"
BOOTSTRAP_REPS="${BOOTSTRAP_REPS:-20000}"
RANDOM_SEED="${RANDOM_SEED:-20260723}"
CONFIDENCE="${CONFIDENCE:-0.95}"

LOG_DIR="${PROJECT_ROOT}/logs/run-1c0f"
mkdir -p "${LOG_DIR}" "${OUTPUT_ROOT}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_DIR}/run-1c0f-npr-xgen-selection-${TIMESTAMP}.log"

if [[ ! -f "${PYTHON_SCRIPT}" ]]; then
    echo "ERROR: Python analysis script not found: ${PYTHON_SCRIPT}" >&2
    exit 2
fi

IFS=':' read -r -a INPUT_ROOT_ARRAY <<< "${INPUT_ROOTS}"
if [[ "${#INPUT_ROOT_ARRAY[@]}" -eq 0 ]]; then
    echo "ERROR: INPUT_ROOTS is empty." >&2
    exit 2
fi

PY_ARGS=(
    "${PYTHON_SCRIPT}"
    "--output-root" "${OUTPUT_ROOT}"
    "--bootstrap-reps" "${BOOTSTRAP_REPS}"
    "--seed" "${RANDOM_SEED}"
    "--confidence" "${CONFIDENCE}"
)

for root in "${INPUT_ROOT_ARRAY[@]}"; do
    if [[ ! -d "${root}" ]]; then
        echo "ERROR: Input root does not exist: ${root}" >&2
        exit 2
    fi
    PY_ARGS+=("--input-root" "${root}")
done

if [[ ! -f "${LEGACY_GEMMA_SCORE_CSV}" && "${LEGACY_GEMMA_EXPLICIT}" -eq 0 ]]; then
    AUTO_LEGACY_GEMMA="$(find "${PROJECT_ROOT}/output" -type f -name "${LEGACY_GEMMA_SCORE_NAME}" -print -quit 2>/dev/null || true)"
    if [[ -n "${AUTO_LEGACY_GEMMA}" ]]; then
        LEGACY_GEMMA_SCORE_CSV="${AUTO_LEGACY_GEMMA}"
    fi
fi

if [[ -f "${LEGACY_GEMMA_SCORE_CSV}" ]]; then
    PY_ARGS+=("--legacy-gemma-score-csv" "${LEGACY_GEMMA_SCORE_CSV}")
elif [[ "${LEGACY_GEMMA_EXPLICIT}" -eq 1 ]]; then
    echo "ERROR: Explicit LEGACY_GEMMA_SCORE_CSV does not exist: ${LEGACY_GEMMA_SCORE_CSV}" >&2
    exit 2
else
    echo "WARNING: Legacy Gemma score CSV not found; optional Gemma reproducibility audit will be skipped." >&2
fi

PYTHON_SHA="$(sha256sum "${PYTHON_SCRIPT}" | awk '{print $1}')"

{
    echo "============================================================================"
    echo "run-1c0f v2: NPR cross-generator scoring-model selection"
    echo "Started:                         $(date)"
    echo "Workspace:                       ${PROJECT_ROOT}"
    echo "Host:                            $(hostname -f 2>/dev/null || hostname)"
    echo "Active conda env:                ${CONDA_DEFAULT_ENV:-<none>}"
    echo "Python path:                     $(command -v "${PYTHON_BIN}")"
    echo "Python version:                  $("${PYTHON_BIN}" --version 2>&1)"
    echo "Python script:                   ${PYTHON_SCRIPT}"
    echo "Python script SHA:               ${PYTHON_SHA}"
    echo "Input roots:                     ${INPUT_ROOTS}"
    echo "Legacy Gemma score CSV:          ${LEGACY_GEMMA_SCORE_CSV}"
    echo "Output root:                     ${OUTPUT_ROOT}"
    echo "Bootstrap replicates:            ${BOOTSTRAP_REPS}"
    echo "Random seed:                     ${RANDOM_SEED}"
    echo "Confidence level:                ${CONFIDENCE}"
    echo "Bootstrap unit:                  mixed-authorship file within length bucket"
    echo "Log file:                        ${LOG_FILE}"
    echo "============================================================================"
} | tee "${LOG_FILE}"

set +e
"${PYTHON_BIN}" "${PY_ARGS[@]}" 2>&1 | tee -a "${LOG_FILE}"
STATUS=${PIPESTATUS[0]}
set -e

{
    echo "============================================================================"
    echo "Completed:                       $(date)"
    echo "Exit code:                       ${STATUS}"
    if [[ "${STATUS}" -eq 0 ]]; then
        echo "Status:                          PASS"
    else
        echo "Status:                          FAIL"
    fi
    echo "============================================================================"
} | tee -a "${LOG_FILE}"

exit "${STATUS}"
