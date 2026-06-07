#!/bin/bash
set -euo pipefail
PROJECT_ROOT=~/project-workspace/detect_code_gpt
CUDA_DEVICE=0
DATASET=CodeSearchNet

GEN_MODEL="${GEN_MODEL:-starcoder2-7b}"
GEN_MODEL_HF="${GEN_MODEL_HF:-bigcode/starcoder2-7b}"
WORKSPACE_ROOT=~/project-workspace
ANALYSIS_DIR="${PROJECT_ROOT}/analysis_results"
CSV_ROOT="${WORKSPACE_ROOT}/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet"
CSV_ROOT_SUB="${CSV_ROOT}/${GEN_MODEL}/validsyntax_4500_complexity"
CSV_PATH="${CSV_PATH:-${CSV_ROOT_SUB}/codesearchnet_starcoder2-7b_python_merged_4500.csv}"

TIMESTAMP=$(date +%m-%d_%H:%M)
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/main_adapter_${TIMESTAMP}.log"

echo "=== Detection run configuration ==="
echo "  DATASET:        ${DATASET}"
echo "  LOG_FILE:       ${LOG_FILE}"
echo "  CSV_PATH:       ${CSV_PATH}"
echo "===================================="
echo ""

cd "${PROJECT_ROOT}"
mkdir -p "${LOG_DIR}"
cd "code-detection"

export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"
## full. completed 2026-06-05.
# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name "${GEN_MODEL_HF}" \
#     --output_name "${GEN_MODEL}_4500_refreshed" \
#     2>&1 | tee "${LOG_FILE}"

## NPR and AUROC by code length (weighted_mean)
echo "=== DETECTION ANALYSIS ==="
# echo "StarCoder2-7B"
# echo "===================================="
# echo ""
# python analyze_by_length.py \
#     --cache "${LOG_DIR}/results_cache_main_adapter_starcoder2-7b_4500_refreshed.pkl" \
#     --aggregate weighted_mean

# echo "CodeLlama-7B"
# echo "===================================="
# echo ""
# python analyze_by_length.py \
#     --cache "${LOG_DIR}/results_cache_main_adapter_codellama-7b_4500_refreshed.pkl" \
#     --aggregate weighted_mean

# echo "GPT-OSS-120B"
# echo "===================================="
# echo ""
# python analyze_by_length.py \
#     --cache "${LOG_DIR}/results_cache_main_adapter_gpt-oss_4500_refreshed.pkl" \
#     --aggregate weighted_mean

# echo "StarCoder2-15B"
# echo "===================================="
# echo ""
# python analyze_by_length.py \
#     --cache "${LOG_DIR}/results_cache_main_adapter_starcoder2-15b-instruct-v0.1_4500_refreshed.pkl" \
#     --aggregate weighted_mean

# cd "${PROJECT_ROOT}"
# rm -rf \
#   "${ANALYSIS_DIR}"/cl7b-mean \
#   "${ANALYSIS_DIR}"/sc7b-mean \
#   "${ANALYSIS_DIR}"/cl7b-sc7b-mean \
#   "${ANALYSIS_DIR}"/cl7b-sc7b-go120b-mean

## === ANALYSIS ============================ 
cd "${ANALYSIS_DIR}"

echo "CodeLlama-7B & StarCoder2-7B & StarCoder2-15B & GPT-OSS-120B"
echo "===================================="
echo ""

# python make_paper_artifacts.py \
#     --cache "CodeLlama-7B=${LOG_DIR}/results_cache_main_adapter_codellama-7b_4500_refreshed.pkl" \
#     --aggregate weighted_mean \
#     --out-dir ./cl7b-mean

# python make_paper_artifacts.py \
#     --cache "StarCoder2-7B=${LOG_DIR}/results_cache_main_adapter_starcoder2-7b_4500_refreshed.pkl" \
#     --aggregate weighted_mean \
#     --out-dir ./sc7b-mean

# python make_paper_artifacts.py \
#     --cache "GPT-OSS-120B=${LOG_DIR}/results_cache_main_adapter_gpt-oss_4500_refreshed.pkl" \
#     --aggregate weighted_mean \
#     --out-dir ./go120b-mean

python make_paper_artifacts.py \
    --cache "StarCoder2-15B=${LOG_DIR}/results_cache_main_adapter_starcoder2-15b-instruct-v0.1_4500_refreshed.pkl" \
    --aggregate weighted_mean \
    --out-dir ./sc15b-mean

python make_paper_artifacts.py \
    --cache "CodeLlama-7B=${LOG_DIR}/results_cache_main_adapter_codellama-7b_4500_refreshed.pkl" \
    --cache "StarCoder2-7B=${LOG_DIR}/results_cache_main_adapter_starcoder2-7b_4500_refreshed.pkl" \
    --cache "StarCoder2-15B=${LOG_DIR}/results_cache_main_adapter_starcoder2-15b-instruct-v0.1_4500_refreshed.pkl" \
    --cache "GPT-OSS-120B=${LOG_DIR}/results_cache_main_adapter_gpt-oss_4500_refreshed.pkl" \
    --aggregate weighted_mean \
    --out-dir ./cl7b-sc7b-sc15b-go120b-mean

# check the empty HWC and MGC
# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --count_empty_only    


# Testing --min_chunk_tokens 10
# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name "${GEN_MODEL_HF}" \
#     --output_name "${GEN_MODEL}_4500_n100" \
#     --min_chunk_tokens 10 --limit 100 \
#     2>&1 | tee "${LOG_FILE}"

# # Testing --min_chunk_tokens 5 - ROC AUC of DetectCodeGPT (NPR): 0.5721
# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name "${GEN_MODEL_HF}" \
#     --output_name "${GEN_MODEL}_4500_n100" \
#     --min_chunk_tokens 5 --limit 100 \
#     2>&1 | tee "${LOG_FILE}"

# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name "${GEN_MODEL_HF}" \
#     --output_name "${GEN_MODEL}_4500" \
#     2>&1 | tee "${LOG_FILE}"

# intermediate check: ~100 pairs first (~10 min) to confirm separation holds at scale
# python main_adapter.py \
#     --csv_path "${CSV_PATH}" \
#     --base_model_name bigcode/starcoder2-7b \
#     --output_name starcoder2_4500_n100 \
#     --limit 100 \
#     2>&1 | tee "${LOG_FILE}"
