cd ~/project-workspace/detect_code_gpt/code-detection
python -c "
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
import torch
import transformers

print('Loading codet5p-770m (fixed: no token-ID overrides)...')
m = transformers.AutoModelForSeq2SeqLM.from_pretrained(
    'Salesforce/codet5p-770m',
    cache_dir=os.path.expanduser('~/.cache/huggingface/hub'),
    device_map='auto',
    torch_dtype=torch.float16,
    trust_remote_code=True,
)
print(f'Loaded. Vocab size: {m.config.vocab_size}')
print(f'decoder_start: {m.config.decoder_start_token_id}')
print(f'pad: {m.config.pad_token_id}')

tok = transformers.AutoTokenizer.from_pretrained('Salesforce/codet5p-770m', model_max_length=512)
print(f'Tokenizer vocab: {tok.vocab_size}')

print()
print('--- Testing a real mask-fill generation ---')
text = 'def hello(<extra_id_0>):\n    return <extra_id_1>'
inputs = tok(text, return_tensors='pt').to('cuda')
print(f'Input shape: {inputs.input_ids.shape}')
print(f'Input IDs sample: {inputs.input_ids[0][:10].tolist()}')
print(f'Max input ID: {inputs.input_ids.max().item()}')
print(f'Min input ID: {inputs.input_ids.min().item()}')

stop_id = tok.encode('<extra_id_1>')[0]
print(f'Stop ID: {stop_id}')

print('Generating...')
with torch.no_grad():
    outputs = m.generate(
        **inputs,
        max_length=64,
        do_sample=True,
        top_p=1.0,
        num_return_sequences=1,
        eos_token_id=stop_id,
        temperature=1.0,
    )

print(f'Output IDs: {outputs[0].tolist()}')
print(f'Decoded: {tok.decode(outputs[0], skip_special_tokens=False)}')
print()
print('SUCCESS — codet5p mask-fill generation works.')
"