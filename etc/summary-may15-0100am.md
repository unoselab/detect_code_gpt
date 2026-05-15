## 1. `run_interactive_mode`: prototype for MGC localization

The `run_interactive_mode` function extends DetectCodeGPT from batch-level evaluation to **single-snippet, chunk-level inspection**. With the `--interactive` flag, the program skips the full dataset pipeline, loads only the base scoring model, and analyzes one pasted code snippet at a time.

Instead of producing only a whole-function verdict, the interactive mode splits long code into **128-token chunks**, matching the calibration length used in the batch experiment. Each chunk receives its own NPR score, making the result directly comparable to the learned thresholds:

```text
Youden’s J threshold = 1.3875
High-confidence threshold = 1.60
```

## 2. From classification to localization

The newer version reframes interactive detection as **MGC localization**. Rather than asking only whether a function is machine-generated, it asks:

```text
Which section of this function is likely machine-generated?
```

For each chunk, the tool reports token offsets, NPR, and a verdict:

```text
HWC-leaning
MGC SUSPECT [WARN]
MGC SUSPECT [HIGH]
UNSCORABLE
```

This makes the tool useful for mixed HWC/MGC code, where only part of a function may be generated.

## 3. Why this matters for the chunk 5 / chunk 6 case

The chunk 5 and chunk 6 example shows the limitation of pure thresholding:

```text
Chunk 5: high NPR, detected as MGC
Chunk 6: weaker NPR, possibly missed
True region: chunks 5–6 form one continuous MGC block
```

The interactive mode exposes this pattern by showing NPR scores chunk by chunk. It can identify the strongest suspicious chunk, while also revealing nearby chunks that may need boundary expansion.

## 4. Local-deviation signal

The updated interactive mode also adds a **local-deviation analysis**. It compares each chunk’s NPR against the function-wide median using MAD. This helps detect chunks that may not exceed the global threshold but still stand out from the surrounding code.

Thus, the localization logic uses two signals:

| Signal             | Role                                                         |
| ------------------ | ------------------------------------------------------------ |
| Absolute threshold | Finds chunks above calibrated NPR cutoffs                    |
| Local deviation    | Finds chunks that spike relative to the surrounding function |

## 5. Contribution statement

This gives us a stronger research story:

```text
We extend DetectCodeGPT from whole-sample detection to mixed-authorship localization. The interactive mode splits a function into calibrated chunks, computes NPR per chunk, and identifies suspicious MGC seed regions. Data-flow or dependency analysis can then expand these seeds to recover the full generated-code region, including neighboring chunks with weaker NPR signals.
```

Short version:

```text
DetectCodeGPT finds the spike; program analysis recovers the boundary.
```

`run_interactive_mode` is the working prototype that makes this visible chunk by chunk.


----

The key issue is that **chunks 5 and 6 were one continuous MGC block, but only chunk 5 was detected**.

```text
Chunk 5: NPR = 1.9534  → detected as MGC
Chunk 6: NPR = 1.3188  → missed
```

The most likely reason is a **short-chunk size effect**. Chunk 6 had only about **38 tokens**, so its NPR score became noisy and drifted toward 1.0. Because the thresholds were calibrated on **128-token chunks**, applying the same threshold to a short tail chunk can under-detect real MGC.

Two possible explanations were considered:

1. **Size effect:** chunk 6 is too short, so perturbations have limited impact and NPR weakens.
2. **Boundary effect:** chunk 6 captures only the tail of the generated block, where the machine-code signal may naturally fade.

The current evidence points more strongly to the **size effect**.

Recommended next steps:

1. **Concatenation test:** combine chunks 5 and 6 and score them as one block.

   * If NPR rises above 1.6, chunk 6 was missed mainly because it was too short.
   * If NPR stays low, the MGC signal genuinely weakens near the boundary.

2. **Add tail merging:** if the final chunk is too short, merge it into the previous chunk instead of scoring it separately.

3. **Add overlapping windows:** use 128-token windows with a smaller stride, such as 32 tokens, so every region is scored inside multiple full-length contexts.

4. **Use data-flow analysis after NPR detection:** NPR finds suspicious regions, while data-flow/dependency analysis can refine the exact generated-code boundary.

The updated takeaway is:

```text
DetectCodeGPT finds the statistical spike.
Length-aware chunking prevents short-tail misses.
Overlapping windows improve boundary coverage.
Data-flow analysis refines the final MGC region.
```
