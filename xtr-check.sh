cd ~/project-workspace/detect_code_gpt/code-selection

python - <<'PY'
from pathlib import Path
import json

p_json = Path("mixedcode_benchmarks/starcoder2-7b/type01_110/mixed_code_001.json")
p_py = Path("mixedcode_benchmarks/starcoder2-7b/type01_110/mixed_code_001.py")

meta = json.loads(p_json.read_text())
mixed_code = p_py.read_text()

f = meta["functions"][0]

body_text = mixed_code[f["body_start_char"]:f["body_end_char"]]

print("function_name:", f["function_name"])
print("role:", f["role"])
print("body_start_char:", f["body_start_char"])
print("body_end_char:", f["body_end_char"])
print("body_tokens:", f["body_tokens"])
print("=" * 80)
print(body_text)
print("=" * 80)
print("repr:")
print(repr(body_text))
PY

echo ""
echo ""

cd ~/project-workspace/detect_code_gpt/code-selection

python - <<'PY'
from pathlib import Path
import json

p_json = Path("mixedcode_benchmarks/starcoder2-7b/type10_200/mixed_code_001.json")
p_py = Path("mixedcode_benchmarks/starcoder2-7b/type10_200/mixed_code_001.py")

meta = json.loads(p_json.read_text())
mixed_code = p_py.read_text()

f = meta["functions"][0]

body_text = mixed_code[f["body_start_char"]:f["body_end_char"]]

print("function_name:", f["function_name"])
print("role:", f["role"])
print("body_start_char:", f["body_start_char"])
print("body_end_char:", f["body_end_char"])
print("body_tokens:", f["body_tokens"])
print("=" * 80)
print(body_text)
print("=" * 80)
print("repr:")
print(repr(body_text))
PY