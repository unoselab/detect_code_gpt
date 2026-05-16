# 2026-05-12 msong: env vars MUST be set BEFORE any import that touches torch.
#   The original code had `import torch` (transitively via baselines.utils.run_baseline)
#   on line 4, BEFORE `os.environ["CUDA_VISIBLE_DEVICES"]` ran on line 25. So PyTorch's
#   CUDA context initialized with BOTH GPUs visible. Later, Accelerate's device_map="auto"
#   enumerated both GPUs, tried to probe GPU 1, and crashed with:
#     DeferredCudaCallError: device >= 0 && device < num_gpus ... device=1, num_gpus=
#   This block fixes that by setting env vars FIRST.
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import sys
from sklearn.neighbors import KernelDensity
from scipy.stats import norm
import math
from baselines.utils.run_baseline import get_roc_metrics, get_precision_recall_metrics, get_accurancy, run_baseline_threshold_experiment
import functools
import torch
from baselines.supervised import eval_supervised
from baselines.entropy import get_entropy
from baselines.rank import get_ranks, get_rank
from baselines.loss import get_ll, get_lls
import random
import re
import numpy as np
from identifier_tagging import get_identifier
import scipy.stats
from tqdm import tqdm
from loguru import logger
import matplotlib.pyplot as plt
from baselines.all_baselines import run_all_baselines
from baselines.utils.loadmodel import load_base_model_and_tokenizer, load_mask_filling_model
from baselines.utils.preprocessing import preprocess_and_save
import json
import argparse
import pickle


def setup_args():
    """Setup and parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=str, default="writing")
    parser.add_argument('--dataset_key', type=str, default="document")
    parser.add_argument('--pct_words_masked', type=float, default=0.5) # default=0.3
    parser.add_argument('--span_length', type=int, default=2)
    parser.add_argument('--n_samples', type=int, default=500) # default=5
    parser.add_argument('--n_perturbation_list', type=str, default="50") # default="10"
    parser.add_argument('--n_perturbation_rounds', type=int, default=1)
    parser.add_argument('--base_model_name', type=str, default="codellama/CodeLlama-7b-hf")
    parser.add_argument('--scoring_model_name', type=str, default="")
    parser.add_argument('--mask_filling_model_name', type=str, default="Salesforce/codet5p-770m") # default="Salesforce/CodeT5-large"
    parser.add_argument('--batch_size', type=int, default=50) # default=5
    parser.add_argument('--chunk_size', type=int, default=10) # default=20
    parser.add_argument('--n_similarity_samples', type=int, default=20)
    parser.add_argument('--int8', action='store_true')
    parser.add_argument('--half', action='store_true')
    parser.add_argument('--base_half', action='store_true')
    parser.add_argument('--do_top_k', action='store_true')
    parser.add_argument('--top_k', type=int, default=40)
    parser.add_argument('--do_top_p', action='store_true')
    parser.add_argument('--top_p', type=float, default=0.96)
    parser.add_argument('--output_name', type=str, default="test_ipynb")
    parser.add_argument('--openai_model', type=str, default=None)
    parser.add_argument('--openai_key', type=str)
    parser.add_argument('--DEVICE', type=str, default='cuda')
    parser.add_argument('--buffer_size', type=int, default=1)
    parser.add_argument('--mask_top_p', type=float, default=1.0)
    parser.add_argument('--mask_temperature', type=float, default=1.0)
    parser.add_argument('--pre_perturb_pct', type=float, default=0.0)
    parser.add_argument('--pre_perturb_span_length', type=int, default=5)
    parser.add_argument('--random_fills', action='store_true')
    parser.add_argument('--random_fills_tokens', action='store_true')
    parser.add_argument('--cache_dir', type=str, default="~/.cache/huggingface/hub")
    parser.add_argument('--prompt_len', type=int, default=30)
    parser.add_argument('--generation_len', type=int, default=200)
    parser.add_argument('--min_words', type=int, default=55)
    parser.add_argument('--temperature', type=float, default=1)
    parser.add_argument('--baselines', type=str, default="LRR,DetectGPT,NPR")
    parser.add_argument('--perturb_type', type=str, default="random-insert-space+newline") # default="random"
    parser.add_argument('--pct_identifiers_masked', type=float, default=0.75) # default=0.5
    parser.add_argument('--min_len', type=int, default=0)
    parser.add_argument('--max_len', type=int, default=128)
    parser.add_argument('--max_comment_num', type=int, default=10)
    parser.add_argument('--max_def_num', type=int, default=5)
    parser.add_argument('--cut_def', action='store_true')
    parser.add_argument('--max_todo_num', type=int, default=3)
    parser.add_argument('--data_path', type=str, default=None,
                        help='Full path to outputs.txt produced by generate.py. '
                             'If provided, overrides dataset/dataset_key/relative-path lookup.')

    # 2026-05-13 msong: skip baseline-only computations to save xx min on n=530/k=50 runs.
    parser.add_argument('--detectcodegpt_only', action='store_true',
                        help='Compute only DetectCodeGPT NPR (and free logrank baseline). '
                             'Skips unperturbed log likelihoods (Block 1, ~36s) and perturbed log '
                             'likelihoods (Block 3, ~32min). Saves ~50% of total runtime.')
    # 2026-05-13 msong: cache the results dict to disk so threshold experimentation doesn't
    # require re-running forward passes.
    parser.add_argument('--results_cache', type=str, default=None,
                        help='Path to pickle file to write results dict after scoring completes. '
                             'If not set, defaults to ../logs/results_cache_{output_name}.pkl')
    parser.add_argument('--load_cached_results', type=str, default=None,
                        help='Path to a results pickle from a previous run. If set, skips ALL '
                             'scoring and goes straight to AUROC + CSV + threshold computation '
                             '(~1 sec total). Useful for iterating on threshold logic.')
    parser.add_argument('--npr_csv_dir', type=str, default=None,
                        help='Directory to write per-sample NPR scores CSV. Defaults to ../logs/.')

    # 2026-05-14 msong, interactive mode
    parser.add_argument('--interactive', action='store_true',
                        help='Run in interactive mode to test a single code snippet.')
    parser.add_argument('--threshold', type=float, default=1.60, 
                        help='Threshold for NPR score in interactive mode (Default: 1.60 for High Confidence)')
    parser.add_argument('--threshold_youden', type=float, default=1.3875,
                    help="Youden's J threshold for NPR score in interactive mode "
                         "(Default: 1.3875 from the n=530 batch run)")

    # 2026-05-15 msong: batch-benchmark mode for MGC localization evaluation.
    parser.add_argument('--batch_benchmark', action='store_true',
                        help='Run detector across all records in a benchmark JSONL, '
                            'producing per-chunk NPR scores. Reads --benchmark_jsonl, '
                            'writes per-chunk CSV and pickle cache.')
    parser.add_argument('--benchmark_jsonl', type=str, default=None,
                        help='Path to benchmark JSONL produced by generate_benchmark.py. '
                            'Required when --batch_benchmark is set.')
    parser.add_argument('--benchmark_results_csv', type=str, default=None,
                        help='Output CSV path. Defaults to ../logs/benchmark_results_<output_name>.csv')
    parser.add_argument('--benchmark_results_pkl', type=str, default=None,
                        help='Output pickle cache path. Defaults to '
                            '../logs/benchmark_results_<output_name>.pkl')
    parser.add_argument('--load_benchmark_results', type=str, default=None,
                        help='Load benchmark results from a pickle file, skip scoring')

    # 2026-05-12 msong, drop the args_dict override in setup_args.
    args = parser.parse_args()
    # 2026-05-12 msong, expand ~ in path-style args. HuggingFace's symlink-based
    # cache layout fails with FileNotFoundError on relative blob paths if cache_dir
    # contains an unexpanded "~", so we resolve it here once and for all.
    args.cache_dir = os.path.expanduser(args.cache_dir)
    if args.data_path is not None:
        args.data_path = os.path.expanduser(args.data_path)
    # 2026-05-13 msong: expand the new path args too
    if args.results_cache is not None:
        args.results_cache = os.path.expanduser(args.results_cache)
    if args.load_cached_results is not None:
        args.load_cached_results = os.path.expanduser(args.load_cached_results)
    if args.npr_csv_dir is not None:
        args.npr_csv_dir = os.path.expanduser(args.npr_csv_dir)
    # 2026-05-15 msong: batch-benchmark mode for MGC localization evaluation.
    if args.benchmark_jsonl is not None:
        args.benchmark_jsonl = os.path.expanduser(args.benchmark_jsonl)
    if args.benchmark_results_csv is not None:
        args.benchmark_results_csv = os.path.expanduser(args.benchmark_results_csv)
    if args.benchmark_results_pkl is not None:
        args.benchmark_results_pkl = os.path.expanduser(args.benchmark_results_pkl)
    if args.load_benchmark_results is not None:
        args.load_benchmark_results = os.path.expanduser(args.load_benchmark_results)

    return args


def generate_data(dataset, key, max_num=200, min_len=0, max_len=128, max_comment_num=10, max_def_num=5, cut_def=False, max_todo_num=3, data_path=None):

    # 2026-05-12 msong, avoid the hard-coded info.
    if data_path is not None:
        path = data_path
    else:
        path = f'../code-generation/output/{dataset}/{key}/outputs.txt'

    logger.info(f'Loading data from {path}')

    all_originals = []
    all_samples = []
    all_source_line_nos = []   # 2026-05-13 msong: track which outputs.txt line each kept sample came from

    max_def_num_count = 0
    min_len_count = 0
    max_comment_num_count = 0
    function_comment_num_count = 0
    max_todo_num_count = 0

    with open(path, 'r') as f:
        for line_no, line in enumerate(tqdm(f, ncols=70)):
            line = line.strip()

            if line == '':
                continue
            line = json.loads(line)

            # cut out the 'def' part after the first generation
            if cut_def:
                line['output'] = line['output'].split('def')[0]
                line['solution'] = line['solution'].split('def')[0]

            # I don't like there to have too many 'def' in the code
            # ~100/100000 examples have more than 3 'def'
            if line['solution'].count('def') > max_def_num or line['output'].count('def') > max_def_num:
                max_def_num_count += 1
                continue

            # avoid examples that are too short (less than min_len words)
            # around 2000/100000 examples have around 55 words
            if len(line['solution'].split()) < min_len or len(line['output'].split()) < min_len:
                min_len_count += 1
                continue

            # if the are too many comments, skip
            def count_comment(text):
                return text.count('#')

            if count_comment(line['solution']) > max_comment_num or count_comment(line['output']) > max_comment_num:
                max_comment_num_count += 1
                continue

            # if there are too many TODOs, skip
            def count_todo_comment(text):
                return text.count('# TODO') + text.count('# todo')

            if count_todo_comment(line['solution']) > max_todo_num or count_todo_comment(line['output']) > max_todo_num:
                max_todo_num_count += 1
                continue

            # the number of text.count("'''") and text.count('"""') should be <1
            if line['solution'].count("'''") > 0 or line['solution'].count('"""') > 0 or line['output'].count("'''") > 0 or line['output'].count('"""') > 0:
                function_comment_num_count += 1
                continue

            # cut to 128 tokens
            all_originals.append(' '.join(line['solution'].split(' ')[:max_len]))
            all_samples.append(' '.join(line['output'].split(' ')[:max_len]))
            all_source_line_nos.append(line_no)

    logger.info(f'{max_def_num_count} examples have more than {max_def_num} "def"')
    logger.info(f'{min_len_count} examples have less than {min_len} words')
    logger.info(f'{max_comment_num_count} examples have more than {max_comment_num} comments')
    logger.info(f'{max_todo_num_count} examples have more than {max_todo_num} TODOs')
    logger.info(f'{function_comment_num_count} examples have more than 1 function comment')
    logger.info(f'Loaded {len(all_originals)} examples after filtering, and will return {min(max_num, len(all_originals))} examples')

    assert len(all_originals) == len(all_samples) == len(all_source_line_nos), \
        f"Filter bookkeeping mismatch: {len(all_originals)} originals, {len(all_samples)} samples, {len(all_source_line_nos)} line_nos"

    # statistical analysis
    # import random
    # random.seed(42)
    # random.shuffle(all_originals)
    # random.shuffle(all_samples)

    return {
        "original": all_originals[:max_num],
        "sampled":  all_samples[:max_num],
        "source_line_no": all_source_line_nos[:max_num],
    }


pattern = re.compile(r"<extra_id_\d+>")
pattern_with_space = re.compile(r" <extra_id_\d+> ")


def remove_mask_space(text):
    # find all the mask positions " <extra_id_\d+> ", and remove the space before and after the mask
    matches = pattern_with_space.findall(text)
    for match in matches:
        text = text.replace(match, match.strip())
    return text


def tokenize_and_mask_identifiers(text, args, span_length, pct, ceil_pct=False, buffer_size=1):

    varnames, pos = get_identifier(text, 'python')

    mask_string = ' <<<mask>>> '
    sampled = random.sample(varnames, int(len(varnames)*1))
    logger.info(f"Sampled {len(sampled)} identifiers to mask: {sampled}")

    # Split the text into lines
    lines = text.split('\n')

    # replacements will change the line length, so we need to start from the end
    pos.sort(key=lambda pos: (-pos[0][0], -pos[0][1]))

    # Process each position
    for start, end in pos:
        # Extract line number and pos in line
        line_number, start_pos = start
        _, end_pos = end

        # mask the identifier if it is in the sampled list
        if lines[line_number][start_pos:end_pos] in sampled:
            # Replace the identified section in the line
            lines[line_number] = lines[line_number][:start_pos] + mask_string + lines[line_number][end_pos:]

    # Join the lines back together
    masked_text = '\n'.join(lines)
    # logger.info(f'masked_text: \n{masked_text}')

    tokens = masked_text.split(' ')
    # logger.info(f'tokens: \n{tokens}')

    # replace each occurrence of mask_string with <extra_id_NUM>, where NUM increments
    num_filled = 0
    for idx, token in enumerate(tokens):
        # logger.info(f'idx: {idx}, token: {token}')
        if token == mask_string.strip():
            # logger.info(f'filling in {token} with <extra_id_{num_filled}>')
            tokens[idx] = f'<extra_id_{num_filled}>'
            num_filled += 1

    text = ' '.join(tokens)  # before removing the space before and after the mask

    text = remove_mask_space(text)
    # logger.info(f'text: \n{text}')
    return text


def tokenize_and_mask(text, args, span_length, pct, ceil_pct=False):
    tokens = text.split(' ')
    mask_string = '<<<mask>>>'

    n_spans = pct * len(tokens) / (span_length + args.buffer_size * 2)
    if ceil_pct:
        n_spans = np.ceil(n_spans)
    n_spans = int(n_spans)

    n_masks = 0
    while n_masks < n_spans:
        start = np.random.randint(0, len(tokens) - span_length)
        end = start + span_length
        search_start = max(0, start - args.buffer_size)
        search_end = min(len(tokens), end + args.buffer_size)
        if mask_string not in tokens[search_start:search_end]:
            tokens[start:end] = [mask_string]
            n_masks += 1

    # replace each occurrence of mask_string with <extra_id_NUM>, where NUM increments
    num_filled = 0
    for idx, token in enumerate(tokens):
        if token == mask_string:
            tokens[idx] = f'<extra_id_{num_filled}>'
            num_filled += 1
    assert num_filled == n_masks, f"num_filled {num_filled} != n_masks {n_masks}"
    text = ' '.join(tokens)
    return text


def count_masks(texts):
    # count the number of masks in each text with the pattern "<extra_id_\d+>"
    pattern = re.compile(r"<extra_id_\d+>")
    n_expected = [len(pattern.findall(x)) for x in texts]
    return n_expected


# replace each masked span with a sample from T5 mask_model
def replace_masks(texts, model_config, args):
    n_expected = count_masks(texts)
    stop_id = model_config['mask_tokenizer'].encode(f"<extra_id_{max(n_expected)}>")[0]
    tokens = model_config['mask_tokenizer'](texts, return_tensors="pt", padding=True).to(args.DEVICE)
    # tokens = model_config['mask_tokenizer'](texts, return_tensors="pt", padding=True, return_token_type_ids=False).to(args.DEVICE)
    outputs = model_config['mask_model'].generate(**tokens, max_length=512, do_sample=True, top_p=args.mask_top_p, num_return_sequences=1, eos_token_id=stop_id, temperature=args.mask_temperature)
    return model_config['mask_tokenizer'].batch_decode(outputs, skip_special_tokens=False)


def apply_extracted_fills(masked_texts, extracted_fills):
    n_expected = count_masks(masked_texts)
    texts = []
    # logger.info(f"n_expected: {n_expected}")

    for idx, (text, fills, n) in enumerate(zip(masked_texts, extracted_fills, n_expected)):
        if len(fills) < n:
            texts.append('')
        else:
            for fill_idx in range(n):
                text = text.replace(f"<extra_id_{fill_idx}>", fills[fill_idx])
            texts.append(text)

    # logger.info(f"texts: {texts}")
    return texts


def extract_fills(texts):
    # remove <pad> from beginning of each text
    texts = [x.replace("<pad>", "").replace("</s>", "").strip() for x in texts]

    # return the text in between each matched mask token
    extracted_fills = [pattern.split(x)[1:-1] for x in texts]

    # remove whitespace around each fill
    extracted_fills = [[y.strip() for y in x] for x in extracted_fills]

    return extracted_fills


def perturb_texts_(texts, args,  model_config, ceil_pct=False):
    span_length = args.span_length
    pct = args.pct_words_masked
    lambda_poisson = args.span_length
    if args.perturb_type == 'random':
        masked_texts = [tokenize_and_mask(x, args, span_length, pct, ceil_pct) for x in texts]
    elif args.perturb_type == 'identifier-masking':
        masked_texts = [tokenize_and_mask_identifiers(x, args, span_length, pct, ceil_pct) for x in texts]
    elif args.perturb_type == 'random-line-shuffle':
        perturbed_texts = [random_line_shuffle(x, pct) for x in texts]
        return perturbed_texts
    elif args.perturb_type == 'random-insert-newline':
        perturbed_texts = [random_insert_newline(x, pct, lambda_poisson) for x in texts]
        return perturbed_texts
    elif args.perturb_type == 'random-insert-space':
        perturbed_texts = [random_insert_space(x, pct, lambda_poisson) for x in texts]
        return perturbed_texts
    elif args.perturb_type == 'random-insert-space-newline':
        perturbed_texts = [random_insert_space(x, pct, lambda_poisson) for x in texts]
        perturbed_texts = [random_insert_newline(x, pct, lambda_poisson) for x in perturbed_texts]
        return perturbed_texts
    elif args.perturb_type == 'random-insert-space+newline':
        perturbed_texts_part1 = [random_insert_space(x, pct, lambda_poisson) for x in texts]
        perturbed_texts_part2 = [random_insert_newline(x, pct, lambda_poisson) for x in texts]
        total_num = len(perturbed_texts_part1)
        n1 = int(total_num / 2)
        n2 = total_num - n1
        perturbed_texts_part1 = perturbed_texts_part1[:n1]
        perturbed_texts_part2 = perturbed_texts_part2[:n2]
        return perturbed_texts_part1 + perturbed_texts_part2
    else:
        raise ValueError(f'Unknown perturb_type: {args.perturb_type}')

    raw_fills = replace_masks(masked_texts, model_config, args)
    extracted_fills = extract_fills(raw_fills)
    perturbed_texts = apply_extracted_fills(masked_texts, extracted_fills)

    # Handle the fact that sometimes the model doesn't generate the right number of fills and we have to try again
    attempts = 1
    while '' in perturbed_texts:
        idxs = [idx for idx, x in enumerate(perturbed_texts) if x == '']
        print(f'WARNING: {len(idxs)} texts have no fills. Trying again [attempt {attempts}].')
        masked_texts = [tokenize_and_mask(x, args, span_length, pct, ceil_pct) for idx, x in enumerate(texts) if idx in idxs]
        raw_fills = replace_masks(masked_texts, model_config, args)
        extracted_fills = extract_fills(raw_fills)
        new_perturbed_texts = apply_extracted_fills(masked_texts, extracted_fills)
        for idx, x in zip(idxs, new_perturbed_texts):
            perturbed_texts[idx] = x
        attempts += 1

        # If it fails for more than 50 texts, then we use the original texts as perturbed texts and inform the user with warning
        if attempts > 50:
            logger.warning(f'WARNING: {len(idxs)} texts have no fills. Using the original texts as perturbed texts.')
            for idx in idxs:
                perturbed_texts[idx] = texts[idx]

    logger.info(f'texts: {texts[0]}')
    logger.info(f'perturbed_texts: {perturbed_texts[0]}')

    return perturbed_texts


def perturb_texts(texts, args,  model_config,  ceil_pct=False):

    def perturb_texts_once(texts, args,  model_config,  ceil_pct=False):

        chunk_size = args.chunk_size
        if '11b' in args.mask_filling_model_name:
            chunk_size //= 2

        outputs = []
        for i in tqdm(range(0, len(texts), chunk_size), desc="Applying perturbations"):
            outputs.extend(perturb_texts_(texts[i:i + chunk_size], args, model_config, ceil_pct=ceil_pct))

        return outputs

    for i in range(args.n_perturbation_rounds):
        texts = perturb_texts_once(texts, args, model_config, ceil_pct=ceil_pct)

    return texts


def drop_last_word(text):
    return ' '.join(text.split(' ')[:-1])


def random_line_shuffle(text, pct=0.3):
    '''
    randomly exchange the order of two adjacent lines for pct of the lines, except for the first and last line
    '''
    lines = text.split('\n')
    n_lines = len(lines)
    n_shuffled = int(n_lines * pct)
    shuffled_idxs = np.random.choice(n_lines, n_shuffled, replace=False)
    for idx in shuffled_idxs:
        if idx == n_lines - 1 or idx == 0:
            continue
        lines[idx], lines[idx+1] = lines[idx+1], lines[idx]
    return '\n'.join(lines)


def random_insert_newline(text, pct=0.3, mean=1):
    '''
    randomly insert a newline for pct of the lines
    '''
    lines = text.split('\n')
    n_lines = len(lines)
    n_inserted = int(n_lines * pct)
    inserted_idxs = np.random.choice(n_lines, n_inserted, replace=False)
    for idx in inserted_idxs:
        n_newlines = 1
        # n_newlines = scipy.stats.poisson.rvs(mean) + 1
        lines[idx] = lines[idx] + '\n'*n_newlines
    return '\n'.join(lines)


def random_insert_space(text, pct=0.3, mean=1):
    '''
    randomly insert a space for pct of the lines
    '''
    tokens = text.split(' ')
    n_tokens = len(tokens)
    n_inserted = int(n_tokens * pct)
    inserted_idxs = np.random.choice(n_tokens, n_inserted, replace=False)
    for idx in inserted_idxs:
        n_spaces = scipy.stats.poisson.rvs(mean) + 1
        # n_spaces = 1
        tokens[idx] = tokens[idx] + ' '*n_spaces
    return ' '.join(tokens)


def vislualize_distribution(predictions, title, ax):

    # remove the nans in predictions (the pairs will be removed together)
    reals = []
    samples = []
    for i in range(len(predictions['real'])-1, -1, -1):
        if math.isnan(predictions['real'][i]) or math.isnan(predictions['samples'][i]):
            continue
        else:
            reals.append(predictions['real'][i])
            samples.append(predictions['samples'][i])
    predictions['real'] = reals
    predictions['samples'] = samples

    ax.hist(predictions['real'], bins=30, density=True, alpha=0.5, color='orange', edgecolor='orange', label='Real')
    ax.hist(predictions['samples'], bins=30, density=True, alpha=0.5, color='green', edgecolor='green', label='Samples')

    mu, std = norm.fit(predictions['real'])
    x = np.linspace(min(predictions['real'], predictions['samples']), max(predictions['real'], predictions['samples']), 100)
    p = norm.pdf(x, mu, std)
    ax.plot(x, p, linewidth=3, color='orange')
    mu, std = norm.fit(predictions['samples'])
    x = np.linspace(min(predictions['samples']), max(predictions['samples']), 100)
    p = norm.pdf(x, mu, std)
    ax.plot(x, p, linewidth=3, color='green')

    ax.set_title(title)
    ax.set_xlabel("Value")
    ax.set_ylabel("Density")
    ax.legend()


def run_batch_benchmark(args, model_config):
    """Score every chunk of every record in a benchmark JSONL.

    Output: per-chunk CSV + pickle cache. Each row is one chunk's NPR result,
    plus ground-truth metadata so localization evaluation is a CSV join.
    """
    print("\n" + "=" * 70)
    print("    DetectCodeGPT Batch Benchmark — MGC Localization Scoring    ")
    print("=" * 70)

    if not args.benchmark_jsonl:
        logger.error("--benchmark_jsonl is required with --batch_benchmark")
        return
    if not os.path.isfile(args.benchmark_jsonl):
        logger.error(f"Benchmark JSONL not found: {args.benchmark_jsonl}")
        return

    # Resolve output paths with defaults
    output_csv = args.benchmark_results_csv or f"../logs/benchmark_results_{args.output_name}.csv"
    output_pkl = args.benchmark_results_pkl or f"../logs/benchmark_results_{args.output_name}.pkl"

    # Short-circuit: load cached results
    if args.load_benchmark_results is not None:
        logger.info(f"Loading cached benchmark results from {args.load_benchmark_results}")
        with open(args.load_benchmark_results, "rb") as f:
            all_chunk_results = pickle.load(f)
        logger.info(f"Loaded {len(all_chunk_results)} chunk results")
    else:
        # Load benchmark records
        records = []
        with open(args.benchmark_jsonl, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        logger.info(f"Loaded {len(records)} benchmark records from {args.benchmark_jsonl}")

        n_perturb = max([int(x) for x in str(args.n_perturbation_list).split(",")])
        max_len = args.max_len

        all_chunk_results = []
        total_chunks_est = sum(
            -(-r['n_tokens_total'] // max_len)  # ceiling division
            for r in records
        )
        logger.info(f"Estimated total chunks to score: {total_chunks_est}")

        for record_idx, record in enumerate(tqdm(records, desc="Records")):
            mixed_code = record["mixed_code"]
            all_tokens = mixed_code.split(" ")
            n_tokens_total = len(all_tokens)

            mgc_region = next(reg for reg in record["regions"] if reg["label"] == "MGC")
            mgc_start_token = mgc_region["start_token"]
            mgc_end_token   = mgc_region["end_token"]

            # Chunk: stride = max_len, no overlap
            for chunk_idx, start in enumerate(range(0, n_tokens_total, max_len)):
                chunk_tokens = all_tokens[start:start + max_len]
                end = start + len(chunk_tokens)
                chunk_text = " ".join(chunk_tokens)

                # Skip pathologically tiny chunks — NPR is unreliable
                if len(chunk_tokens) < 20:
                    all_chunk_results.append({
                        "record_id":         record["id"],
                        "chunk_idx":         chunk_idx,
                        "start_token":       start,
                        "end_token":         end,
                        "n_tokens":          len(chunk_tokens),
                        "npr":               float("nan"),
                        "orig_logrank":      float("nan"),
                        "mean_p_logrank":    float("nan"),
                        "low_conf":          True,
                        "overlaps_mgc":      end > mgc_start_token and start < mgc_end_token,
                        "fully_in_mgc":      start >= mgc_start_token and end <= mgc_end_token,
                        "n_mgc_tokens_in_chunk": max(0, min(end, mgc_end_token) - max(start, mgc_start_token)),
                        "mgc_start_token":   mgc_start_token,
                        "mgc_end_token":     mgc_end_token,
                    })
                    continue

                # Score this chunk
                orig_logrank = get_rank(chunk_text, args, model_config, log=True)
                inputs_to_perturb = [chunk_text for _ in range(n_perturb)]
                p_texts = perturb_texts(inputs_to_perturb, args, model_config)
                p_ranks = get_ranks(p_texts, args, model_config, log=True)
                valid_p_ranks = [r for r in p_ranks if not math.isnan(r)]
                mean_p_rank = np.mean(valid_p_ranks) if valid_p_ranks else float("nan")
                npr = mean_p_rank / orig_logrank if orig_logrank else float("nan")

                # Compute overlap with MGC ground truth (in token indices)
                overlap_start = max(start, mgc_start_token)
                overlap_end = min(end, mgc_end_token)
                n_mgc_in_chunk = max(0, overlap_end - overlap_start)

                all_chunk_results.append({
                    "record_id":         record["id"],
                    "chunk_idx":         chunk_idx,
                    "start_token":       start,
                    "end_token":         end,
                    "n_tokens":          len(chunk_tokens),
                    "npr":               npr,
                    "orig_logrank":      orig_logrank,
                    "mean_p_logrank":    mean_p_rank,
                    "low_conf":          False,
                    "overlaps_mgc":      n_mgc_in_chunk > 0,
                    "fully_in_mgc":      start >= mgc_start_token and end <= mgc_end_token,
                    "n_mgc_tokens_in_chunk": n_mgc_in_chunk,
                    "mgc_start_token":   mgc_start_token,
                    "mgc_end_token":     mgc_end_token,
                })

            if (record_idx + 1) % 50 == 0:
                logger.info(f"Progress: {record_idx + 1}/{len(records)} records, "
                            f"{len(all_chunk_results)} chunks scored")

        # Save pickle cache
        os.makedirs(os.path.dirname(output_pkl) or ".", exist_ok=True)
        with open(output_pkl, "wb") as f:
            pickle.dump(all_chunk_results, f)
        logger.info(f"Cached benchmark results to {output_pkl}")

    # Always write CSV (from cached or fresh data)
    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    with open(output_csv, "w") as f:
        f.write("record_id,chunk_idx,start_token,end_token,n_tokens,npr,"
                "orig_logrank,mean_p_logrank,low_conf,"
                "overlaps_mgc,fully_in_mgc,n_mgc_tokens_in_chunk,"
                "mgc_start_token,mgc_end_token,"
                "predict_mgc_youden,predict_mgc_highconf\n")
        for r in all_chunk_results:
            pred_youden = (not r["low_conf"]) and (not math.isnan(r["npr"])) and (r["npr"] > args.threshold_youden)
            pred_high   = (not r["low_conf"]) and (not math.isnan(r["npr"])) and (r["npr"] > args.threshold)
            f.write(f"{r['record_id']},{r['chunk_idx']},{r['start_token']},{r['end_token']},"
                    f"{r['n_tokens']},{r['npr']:.6f},{r['orig_logrank']:.6f},{r['mean_p_logrank']:.6f},"
                    f"{int(r['low_conf'])},{int(r['overlaps_mgc'])},{int(r['fully_in_mgc'])},"
                    f"{r['n_mgc_tokens_in_chunk']},{r['mgc_start_token']},{r['mgc_end_token']},"
                    f"{int(pred_youden)},{int(pred_high)}\n")
    logger.info(f"Wrote benchmark CSV to {output_csv}")

    # Quick summary
    n_chunks = len(all_chunk_results)
    n_valid = sum(1 for r in all_chunk_results if not r["low_conf"] and not math.isnan(r["npr"]))
    n_pred_youden = sum(
        1 for r in all_chunk_results
        if not r["low_conf"] and not math.isnan(r["npr"]) and r["npr"] > args.threshold_youden
    )
    n_pred_high = sum(
        1 for r in all_chunk_results
        if not r["low_conf"] and not math.isnan(r["npr"]) and r["npr"] > args.threshold
    )
    n_overlap = sum(1 for r in all_chunk_results if r["overlaps_mgc"])

    print("\n" + "=" * 70)
    print("                    BATCH BENCHMARK SUMMARY")
    print("=" * 70)
    print(f"  Total chunks scored:           {n_chunks}")
    print(f"  Valid scores (not low_conf):   {n_valid}")
    print(f"  Chunks overlapping MGC:        {n_overlap}")
    print(f"  Flagged (NPR > {args.threshold_youden:.4f}): {n_pred_youden}")
    print(f"  Flagged (NPR > {args.threshold:.4f}):       {n_pred_high}")
    print("=" * 70)


def run_interactive_mode(args, model_config):
    print("\n" + "=" * 60)
    print("    DetectCodeGPT Interactive Mode — MGC Localization    ")
    print("=" * 60)
    print("Paste your code snippet below.")
    print("When finished, type 'EOF' on a new line and press Enter:")
    print("-" * 60)

    lines = []
    while True:
        line = input()
        if line.strip().upper() == "EOF":
            break
        lines.append(line)

    code_raw = "\n".join(lines).strip()

    if not code_raw:
        logger.error("No code provided. Exiting.")
        return

    # ------------------------------------------------------------------
    # 2026-05-14 msong: MGC-localization mode.
    # Goal: given a (possibly long) function, identify which SECTIONS are
    # likely MGC, not produce a single function-level verdict. The 128-token
    # block-level chunking matches the calibration regime of generate_data(),
    # so each chunk's NPR is directly comparable to the calibrated threshold.
    # ------------------------------------------------------------------
    all_tokens = code_raw.split(' ')
    n_tokens_total = len(all_tokens)
    max_len = args.max_len
    min_chunk_tokens = 20  # below this, NPR is too noisy to trust

    # Track token offset per chunk so we can map back to source location.
    chunks = []
    for start in range(0, n_tokens_total, max_len):
        chunk_tokens = all_tokens[start:start + max_len]
        chunks.append({
            "text":        ' '.join(chunk_tokens),
            "token_start": start,
            "token_end":   start + len(chunk_tokens),  # exclusive
            "n_tokens":    len(chunk_tokens),
        })

    print(f"\n[Input] {n_tokens_total} whitespace-tokens total "
          f"-> split into {len(chunks)} chunk(s) of up to {max_len} tokens each.")
    print(f"[Thresholds] Youden's J = {args.threshold_youden:.4f} (warning),  "
          f"high-confidence = {args.threshold:.4f}")

    n_perturb = max([int(x) for x in str(args.n_perturbation_list).split(",")])

    # ------------------------------------------------------------------
    # Score each chunk
    # ------------------------------------------------------------------
    for ci, ch in enumerate(chunks):
        low_conf = ch["n_tokens"] < min_chunk_tokens

        print("\n" + "-" * 60)
        print(f"  CHUNK {ci + 1}/{len(chunks)}  "
              f"(tokens {ch['token_start']}..{ch['token_end'] - 1}, "
              f"len {ch['n_tokens']}"
              f"{'  [LOW CONFIDENCE: short chunk]' if low_conf else ''})")
        print("-" * 60)

        print(f"  [Step 1] original log rank...")
        orig_logrank = get_rank(ch["text"], args, model_config, log=True)

        print(f"  [Step 2] applying {n_perturb} perturbations...")
        inputs_to_perturb = [ch["text"] for _ in range(n_perturb)]
        p_texts = perturb_texts(inputs_to_perturb, args, model_config)

        print(f"  [Step 3] perturbed log ranks...")
        p_ranks = get_ranks(p_texts, args, model_config, log=True)
        valid_p_ranks = [r for r in p_ranks if not math.isnan(r)]
        if len(valid_p_ranks) < n_perturb:
            print(f"           WARNING: {n_perturb - len(valid_p_ranks)} NaN ranks excluded.")
        mean_p_rank = np.mean(valid_p_ranks) if valid_p_ranks else float('nan')

        npr = mean_p_rank / orig_logrank if orig_logrank else float('nan')

        ch["orig_lr"]   = orig_logrank
        ch["mean_p_lr"] = mean_p_rank
        ch["npr"]       = npr
        ch["low_conf"]  = low_conf

        # Show the chunk and one perturbed example for visibility.
        print(f"\n  --- ORIGINAL (chunk {ci + 1}) ---")
        print(ch["text"])
        print(f"\n  --- PERTURBED COPY #1 of {n_perturb} ---")
        print(p_texts[0])
        print(f"\n  >> Chunk {ci + 1} NPR = {npr:.4f}")

    # ------------------------------------------------------------------
    # Per-chunk profile (the main output)
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("           PER-CHUNK NPR PROFILE  —  MGC LOCALIZATION")
    print("=" * 70)
    print(f"  {'chunk':>5}  {'tokens':>10}  {'len':>5}  {'NPR':>9}  {'flag':<10}  {'verdict':<20}")
    print("  " + "-" * 66)

    suspects = []  # chunks above Youden's J
    for ch in chunks:
        token_range = f"{ch['token_start']:>4}..{ch['token_end'] - 1:<4}"
        if math.isnan(ch["npr"]):
            verdict = "UNSCORABLE"
            flag = ""
        elif ch["npr"] > args.threshold:
            verdict = "MGC SUSPECT"
            flag = "[HIGH]"
            suspects.append(ch)
        elif ch["npr"] > args.threshold_youden:
            verdict = "MGC SUSPECT"
            flag = "[WARN]"
            suspects.append(ch)
        else:
            verdict = "HWC-leaning"
            flag = ""
        low_conf_marker = " *" if ch["low_conf"] else ""
        print(f"  {ch['index'] + 1 if 'index' in ch else chunks.index(ch) + 1:>5}  "
              f"{token_range:>10}  {ch['n_tokens']:>5}  "
              f"{ch['npr']:>9.4f}  {flag:<10}  {verdict:<20}{low_conf_marker}")

    print("=" * 70)

    # ------------------------------------------------------------------
    # Localized suspect report
    # ------------------------------------------------------------------
    if not suspects:
        print(f"\nNo MGC suspects detected. All scorable chunks fell below "
              f"Youden's J = {args.threshold_youden:.4f}.\n")
        return

    print(f"\nDetected {len(suspects)} suspect chunk(s) — possible MGC region(s):\n")
    for ch in suspects:
        ci = chunks.index(ch)
        confidence = "HIGH" if ch["npr"] > args.threshold else "WARNING"
        print(f"  [Chunk {ci + 1}]  tokens {ch['token_start']}..{ch['token_end'] - 1}  "
              f"({ch['n_tokens']} tokens)")
        print(f"             NPR = {ch['npr']:.4f}   ({confidence})")
        # Show first ~6 lines of the chunk as a locator
        preview_lines = ch["text"].split('\n')[:6]
        for ln in preview_lines:
            print(f"             | {ln}")
        if len(ch["text"].split('\n')) > 6:
            print(f"             | ... ({len(ch['text'].split(chr(10))) - 6} more lines)")
        print()

    # ------------------------------------------------------------------
    # Local-deviation pass — chunks that spike vs neighbors
    # ------------------------------------------------------------------
    # Even a chunk below absolute threshold can be suspicious if it stands out
    # sharply relative to surrounding HWC. Compute neighbor-relative deltas.
    if len(chunks) >= 3:
        valid_chunks = [c for c in chunks if not math.isnan(c["npr"])]
        if len(valid_chunks) >= 3:
            nprs = np.array([c["npr"] for c in valid_chunks])
            median_npr = float(np.median(nprs))
            mad = float(np.median(np.abs(nprs - median_npr)))  # MAD: robust spread
            if mad > 0.01:  # avoid divide-by-zero on near-uniform sequences
                print("Local-deviation analysis (vs. function-wide median):")
                print(f"  median NPR across chunks: {median_npr:.4f}")
                print(f"  MAD (robust spread):      {mad:.4f}")
                print(f"  Chunks with z_MAD > 2.0 (sharp deviation from neighbors):")
                found_any = False
                for c in valid_chunks:
                    z_mad = (c["npr"] - median_npr) / (1.4826 * mad)
                    if z_mad > 2.0:
                        ci = chunks.index(c)
                        print(f"    chunk {ci + 1}: NPR={c['npr']:.4f}, "
                              f"z_MAD={z_mad:+.2f}  -> stands out as MGC-like")
                        found_any = True
                if not found_any:
                    print("    (none — no chunk deviates >2 MAD from the median)")
                print()
    print("Next step: data-flow analysis to refine suspect boundaries within "
          "flagged chunks.\n")


def main():
    """Main function to run the code detection pipeline."""
    args = setup_args()

    # =====================================================================
    # 2026-05-15 msong: BATCH_BENCHMARK MODE
    # =====================================================================
    if getattr(args, 'batch_benchmark', False):
        cache_dir, _, _ = preprocess_and_save(args)
        model_config = {'cache_dir': cache_dir}

        logger.info("Batch benchmark mode: loading base scoring model only...")
        model_config = load_base_model_and_tokenizer(args, model_config)

        run_batch_benchmark(args, model_config)
        return
    # =====================================================================
    # 2026-05-14 msong: INTERACTIVE MODE
    # =====================================================================
    if getattr(args, 'interactive', False):
        cache_dir, _, _ = preprocess_and_save(args)
        model_config = {'cache_dir': cache_dir}

        logger.info("Interactive mode: Loading base scoring model only...")
        model_config = load_base_model_and_tokenizer(args, model_config)

        run_interactive_mode(args, model_config)
        return
    # =====================================================================
    
    mask_filling_model_name = args.mask_filling_model_name
    n_samples = args.n_samples
    batch_size = args.batch_size
    n_perturbation_list = [int(x) for x in args.n_perturbation_list.split(",")]
    n_perturbation_rounds = args.n_perturbation_rounds
    n_similarity_samples = args.n_similarity_samples

    cache_dir, base_model_name, SAVE_FOLDER = preprocess_and_save(args)
    model_config = {}
    model_config['cache_dir'] = cache_dir

    # mask filling t5 model
    model_config = load_mask_filling_model(args, mask_filling_model_name, model_config)

    logger.info(f'args: {args}')

    # 2026-05-12 msong, data_path replaces the hard-coded info.
    # data = generate_data(args.dataset, args.dataset_key, max_num=args.n_samples, min_len=args.min_len, max_len=args.max_len,
    #                      max_comment_num=args.max_comment_num, max_def_num=args.max_def_num, cut_def=args.cut_def, max_todo_num=args.max_todo_num)
    data = generate_data(args.dataset, args.dataset_key, max_num=args.n_samples, min_len=args.min_len, max_len=args.max_len,
                         max_comment_num=args.max_comment_num, max_def_num=args.max_def_num, cut_def=args.cut_def, max_todo_num=args.max_todo_num,
                         data_path=args.data_path)

    logger.info(f'Original: {data["original"][0]}')
    logger.info(f'Sampled: {data["sampled"][0]}')

    ceil_pct = False
    texts = ['''
    def remove_mask_space(text, args, **kwargs):
        # find all the mask positions " <extra_id_\d+> ", and remove the space before and after the mask
        pattern = re.compile(r" <extra_id_\d+> ")
        matches = pattern.findall(text)
        for match in matches:
            text = text.replace(match, match.strip())
        return text
    ''']
    span_length = args.span_length
    pct = args.pct_words_masked
    lambda_poisson = args.span_length

    if args.perturb_type == 'random':
        masked_texts = [tokenize_and_mask(x, args, span_length, pct, ceil_pct) for x in texts]
    elif args.perturb_type == 'identifier-masking':
        masked_texts = [tokenize_and_mask_identifiers(x, args, span_length, pct, ceil_pct) for x in texts]
    elif args.perturb_type == 'random-line-shuffle':
        masked_texts = [random_line_shuffle(x, pct) for x in texts]
    elif args.perturb_type == 'random-insert-newline':
        masked_texts = [random_insert_newline(x, pct, lambda_poisson) for x in texts]
    elif args.perturb_type == 'random-insert-space':
        masked_texts = [random_insert_space(x, pct, lambda_poisson) for x in texts]
    elif args.perturb_type == 'random-insert-space-newline':
        masked_texts = [random_insert_space(x, pct, lambda_poisson) for x in texts]
        masked_texts = [random_insert_newline(x, pct, lambda_poisson) for x in masked_texts]
    elif args.perturb_type == 'random-insert-space+newline':
        perturbed_texts_part1 = [random_insert_space(x, pct, lambda_poisson) for x in texts]
        perturbed_texts_part2 = [random_insert_newline(x, pct, lambda_poisson) for x in texts]
        total_num = len(perturbed_texts_part1)
        n1 = int(total_num / 2)
        n2 = total_num - n1
        perturbed_texts_part1 = perturbed_texts_part1[:n1]
        perturbed_texts_part2 = perturbed_texts_part2[:n2]
        masked_texts = perturbed_texts_part1 + perturbed_texts_part2
    else:
        raise ValueError(f'Unknown perturb_type: {args.perturb_type}')

    raw_fills = replace_masks(masked_texts, model_config, args)
    extracted_fills = extract_fills(raw_fills)
    perturbed_texts = apply_extracted_fills(masked_texts, extracted_fills)

    logger.info(f'original texts: {texts[0]}')
    logger.info(f'masked_texts: {masked_texts[0]}')
    logger.info(f'perturbed_texts: {perturbed_texts[0]}')

    # from baselines.detectGPT import perturb_texts

    original_text = data["original"]
    sampled_text = data["sampled"]

    perturb_fn = functools.partial(perturb_texts, args=args, model_config=model_config)  # perturbation function
    p_sampled_text = perturb_fn([x for x in sampled_text for _ in range(max(n_perturbation_list))])  # perturb sampled text
    p_original_text = perturb_fn([x for x in original_text for _ in range(max(n_perturbation_list))])  # perturb original text

    results = []
    for idx in range(len(original_text)):
        results.append({
            "original": original_text[idx],
            "sampled": sampled_text[idx],
            "perturbed_sampled":  p_sampled_text[idx * max(n_perturbation_list): (idx + 1) * max(n_perturbation_list)],
            "perturbed_original": p_original_text[idx * max(n_perturbation_list): (idx + 1) * max(n_perturbation_list)],
            "source_line_no": data["source_line_no"][idx],  # 2026-05-13 msong: pass through for CSV
        })

    selected_index = 1
    selected_perturb = 3

    print(original_text[selected_index])
    # p_original_text[:5]
    print(p_original_text[int(args.n_perturbation_list)*selected_index+selected_perturb])
    # print the difference between the original and perturbed text
    print("\nDifference between original and perturbed text:")
    print([x for x in p_original_text[int(args.n_perturbation_list)*selected_index+selected_perturb].split(' ') if x not in original_text[selected_index].split(' ')])

    # show the length of the original and perturbed text
    print(f"original text length: {len(original_text)}")
    print(f"perturbed text length: {len(p_original_text)}")

    model_config['mask_model'] = model_config['mask_model'].cpu()
    torch.cuda.empty_cache()

    # start to load the base scoring model
    model_config = load_base_model_and_tokenizer(args, model_config)

    # 2026-05-13 msong: short-circuit ALL scoring if loading from a cached results pickle.
    if args.load_cached_results is not None:
        logger.info(f"Loading cached results from {args.load_cached_results} — skipping all scoring")
        with open(args.load_cached_results, "rb") as f:
            results = pickle.load(f)

        # 2026-05-13 msong: backfill source_line_no from a fresh generate_data() call.
        # generate_data is deterministic for given filter args, so the order of returned
        # samples matches the order in the cached results.
        if results and "source_line_no" not in results[0]:
            logger.info("Cached results lack source_line_no — backfilling from generate_data()")
            fresh_data = generate_data(args.dataset, args.dataset_key,
                                       max_num=args.n_samples, min_len=args.min_len, max_len=args.max_len,
                                       max_comment_num=args.max_comment_num, max_def_num=args.max_def_num,
                                       cut_def=args.cut_def, max_todo_num=args.max_todo_num,
                                       data_path=args.data_path)
            assert len(fresh_data["source_line_no"]) == len(results), \
                f"Backfill mismatch: {len(fresh_data['source_line_no'])} line_nos vs {len(results)} cached results"
            for r, line_no in zip(results, fresh_data["source_line_no"]):
                r["source_line_no"] = line_no


        logger.info(f"Loaded {len(results)} cached results")
    else:
        # 2026-05-13 msong: Block 1 (unperturbed LL) is only needed for the LRR baseline.
        # Skip in --detectcodegpt_only mode to save ~36 sec.
        if not args.detectcodegpt_only:
            for res in tqdm(results, desc="Computing unperturbed log likelihoods"):
                res["original_ll"] = get_ll(res["original"], args, model_config)
                res["sampled_ll"] = get_ll(res["sampled"], args, model_config)
        else:
            logger.info("Skipping Block 1 (unperturbed log likelihoods) due to --detectcodegpt_only")

        # Block 2 — REQUIRED for both logrank baseline AND DetectCodeGPT NPR (denominator)
        for res in tqdm(results, desc="Computing unperturbed log rank"):
            res["original_logrank"] = get_rank(res["original"], args, model_config, log=True)
            res["sampled_logrank"] = get_rank(res["sampled"], args, model_config, log=True)

        # 2026-05-13 msong: Block 3 (perturbed LL) is only needed for the
        # DetectGPT-with-DetectCodeGPT-perturbation baseline. Skip in --detectcodegpt_only
        # mode to save ~32 minutes — the single biggest time win available.
        if not args.detectcodegpt_only:
            for res in tqdm(results, desc="Computing perturbed log likelihoods"):
                p_sampled_ll = get_lls(res["perturbed_sampled"], args, model_config)
                p_original_ll = get_lls(res["perturbed_original"], args, model_config)
                for n_perturbation in n_perturbation_list:
                    res[f"perturbed_sampled_ll_{n_perturbation}"] = np.mean([i for i in p_sampled_ll[:n_perturbation] if not math.isnan(i)])
                    res[f"perturbed_original_ll_{n_perturbation}"] = np.mean([i for i in p_original_ll[:n_perturbation] if not math.isnan(i)])
                    res[f"perturbed_sampled_ll_std_{n_perturbation}"] = np.std([i for i in p_sampled_ll[:n_perturbation] if not math.isnan(i)]) if len([
                        i for i in p_sampled_ll[:n_perturbation] if not math.isnan(i)]) > 1 else 1
                    res[f"perturbed_original_ll_std_{n_perturbation}"] = np.std([i for i in p_original_ll[:n_perturbation] if not math.isnan(i)]) if len([
                        i for i in p_original_ll[:n_perturbation] if not math.isnan(i)]) > 1 else 1
        else:
            logger.info("Skipping Block 3 (perturbed log likelihoods) due to --detectcodegpt_only — saves ~32 min")

        # Block 4 — REQUIRED for DetectCodeGPT NPR (numerator)
        for res in tqdm(results, desc="Computing perturbed log rank"):
            p_sampled_rank = get_ranks(res["perturbed_sampled"], args, model_config, log=True)
            p_original_rank = get_ranks(res["perturbed_original"], args, model_config, log=True)
            for n_perturbation in n_perturbation_list:
                res[f"perturbed_sampled_logrank_{n_perturbation}"] = np.mean([i for i in p_sampled_rank[:n_perturbation] if not math.isnan(i)])
                res[f"perturbed_original_logrank_{n_perturbation}"] = np.mean([i for i in p_original_rank[:n_perturbation] if not math.isnan(i)])

        # 2026-05-13 msong: cache the results dict to disk after scoring completes.
        # Subsequent runs with --load_cached_results can skip the 32-64 min scoring
        # phases and iterate on threshold logic in ~1 second.
        results_cache_path = args.results_cache if args.results_cache else f"../logs/results_cache_{args.output_name}.pkl"
        os.makedirs(os.path.dirname(results_cache_path) or ".", exist_ok=True)
        with open(results_cache_path, "wb") as f:
            pickle.dump(results, f)
        logger.info(f"Cached results to {results_cache_path} ({os.path.getsize(results_cache_path) / 1e6:.1f} MB)")
        logger.info(f"To re-run AUROC/threshold analysis without re-scoring: --load_cached_results {results_cache_path}")


    torch.cuda.empty_cache()

    print(len(results))  # corresponds to the number of samples, and the result of each sample is stored in a dictionary
    print(results[0].keys())  # corresponds to the computed metrics of for each sample

    # ==================================================================
    # 2026-05-13 msong: consolidated AUROC + per-sample NPR analysis
    # ==================================================================

    # Compute DetectCodeGPT NPR (the headline number) — always done
    n_perturbation = max(n_perturbation_list)  # 2026-05-13 msong: fixed.
    predictions_dcg = {'real': [], 'samples': []}
    for res in results:
        predictions_dcg['real'].append(
            res[f'perturbed_original_logrank_{n_perturbation}'] / res["original_logrank"]
        )
        predictions_dcg['samples'].append(
            res[f'perturbed_sampled_logrank_{n_perturbation}'] / res["sampled_logrank"]
        )
    _, _, roc_auc_dcg = get_roc_metrics(predictions_dcg['real'], predictions_dcg['samples'])

    real_arr   = np.array(predictions_dcg['real'])     # HWC NPR scores (label=0)
    sample_arr = np.array(predictions_dcg['samples'])  # MGC NPR scores (label=1)

    # ----- summary statistics -----
    print()
    print("=" * 72)
    print(f"DetectCodeGPT NPR scores (n={len(real_arr)} per class)")
    print("=" * 72)
    print(f"HWC (real):    mean={real_arr.mean():.4f}  std={real_arr.std():.4f}  "
          f"min={real_arr.min():.4f}  max={real_arr.max():.4f}  median={np.median(real_arr):.4f}")
    print(f"MGC (samples): mean={sample_arr.mean():.4f}  std={sample_arr.std():.4f}  "
          f"min={sample_arr.min():.4f}  max={sample_arr.max():.4f}  median={np.median(sample_arr):.4f}")
    print(f"Mean separation (MGC - HWC): {sample_arr.mean() - real_arr.mean():.4f}")

    # ----- per-sample preview (first 10) -----
    print()
    print("First 10 pairs (index, HWC NPR, MGC NPR, MGC>HWC?):")
    print("-" * 50)
    for i in range(min(10, len(real_arr))):
        winner = "MGC" if sample_arr[i] > real_arr[i] else "HWC"
        print(f"  {i:3d}    {real_arr[i]:.4f}    {sample_arr[i]:.4f}    {winner}")

    # ----- text histogram -----
    all_scores = np.concatenate([real_arr, sample_arr])
    lo, hi = all_scores.min(), all_scores.max()
    n_bins = 20
    edges = np.linspace(lo, hi, n_bins + 1)
    hist_real,   _ = np.histogram(real_arr,   bins=edges)
    hist_sample, _ = np.histogram(sample_arr, bins=edges)
    max_count = max(hist_real.max(), hist_sample.max())
    bar_width = 30
    print()
    print(f"Histogram (range {lo:.3f} to {hi:.3f}, {n_bins} bins):")
    print(f"{'  bin_center':>12}  {'HWC':>4} {'MGC':>4}  HWC=. MGC=#")
    for i in range(n_bins):
        center = 0.5 * (edges[i] + edges[i + 1])
        bar_real   = "." * int(bar_width * hist_real[i]   / max_count) if max_count else ""
        bar_sample = "#" * int(bar_width * hist_sample[i] / max_count) if max_count else ""
        print(f"  {center:8.4f}    {hist_real[i]:4d} {hist_sample[i]:4d}  {bar_real}{bar_sample}")

    # ----- candidate thresholds -----
    print()
    print("Percentile-based threshold candidates:")
    print("-" * 72)
    for label, arr in [("HWC", real_arr), ("MGC", sample_arr)]:
        p = np.percentile(arr, [5, 25, 50, 75, 95])
        print(f"  {label} percentiles: 5%={p[0]:.4f}  25%={p[1]:.4f}  "
              f"50%={p[2]:.4f}  75%={p[3]:.4f}  95%={p[4]:.4f}")

    # Optimal threshold via Youden's J statistic
    from sklearn.metrics import roc_curve as _roc_curve
    y_true_combined = np.concatenate([np.zeros_like(real_arr), np.ones_like(sample_arr)])
    y_score_combined = np.concatenate([real_arr, sample_arr])
    fpr, tpr, thresholds = _roc_curve(y_true_combined, y_score_combined)
    j_stat = tpr - fpr
    best_idx = np.argmax(j_stat)
    best_threshold = thresholds[best_idx]
    print()
    print(f"Optimal threshold (Youden's J = TPR - FPR maximized):")
    print(f"  threshold = {best_threshold:.4f}")
    print(f"  at TPR = {tpr[best_idx]:.4f}, FPR = {fpr[best_idx]:.4f}, J = {j_stat[best_idx]:.4f}")
    print(f"  decision rule: NPR > {best_threshold:.4f}  =>  predict MGC, else HWC")

    # ----- save CSV -----
    npr_csv_dir = args.npr_csv_dir if args.npr_csv_dir else "../logs"
    os.makedirs(npr_csv_dir, exist_ok=True)
    csv_path = f"{npr_csv_dir}/npr_scores_{args.output_name}.csv"
    with open(csv_path, "w") as f:
        f.write("index,source_line_no,hwc_npr,mgc_npr,winner,"
                "hwc_logrank,mgc_logrank,hwc_perturbed_logrank,mgc_perturbed_logrank\n")

        for i, res in enumerate(results):
            hwc = real_arr[i]
            mgc = sample_arr[i]
            winner = "MGC" if mgc > hwc else "HWC"
            f.write(f"{i},{res['source_line_no']},{hwc:.6f},{mgc:.6f},{winner},"
                    f"{res['original_logrank']:.6f},"
                    f"{res['sampled_logrank']:.6f},"
                    f"{res[f'perturbed_original_logrank_{n_perturbation}']:.6f},"
                    f"{res[f'perturbed_sampled_logrank_{n_perturbation}']:.6f}\n")

    print()
    print(f"Saved per-sample scores to: {csv_path}")
    print(f"  Columns: index, hwc_npr, mgc_npr, winner, "
          f"hwc_logrank, mgc_logrank, hwc_perturbed_logrank, mgc_perturbed_logrank")

    print()
    print("=" * 72)
    print(f"ROC AUC of DetectCodeGPT: {roc_auc_dcg}")
    print("=" * 72)

    # ----- plot + baseline AUROCs -----
    if args.detectcodegpt_only:
        # Smaller 1x2 figure: free logrank baseline + DetectCodeGPT
        fig, axs = plt.subplots(1, 2, figsize=(10, 5))

        # logrank baseline — free, uses already-computed unperturbed log rank
        predictions_lr = {'real': [], 'samples': []}
        for res in results:
            predictions_lr['real'].append(-res['original_logrank'])
            predictions_lr['samples'].append(-res['sampled_logrank'])
        _, _, roc_auc_lr = get_roc_metrics(predictions_lr['real'], predictions_lr['samples'])
        print(f"ROC AUC of logrank: {roc_auc_lr}  (free baseline, sanity check)")
        vislualize_distribution(predictions_lr, f'Logrank AUC = {roc_auc_lr}', axs[0])

        vislualize_distribution(predictions_dcg, f'DetectCodeGPT AUC = {roc_auc_dcg}', axs[1])
    else:
        # Full 2x2 figure with all four methods
        fig, axs = plt.subplots(2, 2, figsize=(10, 10))

        # logrank baseline
        predictions_lr = {'real': [], 'samples': []}
        for res in results:
            predictions_lr['real'].append(-res['original_logrank'])
            predictions_lr['samples'].append(-res['sampled_logrank'])
        _, _, roc_auc_lr = get_roc_metrics(predictions_lr['real'], predictions_lr['samples'])
        print(f"ROC AUC of logrank: {roc_auc_lr}")
        vislualize_distribution(predictions_lr, f'Logrank AUC = {roc_auc_lr}', axs[0, 0])

        # LRR baseline
        predictions_lrr = {'real': [], 'samples': []}
        for res in results:
            predictions_lrr['real'].append(-res['original_ll'] / res['original_logrank'])
            predictions_lrr['samples'].append(-res['sampled_ll'] / res['sampled_logrank'])
        _, _, roc_auc_lrr = get_roc_metrics(predictions_lrr['real'], predictions_lrr['samples'])
        print(f'ROC AUC of LRR: {roc_auc_lrr}')
        vislualize_distribution(predictions_lrr, f'LRR AUC = {roc_auc_lrr}', axs[0, 1])

        # DetectGPT-with-DetectCodeGPT-perturbation baseline
        predictions_dgp = {'real': [], 'samples': []}
        for res in results:
            real_comp = (res['original_ll'] - res[f'perturbed_original_ll_{n_perturbation}']) \
                        / res[f'perturbed_original_ll_std_{n_perturbation}']
            sample_comp = (res['sampled_ll'] - res[f'perturbed_sampled_ll_{n_perturbation}']) \
                          / res[f'perturbed_sampled_ll_std_{n_perturbation}']
            if math.isnan(real_comp) or math.isnan(sample_comp):
                logger.warning("NaN detected, skipping")
                continue
            predictions_dgp['real'].append(real_comp)
            predictions_dgp['samples'].append(sample_comp)
        _, _, roc_auc_dgp = get_roc_metrics(predictions_dgp['real'], predictions_dgp['samples'])
        # 2026-05-13 msong: original code had `print(f"ROC AUC of DetectGPT...")` without the value
        print(f"ROC AUC of DetectGPT with DetectCodeGPT's perturbation: {roc_auc_dgp}")
        vislualize_distribution(predictions_dgp,
                                 f"DetectGPT with DetectCodeGPT's perturbation AUC = {roc_auc_dgp}",
                                 axs[1, 0])

        vislualize_distribution(predictions_dcg, f'DetectCodeGPT AUC = {roc_auc_dcg}', axs[1, 1])


    plt.tight_layout()
    plt.savefig('results.pdf')


if __name__ == "__main__":
    main()



# =====================================================================================================
# How ROC AUC of DetectCodeGPT: 0.9007 is computed
# =====================================================================================================
# res['original_logrank']                  # scalar: log-rank score of the human-written code
# res['sampled_logrank']                   # scalar: log-rank score of the machine-generated code
# res['perturbed_original_logrank_50']     # scalar: mean log-rank over 50 perturbed copies of the human code
#                                          # res[f'perturbed_original_logrank_{n_perturbation}']
# res['perturbed_sampled_logrank_50']      # scalar: mean log-rank over 50 perturbed copies of the machine code
#                                          # res[f'perturbed_sampled_logrank_{n_perturbation}']
# =====================================================================================================
"""
So each sample gets a single number:
score = log (x') / log (x)

x = original code
x' = perturbed copy
avg(log (x)) = average log-rank of each token in the code under LLMs (e.g., CodeLlama)
avg(log (x')) = mean across the 50 perturbations of that sample

NPR score = (E * avg(log (x'))) / avg(log (x))
"""
# =====================================================================================================
"""
For each of 530 valid (human, machine) pairs:
    │
    ├── original_logrank          ← from CodeLlama forward pass on x
    ├── sampled_logrank           ← from CodeLlama forward pass on machine code
    ├── perturbed_original_logrank_50  ← mean of CodeLlama logrank over 50 perturbed human copies
    └── perturbed_sampled_logrank_50   ← mean of CodeLlama logrank over 50 perturbed machine copies
    │
    ▼
NPR_human   = perturbed_original_logrank_50 / original_logrank   ← one number per human
NPR_machine = perturbed_sampled_logrank_50  / sampled_logrank    ← one number per machine
    │
    ▼
List of 530 NPR_human values   (label=0)
List of 530 NPR_machine values (label=1)
    │
    ▼
sklearn.metrics.roc_auc_score(labels=[0]*530 + [1]*530,
                               scores=NPR_human + NPR_machine)
    │
    ▼
        0.9007 ★
"""