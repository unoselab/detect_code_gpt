# Conversation Summary — After Noon, May 13, 2026

## Context entering this period
The morning's scaled detection run (n=530, started 00:03 May 13) had finished with **AUROC = 0.9007** against the paper's target of 0.9095 — a successful tight reproduction. The afternoon focused on understanding the AUROC computation, then building analysis tooling for an eventual interactive single-code detector app.

## Analyzing how AUROC is computed
You asked me to explain exactly how `main.py` produces `ROC AUC of DetectCodeGPT: 0.9007`. I traced the three layers:

1. **Per-sample NPR score** — for each of the 530 valid pairs, `NPR = mean(perturbed_logrank over 50 perturbations) / unperturbed_logrank`, computed separately for human code (HWC) and machine code (MGC)
2. **AUROC conversion** — `get_roc_metrics` wraps `sklearn.metrics.roc_auc_score`; the 530 HWC scores (label 0) and 530 MGC scores (label 1) become 1060 labeled examples; AUROC = probability a random MGC scores higher than a random HWC
3. **Why the formula works** — machine code sits in a "natural" low-logrank region, so perturbation inflates its logrank ratio more than human code's

I also noted a minor upstream bug: line 670's `print(f"ROC AUC of DetectGPT with DetectCodeGPT's perturbation")` is missing the value interpolation.

## Building per-sample NPR output
You asked to print the actual `predictions['real']` and `predictions['samples']` values. I drafted a printing block adding summary statistics, a first-10-pairs preview, a text histogram, percentile thresholds, and a CSV dump.

## Two product-oriented requests
You then asked for (1) storing all scores to a file and (2) a CLI flag to compute only DetectCodeGPT to save time — motivated by wanting to study a **threshold** for an interactive app that classifies a single user-submitted code as HWC or MGC.

I clarified an important point: the expensive part (`Computing perturbed log rank: 32 min`) **cannot be skipped** — it IS the DetectCodeGPT method. But I identified what *can* be skipped.

## Identifying the skippable blocks
You asked which of the four scoring blocks could be skipped. I traced the data dependencies:

| Block | Produces | Needed for NPR? | Verdict |
|---|---|---|---|
| Block 1: unperturbed log likelihoods | `original_ll`, `sampled_ll` | No (LRR baseline only) | **Skippable — saves ~36 sec** |
| Block 2: unperturbed log rank | `*_logrank` | Yes (NPR denominator) | Required |
| Block 3: perturbed log likelihoods | `perturbed_*_ll_50` | No (DetectGPT baseline only) | **Skippable — saves ~32 min** |
| Block 4: perturbed log rank | `perturbed_*_logrank_50` | Yes (NPR numerator) | Required |

Skipping Blocks 1 and 3 halves runtime (~64 min → ~32 min).

## The consolidated patch
You said "yes" to a consolidated patch. I provided edits for `main.py`:
- Three CLI flags: `--detectcodegpt_only`, `--results_cache`, `--load_cached_results`, plus `--npr_csv_dir`
- `os.path.expanduser` expansion for the new path args
- Blocks 1 and 3 wrapped in `if not args.detectcodegpt_only:`
- A `--load_cached_results` short-circuit that loads a pickled `results` dict and skips ALL scoring (~1 sec)
- Pickle cache write after scoring completes
- The full NPR analysis output block (stats, histogram, Youden's J optimal threshold, percentile candidates, CSV)
- Baseline printing guarded so only the free logrank baseline survives in `--detectcodegpt_only` mode

Plus `run2-detect.sh` updates: `DETECTCODEGPT_ONLY` and `LOAD_CACHED_RESULTS` variables.

## First run with the patch
You ran it at 14:26 with `DETECTCODEGPT_ONLY=true`. The log confirmed everything worked: Block 1 skipped, Block 2 ran (~37s), Block 3 skipped ("saves ~32 min"), Block 4 in progress at 3.63 s/it. Total projected ~32 min — exactly the 50% speedup predicted.

## Examining the CSV and the ground-truth question
You shared the first 10 rows of `npr_scores_codellama-7b-hf_csn_t02_n2000_run.csv` and asked: do we have ground truth for each line? What's the input? What's the correct answer?

I explained:
- Each row is a **pair** sharing one prompt. `hwc_*` columns describe the human's `solution`; `mgc_*` columns describe CodeLlama's `output`. Ground truth is implicit in which column the score sits in — no ambiguity.
- 530 rows → 1060 labeled examples for AUROC
- The `winner` column is a paired-comparison metric (did MGC beat its own paired HWC), subtly different from AUROC's pooled comparison
- In your first 10 rows, 9/10 were correctly classified; row 0 was the lone HWC win
- I provided commands to trace a row back to `outputs.txt` and to unroll the CSV into a flat 1060-row labeled file

## The provenance bug you caught
You correctly pointed out that the CSV `index` is the **post-filter index**, NOT the line number in `outputs.txt` — 2000 raw samples were filtered down to 530, so there's no guarantee CSV row 0 corresponds to `outputs.txt` line 0 (it happened to, by coincidence).

I designed a fix to thread `source_line_no` through the pipeline:
1. `generate_data()`: add `all_source_line_nos = []`, change loop to `enumerate(tqdm(...))`, append `line_no` alongside the existing appends, add a length-consistency assertion, add `source_line_no` to the return dict
2. `results` construction: add `"source_line_no": data["source_line_no"][idx]`
3. CSV writer: add the `source_line_no` column to header and rows
4. For `--load_cached_results`: backfill `source_line_no` from a fresh `generate_data()` call since the old pickle predates this change

## Reviewing your patch — found a bug
You applied the patch and sent a diff screenshot. I reviewed all 8 change areas. Seven were correct, but I found one real bug:

🚨 **Your `generate_data()` return statement dropped the `[:max_num]` slicing.** The old code had `all_originals[:max_num]` / `all_samples[:max_num]`; your new version returned the unsliced lists. Silent failure mode: harmless when `max_num` (2000) ≥ filter count (530), but if you ever set `--n_samples 100` it would return all 530 and break downstream perturbation counts.

The fix: `return {"original": all_originals[:max_num], "sampled": all_samples[:max_num], "source_line_no": all_source_line_nos[:max_num]}`.

## Current state — a NEW error to fix
You uploaded the latest `main.py` and a log from a 23:47 run that crashed. The run got through cache loading and `source_line_no` backfilling successfully (the dict_keys output confirms `score_line_no` is present), but then crashed:

```
File ".../main.py", line 723, in main
    res['perturbed_original_logrank_{n_perturbation}'] / res['original_logrank']
UnboundLocalError: cannot access local variable 'n_perturbation' where it is not associated with a value
```

**The bug:** In the NPR computation, `n_perturbation` is being used but was never assigned in that scope. In the original scoring blocks, `n_perturbation` gets bound by the `for n_perturbation in n_perturbation_list:` loops. But in `--load_cached_results` mode (or `--detectcodegpt_only` mode), those loops are skipped — so `n_perturbation` is never defined by the time the AUROC block runs. Also worth noting the log shows `n_perturbation_lists='50'` (with an `s`) as the arg name, and there may be a literal-string-vs-variable issue in how the key is constructed.

**I was just starting to investigate** — I listed the uploads directory and confirmed `main.py` (45402 bytes, May 14) is present. The next step is to view `main.py` around line 723 and the argument parsing for `n_perturbation_list`, then fix the unbound variable — likely by deriving `n_perturbation` explicitly (e.g., `n_perturbation = max(n_perturbation_list)` or parsing it from the arg) before the AUROC block, independent of whether the scoring loops ran.

## Key files
- `main.py` — backups: `.original`, `.before_npr_dump`, `.before_consolidated_patch`
- Results pickle: `~/project-workspace/detect_code_gpt/logs/results_cache_codellama-7b-hf_csn_t02_n2000_run.pkl`
- NPR CSV: `~/project-workspace/detect_code_gpt/logs/npr_scores_codellama-7b-hf_csn_t02_n2000_run.csv`
- Latest crashing log: run from 23:47, `detection_codellama-7b-hf_csn_t02_n2000_run_05-13_23:47.log`

## Pending next steps
1. **Fix the `UnboundLocalError`** — view `main.py` ~line 723 and the `n_perturbation_list` argparse definition, then ensure `n_perturbation` is bound before the AUROC/NPR/CSV block regardless of which scoring blocks ran
2. Re-run with `--load_cached_results` (~5 sec) to produce the CSV with `source_line_no`
3. Spot-check CSV row 0's `source_line_no` against the actual `outputs.txt` line
4. Then build `scripts/detect_single.py` — the interactive single-code detector using the Youden's J threshold