We reviewed the ICSE 2025 paper **“Between Lines of Code: Unraveling the Distinct Patterns of Machine and Human Programmers”**, which proposes **DetectCodeGPT**, a zero-shot detector for machine-generated code. The method perturbs code by inserting spaces and newlines, then measures changes in normalized perturbed log-rank. The paper reports an average AUROC of **0.8308**, and for the specific reproduction target **CodeSearchNet + CodeLlama-7B + T=0.2**, it reports **AUROC ≈ 0.9095**.

## What has been reproduced so far

The reproduction target was narrowed to a **single-model first pass**:

```text
CodeSearchNet Python + CodeLlama-7B + temperature 0.2 + 500 samples
```

The system used for reproduction is stronger than the paper’s hardware:

```text
2× NVIDIA RTX 6000 Ada, 49 GB each
AMD Threadripper 7985WX
251 GB RAM
Ubuntu 22.04.5
CUDA driver 12.4
```

The environment setup required several fixes:

* Python 3.11 was used instead of the paper’s older Python 3.9.7.
* The original unpinned `requirements.txt` was unsafe because it would pull newer incompatible packages.
* Dependencies were pinned around the paper-era stack, including PyTorch 2.1.2 and Transformers 4.36.2.
* PyTorch was installed via conda with CUDA 12.1.
* An MKL ABI issue caused `import torch` to fail with `undefined symbol: iJIT_NotifyEvent`.
* This was fixed by downgrading MKL to 2023.1.0.
* Both RTX 6000 Ada GPUs were successfully visible to PyTorch.

## Dataset and model setup

The paper’s expected CodeSearchNet data path is:

```text
data/CodeSearchNet/python/train.jsonl
```

The `generate.py` script expects each record to contain:

```text
original_string
```

The original CodeSearchNet S3 download failed with **403 Forbidden**, so the Hugging Face mirror `code-search-net/code_search_net` was used instead. Since the HF schema uses `whole_func_string`, a conversion script was written to remap the data into the expected `original_string` format.

The resulting dataset contained:

```text
412,178 Python functions
```

From the generation log:

```text
Failed parse count: 4,573
Successful parse count: 407,605
Filtered prompt-solution pairs: 367,484
Sampled examples: 500
```

The model used was:

```text
codellama/CodeLlama-7b-hf
```

It loaded successfully and generated a sanity-check Fibonacci example.

## How `generate.py` constructs the prompt

The key question was whether the script explicitly asks the model to generate code using the function signature and docstring.

The answer: **yes, but implicitly**.

For CodeSearchNet, `load_data()` constructs each prompt like this:

```python
data['original_string'] = data['original_string'].replace("'''", '"""')
prompt = data['original_string'].split('"""')[0] + '"""' + data['original_string'].split('"""')[1] + '"""'
solution = data['original_string'].split('"""')[2]
```

So the prompt becomes:

```python
def function_name(...):
    """
    docstring text
    """
```

The solution becomes the remaining human-written function body after the docstring.

There is **no explicit natural-language instruction** like:

```text
Please generate the implementation of this function.
```

Instead, this is a **causal language model code-completion task**. The model receives the function signature and docstring as a raw Python prefix and continues the code.

Inside `generate_hf()`, prompts are tokenized and passed to the model:

```python
input_ids = [
    tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_length).input_ids
    for prompt in prompts
]
```

Then the model generates a continuation:

```python
outputs = model.generate(
    input_ids,
    do_sample=do_sample,
    max_length=max_length_sample + input_ids_len,
    top_p=top_p,
    temperature=temperature,
    pad_token_id=tokenizer.pad_token_id,
    use_cache=True
)
```

Only the newly generated continuation is decoded:

```python
decoded_output = tokenizer.decode(outputs[0, input_ids_len:])
```

So the task is best described as:

> Given a Python function signature and docstring, generate the function body.

## Generation run

The generation command used was:

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

The output directory was:

```text
output/CodeSearchNet/CodeLlama-7b-hf-500-tp0.2/
├── outputs.txt
└── outputs_v2.txt
```

The run completed successfully.

## Execution time

From the log:

```text
Script start: 2026-05-12 01:16:47.471
Final write: 2026-05-12 01:37:24.381
```

So the total wall-clock runtime was:

```text
20 minutes 36.91 seconds
```

The generation loop itself reported:

```text
500/500 [20:28<00:00, 2.46s/it]
```

So the timing can be reported as:

| Measurement             |             Duration |
| ----------------------- | -------------------: |
| Full script runtime     | **20 min 36.91 sec** |
| Generation loop only    |    **20 min 28 sec** |
| Average generation time |  **2.46 sec/sample** |

## Important warning in the log

The log repeatedly showed:

```text
The attention mask and the pad token id were not set.
Setting `pad_token_id` to `eos_token_id`:2 for open-end generation.
```

This happens because the script does not explicitly set `pad_token_id` or pass `attention_mask` for CodeLlama.

This is probably not fatal in this run because generation is done one prompt at a time, so there is no batch padding issue. Still, it should be noted as a reproduction caveat.

A future cleanup patch would be:

```python
elif "llama" in model_name.lower() or "wizard" in model_name.lower():
    tokenizer.pad_token_id = tokenizer.eos_token_id
    tokenizer.padding_side = "left"
```

and generation could pass `attention_mask` explicitly.

## `outputs.txt` vs. `outputs_v2.txt`

Both files contain the same logical information:

```text
prompt
output
solution
```

The difference is format and purpose.

### `outputs.txt`

This is the machine-readable JSONL file. Each line is one JSON object:

```json
{"prompt": "...", "output": "...", "solution": "..."}
```

This is the file that detection scripts should use.

### `outputs_v2.txt`

This is a human-readable version. It prints each example in blocks:

```text
--------------------
Prompt:
...
----------
Output:
...
----------
Solution:
...
```

It is meant for manual inspection and debugging, not for the detection pipeline.

## Observed quality of generated outputs

The generated outputs are plausible for CodeLlama-7B at T=0.2, but several patterns appeared:

* Many generations are incomplete because output length is capped at 128 tokens.
* Some generations continue into the next function definition.
* Some continue docstring text instead of immediately producing executable code.
* Some outputs are syntactically invalid, such as `raise *args, **kwargs`.
* Some outputs contain CodeLlama’s EOS token like `</s>`.

These issues seem to result from the original script design, especially because:

* `max_length_sample=128`
* the `eos_id_list` for stopping at `def` is only used when `max_length_sample >= 256`
* the truncation function only removes `<|endoftext|>`, not `</s>` or a new `def`

For strict reproduction, we decided not to modify the script before the first AUROC result.

## Important detail about `batch_size`

For CodeLlama, the `--batch_size` argument is effectively ignored.

In `generate_hf()`, models whose names include `starcoder`, `llama`, `wizard`, or `codegen2` are processed one prompt at a time:

```python
for input_ids in tqdm(input_ids, ncols=50):
```

So even if `--batch_size` were changed, the CodeLlama branch would still generate sequentially.

## Current status

The reproduction has completed:

```text
Phase 1: environment setup
Phase 2: data and model setup
Phase 3: CodeLlama generation
```

The generated data is ready:

```text
output/CodeSearchNet/CodeLlama-7b-hf-500-tp0.2/outputs.txt
```

The next step is:

```text
Phase 4: run code-detection/main.py
```

That phase should score the 500 human samples and 500 machine samples using DetectCodeGPT, compute AUROC, and compare against the paper’s reported **0.9095** for CodeSearchNet + CodeLlama-7B + T=0.2.
