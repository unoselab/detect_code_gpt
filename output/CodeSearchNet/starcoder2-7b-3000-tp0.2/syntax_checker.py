import ast
import json
import re
import textwrap
from pathlib import Path

path = Path("../starcoder2-7b-3000-tp0.2/outputs-512token.txt")

def clean_output(output: str) -> str:
    s = output.replace("\r\n", "\n").replace("\r", "\n")

    # Hard stop: model starts generating repository/file context.
    s = s.split("<file_sep>", 1)[0]

    # Remove markdown fence tail if present.
    s = s.split("```", 1)[0]

    # Cut if the model starts a next top-level definition/class.
    patterns = [
        r"\n\n(?=def\s+\w+\s*\()",          # next top-level def
        r"\n\n(?=async\s+def\s+\w+\s*\()",  # next top-level async def
        r"\n\n(?=class\s+\w+)",             # next top-level class
        r"\n\s{4}def\s*$",                  # dangling "    def"
        r"\n\s{4}async\s+def\s*$",
        r"\n\s{4}class\s*$",
        r"\n\s*def\s*$",                    # dangling "def"
        r"\n\s*async\s+def\s*$",
        r"\n\s*class\s*$",
    ]

    cut = len(s)
    for pat in patterns:
        m = re.search(pat, s)
        if m:
            cut = min(cut, m.start())
    s = s[:cut]

    return s.rstrip() + "\n"

valid = []
invalid = []
salvaged = []

for line_no, line in enumerate(path.read_text().splitlines(), start=1):
    if not line.strip():
        continue

    obj = json.loads(line)

    raw_code = textwrap.dedent(obj["prompt"] + obj["output"]).strip() + "\n"
    clean = clean_output(obj["output"])
    clean_code = textwrap.dedent(obj["prompt"] + clean).strip() + "\n"

    try:
        ast.parse(raw_code)
        obj["_status"] = "raw_valid"
        obj["_clean_output"] = obj["output"]
        valid.append(obj)
        continue
    except SyntaxError as raw_e:
        raw_err = f"{raw_e.msg} at line {raw_e.lineno}"

    try:
        ast.parse(clean_code)
        obj["_status"] = "salvaged_valid"
        obj["_raw_syntax_error"] = raw_err
        obj["_clean_output"] = clean
        obj["_jsonl_line"] = line_no
        valid.append(obj)
        salvaged.append(obj)
    except SyntaxError as e:
        obj["_status"] = "invalid"
        obj["_syntax_error"] = f"{e.msg} at line {e.lineno}"
        obj["_raw_syntax_error"] = raw_err
        obj["_clean_output"] = clean
        obj["_jsonl_line"] = line_no
        invalid.append(obj)

print("total:", len(valid) + len(invalid))
print("valid_total:", len(valid))
print("raw_valid:", sum(1 for x in valid if x["_status"] == "raw_valid"))
print("salvaged_valid:", len(salvaged))
print("invalid:", len(invalid))
print("valid_rate:", round(len(valid) / max(len(valid) + len(invalid), 1), 4))

with open("valid_mgc_salvaged.jsonl", "w") as f:
    for obj in valid:
        f.write(json.dumps(obj) + "\n")

with open("invalid_mgc_salvaged.jsonl", "w") as f:
    for obj in invalid:
        f.write(json.dumps(obj) + "\n")