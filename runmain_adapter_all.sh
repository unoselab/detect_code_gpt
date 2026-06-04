# Step 0 - Compute NPR / AUROC scores
# ---
# ./runmain_adapter_1.sh
# =================================================================
# Step 1 - Analysis
# ---
cd code-detection
python analyze_by_length.py \
    --cache ../logs/results_cache_main_adapter_starcoder2-7b_4500.pkl \
    --aggregate weighted_mean

# echo 'max'
# python main_adapter.py --csv_path "${CSV_PATH}" \
#     --load_cached_results ../logs/results_cache_main_adapter_starcoder2-7b_4500.pkl \
#     --aggregate max

# echo 'mean'
# python main_adapter.py --csv_path "${CSV_PATH}" \
#     --load_cached_results ../logs/results_cache_main_adapter_starcoder2-7b_4500.pkl \
#     --aggregate mean

# echo 'weighted_mean'
# python main_adapter.py --csv_path "${CSV_PATH}" \
#     --load_cached_results ../logs/results_cache_main_adapter_starcoder2-7b_4500.pkl \
#     --aggregate weighted_mean
