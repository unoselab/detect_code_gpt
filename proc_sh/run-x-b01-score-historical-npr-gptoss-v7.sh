#!/usr/bin/env bash
# run-x-b01-v7: deferred-synchronization pipelining probe for GPT-OSS historical NPR.
#
# This standalone wrapper follows the prior B01 wrappers and never calls an older
# shell script. It does not modify or replace the canonical v6 deployment: v6's
# Python is imported read-only as the frozen engine and equivalence reference,
# and v7 writes only under run-x-b01/v7.
#
# DELIVERY (remove -v7 only after the validate/benchmark stages exist and pass):
#   proc_sh/run-x-b01-score-historical-npr-gptoss-v7.sh
#   code-detection/score_historical_npr_gptoss-v7.py
#
# WHY
#   v6 measured forward=~90% of runtime and, via its device-stage diagnostic,
#   that the busiest GPU is active only 34.6% (r158) / 49.1% (173) of wall clock:
#   device_map splits layers across GPUs, so one B=1 sequence walks GPU0 -> GPU1
#   (-> GPU2) while the other devices idle. v6 also calls .item() after every
#   sequence, which blocks the host until that sequence fully drains, so the next
#   sequence cannot start on GPU0 while the previous one finishes downstream.
#
# WHAT V7 DOES
#   Keeps every sequence at batch size 1 -- v4's finding that GPT-OSS batch > 1
#   changes the numbers still stands and is not revisited. The only change is
#   that up to PIPELINE depth sequences are issued before the host synchronizes,
#   so CUDA can overlap the per-device queues. Guards (non-finite logits, the
#   one-match rank invariant) and tie statistics are deferred, never skipped:
#   they are asserted at flush time before any value is returned.
#
# WHAT V7 DOES NOT DO
#   No batching. No changed arithmetic. No threshold (tau=1.545529 stays
#   downstream). No production approval, no production checkpoint. This version
#   implements only MODE=pipeline_profile, the cheap decisive test of whether
#   deferral buys real overlap at identical numbers. The 25-window validate and
#   128-window benchmark stages come next, in that order, only if it does.
#
# REQUIRED READ-ONLY INPUTS:
#   code-detection/score_historical_npr_gptoss.py   (v6 engine; SHA-256 pinned)
#   code-detection/score_snapshot_npr.py
#   code-detection/baselines/rank.py
#   output/snapshot_npr/run-x-a09/{plan,shards}
#   output/snapshot_npr/run-x-b01/smoke/window_scores.sqlite3   (v2 reference)
#   output/snapshot_npr/run-x-b01/v6/profile/profile_summary.json (tie rule)
#   cached openai/gpt-oss-120b at the pinned model revision
#
# FIRST COMMAND (either host; DEPTHS defaults to the GPU count's ladder):
#   MODE=pipeline_profile PROFILE_WINDOWS=5 \
#     bash proc_sh/run-x-b01-score-historical-npr-gptoss-v7.sh
#
#   r158 (3x A6000) -> CUDA_DEVICE=0,1,2, per-GPU cap 44GiB, DEPTHS=1,2,3,6,12
#   173  (2x Ada)   -> CUDA_DEVICE=0,1,   per-GPU cap 42GiB, DEPTHS=1,2,4,8
#   Both are auto-detected from the hostname; override DEPTHS to test others.
#
# READING THE RESULT
#   A depth is usable only if it is EXACT against v6 on every one of the 51
#   per-window components. A depth that is faster but not exact is discarded,
#   not accommodated with a tolerance.
#
#   Depth matters against the stage count: an S-stage device_map keeps at most
#   min(depth, S) devices busy, so on r158 depth 1 and 2 cannot fill the 3-stage
#   pipeline and a flat result there proves nothing. The summary records
#   pipeline_stages and flags each depth with fills_pipeline for this reason.
#
#   This stage deliberately does NOT reuse v6's device-stage diagnostic: those
#   hooks call torch.cuda.synchronize() per device, which would serialize the
#   very overlap being measured. To watch utilization live, sample nvidia-smi
#   from a separate shell instead.
# 
# Run:
# MODE=pipeline_profile PROFILE_WINDOWS=5 bash proc_sh/run-x-b01-score-historical-npr-gptoss-v7.sh
# 

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"
RUN_PREFIX="run-x-b01"
MODE="${MODE:-pipeline_profile}"
case "${MODE}" in
  pipeline_profile) ;;
  *) echo "ERROR: v7 implements MODE=pipeline_profile only (validate/benchmark/run are not built yet)." >&2; exit 2 ;;
esac
PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/score_historical_npr_gptoss-v7.py}"
V6_SCRIPT="${V6_SCRIPT:-code-detection/score_historical_npr_gptoss.py}"
EXPECTED_V6_SHA256="${EXPECTED_V6_SHA256:-321ca3331bc2e8f3c5a8cb5feff86a8722053aec636a50c9a433a64c0e3f7485}"
A02_SCRIPT="${A02_SCRIPT:-code-detection/score_snapshot_npr.py}"
RANK_SCRIPT="${RANK_SCRIPT:-code-detection/baselines/rank.py}"
A09_ROOT="${A09_ROOT:-output/snapshot_npr/run-x-a09}"
REFERENCE_DB="${REFERENCE_DB:-output/snapshot_npr/run-x-b01/smoke/window_scores.sqlite3}"
V6_PROFILE_SUMMARY="${V6_PROFILE_SUMMARY:-output/snapshot_npr/run-x-b01/v6/profile/profile_summary.json}"
OUTPUT_ROOT="${OUTPUT_ROOT:-output/snapshot_npr/run-x-b01/v7}"
OUTPUT_DIR="${OUTPUT_DIR:-${OUTPUT_ROOT}/pipeline_profile}"
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
# An S-stage pipeline needs at least S in-flight sequences before every device
# can be busy at once, so the default depth ladder follows the visible GPU count:
# r158's 3-way split is not exercised by a 2-GPU ladder that skips depth 3.
GPU_COUNT="$(awk -F, '{print NF}' <<< "${CUDA_DEVICE}")"
if [[ -z "${DEPTHS:-}" ]]; then
  case "${GPU_COUNT}" in
    3) DEPTHS="1,2,3,6,12" ;;
    2) DEPTHS="1,2,4,8" ;;
    *) DEPTHS="1,2,4,8" ;;
  esac
fi
RANK_BACKEND="${RANK_BACKEND:-auto}"
RANK_TILE_TOKENS="${RANK_TILE_TOKENS:-32}"
MAX_BATCH_TOKENS="${MAX_BATCH_TOKENS:-2048}"
USE_CACHE="${USE_CACHE:-false}"
MINIMUM_USEFUL_SPEEDUP="${MINIMUM_USEFUL_SPEEDUP:-1.15}"
PREFERRED_PRODUCTION_DAYS="${PREFERRED_PRODUCTION_DAYS:-5}"
MAX_PRODUCTION_DAYS="${MAX_PRODUCTION_DAYS:-7}"
TWO_GPU_MAX_MEMORY="${TWO_GPU_MAX_MEMORY:-42GiB}"
PER_GPU_MAX_MEMORY="${PER_GPU_MAX_MEMORY:-44GiB}"
CPU_MAX_MEMORY="${CPU_MAX_MEMORY:-128GiB}"
ALLOW_UNSUPPORTED_GPU_TOPOLOGY="${ALLOW_UNSUPPORTED_GPU_TOPOLOGY:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-0}"
TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-0}"
export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"
export TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE TRANSFORMERS_OFFLINE

# GPT-OSS MXFP4 loads Hugging Face kernels, which performs an online publisher
# trust check even with cached weights, so offline mode must stay off. The model
# is still reproducible: the revision is pinned and nothing is installed here.
case "${HF_HUB_OFFLINE,,}" in
  1|true|yes|on)
    echo "ERROR: HF_HUB_OFFLINE=${HF_HUB_OFFLINE} blocks GPT-OSS kernel trust verification. Set HF_HUB_OFFLINE=0." >&2
    exit 2
    ;;
esac
case "${TRANSFORMERS_OFFLINE,,}" in
  1|true|yes|on)
    echo "ERROR: TRANSFORMERS_OFFLINE=${TRANSFORMERS_OFFLINE} is not supported for B01 GPT-OSS runs. Set TRANSFORMERS_OFFLINE=0." >&2
    exit 2
    ;;
esac
TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/${RUN_PREFIX}-v7-${MODE}-${SYSTEM_LABEL}-${TIMESTAMP}.log}"
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
require_file "${PY_SCRIPT}" "B01-v7 Python"
require_file "${V6_SCRIPT}" "B01-v6 engine (frozen reference)"
require_file "${A02_SCRIPT}" "frozen A02 helper"
require_file "${RANK_SCRIPT}" "original rank implementation"
require_file "${A09_ROOT}/plan/summary.json" "A09 summary"
require_file "${A09_ROOT}/plan/unique_primary_units.csv" "A09 unit plan"
require_file "${REFERENCE_DB}" "v2 smoke checkpoint (read-only)"
if [[ "${RANK_BACKEND}" == "auto" ]]; then
  require_file "${V6_PROFILE_SUMMARY}" "v6 profile summary (supplies the exact tie rule)"
fi
START_EPOCH="$(date +%s)"
START_TEXT="$(date)"
finish() {
    local exit_code=$?
    local end_epoch elapsed
    end_epoch="$(date +%s)"
    elapsed=$((end_epoch - START_EPOCH))
    echo
    echo "============================================================================"
    echo "run-x-b01-v7 execution summary"
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
V6_SHA="$(sha256sum "${V6_SCRIPT}" | awk '{print $1}')"
A02_SHA="$(sha256sum "${A02_SCRIPT}" | awk '{print $1}')"
RANK_SHA="$(sha256sum "${RANK_SCRIPT}" | awk '{print $1}')"
echo "============================================================================"
echo "run-x-b01-v7: deferred-synchronization pipelining probe (B=1 preserved)"
echo "Mode:                            ${MODE}"
echo "Project root:                    ${PROJECT_ROOT}"
echo "Python:                          ${PYTHON_RESOLVED} (${PYTHON_VERSION})"
echo "Active conda env:                ${CONDA_DEFAULT_ENV:-<none>}"
echo "v7 script SHA256:                ${PY_SHA}"
echo "v6 engine SHA256:                ${V6_SHA}"
echo "v6 engine SHA256 expected:       ${EXPECTED_V6_SHA256:-<unpinned>}"
echo "Frozen A02 SHA256:               ${A02_SHA}"
echo "Original rank SHA256:            ${RANK_SHA}"
echo "Scoring model:                   ${SCORING_MODEL}"
echo "Pinned model revision:           ${MODEL_REVISION}"
echo "CUDA_VISIBLE_DEVICES:            ${CUDA_VISIBLE_DEVICES}"
echo "System label:                    ${SYSTEM_LABEL}"
echo "v2 reference (READ ONLY):        ${REFERENCE_DB}"
echo "v6 profile (READ ONLY):          ${V6_PROFILE_SUMMARY}"
echo "Output directory:                ${OUTPUT_DIR}"
echo "Scope / shards:                  ${SCOPE} / ${SHARD_IDS}"
echo "Execution:                       B=1 always; pipeline depths=${DEPTHS}; backend=${RANK_BACKEND}"
echo "Visible GPUs / depth ladder:     ${GPU_COUNT} (a depth below the stage count cannot fill the pipeline)"
echo "Profile windows:                 ${PROFILE_WINDOWS} (each = 1 original + 50 perturbations)"
echo "Equivalence bar:                 EXACT vs v6 on all 51 components (no tolerance)"
echo "Useful-speedup floor:            ${MINIMUM_USEFUL_SPEEDUP}x"
echo "Conference runtime target:       preferred <=${PREFERRED_PRODUCTION_DAYS} days; hard <=${MAX_PRODUCTION_DAYS} days"
echo "Classification / thresholding:   disabled"
echo "Production approval:             not granted by this stage"
echo "HF_HUB_OFFLINE / TRANSFORMERS:    ${HF_HUB_OFFLINE} / ${TRANSFORMERS_OFFLINE}"
echo "Log file:                        ${LOG_FILE}"
nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv,noheader || true
echo "============================================================================"
if [[ "${RUN_SELF_TEST}" == "1" ]]; then
  "${PYTHON_BIN}" "${PY_SCRIPT}" --project-root "${PROJECT_ROOT}" --v6-script "${V6_SCRIPT}" \
    --expected-v6-sha256 "${EXPECTED_V6_SHA256}" --output-dir "/tmp/run-x-b01-v7-self-test" --self-test-only
fi
ARGS=(
  --mode "${MODE}" --project-root "${PROJECT_ROOT}"
  --v6-script "${V6_SCRIPT}" --expected-v6-sha256 "${EXPECTED_V6_SHA256}"
  --v6-profile-summary "${V6_PROFILE_SUMMARY}"
  --a02-script "${A02_SCRIPT}" --rank-script "${RANK_SCRIPT}" --a09-root "${A09_ROOT}"
  --reference-db "${REFERENCE_DB}" --output-dir "${OUTPUT_DIR}"
  --scope "${SCOPE}" --shard-ids "${SHARD_IDS}"
  --scoring-model "${SCORING_MODEL}" --model-cache-dir "${MODEL_CACHE_DIR}"
  --model-revision "${MODEL_REVISION}" --expected-model-revision "${EXPECTED_MODEL_REVISION}"
  --system-label "${SYSTEM_LABEL}" --two-gpu-max-memory "${TWO_GPU_MAX_MEMORY}"
  --per-gpu-max-memory "${PER_GPU_MAX_MEMORY}" --cpu-max-memory "${CPU_MAX_MEMORY}"
  --profile-windows "${PROFILE_WINDOWS}" --depths "${DEPTHS}"
  --rank-backend "${RANK_BACKEND}" --rank-tile-tokens "${RANK_TILE_TOKENS}"
  --max-batch-tokens "${MAX_BATCH_TOKENS}" --use-cache "${USE_CACHE}"
  --minimum-useful-speedup "${MINIMUM_USEFUL_SPEEDUP}"
  --preferred-production-days "${PREFERRED_PRODUCTION_DAYS}"
  --max-production-days "${MAX_PRODUCTION_DAYS}"
)
[[ "${ALLOW_UNSUPPORTED_GPU_TOPOLOGY}" != "1" ]] || ARGS+=(--allow-unsupported-gpu-topology)
"${PYTHON_BIN}" "${PY_SCRIPT}" "${ARGS[@]}"
require_file "${OUTPUT_DIR}/summary.json" "v7 stage summary"
"${PYTHON_BIN}" - "${OUTPUT_DIR}/summary.json" <<'PYVERIFY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as stream:
    summary = json.load(stream)
print("Stage status:", summary.get("status"))
print("Production:", "APPROVED" if summary.get("production_ready") else "HOLD")
print("Baseline (v6 engine) days:", summary.get("baseline_projected_days"))
print("Recommended depth:", summary.get("recommended_pipeline_depth"))
print("Recommended speedup:", summary.get("recommended_speedup"))
print("Recommended projected days:", summary.get("recommended_projected_days"))
print("Pipeline stages:", summary.get("pipeline_stages"),
      "devices:", summary.get("pipeline_stage_devices"))
print("Next step:", summary.get("next_step"))
print("Note:", summary.get("note"))
for row in summary.get("candidates", []):
    print(f"  depth={row.get('pipeline_depth')} status={row.get('status')} "
          f"fills_pipeline={row.get('fills_pipeline')} "
          f"rate={row.get('windows_per_second')} speedup={row.get('speedup')} "
          f"days={row.get('projected_days')} peak_gib={row.get('peak_allocated_gib_per_device')}")
if summary.get("status") != "PASS":
    raise SystemExit(1)
PYVERIFY
