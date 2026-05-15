# **Building a mixed HWC/MGC localization benchmark**.

First, we created the filtered 530-pair dataset from the original 2000 CodeLlama generations. The key fix was using `source_line_no` from `npr_scores_codellama-7b-hf_csn_t02_n2000_run.csv` to map each filtered row back to the correct line in `outputs.txt`, rather than assuming the CSV index matched the original file line. The resulting file is:

```text
output/CodeSearchNet/CodeLlama-7b-hf-2000-tp0.2/outputs_530_filter.jsonl
```

Each record contains:

```text
prompt   = function header + docstring
solution = HWC
output   = MGC
```

We then cleaned up `run4-selection.sh`. We made it variable-driven, added project/run identity variables, used absolute paths internally, and improved printed output by replacing the long project root with `PRJ`. We also updated `create_outputs_530_filter.py` so its own output message prints `PRJ/...` consistently via a `--project_root` argument.

After that, we planned the first benchmark dataset for MGC localization. The easiest version, now called **level1**, simply concatenates:

```text
mixed_code = prompt + solution + output
```

The goal is to test whether `code-detection/main.py` can isolate the final `output` region as MGC while not flagging the `solution` region as MGC. We renamed the benchmark generator concept from `create_mix_easy.py` to:

```text
code-selection/generate_benchmark.py
```

and added a `--complexity` option, where:

```text
--complexity level1
```

means the simple `prompt + HWC + MGC` benchmark.

We also discussed ground-truth metadata. The benchmark should store region spans for:

```text
prompt
HWC
MGC
```

using character offsets, and also token offsets where possible, so later we can evaluate localization with overlap metrics such as precision, recall, and F1 over detected versus true MGC regions.

Finally, we checked the tokenization mismatch between `generate_benchmark.py` and `run_interactive_mode()` in `main.py`. We noticed that the benchmark script used regex tokenization:

```python
re.finditer(r"\S+", mixed_code)
```

but `main.py` interactive chunking used:

```python
code_raw.split(" ")
```

Because the learned thresholds came from batch mode using `split(" ")` and 128-token chunks, we decided the benchmark token-span logic should also follow `split(" ")`, not regex whitespace tokenization. The principle we settled on is:

```text
Use split(" ") for threshold-calibrated token offsets.
Use character spans for localization evaluation.
```

