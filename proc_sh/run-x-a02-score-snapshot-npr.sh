#!/usr/bin/env bash
# Score A01 snapshot code units with DetectCodeGPT-style continuous NPR.
#
# Workspace:
#   /home/user1-system12/project-workspace/detect_code_gpt
#
# Versioned delivery file:
#   proc_sh/run-x-a02-score-snapshot-npr-v3.sh
#
# Canonical server path after removing the delivery version suffix:
#   proc_sh/run-x-a02-score-snapshot-npr.sh
#
# Canonical Python implementation after removing the delivery version suffix:
#   code-detection/score_snapshot_npr.py
#
# This wrapper is standalone. Its execution, dependency checking, CUDA
# validation, logging, self-test, resume validation, and output verification
# structure is adapted from the existing run-1c NPR wrapper, but it does not
# call or depend on that wrapper.
#
# Main input from A01:
#   output/snapshot_npr/run-x-a01/python_code_unit_manifest.csv
#   output/snapshot_npr/run-x-a01/code_units/<sha-prefix>/<sha256>.txt
#
# Main outputs:
#   output/snapshot_npr/run-x-a02/
#     python_unique_code_unit_npr_scores.csv
#     python_code_unit_npr_scores.csv
#     python_window_npr_scores.csv
#     python_snapshot_npr_failures.csv
#     cache/
#     qc/python_snapshot_npr_artifact_errors.csv
#     qc/python_snapshot_npr_checks.csv
#     qc/python_snapshot_npr_summary.json
#     qc/python_snapshot_npr_metadata.json
#     qc/python_snapshot_npr_reproducibility_checks.csv
#     qc/python_snapshot_npr_run_history.jsonl
#     qc/python_snapshot_npr_resume_check.json
#
# Methodology:
#   - 128 space-by-token windows based on text.split(" ").
#   - Final short tail is shifted backward into a full overlap window.
#   - No LLM-token truncation is added by this wrapper or Python program.
#   - LLM token counts are diagnostic only.
#   - NPR remains continuous; no AGC/HWC classification is performed.
#
# Optional environment variables:
#   PROJECT_ROOT, PYTHON_BIN, PY_SCRIPT, RUN_A01_DIR,
#   INPUT_CODE_UNIT_MANIFEST, ARTIFACT_BASE, OUTPUT_DIR, QC_DIR, CACHE_DIR,
#   LOG_DIR, CUDA_DEVICE, CUDA_VISIBLE_DEVICES, MODEL_CACHE_DIR,
#   SCORING_MODEL, WINDOW_SIZE, PERTURBATIONS_PER_WINDOW, PERTURBATION_TYPE,
#   RANDOM_SEED, PCT_WORDS_MASKED, SPAN_LENGTH, PERTURBATION_CHUNK_SIZE,
#   N_PERTURBATION_ROUNDS, REPRODUCIBILITY_CHECK_UNITS,
#   REPRODUCIBILITY_TOLERANCE, PROGRESS_EVERY_UNITS,
#   OVERWRITE_OUTPUT, CLEAR_CACHE, RUN_SELF_TEST, RUN_RESUME_CHECK,
#   REQUIRE_ALL_COMPLETED, ALLOW_CPU, MOCK_SCORING.
#
# Python policy:
#   - Run this A02 wrapper with Python 3.11.x in the detectcodegpt conda env.
#   - Python 3.12 is reserved for AST-parsing source-preparation stages.
#
# Typical server run:
#   OVERWRITE_OUTPUT=1 CUDA_DEVICE=0 bash proc_sh/run-x-a02-score-snapshot-npr.sh
#
# Non-GPU structural integration test:
#   MOCK_SCORING=1 OVERWRITE_OUTPUT=1 bash proc_sh/run-x-a02-score-snapshot-npr.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${PROJECT_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PY_SCRIPT="${PY_SCRIPT:-code-detection/score_snapshot_npr.py}"

RUN_A01_DIR="${RUN_A01_DIR:-output/snapshot_npr/run-x-a01}"
INPUT_CODE_UNIT_MANIFEST="${INPUT_CODE_UNIT_MANIFEST:-${RUN_A01_DIR}/python_code_unit_manifest.csv}"
ARTIFACT_BASE="${ARTIFACT_BASE:-${RUN_A01_DIR}}"

OUTPUT_DIR="${OUTPUT_DIR:-output/snapshot_npr/run-x-a02}"
QC_DIR="${QC_DIR:-${OUTPUT_DIR}/qc}"
CACHE_DIR="${CACHE_DIR:-${OUTPUT_DIR}/cache}"
LOG_DIR="${LOG_DIR:-logs/run-x-a02}"
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-${HOME}/.cache/huggingface/hub}"

SCORING_MODEL="${SCORING_MODEL:-bigcode/starcoder2-7b}"
WINDOW_SIZE="${WINDOW_SIZE:-128}"
PERTURBATIONS_PER_WINDOW="${PERTURBATIONS_PER_WINDOW:-50}"
PERTURBATION_TYPE="${PERTURBATION_TYPE:-random-insert-space+newline}"
RANDOM_SEED="${RANDOM_SEED:-20260723}"
PCT_WORDS_MASKED="${PCT_WORDS_MASKED:-0.5}"
SPAN_LENGTH="${SPAN_LENGTH:-2}"
PERTURBATION_CHUNK_SIZE="${PERTURBATION_CHUNK_SIZE:-10}"
N_PERTURBATION_ROUNDS="${N_PERTURBATION_ROUNDS:-1}"
REPRODUCIBILITY_CHECK_UNITS="${REPRODUCIBILITY_CHECK_UNITS:-1}"
REPRODUCIBILITY_TOLERANCE="${REPRODUCIBILITY_TOLERANCE:-1e-12}"
PROGRESS_EVERY_UNITS="${PROGRESS_EVERY_UNITS:-5}"

CUDA_DEVICE="${CUDA_DEVICE:-0}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-${CUDA_DEVICE}}"
export TOKENIZERS_PARALLELISM="false"

OVERWRITE_OUTPUT="${OVERWRITE_OUTPUT:-0}"
CLEAR_CACHE="${CLEAR_CACHE:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-1}"
RUN_RESUME_CHECK="${RUN_RESUME_CHECK:-1}"
REQUIRE_ALL_COMPLETED="${REQUIRE_ALL_COMPLETED:-0}"
ALLOW_CPU="${ALLOW_CPU:-0}"
MOCK_SCORING="${MOCK_SCORING:-0}"

TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/run-x-a02-v3-score-snapshot-npr-${TIMESTAMP}.log}"

UNIQUE_SCORE_OUTPUT="${OUTPUT_DIR}/python_unique_code_unit_npr_scores.csv"
OCCURRENCE_SCORE_OUTPUT="${OUTPUT_DIR}/python_code_unit_npr_scores.csv"
WINDOW_SCORE_OUTPUT="${OUTPUT_DIR}/python_window_npr_scores.csv"
FAILURE_OUTPUT="${OUTPUT_DIR}/python_snapshot_npr_failures.csv"
ARTIFACT_ERROR_OUTPUT="${QC_DIR}/python_snapshot_npr_artifact_errors.csv"
CHECK_OUTPUT="${QC_DIR}/python_snapshot_npr_checks.csv"
SUMMARY_OUTPUT="${QC_DIR}/python_snapshot_npr_summary.json"
METADATA_OUTPUT="${QC_DIR}/python_snapshot_npr_metadata.json"
REPRO_OUTPUT="${QC_DIR}/python_snapshot_npr_reproducibility_checks.csv"
RUN_HISTORY_OUTPUT="${QC_DIR}/python_snapshot_npr_run_history.jsonl"
RESUME_CHECK_OUTPUT="${QC_DIR}/python_snapshot_npr_resume_check.json"

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

require_file "${PY_SCRIPT}" "run-x-a02 Python script"
require_file "${INPUT_CODE_UNIT_MANIFEST}" "A01 code-unit manifest"

read -r PYTHON_MAJOR PYTHON_MINOR PYTHON_MICRO < <(
    "${PYTHON_BIN}" -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)'
)
PYTHON_VERSION="${PYTHON_MAJOR}.${PYTHON_MINOR}.${PYTHON_MICRO}"
# Runtime policy for A02:
# - A01/source-AST parsing uses Python 3.12.
# - A02 NPR scoring runs inside the detectcodegpt conda environment, whose
#   required detector/model dependencies are installed for Python 3.11.
if (( PYTHON_MAJOR != 3 || PYTHON_MINOR != 11 )); then
    echo "ERROR: run-x-a02 requires Python 3.11.x from the detectcodegpt conda environment; found ${PYTHON_VERSION}." >&2
    echo "ERROR: Python 3.12 is required only for source-snippet AST parsing stages such as run-x-a01." >&2
    exit 2
fi

PYTHON_RESOLVED="$("${PYTHON_BIN}" -c 'import sys; print(sys.executable)')"
mkdir -p "${LOG_DIR}"
START_EPOCH="$(date +%s)"
START_TEXT="$(date)"
RESUME_TMP_ROOT=""

finish() {
    local exit_code=$?
    if [[ -n "${RESUME_TMP_ROOT}" ]] && [[ -d "${RESUME_TMP_ROOT}" ]]; then
        rm -rf "${RESUME_TMP_ROOT}"
    fi
    local end_epoch elapsed hours minutes seconds
    end_epoch="$(date +%s)"
    elapsed=$((end_epoch - START_EPOCH))
    hours=$((elapsed / 3600))
    minutes=$(((elapsed % 3600) / 60))
    seconds=$((elapsed % 60))

    echo
    echo "============================================================================"
    echo "run-x-a02 execution summary"
    echo "Started:                    ${START_TEXT}"
    echo "Completed:                  $(date)"
    printf 'Elapsed:                    %02d:%02d:%02d\n' "${hours}" "${minutes}" "${seconds}"
    echo "Exit code:                  ${exit_code}"
    echo "Python path:                ${PYTHON_RESOLVED}"
    echo "Python version:             ${PYTHON_VERSION}"
    echo "Python script:              ${PY_SCRIPT}"
    echo "A01 code-unit manifest:     ${INPUT_CODE_UNIT_MANIFEST}"
    echo "Artifact base:              ${ARTIFACT_BASE}"
    echo "Output directory:           ${OUTPUT_DIR}"
    echo "Cache directory:            ${CACHE_DIR}"
    echo "QC directory:               ${QC_DIR}"
    echo "Log file:                   ${LOG_FILE}"
    echo "============================================================================"
    exit "${exit_code}"
}

trap finish EXIT
exec > >(tee -a "${LOG_FILE}") 2>&1

PY_SCRIPT_SHA="$(sha256_file "${PY_SCRIPT}")"
INPUT_MANIFEST_SHA="$(sha256_file "${INPUT_CODE_UNIT_MANIFEST}")"

DEPENDENCY_INFO="$("${PYTHON_BIN}" - <<'PY'
import json
modules = {}
for name in ("numpy", "pandas", "scipy", "torch", "transformers", "loguru"):
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
}, sort_keys=True))
PY
)"

read -r CUDA_AVAILABLE GPU_MEMORY_BYTES < <(
    "${PYTHON_BIN}" - "${DEPENDENCY_INFO}" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
print(int(payload["cuda_available"]), int(payload["gpu_total_memory_bytes"]))
PY
)
GPU_NAME_DISPLAY="$("${PYTHON_BIN}" - "${DEPENDENCY_INFO}" <<'PY'
import json
import sys
print(json.loads(sys.argv[1])["gpu_name"])
PY
)"

if [[ "${MOCK_SCORING}" != "1" ]]; then
    "${PYTHON_BIN}" - "${DEPENDENCY_INFO}" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
errors = [f"{name}={value}" for name, value in payload["modules"].items() if str(value).startswith("ERROR:")]
if errors:
    raise SystemExit("Missing NPR dependencies: " + "; ".join(errors))
PY
    if [[ "${CUDA_AVAILABLE}" != "1" ]] && [[ "${ALLOW_CPU}" != "1" ]]; then
        echo "ERROR: CUDA is not available in ${PYTHON_RESOLVED}." >&2
        echo "Activate the detectcodegpt environment and expose a GPU, or set ALLOW_CPU=1." >&2
        exit 2
    fi
fi

cat <<INFO
============================================================================
run-x-a02: snapshot-level continuous NPR scoring
Started:                         ${START_TEXT}
Workspace:                       ${PROJECT_ROOT}
Active conda env:                ${CONDA_DEFAULT_ENV:-<none>}
Python path:                     ${PYTHON_RESOLVED}
Python version:                  ${PYTHON_VERSION}
Python script:                   ${PY_SCRIPT}
Python script SHA:               ${PY_SCRIPT_SHA}
A01 code-unit manifest:          ${INPUT_CODE_UNIT_MANIFEST}
A01 manifest SHA:                ${INPUT_MANIFEST_SHA}
Artifact base:                   ${ARTIFACT_BASE}
Scoring model:                   ${SCORING_MODEL}
Window size (space-by tokens):   ${WINDOW_SIZE}
Perturbations per window:        ${PERTURBATIONS_PER_WINDOW}
Perturbation type:               ${PERTURBATION_TYPE}
Random seed:                     ${RANDOM_SEED}
LLM-token truncation:            none added by A02
Classification:                  disabled
Dependency versions JSON:          ${DEPENDENCY_INFO}
CUDA_VISIBLE_DEVICES:            ${CUDA_VISIBLE_DEVICES}
CUDA available:                  ${CUDA_AVAILABLE}
GPU name:                        ${GPU_NAME_DISPLAY}
GPU total memory bytes:          ${GPU_MEMORY_BYTES}
Model cache:                     ${MODEL_CACHE_DIR}
Output directory:                ${OUTPUT_DIR}
Cache directory:                 ${CACHE_DIR}
QC directory:                    ${QC_DIR}
Reproducibility units:           ${REPRODUCIBILITY_CHECK_UNITS}
Overwrite output:                ${OVERWRITE_OUTPUT}
Clear cache:                     ${CLEAR_CACHE}
Run self-test:                   ${RUN_SELF_TEST}
Run resume check:                ${RUN_RESUME_CHECK}
Require all completed:           ${REQUIRE_ALL_COMPLETED}
Mock scoring:                    ${MOCK_SCORING}
Log file:                        ${LOG_FILE}
============================================================================
INFO

"${PYTHON_BIN}" -m py_compile "${PY_SCRIPT}"
if [[ "${RUN_SELF_TEST}" == "1" ]]; then
    "${PYTHON_BIN}" "${PY_SCRIPT}" --self-test
fi

COMMAND=(
    "${PYTHON_BIN}" "${PY_SCRIPT}"
    --project-root "${PROJECT_ROOT}"
    --input-code-unit-manifest "${INPUT_CODE_UNIT_MANIFEST}"
    --artifact-base "${ARTIFACT_BASE}"
    --output-dir "${OUTPUT_DIR}"
    --qc-dir "${QC_DIR}"
    --cache-dir "${CACHE_DIR}"
    --model-cache-dir "${MODEL_CACHE_DIR}"
    --scoring-model "${SCORING_MODEL}"
    --window-size "${WINDOW_SIZE}"
    --perturbations-per-window "${PERTURBATIONS_PER_WINDOW}"
    --perturbation-type "${PERTURBATION_TYPE}"
    --random-seed "${RANDOM_SEED}"
    --pct-words-masked "${PCT_WORDS_MASKED}"
    --span-length "${SPAN_LENGTH}"
    --perturbation-chunk-size "${PERTURBATION_CHUNK_SIZE}"
    --n-perturbation-rounds "${N_PERTURBATION_ROUNDS}"
    --reproducibility-check-units "${REPRODUCIBILITY_CHECK_UNITS}"
    --reproducibility-tolerance "${REPRODUCIBILITY_TOLERANCE}"
    --progress-every-units "${PROGRESS_EVERY_UNITS}"
)

if [[ "${ALLOW_CPU}" == "1" ]] && [[ "${CUDA_AVAILABLE}" != "1" ]]; then
    COMMAND+=(--device cpu)
else
    COMMAND+=(--device cuda)
fi
if [[ "${OVERWRITE_OUTPUT}" == "1" ]]; then
    COMMAND+=(--overwrite-output)
fi
if [[ "${CLEAR_CACHE}" == "1" ]]; then
    COMMAND+=(--clear-cache)
fi
if [[ "${REQUIRE_ALL_COMPLETED}" == "1" ]]; then
    COMMAND+=(--require-all-completed)
fi
if [[ "${MOCK_SCORING}" == "1" ]]; then
    COMMAND+=(--mock-scoring)
fi

"${COMMAND[@]}"

for expected_file in \
    "${UNIQUE_SCORE_OUTPUT}" \
    "${OCCURRENCE_SCORE_OUTPUT}" \
    "${WINDOW_SCORE_OUTPUT}" \
    "${FAILURE_OUTPUT}" \
    "${ARTIFACT_ERROR_OUTPUT}" \
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

read -r STATUS FAILED_CHECKS PRIMARY_OCCURRENCES UNIQUE_UNITS SUCCESSFUL FAILED WINDOWS INVALID_WINDOWS PARTIAL_UNITS SCORED_THIS_RUN REUSED_THIS_RUN MODEL_LOADED REPRO_FAILURES < <(
    "${PYTHON_BIN}" - "${SUMMARY_OUTPUT}" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as stream:
    summary = json.load(stream)
print(
    summary["status"],
    summary["failed_checks"],
    summary["primary_code_unit_occurrences"],
    summary["unique_primary_code_units"],
    summary["successful_unique_code_units"],
    summary["failed_unique_code_units"],
    summary["window_score_rows"],
    summary["invalid_npr_windows"],
    summary["partial_code_unit_scores"],
    summary["newly_scored_unique_code_units"],
    summary["cache_reused_unique_code_units"],
    int(summary["model_loaded_this_run"]),
    summary["reproducibility_failures"],
)
PY
)

if [[ "${STATUS}" == "FAIL" ]] || [[ "${FAILED_CHECKS}" != "0" ]] || [[ "${REPRO_FAILURES}" != "0" ]]; then
    echo "ERROR: run-x-a02 QC failed: status=${STATUS}, failed_checks=${FAILED_CHECKS}, repro_failures=${REPRO_FAILURES}" >&2
    exit 4
fi
if [[ "${REQUIRE_ALL_COMPLETED}" == "1" ]] && [[ "${STATUS}" != "PASS" ]]; then
    echo "ERROR: REQUIRE_ALL_COMPLETED=1 but status=${STATUS}." >&2
    exit 4
fi

FIRST_RUN_STATUS="${STATUS}"
FIRST_RUN_SCORED="${SCORED_THIS_RUN}"
FIRST_RUN_REUSED="${REUSED_THIS_RUN}"
FIRST_RUN_MODEL_LOADED="${MODEL_LOADED}"

# Preserve the canonical first-run outputs. Resume/cache validation writes only to
# a temporary output namespace while reusing the canonical cache directory.
# This prevents the fast cache-validation invocation from replacing first-run GPU,
# model-context, runtime, and scored/cached provenance in the canonical artifacts.
CANONICAL_HASH_FILE="$(mktemp "${TMPDIR:-/tmp}/run-x-a02-canonical-hashes.XXXXXX")"
"${PYTHON_BIN}" - "${CANONICAL_HASH_FILE}" \
    "${UNIQUE_SCORE_OUTPUT}" "${OCCURRENCE_SCORE_OUTPUT}" "${WINDOW_SCORE_OUTPUT}" \
    "${FAILURE_OUTPUT}" "${ARTIFACT_ERROR_OUTPUT}" "${CHECK_OUTPUT}" \
    "${SUMMARY_OUTPUT}" "${METADATA_OUTPUT}" "${REPRO_OUTPUT}" "${RUN_HISTORY_OUTPUT}" <<'PYHASH'
import hashlib
import json
import pathlib
import sys


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


output = pathlib.Path(sys.argv[1])
paths = [pathlib.Path(value) for value in sys.argv[2:]]
payload = {str(path): sha256_file(path) for path in paths}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PYHASH

if [[ "${RUN_RESUME_CHECK}" == "1" ]] && [[ "${STATUS}" == "PASS" ]]; then
    RESUME_TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/run-x-a02-resume-check.XXXXXX")"
    RESUME_OUTPUT_DIR="${RESUME_TMP_ROOT}/output"
    RESUME_QC_DIR="${RESUME_OUTPUT_DIR}/qc"

    RESUME_COMMAND=(
        "${PYTHON_BIN}" "${PY_SCRIPT}"
        --project-root "${PROJECT_ROOT}"
        --input-code-unit-manifest "${INPUT_CODE_UNIT_MANIFEST}"
        --artifact-base "${ARTIFACT_BASE}"
        --output-dir "${RESUME_OUTPUT_DIR}"
        --qc-dir "${RESUME_QC_DIR}"
        --cache-dir "${CACHE_DIR}"
        --model-cache-dir "${MODEL_CACHE_DIR}"
        --scoring-model "${SCORING_MODEL}"
        --window-size "${WINDOW_SIZE}"
        --perturbations-per-window "${PERTURBATIONS_PER_WINDOW}"
        --perturbation-type "${PERTURBATION_TYPE}"
        --random-seed "${RANDOM_SEED}"
        --pct-words-masked "${PCT_WORDS_MASKED}"
        --span-length "${SPAN_LENGTH}"
        --perturbation-chunk-size "${PERTURBATION_CHUNK_SIZE}"
        --n-perturbation-rounds "${N_PERTURBATION_ROUNDS}"
        --reproducibility-check-units "0"
        --progress-every-units "${PROGRESS_EVERY_UNITS}"
    )
    if [[ "${ALLOW_CPU}" == "1" ]] && [[ "${CUDA_AVAILABLE}" != "1" ]]; then
        RESUME_COMMAND+=(--device cpu)
    else
        RESUME_COMMAND+=(--device cuda)
    fi
    if [[ "${MOCK_SCORING}" == "1" ]]; then
        RESUME_COMMAND+=(--mock-scoring)
    fi

    "${RESUME_COMMAND[@]}"

    RESUME_SUMMARY_OUTPUT="${RESUME_QC_DIR}/python_snapshot_npr_summary.json"
    read -r RESUME_STATUS RESUME_FAILED_CHECKS RESUME_SUCCESSFUL RESUME_SCORED RESUME_REUSED RESUME_MODEL_LOADED < <(
        "${PYTHON_BIN}" - "${RESUME_SUMMARY_OUTPUT}" <<'PYRESUME'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as stream:
    summary = json.load(stream)
print(
    summary["status"],
    summary["failed_checks"],
    summary["successful_unique_code_units"],
    summary["newly_scored_unique_code_units"],
    summary["cache_reused_unique_code_units"],
    int(summary["model_loaded_this_run"]),
)
PYRESUME
    )

    if [[ "${RESUME_STATUS}" != "PASS" ]] || [[ "${RESUME_FAILED_CHECKS}" != "0" ]] || \
       [[ "${RESUME_SUCCESSFUL}" != "${UNIQUE_UNITS}" ]] || [[ "${RESUME_SCORED}" != "0" ]] || \
       [[ "${RESUME_REUSED}" != "${UNIQUE_UNITS}" ]] || [[ "${RESUME_MODEL_LOADED}" != "0" ]]; then
        echo "ERROR: run-x-a02 resume validation failed." >&2
        echo "status=${RESUME_STATUS} failed_checks=${RESUME_FAILED_CHECKS} successful=${RESUME_SUCCESSFUL} scored=${RESUME_SCORED} reused=${RESUME_REUSED} model_loaded=${RESUME_MODEL_LOADED}" >&2
        exit 5
    fi

    "${PYTHON_BIN}" - "${CANONICAL_HASH_FILE}" "${RESUME_CHECK_OUTPUT}" \
        "${UNIQUE_SCORE_OUTPUT}" "${OCCURRENCE_SCORE_OUTPUT}" "${WINDOW_SCORE_OUTPUT}" \
        "${FAILURE_OUTPUT}" "${ARTIFACT_ERROR_OUTPUT}" "${CHECK_OUTPUT}" \
        "${SUMMARY_OUTPUT}" "${METADATA_OUTPUT}" "${REPRO_OUTPUT}" "${RUN_HISTORY_OUTPUT}" \
        "${RESUME_STATUS}" "${RESUME_FAILED_CHECKS}" "${RESUME_SUCCESSFUL}" \
        "${RESUME_SCORED}" "${RESUME_REUSED}" "${RESUME_MODEL_LOADED}" <<'PYVERIFY'
import datetime
import hashlib
import json
import pathlib
import sys


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


baseline_path = pathlib.Path(sys.argv[1])
resume_output_path = pathlib.Path(sys.argv[2])
paths = [pathlib.Path(value) for value in sys.argv[3:13]]
status, failed_checks, successful, scored, reused, model_loaded = sys.argv[13:19]
baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
after = {str(path): sha256_file(path) for path in paths}
unchanged = baseline == after
payload = {
    "status": "PASS" if unchanged else "FAIL",
    "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "resume_status": status,
    "resume_failed_checks": int(failed_checks),
    "resume_successful_unique_code_units": int(successful),
    "resume_newly_scored_unique_code_units": int(scored),
    "resume_cache_reused_unique_code_units": int(reused),
    "resume_model_loaded_this_run": bool(int(model_loaded)),
    "canonical_outputs_unchanged": unchanged,
    "canonical_hashes_before": baseline,
    "canonical_hashes_after": after,
    "note": "Resume validation used a temporary output namespace and the canonical cache directory.",
}
resume_output_path.parent.mkdir(parents=True, exist_ok=True)
resume_output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if not unchanged:
    raise SystemExit("Canonical A02 outputs changed during resume validation.")
PYVERIFY
else
    "${PYTHON_BIN}" - "${RESUME_CHECK_OUTPUT}" "${RUN_RESUME_CHECK}" "${STATUS}" <<'PYSKIP'
import datetime
import json
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
payload = {
    "status": "SKIPPED",
    "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "run_resume_check": bool(int(sys.argv[2])),
    "first_run_status": sys.argv[3],
    "canonical_outputs_unchanged": True,
}
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PYSKIP
fi
rm -f "${CANONICAL_HASH_FILE}"
if [[ -n "${RESUME_TMP_ROOT}" ]] && [[ -d "${RESUME_TMP_ROOT}" ]]; then
    rm -rf "${RESUME_TMP_ROOT}"
    RESUME_TMP_ROOT=""
fi

if [[ ! -f "${RESUME_CHECK_OUTPUT}" ]]; then
    echo "ERROR: Missing resume-check QC output: ${RESUME_CHECK_OUTPUT}" >&2
    exit 5
fi

UNIQUE_SCORE_ROWS=$(( $(wc -l < "${UNIQUE_SCORE_OUTPUT}") - 1 ))
OCCURRENCE_SCORE_ROWS=$(( $(wc -l < "${OCCURRENCE_SCORE_OUTPUT}") - 1 ))
WINDOW_SCORE_ROWS=$(( $(wc -l < "${WINDOW_SCORE_OUTPUT}") - 1 ))
FAILURE_ROWS=$(( $(wc -l < "${FAILURE_OUTPUT}") - 1 ))

cat <<INFO

============================================================================
run-x-a02 output verification
First-run status:                ${FIRST_RUN_STATUS}
Resume validation QC:            ${RESUME_CHECK_OUTPUT}
Primary code-unit occurrences:   ${PRIMARY_OCCURRENCES}
Unique primary code units:       ${UNIQUE_UNITS}
Successful unique code units:    ${SUCCESSFUL}
Failed unique code units:        ${FAILED}
Window score rows:               ${WINDOWS}
Invalid NPR windows:             ${INVALID_WINDOWS}
Partial code-unit scores:        ${PARTIAL_UNITS}
First invocation scored units:   ${FIRST_RUN_SCORED}
First invocation reused units:   ${FIRST_RUN_REUSED}
First invocation model loaded:   ${FIRST_RUN_MODEL_LOADED}
Unique-score CSV rows:           ${UNIQUE_SCORE_ROWS}
Occurrence-score CSV rows:       ${OCCURRENCE_SCORE_ROWS}
Window-score CSV rows:           ${WINDOW_SCORE_ROWS}
Failure CSV rows:                ${FAILURE_ROWS}
Failed QC checks:                ${FAILED_CHECKS}
Unique scores:                   ${UNIQUE_SCORE_OUTPUT}
Occurrence scores:               ${OCCURRENCE_SCORE_OUTPUT}
Window scores:                   ${WINDOW_SCORE_OUTPUT}
Checks:                          ${CHECK_OUTPUT}
Summary:                         ${SUMMARY_OUTPUT}
Metadata:                        ${METADATA_OUTPUT}
Log file:                        ${LOG_FILE}
============================================================================
INFO
