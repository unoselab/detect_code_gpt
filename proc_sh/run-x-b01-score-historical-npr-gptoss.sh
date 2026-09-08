#!/usr/bin/env bash
# run-x-b01-v5: exact-tie profiling and B=1 GPT-OSS historical NPR optimization.
#
# This standalone wrapper was created by copying the prior B01 wrapper logic and
# adapting it for the v5 Python experiment. It never calls an older shell script.
# Existing A02 and rank.py Python code are reused only as frozen scientific/reference
# implementations; A09 windows and ordered perturbations remain unchanged.
#
# DELIVERY (remove -v5 when deploying to canonical server names):
#   proc_sh/run-x-b01-score-historical-npr-gptoss-v5.sh
#   code-detection/score_historical_npr_gptoss-v5.py
#
# REQUIRED READ-ONLY INPUTS:
#   code-detection/score_snapshot_npr.py
#   code-detection/baselines/rank.py
#   output/snapshot_npr/run-x-a09/{plan,shards}
#   output/snapshot_npr/run-x-b01/smoke/window_scores.sqlite3 (v2 reference)
#   cached openai/gpt-oss-120b at the pinned model revision
#
# MODES:
#   profile (default; smoke alias):
#     Use B=1 only. Measure tokenizer, H2D, model-forward, legacy argsort,
#     reduction, and the unchanged rank.py 0.01-s sleep contribution. On the same
#     real logits, test exact O(V) tie-order hypotheses. No production approval.
#   validate:
#     Requires profile_summary.json with a zero-integer-mismatch non-sort tie rule.
#     Recompute 25 v2 windows and all 51 scalar components using B=1 only.
#   benchmark:
#     Requires passing validation. Uniformly sample 128 planned windows plus stress
#     cases, recheck sequential equivalence, and estimate full-run completion time.
#   run:
#     Requires a matching production_approval.json. The hard conference runtime gate
#     is <=7 days; <=5 days is preferred.
#   finalize:
#     Rebuild exports from an existing v5 production checkpoint without loading GPT-OSS.
#
# FIRST COMMAND ON r158:
#   MODE=profile CUDA_DEVICE=0,1,2 PROFILE_WINDOWS=5 bash proc_sh/run-x-b01-score-historical-npr-gptoss.sh
#
# IMPORTANT:
#   v4 established that GPT-OSS batch size >1 changes the numerical result. v5 therefore
#   fixes BATCH_SIZES=1 and searches only for an exact rank-extraction speedup.
#   No classification/thresholding is performed in B01; tau=1.545529 is downstream.
#   v2 smoke and A09 inputs are read-only. v5 writes only under run-x-b01/v5 by default.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"
RUN_PREFIX="run-x-b01"
MODE="${MODE:-profile}"
[[ "${MODE}" != "smoke" ]] || MODE="profile"
case "${MODE}" in
  profile|validate|benchmark|run|finalize) ;;
  *) echo "ERROR: MODE must be profile, validate, benchmark, run, or finalize." >&2; exit 2 ;;
esac
PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/score_historical_npr_gptoss.py}"
A02_SCRIPT="${A02_SCRIPT:-code-detection/score_snapshot_npr.py}"
RANK_SCRIPT="${RANK_SCRIPT:-code-detection/baselines/rank.py}"
A09_ROOT="${A09_ROOT:-output/snapshot_npr/run-x-a09}"
A10_ROOT="${A10_ROOT:-output/snapshot_npr/run-x-a10}"
A13_ROOT="${A13_ROOT:-output/snapshot_npr/run-x-a13}"
REFERENCE_DB="${REFERENCE_DB:-output/snapshot_npr/run-x-b01/smoke/window_scores.sqlite3}"
OUTPUT_ROOT="${OUTPUT_ROOT:-output/snapshot_npr/run-x-b01/v5}"
PROFILE_DIR="${PROFILE_DIR:-${OUTPUT_ROOT}/profile}"
VALIDATION_DIR="${VALIDATION_DIR:-${OUTPUT_ROOT}/validation}"
BENCHMARK_DIR="${BENCHMARK_DIR:-${OUTPUT_ROOT}/benchmark}"
PROFILE_SUMMARY="${PROFILE_SUMMARY:-${PROFILE_DIR}/profile_summary.json}"
VALIDATION_SUMMARY="${VALIDATION_SUMMARY:-${VALIDATION_DIR}/validation_summary.json}"
APPROVAL="${APPROVAL:-${BENCHMARK_DIR}/production_approval.json}"
LOG_DIR="${LOG_DIR:-logs/run-x-b01}"
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-${HOME}/.cache/huggingface/hub}"
SCORING_MODEL="openai/gpt-oss-120b"
MODEL_REVISION="${MODEL_REVISION:-b5c939de8f754692c1647ca79fbf85e8c1e70f8a}"
EXPECTED_MODEL_REVISION="${EXPECTED_MODEL_REVISION:-${MODEL_REVISION}}"
SCOPE="${SCOPE:-all}"
SHARD_IDS="${SHARD_IDS:-all}"
HOST_SHORT="$(hostname -s 2>/dev/null || hostname)"
if [[ -z "${CUDA_DEVICE:-}" ]]; then
  case "${HOST_SHORT}" in *r158*|*R158*) CUDA_DEVICE="0,1,2" ;; *) CUDA_DEVICE="0,1" ;; esac
fi
if [[ -z "${SYSTEM_LABEL:-}" ]]; then
  case "${HOST_SHORT}" in
    *r158*|*R158*) SYSTEM_LABEL="r158-3x-a6000" ;;
    *173*|*IST173*) SYSTEM_LABEL="173-2x-rtx6000ada" ;;
    *) SYSTEM_LABEL="${HOST_SHORT}" ;;
  esac
fi
PROFILE_WINDOWS="${PROFILE_WINDOWS:-5}"
VALIDATION_WINDOWS="${VALIDATION_WINDOWS:-${SMOKE_MAX_WINDOWS:-25}}"
BENCHMARK_WINDOWS="${BENCHMARK_WINDOWS:-128}"
SAMPLING_SEED="${SAMPLING_SEED:-20260723}"
BATCH_SIZES="${BATCH_SIZES:-1}"
MAX_BATCH_TOKENS="${MAX_BATCH_TOKENS:-2048}"
RANK_BACKEND="${RANK_BACKEND:-auto}"
RANK_TILE_TOKENS="${RANK_TILE_TOKENS:-32}"
USE_CACHE="${USE_CACHE:-false}"
OOM_POLICY="${OOM_POLICY:-split}"
CANDIDATE="${CANDIDATE:-}"
ATOL="${ATOL:-1e-6}"
RTOL="${RTOL:-1e-6}"
PREFERRED_PRODUCTION_DAYS="${PREFERRED_PRODUCTION_DAYS:-5}"
MAX_PRODUCTION_DAYS="${MAX_PRODUCTION_DAYS:-7}"
PROGRESS_EVERY_WINDOWS="${PROGRESS_EVERY_WINDOWS:-5}"
AUDIT_EVERY_WINDOWS="${AUDIT_EVERY_WINDOWS:-1000}"
OVERWRITE="${OVERWRITE:-0}"
RETRY_ERROR_WINDOWS="${RETRY_ERROR_WINDOWS:-1}"
TWO_GPU_MAX_MEMORY="${TWO_GPU_MAX_MEMORY:-42GiB}"
PER_GPU_MAX_MEMORY="${PER_GPU_MAX_MEMORY:-44GiB}"
CPU_MAX_MEMORY="${CPU_MAX_MEMORY:-128GiB}"
ALLOW_UNSUPPORTED_GPU_TOPOLOGY="${ALLOW_UNSUPPORTED_GPU_TOPOLOGY:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-0}"
TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-0}"
case "${MODE}" in
  profile) OUTPUT_DIR="${OUTPUT_DIR:-${PROFILE_DIR}}" ;;
  validate) OUTPUT_DIR="${OUTPUT_DIR:-${VALIDATION_DIR}}" ;;
  benchmark) OUTPUT_DIR="${OUTPUT_DIR:-${BENCHMARK_DIR}}" ;;
  *) OUTPUT_DIR="${OUTPUT_DIR:-${OUTPUT_ROOT}/results}" ;;
esac
if [[ "${OVERWRITE}" != "0" && "${MODE}" != "run" ]]; then
  echo "ERROR: OVERWRITE=1 is only valid for an explicitly fresh v5 production checkpoint." >&2; exit 2
fi
export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"
export TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE TRANSFORMERS_OFFLINE

# GPT-OSS MXFP4 uses the Hugging Face kernels package, which performs an online
# publisher-trust check for kernels-community/gpt-oss-triton-kernels during model
# loading even when the model weights are already cached.  B01 therefore must not
# force Hugging Face offline mode.  The model itself remains reproducible because
# MODEL_REVISION is pinned and no package installation/update is performed here.
case "${HF_HUB_OFFLINE,,}" in
  1|true|yes|on)
    echo "ERROR: HF_HUB_OFFLINE=${HF_HUB_OFFLINE} blocks GPT-OSS kernel trust verification. Set HF_HUB_OFFLINE=0." >&2
    exit 2
    ;;
esac
case "${TRANSFORMERS_OFFLINE,,}" in
  1|true|yes|on)
    echo "ERROR: TRANSFORMERS_OFFLINE=${TRANSFORMERS_OFFLINE} is not supported for B01 GPT-OSS validation. Set TRANSFORMERS_OFFLINE=0." >&2
    exit 2
    ;;
esac
TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/${RUN_PREFIX}-v5-${MODE}-${SYSTEM_LABEL}-${TIMESTAMP}.log}"
mkdir -p "${LOG_DIR}"
require_file() {
    local path="$1"
    local label="$2"
    [[ -f "${path}" ]] || { echo "ERROR: Missing ${label}: ${path}" >&2; exit 2; }
}


if [[ "${PYTHON_BIN}" == */* ]]; then
  [[ -x "${PYTHON_BIN}" ]] || { echo "ERROR: Python unavailable: ${PYTHON_BIN}" >&2; exit 2; }
else
  command -v "${PYTHON_BIN}" >/dev/null || { echo "ERROR: Python unavailable: ${PYTHON_BIN}" >&2; exit 2; }
fi
require_file "${PY_SCRIPT}" "B01-v5 Python"
require_file "${A02_SCRIPT}" "frozen A02 helper"
require_file "${RANK_SCRIPT}" "original rank implementation"
require_file "${A09_ROOT}/plan/summary.json" "A09 summary"
require_file "${A09_ROOT}/plan/unique_primary_units.csv" "A09 unit plan"
case "${MODE}" in
  profile) require_file "${REFERENCE_DB}" "v2 smoke checkpoint (read-only)" ;;
  validate) require_file "${REFERENCE_DB}" "v2 smoke checkpoint (read-only)"; require_file "${PROFILE_SUMMARY}" "passing v5 profile" ;;
  benchmark) require_file "${VALIDATION_SUMMARY}" "passing v5 validation" ;;
  run) require_file "${APPROVAL}" "production approval; otherwise full run is HOLD" ;;
esac
START_EPOCH="$(date +%s)"
START_TEXT="$(date)"
finish() {
    local exit_code=$?
    local end_epoch elapsed
    end_epoch="$(date +%s)"
    elapsed=$((end_epoch - START_EPOCH))
    echo
    echo "============================================================================"
    echo "run-x-b01-v5 execution summary"
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


PYTHON_RESOLVED="$("${PYTHON_BIN}" -c 'import sys; print(sys.executable)')"
PYTHON_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(sys.version.split()[0])')"
PYTHON_MINOR="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "${PYTHON_MINOR}" != "3.11" ]]; then
  echo "ERROR: Use the existing Python 3.11 GPT-OSS environment; found ${PYTHON_VERSION}." >&2; exit 2
fi
PY_SHA="$(sha256sum "${PY_SCRIPT}" | awk '{print $1}')"
A02_SHA="$(sha256sum "${A02_SCRIPT}" | awk '{print $1}')"
RANK_SHA="$(sha256sum "${RANK_SCRIPT}" | awk '{print $1}')"
echo "============================================================================"
echo "run-x-b01-v5: exact-tie profiling and B=1 GPT-OSS historical NPR optimization"
echo "Mode:                            ${MODE}"
echo "Project root:                    ${PROJECT_ROOT}"
echo "Python:                          ${PYTHON_RESOLVED} (${PYTHON_VERSION})"
echo "Active conda env:                ${CONDA_DEFAULT_ENV:-<none>}"
echo "Python script SHA256:            ${PY_SHA}"
echo "Frozen A02 SHA256:               ${A02_SHA}"
echo "Original rank SHA256:            ${RANK_SHA}"
echo "Scoring model:                   ${SCORING_MODEL}"
echo "Pinned model revision:           ${MODEL_REVISION}"
echo "CUDA_VISIBLE_DEVICES:            ${CUDA_VISIBLE_DEVICES}"
echo "System label:                    ${SYSTEM_LABEL}"
echo "v2 reference (READ ONLY):        ${REFERENCE_DB}"
echo "Output directory:                ${OUTPUT_DIR}"
echo "Scope / shards:                  ${SCOPE} / ${SHARD_IDS}"
echo "Rank execution:                  B=1 only; backend=${RANK_BACKEND}"
echo "Profile / validation / benchmark: ${PROFILE_WINDOWS} / ${VALIDATION_WINDOWS} / ${BENCHMARK_WINDOWS} windows"
echo "Padded-token batch cap:          ${MAX_BATCH_TOKENS} (no truncation)"
echo "use_cache / OOM policy:          ${USE_CACHE} / ${OOM_POLICY}"
echo "Scalar tolerances (atol / rtol):  ${ATOL} / ${RTOL}"
echo "Conference runtime target:       preferred <=${PREFERRED_PRODUCTION_DAYS} days; hard <=${MAX_PRODUCTION_DAYS} days"
echo "Production execution settings:   read from matching approval only"
echo "Window / perturbations:          128 literal-space tokens / original ordered 50"
echo "Classification / thresholding:   disabled"
echo "HF_HUB_OFFLINE / TRANSFORMERS:    ${HF_HUB_OFFLINE} / ${TRANSFORMERS_OFFLINE}"
echo "Model reproducibility:            revision pinned; no package updates; HF network allowed for kernel trust/cache"
echo "Log file:                        ${LOG_FILE}"
nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv,noheader || true
echo "============================================================================"
if [[ "${RUN_SELF_TEST}" == "1" ]]; then
  "${PYTHON_BIN}" "${PY_SCRIPT}" --project-root "${PROJECT_ROOT}" --a02-script "${A02_SCRIPT}" \
    --rank-script "${RANK_SCRIPT}" --output-dir "/tmp/run-x-b01-v5-self-test" --self-test-only
fi
ARGS=(
  --mode "${MODE}" --project-root "${PROJECT_ROOT}"
  --a02-script "${A02_SCRIPT}" --rank-script "${RANK_SCRIPT}"
  --a09-root "${A09_ROOT}" --a10-root "${A10_ROOT}" --a13-root "${A13_ROOT}"
  --output-dir "${OUTPUT_DIR}" --reference-db "${REFERENCE_DB}"
  --profile-summary "${PROFILE_SUMMARY}" --validation-summary "${VALIDATION_SUMMARY}" --approval "${APPROVAL}"
  --scope "${SCOPE}" --shard-ids "${SHARD_IDS}"
  --scoring-model "${SCORING_MODEL}" --model-cache-dir "${MODEL_CACHE_DIR}"
  --model-revision "${MODEL_REVISION}" --expected-model-revision "${EXPECTED_MODEL_REVISION}"
  --system-label "${SYSTEM_LABEL}" --two-gpu-max-memory "${TWO_GPU_MAX_MEMORY}"
  --per-gpu-max-memory "${PER_GPU_MAX_MEMORY}" --cpu-max-memory "${CPU_MAX_MEMORY}"
  --profile-windows "${PROFILE_WINDOWS}" --validation-windows "${VALIDATION_WINDOWS}" --benchmark-windows "${BENCHMARK_WINDOWS}"
  --sampling-seed "${SAMPLING_SEED}" --batch-sizes "${BATCH_SIZES}"
  --max-batch-tokens "${MAX_BATCH_TOKENS}" --rank-backend "${RANK_BACKEND}"
  --rank-tile-tokens "${RANK_TILE_TOKENS}" --use-cache "${USE_CACHE}" --oom-policy "${OOM_POLICY}"
  --atol "${ATOL}" --rtol "${RTOL}" --preferred-production-days "${PREFERRED_PRODUCTION_DAYS}" --max-production-days "${MAX_PRODUCTION_DAYS}"
  --progress-every-windows "${PROGRESS_EVERY_WINDOWS}" --audit-every-windows "${AUDIT_EVERY_WINDOWS}"
)
[[ -z "${CANDIDATE}" ]] || ARGS+=(--candidate "${CANDIDATE}")
[[ "${OVERWRITE}" != "1" ]] || ARGS+=(--overwrite)
[[ "${ALLOW_UNSUPPORTED_GPU_TOPOLOGY}" != "1" ]] || ARGS+=(--allow-unsupported-gpu-topology)
if [[ "${RETRY_ERROR_WINDOWS}" == "1" ]]; then ARGS+=(--retry-error-windows); else ARGS+=(--no-retry-error-windows); fi
"${PYTHON_BIN}" "${PY_SCRIPT}" "${ARGS[@]}"
require_file "${OUTPUT_DIR}/summary.json" "v5 stage summary"
"${PYTHON_BIN}" - "${OUTPUT_DIR}/summary.json" <<'PYVERIFY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as stream:
    summary = json.load(stream)
print("Stage status:", summary.get("status"))
if "production_ready" in summary:
    print("Production:", "APPROVED" if summary["production_ready"] else "HOLD")
if summary.get("status") != "PASS":
    raise SystemExit(1)
PYVERIFY
