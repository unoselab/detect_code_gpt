for csv in \
  /home/user1-system12/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet/codellama-7b/validsyntax_4500_complexity/codesearchnet_codellama-7b_python_merged_4500.csv \
  /home/user1-system12/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet/gemma/validsyntax_4500_complexity/codesearchnet_gemma_python_merged_4500.csv \
  /home/user1-system12/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet/starcoder2-7b/validsyntax_4500_complexity/codesearchnet_starcoder2-7b_python_merged_4500.csv \
  /home/user1-system12/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet/starcoder2-15b-instruct-v0.1/validsyntax_4500_complexity/codesearchnet_starcoder2-15b-instruct-v0.1_python_merged_4500.csv \
  /home/user1-system12/project-workspace/ai_detector/src/code-analyzer-tree-sitter/data_codesearchnet/gpt-oss/validsyntax_4500_complexity/codesearchnet_gpt-oss_python_merged_4500.csv
do
  echo "============================================================"
  echo "Preflight: $csv"
  echo "============================================================"
  python code-detection/main_adapter_v0.4.py --csv_path "$csv" --preflight_only
done
