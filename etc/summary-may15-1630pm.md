## What needs to happen

For each of the 530 records:
1. Take `mixed_code`
2. Chunk it into 128-token blocks (using `split(" ")`)
3. Score each chunk's NPR using CodeLlama + 50 whitespace perturbations
4. Record per-chunk: `start_token`, `end_token`, `NPR`, `verdict`
5. Save results — eventually compare predicted suspect regions against ground-truth MGC region

That's the operation. Now the design choices.

## Design choices to make first

**1. What's a "suspect chunk"?**

Three reasonable thresholding strategies, in increasing strictness:

- `NPR > threshold_YOUDEN` (1.3875) — flagged as MGC suspect
- `NPR > threshold_high` (1.6) — high-confidence MGC
- `NPR > median_NPR + 2 * MAD` (local deviation) — chunk stands out relative to its neighbors

For the first batch run, I'd use **just the absolute thresholds** (Youden's J and high-confidence) and skip local-deviation. Why: we want to know how the absolute thresholds perform on a fresh dataset before adding the local-deviation refinement.

**2. Output format — one row per chunk, or one row per record?**

Per-chunk is more flexible. You can aggregate per-record from per-chunk data, but not the reverse. Per-chunk also lets you write a single CSV that's easy to load in pandas later for analysis.

**3. Where does this run live?**

Two options:
- **(a)** Add a new mode `--batch_benchmark` to `main.py` (alongside `--interactive`)
- **(b)** Make a new script `code-detection/batch_benchmark.py` that reuses `main.py`'s scoring functions

I lean toward **(a)** — `main.py` already has all the model loading, perturbation, and `get_rank` machinery. A new mode is just a different loop driver around the same primitives. Less duplication.

But to be honest about the tradeoff: `main.py` is already long (~1000 lines) and has accumulated a lot of modes. Adding a third mode adds complexity. If you'd rather keep concerns separate, a thin standalone script that imports from `main.py` is also defensible.

I'll show the `--batch_benchmark` mode approach since it keeps everything in one file, but it's not a strong opinion.

**4. Time budget**

For each record's chunk: ~3.5 seconds per chunk (from your earlier interactive runs — 50 perturbations × CodeLlama log-rank forward pass).

Per record: ~2-6 chunks (mostly 2-3 for medium functions, up to 6 for the longest), say average 3.

Total: 530 × 3 × 3.5 ≈ **5500 seconds = 90 minutes**.

Same ballpark as the original detection run. Worth running once and caching results.

**5. Cache strategy**

Same pattern as `--load_cached_results`: after scoring every chunk, pickle the full chunk-NPR list to disk. Subsequent threshold experiments are then 1-second operations.

## Recommended approach

Here's what I'd build:

### Step 1 — Add `--batch_benchmark` flag to `main.py`

In `setup_args()`:

```python
# 2026-05-15 msong: batch-benchmark mode for MGC localization evaluation.
parser.add_argument('--batch_benchmark', action='store_true',
                    help='Run detector across all records in a benchmark JSONL, '
                         'producing per-chunk NPR scores. Reads --benchmark_jsonl, '
                         'writes per-chunk CSV and pickle cache.')
parser.add_argument('--benchmark_jsonl', type=str, default=None,
                    help='Path to benchmark JSONL produced by generate_benchmark.py. '
                         'Required when --batch_benchmark is set.')
parser.add_argument('--benchmark_results_csv', type=str, default=None,
                    help='Output CSV path. Defaults to ../logs/benchmark_results_<output_name>.csv')
parser.add_argument('--benchmark_results_pkl', type=str, default=None,
                    help='Output pickle cache path. Defaults to '
                         '../logs/benchmark_results_<output_name>.pkl')
parser.add_argument('--load_benchmark_results', type=str, default=None,
                    help='Load benchmark results from a pickle file, skip scoring, '
                         'just compute metrics. ~1 sec.')
```

Add path expansion for the new args:

```python
if args.benchmark_jsonl is not None:
    args.benchmark_jsonl = os.path.expanduser(args.benchmark_jsonl)
if args.benchmark_results_csv is not None:
    args.benchmark_results_csv = os.path.expanduser(args.benchmark_results_csv)
if args.benchmark_results_pkl is not None:
    args.benchmark_results_pkl = os.path.expanduser(args.benchmark_results_pkl)
if args.load_benchmark_results is not None:
    args.load_benchmark_results = os.path.expanduser(args.load_benchmark_results)
```

### Step 2 — Add the `run_batch_benchmark` function

Add this above `run_interactive_mode` (it shares the chunking and scoring patterns):

```python
def run_batch_benchmark(args, model_config):
    """Score every chunk of every record in a benchmark JSONL.

    Output: per-chunk CSV + pickle cache. Each row is one chunk's NPR result,
    plus ground-truth metadata so localization evaluation is a CSV join.
    """
    print("\n" + "=" * 70)
    print("    DetectCodeGPT Batch Benchmark — MGC Localization Scoring    ")
    print("=" * 70)

    if not args.benchmark_jsonl:
        logger.error("--benchmark_jsonl is required with --batch_benchmark")
        return

    if not os.path.isfile(args.benchmark_jsonl):
        logger.error(f"Benchmark JSONL not found: {args.benchmark_jsonl}")
        return

    # Resolve output paths with defaults
    output_csv = args.benchmark_results_csv or f"../logs/benchmark_results_{args.output_name}.csv"
    output_pkl = args.benchmark_results_pkl or f"../logs/benchmark_results_{args.output_name}.pkl"

    # Short-circuit: load cached results
    if args.load_benchmark_results is not None:
        logger.info(f"Loading cached benchmark results from {args.load_benchmark_results}")
        with open(args.load_benchmark_results, "rb") as f:
            all_chunk_results = pickle.load(f)
        logger.info(f"Loaded {len(all_chunk_results)} chunk results")
    else:
        # Load benchmark records
        records = []
        with open(args.benchmark_jsonl, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        logger.info(f"Loaded {len(records)} benchmark records from {args.benchmark_jsonl}")

        n_perturb = max([int(x) for x in str(args.n_perturbation_list).split(",")])
        max_len = args.max_len

        all_chunk_results = []
        total_chunks_est = sum(
            -(-r['n_tokens_total'] // max_len)  # ceiling division
            for r in records
        )
        logger.info(f"Estimated total chunks to score: {total_chunks_est}")

        for record_idx, record in enumerate(tqdm(records, desc="Records")):
            mixed_code = record["mixed_code"]
            all_tokens = mixed_code.split(" ")
            n_tokens_total = len(all_tokens)

            mgc_region = next(reg for reg in record["regions"] if reg["label"] == "MGC")
            mgc_start_token = mgc_region["start_token"]
            mgc_end_token   = mgc_region["end_token"]

            # Chunk: stride = max_len, no overlap
            for chunk_idx, start in enumerate(range(0, n_tokens_total, max_len)):
                chunk_tokens = all_tokens[start:start + max_len]
                end = start + len(chunk_tokens)
                chunk_text = " ".join(chunk_tokens)

                # Skip pathologically tiny chunks — NPR is unreliable
                if len(chunk_tokens) < 20:
                    all_chunk_results.append({
                        "record_id":         record["id"],
                        "chunk_idx":         chunk_idx,
                        "start_token":       start,
                        "end_token":         end,
                        "n_tokens":          len(chunk_tokens),
                        "npr":               float("nan"),
                        "orig_logrank":      float("nan"),
                        "mean_p_logrank":    float("nan"),
                        "low_conf":          True,
                        "overlaps_mgc":      end > mgc_start_token and start < mgc_end_token,
                        "fully_in_mgc":      start >= mgc_start_token and end <= mgc_end_token,
                        "n_mgc_tokens_in_chunk": max(0, min(end, mgc_end_token) - max(start, mgc_start_token)),
                        "mgc_start_token":   mgc_start_token,
                        "mgc_end_token":     mgc_end_token,
                    })
                    continue

                # Score this chunk
                orig_logrank = get_rank(chunk_text, args, model_config, log=True)
                inputs_to_perturb = [chunk_text for _ in range(n_perturb)]
                p_texts = perturb_texts(inputs_to_perturb, args, model_config)
                p_ranks = get_ranks(p_texts, args, model_config, log=True)
                valid_p_ranks = [r for r in p_ranks if not math.isnan(r)]
                mean_p_rank = np.mean(valid_p_ranks) if valid_p_ranks else float("nan")
                npr = mean_p_rank / orig_logrank if orig_logrank else float("nan")

                # Compute overlap with MGC ground truth (in token indices)
                overlap_start = max(start, mgc_start_token)
                overlap_end = min(end, mgc_end_token)
                n_mgc_in_chunk = max(0, overlap_end - overlap_start)

                all_chunk_results.append({
                    "record_id":         record["id"],
                    "chunk_idx":         chunk_idx,
                    "start_token":       start,
                    "end_token":         end,
                    "n_tokens":          len(chunk_tokens),
                    "npr":               npr,
                    "orig_logrank":      orig_logrank,
                    "mean_p_logrank":    mean_p_rank,
                    "low_conf":          False,
                    "overlaps_mgc":      n_mgc_in_chunk > 0,
                    "fully_in_mgc":      start >= mgc_start_token and end <= mgc_end_token,
                    "n_mgc_tokens_in_chunk": n_mgc_in_chunk,
                    "mgc_start_token":   mgc_start_token,
                    "mgc_end_token":     mgc_end_token,
                })

            if (record_idx + 1) % 50 == 0:
                logger.info(f"Progress: {record_idx + 1}/{len(records)} records, "
                            f"{len(all_chunk_results)} chunks scored")

        # Save pickle cache
        os.makedirs(os.path.dirname(output_pkl) or ".", exist_ok=True)
        with open(output_pkl, "wb") as f:
            pickle.dump(all_chunk_results, f)
        logger.info(f"Cached benchmark results to {output_pkl}")

    # Always write CSV (from cached or fresh data)
    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    with open(output_csv, "w") as f:
        f.write("record_id,chunk_idx,start_token,end_token,n_tokens,npr,"
                "orig_logrank,mean_p_logrank,low_conf,"
                "overlaps_mgc,fully_in_mgc,n_mgc_tokens_in_chunk,"
                "mgc_start_token,mgc_end_token,"
                "predict_mgc_youden,predict_mgc_highconf\n")
        for r in all_chunk_results:
            pred_youden = (not r["low_conf"]) and (not math.isnan(r["npr"])) and (r["npr"] > args.threshold_YOUDEN)
            pred_high   = (not r["low_conf"]) and (not math.isnan(r["npr"])) and (r["npr"] > args.threshold)
            f.write(f"{r['record_id']},{r['chunk_idx']},{r['start_token']},{r['end_token']},"
                    f"{r['n_tokens']},{r['npr']:.6f},{r['orig_logrank']:.6f},{r['mean_p_logrank']:.6f},"
                    f"{int(r['low_conf'])},{int(r['overlaps_mgc'])},{int(r['fully_in_mgc'])},"
                    f"{r['n_mgc_tokens_in_chunk']},{r['mgc_start_token']},{r['mgc_end_token']},"
                    f"{int(pred_youden)},{int(pred_high)}\n")
    logger.info(f"Wrote benchmark CSV to {output_csv}")

    # Quick summary
    n_chunks = len(all_chunk_results)
    n_valid = sum(1 for r in all_chunk_results if not r["low_conf"] and not math.isnan(r["npr"]))
    n_pred_youden = sum(
        1 for r in all_chunk_results
        if not r["low_conf"] and not math.isnan(r["npr"]) and r["npr"] > args.threshold_YOUDEN
    )
    n_pred_high = sum(
        1 for r in all_chunk_results
        if not r["low_conf"] and not math.isnan(r["npr"]) and r["npr"] > args.threshold
    )
    n_overlap = sum(1 for r in all_chunk_results if r["overlaps_mgc"])

    print("\n" + "=" * 70)
    print("                    BATCH BENCHMARK SUMMARY")
    print("=" * 70)
    print(f"  Total chunks scored:           {n_chunks}")
    print(f"  Valid scores (not low_conf):   {n_valid}")
    print(f"  Chunks overlapping MGC:        {n_overlap}")
    print(f"  Flagged (NPR > {args.threshold_YOUDEN:.4f}): {n_pred_youden}")
    print(f"  Flagged (NPR > {args.threshold:.4f}):       {n_pred_high}")
    print("=" * 70)
```

### Step 3 — Add the mode dispatcher to `main()`

Near the top of `main()`, before the existing `--interactive` check:

```python
if getattr(args, 'batch_benchmark', False):
    cache_dir, _, _ = preprocess_and_save(args)
    model_config = {'cache_dir': cache_dir}

    logger.info("Batch benchmark mode: loading base scoring model only...")
    model_config = load_base_model_and_tokenizer(args, model_config)

    run_batch_benchmark(args, model_config)
    return
```

### Step 4 — Create `run6-batch-benchmark.sh`

Following the established pattern:

```bash
#!/bin/bash
# Run DetectCodeGPT against the level1 benchmark, producing per-chunk NPR scores.

set -euo pipefail

# =====================================================================
# Configuration
# =====================================================================

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
OUTPUT_ROOT="${PROJECT_ROOT}/output"

CUDA_DEVICE=0
DATASET_NAME="CodeSearchNet"
GEN_MODEL="CodeLlama-7b-hf"
GEN_MAX_NUM="2000"
GEN_TEMPERATURE="0.2"
DATASET_KEY="${GEN_MODEL}-${GEN_MAX_NUM}-tp${GEN_TEMPERATURE}"
COMPLEXITY="level1"

BASE_MODEL_NAME="codellama/CodeLlama-7b-hf"
N_PERTURBATIONS=50
MAX_LEN=128
THRESHOLD_YOUDEN=1.3875
THRESHOLD_HIGH=1.60

# Toggle: set to a pickle path to skip scoring and just regenerate CSV/metrics
LOAD_CACHED=""

BENCHMARK_JSONL="${OUTPUT_ROOT}/${DATASET_NAME}/${DATASET_KEY}/outputs_530_benchmark_${COMPLEXITY}.jsonl"
OUTPUT_NAME="benchmark_${COMPLEXITY}_${GEN_MODEL,,}"
TIMESTAMP=$(date +%m-%d_%H:%M)
LOG_FILE="${LOG_DIR}/${OUTPUT_NAME}_${TIMESTAMP}.log"

# =====================================================================
# Pre-flight
# =====================================================================

echo "=== Batch benchmark configuration ==="
echo "  BENCHMARK_JSONL:  ${BENCHMARK_JSONL/${PROJECT_ROOT}/PRJ}"
echo "  BASE_MODEL:       ${BASE_MODEL_NAME}"
echo "  N_PERTURBATIONS:  ${N_PERTURBATIONS}"
echo "  MAX_LEN:          ${MAX_LEN}"
echo "  CUDA_DEVICE:      ${CUDA_DEVICE}"
echo "  OUTPUT_NAME:      ${OUTPUT_NAME}"
echo "  LOG_FILE:         ${LOG_FILE/${PROJECT_ROOT}/PRJ}"
[[ -n "${LOAD_CACHED}" ]] && echo "  LOAD_CACHED:      ${LOAD_CACHED}"
echo "===================================="
echo ""

if [[ ! -f "${BENCHMARK_JSONL}" ]]; then
    echo "ERROR: benchmark JSONL not found:"
    echo "  ${BENCHMARK_JSONL}"
    exit 1
fi

cd "${PROJECT_ROOT}"
mkdir -p "${LOG_DIR}"
cd code-detection

export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"

LOAD_FLAG=""
if [[ -n "${LOAD_CACHED}" ]]; then
    LOAD_FLAG="--load_benchmark_results ${LOAD_CACHED}"
fi

python main.py \
    --batch_benchmark \
    --benchmark_jsonl "${BENCHMARK_JSONL}" \
    --base_model_name "${BASE_MODEL_NAME}" \
    --n_perturbation_list "${N_PERTURBATIONS}" \
    --max_len "${MAX_LEN}" \
    --threshold "${THRESHOLD_HIGH}" \
    --threshold_YOUDEN "${THRESHOLD_YOUDEN}" \
    --output_name "${OUTPUT_NAME}" \
    --pct_words_masked 0.5 \
    --pct_identifiers_masked 0.75 \
    --span_length 2 \
    --batch_size 50 \
    --chunk_size 10 \
    --baselines "LRR,DetectGPT,NPR" \
    --perturb_type "random-insert-space+newline" \
    ${LOAD_FLAG} \
    2>&1 | tee "${LOG_FILE}"
```

## What the output CSV looks like

Each chunk gets one row. Key columns:

| Column | Meaning |
|---|---|
| `record_id`, `chunk_idx` | Identifiers |
| `start_token`, `end_token`, `n_tokens` | Chunk token range |
| `npr`, `orig_logrank`, `mean_p_logrank` | Raw detector outputs |
| `overlaps_mgc`, `fully_in_mgc` | Ground truth: is this chunk inside MGC? |
| `n_mgc_tokens_in_chunk` | How many of this chunk's tokens are actually MGC |
| `predict_mgc_youden`, `predict_mgc_highconf` | Predictions at the two thresholds |

With this CSV, your eventual `evaluate_benchmark.py` is a one-page script that loads CSV, computes:
- Per-chunk precision/recall (predicted vs `overlaps_mgc`)
- Per-record token-level precision/recall (predicted token ranges vs ground-truth MGC range)
- Per-record IoU

## What I'd watch for during the run

After the first ~50 records:
- **What's the NPR distribution looking like?** If most chunks are scoring near 1.0 (no separation between HWC and MGC content), something's off.
- **Are MGC chunks scoring high?** If `fully_in_mgc=True` chunks have mean NPR around 1.5-2.0 and `overlaps_mgc=False` chunks have mean NPR around 1.0-1.2, the detector is working as expected.
- **Are there false positives in `prompt` chunks?** Prompt regions are real code (function signatures + docstrings). They might score near HWC values. If they're spiking above threshold, that's interesting and worth noting.

## Optional: smaller test run first

Before committing 90 minutes, you could do a test run on the first 10 records to confirm the pipeline works end-to-end:

```bash
# Quick way: head the benchmark JSONL to a temp file
head -10 "${BENCHMARK_JSONL}" > /tmp/benchmark_test.jsonl
# Then run with --benchmark_jsonl /tmp/benchmark_test.jsonl
```

That's ~3 minutes instead of 90. Catches any bugs in the run loop before you commit to the full thing.

## Where this leaves us

After the run completes you have:
1. A CSV ready for evaluation analysis
2. A pickle cache for future threshold experiments (~1 sec to re-run)
3. Concrete data to answer "does the chunker localize MGC well on a 530-record benchmark?"



