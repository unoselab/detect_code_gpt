## The paper
**"Between Lines of Code: Unraveling the Distinct Patterns of Machine and Human Programmers"** (ICSE 2025, Shi et al.)

Studies how LLM-generated code differs from human-written code across lexical diversity, conciseness, and naturalness. Proposes **DetectCodeGPT**: a zero-shot detector that perturbs code by inserting random whitespace/newlines (instead of MLM token replacement like DetectGPT), then measures how much the NPR score drops. Reports 0.8308 average AUROC, beating prior methods by 7.6%.

## What we set out to reproduce
**Single-model first pass:** CodeLlama-7B on CodeSearchNet at T=0.2 → expected AUROC ≈ 0.9095 (paper's Table IV).

## Your system
- **GPUs:** 2× NVIDIA RTX 6000 Ada (49 GB each — 2× the paper's 4090s)
- **CPU:** AMD Threadripper 7985WX (128 threads)
- **RAM:** 251 GB
- **OS:** Ubuntu 22.04.5
- **CUDA driver:** 12.4
- **Disk:** 1.4 TB free on NVMe — huge headroom

## Phase 1 — Environment setup (the part with the most friction)

| Step | What we did | Outcome |
|---|---|---|
| Python version | Picked 3.11 over paper's 3.9.7 (EOL since Oct 2025) | ✓ |
| Initial pip install | Failed with `BrokenPipeError` on cudnn download; `requirements.txt` had no pins → pulled torch 2.11, transformers 5.x (would break paper's code) | ✗ |
| Pinned requirements | Rewrote `requirements.txt` with versions contemporary to the paper (torch 2.1.2, transformers 4.36.2, datasets 2.16.1, numpy 1.26.3, tree-sitter 0.20.4, etc.) | ✓ |
| PyTorch install | Used `conda install pytorch==2.1.2 pytorch-cuda=12.1 -c pytorch -c nvidia` instead of pip → cleaner CUDA handling | ✓ |
| MKL ABI bug | `import torch` failed with `undefined symbol: iJIT_NotifyEvent` — conda's default pulled MKL 2025.0.0 which removed that symbol | ✗ |
| MKL fix | Downgraded to MKL 2023.1.0 (latest version that still has the symbol — Anaconda skipped MKL 2024.x on pkgs/main) | ✓ |
| GPU verify | PyTorch 2.1.2 + CUDA 12.1 + cuDNN 8.9.2, both RTX 6000 Ada visible | ✓ |
| Env snapshot | Saved `detectcodegpt_env_snapshot.yml` + pip freeze for reproducibility | ✓ |

## Phase 2 — Data and model

| Step | What we did | Outcome |
|---|---|---|
| Read `generate.py` | Confirmed it expects `data/CodeSearchNet/python/train.jsonl` with field `original_string` | ✓ |
| Tried S3 download | `wget https://s3.amazonaws.com/code-search-net/CodeSearchNet/v2/python.zip` → **403 Forbidden** (GitHub revoked S3 access when they archived the repo in April 2023) | ✗ |
| HuggingFace mirror | Used `code-search-net/code_search_net` on HF Hub — has schema mismatch (`whole_func_string` vs `original_string`) | — |
| Conversion script | Wrote `scripts/download_codesearchnet.py` to pull via HF and remap fields → produced `train.jsonl` with 412,178 Python functions (1.1 GB) | ✓ |
| CodeLlama-7B | Turns out `codellama/CodeLlama-7b-hf` is **not gated** (community-uploaded mirror) — downloaded anonymously, 17 files (~13.5 GB) in **1m 56s** at ~42 MB/s | ✓ |
| Model sanity check | Tokenizer (vocab 32016), model loaded (6.739 B params), GPU memory 13.75 GB, generated valid Fibonacci code | ✓ |

## Phase 3 — Generation run

| Step | What we did | Outcome |
|---|---|---|
| tmux session | Created `codellama0` tmux session — survives SSH disconnect | ✓ |
| First launch | Started but `tee logs/...` failed because `logs/` didn't exist; killed it to restart with logging | ✗ |
| Clean restart | `mkdir -p logs` then relaunched with `2>&1 \| tee logs/codellama_csn_t02.log` | ✓ |
| **Currently running** | 500 samples, ~2.45 sec/iter, ETA ~20 minutes total. Same 500 prompts as first run (seed=42 in `generate.py`) | ⏳ |

## Command currently executing

```bash
python code-generation/generate.py \
    --path data/CodeSearchNet \
    --model_name codellama/CodeLlama-7b-hf \
    --max_num 500 \
    --temperature 0.2 \
    --max_length 128 \
    --batch_size 1 \
    2>&1 | tee logs/codellama_csn_t02.log
```

## Expected output files when it finishes

```
output/CodeSearchNet/CodeLlama-7b-hf-500-tp0.2/
├── outputs.txt        ← 500 lines of JSON: {prompt, output, solution}
└── outputs_v2.txt     ← human-readable version

logs/
└── codellama_csn_t02.log
```

## What's next (Phase 4 — Detection)

Once generation finishes, run `code-detection/main.py` to:
1. Score each of the 500 human samples + 500 machine samples with DetectCodeGPT (NPR + space/newline perturbations)
2. Compute AUROC
3. Compare against paper's reported **0.9095** for this exact configuration

That's where the actual paper's claim gets validated.

## Key takeaways from this setup journey

1. **Old reproduction artifacts age fast.** S3 buckets disappear, library versions break ABIs (MKL 2025 dropping symbols), license gates appear and vanish. Two-year-old papers already have brittle infrastructure.
2. **Pin everything.** The blank `requirements.txt` would have silently installed transformers 5.x and broken the paper's model loading code in ways that would only surface at runtime.
3. **conda for CUDA-heavy stacks, pip for Python pure stuff.** That split worked here.
4. **tmux + tee from the start.** Long runs on remote servers need both — survive disconnects AND have a permanent record.

Currently waiting on generation to finish (~20 min total, running in tmux). After that, we kick off detection and finally see if the AUROC lands near 0.91.