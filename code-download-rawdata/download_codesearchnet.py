"""
Download CodeSearchNet Python from HuggingFace and convert to the
schema expected by code-generation/generate.py.

The paper's script reads data['original_string'], but HF's mirror
uses 'whole_func_string'. We remap on the fly so generate.py works
unmodified.
"""

import json
import os
from datasets import load_dataset
from tqdm import tqdm

OUTPUT_DIR = "data/CodeSearchNet/python"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "train.jsonl")

os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"Downloading code-search-net/code_search_net (python) from HuggingFace...")
print("This will cache to ~/.cache/huggingface/ on first run (~1-2 GB).")

# Load the python subset, train split only
ds = load_dataset("code-search-net/code_search_net", "python", split="train", trust_remote_code=True)

print(f"Loaded {len(ds)} Python functions.")
print(f"Schema: {ds.column_names}")
print(f"Writing to {OUTPUT_FILE} with field remapping...")

written = 0
skipped = 0

with open(OUTPUT_FILE, "w") as fout:
    for row in tqdm(ds, ncols=80):
        whole = row.get("whole_func_string")
        if not whole:
            skipped += 1
            continue

        # Map HF schema -> paper's expected schema
        # generate.py only reads 'original_string', but we'll keep
        # a few useful fields for completeness/debugging.
        out = {
            "original_string": whole,
            "code": row.get("func_code_string", ""),
            "docstring": row.get("func_documentation_string", ""),
            "func_name": row.get("func_name", ""),
            "repo": row.get("repository_name", ""),
            "path": row.get("func_path_in_repository", ""),
            "language": "python",
        }
        fout.write(json.dumps(out) + "\n")
        written += 1

print(f"\nDone. Wrote {written} functions, skipped {skipped} (no whole_func_string).")
print(f"Output: {OUTPUT_FILE}")
print(f"Size: {os.path.getsize(OUTPUT_FILE) / 1e9:.2f} GB")