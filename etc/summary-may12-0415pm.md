Here is the summary of our technical progress and experiments since 3:00 PM today:

### 1. **System Optimization & Error Resolution**

* **Token ID & Vocabulary Fix**: We identified that `loadmodel.py` was hardcoding a `decoder_start_token_id` of **50256**, which caused an index out-of-bounds error because the **CodeT5+ 770m** model has a vocabulary of only **32,100**. We updated the script to use the correct IDs (0) from the model config.
* **GPU Stability**: To resolve `CUBLAS` execution failures on the **RTX 6000 Ada** GPUs, we switched the model precision from `float16` to **`bfloat16`**, which is natively supported and more stable for the Ada Lovelace architecture.
* 
**Dependency Updates**: We resolved an `ImportError` by installing **`sentencepiece`** and `protobuf`, which are required for the Llama tokenizer. We then updated `requirements.txt` and `0-install.txt` to include these fixes for future environments.



---

### 2. **Experimental Results (DetectCodeGPT)**

* **Data Preparation**: We successfully remapped and processed the **CodeSearchNet** Python corpus, bypassing previous "403 Forbidden" errors by using the Hugging Face hub.
* **Successful Detection Run**: We executed the detection pipeline using **CodeLlama-7B** and the stylized perturbation strategy (inserting spaces and newlines).
* **High Accuracy**: The experiment confirmed the **ICSE 2025** paper's findings, with **DetectCodeGPT (NPR)** achieving a top **ROC AUC of 0.8953**. This outperformed standard baselines like Log Likelihood Ratio (LRR) and standard Log Rank.

---

### 3. **Future Scaling & Methodology**

* **Sample Size Strategy**: To increase the valid sample size from **131** to near **500**, we decided on "Option 2"—increasing the initial sample pool to **2,000** to account for the strict filtering of complex functions and docstrings.
* **Hardware Setup**: Although the system has two GPUs, we confirmed that using **GPU 0** exclusively is the most stable approach to avoid the `DeferredCudaCallError` encountered during multi-GPU initialization.
* **Validation of Finding 5**: The results successfully validated the theory that machine-generated code is more "natural" and predictable than human code, particularly in stylistic elements like whitespaces.

Everything is now configured for high-scale, stable detection runs. Would you like to start the 2,000-sample scaled execution now?