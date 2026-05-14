## Summary: DetectCodeGPT reproduction and optimization

**Paper understanding → environment setup → generation → detection reproduction → engineering improvements → interactive detector planning**

---

### Table of Contents

- [Summary: DetectCodeGPT reproduction and optimization](#summary-detectcodegpt-reproduction-and-optimization)
  - [Table of Contents](#table-of-contents)
  - [1. Paper and reproduction target](#1-paper-and-reproduction-target)
  - [2. Methodology and main result](#2-methodology-and-main-result)
  - [3. Environment and data setup](#3-environment-and-data-setup)
  - [4. Major code fixes during detection](#4-major-code-fixes-during-detection)
  - [5. Scaling from 131 to 530 valid pairs](#5-scaling-from-131-to-530-valid-pairs)
  - [6. Runtime optimization](#6-runtime-optimization)
  - [7. Threshold analysis and interactive detector](#7-threshold-analysis-and-interactive-detector)
  - [8. Workspace](#8-workspace)
  - [9. Current status](#9-current-status)
  - [10. Best next step](#10-best-next-step)

---

### 1. Paper and reproduction target

The paper is **"Between Lines of Code: Unraveling the Distinct Patterns of Machine and Human Programmers"** from ICSE 2025. Its core claim is that machine-generated code differs from human-written code in lexical diversity, conciseness, and especially **naturalness/stylistic regularity**.

The paper proposes **DetectCodeGPT**, a zero-shot method that detects machine-generated code by perturbing whitespace/newlines and measuring the resulting change in code naturalness. The paper reports an average AUROC of **0.8308**. For the exact target reproduced here — **CodeSearchNet + CodeLlama-7B + temperature 0.2** — Table IV reports **DetectCodeGPT AUROC = 0.9095**.

The reproduction target was therefore:

```text
Dataset: CodeSearchNet Python
Generator: CodeLlama-7B
Temperature: 0.2
Detection method: DetectCodeGPT / NPR with 50 whitespace perturbations
Paper target: AUROC ≈ 0.9095
````

### 2. Methodology and main result

DetectCodeGPT uses **NPR: Normalized Perturbed Log Rank**:

```text
NPR(x) = mean(log-rank of perturbed code) / log-rank of original code
```

The key intuition is that machine-generated code is usually more "natural" or predictable to the model. When random spaces/newlines are inserted, its log-rank rises more sharply than human-written code. As a result, machine-generated code tends to receive a higher NPR score.

The main confirmed reproduction result is:

```text
DetectCodeGPT AUROC = 0.9007
Valid pairs = 530
Paper target = 0.9095
Gap = about 0.009
```

The baseline results were:

| Method        |      AUROC |
| ------------- | ---------: |
| Log Rank      |     0.8924 |
| LRR           |     0.8267 |
| DetectCodeGPT | **0.9007** |

### 3. Environment and data setup

```text
NVIDIA RTX 6000
CUDA driver 12.4
```

The environment used Python 3.11 and PyTorch 2.1.2 with CUDA 12.1. An MKL ABI issue was fixed by downgrading MKL to 2023.1.0.

For the data setup:

```text
1. The original CodeSearchNet S3 download failed with 403 Forbidden.
2. The Hugging Face mirror was used instead.
3. The Hugging Face schema uses `whole_func_string`, while the code expected `original_string`.
   - A conversion script remapped the dataset.
   - The resulting Python dataset contained 412,178 functions.
```

### 4. Major code fixes during detection

The detection repository was not directly reproducible. We fixed several important issues:

1. **Hardcoded CLI configuration**

   `main.py` originally ignored command-line arguments because of a hardcoded `args_dict`. We refactored it to use real CLI arguments, added `--data_path`, and created reusable scripts such as `run2-detect.sh`.

2. **Tree-sitter parser failure**

   The repository tried to compile tree-sitter grammar files that were not included. We replaced the runtime compilation path with `tree_sitter_languages`, which ships prebuilt parsers.

3. **`~` expansion bug in the Hugging Face cache path**

   `--cache_dir` used a literal `"~/.cache/..."`, which broke Hugging Face symlink resolution. We added `os.path.expanduser()` for both `cache_dir` and `data_path`.

4. **CUDA / device-map instability**

   `CUDA_VISIBLE_DEVICES` was being set too late, after torch-related imports had already enumerated GPUs. We moved the environment setup to the top of `main.py` and also exported `CUDA_VISIBLE_DEVICES=0` in the shell script.

5. **Missing `trust_remote_code=True` for CodeT5+**

   CodeT5+ 770M uses custom architecture code. Without `trust_remote_code=True`, model loading failed or produced invalid meta-tensor behavior.

6. **Hardcoded invalid token IDs**

   The repository hardcoded `decoder_start_token_id=50256` and `pad_token_id=50256`, copied from a model with a GPT-2-sized vocabulary. CodeT5+ 770M has a vocabulary size of **32,100**, with config IDs equal to **0**, so token ID 50256 caused an out-of-range embedding lookup. The fix was to remove the hardcoded IDs and use the model configuration.

7. **Cache loading bug**

   Later, `--load_cached_results` triggered an `UnboundLocalError` because `n_perturbation` was normally assigned inside scoring loops that were skipped in cached mode. We fixed this by explicitly defining it before the final NPR calculation.

### 5. Scaling from 131 to 530 valid pairs

The first 500 generated examples produced only **131 valid pairs** because the detection filter rejected many functions, especially those with docstring/comment patterns. The rejection rate was about 70%.

To match the paper's 500-pair evaluation scale, we regenerated the dataset with:

```text
--max_num 2000
```

This produced **530 valid pairs**, very close to the paper's intended evaluation size. The scaled run was therefore the decisive reproduction run.

### 6. Runtime optimization

The original detection pipeline had four scoring blocks:

| Block                      | Needed for DetectCodeGPT? | Approx. time |
| -------------------------- | ------------------------: | -----------: |
| Unperturbed log likelihood |                        No |      ~36 sec |
| Unperturbed log rank       |                       Yes |      ~37 sec |
| Perturbed log likelihood   |                        No |      ~32 min |
| Perturbed log rank         |                       Yes |      ~32 min |

The optimization included a **DetectCodeGPT NPR-only** mode:

```text
original_logrank
sampled_logrank
perturbed_original_logrank_50
perturbed_sampled_logrank_50
```

We added `--detectcodegpt_only` to skip the log-likelihood blocks, reducing runtime from about **64 minutes** to about **32 minutes**. We also added pickle caching so that threshold analysis, CSV export, and plotting can be rerun in about one second without rerunning CodeLlama forward passes.

The new runtime modes are:

| Mode                    | Runtime | Purpose                                 |
| ----------------------- | ------: | --------------------------------------- |
| Full mode               | ~64 min | All baselines + DetectCodeGPT           |
| `--detectcodegpt_only`  | ~32 min | DetectCodeGPT + free log-rank baseline  |
| `--load_cached_results` | ~30 sec | Recompute AUROC, thresholds, CSV, plots |

### 7. Threshold analysis and interactive detector

After the successful 530-sample batch run, the analysis moved toward building a practical single-snippet detector.

The batch distribution showed:

```text
Human-written code cluster: around NPR 1.24
Machine-generated code cluster: around NPR 1.59
Youden's J optimal threshold: 1.3875
Conservative threshold: 1.60
```

The **1.60 threshold** was identified as conservative: scores above 1.6 are "strongly machine-like" while keeping the false-positive risk low.

The interactive detector workflow is:

```text
1. Accept one code snippet.
2. Compute the original log-rank.
3. Generate 50 whitespace/newline perturbations.
4. Compute the mean perturbed log-rank.
5. Compute NPR.
   -> NPR(x) = mean(log-rank of perturbed code) / log-rank of original code
6. Compare NPR against the threshold.
7. Predict HWC or MGC.
```

We integrated an `--interactive` flag into `main.py` instead of creating a separate script, preserving code reuse. Startup time dropped to under a few seconds.

Live tests matched expectations:

```text
AI-hallucinated infinite loop: NPR 2.2142 → Machine
Complex human math algorithm: NPR 1.2925 → Human
```

### 8. Workspace

```text
Do not push:
- 24 MB pickle cache files
- verbose .log files

Do track:
- lightweight final CSV score files
- source patches/scripts
```

We also prepared `scp` and `rsync` commands for safely downloading the remote workspace from `user1-system12@oisse-ist173c01`, including ways to exclude `.git` and log files.

### 9. Current status

The project has achieved the main reproduction goal:

```text
Paper target:       0.9095
Reproduction:       0.9007
Valid pairs:        530
Conclusion:         successful reproduction
```

The final workspace now includes:

```text
- CLI-driven configuration
- fixed parser dependency
- fixed Hugging Face cache paths
- fixed CodeT5+ loading
- fixed invalid token IDs
- GPU-stable execution
- reusable run scripts
- DetectCodeGPT-only fast mode
- result caching
- per-sample NPR CSV export
- threshold analysis
- interactive single-code detector mode
```

### 10. Best next step

The next best step is to write `evaluate_metrics.py` to read the existing `npr_scores_...csv` file and compute:

```
Accuracy
Precision
Recall
F1
TPR/FPR
Confusion matrix
Metrics at threshold 1.3875
Metrics at threshold 1.60
```
