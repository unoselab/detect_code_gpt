cd code-selection
sed -n '1,120p' mixedcode_benchmarks/starcoder2-7b/type01_110/mixed_code_001.py
python -m json.tool mixedcode_benchmarks/starcoder2-7b/type01_110/mixed_code_001.json | head -n 80