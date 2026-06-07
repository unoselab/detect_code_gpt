cd ~/project-workspace/detect_code_gpt/code-selection

python - <<'PY'
from pathlib import Path

p = Path("generate_mixedcode_benchmark.py")
s = p.read_text()

old_func = '''def ensure_function_separator(text: str) -> str:
    """End a function with a split-space-safe separator.

    We add a literal trailing space before the newline. This is harmless for
    Python semantics and prevents text.split(' ') tokens from crossing function
    boundaries through newlines.
    """
    t = text.rstrip("\\n")
    return t + " \\n\\n"
'''

new_func = '''def make_split_space_safe_function_block(raw_func: str, is_first: bool, is_last: bool) -> str:
    """
    Build a valid Python function block whose boundaries are safe under
    split_space_v1 = text.split(" ").

    The key idea:
      - Non-final functions end with a literal space.
      - Blank lines before the next function belong to the next function block.
      - Therefore a token like "\\\\n\\\\ndef" starts exactly at the next region,
        rather than crossing from the previous region into the next one.
    """
    prefix = "" if is_first else "\\n\\n"
    core = raw_func.rstrip("\\n")
    suffix = "\\n" if is_last else " "
    return prefix + core + suffix
'''

if old_func not in s:
    raise SystemExit("Could not find ensure_function_separator() block.")

s = s.replace(old_func, new_func, 1)

old_call = '''        raw_func, func_name = make_safe_unique_function_text(cand, file_id=file_id, function_id=i)
        func_text = ensure_function_separator(raw_func)
'''

new_call = '''        raw_func, func_name = make_safe_unique_function_text(cand, file_id=file_id, function_id=i)
        func_text = make_split_space_safe_function_block(
            raw_func,
            is_first=(i == 1),
            is_last=(i == len(selected)),
        )
'''

if old_call not in s:
    raise SystemExit("Could not find function separator call.")

s = s.replace(old_call, new_call, 1)

p.write_text(s)
print("Patched", p)
PY