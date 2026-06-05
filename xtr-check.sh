cd ~/project-workspace/detect_code_gpt/code-detection
cp baselines/utils/loadmodel.py baselines/utils/loadmodel.py.bak_gptoss

python - <<'PY'
from pathlib import Path

p = Path("baselines/utils/loadmodel.py")
s = p.read_text()

needle = "    elif '20b' in name:\n"
insert = '''    elif 'gpt-oss' in name.lower():
        # GPT-OSS models need the native Transformers loader.
        # Do not route openai/gpt-oss-120b through the generic "20b" branch:
        # "120b" contains "20b", and that branch is hardcoded for GPT-NeoX.
        n_gpu = torch.cuda.device_count()
        max_memory = {i: "44GiB" for i in range(n_gpu)}
        max_memory["cpu"] = "128GiB"

        base_model = transformers.AutoModelForCausalLM.from_pretrained(
            name,
            cache_dir=model_config["cache_dir"],
            torch_dtype="auto",
            device_map="auto",
            max_memory=max_memory,
            trust_remote_code=True,
        )
        # NOTE: do not call base_model.to(args.DEVICE) after device_map="auto".

'''

if insert.strip() in s:
    print("gpt-oss branch already present")
else:
    if needle not in s:
        raise SystemExit("Could not find insertion point")
    s = s.replace(needle, insert + needle)
    p.write_text(s)
    print("patched", p)
PY