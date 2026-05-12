cd code-detection

python -c "
import sys
sys.argv = [
    'main.py',
    '--dataset', 'CodeSearchNet',
    '--dataset_key', 'CodeLlama-7b-hf-500-tp0.2',
    '--data_path', '/home/user1-system12/project-workspace/detect_code_gpt/output/CodeSearchNet/CodeLlama-7b-hf-500-tp0.2/outputs.txt',
    '--n_samples', '10',
]
from main import setup_args, generate_data
args = setup_args()
print('Parsed args:')
print(f'  dataset:                {args.dataset}')
print(f'  dataset_key:            {args.dataset_key}')
print(f'  data_path:              {args.data_path}')
print(f'  n_samples:              {args.n_samples}')
print(f'  base_model_name:        {args.base_model_name}')
print(f'  mask_filling_model:     {args.mask_filling_model_name}')
print(f'  n_perturbation_list:    {args.n_perturbation_list}')
print(f'  pct_words_masked:       {args.pct_words_masked}')
print(f'  pct_identifiers_masked: {args.pct_identifiers_masked}')
print(f'  perturb_type:           {args.perturb_type}')
print(f'  baselines:              {args.baselines}')
print()
print('Testing generate_data()...')
data = generate_data(args.dataset, args.dataset_key,
                     max_num=10, min_len=args.min_len, max_len=args.max_len,
                     max_comment_num=args.max_comment_num, max_def_num=args.max_def_num,
                     cut_def=args.cut_def, max_todo_num=args.max_todo_num,
                     data_path=args.data_path)
print(f'Loaded {len(data[\"original\"])} originals, {len(data[\"sampled\"])} samples')
print()
print('--- First human (original) sample (first 200 chars): ---')
print(data['original'][0][:200])
print()
print('--- First machine (sampled) sample (first 200 chars): ---')
print(data['sampled'][0][:200])
print()
print('Dry run PASSED. Ready for full launch.')
"