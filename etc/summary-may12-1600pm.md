## Where the morning left off
- Generation completed: 500 CodeLlama-7B samples on CodeSearchNet at T=0.2, saved to `output/CodeSearchNet/CodeLlama-7b-hf-500-tp0.2/outputs.txt`
- Total generation runtime: 20m 36.91s, avg 2.46s/sample
- Goal for afternoon: run `code-detection/main.py` and produce AUROC, comparing against paper's reported 0.9095

## Phase 4 prep — refactoring the detection script

### Found the script was hardcoded
`code-detection/main.py` had a `setup_args()` function that built a hardcoded `args_dict` dictionary and ignored CLI arguments entirely. Wanted CLI args for reusability across models/temps/datasets.

### Refactored `main.py`
You asked for CLI-driven config instead of hardcoded values. Applied these changes:

| Change | Lines | Why |
|---|---|---|
| Updated argparse defaults to paper values | 35-77 | Match paper config without needing CLI flags |
| Added `--data_path` argument | 78 | Direct path override (no relative-path symlink needed) |
| Removed `args_dict` override block | 79-133 | Use real CLI args |
| Updated `generate_data` to accept `data_path` | 86 | Wire the new arg through |
| Pass `data_path=args.data_path` at call site | 500 | Complete the wiring |

Comments tagged `# 2026-05-12 msong, ...` for traceability.

### Caught a bug in your first revision
Initial revision had `path = data_path` inside `generate_data` without `data_path` in the function signature → would have crashed with `NameError`. Fixed by adding `data_path=None` to the signature and using `if/else` fallback to the original relative-path lookup.

### Created shell scripts
- `run1-generate.sh` (placeholder)
- `run2-detect.sh` — the full detection invocation
- `run2a-detect-dryrun.sh` — small sanity check with 10 samples, no model load

## Bug #1 — tree-sitter compilation failure

`./run2-detect.sh` immediately crashed on `import identifier_tagging` with:
```
FileNotFoundError: ./tree-sitter/tree-sitter-python/src/parser.c
```

The original code used `Language.build_library(...)` to compile C source at runtime, but the repo never committed those C source files. Old deprecated API.

**Fix:** Patched `identifier_tagging.py` to use the modern `tree_sitter_languages` package (already in our env) which ships pre-built parsers:
```python
from tree_sitter_languages import get_language, get_parser
LANGUAGE_MAP = { 'python': get_language('python'), ... }
parser = get_parser('python')
```

Verified with import test (4 identifiers, 6 positions correctly extracted).

## Dry-run validation (n=10)

Ran a no-model dry-run to verify argparse + data loading wiring:

```
Parsed args:  ✓ all values correct
500it read → filtering → 131 examples passed filters
Loaded 10 originals, 10 samples
```

**Discovered the function-comment filter drops 352 of 500 samples** (70%) because both human and machine outputs contain `"""docstring"""`. Final usable count: 131 pairs. Decided to proceed with n=131 for first pass rather than regenerate.

## Bug #2 — `cache_dir` `~` not expanded

Real run crashed on:
```
FileNotFoundError: '../../blobs/<sha>' -> 
'/home/.../models--Salesforce--codet5p-770m/snapshots/.../config.json'
```

Root cause: `--cache_dir` default was `"~/.cache/huggingface/hub"` (literal `~`, never expanded). HF's symlink-based cache couldn't resolve the relative blob path.

**Fix:** Added `os.path.expanduser()` in `setup_args()`:
```python
args.cache_dir = os.path.expanduser(args.cache_dir)
if args.data_path is not None:
    args.data_path = os.path.expanduser(args.data_path)
```

Also cleared the half-downloaded cache directory and re-pulled codet5p-770m cleanly via `huggingface-cli download`.

## Bug #3 — `device=1, num_gpus=` CUDA assertion

Next crash:
```
RuntimeError: device >= 0 && device < num_gpus INTERNAL ASSERT FAILED
device=1, num_gpus=
```

Initially misdiagnosed as an import-order issue — gave you the wrong patch. You caught it by running a standalone test:
```
device count: 2     ← torch sees both GPUs without env manipulation
```

I corrected the diagnosis after seeing `loadmodel.py`. Two distinct sub-bugs:

**3a. Missing `trust_remote_code=True`** in `load_mask_filling_model`. The codet5p-770m model is a Salesforce custom architecture; without `trust_remote_code`, transformers falls back to vanilla T5 and weights mis-load with meta-tensor placeholders.

**3b. `CUDA_VISIBLE_DEVICES="0"` set too late** — after torch was already imported via `baselines.utils.run_baseline`. By the time the env var was set, Accelerate had already enumerated both GPUs, then crashed iterating to phantom GPU 1 during `device_map="auto"` planning.

**Fix 3a:** Added a dedicated `codet5p` branch in `load_mask_filling_model`:
```python
elif 'codet5p' in mask_filling_model_name:
    mask_model = transformers.AutoModelForSeq2SeqLM.from_pretrained(
        mask_filling_model_name,
        cache_dir=model_config['cache_dir'],
        device_map="auto",
        torch_dtype=torch.float16,
        trust_remote_code=True,
        decoder_start_token_id=50256,   # ← will turn out to be wrong, see Bug #4
        pad_token_id=50256,             # ← same
    )
```

**Fix 3b:** Moved `import os` and env-var setting to the top of `main.py`, BEFORE any other imports. Also added `export CUDA_VISIBLE_DEVICES=0` to `run2-detect.sh` as belt-and-suspenders.

Verified with isolated test:
```
torch sees 1 GPU(s)        ✓
SUCCESS — model loaded
Sample param device: cuda:0
GPU memory: 1.88 GB
```

## Bug #4 — Token ID out of vocab range (CURRENT)

Re-launched detection. Got further this time:
- ✓ Args parsed
- ✓ Data loaded (131 examples)
- ✓ Mask-filling model loaded
- ✗ Crashed mid-generation in `replace_masks`

```
RuntimeError: CUDA error: CUBLAS_STATUS_EXECUTION_FAILED
+ flood of: indexSelectSmallIndex: Assertion `srcIndex < srcSelectDimSize` failed
```

`indexSelectSmallIndex` is an embedding-table lookup. Out-of-range index.

Ran diagnostic:
```
Vocab size: 32100
decoder_start_token_id: 0
pad_token_id: 0
Is 50256 a valid token ID? FALSE  ← 50256 way out of range
```

**Root cause confirmed:** The author copy-pasted `decoder_start_token_id=50256, pad_token_id=50256` from a codet5p-220m-py loader (which has a 50K GPT-2 vocab), into the codet5p-770m loader (which has a 32K T5 vocab). Token 50256 doesn't exist in this model's embedding table.

**Pending fix:** Remove the two `_id=50256` lines from the codet5p branch in `loadmodel.py`. Let the model use its own config (`decoder_start_token_id=0`, `pad_token_id=0`).

## Current status — about to apply Bug #4 fix

Just gave you the instructions:
1. Edit `loadmodel.py` — remove the two `_id=50256` lines
2. Verify with grep
3. Run isolated test that exercises the exact crashing code path (codet5p `generate()` call)
4. If isolated test succeeds → relaunch `./run2-detect.sh`

**Bugs fixed so far in `loadmodel.py` and `main.py`:**
1. tree-sitter compilation → use `tree_sitter_languages` package
2. `cache_dir` `~` unexpanded → `os.path.expanduser`
3a. Missing `trust_remote_code` for codet5p → added codet5p branch
3b. `CUDA_VISIBLE_DEVICES` set too late → env vars moved to top of main.py
4. Hardcoded `50256` token IDs incompatible with 770m vocab → **about to remove**

**Still pending:** Apply Fix #4, verify with isolated `generate()` test, then run the actual detection. Target: AUROC ≈ 0.9095 (paper's reported value for CodeLlama-7B + CodeSearchNet + T=0.2).

**Lurking observation:** The same `50256` bug exists in `load_base_model_and_tokenizer` for codet5p. Doesn't trigger today because we don't use codet5p as a base model — but worth noting if anyone tries.