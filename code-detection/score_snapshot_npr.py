#!/usr/bin/env python3
"""Score A01 snapshot code units with DetectCodeGPT-style NPR.

This stage is intentionally limited to continuous NPR measurement. It does not
classify code as AI-generated or human-written and it does not aggregate to the
file or snapshot level; A03 performs those downstream aggregations.

Runtime policy
--------------
This scoring stage runs in the DetectCodeGPT conda environment on Python 3.11.
Python 3.12 is reserved for stages that AST-parse source snippets (for example,
A01). A02 does not AST-parse source code.

Primary methodological choices
------------------------------
1. The primary window coordinate is the original DetectCodeGPT literal-space
   convention: ``text.split(" ")``.
2. Each long code unit is covered by 128-space-by-token windows. A short final
   tail is shifted backward into a full overlapping final window.
3. Window text is sliced directly from the original UTF-8 A01 artifact using
   character boundaries derived from literal-space token positions. The LLM
   tokenizer is never used to reconstruct source text.
4. The scoring model tokenizer is called without max_length or truncation in
   the NPR scoring path, matching baselines.rank.get_rank(). LLM-token counts
   are recorded only as diagnostics.
5. NPR is mean perturbed log-rank / original log-rank, with 50 perturbations by
   default. The original and perturbed log-rank components are retained.
6. Code-unit results are cached by code-unit SHA-256 plus a scoring-config
   fingerprint. Identical source units across historical snapshots are scored
   once and then expanded back to all A01 manifest occurrences.
7. No AGC/HWC threshold or decision rule is present in this program.
8. The v3 delivery changes provenance handling only. The scoring/cache method is
   intentionally cache-compatible with v2 so existing v2 NPR cache entries remain
   reusable without rescoring.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import random
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import pandas as pd


SCRIPT_VERSION = "run-x-a02-v3"
CACHE_SCORING_VERSION = "run-x-a02-v2"
WINDOW_POLICY = "128_space_by_tokens_final_full_window_shifted_backward_with_overlap"
AGGREGATION_POLICY = "valid_frontier_space_by_token_weighting_with_component_retention"

PRIMARY_ROLE = "primary"

REQUIRED_A01_COLUMNS = {
    "snapshot_order",
    "snapshot_id",
    "dataset_source",
    "repo_name",
    "snapshot_time",
    "snapshot_commit",
    "relative_path",
    "file_sha256",
    "code_unit_id",
    "code_unit_type",
    "aggregation_role",
    "qualified_name",
    "code_unit_sha256",
    "code_unit_relative_path",
    "character_count",
    "utf8_byte_count",
    "physical_line_count",
    "space_by_token_count",
}

CHECK_COLUMNS = ["check_name", "passed", "observed", "expected", "note"]

UNIQUE_SCORE_COLUMNS = [
    "code_unit_sha256",
    "code_unit_relative_path",
    "code_unit_type_representative",
    "space_by_tokens_total",
    "n_expected_windows",
    "n_attempted_windows",
    "n_valid_npr_windows",
    "n_invalid_npr_windows",
    "space_by_tokens_scored",
    "npr_coverage_ratio",
    "original_llm_tokens_all_windows",
    "original_llm_tokens_valid_windows",
    "code_unit_npr_space_by_token_weighted",
    "code_unit_original_log_rank_weighted",
    "code_unit_mean_perturbed_log_rank_weighted",
    "code_unit_npr_pooled_components",
    "partial_code_unit_score",
    "scoring_seconds",
    "cache_reused_this_run",
    "status",
    "config_fingerprint",
]

WINDOW_SCORE_COLUMNS = [
    "code_unit_sha256",
    "code_unit_relative_path",
    "window_index",
    "window_space_by_start",
    "window_space_by_end",
    "window_space_by_token_count",
    "window_marginal_space_by_token_count",
    "window_aggregation_weight_space_by_tokens",
    "overlaps_previous_window",
    "raw_char_start",
    "raw_char_end",
    "raw_char_count",
    "raw_utf8_byte_count",
    "window_text_sha256",
    "window_seed",
    "original_llm_token_count",
    "perturbed_llm_token_count_min",
    "perturbed_llm_token_count_mean",
    "perturbed_llm_token_count_max",
    "reported_model_context_limit",
    "original_llm_tokens_exceed_reported_context",
    "original_log_rank",
    "mean_perturbed_log_rank",
    "window_npr",
    "window_npr_valid",
    "window_npr_invalid_reason",
    "scoring_error_type",
    "scoring_error_message",
    "expected_perturbations",
    "valid_perturbation_scores",
    "scoring_seconds",
    "config_fingerprint",
]

FAILURE_COLUMNS = [
    "code_unit_sha256",
    "code_unit_relative_path",
    "stage",
    "error_type",
    "error_message",
]

ARTIFACT_ERROR_COLUMNS = [
    "code_unit_sha256",
    "code_unit_relative_path",
    "error_type",
    "observed",
    "expected",
]

REPRO_COLUMNS = [
    "code_unit_sha256",
    "original_weighted_npr",
    "rerun_weighted_npr",
    "weighted_npr_abs_diff",
    "original_pooled_npr",
    "rerun_pooled_npr",
    "pooled_npr_abs_diff",
    "window_count_match",
    "all_window_scores_match",
    "passed",
]


@dataclass(frozen=True)
class DetectorConfig:
    scoring_model: str
    window_size: int
    perturbations_per_window: int
    perturbation_type: str
    random_seed: int
    pct_words_masked: float
    span_length: int
    perturbation_chunk_size: int
    n_perturbation_rounds: int

    def payload(self, source_hashes: dict[str, str], package_versions: dict[str, str]) -> dict[str, Any]:
        return {
            "script_version": CACHE_SCORING_VERSION,
            "scoring_model": self.scoring_model,
            "window_size_space_by_tokens": self.window_size,
            "perturbations_per_window": self.perturbations_per_window,
            "perturbation_type": self.perturbation_type,
            "random_seed": self.random_seed,
            "pct_words_masked": self.pct_words_masked,
            "span_length": self.span_length,
            "perturbation_chunk_size": self.perturbation_chunk_size,
            "n_perturbation_rounds": self.n_perturbation_rounds,
            "window_policy": WINDOW_POLICY,
            "aggregation_policy": AGGREGATION_POLICY,
            "explicit_llm_truncation": False,
            "classification_enabled": False,
            "detector_source_hashes": source_hashes,
            "package_versions": package_versions,
        }


@dataclass
class RuntimeBundle:
    args: argparse.Namespace
    detector_main: Any
    get_rank: Callable[..., float]
    get_ranks: Callable[..., list[float]]
    model_config: dict[str, Any]
    torch: Any
    model_load_seconds: float
    gpu_name: str
    gpu_total_memory_bytes: int
    tokenizer_model_max_length: int | None
    model_context_fields: dict[str, int]
    reported_model_context_limit: int | None


@dataclass(frozen=True)
class RawWindow:
    index: int
    start_token: int
    end_token: int
    token_count: int
    marginal_token_count: int
    char_start: int
    char_end: int
    text: str
    overlaps_previous_window: bool


class AllWindowsInvalidError(RuntimeError):
    """Raised when a code unit has no finite NPR window.

    The attempted window diagnostics are attached so the caller can persist
    them even though no code-unit aggregate is available.
    """

    def __init__(self, message: str, window_rows: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.window_rows = window_rows or []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_json_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(raw)


def atomic_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    os.replace(tmp, path)


def atomic_csv(frame: pd.DataFrame, path: Path, columns: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = frame.copy()
    if columns is not None:
        for column in columns:
            if column not in output.columns:
                output[column] = pd.Series(dtype="object")
        output = output[list(columns)]
    tmp = path.with_suffix(path.suffix + ".tmp")
    output.to_csv(tmp, index=False, quoting=csv.QUOTE_MINIMAL)
    os.replace(tmp, path)


def append_jsonl(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False))
        stream.write("\n")


def sanitize_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def collect_package_versions() -> dict[str, str]:
    return {
        name: package_version(name)
        for name in ("numpy", "pandas", "scipy", "torch", "transformers", "loguru")
    }


def collect_detector_source_hashes(project_root: Path) -> dict[str, str]:
    candidates = {
        "main.py": ["main.py", "code-detection/main.py"],
        "baselines/rank.py": ["baselines/rank.py", "code-detection/baselines/rank.py"],
        "baselines/utils/loadmodel.py": [
            "baselines/utils/loadmodel.py",
            "code-detection/baselines/utils/loadmodel.py",
        ],
    }
    result: dict[str, str] = {}
    for logical_name, relative_candidates in candidates.items():
        selected = next(
            (project_root / relative for relative in relative_candidates if (project_root / relative).is_file()),
            None,
        )
        result[logical_name] = sha256_file(selected) if selected is not None else "missing"
    return result


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def set_all_seeds(seed: int, torch_module: Any | None = None) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch_module is not None:
        torch_module.manual_seed(seed)
        if torch_module.cuda.is_available():
            torch_module.cuda.manual_seed_all(seed)


def derive_window_seed(global_seed: int, code_unit_sha: str, window_index: int) -> int:
    raw = f"{global_seed}|{code_unit_sha}|{window_index}".encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return int.from_bytes(digest[:4], "big", signed=False)


def literal_space_token_spans(text: str) -> tuple[list[int], list[int]]:
    """Return raw character start/end offsets for every text.split(" ") token."""
    spaces = [index for index, char in enumerate(text) if char == " "]
    starts = [0] + [index + 1 for index in spaces]
    ends = spaces + [len(text)]
    if len(starts) != len(text.split(" ")) or len(ends) != len(starts):
        raise AssertionError("Literal-space token span construction is inconsistent with text.split(' ').")
    return starts, ends


def build_raw_windows(text: str, window_size: int) -> list[RawWindow]:
    """Build 128-space-by-token windows while slicing original raw source text."""
    if window_size < 1:
        raise ValueError("window_size must be positive")
    starts, ends = literal_space_token_spans(text)
    total_tokens = len(starts)

    intervals: list[tuple[int, int]] = []
    if total_tokens <= window_size:
        intervals.append((0, total_tokens))
    else:
        start = 0
        while start < total_tokens:
            end = min(start + window_size, total_tokens)
            if end - start < window_size and intervals:
                start = end - window_size
            intervals.append((start, end))
            if end >= total_tokens:
                break
            start = end

    windows: list[RawWindow] = []
    frontier = 0
    for index, (start_token, end_token) in enumerate(intervals):
        char_start = starts[start_token]
        char_end = ends[end_token - 1]
        raw_text = text[char_start:char_end]
        observed_token_count = len(raw_text.split(" "))
        expected_token_count = end_token - start_token
        if observed_token_count != expected_token_count:
            raise AssertionError(
                f"Raw window token mismatch: observed={observed_token_count}, expected={expected_token_count}"
            )
        marginal_start = max(start_token, frontier)
        marginal_count = max(0, end_token - marginal_start)
        frontier = max(frontier, end_token)
        windows.append(
            RawWindow(
                index=index,
                start_token=start_token,
                end_token=end_token,
                token_count=expected_token_count,
                marginal_token_count=marginal_count,
                char_start=char_start,
                char_end=char_end,
                text=raw_text,
                overlaps_previous_window=marginal_count < expected_token_count,
            )
        )
    if windows and sum(window.marginal_token_count for window in windows) != total_tokens:
        raise AssertionError("Window marginal counts do not cover the code unit exactly once.")
    return windows


def compute_aggregation_weights(window_rows: list[dict[str, Any]]) -> list[int]:
    """Weight each valid window by source tokens not covered by an earlier valid window."""
    weights: list[int] = []
    frontier = 0
    for row in window_rows:
        if not bool(row["window_npr_valid"]):
            weights.append(0)
            continue
        start = int(row["window_space_by_start"])
        end = int(row["window_space_by_end"])
        marginal_start = max(start, frontier)
        weights.append(max(0, end - marginal_start))
        frontier = max(frontier, end)
    return weights


def aggregate_code_unit(window_rows: list[dict[str, Any]], total_space_by_tokens: int) -> dict[str, Any]:
    weights = compute_aggregation_weights(window_rows)
    for row, weight in zip(window_rows, weights):
        row["window_aggregation_weight_space_by_tokens"] = int(weight)

    valid_rows = [
        row
        for row in window_rows
        if bool(row["window_npr_valid"])
        and int(row["window_aggregation_weight_space_by_tokens"]) > 0
    ]
    if not valid_rows:
        raise AllWindowsInvalidError(
            "All windows are invalid; no finite code-unit NPR can be computed.",
            window_rows=window_rows,
        )

    denominator = sum(int(row["window_aggregation_weight_space_by_tokens"]) for row in valid_rows)
    weighted_npr = sum(
        float(row["window_npr"]) * int(row["window_aggregation_weight_space_by_tokens"])
        for row in valid_rows
    ) / denominator
    weighted_original = sum(
        float(row["original_log_rank"]) * int(row["window_aggregation_weight_space_by_tokens"])
        for row in valid_rows
    ) / denominator
    weighted_perturbed = sum(
        float(row["mean_perturbed_log_rank"]) * int(row["window_aggregation_weight_space_by_tokens"])
        for row in valid_rows
    ) / denominator
    pooled_npr = weighted_perturbed / weighted_original if weighted_original else float("nan")

    return {
        "space_by_tokens_scored": int(denominator),
        "npr_coverage_ratio": float(denominator / total_space_by_tokens) if total_space_by_tokens else 0.0,
        "code_unit_npr_space_by_token_weighted": float(weighted_npr),
        "code_unit_original_log_rank_weighted": float(weighted_original),
        "code_unit_mean_perturbed_log_rank_weighted": float(weighted_perturbed),
        "code_unit_npr_pooled_components": float(pooled_npr),
    }


def classify_window_validity(scored: dict[str, Any]) -> tuple[bool, str | None]:
    if scored.get("scoring_error_type"):
        return False, "scoring_exception"
    npr = sanitize_float(scored.get("window_npr"))
    if npr is not None:
        return True, None
    if int(scored.get("valid_perturbation_scores", 0)) == 0:
        return False, "no_valid_perturbation_scores"
    if sanitize_float(scored.get("mean_perturbed_log_rank")) is None:
        return False, "nonfinite_mean_perturbed_log_rank"
    original = sanitize_float(scored.get("original_log_rank"))
    if original is None:
        return False, "nonfinite_original_log_rank"
    if original == 0.0:
        return False, "zero_original_log_rank"
    return False, "unknown_invalid_window"


def tokenizer_input_length(tokenizer: Any, text: str) -> int:
    """Measure the same default tokenizer input length used by get_rank()."""
    encoded = tokenizer(text, return_tensors="pt")
    return int(encoded["input_ids"].shape[-1])


def tokenizer_lengths(tokenizer: Any, texts: Iterable[str]) -> list[int]:
    return [tokenizer_input_length(tokenizer, text) for text in texts]


def build_detector_args(detector_main: Any, config: DetectorConfig, args: argparse.Namespace) -> argparse.Namespace:
    injected = [
        "--base_model_name",
        config.scoring_model,
        "--n_perturbation_list",
        str(config.perturbations_per_window),
        "--perturb_type",
        config.perturbation_type,
        "--pct_words_masked",
        str(config.pct_words_masked),
        "--span_length",
        str(config.span_length),
        "--chunk_size",
        str(config.perturbation_chunk_size),
        "--n_perturbation_rounds",
        str(config.n_perturbation_rounds),
        "--max_len",
        str(config.window_size),
        "--DEVICE",
        args.device,
        "--cache_dir",
        str(args.model_cache_dir),
        "--output_name",
        args.detector_output_name,
    ]
    saved_argv = sys.argv
    try:
        sys.argv = ["main.py", *injected]
        detector_args = detector_main.setup_args()
    finally:
        sys.argv = saved_argv
    return detector_args


def positive_context_value(value: Any) -> int | None:
    try:
        numeric = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if numeric <= 0 or numeric >= 10**12:
        return None
    return numeric


def load_runtime(config: DetectorConfig, args: argparse.Namespace) -> RuntimeBundle:
    project_root = str(args.project_root.resolve())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    import torch
    from loguru import logger

    import main as detector_main
    from baselines.rank import get_rank, get_ranks
    from baselines.utils.loadmodel import load_base_model_and_tokenizer
    from baselines.utils.preprocessing import preprocess_and_save

    if args.quiet_internal_progress:
        detector_main.tqdm = lambda iterable, **_: iterable
        logger.remove()
        logger.add(sys.stderr, level=args.detector_log_level)

    detector_args = build_detector_args(detector_main, config, args)
    set_all_seeds(config.random_seed, torch)

    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA scoring was requested, but torch.cuda.is_available() is false.")

    cache_dir, _, _ = preprocess_and_save(detector_args)
    model_config: dict[str, Any] = {"cache_dir": cache_dir}
    started = time.perf_counter()
    model_config = load_base_model_and_tokenizer(detector_args, model_config)
    model_load_seconds = time.perf_counter() - started
    model_config["base_model"].eval()

    tokenizer = model_config["base_tokenizer"]
    model = model_config["base_model"]
    tokenizer_limit = positive_context_value(getattr(tokenizer, "model_max_length", None))
    context_fields: dict[str, int] = {}
    for field in ("max_position_embeddings", "n_positions", "max_sequence_length", "seq_length"):
        value = positive_context_value(getattr(model.config, field, None))
        if value is not None:
            context_fields[field] = value
    candidates = list(context_fields.values())
    if tokenizer_limit is not None:
        candidates.append(tokenizer_limit)
    reported_context = min(candidates) if candidates else None

    gpu_name = "cpu"
    gpu_total_memory_bytes = 0
    if torch.cuda.is_available():
        gpu_name = str(torch.cuda.get_device_name(0))
        gpu_total_memory_bytes = int(torch.cuda.get_device_properties(0).total_memory)
        torch.cuda.reset_peak_memory_stats()

    return RuntimeBundle(
        args=detector_args,
        detector_main=detector_main,
        get_rank=get_rank,
        get_ranks=get_ranks,
        model_config=model_config,
        torch=torch,
        model_load_seconds=float(model_load_seconds),
        gpu_name=gpu_name,
        gpu_total_memory_bytes=gpu_total_memory_bytes,
        tokenizer_model_max_length=tokenizer_limit,
        model_context_fields=context_fields,
        reported_model_context_limit=reported_context,
    )


def score_window_real(text: str, seed: int, config: DetectorConfig, runtime: RuntimeBundle) -> dict[str, Any]:
    set_all_seeds(seed, runtime.torch)
    started = time.perf_counter()
    tokenizer = runtime.model_config["base_tokenizer"]
    original_llm_tokens: int | None = None
    perturbed_lengths: list[int] = []
    try:
        original_llm_tokens = tokenizer_input_length(tokenizer, text)
        original_log_rank = runtime.get_rank(text, runtime.args, runtime.model_config, log=True)
        perturbed = runtime.detector_main.perturb_texts(
            [text for _ in range(config.perturbations_per_window)],
            runtime.args,
            runtime.model_config,
        )
        perturbed_lengths = tokenizer_lengths(tokenizer, perturbed)
        perturbed_ranks = runtime.get_ranks(perturbed, runtime.args, runtime.model_config, log=True)
        valid = [float(value) for value in perturbed_ranks if math.isfinite(float(value))]
        mean_perturbed = float(np.mean(valid)) if valid else float("nan")
        npr = mean_perturbed / float(original_log_rank) if float(original_log_rank) else float("nan")
        return {
            "original_llm_token_count": original_llm_tokens,
            "perturbed_llm_token_count_min": min(perturbed_lengths) if perturbed_lengths else None,
            "perturbed_llm_token_count_mean": float(np.mean(perturbed_lengths)) if perturbed_lengths else None,
            "perturbed_llm_token_count_max": max(perturbed_lengths) if perturbed_lengths else None,
            "original_log_rank": float(original_log_rank),
            "mean_perturbed_log_rank": mean_perturbed,
            "window_npr": float(npr),
            "expected_perturbations": int(config.perturbations_per_window),
            "valid_perturbation_scores": int(len(valid)),
            "scoring_error_type": None,
            "scoring_error_message": None,
            "scoring_seconds": float(time.perf_counter() - started),
        }
    except Exception as error:
        if runtime.torch.cuda.is_available() and "out of memory" in str(error).lower():
            runtime.torch.cuda.empty_cache()
        return {
            "original_llm_token_count": original_llm_tokens,
            "perturbed_llm_token_count_min": min(perturbed_lengths) if perturbed_lengths else None,
            "perturbed_llm_token_count_mean": float(np.mean(perturbed_lengths)) if perturbed_lengths else None,
            "perturbed_llm_token_count_max": max(perturbed_lengths) if perturbed_lengths else None,
            "original_log_rank": None,
            "mean_perturbed_log_rank": None,
            "window_npr": None,
            "expected_perturbations": int(config.perturbations_per_window),
            "valid_perturbation_scores": 0,
            "scoring_error_type": type(error).__name__,
            "scoring_error_message": str(error)[:2000],
            "scoring_seconds": float(time.perf_counter() - started),
        }


def score_window_mock(text: str, seed: int, config: DetectorConfig, runtime: RuntimeBundle | None) -> dict[str, Any]:
    del runtime
    original = 1.2 + ((seed >> 8) % 1000) / 10000.0
    ratio = 1.0 + (seed % 800) / 1000.0
    mean_perturbed = original * ratio
    pseudo_llm = max(2, len(text.encode("utf-8")) // 4)
    return {
        "original_llm_token_count": int(pseudo_llm),
        "perturbed_llm_token_count_min": int(pseudo_llm),
        "perturbed_llm_token_count_mean": float(pseudo_llm),
        "perturbed_llm_token_count_max": int(pseudo_llm + 2),
        "original_log_rank": float(original),
        "mean_perturbed_log_rank": float(mean_perturbed),
        "window_npr": float(ratio),
        "expected_perturbations": int(config.perturbations_per_window),
        "valid_perturbation_scores": int(config.perturbations_per_window),
        "scoring_error_type": None,
        "scoring_error_message": None,
        "scoring_seconds": 0.001,
    }


def verify_artifacts(unique_manifest: pd.DataFrame, artifact_base: Path) -> pd.DataFrame:
    errors: list[dict[str, Any]] = []
    for row in unique_manifest.itertuples(index=False):
        code_sha = str(row.code_unit_sha256)
        relative = str(row.code_unit_relative_path)
        path = artifact_base / relative
        if not path.is_file():
            errors.append({
                "code_unit_sha256": code_sha,
                "code_unit_relative_path": relative,
                "error_type": "missing_artifact",
                "observed": str(path),
                "expected": "existing regular file",
            })
            continue
        raw = path.read_bytes()
        observed_sha = sha256_bytes(raw)
        if observed_sha != code_sha:
            errors.append({
                "code_unit_sha256": code_sha,
                "code_unit_relative_path": relative,
                "error_type": "sha256_mismatch",
                "observed": observed_sha,
                "expected": code_sha,
            })
        if len(raw) != int(row.utf8_byte_count):
            errors.append({
                "code_unit_sha256": code_sha,
                "code_unit_relative_path": relative,
                "error_type": "utf8_byte_count_mismatch",
                "observed": len(raw),
                "expected": int(row.utf8_byte_count),
            })
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            errors.append({
                "code_unit_sha256": code_sha,
                "code_unit_relative_path": relative,
                "error_type": "utf8_decode_error",
                "observed": str(error),
                "expected": "valid UTF-8",
            })
            continue
        if len(text) != int(row.character_count):
            errors.append({
                "code_unit_sha256": code_sha,
                "code_unit_relative_path": relative,
                "error_type": "character_count_mismatch",
                "observed": len(text),
                "expected": int(row.character_count),
            })
        if len(text.split(" ")) != int(row.space_by_token_count):
            errors.append({
                "code_unit_sha256": code_sha,
                "code_unit_relative_path": relative,
                "error_type": "space_by_token_count_mismatch",
                "observed": len(text.split(" ")),
                "expected": int(row.space_by_token_count),
            })
    return pd.DataFrame(errors, columns=ARTIFACT_ERROR_COLUMNS)


def build_unique_manifest(primary_manifest: pd.DataFrame, window_size: int) -> pd.DataFrame:
    consistency_columns = [
        "code_unit_relative_path",
        "character_count",
        "utf8_byte_count",
        "space_by_token_count",
    ]
    rows: list[pd.Series] = []
    for code_sha, group in primary_manifest.groupby("code_unit_sha256", sort=False):
        for column in consistency_columns:
            if group[column].astype(str).nunique(dropna=False) != 1:
                raise ValueError(f"Duplicate code-unit SHA has inconsistent {column}: {code_sha}")
        row = group.iloc[0].copy()
        row["manifest_occurrence_count"] = int(len(group))
        row["n_expected_windows"] = int(math.ceil(int(row["space_by_token_count"]) / window_size))
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=list(primary_manifest.columns) + ["manifest_occurrence_count", "n_expected_windows"])
    return pd.DataFrame(rows).sort_values("code_unit_sha256", kind="mergesort").reset_index(drop=True)


def cache_path(cache_dir: Path, fingerprint: str, code_sha: str) -> Path:
    return cache_dir / fingerprint[:16] / code_sha[:2] / f"{code_sha}.json"


def load_cached_result(path: Path, fingerprint: str, code_sha: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
    except Exception:
        return None
    if payload.get("config_fingerprint") != fingerprint or payload.get("code_unit_sha256") != code_sha:
        return None
    score = payload.get("unique_score")
    windows = payload.get("windows")
    if not isinstance(score, dict) or not isinstance(windows, list):
        return None
    return payload


def save_cached_result(path: Path, payload: dict[str, Any]) -> None:
    atomic_json(payload, path)


def score_code_unit(
    row: pd.Series,
    text: str,
    config: DetectorConfig,
    fingerprint: str,
    score_window: Callable[[str, int, DetectorConfig, RuntimeBundle | None], dict[str, Any]],
    runtime: RuntimeBundle | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    code_sha = str(row["code_unit_sha256"])
    relative = str(row["code_unit_relative_path"])
    total_tokens = int(row["space_by_token_count"])
    started = time.perf_counter()
    raw_windows = build_raw_windows(text, config.window_size)
    window_rows: list[dict[str, Any]] = []
    reported_context = runtime.reported_model_context_limit if runtime is not None else None

    for window in raw_windows:
        seed = derive_window_seed(config.random_seed, code_sha, window.index)
        scored = score_window(window.text, seed, config, runtime)
        valid, reason = classify_window_validity(scored)
        original_llm_count = scored.get("original_llm_token_count")
        exceeds = (
            bool(int(original_llm_count) > int(reported_context))
            if original_llm_count is not None and reported_context is not None
            else False
        )
        window_rows.append({
            "code_unit_sha256": code_sha,
            "code_unit_relative_path": relative,
            "window_index": int(window.index),
            "window_space_by_start": int(window.start_token),
            "window_space_by_end": int(window.end_token),
            "window_space_by_token_count": int(window.token_count),
            "window_marginal_space_by_token_count": int(window.marginal_token_count),
            "window_aggregation_weight_space_by_tokens": 0,
            "overlaps_previous_window": bool(window.overlaps_previous_window),
            "raw_char_start": int(window.char_start),
            "raw_char_end": int(window.char_end),
            "raw_char_count": int(len(window.text)),
            "raw_utf8_byte_count": int(len(window.text.encode("utf-8"))),
            "window_text_sha256": sha256_bytes(window.text.encode("utf-8")),
            "window_seed": int(seed),
            "original_llm_token_count": original_llm_count,
            "perturbed_llm_token_count_min": scored.get("perturbed_llm_token_count_min"),
            "perturbed_llm_token_count_mean": scored.get("perturbed_llm_token_count_mean"),
            "perturbed_llm_token_count_max": scored.get("perturbed_llm_token_count_max"),
            "reported_model_context_limit": reported_context,
            "original_llm_tokens_exceed_reported_context": bool(exceeds),
            "original_log_rank": sanitize_float(scored.get("original_log_rank")),
            "mean_perturbed_log_rank": sanitize_float(scored.get("mean_perturbed_log_rank")),
            "window_npr": sanitize_float(scored.get("window_npr")),
            "window_npr_valid": bool(valid),
            "window_npr_invalid_reason": reason,
            "scoring_error_type": scored.get("scoring_error_type"),
            "scoring_error_message": scored.get("scoring_error_message"),
            "expected_perturbations": int(scored.get("expected_perturbations", config.perturbations_per_window)),
            "valid_perturbation_scores": int(scored.get("valid_perturbation_scores", 0)),
            "scoring_seconds": float(scored.get("scoring_seconds", 0.0)),
            "config_fingerprint": fingerprint,
        })

    aggregate = aggregate_code_unit(window_rows, total_tokens)
    valid_rows = [row_out for row_out in window_rows if bool(row_out["window_npr_valid"])]
    unique_score = {
        "code_unit_sha256": code_sha,
        "code_unit_relative_path": relative,
        "code_unit_type_representative": str(row.get("code_unit_type", "")),
        "space_by_tokens_total": total_tokens,
        "n_expected_windows": int(len(raw_windows)),
        "n_attempted_windows": int(len(window_rows)),
        "n_valid_npr_windows": int(len(valid_rows)),
        "n_invalid_npr_windows": int(len(window_rows) - len(valid_rows)),
        "space_by_tokens_scored": int(aggregate["space_by_tokens_scored"]),
        "npr_coverage_ratio": float(aggregate["npr_coverage_ratio"]),
        "original_llm_tokens_all_windows": int(sum(int(r["original_llm_token_count"] or 0) for r in window_rows)),
        "original_llm_tokens_valid_windows": int(sum(int(r["original_llm_token_count"] or 0) for r in valid_rows)),
        "code_unit_npr_space_by_token_weighted": float(aggregate["code_unit_npr_space_by_token_weighted"]),
        "code_unit_original_log_rank_weighted": float(aggregate["code_unit_original_log_rank_weighted"]),
        "code_unit_mean_perturbed_log_rank_weighted": float(aggregate["code_unit_mean_perturbed_log_rank_weighted"]),
        "code_unit_npr_pooled_components": float(aggregate["code_unit_npr_pooled_components"]),
        "partial_code_unit_score": int(len(valid_rows) != len(window_rows)),
        "scoring_seconds": float(time.perf_counter() - started),
        "cache_reused_this_run": 0,
        "status": "scored",
        "config_fingerprint": fingerprint,
    }
    return unique_score, window_rows


def nullable_numeric_match(left: Any, right: Any, tolerance: float) -> bool:
    left_value = sanitize_float(left)
    right_value = sanitize_float(right)
    if left_value is None or right_value is None:
        return left_value is None and right_value is None
    return abs(left_value - right_value) <= tolerance


def compare_scoring_results(
    original_score: dict[str, Any],
    original_windows: list[dict[str, Any]],
    rerun_score: dict[str, Any],
    rerun_windows: list[dict[str, Any]],
    tolerance: float,
) -> dict[str, Any]:
    count_match = len(original_windows) == len(rerun_windows)
    all_windows_match = count_match
    if count_match:
        for left, right in zip(original_windows, rerun_windows):
            if int(left["window_index"]) != int(right["window_index"]):
                all_windows_match = False
                break
            for key in ("original_log_rank", "mean_perturbed_log_rank", "window_npr"):
                if not nullable_numeric_match(left.get(key), right.get(key), tolerance):
                    all_windows_match = False
                    break
            if left.get("window_npr_valid") != right.get("window_npr_valid"):
                all_windows_match = False
            if left.get("window_npr_invalid_reason") != right.get("window_npr_invalid_reason"):
                all_windows_match = False
            if not all_windows_match:
                break

    original_weighted = float(original_score["code_unit_npr_space_by_token_weighted"])
    rerun_weighted = float(rerun_score["code_unit_npr_space_by_token_weighted"])
    original_pooled = float(original_score["code_unit_npr_pooled_components"])
    rerun_pooled = float(rerun_score["code_unit_npr_pooled_components"])
    weighted_diff = abs(original_weighted - rerun_weighted)
    pooled_diff = abs(original_pooled - rerun_pooled)
    passed = bool(
        count_match
        and all_windows_match
        and weighted_diff <= tolerance
        and pooled_diff <= tolerance
    )
    return {
        "original_weighted_npr": original_weighted,
        "rerun_weighted_npr": rerun_weighted,
        "weighted_npr_abs_diff": weighted_diff,
        "original_pooled_npr": original_pooled,
        "rerun_pooled_npr": rerun_pooled,
        "pooled_npr_abs_diff": pooled_diff,
        "window_count_match": bool(count_match),
        "all_window_scores_match": bool(all_windows_match),
        "passed": passed,
    }


def run_reproducibility_checks(
    unique_manifest: pd.DataFrame,
    successful_results: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]],
    artifact_base: Path,
    config: DetectorConfig,
    fingerprint: str,
    score_window: Callable[[str, int, DetectorConfig, RuntimeBundle | None], dict[str, Any]],
    runtime: RuntimeBundle | None,
    count: int,
    tolerance: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if count <= 0:
        return pd.DataFrame(rows, columns=REPRO_COLUMNS)
    selected = unique_manifest[
        unique_manifest["code_unit_sha256"].astype(str).isin(successful_results)
    ].head(count)
    for _, manifest_row in selected.iterrows():
        code_sha = str(manifest_row["code_unit_sha256"])
        text = (artifact_base / str(manifest_row["code_unit_relative_path"])).read_bytes().decode("utf-8")
        rerun_score, rerun_windows = score_code_unit(
            manifest_row, text, config, fingerprint, score_window, runtime
        )
        original_score, original_windows = successful_results[code_sha]
        comparison = compare_scoring_results(
            original_score,
            original_windows,
            rerun_score,
            rerun_windows,
            tolerance,
        )
        rows.append({"code_unit_sha256": code_sha, **comparison})
    return pd.DataFrame(rows, columns=REPRO_COLUMNS)


def run_window_self_test() -> None:
    cases = [
        ("a b", 5, [(0, 2, 2, 2)]),
        ("a b c d", 2, [(0, 2, 2, 2), (2, 4, 2, 2)]),
        ("a b c", 2, [(0, 2, 2, 2), (1, 3, 2, 1)]),
        ("a  b", 2, [(0, 2, 2, 2), (1, 3, 2, 1)]),
        ("line1\nline2  z", 2, [(0, 2, 2, 2), (1, 3, 2, 1)]),
    ]
    for text, size, expected in cases:
        windows = build_raw_windows(text, size)
        observed = [
            (window.start_token, window.end_token, window.token_count, window.marginal_token_count)
            for window in windows
        ]
        if observed != expected:
            raise AssertionError(f"Window self-test failed for {text!r}: {observed} != {expected}")
        for window in windows:
            if window.text != text[window.char_start:window.char_end]:
                raise AssertionError("Raw window text is not a direct source slice.")
    stub = [
        {"window_space_by_start": 0, "window_space_by_end": 2, "window_npr_valid": True},
        {"window_space_by_start": 1, "window_space_by_end": 3, "window_npr_valid": True},
    ]
    if compute_aggregation_weights(stub) != [2, 1]:
        raise AssertionError("All-valid overlap weighting failed.")
    stub[0]["window_npr_valid"] = False
    if compute_aggregation_weights(stub) != [0, 2]:
        raise AssertionError("Partial overlap weighting failed.")


def run_self_test() -> None:
    run_window_self_test()
    config = DetectorConfig(
        scoring_model="mock/model",
        window_size=2,
        perturbations_per_window=3,
        perturbation_type="random-insert-space+newline",
        random_seed=123,
        pct_words_masked=0.5,
        span_length=2,
        perturbation_chunk_size=2,
        n_perturbation_rounds=1,
    )
    row = pd.Series({
        "code_unit_sha256": sha256_bytes(b"a b c"),
        "code_unit_relative_path": "code_units/mock.txt",
        "code_unit_type": "module_block",
        "space_by_token_count": 3,
    })
    score, windows = score_code_unit(
        row,
        "a b c",
        config,
        "mock-fingerprint",
        score_window_mock,
        None,
    )
    if score["n_expected_windows"] != 2 or len(windows) != 2:
        raise AssertionError("Mock code-unit scoring window count failed.")
    if score["space_by_tokens_scored"] != 3 or score["npr_coverage_ratio"] != 1.0:
        raise AssertionError("Mock code-unit coverage failed.")
    print("score_snapshot_npr self-test: PASS")


def prepare_output_dir(output_dir: Path, qc_dir: Path, overwrite: bool) -> None:
    if overwrite:
        for directory in (output_dir, qc_dir):
            if not directory.exists():
                continue
            for child in directory.iterdir():
                if child.name == "cache" or child == qc_dir:
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                elif child.is_file():
                    child.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)
    qc_dir.mkdir(parents=True, exist_ok=True)


def build_checks(
    primary_manifest: pd.DataFrame,
    unique_manifest: pd.DataFrame,
    artifact_errors: pd.DataFrame,
    unique_scores: pd.DataFrame,
    occurrence_scores: pd.DataFrame,
    window_scores: pd.DataFrame,
    failures: pd.DataFrame,
    reproducibility: pd.DataFrame,
) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, observed: Any, expected: Any, note: str = "") -> None:
        checks.append({
            "check_name": name,
            "passed": bool(passed),
            "observed": observed,
            "expected": expected,
            "note": note,
        })

    add("a01_primary_manifest_nonempty", len(primary_manifest) > 0, len(primary_manifest), "> 0")
    add(
        "unique_hash_count_matches_manifest",
        len(unique_manifest) == primary_manifest["code_unit_sha256"].nunique(),
        len(unique_manifest),
        primary_manifest["code_unit_sha256"].nunique(),
    )
    add("artifact_integrity_failures_zero", len(artifact_errors) == 0, len(artifact_errors), 0)
    add(
        "unique_scores_plus_failures_cover_unique_units",
        len(unique_scores) + len(failures) == len(unique_manifest),
        len(unique_scores) + len(failures),
        len(unique_manifest),
    )
    add(
        "occurrence_scores_cover_successful_manifest_rows",
        len(occurrence_scores) == int(primary_manifest["code_unit_sha256"].isin(set(unique_scores["code_unit_sha256"])).sum()),
        len(occurrence_scores),
        int(primary_manifest["code_unit_sha256"].isin(set(unique_scores["code_unit_sha256"])).sum()),
    )
    expected_windows_success = 0
    successful_window_rows = 0
    if not unique_scores.empty:
        expected_windows_success = int(unique_scores["n_expected_windows"].sum())
        successful_hashes = set(unique_scores["code_unit_sha256"].astype(str))
        successful_window_rows = int(window_scores["code_unit_sha256"].astype(str).isin(successful_hashes).sum())
    add(
        "window_rows_match_successful_expected_windows",
        successful_window_rows == expected_windows_success,
        successful_window_rows,
        expected_windows_success,
        "Failed all-window units may additionally retain diagnostic window rows.",
    )
    if not unique_scores.empty:
        coverage_ok = unique_scores["npr_coverage_ratio"].between(0.0, 1.0, inclusive="both").all()
        finite_scores = np.isfinite(unique_scores["code_unit_npr_space_by_token_weighted"].astype(float)).all()
        pooled_finite = np.isfinite(unique_scores["code_unit_npr_pooled_components"].astype(float)).all()
    else:
        coverage_ok = True
        finite_scores = True
        pooled_finite = True
    add("coverage_ratio_in_unit_interval", bool(coverage_ok), int(bool(coverage_ok)), 1)
    add("weighted_npr_finite_for_successes", bool(finite_scores), int(bool(finite_scores)), 1)
    add("pooled_component_npr_finite_for_successes", bool(pooled_finite), int(bool(pooled_finite)), 1)
    if not reproducibility.empty:
        repro_ok = reproducibility["passed"].astype(bool).all()
        add("same_seed_reproducibility", bool(repro_ok), int(reproducibility["passed"].astype(bool).sum()), len(reproducibility))
    else:
        add("same_seed_reproducibility", True, 0, "0 or configured checks")
    classification_columns = {"agc_like", "hwc_like", "agc_threshold", "decision_rule"}
    observed_classification = classification_columns & set(unique_scores.columns)
    add(
        "no_agc_hwc_classification_columns",
        not observed_classification,
        ",".join(sorted(observed_classification)),
        "none",
    )
    add(
        "no_explicit_llm_truncation",
        True,
        "base tokenizer scoring delegated to baselines.rank.get_rank without max_length/truncation",
        "no explicit truncation",
    )
    return pd.DataFrame(checks, columns=CHECK_COLUMNS)


def expand_occurrence_scores(primary_manifest: pd.DataFrame, unique_scores: pd.DataFrame) -> pd.DataFrame:
    score_columns = [column for column in UNIQUE_SCORE_COLUMNS if column != "code_unit_relative_path"]
    expanded = primary_manifest.merge(
        unique_scores[score_columns],
        on="code_unit_sha256",
        how="inner",
        validate="many_to_one",
    )
    return expanded


def run_analysis(args: argparse.Namespace) -> int:
    started_utc = utc_now()
    started = time.perf_counter()
    config = DetectorConfig(
        scoring_model=args.scoring_model,
        window_size=args.window_size,
        perturbations_per_window=args.perturbations_per_window,
        perturbation_type=args.perturbation_type,
        random_seed=args.random_seed,
        pct_words_masked=args.pct_words_masked,
        span_length=args.span_length,
        perturbation_chunk_size=args.perturbation_chunk_size,
        n_perturbation_rounds=args.n_perturbation_rounds,
    )

    project_root = args.project_root.resolve()
    source_hashes = collect_detector_source_hashes(project_root)
    package_versions = collect_package_versions()
    fingerprint_payload = config.payload(source_hashes, package_versions)
    fingerprint = stable_json_hash(fingerprint_payload)

    prepare_output_dir(args.output_dir, args.qc_dir, args.overwrite_output)
    if args.clear_cache and args.cache_dir.exists():
        shutil.rmtree(args.cache_dir)
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    manifest = pd.read_csv(args.input_code_unit_manifest)
    require_columns(manifest, REQUIRED_A01_COLUMNS, "A01 code-unit manifest")
    primary_manifest = manifest.loc[manifest["aggregation_role"].astype(str).eq(PRIMARY_ROLE)].copy()
    unique_manifest = build_unique_manifest(primary_manifest, config.window_size)
    artifact_errors = verify_artifacts(unique_manifest, args.artifact_base)
    atomic_csv(artifact_errors, args.qc_dir / "python_snapshot_npr_artifact_errors.csv", ARTIFACT_ERROR_COLUMNS)
    if not artifact_errors.empty:
        raise RuntimeError(f"A01 artifact validation failed for {len(artifact_errors)} record(s).")

    unique_score_rows: list[dict[str, Any]] = []
    all_window_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    successful_results: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    bodies_reused = 0
    bodies_scored = 0
    runtime: RuntimeBundle | None = None
    model_loaded_this_run = False
    score_window = score_window_mock if args.mock_scoring else score_window_real

    cache_misses: list[pd.Series] = []
    for _, row in unique_manifest.iterrows():
        code_sha = str(row["code_unit_sha256"])
        cpath = cache_path(args.cache_dir, fingerprint, code_sha)
        cached = load_cached_result(cpath, fingerprint, code_sha)
        if cached is None:
            cache_misses.append(row)
            continue
        unique_score = dict(cached["unique_score"])
        unique_score["cache_reused_this_run"] = 1
        unique_score["status"] = "cached"
        windows = [dict(item) for item in cached["windows"]]
        unique_score_rows.append(unique_score)
        all_window_rows.extend(windows)
        successful_results[code_sha] = (unique_score, windows)
        bodies_reused += 1

    if cache_misses and not args.mock_scoring:
        runtime = load_runtime(config, args)
        model_loaded_this_run = True

    for index, row in enumerate(cache_misses, start=1):
        code_sha = str(row["code_unit_sha256"])
        relative = str(row["code_unit_relative_path"])
        try:
            text = (args.artifact_base / relative).read_bytes().decode("utf-8")
            unique_score, windows = score_code_unit(
                row,
                text,
                config,
                fingerprint,
                score_window,
                runtime,
            )
            unique_score_rows.append(unique_score)
            all_window_rows.extend(windows)
            successful_results[code_sha] = (unique_score, windows)
            save_cached_result(
                cache_path(args.cache_dir, fingerprint, code_sha),
                {
                    "schema_version": 1,
                    "created_utc": utc_now(),
                    "config_fingerprint": fingerprint,
                    "code_unit_sha256": code_sha,
                    "unique_score": unique_score,
                    "windows": windows,
                },
            )
            bodies_scored += 1
        except Exception as error:
            if isinstance(error, AllWindowsInvalidError):
                all_window_rows.extend(error.window_rows)
            failure_rows.append({
                "code_unit_sha256": code_sha,
                "code_unit_relative_path": relative,
                "stage": "score_code_unit",
                "error_type": type(error).__name__,
                "error_message": str(error)[:4000],
            })
        if args.progress_every_units > 0 and index % args.progress_every_units == 0:
            print(
                f"Progress: attempted {index}/{len(cache_misses)} cache-miss units; "
                f"successful={bodies_scored}, failures={len(failure_rows)}",
                flush=True,
            )

    unique_scores = pd.DataFrame(unique_score_rows, columns=UNIQUE_SCORE_COLUMNS)
    if not unique_scores.empty:
        unique_scores = unique_scores.sort_values("code_unit_sha256", kind="mergesort").reset_index(drop=True)
    window_scores = pd.DataFrame(all_window_rows, columns=WINDOW_SCORE_COLUMNS)
    if not window_scores.empty:
        window_scores = window_scores.sort_values(["code_unit_sha256", "window_index"], kind="mergesort").reset_index(drop=True)
    failures = pd.DataFrame(failure_rows, columns=FAILURE_COLUMNS)
    occurrence_scores = expand_occurrence_scores(primary_manifest, unique_scores) if not unique_scores.empty else pd.DataFrame()

    repro_path = args.qc_dir / "python_snapshot_npr_reproducibility_checks.csv"
    if bodies_scored == 0 and repro_path.is_file() and not args.overwrite_output:
        reproducibility = pd.read_csv(repro_path)
    else:
        if args.reproducibility_check_units > 0 and not successful_results:
            reproducibility = pd.DataFrame(columns=REPRO_COLUMNS)
        else:
            if args.reproducibility_check_units > 0 and runtime is None and not args.mock_scoring:
                runtime = load_runtime(config, args)
                model_loaded_this_run = True
            reproducibility = run_reproducibility_checks(
                unique_manifest,
                successful_results,
                args.artifact_base,
                config,
                fingerprint,
                score_window,
                runtime,
                args.reproducibility_check_units,
                args.reproducibility_tolerance,
            )

    checks = build_checks(
        primary_manifest,
        unique_manifest,
        artifact_errors,
        unique_scores,
        occurrence_scores,
        window_scores,
        failures,
        reproducibility,
    )
    failed_checks = int((~checks["passed"].astype(bool)).sum())

    status = "PASS"
    if failed_checks > 0:
        status = "FAIL"
    elif len(failures) > 0:
        status = "PARTIAL"

    atomic_csv(unique_scores, args.output_dir / "python_unique_code_unit_npr_scores.csv", UNIQUE_SCORE_COLUMNS)
    atomic_csv(occurrence_scores, args.output_dir / "python_code_unit_npr_scores.csv")
    atomic_csv(window_scores, args.output_dir / "python_window_npr_scores.csv", WINDOW_SCORE_COLUMNS)
    atomic_csv(failures, args.output_dir / "python_snapshot_npr_failures.csv", FAILURE_COLUMNS)
    atomic_csv(checks, args.qc_dir / "python_snapshot_npr_checks.csv", CHECK_COLUMNS)
    atomic_csv(reproducibility, repro_path, REPRO_COLUMNS)

    elapsed = time.perf_counter() - started
    context_exceed_windows = 0
    invalid_windows = 0
    partial_units = 0
    if not window_scores.empty:
        context_exceed_windows = int(window_scores["original_llm_tokens_exceed_reported_context"].astype(bool).sum())
        invalid_windows = int((~window_scores["window_npr_valid"].astype(bool)).sum())
    if not unique_scores.empty:
        partial_units = int(unique_scores["partial_code_unit_score"].astype(int).sum())

    summary = {
        "status": status,
        "implementation_version": "v3",
        "config_fingerprint": fingerprint,
        "a01_manifest_rows": int(len(manifest)),
        "primary_code_unit_occurrences": int(len(primary_manifest)),
        "unique_primary_code_units": int(len(unique_manifest)),
        "successful_unique_code_units": int(len(unique_scores)),
        "failed_unique_code_units": int(len(failures)),
        "code_unit_occurrence_scores": int(len(occurrence_scores)),
        "window_score_rows": int(len(window_scores)),
        "valid_npr_windows": int(len(window_scores) - invalid_windows),
        "invalid_npr_windows": int(invalid_windows),
        "partial_code_unit_scores": int(partial_units),
        "windows_exceeding_reported_model_context": int(context_exceed_windows),
        "cache_reused_unique_code_units": int(bodies_reused),
        "newly_scored_unique_code_units": int(bodies_scored),
        "model_loaded_this_run": bool(model_loaded_this_run),
        "reproducibility_checks": int(len(reproducibility)),
        "reproducibility_failures": int((~reproducibility["passed"].astype(bool)).sum()) if not reproducibility.empty else 0,
        "failed_checks": int(failed_checks),
        "elapsed_seconds": float(elapsed),
    }
    atomic_json(summary, args.qc_dir / "python_snapshot_npr_summary.json")

    runtime_metadata = {
        "model_loaded": bool(runtime is not None),
        "model_load_seconds": float(runtime.model_load_seconds) if runtime is not None else 0.0,
        "gpu_name": runtime.gpu_name if runtime is not None else "not_loaded",
        "gpu_total_memory_bytes": int(runtime.gpu_total_memory_bytes) if runtime is not None else 0,
        "tokenizer_model_max_length": runtime.tokenizer_model_max_length if runtime is not None else None,
        "model_context_fields": runtime.model_context_fields if runtime is not None else {},
        "reported_model_context_limit": runtime.reported_model_context_limit if runtime is not None else None,
        "explicit_llm_truncation": False,
    }
    metadata = {
        "script_version": SCRIPT_VERSION,
        "started_utc": started_utc,
        "completed_utc": utc_now(),
        "project_root": str(project_root),
        "input_code_unit_manifest": str(args.input_code_unit_manifest.resolve()),
        "input_code_unit_manifest_sha256": sha256_file(args.input_code_unit_manifest),
        "artifact_base": str(args.artifact_base.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "cache_dir": str(args.cache_dir.resolve()),
        "config_fingerprint": fingerprint,
        "scoring_configuration": fingerprint_payload,
        "cache_scoring_version": CACHE_SCORING_VERSION,
        "runtime": runtime_metadata,
        "methodology_notes": {
            "primary_window_coordinate": "space-by tokens from text.split(\" \")",
            "window_text_source": "direct raw character slice from A01 UTF-8 code-unit artifact",
            "llm_token_count_role": "diagnostic only; not the primary window coordinate",
            "llm_truncation_policy": "none added by A02; scoring uses baselines.rank.get_rank default tokenizer call",
            "classification": "disabled; NPR remains continuous",
            "weighted_npr": "space-by-token weighted mean of valid window NPR ratios",
            "pooled_component_npr": "weighted perturbed-log-rank component divided by weighted original-log-rank component",
            "llm_token_total_semantics": "sum across model-scored windows; overlapping final windows can double-count LLM workload tokens",
        },
        "package_versions": package_versions,
        "detector_source_hashes": source_hashes,
    }
    atomic_json(metadata, args.qc_dir / "python_snapshot_npr_metadata.json")
    append_jsonl(
        {
            "started_utc": started_utc,
            "completed_utc": utc_now(),
            "status": status,
            "config_fingerprint": fingerprint,
            "newly_scored_unique_code_units": int(bodies_scored),
            "cache_reused_unique_code_units": int(bodies_reused),
            "model_loaded_this_run": bool(model_loaded_this_run),
            "elapsed_seconds": float(elapsed),
        },
        args.qc_dir / "python_snapshot_npr_run_history.jsonl",
    )

    print("=" * 78)
    print("run-x-a02 snapshot NPR scoring")
    print(f"Status:                         {status}")
    print(f"Primary code-unit occurrences:  {len(primary_manifest)}")
    print(f"Unique primary code units:      {len(unique_manifest)}")
    print(f"Successful unique code units:   {len(unique_scores)}")
    print(f"Failed unique code units:       {len(failures)}")
    print(f"Window score rows:              {len(window_scores)}")
    print(f"Invalid NPR windows:            {invalid_windows}")
    print(f"Partial code-unit scores:       {partial_units}")
    print(f"Newly scored units:             {bodies_scored}")
    print(f"Cache-reused units:             {bodies_reused}")
    print(f"Model loaded this run:          {int(model_loaded_this_run)}")
    print(f"Failed QC checks:               {failed_checks}")
    print(f"Config fingerprint:             {fingerprint}")
    print(f"Output directory:               {args.output_dir}")
    print("=" * 78)

    if status == "FAIL":
        return 5
    if status == "PARTIAL" and args.require_all_completed:
        return 6
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score A01 snapshot code units with continuous NPR.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--input-code-unit-manifest",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a01/python_code_unit_manifest.csv"),
    )
    parser.add_argument(
        "--artifact-base",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a01"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a02"),
    )
    parser.add_argument("--qc-dir", type=Path, default=None)
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--scoring-model", default="bigcode/starcoder2-7b")
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--perturbations-per-window", type=int, default=50)
    parser.add_argument("--perturbation-type", default="random-insert-space+newline")
    parser.add_argument("--random-seed", type=int, default=20260723)
    parser.add_argument("--pct-words-masked", type=float, default=0.5)
    parser.add_argument("--span-length", type=int, default=2)
    parser.add_argument("--perturbation-chunk-size", type=int, default=10)
    parser.add_argument("--n-perturbation-rounds", type=int, default=1)
    parser.add_argument("--device", default="cuda")
    parser.add_argument(
        "--model-cache-dir",
        type=Path,
        default=Path("~/.cache/huggingface/hub").expanduser(),
    )
    parser.add_argument("--detector-output-name", default="run_x_a02_snapshot_npr")
    parser.add_argument("--quiet-internal-progress", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--detector-log-level", default="WARNING")
    parser.add_argument("--progress-every-units", type=int, default=5)
    parser.add_argument("--reproducibility-check-units", type=int, default=1)
    parser.add_argument("--reproducibility-tolerance", type=float, default=1e-12)
    parser.add_argument("--overwrite-output", action="store_true")
    parser.add_argument("--clear-cache", action="store_true")
    parser.add_argument("--require-all-completed", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--mock-scoring", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.qc_dir is None:
        args.qc_dir = args.output_dir / "qc"
    if args.cache_dir is None:
        args.cache_dir = args.output_dir / "cache"
    args.model_cache_dir = args.model_cache_dir.expanduser()
    return args


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return
    raise SystemExit(run_analysis(args))


if __name__ == "__main__":
    main()
