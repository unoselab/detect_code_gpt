python -c "
import json
path = '/home/user1-system12/project-workspace/detect_code_gpt/output/CodeSearchNet/CodeLlama-7b-hf-2000-tp0.2/outputs_530_benchmark_level1.jsonl'

n_checked = 0
n_off_by_one_or_two = 0
n_wildly_wrong = 0

with open(path) as f:
    for i, line in enumerate(f):
        r = json.loads(line)
        tokens = r['mixed_code'].split(' ')

        # MGC region as ground truth
        mgc_region = next(reg for reg in r['regions'] if reg['label'] == 'MGC')
        mgc_tokens_slice = tokens[mgc_region['start_token']:mgc_region['end_token']]
        mgc_reconstructed = ' '.join(mgc_tokens_slice)

        # The MGC field itself, for comparison
        mgc_original = r['mgc']

        # Character lengths should match within ~3 chars (boundary token may carry
        # a few chars from HWC's end into MGC's reconstruction).
        diff = abs(len(mgc_reconstructed) - len(mgc_original))
        if diff == 0:
            pass  # exact match
        elif diff <= 3:
            n_off_by_one_or_two += 1
        else:
            n_wildly_wrong += 1
            if n_wildly_wrong <= 3:
                print(f'Record {i}: MGC len mismatch: original={len(mgc_original)}, reconstructed={len(mgc_reconstructed)}, diff={diff}')
        n_checked += 1

print(f'Checked: {n_checked} records')
print(f'  Exact reconstruction: {n_checked - n_off_by_one_or_two - n_wildly_wrong}')
print(f'  Off by <=3 chars (boundary tokens): {n_off_by_one_or_two}')
print(f'  Off by >3 chars (real mismatch): {n_wildly_wrong}')
"