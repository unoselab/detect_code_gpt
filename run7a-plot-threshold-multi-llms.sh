python code-detection/plot_threshold_multi_llms.py \
    --csv logs/benchmark_results_benchmark_level1_codellama-7b-hf.csv \
    --csv logs/benchmark_results_benchmark_level1_starcoder2-7b.csv \
    --label "CodeLlama-7B" \
    --label "StarCoder2-7B" \
    --classification_threshold 1.3875 \
    --classification_threshold 1.6470 \
    --truth_ratio 0.5 \
    --high_precision_target 0.80 \
    --n_samples 530 \
    --output_image logs/fig1_threshold_per_llm.png

