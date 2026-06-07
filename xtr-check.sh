cd ~/project-workspace/detect_code_gpt

find logs -type f \( \
  -name "npr_scores_main_mixedcode_benchmark_mixedcode_*_50files.csv" -o \
  -name "npr_scores_main_mixedcode_benchmark_mixedcode_*_50files_bucket_summary.csv" -o \
  -name "npr_chunks_main_mixedcode_benchmark_mixedcode_*_50files.csv" -o \
  -name "results_cache_main_mixedcode_benchmark_mixedcode_*_50files.pkl" \
\) -printf "%TY-%Tm-%Td %TH:%TM  %p\n" | sort