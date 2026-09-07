#!/usr/bin/env bash
#
# run-x-b01: GPT-OSS-120B historical NPR scoring.
#
# This wrapper is standalone. It reuses the scientific inputs prepared by the
# existing historical NPR pipeline, but it does not call any previous shell
# wrapper. The corresponding B01 Python script replaces the old StarCoder2-7B
# scorer with GPT-OSS-120B while preserving A09 windows, perturbations, and A02
# NPR aggregation semantics.
#
# Versioned delivery files:
#   proc_sh/run-x-b01-score-historical-npr-gptoss-v2.sh
#   code-detection/score_historical_npr_gptoss-v2.py
#
# Canonical server files after removing the version suffix:
#   proc_sh/run-x-b01-score-historical-npr-gptoss.sh
#   code-detection/score_historical_npr_gptoss.py
#
# INPUTS
#   output/snapshot_npr/run-x-a09/plan/summary.json
#   output/snapshot_npr/run-x-a09/plan/unique_primary_units.csv
#   output/snapshot_npr/run-x-a09/shards/shard-000-of-096.jsonl.gz ... 095
#   output/snapshot_npr/run-x-a09/shards/shard-000-of-096.summary.json ... 095
#       Frozen historical windows and ordered 50 perturbations/window.
#   code-detection/score_snapshot_npr.py
#       Frozen A02 aggregation/validity helper; SHA-256 is checked by Python.
#   output/snapshot_npr/run-x-a10/summary.json
#   output/snapshot_npr/run-x-a13/summary.json
#       Reference-only provenance checks for the prior FUN/C_FUN workloads.
#
# OUTPUTS
#   output/snapshot_npr/run-x-b01/{smoke|results}/window_scores.sqlite3
#       Durable per-window resume checkpoint.
#   python_historical_gptoss_window_npr_scores.csv
#   python_historical_gptoss_unique_code_unit_npr_scores.csv
#   python_fun_unique_code_unit_npr_scores.csv
#   python_cfun_unique_code_unit_npr_scores.csv
#   python_historical_gptoss_npr_exclusions.csv
#   python_historical_gptoss_npr_failures.csv
#   assigned_shard_audit.csv, checks.csv, progress.json, summary.json, metadata.json
#
# DEFAULT SCIENTIFIC SCOPE
#   SCOPE=all scores the union of A09 FUN and C_FUN memberships. This covers both
#   regular functions and class methods required by downstream RF/CM/RF+CM analyses.
#   The three FUN/C_FUN overlap SHAs are scored once and retain both memberships.
#
# MODES
#   MODE=smoke     Small end-to-end GPT-OSS scoring run. Uses a separate output dir.
#   MODE=run       Production/resume scoring. OVERWRITE=1 starts fresh; 0 resumes.
#   MODE=finalize  Rebuild CSV/QC from an existing SQLite checkpoint without loading
#                  GPT-OSS or rescoring any window. OVERWRITE must be 0.
#
# R158 PRIMARY EXAMPLES
#   Smoke on all three RTX A6000 GPUs:
#     MODE=smoke CUDA_DEVICE=0,1,2 bash proc_sh/run-x-b01-score-historical-npr-gptoss.sh
#
#   First production invocation after smoke:
#     MODE=run CUDA_DEVICE=0,1,2 OVERWRITE=1 bash proc_sh/run-x-b01-score-historical-npr-gptoss.sh
#
#   Resume an interrupted production invocation:
#     MODE=run CUDA_DEVICE=0,1,2 OVERWRITE=0 bash proc_sh/run-x-b01-score-historical-npr-gptoss.sh
#
#   Finalize/rebuild exports without loading the model:
#     MODE=finalize OVERWRITE=0 bash proc_sh/run-x-b01-score-historical-npr-gptoss.sh
#
# SERVER 173 OPTIONAL REPRODUCTION EXAMPLE
#   The same package can be tested on the 2x48GiB RTX 6000 Ada topology:
#     MODE=smoke CUDA_DEVICE=0,1 bash proc_sh/run-x-b01-score-historical-npr-gptoss.sh
#
# IMPORTANT
#   B01 intentionally does NOT apply the new downstream threshold 1.545529.
#   This stage produces continuous GPT-OSS NPR scores only. Thresholding and
#   historical occurrence/file localization belong to the next experiment.
#
# Optional environment variables:
#   PROJECT_ROOT, PYTHON_BIN, PY_SCRIPT, A02_SCRIPT, RANK_SCRIPT, A09_ROOT, A10_ROOT, A13_ROOT,
#   OUTPUT_ROOT, OUTPUT_DIR, LOG_DIR, MODEL_CACHE_DIR, SCORING_MODEL, MODEL_REVISION,
#   EXPECTED_MODEL_REVISION, MODE, SCOPE, SHARD_IDS, CUDA_DEVICE, SYSTEM_LABEL,
#   SMOKE_MAX_WINDOWS, PROGRESS_EVERY_WINDOWS, OVERWRITE, RETRY_ERROR_WINDOWS,
#   TWO_GPU_MAX_MEMORY, PER_GPU_MAX_MEMORY, CPU_MAX_MEMORY,
#   ALLOW_UNSUPPORTED_GPU_TOPOLOGY, RUN_SELF_TEST, HF_HUB_OFFLINE,
#   TRANSFORMERS_OFFLINE, TIMESTAMP, LOG_FILE.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

RUN_PREFIX="run-x-b01"
MODE="${MODE:-smoke}"
case "${MODE}" in
    smoke|run|finalize) ;;
    *) echo "ERROR: MODE must be smoke, run, or finalize; got ${MODE}" >&2; exit 2 ;;
esac

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/score_historical_npr_gptoss.py}"
A02_SCRIPT="${A02_SCRIPT:-code-detection/score_snapshot_npr.py}"
RANK_SCRIPT="${RANK_SCRIPT:-code-detection/baselines/rank.py}"
A09_ROOT="${A09_ROOT:-output/snapshot_npr/run-x-a09}"
A10_ROOT="${A10_ROOT:-output/snapshot_npr/run-x-a10}"
A13_ROOT="${A13_ROOT:-output/snapshot_npr/run-x-a13}"
OUTPUT_ROOT="${OUTPUT_ROOT:-output/snapshot_npr/run-x-b01}"
LOG_DIR="${LOG_DIR:-logs/run-x-b01}"
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-${HOME}/.cache/huggingface/hub}"

SCORING_MODEL="${SCORING_MODEL:-openai/gpt-oss-120b}"
MODEL_REVISION="${MODEL_REVISION:-}"
EXPECTED_MODEL_REVISION="${EXPECTED_MODEL_REVISION:-}"
SCOPE="${SCOPE:-all}"
SHARD_IDS="${SHARD_IDS:-all}"
HOST_SHORT="$(hostname -s 2>/dev/null || hostname)"
if [[ -z "${CUDA_DEVICE:-}" ]]; then
    case "${HOST_SHORT}" in
        *r158*|*R158*) CUDA_DEVICE="0,1,2" ;;
        *)            CUDA_DEVICE="0,1" ;;
    esac
fi
if [[ -z "${SYSTEM_LABEL:-}" ]]; then
    case "${HOST_SHORT}" in
        *r158*|*R158*) SYSTEM_LABEL="r158-3x-a6000" ;;
        *173*|*IST173*) SYSTEM_LABEL="173-2x-rtx6000ada" ;;
        *) SYSTEM_LABEL="${HOST_SHORT}" ;;
    esac
fi
SMOKE_MAX_WINDOWS="${SMOKE_MAX_WINDOWS:-2}"
PROGRESS_EVERY_WINDOWS="${PROGRESS_EVERY_WINDOWS:-25}"
OVERWRITE="${OVERWRITE:-0}"
RETRY_ERROR_WINDOWS="${RETRY_ERROR_WINDOWS:-1}"
TWO_GPU_MAX_MEMORY="${TWO_GPU_MAX_MEMORY:-42GiB}"
PER_GPU_MAX_MEMORY="${PER_GPU_MAX_MEMORY:-44GiB}"
CPU_MAX_MEMORY="${CPU_MAX_MEMORY:-128GiB}"
ALLOW_UNSUPPORTED_GPU_TOPOLOGY="${ALLOW_UNSUPPORTED_GPU_TOPOLOGY:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"

if [[ "${MODE}" == "smoke" ]]; then
    OUTPUT_DIR="${OUTPUT_DIR:-${OUTPUT_ROOT}/smoke}"
    HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-0}"
    TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-0}"
elif [[ "${MODE}" == "run" ]]; then
    OUTPUT_DIR="${OUTPUT_DIR:-${OUTPUT_ROOT}/results}"
    # Production defaults to the already-cached model to prevent model drift.
    HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
    TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
else
    OUTPUT_DIR="${OUTPUT_DIR:-${OUTPUT_ROOT}/results}"
    HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
    TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
fi

if [[ "${MODE}" == "finalize" && "${OVERWRITE}" != "0" ]]; then
    echo "ERROR: MODE=finalize requires OVERWRITE=0." >&2
    exit 2
fi

# If production follows a successful smoke and no explicit revision was supplied,
# automatically pin production to the exact model revision recorded by smoke.
if [[ "${MODE}" == "run" && -z "${MODEL_REVISION}" && -f "${OUTPUT_ROOT}/smoke/summary.json" ]]; then
    MODEL_REVISION="$(${PYTHON_BIN} - "${OUTPUT_ROOT}/smoke/summary.json" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as stream:
    print(json.load(stream).get("model_revision", ""))
PY
)"
    if [[ -n "${MODEL_REVISION}" && -z "${EXPECTED_MODEL_REVISION}" ]]; then
        EXPECTED_MODEL_REVISION="${MODEL_REVISION}"
    fi
fi

export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"
export TOKENIZERS_PARALLELISM="false"
export HF_HUB_OFFLINE
export TRANSFORMERS_OFFLINE

TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/${RUN_PREFIX}-v2-${MODE}-${SYSTEM_LABEL}-${TIMESTAMP}.log}"
mkdir -p "${LOG_DIR}"

require_file() {
    local path="$1"
    local label="$2"
    [[ -f "${path}" ]] || { echo "ERROR: Missing ${label}: ${path}" >&2; exit 2; }
}

if [[ "${PYTHON_BIN}" == */* ]]; then
    [[ -x "${PYTHON_BIN}" ]] || { echo "ERROR: Python unavailable: ${PYTHON_BIN}" >&2; exit 2; }
elif ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "ERROR: Python unavailable: ${PYTHON_BIN}" >&2
    exit 2
fi

require_file "${PY_SCRIPT}" "B01 Python script"
require_file "${A02_SCRIPT}" "frozen A02 scoring script"
require_file "${RANK_SCRIPT}" "DetectCodeGPT rank script"
require_file "${A09_ROOT}/plan/summary.json" "A09 plan summary"
require_file "${A09_ROOT}/plan/unique_primary_units.csv" "A09 unique-unit plan"

START_EPOCH="$(date +%s)"
START_TEXT="$(date)"
finish() {
    local exit_code=$?
    local end_epoch elapsed
    end_epoch="$(date +%s)"
    elapsed=$((end_epoch - START_EPOCH))
    echo
    echo "============================================================================"
    echo "run-x-b01-v2 execution summary"
    echo "Mode:             ${MODE}"
    echo "System label:     ${SYSTEM_LABEL}"
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

PYTHON_RESOLVED="$(${PYTHON_BIN} -c 'import sys; print(sys.executable)')"
PYTHON_VERSION="$(${PYTHON_BIN} -c 'import sys; print(sys.version.split()[0])')"
PYTHON_MINOR="$(${PYTHON_BIN} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "${PYTHON_MINOR}" != "3.11" ]]; then
    echo "ERROR: B01 requires Python 3.11.x; got ${PYTHON_VERSION}." >&2
    exit 2
fi

PY_SHA="$(sha256sum "${PY_SCRIPT}" | awk '{print $1}')"
A02_SHA="$(sha256sum "${A02_SCRIPT}" | awk '{print $1}')"
RANK_SHA="$(sha256sum "${RANK_SCRIPT}" | awk '{print $1}')"

echo "============================================================================"
echo "run-x-b01-v2: GPT-OSS historical NPR scoring"
echo "Started:                         ${START_TEXT}"
echo "Mode:                            ${MODE}"
echo "Project root:                    ${PROJECT_ROOT}"
echo "Python:                          ${PYTHON_RESOLVED} (${PYTHON_VERSION})"
echo "Active conda env:                ${CONDA_DEFAULT_ENV:-<none>}"
echo "Python script:                   ${PY_SCRIPT}"
echo "Python script SHA256:            ${PY_SHA}"
echo "Frozen A02 script:              ${A02_SCRIPT}"
echo "Frozen A02 SHA256:               ${A02_SHA}"
echo "DetectCodeGPT rank script:        ${RANK_SCRIPT}"
echo "DetectCodeGPT rank SHA256:        ${RANK_SHA}"
echo "A09 root:                        ${A09_ROOT}"
echo "A10 reference root:              ${A10_ROOT}"
echo "A13 reference root:              ${A13_ROOT}"
echo "Output directory:                ${OUTPUT_DIR}"
echo "Scoring model:                   ${SCORING_MODEL}"
echo "Model revision request:          ${MODEL_REVISION:-<default/cache>}"
echo "Expected model revision:         ${EXPECTED_MODEL_REVISION:-<record only>}"
echo "Scope:                           ${SCOPE}"
echo "Shard IDs:                       ${SHARD_IDS}"
echo "CUDA_VISIBLE_DEVICES:            ${CUDA_VISIBLE_DEVICES}"
echo "System label:                    ${SYSTEM_LABEL}"
echo "2-GPU max memory/device:         ${TWO_GPU_MAX_MEMORY}"
echo "3+-GPU max memory/device:        ${PER_GPU_MAX_MEMORY}"
echo "CPU max memory:                  ${CPU_MAX_MEMORY}"
echo "HF offline:                      ${HF_HUB_OFFLINE}"
echo "Transformers offline:            ${TRANSFORMERS_OFFLINE}"
echo "Window size:                     128 literal-space tokens"
echo "Perturbations/window:            50 (reused exactly from A09)"
echo "Perturbation regeneration:       disabled"
echo "Classification/thresholding:     disabled"
echo "Production threshold 1.545529:   intentionally NOT applied in B01"
echo "Resume checkpoint:               SQLite per window"
echo "Overwrite checkpoint:            ${OVERWRITE}"
echo "Retry prior scoring errors:      ${RETRY_ERROR_WINDOWS}"
if [[ "${MODE}" == "smoke" ]]; then
    echo "Smoke max windows:               ${SMOKE_MAX_WINDOWS}"
fi
echo "Log file:                        ${LOG_FILE}"
echo "GPU inventory:"
nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv,noheader || true
echo "============================================================================"

if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" \
        --project-root "${PROJECT_ROOT}" \
        --a02-script "${A02_SCRIPT}" \
        --rank-script "${RANK_SCRIPT}" \
        --output-dir "/tmp/run-x-b01-self-test" \
        --self-test-only
fi

ARGS=(
    --project-root "${PROJECT_ROOT}"
    --a02-script "${A02_SCRIPT}"
    --rank-script "${RANK_SCRIPT}"
    --a09-root "${A09_ROOT}"
    --a10-root "${A10_ROOT}"
    --a13-root "${A13_ROOT}"
    --output-dir "${OUTPUT_DIR}"
    --scope "${SCOPE}"
    --shard-ids "${SHARD_IDS}"
    --scoring-model "${SCORING_MODEL}"
    --model-cache-dir "${MODEL_CACHE_DIR}"
    --system-label "${SYSTEM_LABEL}"
    --progress-every-windows "${PROGRESS_EVERY_WINDOWS}"
    --two-gpu-max-memory "${TWO_GPU_MAX_MEMORY}"
    --per-gpu-max-memory "${PER_GPU_MAX_MEMORY}"
    --cpu-max-memory "${CPU_MAX_MEMORY}"
)

if [[ -n "${MODEL_REVISION}" ]]; then
    ARGS+=(--model-revision "${MODEL_REVISION}")
fi
if [[ -n "${EXPECTED_MODEL_REVISION}" ]]; then
    ARGS+=(--expected-model-revision "${EXPECTED_MODEL_REVISION}")
fi
if [[ "${MODE}" == "smoke" ]]; then
    ARGS+=(--max-windows "${SMOKE_MAX_WINDOWS}")
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
if [[ "${ALLOW_UNSUPPORTED_GPU_TOPOLOGY}" == "1" ]]; then
    ARGS+=(--allow-unsupported-gpu-topology)
fi

"${PYTHON_BIN}" "${PY_SCRIPT}" "${ARGS[@]}"

require_file "${OUTPUT_DIR}/summary.json" "B01 summary"
require_file "${OUTPUT_DIR}/checks.csv" "B01 checks"
require_file "${OUTPUT_DIR}/window_scores.sqlite3" "B01 SQLite checkpoint"
require_file "${OUTPUT_DIR}/python_historical_gptoss_unique_code_unit_npr_scores.csv" "B01 unit scores"

read -r STATUS DB_WINDOWS ERRORS FAILED MODEL_REV < <(
    "${PYTHON_BIN}" - "${OUTPUT_DIR}/summary.json" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as stream:
    s = json.load(stream)
print(s["status"], s["database_windows"], s["scoring_errors"], s["failed_checks"], s.get("model_revision", ""))
PY
)

echo
echo "============================================================================"
echo "run-x-b01-v2 verification"
echo "Status:                          ${STATUS}"
echo "Database windows:                ${DB_WINDOWS}"
echo "Scoring errors:                  ${ERRORS}"
echo "Failed checks:                   ${FAILED}"
echo "Resolved model revision:         ${MODEL_REV:-<not loaded/finalize>}"
echo "============================================================================"

if [[ "${STATUS}" != "PASS" || "${FAILED}" != "0" ]]; then
    echo "ERROR: B01 verification failed." >&2
    exit 1
fi
