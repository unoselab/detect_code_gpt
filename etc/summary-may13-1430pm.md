## Overall topic

The conversation focused on reproducing and optimizing a **DetectCodeGPT** experiment for detecting machine-generated code using CodeLlama-based log-rank scoring and whitespace perturbations.

The main confirmed result was:

**DetectCodeGPT AUROC = 0.9007 with n = 530**, which closely matches the paper’s reported **0.9095**. The gap is only about **0.009**, considered a successful reproduction.

## Key technical explanation

The DetectCodeGPT score is based on **NPR: Normalized Perturbed Log Rank**.

For each sample, the score is:

[
\text{NPR}(x)=\frac{\text{mean log-rank of perturbed code}}{\text{log-rank of original code}}
]

The script computes two score lists:

* `predictions['real']`: NPR scores for human-written code
* `predictions['samples']`: NPR scores for machine-generated code

Then it computes AUROC using `sklearn.metrics.roc_auc_score`.

The intuition explained was:

* Machine-generated code usually has lower original log-rank under CodeLlama.
* Random whitespace perturbations make it look less natural to the model.
* Therefore, perturbed log-rank rises more sharply for machine code.
* This gives machine-generated code larger NPR scores on average.

AUROC = 0.9007 means that about **90.07% of randomly chosen machine/human sample pairs** are ranked correctly by NPR.

## Baseline results discussed

The run produced these metrics:

| Method                                    |                                   Score idea |                                    AUROC |
| ----------------------------------------- | -------------------------------------------: | ---------------------------------------: |
| Log Rank                                  |                               `-log_rank(x)` |                                   0.8924 |
| LRR                                       |           `-log_likelihood(x) / log_rank(x)` |                                   0.8267 |
| DetectGPT with DetectCodeGPT perturbation | z-score based on log likelihood perturbation | value not printed because of a small bug |
| DetectCodeGPT                             |  NPR: perturbed log-rank / original log-rank |                                   0.9007 |

A bug was identified: the script printed the label for “DetectGPT with DetectCodeGPT’s perturbation” but did not include the actual AUROC value in the print statement.

## Proposed code improvements

Several patches were designed for `main.py`.

### 1. Print NPR score statistics

A block was proposed to print:

* Mean, standard deviation, min, max, and median for human and machine NPR scores
* Mean separation between machine and human scores
* First 10 or 20 paired NPR values
* A text histogram showing distribution overlap
* AUROC at the end

### 2. Save NPR scores to CSV

A CSV export was proposed with columns such as:

```text
index, hwc_npr, mgc_npr, winner,
hwc_logrank, mgc_logrank,
hwc_perturbed_logrank, mgc_perturbed_logrank
```

This would allow offline threshold analysis without rerunning CodeLlama.

### 3. Add a `--detectcodegpt_only` flag

Initially, this flag was described as skipping only baseline AUROC computations, which would save only a few seconds. Later, the design was improved so that it skips baseline-only scoring blocks too.

The important realization was:

DetectCodeGPT NPR only needs four values:

```python
original_logrank
sampled_logrank
perturbed_original_logrank_50
perturbed_sampled_logrank_50
```

Therefore, these blocks are required:

* Unperturbed log rank
* Perturbed log rank

These blocks are not required for DetectCodeGPT NPR:

* Unperturbed log likelihood
* Perturbed log likelihood

Skipping the log-likelihood blocks cuts runtime from about **64 minutes to about 32 minutes**.

### 4. Add pickle caching

A cache mechanism was proposed:

* Save the completed `results` list to a pickle file after scoring
* Load that pickle later with `--load_cached_results`
* Recompute AUROC, thresholds, CSV, and plots in about one second without rerunning model forward passes

Suggested flags:

```python
--results_cache
--load_cached_results
--npr_csv_dir
```

## Runtime analysis

The original run had four main scoring blocks:

| Block                      | Purpose            | Required for DetectCodeGPT? |    Time |
| -------------------------- | ------------------ | --------------------------: | ------: |
| Unperturbed log likelihood | LRR baseline       |                          No | ~36 sec |
| Unperturbed log rank       | NPR denominator    |                         Yes | ~37 sec |
| Perturbed log likelihood   | DetectGPT baseline |                          No | ~32 min |
| Perturbed log rank         | NPR numerator      |                         Yes | ~32 min |

The major optimization was to skip perturbed log likelihood when only DetectCodeGPT is needed.

Expected runtime modes:

| Mode                    | Runtime | Output                                      |
| ----------------------- | ------: | ------------------------------------------- |
| Full mode               | ~64 min | All AUROCs                                  |
| `--detectcodegpt_only`  | ~32 min | DetectCodeGPT AUROC + free logrank baseline |
| `--load_cached_results` |  ~1 sec | AUROC, CSV, thresholds, plots only          |

## Threshold analysis for an interactive app

The conversation also planned for an eventual **single-code-snippet detector**.

The batch experiment processes:

```text
530 samples × 50 perturbations = 26,500 forward passes
```

But an interactive detector would process:

```text
1 sample × 50 perturbations = 50 forward passes
```

So a single-input version could be practical, roughly a few seconds per query after model loading.

The proposed detector would:

1. Accept one code snippet.
2. Compute original log-rank.
3. Generate 50 whitespace-perturbed variants.
4. Compute mean perturbed log-rank.
5. Compute NPR.
6. Compare NPR against a threshold.
7. Predict either:

   * HWC: human-written code
   * MGC: machine-generated code

A threshold based on **Youden’s J statistic** was proposed:

[
J = \text{TPR} - \text{FPR}
]

The best threshold would maximize this value.

## Final observed run status

After applying the optimized patch, the run showed:

* `detectcodegpt_only=True`
* Dataset loaded successfully
* 2000 input examples filtered down to 530 valid examples
* Block 1 skipped correctly
* Block 2 completed in about 36.7 seconds
* Block 3 skipped correctly
* Block 4, perturbed log-rank, was running as expected

At the snapshot shown, Block 4 was about **9% complete**, with an estimated **~29 minutes remaining**.

The expected final output included:

* NPR summary statistics
* First 10 NPR pairs
* Text histogram
* Percentile thresholds
* Youden’s J optimal threshold
* CSV file path
* Pickle cache path
* DetectCodeGPT AUROC
* Free logrank baseline AUROC

## Main conclusion

The reproduction was successful: **DetectCodeGPT reached AUROC 0.9007**, very close to the paper’s **0.9095**.

The conversation then moved from reproduction to engineering improvements:

1. Make the score computation transparent.
2. Save per-sample scores.
3. Add threshold analysis.
4. Reduce runtime by skipping unnecessary baseline scoring.
5. Add caching for fast re-analysis.
6. Prepare for a future interactive single-snippet DetectCodeGPT tool.
