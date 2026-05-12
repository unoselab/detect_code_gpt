#!/bin/bash
# Run this script from inside a tmux session (e.g., `tmux attach -t codellama0` first)
# Detection Phase — DetectCodeGPT scoring on CodeLlama-7B + CodeSearchNet + T=0.2

set -euo pipefail  # exit on error, undefined var, or failed pipe

cd ~/project-workspace/detect_code_gpt

mkdir -p logs

cd code-detection

# Launch with explicit args — no more hardcoded config!
python main.py \
    --dataset CodeSearchNet \
    --dataset_key CodeLlama-7b-hf-500-tp0.2 \
    --data_path ~/project-workspace/detect_code_gpt/output/CodeSearchNet/CodeLlama-7b-hf-500-tp0.2/outputs.txt \
    --base_model_name codellama/CodeLlama-7b-hf \
    --mask_filling_model_name Salesforce/codet5p-770m \
    --n_samples 500 \
    --n_perturbation_list 50 \
    --pct_words_masked 0.5 \
    --pct_identifiers_masked 0.75 \
    --span_length 2 \
    --batch_size 50 \
    --chunk_size 10 \
    --baselines "LRR,DetectGPT,NPR" \
    --perturb_type "random-insert-space+newline" \
    --output_name codellama_csn_t02_first_run \
    2>&1 | tee ../logs/detection_codellama_csn_t02.log