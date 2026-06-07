cd ~/project-workspace/detect_code_gpt/code-selection

find mixedcode_benchmarks/gpt-oss -name "mixed_code_*.py" | wc -l
find mixedcode_benchmarks/gpt-oss -name "mixed_code_*.json" | wc -l
cat mixedcode_benchmarks/gpt-oss/manifest.csv