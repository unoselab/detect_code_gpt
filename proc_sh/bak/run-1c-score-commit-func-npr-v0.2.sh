#!/usr/bin/env bash
# Run a deterministic dual-profile StarCoder2 NPR pilot.
#
# Workspace:
#   ~/project-workspace/detect_code_gpt
#
# Versioned delivery file:
#   proc_sh/run-1c-score-commit-func-npr-v4.sh
#
# Canonical path:
#   proc_sh/run-1c-score-commit-func-npr.sh
#
# Purpose:
#   Measure scoring correctness, throughput, cache size, GPU memory, resume
#   behavior, and same-seed reproducibility before full commit-function NPR
#   scoring. The pilot contains two deterministic profiles:
#
#   1. 100 bodies from the benchmark-compatible 100-200 token range.
#   2. 100 bodies above 200 tokens, stratified by 128-token window count.
#
# Partial-body policy:
#   A body may succeed with one excluded window only when that window is a
#   true incomplete final tail and its original_log_rank is exactly zero.
#   Invalid non-tail windows, full-size final windows, and other invalid-tail
#   reasons are recorded as body scoring failures.
#
# The wrapper is standalone. It reuses the execution, logging, validation,
# and output-verification structure of run-1b2 and the CUDA invocation pattern
# of the existing mixed-code benchmark runner, but it does not call either
# existing shell wrapper.
#
# Main inputs:
#   output/commit_function/run-1a/strict/
#     commit_function_detectcodegpt_unique_bodies.csv
#     commit_function_detectcodegpt_input_events.csv
#   output/commit_function/run-1b/strict/
#     commit_function_body_eligibility_support.csv
#     commit_function_detectcodegpt_scoring_spec.json
#   ../ai_code_complexity_study_python/ai-code-complexity-study/
#     repo_python/run-py-4a/strict/panel_event_monthly_agc_changed_block_py.csv
#
# Main outputs:
#   output/commit_function/run-1c/pilot200-dual-profile-v4/
#     commit_function_npr_pilot_manifest.csv
#     commit_function_npr_body_scores.csv
#     commit_function_npr_window_scores.csv
#     commit_function_npr_runtime_metrics.csv
#     commit_function_npr_full_run_estimates.csv
#     commit_function_npr_checkpoint_index.csv
#     commit_function_npr_failures.csv
#     cache/body_results/
#     qc/commit_function_npr_checks.csv
#     qc/commit_function_npr_summary.json
#     qc/commit_function_npr_metadata.json
#     qc/commit_function_npr_reproducibility_checks.csv
#     qc/commit_function_npr_run_history.jsonl
#
# Optional environment variables:
#   PROJECT_ROOT, PYTHON_BIN, PY_SCRIPT, RUN1A_DIR, RUN1B_DIR,
#   INPUT_UNIQUE_BODIES, INPUT_EVENTS, INPUT_PANEL, INPUT_SUPPORT,
#   INPUT_SPECIFICATION, BODY_ARTIFACT_BASE, OUTPUT_DIR, QC_DIR, CACHE_DIR,
#   LOG_DIR, CUDA_DEVICE, CUDA_VISIBLE_DEVICES, MODEL_CACHE_DIR,
#   CALIBRATION_PROFILE_SIZE, LONG_PROFILE_SIZE, CALIBRATION_BANDS,
#   LONG_WINDOW_STRATA, REPRODUCIBILITY_CHECK_PER_PROFILE,
#   PROGRESS_EVERY_BODIES, OVERWRITE_OUTPUT, RUN_SELF_TEST,
#   RUN_RESUME_CHECK, PREPARE_ONLY, ALLOW_CPU
# 
# Usage:
#  PYTHONUNBUFFERED=1 OVERWRITE_OUTPUT=1 CUDA_DEVICE=0 bash proc_sh/run-1c-score-commit-func-npr.sh
# 

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/score_commit_function_npr.py}"

RUN1A_DIR="${RUN1A_DIR:-output/commit_function/run-1a/strict}"
RUN1B_DIR="${RUN1B_DIR:-output/commit_function/run-1b/strict}"
INPUT_UNIQUE_BODIES="${INPUT_UNIQUE_BODIES:-${RUN1A_DIR}/commit_function_detectcodegpt_unique_bodies.csv}"
INPUT_EVENTS="${INPUT_EVENTS:-${RUN1A_DIR}/commit_function_detectcodegpt_input_events.csv}"
INPUT_PANEL="${INPUT_PANEL:-../ai_code_complexity_study_python/ai-code-complexity-study/repo_python/run-py-4a/strict/panel_event_monthly_agc_changed_block_py.csv}"
INPUT_SUPPORT="${INPUT_SUPPORT:-${RUN1B_DIR}/commit_function_body_eligibility_support.csv}"
INPUT_SPECIFICATION="${INPUT_SPECIFICATION:-${RUN1B_DIR}/commit_function_detectcodegpt_scoring_spec.json}"
BODY_ARTIFACT_BASE="${BODY_ARTIFACT_BASE:-${RUN1A_DIR}}"

CALIBRATION_PROFILE_SIZE="${CALIBRATION_PROFILE_SIZE:-100}"
LONG_PROFILE_SIZE="${LONG_PROFILE_SIZE:-100}"
CALIBRATION_BANDS="${CALIBRATION_BANDS:-100:110,111:120,121:130,131:140,141:150,151:160,161:170,171:180,181:190,191:200}"
LONG_WINDOW_STRATA="${LONG_WINDOW_STRATA:-2:2,3:4,5:8,9:16,17:}"
REPRODUCIBILITY_CHECK_PER_PROFILE="${REPRODUCIBILITY_CHECK_PER_PROFILE:-1}"
PROGRESS_EVERY_BODIES="${PROGRESS_EVERY_BODIES:-5}"

OUTPUT_DIR="${OUTPUT_DIR:-output/commit_function/run-1c/pilot200-dual-profile-v4}"
QC_DIR="${QC_DIR:-${OUTPUT_DIR}/qc}"
CACHE_DIR="${CACHE_DIR:-${OUTPUT_DIR}/cache}"
LOG_DIR="${LOG_DIR:-logs/run-1c}"
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-${HOME}/.cache/huggingface/hub}"

CUDA_DEVICE="${CUDA_DEVICE:-0}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-${CUDA_DEVICE}}"
export TOKENIZERS_PARALLELISM="false"

OVERWRITE_OUTPUT="${OVERWRITE_OUTPUT:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
RUN_RESUME_CHECK="${RUN_RESUME_CHECK:-1}"
PREPARE_ONLY="${PREPARE_ONLY:-0}"
ALLOW_CPU="${ALLOW_CPU:-0}"

TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/run-1c-score-commit-func-npr-pilot-v4-${TIMESTAMP}.log}"

MANIFEST_OUTPUT="${OUTPUT_DIR}/commit_function_npr_pilot_manifest.csv"
PROFILE_SUPPORT_OUTPUT="${OUTPUT_DIR}/commit_function_npr_pilot_profile_support.csv"
BODY_SCORE_OUTPUT="${OUTPUT_DIR}/commit_function_npr_body_scores.csv"
WINDOW_SCORE_OUTPUT="${OUTPUT_DIR}/commit_function_npr_window_scores.csv"
FAILURE_OUTPUT="${OUTPUT_DIR}/commit_function_npr_failures.csv"
CHECKPOINT_OUTPUT="${OUTPUT_DIR}/commit_function_npr_checkpoint_index.csv"
RUNTIME_OUTPUT="${OUTPUT_DIR}/commit_function_npr_runtime_metrics.csv"
ESTIMATE_OUTPUT="${OUTPUT_DIR}/commit_function_npr_full_run_estimates.csv"
CHECK_OUTPUT="${QC_DIR}/commit_function_npr_checks.csv"
SUMMARY_OUTPUT="${QC_DIR}/commit_function_npr_summary.json"
METADATA_OUTPUT="${QC_DIR}/commit_function_npr_metadata.json"
REPRO_OUTPUT="${QC_DIR}/commit_function_npr_reproducibility_checks.csv"
RUN_HISTORY_OUTPUT="${QC_DIR}/commit_function_npr_run_history.jsonl"

require_file() {
    local path="$1"
    local label="$2"
    if [[ ! -f "${path}" ]]; then
        echo "ERROR: Missing ${label}: ${path}" >&2
        exit 2
    fi
}

sha256_file() {
    local path="$1"
    sha256sum "${path}" | awk '{print $1}'
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

require_file "${PY_SCRIPT}" "run-1c Python script"
require_file "${INPUT_UNIQUE_BODIES}" "run-1a unique-body manifest"
require_file "${INPUT_EVENTS}" "run-1a event manifest"
require_file "${INPUT_PANEL}" "matched repository-month panel"
require_file "${INPUT_SUPPORT}" "run-1b eligibility support"
require_file "${INPUT_SPECIFICATION}" "run-1b frozen specification"

read -r PYTHON_MAJOR PYTHON_MINOR PYTHON_MICRO < <(
    "${PYTHON_BIN}" -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)'
)
PYTHON_VERSION="${PYTHON_MAJOR}.${PYTHON_MINOR}.${PYTHON_MICRO}"
if (( PYTHON_MAJOR < 3 || (PYTHON_MAJOR == 3 && PYTHON_MINOR < 10) )); then
    echo "ERROR: Python 3.10 or newer is required; found ${PYTHON_VERSION}." >&2
    exit 2
fi

PYTHON_RESOLVED="$("${PYTHON_BIN}" -c 'import sys; print(sys.executable)')"

mkdir -p "${LOG_DIR}"
START_EPOCH="$(date +%s)"
START_TEXT="$(date)"

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
    echo "run-1c execution summary"
    echo "Started:               ${START_TEXT}"
    echo "Completed:             $(date)"
    printf 'Elapsed:               %02d:%02d:%02d\n' "${hours}" "${minutes}" "${seconds}"
    echo "Exit code:             ${exit_code}"
    echo "Python path:           ${PYTHON_RESOLVED}"
    echo "Python version:        ${PYTHON_VERSION}"
    echo "Script path:           ${PY_SCRIPT}"
    echo "Input unique bodies:   ${INPUT_UNIQUE_BODIES}"
    echo "Input events:          ${INPUT_EVENTS}"
    echo "Input panel:           ${INPUT_PANEL}"
    echo "Input support:         ${INPUT_SUPPORT}"
    echo "Input specification:   ${INPUT_SPECIFICATION}"
    echo "Output directory:      ${OUTPUT_DIR}"
    echo "Cache directory:       ${CACHE_DIR}"
    echo "QC directory:          ${QC_DIR}"
    echo "Log file:              ${LOG_FILE}"
    echo "============================================================================"
    exit "${exit_code}"
}

trap finish EXIT
exec > >(tee -a "${LOG_FILE}") 2>&1

PY_SCRIPT_SHA="$(sha256_file "${PY_SCRIPT}")"
INPUT_UNIQUE_BODIES_SHA="$(sha256_file "${INPUT_UNIQUE_BODIES}")"
INPUT_EVENTS_SHA="$(sha256_file "${INPUT_EVENTS}")"
INPUT_PANEL_SHA="$(sha256_file "${INPUT_PANEL}")"
INPUT_SUPPORT_SHA="$(sha256_file "${INPUT_SUPPORT}")"
INPUT_SPECIFICATION_SHA="$(sha256_file "${INPUT_SPECIFICATION}")"

DEPENDENCY_INFO="$("${PYTHON_BIN}" - <<'PY'
import json

modules = {}
for name in ("numpy", "pandas", "scipy", "torch", "transformers"):
    try:
        module = __import__(name)
        modules[name] = getattr(module, "__version__", "unknown")
    except Exception as error:
        modules[name] = f"ERROR:{type(error).__name__}:{error}"

try:
    import torch
    cuda_available = bool(torch.cuda.is_available())
    gpu_name = torch.cuda.get_device_name(0) if cuda_available else "<none>"
    gpu_memory = int(torch.cuda.get_device_properties(0).total_memory) if cuda_available else 0
except Exception:
    cuda_available = False
    gpu_name = "<unavailable>"
    gpu_memory = 0

print(json.dumps({
    "modules": modules,
    "cuda_available": cuda_available,
    "gpu_name": gpu_name,
    "gpu_total_memory_bytes": gpu_memory,
}))
PY
)"

read -r CUDA_AVAILABLE GPU_NAME GPU_MEMORY_BYTES TORCH_VERSION TRANSFORMERS_VERSION SCIPY_VERSION NUMPY_VERSION PANDAS_VERSION < <(
    "${PYTHON_BIN}" - "${DEPENDENCY_INFO}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
modules = payload["modules"]
print(
    int(payload["cuda_available"]),
    str(payload["gpu_name"]).replace(" ", "_"),
    payload["gpu_total_memory_bytes"],
    modules.get("torch", "missing"),
    modules.get("transformers", "missing"),
    modules.get("scipy", "missing"),
    modules.get("numpy", "missing"),
    modules.get("pandas", "missing"),
)
PY
)
GPU_NAME_DISPLAY="${GPU_NAME//_/ }"

for value in "${TORCH_VERSION}" "${TRANSFORMERS_VERSION}" "${SCIPY_VERSION}" "${NUMPY_VERSION}" "${PANDAS_VERSION}"; do
    if [[ "${value}" == ERROR:* ]] || [[ "${value}" == "missing" ]]; then
        echo "ERROR: Required Python dependency is unavailable: ${value}" >&2
        echo "Use the detectcodegpt Conda environment for run-1c." >&2
        exit 2
    fi
done

if [[ "${PREPARE_ONLY}" != "1" ]] && [[ "${CUDA_AVAILABLE}" != "1" ]] && [[ "${ALLOW_CPU}" != "1" ]]; then
    echo "ERROR: CUDA is not available in ${PYTHON_RESOLVED}." >&2
    echo "Activate the detectcodegpt environment and expose a GPU, or set PREPARE_ONLY=1." >&2
    exit 2
fi

cat <<INFO
============================================================================
run-1c: deterministic dual-profile commit-function NPR pilot
Started:                         ${START_TEXT}
Workspace:                       ${PROJECT_ROOT}
Active conda env:                ${CONDA_DEFAULT_ENV:-<none>}
Python path:                     ${PYTHON_RESOLVED}
Python version:                  ${PYTHON_VERSION}
Python script:                   ${PY_SCRIPT}
Python script SHA:               ${PY_SCRIPT_SHA}
PyTorch version:                 ${TORCH_VERSION}
Transformers version:            ${TRANSFORMERS_VERSION}
SciPy version:                   ${SCIPY_VERSION}
NumPy version:                   ${NUMPY_VERSION}
Pandas version:                  ${PANDAS_VERSION}
CUDA_VISIBLE_DEVICES:            ${CUDA_VISIBLE_DEVICES}
CUDA available:                  ${CUDA_AVAILABLE}
GPU name:                        ${GPU_NAME_DISPLAY}
GPU total memory bytes:          ${GPU_MEMORY_BYTES}
Model cache:                     ${MODEL_CACHE_DIR}
Input unique bodies:             ${INPUT_UNIQUE_BODIES}
Input unique bodies SHA:         ${INPUT_UNIQUE_BODIES_SHA}
Input events:                    ${INPUT_EVENTS}
Input events SHA:                ${INPUT_EVENTS_SHA}
Input panel:                     ${INPUT_PANEL}
Input panel SHA:                 ${INPUT_PANEL_SHA}
Input run-1b support:            ${INPUT_SUPPORT}
Input run-1b support SHA:        ${INPUT_SUPPORT_SHA}
Input specification:            ${INPUT_SPECIFICATION}
Input specification SHA:        ${INPUT_SPECIFICATION_SHA}
Body artifact base:              ${BODY_ARTIFACT_BASE}
Calibration profile size:        ${CALIBRATION_PROFILE_SIZE}
Long-body profile size:          ${LONG_PROFILE_SIZE}
Calibration bands:               ${CALIBRATION_BANDS}
Long-body window strata:         ${LONG_WINDOW_STRATA}
Repro checks per profile:        ${REPRODUCIBILITY_CHECK_PER_PROFILE}
Output directory:                ${OUTPUT_DIR}
Cache directory:                 ${CACHE_DIR}
QC directory:                    ${QC_DIR}
Log file:                        ${LOG_FILE}
Overwrite output:                ${OVERWRITE_OUTPUT}
Run self-test:                   ${RUN_SELF_TEST}
Run resume check:                ${RUN_RESUME_CHECK}
Prepare only:                    ${PREPARE_ONLY}
============================================================================
INFO

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"

if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test
fi

COMMAND=(
    "${PYTHON_BIN}" "${PY_SCRIPT}"
    --input-unique-bodies "${INPUT_UNIQUE_BODIES}"
    --input-events "${INPUT_EVENTS}"
    --input-panel "${INPUT_PANEL}"
    --input-support "${INPUT_SUPPORT}"
    --input-specification "${INPUT_SPECIFICATION}"
    --body-artifact-base "${BODY_ARTIFACT_BASE}"
    --output-dir "${OUTPUT_DIR}"
    --qc-dir "${QC_DIR}"
    --cache-dir "${CACHE_DIR}"
    --model-cache-dir "${MODEL_CACHE_DIR}"
    --calibration-profile-size "${CALIBRATION_PROFILE_SIZE}"
    --long-profile-size "${LONG_PROFILE_SIZE}"
    --calibration-bands "${CALIBRATION_BANDS}"
    --long-window-strata "${LONG_WINDOW_STRATA}"
    --reproducibility-check-per-profile "${REPRODUCIBILITY_CHECK_PER_PROFILE}"
    --progress-every-bodies "${PROGRESS_EVERY_BODIES}"
)

if [[ "${OVERWRITE_OUTPUT}" == "1" ]]; then
    COMMAND+=(--overwrite-output)
fi
if [[ "${PREPARE_ONLY}" == "1" ]]; then
    COMMAND+=(--prepare-only)
fi

"${COMMAND[@]}"

for expected_file in \
    "${MANIFEST_OUTPUT}" \
    "${PROFILE_SUPPORT_OUTPUT}" \
    "${BODY_SCORE_OUTPUT}" \
    "${WINDOW_SCORE_OUTPUT}" \
    "${FAILURE_OUTPUT}" \
    "${CHECKPOINT_OUTPUT}" \
    "${RUNTIME_OUTPUT}" \
    "${ESTIMATE_OUTPUT}" \
    "${CHECK_OUTPUT}" \
    "${SUMMARY_OUTPUT}" \
    "${METADATA_OUTPUT}" \
    "${REPRO_OUTPUT}" \
    "${RUN_HISTORY_OUTPUT}"; do
    if [[ ! -f "${expected_file}" ]]; then
        echo "ERROR: Missing expected output: ${expected_file}" >&2
        exit 3
    fi
done

read -r STATUS FAILED_CHECKS SELECTED SUCCESSFUL FAILED EXPECTED_WINDOWS SCORED_WINDOWS PARTIAL_BODIES INVALID_WINDOWS INVALID_TOKENS SCORED_THIS_RUN REUSED_THIS_RUN MODEL_LOADED < <(
    "${PYTHON_BIN}" - "${SUMMARY_OUTPUT}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as stream:
    summary = json.load(stream)

print(
    summary["status"],
    summary["failed_checks"],
    summary["selected_unique_bodies"],
    summary["successful_unique_bodies"],
    summary["failed_unique_bodies"],
    summary["expected_windows"],
    summary["scored_windows"],
    summary["partial_body_score_count"],
    summary["invalid_npr_window_count"],
    summary["invalid_npr_token_count"],
    summary["bodies_scored_this_run"],
    summary["bodies_reused_this_run"],
    int(summary["model_loaded_this_run"]),
)
PY
)

EXPECTED_SELECTED=$((CALIBRATION_PROFILE_SIZE + LONG_PROFILE_SIZE))
EXPECTED_STATUS="PASS"
if [[ "${PREPARE_ONLY}" == "1" ]]; then
    EXPECTED_STATUS="PREPARED_ONLY"
fi

if [[ "${STATUS}" != "${EXPECTED_STATUS}" ]] || [[ "${FAILED_CHECKS}" != "0" ]]; then
    echo "ERROR: run-1c QC failed: status=${STATUS}, failed_checks=${FAILED_CHECKS}" >&2
    exit 4
fi
if [[ "${SELECTED}" != "${EXPECTED_SELECTED}" ]]; then
    echo "ERROR: Selected body count mismatch: ${SELECTED} != ${EXPECTED_SELECTED}" >&2
    exit 4
fi
if [[ "${PREPARE_ONLY}" != "1" ]] && { [[ "${SUCCESSFUL}" != "${EXPECTED_SELECTED}" ]] || [[ "${FAILED}" != "0" ]]; }; then
    echo "ERROR: Pilot scoring was incomplete: successful=${SUCCESSFUL}, failed=${FAILED}" >&2
    exit 4
fi

FIRST_RUN_SCORED="${SCORED_THIS_RUN}"
FIRST_RUN_REUSED="${REUSED_THIS_RUN}"
FIRST_RUN_MODEL_LOADED="${MODEL_LOADED}"

if [[ "${RUN_RESUME_CHECK}" == "1" ]] && [[ "${PREPARE_ONLY}" != "1" ]]; then
    RESUME_COMMAND=(
        "${PYTHON_BIN}" "${PY_SCRIPT}"
        --input-unique-bodies "${INPUT_UNIQUE_BODIES}"
        --input-events "${INPUT_EVENTS}"
        --input-panel "${INPUT_PANEL}"
        --input-support "${INPUT_SUPPORT}"
        --input-specification "${INPUT_SPECIFICATION}"
        --body-artifact-base "${BODY_ARTIFACT_BASE}"
        --output-dir "${OUTPUT_DIR}"
        --qc-dir "${QC_DIR}"
        --cache-dir "${CACHE_DIR}"
        --model-cache-dir "${MODEL_CACHE_DIR}"
        --calibration-profile-size "${CALIBRATION_PROFILE_SIZE}"
        --long-profile-size "${LONG_PROFILE_SIZE}"
        --calibration-bands "${CALIBRATION_BANDS}"
        --long-window-strata "${LONG_WINDOW_STRATA}"
        --reproducibility-check-per-profile "${REPRODUCIBILITY_CHECK_PER_PROFILE}"
        --progress-every-bodies "${PROGRESS_EVERY_BODIES}"
        --require-all-completed
    )
    "${RESUME_COMMAND[@]}"

    read -r RESUME_STATUS RESUME_FAILED RESUME_SCORED RESUME_REUSED RESUME_MODEL_LOADED RESUME_PASSED < <(
        "${PYTHON_BIN}" - "${SUMMARY_OUTPUT}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as stream:
    summary = json.load(stream)

print(
    summary["status"],
    summary["failed_checks"],
    summary["bodies_scored_this_run"],
    summary["bodies_reused_this_run"],
    int(summary["model_loaded_this_run"]),
    int(summary["resume_validation_passed"]),
)
PY
    )

    if [[ "${RESUME_STATUS}" != "PASS" ]] || [[ "${RESUME_FAILED}" != "0" ]] || \
       [[ "${RESUME_SCORED}" != "0" ]] || [[ "${RESUME_REUSED}" != "${EXPECTED_SELECTED}" ]] || \
       [[ "${RESUME_MODEL_LOADED}" != "0" ]] || [[ "${RESUME_PASSED}" != "1" ]]; then
        echo "ERROR: Resume validation failed." >&2
        echo "status=${RESUME_STATUS} failed=${RESUME_FAILED} scored=${RESUME_SCORED} reused=${RESUME_REUSED} model_loaded=${RESUME_MODEL_LOADED} passed=${RESUME_PASSED}" >&2
        exit 5
    fi
fi

BODY_SCORE_ROWS=$(( $(wc -l < "${BODY_SCORE_OUTPUT}") - 1 ))
WINDOW_SCORE_ROWS=$(( $(wc -l < "${WINDOW_SCORE_OUTPUT}") - 1 ))
FAILURE_ROWS=$(( $(wc -l < "${FAILURE_OUTPUT}") - 1 ))
CHECKPOINT_ROWS=$(( $(wc -l < "${CHECKPOINT_OUTPUT}") - 1 ))

cat <<INFO

============================================================================
run-1c output verification
Status after validation:         ${STATUS}
Selected unique bodies:          ${SELECTED}
Successful unique bodies:        ${SUCCESSFUL}
Failed unique bodies:            ${FAILED}
Expected windows:                ${EXPECTED_WINDOWS}
Scored windows:                  ${SCORED_WINDOWS}
Partial-body scores:             ${PARTIAL_BODIES}
Invalid NPR windows:             ${INVALID_WINDOWS}
Invalid NPR tokens:              ${INVALID_TOKENS}
First invocation scored bodies:  ${FIRST_RUN_SCORED}
First invocation reused bodies:  ${FIRST_RUN_REUSED}
First invocation model loaded:   ${FIRST_RUN_MODEL_LOADED}
Body score rows:                 ${BODY_SCORE_ROWS}
Window score rows:               ${WINDOW_SCORE_ROWS}
Failure rows:                    ${FAILURE_ROWS}
Checkpoint rows:                 ${CHECKPOINT_ROWS}
Failed QC checks:                ${FAILED_CHECKS}
Pilot manifest:                  ${MANIFEST_OUTPUT}
Body scores:                     ${BODY_SCORE_OUTPUT}
Window scores:                   ${WINDOW_SCORE_OUTPUT}
Runtime metrics:                 ${RUNTIME_OUTPUT}
Full-run estimates:              ${ESTIMATE_OUTPUT}
Checks:                          ${CHECK_OUTPUT}
Summary:                         ${SUMMARY_OUTPUT}
Metadata:                        ${METADATA_OUTPUT}
Log file:                        ${LOG_FILE}
============================================================================
INFO
