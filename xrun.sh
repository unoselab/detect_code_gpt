# Confirm that the incorrect run has stopped.
pgrep -af 'main_mixedcode_benchmark_overlap.py' || true

# Check whether the interrupted run created final outputs.
ls -lh \
  output/commit_function/run-1c0a/mixedcode-overlap-v1/*mixedcode_codellama-7b_50files_overlap-v1* \
  2>/dev/null || true

# Run the correct matched-model CL-7B benchmark.
CUDA_DEVICE=0 GEN_MODEL=codellama-7b BASE_MODEL_NAME=codellama/CodeLlama-7b-hf OUTPUT_NAME=mixedcode_codellama-7b_50files_overlap-v1 bash proc_sh/run-1c0a-score-mixedcode-overlap-benchmark.sh