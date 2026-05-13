cd ~/project-workspace/detect_code_gpt/code-detection
python -c "
import sys
sys.argv = [
    'main.py',
    '--dataset', 'CodeSearchNet',
    '--dataset_key', 'CodeLlama-7b-hf-2000-tp0.2',
    '--data_path', '/home/user1-system12/project-workspace/detect_code_gpt/output/CodeSearchNet/CodeLlama-7b-hf-2000-tp0.2/outputs.txt',
    '--n_samples', '500',
]
from main import setup_args, generate_data
args = setup_args()
data = generate_data(args.dataset, args.dataset_key,
                     max_num=500, min_len=args.min_len, max_len=args.max_len,
                     max_comment_num=args.max_comment_num, max_def_num=args.max_def_num,
                     cut_def=args.cut_def, max_todo_num=args.max_todo_num,
                     data_path=args.data_path)
print(f'After filtering: {len(data[\"original\"])} originals, {len(data[\"sampled\"])} samples')
print('Target: 500+ pairs')
"