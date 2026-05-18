python code-detection/plot_threshold_sweep.py \
  --csv logs/benchmark_results_benchmark_level1_codellama-7b-hf.csv \
  --threshold_min 1.0 \
  --threshold_max 2.0 \
  --output_image logs/threshold_sweep_codellama-7b-hf.png

python code-detection/plot_threshold_sweep.py \
  --csv logs/benchmark_results_benchmark_level1_starcoder2-7b.csv \
  --threshold_min 1.0 \
  --threshold_max 2.2 \
  --output_image logs/threshold_sweep_starcoder2-7b.png