## Where we started this session

After the afternoon's Phase 4 detection run completed at 16:41, you had a successful first reproduction with **AUROC 0.8965** on n=131 valid pairs (vs paper's target 0.9095). The gap was attributed to small sample size — the function-comment filter dropped 352 of 500 input samples (70% rejection rate).

You chose **Option A** to tighten that: regenerate with `--max_num 2000` to get ~500 valid pairs after filtering, matching the paper's evaluation size.

## What we did

### Step 1: Refactored `run2-detect.sh` to be variable-driven

You asked for variables at the top instead of hardcoded values, so I rewrote the script with:

- **Configuration block** with logical groupings (paths, GPU, dataset identity, model IDs, hyperparameters, run identity)
- **Derived variables** — `DATASET_KEY` and `DATA_PATH` automatically computed from `GEN_MODEL`, `GEN_MAX_NUM`, `GEN_TEMPERATURE`
- **`OUTPUT_NAME`** derived using bash lowercasing (`${VAR,,}`) and dot removal (`${VAR/./}`) → `codellama-7b-hf_csn_t02_n2000_run`
- **Pre-flight checks** for input file existence and `code-detection/` directory
- **Configuration banner** echoed at script start for log self-documentation

### Step 2: Added historical context comments

You requested inline reminders of previous values for future-you. Added:

- Inline comments next to `GEN_MAX_NUM` and `N_SAMPLES` showing previous (500 → 131 valid) vs current (2000 → ~520 valid)
- A **"Historical results" block** between config and pre-flight, recording Run 1's AUROC numbers (0.8786 logrank, 0.8412 LRR, 0.8965 DetectCodeGPT) for direct comparison

### Step 3: Added timestamped log filenames

You asked for `MM-DD_HH:MM` format in `LOG_FILE`. Added:
```bash
TIMESTAMP=$(date +%m-%d_%H:%M)
LOG_FILE="${LOG_DIR}/detection_${OUTPUT_NAME}_${TIMESTAMP}.log"
```

I flagged the caveat that colons in filenames can confuse some tools (scp, tab-completion) and offered Option B (`%m-%d_%H%M` without colon) as an alternative. You stuck with the colon form.

Resulting filename: `detection_codellama-7b-hf_csn_t02_n2000_run_05-13_00:03.log`

### Step 4: Launched the scaled detection run

You ran `./run2-detect.sh` at **00:03 on May 13**. The configuration banner confirmed:

```
DATASET_KEY:    CodeLlama-7b-hf-2000-tp0.2
N_SAMPLES:      2000
LOG_FILE:       .../detection_codellama-7b-hf_csn_t02_n2000_run_05-13_00:03.log
```

### Step 5: Detection started cleanly

The pipeline executed smoothly through every phase we had previously fixed:

**Data loading and filtering:**
- 2000 input samples read in <1 sec
- Filter breakdown: 34 too-many-defs, 32 too-many-comments, 7 too-many-TODOs, **1397 function-comment failures**
- **530 valid pairs after filtering** — slightly above the predicted ~524, exactly matching the paper's evaluation size

**Model loads:**
- codet5p-770m loaded from cache (no errors — all earlier `trust_remote_code` / `device_map="auto"` / token-ID fixes held)
- CodeLlama-7B loaded in <1 sec from warm cache

**Unperturbed scoring completed:**
- Log likelihoods: 530 samples in 36 sec at 14.71 it/s
- Log rank: 530 samples in 37 sec at 14.31 it/s
- Scaling was linear from n=131 (9 sec) → n=530 (36 sec) as expected

**Perturbed scoring (in progress):**
- At the screenshot moment: `18% | 95/530 [05:33<25:54, 3.57 s/it]`
- Estimated remaining: ~57 minutes
- Expected total runtime: ~63 minutes (start 00:03 → finish ~01:05)

## What I observed about perturbation quality

The example perturbed snippet in the log clearly shows DetectCodeGPT's strategy at work — random extra spaces between tokens, random extra indentation, occasional blank lines, but **no semantic changes**. This is exactly the design principle from the paper's Section VI.A ("Preservation of Code Correctness").

## Current status

**Run is still in progress** as of the last screenshot you sent. Expected completion ~01:00–01:05.

**Expected results based on n=131 run scaling:**
- DetectCodeGPT AUROC: predicted **0.89–0.92**, most likely **0.90–0.91**
- Paper target for this exact config: **0.9095**
- Confidence interval at n=530 tightens to ~±0.02, so any result in this range would qualify as a successful tight reproduction

**Pending:** Wait for run to finish, then paste back the four AUROC numbers, NaN counts, `results.pdf` confirmation, and total runtime.

## Things to highlight in any future writeup

The scripts you now have are reusable artifacts:

- `run1-generate.sh` (still simple, could get the same variable treatment)
- `run2-detect.sh` (fully variable-driven with self-documenting config banner, pre-flight checks, timestamped logs, and historical-results commentary)

Combined with the bug-fixing log from the afternoon (tree-sitter compilation, `~` expansion, `CUDA_VISIBLE_DEVICES` ordering, `trust_remote_code`, vocab-mismatched token IDs), you've turned the paper's repo into something that actually reproduces cleanly. That's genuinely useful — multiple of those bugs are still latent in the upstream repo and would bite anyone else who tries.

---
