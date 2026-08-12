#!/usr/bin/env bash
# Score A13's new C_FUN (class-method) workload on one R158 RTX A6000.
#
# This wrapper is standalone. It was created by first copying the frozen A11 v3
# scoring wrapper and then adapting its inputs/outputs from FUN/A10 to the A13
# new-C_FUN workload. It does not call the A11 or A13 shell wrappers.
#
# Versioned delivery files:
#   code-detection/score_snapshot_npr_cfun_shards-v1.py
#   proc_sh/run-x-a14-score-snapshot-npr-cfun-v1.sh
#
# Canonical server paths after deployment:
#   code-detection/score_snapshot_npr_cfun_shards.py
#   proc_sh/run-x-a14-score-snapshot-npr-cfun.sh
#
# Required inputs:
#   code-detection/score_snapshot_npr.py
#       Frozen A02 scorer. A14 verifies its SHA-256 and scoring fingerprint.
#   output/snapshot_npr/run-x-a09/plan/summary.json
#   output/snapshot_npr/run-x-a09/shards/shard-000-of-096.jsonl.gz ... 095
#   output/snapshot_npr/run-x-a09/shards/shard-000-of-096.summary.json ... 095
#       Frozen original windows plus the ordered 50 pregenerated perturbations.
#   output/snapshot_npr/run-x-a13/summary.json
#   output/snapshot_npr/run-x-a13/python_cfun_new_scoring_units.csv
#   output/snapshot_npr/run-x-a13/cfun_new_gpu_lpt_plan.csv
#       Frozen C_FUN-only SHA universe and 3-GPU deterministic LPT assignment.
#
# A13 accounting frozen before A14:
#   Total C_FUN memberships:      195,193 units / 567,557 windows
#   Reused from A11:              3 units / 3 windows
#   A14 new scoring workload:     195,190 units / 567,554 windows
#   A14 new perturbations:        28,377,700
#   GPU window loads:             189,150 / 189,188 / 189,216
#
# Per-worker outputs:
#   window_scores.sqlite3
#       Durable per-window checkpoint database. A rerun skips completed keys.
#   python_cfun_new_window_npr_scores.csv
#       Window-level rank/NPR values and provenance for A14-new C_FUN units.
#   python_cfun_new_unique_code_unit_npr_scores.csv
#       Finite C_FUN code-unit aggregates using frozen A02 aggregation logic.
#   python_cfun_new_npr_exclusions.csv
#       Prespecified deterministic measurement-domain exclusions.
#   python_cfun_new_npr_failures.csv
#       Unexpected scoring/aggregation failures; must remain empty for PASS.
#   assigned_shard_audit.csv, reference_scoring_checks.csv, checks.csv,
#   progress.json, summary.json, metadata.json
#
# Modes:
#   MODE=smoke
#       Uses a separate smoke output root. By default it scores one A14-new C_FUN
#       window from each of six assigned logical shards and runs one exact A02
#       regeneration reference comparison. Smoke does not contaminate production.
#   MODE=run
#       Scores the complete A13-assigned new C_FUN workload for this GPU. A09
#       perturbations are never regenerated. Resume uses OVERWRITE=0.
#   MODE=finalize
#       Reuses the existing A14 production SQLite checkpoint in results/gpu-X.
#       No model is loaded and no window is rescored; exports/QC are rebuilt.
#
# Recommended three-terminal smoke commands on R158:
#   MODE=smoke GPU_INDEX=0 CUDA_DEVICE=0 OVERWRITE=1 bash proc_sh/run-x-a14-score-snapshot-npr-cfun.sh
#   MODE=smoke GPU_INDEX=1 CUDA_DEVICE=1 OVERWRITE=1 bash proc_sh/run-x-a14-score-snapshot-npr-cfun.sh
#   MODE=smoke GPU_INDEX=2 CUDA_DEVICE=2 OVERWRITE=1 bash proc_sh/run-x-a14-score-snapshot-npr-cfun.sh
#
# After all three smoke runs PASS, start production in three terminals:
#   MODE=run GPU_INDEX=0 CUDA_DEVICE=0 SYSTEM_LABEL=r158-a6000-0 OVERWRITE=1 bash proc_sh/run-x-a14-score-snapshot-npr-cfun.sh
#   MODE=run GPU_INDEX=1 CUDA_DEVICE=1 SYSTEM_LABEL=r158-a6000-1 OVERWRITE=1 bash proc_sh/run-x-a14-score-snapshot-npr-cfun.sh
#   MODE=run GPU_INDEX=2 CUDA_DEVICE=2 SYSTEM_LABEL=r158-a6000-2 OVERWRITE=1 bash proc_sh/run-x-a14-score-snapshot-npr-cfun.sh
#
# Use OVERWRITE=1 only for the first clean production invocation. If interrupted,
# rerun the same GPU with OVERWRITE=0 to resume from its SQLite checkpoint.
#
# Optional environment variables:
#   PROJECT_ROOT, PYTHON_BIN, PY_SCRIPT, A02_SCRIPT, A09_ROOT, A13_ROOT,
#   OUTPUT_ROOT, LOG_DIR, MODEL_CACHE_DIR, MODE, GPU_INDEX, CUDA_DEVICE,
#   SYSTEM_LABEL, PROGRESS_EVERY_WINDOWS, REFERENCE_CHECK_WINDOWS,
#   RETRY_ERROR_WINDOWS, SMOKE_MAX_SHARDS, SMOKE_WINDOWS_PER_SHARD, OVERWRITE,
#   REQUIRE_ALL_VALID, ALLOW_NON_A6000, RUN_SELF_TEST, HF_HUB_OFFLINE,
#   TRANSFORMERS_OFFLINE, TIMESTAMP, LOG_FILE.
#
# Python/runtime policy:
#   - Python 3.11.x in the detectcodegpt environment.
#   - One process sees exactly one physical GPU through CUDA_VISIBLE_DEVICES.
#   - Production GPU is expected to be NVIDIA RTX A6000.
#   - Hugging Face offline mode is enabled by default to avoid model drift.
#   - No AGC/HWC classification is performed.
#   - A14 does not rescore the three C_FUN/FUN overlap SHAs frozen by A13.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

RUN_PREFIX="run-x-a14"
MODE="${MODE:-smoke}"
case "${MODE}" in
    smoke|run|finalize) ;;
    *) echo "ERROR: MODE must be smoke, run, or finalize; got ${MODE}" >&2; exit 2 ;;
esac

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/score_snapshot_npr_cfun_shards.py}"
A02_SCRIPT="${A02_SCRIPT:-code-detection/score_snapshot_npr.py}"
A09_ROOT="${A09_ROOT:-output/snapshot_npr/run-x-a09}"
A13_ROOT="${A13_ROOT:-output/snapshot_npr/run-x-a13}"
OUTPUT_ROOT="${OUTPUT_ROOT:-output/snapshot_npr/run-x-a14}"
LOG_DIR="${LOG_DIR:-logs/run-x-a14}"
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-${HOME}/.cache/huggingface/hub}"

GPU_INDEX="${GPU_INDEX:-0}"
CUDA_DEVICE="${CUDA_DEVICE:-${GPU_INDEX}}"
SYSTEM_LABEL="${SYSTEM_LABEL:-r158-a6000-${GPU_INDEX}}"
PROGRESS_EVERY_WINDOWS="${PROGRESS_EVERY_WINDOWS:-100}"
OVERWRITE="${OVERWRITE:-0}"
if [[ "${MODE}" == "finalize" ]]; then
    RETRY_ERROR_WINDOWS="${RETRY_ERROR_WINDOWS:-0}"
else
    RETRY_ERROR_WINDOWS="${RETRY_ERROR_WINDOWS:-1}"
fi
# A14 permits only prespecified deterministic exclusions; unexpected invalid rows
# remain hard failures in Python. Set REQUIRE_ALL_VALID=1 only for a stricter
# diagnostic run that also rejects expected exclusions.
REQUIRE_ALL_VALID="${REQUIRE_ALL_VALID:-0}"
ALLOW_NON_A6000="${ALLOW_NON_A6000:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"

SMOKE_MAX_SHARDS="${SMOKE_MAX_SHARDS:-6}"
SMOKE_WINDOWS_PER_SHARD="${SMOKE_WINDOWS_PER_SHARD:-1}"
if [[ "${MODE}" == "smoke" ]]; then
    REFERENCE_CHECK_WINDOWS="${REFERENCE_CHECK_WINDOWS:-1}"
    OUTPUT_DIR="${OUTPUT_ROOT}/smoke/gpu-${GPU_INDEX}"
else
    REFERENCE_CHECK_WINDOWS="${REFERENCE_CHECK_WINDOWS:-0}"
    OUTPUT_DIR="${OUTPUT_ROOT}/results/gpu-${GPU_INDEX}"
fi

if [[ "${MODE}" == "finalize" && "${OVERWRITE}" != "0" ]]; then
    echo "ERROR: MODE=finalize must use OVERWRITE=0 to preserve the existing SQLite checkpoint." >&2
    exit 2
fi

export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"
export TOKENIZERS_PARALLELISM="false"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"

TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/${RUN_PREFIX}-v1-${MODE}-${SYSTEM_LABEL}-${TIMESTAMP}.log}"

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

require_file "${PY_SCRIPT}" "canonical A14 Python script"
require_file "${A02_SCRIPT}" "frozen A02 scoring script"
require_file "${A09_ROOT}/plan/summary.json" "A09 plan summary"
require_file "${A13_ROOT}/summary.json" "A13 C_FUN workload summary"
require_file "${A13_ROOT}/python_cfun_new_scoring_units.csv" "A13 new C_FUN unit plan"
require_file "${A13_ROOT}/cfun_new_gpu_lpt_plan.csv" "A13 new C_FUN LPT plan"

mkdir -p "${LOG_DIR}"
START_EPOCH="$(date +%s)"
START_TEXT="$(date)"

finish() {
    local exit_code=$?
    local end_epoch elapsed
    end_epoch="$(date +%s)"
    elapsed=$((end_epoch - START_EPOCH))
    echo
    echo "============================================================================"
    echo "run-x-a14-v1 execution summary"
    echo "Mode:             ${MODE}"
    echo "System label:     ${SYSTEM_LABEL}"
    echo "GPU index:        ${GPU_INDEX}"
    echo "CUDA device:      ${CUDA_DEVICE}"
    echo "Started:          ${START_TEXT}"
    echo "Completed:        $(date)"
    printf 'Elapsed:          %02d:%02d:%02d\n' "$((elapsed / 3600))" "$(((elapsed % 3600) / 60))" "$((elapsed % 60))"
    echo "Exit code:        ${exit_code}"
    echo "Output directory: ${OUTPUT_DIR}"
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
    echo "ERROR: A14 requires Python 3.11.x; got ${PYTHON_VERSION}." >&2
    exit 2
fi

if ! [[ "${GPU_INDEX}" =~ ^[012]$ ]]; then
    echo "ERROR: GPU_INDEX must be 0, 1, or 2; got ${GPU_INDEX}." >&2
    exit 2
fi
if ! [[ "${CUDA_DEVICE}" =~ ^[012]$ ]]; then
    echo "ERROR: CUDA_DEVICE must be 0, 1, or 2 on R158; got ${CUDA_DEVICE}." >&2
    exit 2
fi

PY_SHA="$(sha256sum "${PY_SCRIPT}" | awk '{print $1}')"
A02_SHA="$(sha256sum "${A02_SCRIPT}" | awk '{print $1}')"

CUDA_INFO="$("${PYTHON_BIN}" - <<'PY'
import json
try:
    import torch
    payload = {
        "available": bool(torch.cuda.is_available()),
        "count": int(torch.cuda.device_count()),
        "name": str(torch.cuda.get_device_name(0)) if torch.cuda.is_available() else "unavailable",
        "memory": int(torch.cuda.get_device_properties(0).total_memory) if torch.cuda.is_available() else 0,
        "torch": str(torch.__version__),
        "torch_cuda": str(torch.version.cuda),
        "cudnn": int(torch.backends.cudnn.version() or 0),
    }
except Exception as error:
    payload = {"error": type(error).__name__ + ": " + str(error)}
print(json.dumps(payload, sort_keys=True))
PY
)"

echo "============================================================================"
echo "run-x-a14-v1: C_FUN fixed-perturbation NPR scoring on homogeneous R158 GPUs"
echo "Started:                         ${START_TEXT}"
echo "Mode:                            ${MODE}"
echo "Project root:                    ${PROJECT_ROOT}"
echo "Python:                          ${PYTHON_RESOLVED} (${PYTHON_VERSION})"
echo "Python script:                   ${PY_SCRIPT}"
echo "Python script SHA256:            ${PY_SHA}"
echo "Frozen A02 script:              ${A02_SCRIPT}"
echo "Frozen A02 SHA256:               ${A02_SHA}"
echo "A09 root:                        ${A09_ROOT}"
echo "A13 root:                        ${A13_ROOT}"
echo "Output directory:                ${OUTPUT_DIR}"
echo "System label:                    ${SYSTEM_LABEL}"
echo "GPU plan index:                  ${GPU_INDEX}"
echo "Physical CUDA device:            ${CUDA_DEVICE}"
echo "CUDA_VISIBLE_DEVICES:            ${CUDA_VISIBLE_DEVICES}"
echo "CUDA info JSON:                  ${CUDA_INFO}"
echo "Model cache:                     ${MODEL_CACHE_DIR}"
echo "HF offline:                      ${HF_HUB_OFFLINE}"
echo "Transformers offline:            ${TRANSFORMERS_OFFLINE}"
echo "Category:                        C_FUN (method_body)"
echo "Assignment policy:               deterministic_lpt_by_new_cfun_windows"
echo "A14 new C_FUN windows:            567554"
echo "A14 new C_FUN perturbations:      28377700"
echo "A14 GPU window loads:             [189150, 189188, 189216]"
echo "A11 overlap reuse (units/windows): 3 / 3"
echo "Prepared perturbations:          reused exactly from A09"
echo "Perturbation regeneration:       disabled in production scoring"
echo "Classification:                  disabled"
echo "Resume checkpoint:               SQLite per window"
echo "Overwrite checkpoint:            ${OVERWRITE}"
echo "Retry prior scoring errors:      ${RETRY_ERROR_WINDOWS}"
echo "Require all valid (strict):      ${REQUIRE_ALL_VALID}"
echo "Expected exclusion policy:       context-overflow / zero-denominator / <=1-token no-valid-perturbation"
echo "Reference check windows:         ${REFERENCE_CHECK_WINDOWS}"
if [[ "${MODE}" == "smoke" ]]; then
    echo "Smoke max assigned shards:       ${SMOKE_MAX_SHARDS}"
    echo "Smoke new C_FUN windows/shard:    ${SMOKE_WINDOWS_PER_SHARD}"
fi
echo "Log file:                        ${LOG_FILE}"
echo "============================================================================"

if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test-only --output-dir /tmp/a14-self-test-output --gpu-index "${GPU_INDEX}" --system-label self-test
fi

ARGS=(
    --project-root "${PROJECT_ROOT}"
    --a09-root "${A09_ROOT}"
    --a13-root "${A13_ROOT}"
    --a02-script "${A02_SCRIPT}"
    --output-dir "${OUTPUT_DIR}"
    --gpu-index "${GPU_INDEX}"
    --system-label "${SYSTEM_LABEL}"
    --model-cache-dir "${MODEL_CACHE_DIR}"
    --progress-every-windows "${PROGRESS_EVERY_WINDOWS}"
    --reference-check-windows "${REFERENCE_CHECK_WINDOWS}"
)

if [[ "${MODE}" == "smoke" ]]; then
    ARGS+=(--max-shards "${SMOKE_MAX_SHARDS}" --max-windows-per-shard "${SMOKE_WINDOWS_PER_SHARD}")
fi
if [[ "${MODE}" == "finalize" ]]; then
    ARGS+=(--finalize-only)
fi
if [[ "${OVERWRITE}" == "1" ]]; then
    ARGS+=(--overwrite)
fi
if [[ "${RETRY_ERROR_WINDOWS}" == "1" ]]; then
    ARGS+=(--retry-error-windows)
else
    ARGS+=(--no-retry-error-windows)
fi
if [[ "${REQUIRE_ALL_VALID}" == "1" ]]; then
    ARGS+=(--require-all-valid)
else
    ARGS+=(--no-require-all-valid)
fi
if [[ "${ALLOW_NON_A6000}" == "1" ]]; then
    ARGS+=(--allow-non-a6000)
fi

"${PYTHON_BIN}" "${PY_SCRIPT}" "${ARGS[@]}"

# Verify that the worker produced the complete expected artifact set and that
# all hard QC gates passed. Expected exclusions are allowed by policy.
for required_output in \
    "${OUTPUT_DIR}/window_scores.sqlite3" \
    "${OUTPUT_DIR}/python_cfun_new_window_npr_scores.csv" \
    "${OUTPUT_DIR}/python_cfun_new_unique_code_unit_npr_scores.csv" \
    "${OUTPUT_DIR}/python_cfun_new_npr_exclusions.csv" \
    "${OUTPUT_DIR}/python_cfun_new_npr_failures.csv" \
    "${OUTPUT_DIR}/assigned_shard_audit.csv" \
    "${OUTPUT_DIR}/reference_scoring_checks.csv" \
    "${OUTPUT_DIR}/checks.csv" \
    "${OUTPUT_DIR}/progress.json" \
    "${OUTPUT_DIR}/summary.json" \
    "${OUTPUT_DIR}/metadata.json"; do
    require_file "${required_output}" "A14 worker output"
done

read -r STATUS FULL_WINDOWS SELECTED_WINDOWS DB_WINDOWS ERRORS EXPECTED_EXCLUSIONS UNEXPECTED_INVALID PARTIAL_UNITS FAILED_CHECKS FAILURE_ROWS REFERENCE_FAILURES < <(
    "${PYTHON_BIN}" - "${OUTPUT_DIR}/summary.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as stream:
    summary = json.load(stream)

print(
    summary["status"],
    summary["full_expected_cfun_new_windows"],
    summary["selected_expected_windows"],
    summary["database_windows"],
    summary["scoring_errors"],
    summary["expected_exclusion_windows"],
    summary["unexpected_invalid_windows"],
    summary["partial_unique_units"],
    summary["failed_checks"],
    summary["failure_rows"],
    summary["reference_failures"],
)
PY
)

case "${GPU_INDEX}" in
    0) EXPECTED_GPU_WINDOWS=189150 ;;
    1) EXPECTED_GPU_WINDOWS=189188 ;;
    2) EXPECTED_GPU_WINDOWS=189216 ;;
esac

echo
echo "============================================================================"
echo "run-x-a14-v1 worker output verification"
echo "Status:                          ${STATUS}"
echo "Full planned new C_FUN windows: ${FULL_WINDOWS}"
echo "Selected expected windows:       ${SELECTED_WINDOWS}"
echo "Database windows:                ${DB_WINDOWS}"
echo "Scoring errors:                  ${ERRORS}"
echo "Expected exclusion windows:      ${EXPECTED_EXCLUSIONS}"
echo "Unexpected invalid windows:      ${UNEXPECTED_INVALID}"
echo "Partial unique units:            ${PARTIAL_UNITS}"
echo "Failed checks:                   ${FAILED_CHECKS}"
echo "Failure rows:                    ${FAILURE_ROWS}"
echo "Reference failures:              ${REFERENCE_FAILURES}"
echo "============================================================================"

if [[ "${STATUS}" != "PASS" && "${STATUS}" != "PASS_WITH_EXCLUSIONS" ]]; then
    echo "ERROR: A14 worker completed with non-passing status: ${STATUS}" >&2
    exit 1
fi
if [[ "${FAILED_CHECKS}" != "0" || "${FAILURE_ROWS}" != "0" || "${ERRORS}" != "0" || "${UNEXPECTED_INVALID}" != "0" || "${REFERENCE_FAILURES}" != "0" ]]; then
    echo "ERROR: A14 worker hard QC gate failed." >&2
    exit 1
fi
if [[ "${MODE}" != "smoke" && "${FULL_WINDOWS}" != "${EXPECTED_GPU_WINDOWS}" ]]; then
    echo "ERROR: GPU ${GPU_INDEX} expected ${EXPECTED_GPU_WINDOWS} new C_FUN windows but summary reports ${FULL_WINDOWS}." >&2
    exit 1
fi
if [[ "${MODE}" != "smoke" && "${SELECTED_WINDOWS}" != "${EXPECTED_GPU_WINDOWS}" ]]; then
    echo "ERROR: Non-smoke A14 selected-window count does not match the frozen GPU load." >&2
    exit 1
fi
if [[ "${DB_WINDOWS}" != "${SELECTED_WINDOWS}" ]]; then
    echo "ERROR: A14 database-window count does not reconcile selected expected windows." >&2
    exit 1
fi
