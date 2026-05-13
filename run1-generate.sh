#!/bin/bash
# Run this script from inside a tmux session
# Generation Phase — CodeLlama-7B on CodeSearchNet at T=0.2
# Scaled run: 2000 samples (target ~500 after 26% filter pass rate)

set -euo pipefail

cd ~/project-workspace/detect_code_gpt

mkdir -p logs

export CUDA_VISIBLE_DEVICES=0

python code-generation/generate.py \
    --path data/CodeSearchNet \
    --model_name codellama/CodeLlama-7b-hf \
    --max_num 2000 \
    --temperature 0.2 \
    --max_length 128 \
    --batch_size 1 \
    2>&1 | tee logs/generate_codellama_csn_t02_n2000.log