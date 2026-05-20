import ast
import json
import textwrap
from pathlib import Path

path = Path("../starcoder2-7b-3000-tp0.2/outputs_638_filter.jsonl")

valid = []
invalid = []

for line_no, line in enumerate(path.read_text().splitlines(), start=1):
    if not line.strip():
        continue

    obj = json.loads(line)
    code = textwrap.dedent(obj["prompt"] + obj["output"]).strip() + "\n"

    try:
        ast.parse(code)
        valid.append(obj)
    except SyntaxError as e:
        obj["_syntax_error"] = f"{e.msg} at line {e.lineno}"
        obj["_jsonl_line"] = line_no
        invalid.append(obj)

print("total:", len(valid) + len(invalid))
print("valid:", len(valid))
print("invalid:", len(invalid))

with open("valid_mgc.jsonl", "w") as f:
    for obj in valid:
        f.write(json.dumps(obj) + "\n")

with open("invalid_mgc.jsonl", "w") as f:
    for obj in invalid:
        f.write(json.dumps(obj) + "\n")