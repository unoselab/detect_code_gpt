#!/usr/bin/env bash
# Run deterministic three-GPU StarCoder2 NPR scoring for the frozen gt200
# eligibility specification.
#
# Versioned delivery files:
#   code-detection/score_commit_function_npr_full-gt200-v2.py
#   proc_sh/run-1d-score-commit-func-npr-full-gt200-v2.sh
#
# Canonical R158 paths after validation:
#   code-detection/score_commit_function_npr_full-gt200.py
#   proc_sh/run-1d-score-commit-func-npr-full-gt200.sh
#
# This wrapper is standalone. It does not call the original run-1d wrapper.
#
# Main inputs:
#   output/commit_function/run-1a/strict/
#     commit_function_detectcodegpt_unique_bodies.csv
#     commit_function_detectcodegpt_input_events.csv
#     function_bodies/
#   output/commit_function/run-1b/gt200/
#     commit_function_body_eligibility_support.csv
#     commit_function_detectcodegpt_scoring_spec.json
#   output/commit_function/run-1c0b/mixedcode-overlap-threshold-v1/
#     mixedcode_overlap_threshold_specification.json
#   ../ai_code_complexity_study_python/ai-code-complexity-study/
#     repo_python/run-py-4a/strict/
#       panel_event_monthly_agc_changed_block_py.csv
#
# Main outputs:
#   output/commit_function/run-1d/gt200-overlap/
#     shards/shard-000-of-003/
#     shards/shard-001-of-003/
#     shards/shard-002-of-003/
#       cache/body_results/
#       cache/failures/
#       qc/
#       commit_function_npr_*.csv
#     merged/
#       commit_function_npr_full_manifest.csv
#       commit_function_npr_body_scores.csv
#       commit_function_npr_window_scores.csv
#       commit_function_npr_checkpoint_index.csv
#       commit_function_npr_runtime_metrics.csv
#       commit_function_npr_full_progress_estimates.csv
#       qc/commit_function_npr_checks.csv
#       qc/commit_function_npr_summary.json
#       qc/commit_function_npr_metadata.json
#
# Default R158 GPU mapping:
#   shard 0 -> physical GPU 0
#   shard 1 -> physical GPU 1
#   shard 2 -> physical GPU 2
#
# Recommended execution sequence:
#   1. Prepare-only:
#      PREPARE_ONLY=1 OVERWRITE_OUTPUT=1 RUN_SELF_TEST=1 \
#        bash proc_sh/run-1d-score-commit-func-npr-full-gt200.sh
#   2. Three-body GPU smoke test:
#      MAX_BODIES_PER_SHARD=1 OVERWRITE_OUTPUT=1 RUN_SELF_TEST=0 \
#        bash proc_sh/run-1d-score-commit-func-npr-full-gt200.sh
#   3. Full resumable scoring:
#      RUN_SELF_TEST=0 RUN_RESUME_CHECK=1 \
#        bash proc_sh/run-1d-score-commit-func-npr-full-gt200.sh
#
# Important:
#   OVERWRITE_OUTPUT=1 removes each shard directory before that invocation.
#   Do not use it when resuming a partially completed full run.
# 
# Usage:
# PREPARE_ONLY=1 OVERWRITE_OUTPUT=1 RUN_SELF_TEST=1 RUN_RESUME_CHECK=0 bash proc_sh/run-1d-score-commit-func-npr-full-gt200.sh
# MAX_BODIES_PER_SHARD=1 OVERWRITE_OUTPUT=1 RUN_SELF_TEST=0 RUN_RESUME_CHECK=0 bash proc_sh/run-1d-score-commit-func-npr-full-gt200.sh
# 
# 
# 
# 

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/score_commit_function_npr_full-gt200.py}"

RUN1A_DIR="${RUN1A_DIR:-output/commit_function/run-1a/strict}"
RUN1B_DIR="${RUN1B_DIR:-output/commit_function/run-1b/gt200}"
INPUT_UNIQUE_BODIES="${INPUT_UNIQUE_BODIES:-${RUN1A_DIR}/commit_function_detectcodegpt_unique_bodies.csv}"
INPUT_EVENTS="${INPUT_EVENTS:-${RUN1A_DIR}/commit_function_detectcodegpt_input_events.csv}"
INPUT_PANEL="${INPUT_PANEL:-../ai_code_complexity_study_python/ai-code-complexity-study/repo_python/run-py-4a/strict/panel_event_monthly_agc_changed_block_py.csv}"
INPUT_SUPPORT="${INPUT_SUPPORT:-${RUN1B_DIR}/commit_function_body_eligibility_support.csv}"
INPUT_ELIGIBILITY_SPECIFICATION="${INPUT_ELIGIBILITY_SPECIFICATION:-${RUN1B_DIR}/commit_function_detectcodegpt_scoring_spec.json}"
INPUT_THRESHOLD_SPECIFICATION="${INPUT_THRESHOLD_SPECIFICATION:-output/commit_function/run-1c0b/mixedcode-overlap-threshold-v1/mixedcode_overlap_threshold_specification.json}"
BODY_ARTIFACT_BASE="${BODY_ARTIFACT_BASE:-${RUN1A_DIR}}"

SPEC_NAME="${SPEC_NAME:-gt200}"
PROFILE_NAME="${PROFILE_NAME:-gt200_full}"
NUM_SHARDS="${NUM_SHARDS:-3}"
GPU_IDS="${GPU_IDS:-0,1,2}"
EXPECTED_GLOBAL_BODIES="${EXPECTED_GLOBAL_BODIES:-154150}"
EXPECTED_GLOBAL_WINDOWS="${EXPECTED_GLOBAL_WINDOWS:-1025732}"
EXPECTED_MINIMUM_TOKENS="${EXPECTED_MINIMUM_TOKENS:-201}"
EXPECTED_AGC_THRESHOLD="${EXPECTED_AGC_THRESHOLD:-1.571637}"
EXPECTED_ALGORITHM_VERSION="${EXPECTED_ALGORITHM_VERSION:-overlap_final_full_window_valid_frontier_weighting-v1}"
EXPECTED_FUNCTION_AGGREGATION="${EXPECTED_FUNCTION_AGGREGATION:-valid_frontier_weighted_mean}"
EXPECTED_DECISION_RULE="${EXPECTED_DECISION_RULE:-function_npr > agc_threshold}"
EXPECTED_WINDOW_POLICY="${EXPECTED_WINDOW_POLICY:-full_size_final_window_shifted_backward_with_overlap}"
EXPECTED_PARTIAL_BODY_POLICY="${EXPECTED_PARTIAL_BODY_POLICY:-any_valid_window_partial_success_full_windows-v2}"

OUTPUT_ROOT="${OUTPUT_ROOT:-output/commit_function/run-1d/gt200-overlap}"
SHARD_ROOT="${SHARD_ROOT:-${OUTPUT_ROOT}/shards}"
MERGED_OUTPUT_DIR="${MERGED_OUTPUT_DIR:-${OUTPUT_ROOT}/merged}"
MERGED_QC_DIR="${MERGED_QC_DIR:-${MERGED_OUTPUT_DIR}/qc}"
LOG_DIR="${LOG_DIR:-logs/run-1d/gt200}"
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-${HOME}/.cache/huggingface/hub}"

PROGRESS_EVERY_BODIES="${PROGRESS_EVERY_BODIES:-100}"
REPRODUCIBILITY_CHECK_PER_PROFILE="${REPRODUCIBILITY_CHECK_PER_PROFILE:-1}"
PREPARE_ONLY="${PREPARE_ONLY:-0}"
OVERWRITE_OUTPUT="${OVERWRITE_OUTPUT:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
RUN_RESUME_CHECK="${RUN_RESUME_CHECK:-1}"
MAX_BODIES_PER_SHARD="${MAX_BODIES_PER_SHARD:-}"

export TOKENIZERS_PARALLELISM="false"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"

TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
MAIN_LOG="${MAIN_LOG:-${LOG_DIR}/run-1d-score-commit-func-npr-full-gt200-${TIMESTAMP}.log}"

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

sha256_file() {
    local path="$1"
    sha256sum "${path}" | awk '{print $1}'
}

if [[ "${PYTHON_BIN}" == */* ]]; then
    [[ -x "${PYTHON_BIN}" ]] || {
        echo "ERROR: Python executable is unavailable: ${PYTHON_BIN}" >&2
        exit 2
    }
elif ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "ERROR: Python executable is unavailable: ${PYTHON_BIN}" >&2
    exit 2
fi

require_file "${PY_SCRIPT}" "sharded run-1d Python scorer"
require_file "${INPUT_UNIQUE_BODIES}" "run-1a unique-body manifest"
require_file "${INPUT_EVENTS}" "run-1a event manifest"
require_file "${INPUT_PANEL}" "matched repository-month panel"
require_file "${INPUT_SUPPORT}" "run-1b gt200 eligibility support"
require_file "${INPUT_ELIGIBILITY_SPECIFICATION}" "run-1b gt200 frozen specification"
require_file "${INPUT_THRESHOLD_SPECIFICATION}" "frozen overlap threshold specification"
require_dir "${BODY_ARTIFACT_BASE}/function_bodies" "run-1a function-body artifact directory"

if ! [[ "${NUM_SHARDS}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: NUM_SHARDS must be a positive integer." >&2
    exit 2
fi
if [[ -n "${MAX_BODIES_PER_SHARD}" ]] && ! [[ "${MAX_BODIES_PER_SHARD}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: MAX_BODIES_PER_SHARD must be empty or a positive integer." >&2
    exit 2
fi

IFS=',' read -r -a GPU_ARRAY <<< "${GPU_IDS}"
if [[ "${#GPU_ARRAY[@]}" -ne "${NUM_SHARDS}" ]]; then
    echo "ERROR: GPU_IDS count (${#GPU_ARRAY[@]}) must match NUM_SHARDS (${NUM_SHARDS})." >&2
    exit 2
fi
for gpu_id in "${GPU_ARRAY[@]}"; do
    if ! [[ "${gpu_id}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: Invalid GPU index in GPU_IDS: ${gpu_id}" >&2
        exit 2
    fi
done
if [[ "$(printf '%s\n' "${GPU_ARRAY[@]}" | sort -u | wc -l)" -ne "${NUM_SHARDS}" ]]; then
    echo "ERROR: GPU_IDS must contain one unique physical GPU index per shard." >&2
    exit 2
fi

mkdir -p "${LOG_DIR}" "${SHARD_ROOT}"
START_EPOCH="$(date +%s)"
START_TEXT="$(date)"

finish() {
    local exit_code=$?
    local end_epoch elapsed
    end_epoch="$(date +%s)"
    elapsed=$((end_epoch - START_EPOCH))
    echo
    echo "============================================================================"
    echo "run-1d gt200 three-GPU execution summary"
    echo "Started:             ${START_TEXT}"
    echo "Completed:           $(date)"
    printf 'Elapsed:             %02d:%02d:%02d\n' \
        "$((elapsed / 3600))" "$(((elapsed % 3600) / 60))" "$((elapsed % 60))"
    echo "Exit code:           ${exit_code}"
    echo "Shard root:          ${SHARD_ROOT}"
    echo "Merged output:       ${MERGED_OUTPUT_DIR}"
    echo "Main log:            ${MAIN_LOG}"
    echo "============================================================================"
    exit "${exit_code}"
}
trap finish EXIT
exec > >(tee -a "${MAIN_LOG}") 2>&1

PYTHON_RESOLVED="$("${PYTHON_BIN}" -c 'import sys; print(sys.executable)')"
PYTHON_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(sys.version.split()[0])')"

cat <<INFO
============================================================================
run-1d gt200: deterministic three-GPU full NPR scoring
Started:                         ${START_TEXT}
Workspace:                       ${PROJECT_ROOT}
Active conda env:                ${CONDA_DEFAULT_ENV:-<none>}
Python path:                     ${PYTHON_RESOLVED}
Python version:                  ${PYTHON_VERSION}
Python script:                   ${PY_SCRIPT}
Python script SHA:               $(sha256_file "${PY_SCRIPT}")
Specification:                  ${SPEC_NAME}
Profile:                        ${PROFILE_NAME}
Number of shards:               ${NUM_SHARDS}
GPU IDs:                        ${GPU_IDS}
Expected global bodies:         ${EXPECTED_GLOBAL_BODIES}
Expected global windows:        ${EXPECTED_GLOBAL_WINDOWS}
Expected gt200 minimum:         ${EXPECTED_MINIMUM_TOKENS}
Expected AGC threshold:         ${EXPECTED_AGC_THRESHOLD}
Expected aggregation:           ${EXPECTED_FUNCTION_AGGREGATION}
Expected window policy:         ${EXPECTED_WINDOW_POLICY}
Prepare only:                   ${PREPARE_ONLY}
Maximum bodies per shard:       ${MAX_BODIES_PER_SHARD:-<none>}
Overwrite shard outputs:        ${OVERWRITE_OUTPUT}
Run self-test:                  ${RUN_SELF_TEST}
Run resume check:               ${RUN_RESUME_CHECK}
Input unique bodies:            ${INPUT_UNIQUE_BODIES}
Input events:                   ${INPUT_EVENTS}
Input panel:                    ${INPUT_PANEL}
Input support:                  ${INPUT_SUPPORT}
Eligibility specification:     ${INPUT_ELIGIBILITY_SPECIFICATION}
Threshold specification:       ${INPUT_THRESHOLD_SPECIFICATION}
Body artifact base:             ${BODY_ARTIFACT_BASE}
Shard root:                     ${SHARD_ROOT}
Merged output:                  ${MERGED_OUTPUT_DIR}
Model cache:                    ${MODEL_CACHE_DIR}
============================================================================
INFO

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"
if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test
fi

if [[ "${PREPARE_ONLY}" != "1" ]]; then
    "${PYTHON_BIN}" - "${GPU_IDS}" <<'PY'
import sys
import torch

requested = [int(value) for value in sys.argv[1].split(",")]
if not torch.cuda.is_available():
    raise SystemExit("ERROR: CUDA is not available in the active Python environment.")
if torch.cuda.device_count() < len(requested):
    raise SystemExit(
        f"ERROR: Python sees only {torch.cuda.device_count()} GPUs, "
        f"but {len(requested)} shard workers were requested."
    )
invalid = [index for index in requested if index < 0 or index >= torch.cuda.device_count()]
if invalid:
    raise SystemExit(
        f"ERROR: GPU_IDS contains unavailable physical indices {invalid}; "
        f"valid indices are 0..{torch.cuda.device_count() - 1}."
    )
print(f"CUDA preflight: PASS ({torch.cuda.device_count()} visible GPUs)")
PY
fi

launch_shards() {
    local phase="$1"
    local overwrite="$2"
    local -a pids=()
    local -a labels=()

    for ((shard_index = 0; shard_index < NUM_SHARDS; shard_index++)); do
        local gpu_id="${GPU_ARRAY[shard_index]}"
        local shard_name
        local shard_dir
        local shard_log
        shard_name="$(printf 'shard-%03d-of-%03d' "${shard_index}" "${NUM_SHARDS}")"
        shard_dir="${SHARD_ROOT}/${shard_name}"
        shard_log="${LOG_DIR}/run-1d-gt200-${shard_name}-${phase}-${TIMESTAMP}.log"

        local -a command=(
            "${PYTHON_BIN}" "${PY_SCRIPT}"
            --input-unique-bodies "${INPUT_UNIQUE_BODIES}"
            --input-events "${INPUT_EVENTS}"
            --input-panel "${INPUT_PANEL}"
            --input-support "${INPUT_SUPPORT}"
            --input-eligibility-specification "${INPUT_ELIGIBILITY_SPECIFICATION}"
            --input-threshold-specification "${INPUT_THRESHOLD_SPECIFICATION}"
            --body-artifact-base "${BODY_ARTIFACT_BASE}"
            --spec-name "${SPEC_NAME}"
            --profile-name "${PROFILE_NAME}"
            --num-shards "${NUM_SHARDS}"
            --shard-index "${shard_index}"
            --output-dir "${shard_dir}"
            --qc-dir "${shard_dir}/qc"
            --cache-dir "${shard_dir}/cache"
            --model-cache-dir "${MODEL_CACHE_DIR}"
            --detector-output-name "run1d_gt200_${shard_name}_v2"
            --progress-every-bodies "${PROGRESS_EVERY_BODIES}"
            --reproducibility-check-per-profile "${REPRODUCIBILITY_CHECK_PER_PROFILE}"
        )
        if [[ "${PREPARE_ONLY}" == "1" ]]; then
            command+=(--prepare-only)
        fi
        if [[ "${overwrite}" == "1" ]]; then
            command+=(--overwrite-output)
        fi
        if [[ -n "${MAX_BODIES_PER_SHARD}" ]]; then
            command+=(--max-bodies-per-shard "${MAX_BODIES_PER_SHARD}")
        fi
        if [[ "${phase}" == "resume" ]]; then
            command+=(--require-all-completed)
        fi

        echo "Launching ${shard_name} on physical GPU ${gpu_id}; log=${shard_log}"
        (
            export CUDA_VISIBLE_DEVICES="${gpu_id}"
            "${command[@]}"
        ) > >(tee -a "${shard_log}") 2>&1 &
        pids+=("$!")
        labels+=("${shard_name}")
    done

    local failures=0
    for index in "${!pids[@]}"; do
        if wait "${pids[index]}"; then
            echo "Completed: ${labels[index]}"
        else
            echo "ERROR: ${labels[index]} failed." >&2
            failures=$((failures + 1))
        fi
    done
    if [[ "${failures}" -ne 0 ]]; then
        echo "ERROR: ${failures} shard process(es) failed during ${phase}." >&2
        return 6
    fi
}

merge_shards() {
    local -a command=(
        "${PYTHON_BIN}" "${PY_SCRIPT}"
        --merge-shards
        --num-shards "${NUM_SHARDS}"
        --shard-root "${SHARD_ROOT}"
        --input-support "${INPUT_SUPPORT}"
        --input-eligibility-specification "${INPUT_ELIGIBILITY_SPECIFICATION}"
        --input-threshold-specification "${INPUT_THRESHOLD_SPECIFICATION}"
        --spec-name "${SPEC_NAME}"
        --profile-name "${PROFILE_NAME}"
        --output-dir "${MERGED_OUTPUT_DIR}"
        --qc-dir "${MERGED_QC_DIR}"
        --overwrite-output
    )
    if [[ -n "${MAX_BODIES_PER_SHARD}" ]]; then
        command+=(--allow-partial-shards)
    fi
    "${command[@]}"
}

launch_shards "primary" "${OVERWRITE_OUTPUT}"
merge_shards

if [[ "${RUN_RESUME_CHECK}" == "1" ]] \
    && [[ "${PREPARE_ONLY}" != "1" ]] \
    && [[ -z "${MAX_BODIES_PER_SHARD}" ]]; then
    launch_shards "resume" "0"
    merge_shards
fi

SUMMARY_OUTPUT="${MERGED_QC_DIR}/commit_function_npr_summary.json"
require_file "${SUMMARY_OUTPUT}" "merged summary"

"${PYTHON_BIN}" - \
    "${SUMMARY_OUTPUT}" \
    "${PREPARE_ONLY}" \
    "${MAX_BODIES_PER_SHARD}" \
    "${EXPECTED_GLOBAL_BODIES}" \
    "${EXPECTED_GLOBAL_WINDOWS}" \
    "${RUN_RESUME_CHECK}" \
    "${EXPECTED_MINIMUM_TOKENS}" \
    "${EXPECTED_AGC_THRESHOLD}" \
    "${EXPECTED_ALGORITHM_VERSION}" \
    "${EXPECTED_FUNCTION_AGGREGATION}" \
    "${EXPECTED_DECISION_RULE}" \
    "${EXPECTED_WINDOW_POLICY}" \
    "${EXPECTED_PARTIAL_BODY_POLICY}" <<'PY'
import json
import math
import sys

(
    summary_path,
    prepare_only,
    body_limit,
    expected_bodies,
    expected_windows,
    resume_check,
    expected_minimum,
    expected_threshold,
    expected_algorithm,
    expected_aggregation,
    expected_decision_rule,
    expected_window_policy,
    expected_partial_body_policy,
) = sys.argv[1:]
with open(summary_path, "r", encoding="utf-8") as stream:
    summary = json.load(stream)

if body_limit:
    expected_status = "SMOKE_PASS"
elif prepare_only == "1":
    expected_status = "PREPARED_ONLY"
else:
    expected_status = "PASS"

errors = []
if summary["status"] != expected_status:
    errors.append(f"status={summary['status']} expected={expected_status}")
if int(summary["failed_checks"]) != 0:
    errors.append(f"failed_checks={summary['failed_checks']}")
if int(summary["duplicate_body_hashes"]) != 0:
    errors.append(f"duplicate_body_hashes={summary['duplicate_body_hashes']}")
if summary["selected_specification"] != "gt200":
    errors.append(
        f"selected_specification={summary['selected_specification']} expected=gt200"
    )
if summary["selected_specification_role"] != "primary_candidate":
    errors.append(
        "selected_specification_role="
        f"{summary['selected_specification_role']} expected=primary_candidate"
    )
if int(summary["minimum_literal_space_tokens"]) != int(expected_minimum):
    errors.append(
        f"minimum_literal_space_tokens={summary['minimum_literal_space_tokens']} "
        f"expected={expected_minimum}"
    )
if summary["maximum_literal_space_tokens"] is not None:
    errors.append(
        "maximum_literal_space_tokens="
        f"{summary['maximum_literal_space_tokens']} expected=None"
    )
if not math.isclose(
    float(summary["agc_threshold"]),
    float(expected_threshold),
    rel_tol=0.0,
    abs_tol=1e-12,
):
    errors.append(
        f"agc_threshold={summary['agc_threshold']} expected={expected_threshold}"
    )
for key, expected in (
    ("algorithm_version", expected_algorithm),
    ("function_aggregation", expected_aggregation),
    ("decision_rule", expected_decision_rule),
    ("window_policy", expected_window_policy),
    ("partial_body_policy", expected_partial_body_policy),
):
    if summary[key] != expected:
        errors.append(f"{key}={summary[key]} expected={expected}")

if not body_limit:
    if int(summary["selected_unique_bodies"]) != int(expected_bodies):
        errors.append(
            f"selected_unique_bodies={summary['selected_unique_bodies']} "
            f"expected={expected_bodies}"
        )
    if int(summary["expected_windows"]) != int(expected_windows):
        errors.append(
            f"expected_windows={summary['expected_windows']} expected={expected_windows}"
        )

if prepare_only != "1" and not body_limit:
    if int(summary["successful_unique_bodies"]) != int(expected_bodies):
        errors.append(
            f"successful_unique_bodies={summary['successful_unique_bodies']} "
            f"expected={expected_bodies}"
        )
    if int(summary["failed_unique_bodies"]) != 0:
        errors.append(f"failed_unique_bodies={summary['failed_unique_bodies']}")
    if resume_check == "1" and not bool(summary["resume_validation_passed"]):
        errors.append("resume_validation_passed is false")

if errors:
    raise SystemExit("ERROR: merged verification failed: " + "; ".join(errors))

print("=" * 76)
print("run-1d gt200 merged verification")
print(f"Status:                         {summary['status']}")
print(f"Shards:                         {summary['num_shards']}")
print(f"Eligibility:                    {summary['selected_specification']} >= {summary['minimum_literal_space_tokens']}")
print(f"AGC threshold:                  {summary['agc_threshold']}")
print(f"Aggregation:                    {summary['function_aggregation']}")
print(f"Selected unique bodies:         {summary['selected_unique_bodies']}")
print(f"Successful unique bodies:       {summary['successful_unique_bodies']}")
print(f"Failed unique bodies:           {summary['failed_unique_bodies']}")
print(f"Expected windows:               {summary['expected_windows']}")
print(f"Scored windows:                 {summary['scored_windows']}")
print(f"Duplicate body hashes:          {summary['duplicate_body_hashes']}")
print(f"Bodies scored this invocation:  {summary['bodies_scored_this_run']}")
print(f"Bodies reused this invocation:  {summary['bodies_reused_this_run']}")
print(f"Resume validation passed:       {int(summary['resume_validation_passed'])}")
print(f"Failed checks:                  {summary['failed_checks']}")
print("=" * 76)
PY

echo "run-1d gt200 three-GPU verification: PASS"
