#!/usr/bin/env python3
"""Run a dual-profile StarCoder2 NPR pilot on unique implementation bodies.

This experiment follows run-1a, run-1b, and run-1b2.

Purpose:
    1. Select a deterministic calibration-range sample from 100-200
       literal-space tokens.
    2. Select a deterministic long-body sample above 200 literal-space tokens.
    3. Score each unique implementation body with the existing DetectCodeGPT
       perturbation and rank-scoring implementation.
    4. Measure profile-specific throughput, cache size, GPU memory, resume
       behavior, and same-seed reproducibility before a full scoring run.

Scientific unit:
    One approved commit-function change event.

Computational unit:
    One unique implementation body identified by SHA-256.

The program does not aggregate repository-month outcomes or run DiD. The
current run-1b specification remains an audit input; this pilot does not
silently redefine the primary specification.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import pandas as pd


SCRIPT_VERSION = "run-1c-v4"
PARTIAL_BODY_POLICY = "incomplete_tail_zero_original_rank_only-v1"

UNIQUE_BODY_REQUIRED = {
    "function_body_sha256",
    "function_body_relative_path",
    "function_body_character_count",
    "function_body_utf8_byte_count",
    "function_body_line_count",
    "function_body_split_space_token_count",
    "function_body_nonempty_whitespace_token_count",
    "n_128_token_windows",
    "tail_window_token_count",
    "referencing_function_event_count",
}

EVENT_REQUIRED = {
    "function_event_id",
    "dataset_source",
    "repo_name",
    "time",
    "function_body_sha256",
    "input_preparation_complete",
    "body_extraction_status",
}

PANEL_REQUIRED = {"dataset_source", "repo_name", "time", "time_to_event"}

SUPPORT_REQUIRED = {
    "spec_name",
    "eligible_unique_bodies",
    "total_windows",
    "total_scoring_sequences",
}

CHECK_COLUMNS = ["check_name", "passed", "observed", "expected", "note"]

BODY_SCORE_COLUMNS = [
    "profile_name",
    "stratum_name",
    "sample_rank",
    "function_body_sha256",
    "function_body_relative_path",
    "function_body_split_space_token_count",
    "n_expected_windows",
    "n_scored_windows",
    # Partial-body scoring audit fields (added to support a body succeeding
    # when at least one window is valid, instead of discarding the whole
    # body's already-computed function_npr -- see score_one_body()).
    "n_attempted_windows",
    "n_valid_npr_windows",
    "n_invalid_npr_windows",
    "valid_npr_token_count",
    "invalid_npr_token_count",
    "partial_body_score",
    "referencing_function_event_count",
    "function_npr",
    "agc_threshold",
    "agc_like",
    "hwc_like",
    "scoring_seconds",
    "cache_result_bytes",
    "status",
]

WINDOW_SCORE_COLUMNS = [
    "profile_name",
    "stratum_name",
    "sample_rank",
    "function_body_sha256",
    "chunk_index",
    "start_token_body",
    "end_token_body",
    "chunk_token_count",
    "window_seed",
    "is_last_window",
    "is_incomplete_tail_window",
    "original_log_rank",
    "mean_perturbed_log_rank",
    "window_npr",
    # window_npr_valid/window_npr_invalid_reason record why a window's
    # window_npr is null, instead of leaving null as the only signal --
    # see classify_window_validity().
    "window_npr_valid",
    "window_npr_invalid_reason",
    "expected_perturbations",
    "valid_perturbation_scores",
    "scoring_seconds",
]

FAILURE_COLUMNS = [
    "profile_name",
    "stratum_name",
    "sample_rank",
    "function_body_sha256",
    "stage",
    "error_type",
    "error_message",
]

ARTIFACT_ERROR_COLUMNS = [
    "function_body_sha256",
    "function_body_relative_path",
    "error_type",
    "observed",
    "expected",
]

REPRO_COLUMNS = [
    "profile_name",
    "function_body_sha256",
    "selection_reason",
    "original_function_npr",
    "rerun_function_npr",
    "absolute_difference",
    "window_count_match",
    "all_window_scores_match",
    "passed",
]


@dataclass(frozen=True)
class Paths:
    input_unique_bodies: Path
    input_events: Path
    input_panel: Path
    input_support: Path
    input_specification: Path
    body_artifact_base: Path
    output_dir: Path
    qc_dir: Path
    cache_dir: Path


@dataclass(frozen=True)
class DetectorConfig:
    specification_status: str
    specification_primary: str
    scoring_model: str
    window_size: int
    perturbations_per_window: int
    perturbation_type: str
    function_aggregation: str
    agc_threshold: float
    random_seed: int
    eligibility_specifications: tuple[dict[str, Any], ...]

    def fingerprint_payload(self, profile_definition: dict[str, Any]) -> dict[str, Any]:
        return {
            "script_version": SCRIPT_VERSION,
            "specification_status": self.specification_status,
            "specification_primary": self.specification_primary,
            "scoring_model": self.scoring_model,
            "window_size": self.window_size,
            "perturbations_per_window": self.perturbations_per_window,
            "perturbation_type": self.perturbation_type,
            "function_aggregation": self.function_aggregation,
            "agc_threshold": self.agc_threshold,
            "random_seed": self.random_seed,
            "partial_body_policy": PARTIAL_BODY_POLICY,
            "profile_definition": profile_definition,
        }


@dataclass
class RuntimeBundle:
    args: argparse.Namespace
    detector_main: Any
    get_rank: Callable[..., float]
    get_ranks: Callable[..., list[float]]
    model_config: dict[str, Any]
    torch: Any
    transformers: Any
    scipy: Any
    model_load_seconds: float
    gpu_name: str
    gpu_total_memory_bytes: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    os.replace(tmp, path)


def atomic_csv(frame: pd.DataFrame, path: Path, columns: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if columns is not None:
        for column in columns:
            if column not in frame.columns:
                frame[column] = pd.Series(dtype="object")
        frame = frame[list(columns)]
    frame.to_csv(tmp, index=False, quoting=csv.QUOTE_MINIMAL)
    os.replace(tmp, path)


def append_jsonl(record: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False))
        stream.write("\n")


def parse_bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y"})


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def parse_ranges(text: str, allow_open_max: bool = False) -> list[tuple[int, int | None]]:
    ranges: list[tuple[int, int | None]] = []
    for raw in str(text).split(","):
        raw = raw.strip()
        if not raw:
            continue
        if ":" not in raw:
            raise ValueError(f"Range must use MIN:MAX syntax: {raw!r}")
        left, right = raw.split(":", 1)
        minimum = int(left)
        maximum = None if allow_open_max and right.strip() == "" else int(right)
        if minimum < 1:
            raise ValueError(f"Range minimum must be positive: {raw!r}")
        if maximum is not None and maximum < minimum:
            raise ValueError(f"Range maximum is below minimum: {raw!r}")
        ranges.append((minimum, maximum))
    if not ranges:
        raise ValueError("At least one range is required.")
    return ranges


def range_label(prefix: str, minimum: int, maximum: int | None) -> str:
    if maximum is None:
        return f"{prefix}{minimum}_plus"
    if minimum == maximum:
        return f"{prefix}{minimum}"
    return f"{prefix}{minimum}_{maximum}"


def allocation(total: int, count: int) -> list[int]:
    if total <= 0 or count <= 0:
        raise ValueError("Allocation total and stratum count must be positive.")
    base, remainder = divmod(total, count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


def deterministic_order(frame: pd.DataFrame, seed: int, namespace: str) -> pd.DataFrame:
    ordered = frame.copy()
    ordered["deterministic_sample_key"] = ordered["function_body_sha256"].map(
        lambda value: stable_hash(f"{seed}|{namespace}|{value}")
    )
    return ordered.sort_values(
        ["deterministic_sample_key", "function_body_sha256"], kind="mergesort"
    )


def load_detector_config(path: Path) -> DetectorConfig:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    required = {
        "status",
        "primary_spec",
        "scoring_model",
        "window_size_literal_space_tokens",
        "perturbations_per_window",
        "perturbation_type",
        "function_aggregation",
        "agc_threshold",
        "random_seed",
        "eligibility_specifications",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"Specification JSON is missing keys: {missing}")
    return DetectorConfig(
        specification_status=str(payload["status"]),
        specification_primary=str(payload["primary_spec"]),
        scoring_model=str(payload["scoring_model"]),
        window_size=int(payload["window_size_literal_space_tokens"]),
        perturbations_per_window=int(payload["perturbations_per_window"]),
        perturbation_type=str(payload["perturbation_type"]),
        function_aggregation=str(payload["function_aggregation"]),
        agc_threshold=float(payload["agc_threshold"]),
        random_seed=int(payload["random_seed"]),
        eligibility_specifications=tuple(payload["eligibility_specifications"]),
    )


def find_spec(config: DetectorConfig, name: str) -> dict[str, Any]:
    matches = [spec for spec in config.eligibility_specifications if str(spec.get("name")) == name]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one eligibility specification named {name!r}; found {len(matches)}")
    return matches[0]


def build_profile_definition(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "calibration_profile_name": args.calibration_profile_name,
        "calibration_profile_size": args.calibration_profile_size,
        "calibration_bands": args.calibration_bands,
        "long_profile_name": args.long_profile_name,
        "long_profile_size": args.long_profile_size,
        "long_window_strata": args.long_window_strata,
        "sampling_method": "seeded_sha256_order",
    }


def config_fingerprint(config: DetectorConfig, profile_definition: dict[str, Any]) -> str:
    payload = config.fingerprint_payload(profile_definition)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def select_calibration_profile(
    unique_bodies: pd.DataFrame,
    config: DetectorConfig,
    profile_name: str,
    sample_size: int,
    ranges: list[tuple[int, int | None]],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    targets = allocation(sample_size, len(ranges))
    selected_parts: list[pd.DataFrame] = []
    support: list[dict[str, Any]] = []
    token_count = unique_bodies["function_body_split_space_token_count"]

    for index, ((minimum, maximum), target) in enumerate(zip(ranges, targets)):
        if maximum is None:
            raise ValueError("Calibration bands must have a finite maximum.")
        mask = token_count.ge(minimum) & token_count.le(maximum)
        candidates = unique_bodies.loc[mask].copy()
        label = range_label("tokens_", minimum, maximum)
        ordered = deterministic_order(candidates, config.random_seed, f"{profile_name}|{label}")
        chosen = ordered.head(target).copy()
        chosen["profile_name"] = profile_name
        chosen["stratum_name"] = label
        chosen["stratum_order"] = index
        chosen["stratum_sample_target"] = target
        chosen["sampling_fill_mode"] = "stratum"
        selected_parts.append(chosen)
        support.append(
            {
                "profile_name": profile_name,
                "stratum_name": label,
                "minimum_literal_space_tokens": minimum,
                "maximum_literal_space_tokens": maximum,
                "available_unique_bodies": int(len(candidates)),
                "target_unique_bodies": int(target),
                "selected_unique_bodies": int(len(chosen)),
                "target_met": bool(len(chosen) == target),
            }
        )

    selected = pd.concat(selected_parts, ignore_index=True) if selected_parts else pd.DataFrame()
    if len(selected) != sample_size:
        short = [row for row in support if not row["target_met"]]
        raise RuntimeError(
            f"Calibration profile could select only {len(selected)}/{sample_size} bodies; "
            f"under-supported strata={short}"
        )
    return selected, support


def select_long_profile(
    unique_bodies: pd.DataFrame,
    config: DetectorConfig,
    profile_name: str,
    sample_size: int,
    ranges: list[tuple[int, int | None]],
    minimum_body_tokens: int,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    targets = allocation(sample_size, len(ranges))
    base_candidates = unique_bodies.loc[
        unique_bodies["function_body_split_space_token_count"].gt(minimum_body_tokens)
    ].copy()
    selected_parts: list[pd.DataFrame] = []
    support: list[dict[str, Any]] = []
    selected_hashes: set[str] = set()

    for index, ((minimum, maximum), target) in enumerate(zip(ranges, targets)):
        windows = base_candidates["n_128_token_windows"]
        mask = windows.ge(minimum)
        if maximum is not None:
            mask &= windows.le(maximum)
        candidates = base_candidates.loc[mask].copy()
        label = range_label("windows_", minimum, maximum)
        ordered = deterministic_order(candidates, config.random_seed, f"{profile_name}|{label}")
        chosen = ordered.head(target).copy()
        chosen["profile_name"] = profile_name
        chosen["stratum_name"] = label
        chosen["stratum_order"] = index
        chosen["stratum_sample_target"] = target
        chosen["sampling_fill_mode"] = "stratum"
        selected_parts.append(chosen)
        selected_hashes.update(chosen["function_body_sha256"].astype(str))
        support.append(
            {
                "profile_name": profile_name,
                "stratum_name": label,
                "minimum_windows": minimum,
                "maximum_windows": maximum,
                "available_unique_bodies": int(len(candidates)),
                "target_unique_bodies": int(target),
                "selected_unique_bodies": int(len(chosen)),
                "target_met": bool(len(chosen) == target),
            }
        )

    selected = pd.concat(selected_parts, ignore_index=True) if selected_parts else pd.DataFrame()
    missing = sample_size - len(selected)
    if missing > 0:
        fallback = base_candidates.loc[
            ~base_candidates["function_body_sha256"].astype(str).isin(selected_hashes)
        ].copy()
        fallback = deterministic_order(fallback, config.random_seed, f"{profile_name}|fallback")
        fallback = fallback.head(missing).copy()
        fallback["profile_name"] = profile_name
        fallback["stratum_name"] = "fallback_from_underfilled_strata"
        fallback["stratum_order"] = len(ranges)
        fallback["stratum_sample_target"] = missing
        fallback["sampling_fill_mode"] = "fallback"
        selected = pd.concat([selected, fallback], ignore_index=True)

    if len(selected) != sample_size:
        raise RuntimeError(
            f"Long-body profile could select only {len(selected)}/{sample_size} bodies."
        )
    if selected["function_body_sha256"].duplicated().any():
        raise RuntimeError("Long-body profile contains duplicate body hashes.")
    return selected, support


def derive_treatment_period(row: pd.Series) -> str:
    if str(row.get("dataset_source", "")) == "control":
        return "control"
    value = pd.to_numeric(pd.Series([row.get("time_to_event")]), errors="coerce").iloc[0]
    if pd.isna(value):
        return "unknown"
    if value < 0:
        return "pre"
    if value == 0:
        return "event"
    return "post"


def enrich_manifest_context(
    manifest: pd.DataFrame,
    events: pd.DataFrame,
    panel: pd.DataFrame,
) -> pd.DataFrame:
    hashes = set(manifest["function_body_sha256"].astype(str))
    prepared = events.loc[
        events["body_extraction_status"].astype(str).eq("prepared")
        & parse_bool_series(events["input_preparation_complete"])
        & events["function_body_sha256"].astype(str).isin(hashes)
    ].copy()
    prepared["time"] = prepared["time"].astype(str)
    panel_small = panel[["dataset_source", "repo_name", "time", "time_to_event"]].copy()
    panel_small["time"] = panel_small["time"].astype(str)
    prepared = prepared.merge(
        panel_small,
        on=["dataset_source", "repo_name", "time"],
        how="left",
        validate="many_to_one",
    )
    prepared["treatment_period"] = prepared.apply(derive_treatment_period, axis=1)

    rows: list[dict[str, Any]] = []
    for body_sha, group in prepared.groupby("function_body_sha256", sort=False):
        periods = group["treatment_period"].value_counts()
        sources = group["dataset_source"].value_counts()
        rows.append(
            {
                "function_body_sha256": str(body_sha),
                "context_reference_events": int(len(group)),
                "context_treatment_events": int(sources.get("treatment", 0)),
                "context_control_events": int(sources.get("control", 0)),
                "context_pre_events": int(periods.get("pre", 0)),
                "context_event_month_events": int(periods.get("event", 0)),
                "context_post_events": int(periods.get("post", 0)),
                "context_unknown_period_events": int(periods.get("unknown", 0)),
                "context_unique_repositories": int(group["repo_name"].nunique()),
                "context_unique_repository_months": int(
                    group[["dataset_source", "repo_name", "time"]].drop_duplicates().shape[0]
                ),
            }
        )
    context = pd.DataFrame(rows)
    if context.empty:
        context = pd.DataFrame(columns=["function_body_sha256"])
    result = manifest.merge(context, on="function_body_sha256", how="left", validate="one_to_one")
    context_columns = [column for column in result.columns if column.startswith("context_")]
    for column in context_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
    return result


def prepare_manifest(
    unique_bodies: pd.DataFrame,
    events: pd.DataFrame,
    panel: pd.DataFrame,
    config: DetectorConfig,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    calibration_ranges = parse_ranges(args.calibration_bands)
    long_ranges = parse_ranges(args.long_window_strata, allow_open_max=True)

    calibration, calibration_support = select_calibration_profile(
        unique_bodies,
        config,
        args.calibration_profile_name,
        args.calibration_profile_size,
        calibration_ranges,
    )
    long_profile, long_support = select_long_profile(
        unique_bodies,
        config,
        args.long_profile_name,
        args.long_profile_size,
        long_ranges,
        minimum_body_tokens=max(maximum for _, maximum in calibration_ranges if maximum is not None),
    )
    overlap = set(calibration["function_body_sha256"]) & set(long_profile["function_body_sha256"])
    if overlap:
        raise RuntimeError(f"Pilot profiles overlap on {len(overlap)} body hashes.")

    manifest = pd.concat([calibration, long_profile], ignore_index=True)
    manifest = manifest.sort_values(
        ["profile_name", "stratum_order", "deterministic_sample_key", "function_body_sha256"],
        kind="mergesort",
    ).reset_index(drop=True)
    manifest["sample_rank"] = manifest.groupby("profile_name").cumcount() + 1
    manifest["n_expected_windows"] = manifest["n_128_token_windows"].astype(int)
    manifest["selected_for_pilot"] = 1
    manifest = enrich_manifest_context(manifest, events, panel)

    support = pd.DataFrame(calibration_support + long_support)
    return manifest, support


def verify_selected_artifacts(
    manifest: pd.DataFrame,
    base_dir: Path,
    window_size: int,
) -> pd.DataFrame:
    errors: list[dict[str, Any]] = []
    for row in manifest.itertuples(index=False):
        body_sha = str(row.function_body_sha256)
        relative = str(row.function_body_relative_path)
        path = base_dir / relative
        if not path.is_file():
            errors.append(
                {
                    "function_body_sha256": body_sha,
                    "function_body_relative_path": relative,
                    "error_type": "missing_body_artifact",
                    "observed": str(path),
                    "expected": "existing regular file",
                }
            )
            continue
        raw = path.read_bytes()
        observed_sha = sha256_bytes(raw)
        if observed_sha != body_sha:
            errors.append(
                {
                    "function_body_sha256": body_sha,
                    "function_body_relative_path": relative,
                    "error_type": "sha256_mismatch",
                    "observed": observed_sha,
                    "expected": body_sha,
                }
            )
        expected_bytes = int(row.function_body_utf8_byte_count)
        if len(raw) != expected_bytes:
            errors.append(
                {
                    "function_body_sha256": body_sha,
                    "function_body_relative_path": relative,
                    "error_type": "utf8_byte_count_mismatch",
                    "observed": len(raw),
                    "expected": expected_bytes,
                }
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            errors.append(
                {
                    "function_body_sha256": body_sha,
                    "function_body_relative_path": relative,
                    "error_type": "utf8_decode_error",
                    "observed": str(error),
                    "expected": "valid UTF-8",
                }
            )
            continue
        observed_tokens = len(text.split(" "))
        expected_tokens = int(row.function_body_split_space_token_count)
        if observed_tokens != expected_tokens:
            errors.append(
                {
                    "function_body_sha256": body_sha,
                    "function_body_relative_path": relative,
                    "error_type": "literal_space_token_count_mismatch",
                    "observed": observed_tokens,
                    "expected": expected_tokens,
                }
            )
        observed_windows = math.ceil(observed_tokens / window_size)
        expected_windows = int(row.n_expected_windows)
        if observed_windows != expected_windows:
            errors.append(
                {
                    "function_body_sha256": body_sha,
                    "function_body_relative_path": relative,
                    "error_type": "window_count_mismatch",
                    "observed": observed_windows,
                    "expected": expected_windows,
                }
            )
    return pd.DataFrame(errors, columns=ARTIFACT_ERROR_COLUMNS)


def chunk_literal_space(text: str, window_size: int) -> list[tuple[str, int, int, int]]:
    tokens = text.split(" ")
    chunks: list[tuple[str, int, int, int]] = []
    for start in range(0, len(tokens), window_size):
        selected = tokens[start : start + window_size]
        chunks.append((" ".join(selected), len(selected), start, start + len(selected)))
    return chunks


def derive_window_seed(global_seed: int, body_sha: str, chunk_index: int) -> int:
    digest = hashlib.sha256(f"{global_seed}|{body_sha}|{chunk_index}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big", signed=False)


def set_all_seeds(seed: int, torch_module: Any | None = None) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch_module is not None:
        torch_module.manual_seed(seed)
        if torch_module.cuda.is_available():
            torch_module.cuda.manual_seed_all(seed)


def aggregate_weighted(chunks: list[dict[str, Any]]) -> float:
    valid = [chunk for chunk in chunks if math.isfinite(float(chunk["window_npr"]))]
    if not valid:
        return float("nan")
    numerator = sum(float(chunk["window_npr"]) * int(chunk["chunk_token_count"]) for chunk in valid)
    denominator = sum(int(chunk["chunk_token_count"]) for chunk in valid)
    return float(numerator / denominator) if denominator else float("nan")


def sanitize_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def build_full_detector_args(
    detector_main: Any,
    config: DetectorConfig,
    args: argparse.Namespace,
) -> argparse.Namespace:
    injected = [
        "--base_model_name",
        config.scoring_model,
        "--n_perturbation_list",
        str(config.perturbations_per_window),
        "--perturb_type",
        config.perturbation_type,
        "--pct_words_masked",
        str(args.pct_words_masked),
        "--span_length",
        str(args.span_length),
        "--chunk_size",
        str(args.perturbation_chunk_size),
        "--n_perturbation_rounds",
        str(args.n_perturbation_rounds),
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


def load_runtime(config: DetectorConfig, args: argparse.Namespace) -> RuntimeBundle:
    import scipy
    import torch
    import transformers
    from loguru import logger

    import main as detector_main
    from baselines.rank import get_rank, get_ranks
    from baselines.utils.loadmodel import load_base_model_and_tokenizer
    from baselines.utils.preprocessing import preprocess_and_save

    if args.quiet_internal_progress:
        detector_main.tqdm = lambda iterable, **_: iterable
        logger.remove()
        logger.add(sys.stderr, level=args.detector_log_level)

    detector_args = build_full_detector_args(detector_main, config, args)
    set_all_seeds(config.random_seed, torch)

    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA scoring was requested, but torch.cuda.is_available() is false. "
            "Use the detectcodegpt environment and a visible GPU."
        )

    cache_dir, _, _ = preprocess_and_save(detector_args)
    model_config: dict[str, Any] = {"cache_dir": cache_dir}
    started = time.perf_counter()
    model_config = load_base_model_and_tokenizer(detector_args, model_config)
    model_load_seconds = time.perf_counter() - started
    model = model_config["base_model"]
    model.eval()

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
        transformers=transformers,
        scipy=scipy,
        model_load_seconds=model_load_seconds,
        gpu_name=gpu_name,
        gpu_total_memory_bytes=gpu_total_memory_bytes,
    )


class AllWindowsInvalidNprError(RuntimeError):
    """Raised when every window in a body has a non-finite window_npr, so no
    finite function_npr can be computed at all. Recorded as a genuine body
    scoring failure (error_type == this class name in failures.csv)."""


class NonTailWindowInvalidNprError(RuntimeError):
    """Raised when an invalid window is not a true incomplete final tail.

    This includes any non-final window and a final window whose token count
    equals the configured window size. A full-size final window is not a
    tail merely because it is last in the sequence.
    """


class DisallowedTailWindowInvalidNprError(RuntimeError):
    """Raised when a true incomplete final tail is invalid for a reason other
    than zero_original_log_rank.

    The pilot allows only the known zero-denominator tail edge case as a
    partial-body success. Missing perturbation ranks, non-finite original
    ranks, non-finite perturbed means, and unknown invalid states remain
    body-level scoring failures.
    """


def classify_window_validity(scored: dict[str, Any]) -> tuple[bool, str | None]:
    """Determine whether a single window's score is usable, and if not, why.

    Problem this addresses
    -----------------------
    score_window_real() can produce a non-finite window_npr for more than
    one underlying reason (a zero-token-effective original rank, a fully
    non-finite perturbation batch, etc.). Recording only `window_npr: null`
    told us THAT a window failed but not WHY, which made it impossible to
    tell a genuine model-scoring problem apart from the known, comparatively
    benign near-empty-tail-window edge case, either by eye or with an
    automated QC check.

    Returns
    -------
    (True, None) if window_npr is finite.
    (False, reason) otherwise, where `reason` is one of:
        - "no_valid_perturbation_scores": none of the perturbed variants
          produced a finite rank, so mean_perturbed_log_rank could not be
          computed at all.
        - "nonfinite_mean_perturbed_log_rank": defensive catch-all for a
          non-finite mean despite some perturbations reporting as valid.
        - "nonfinite_original_log_rank": the original window's own log-rank
          was not finite (should not normally happen; get_rank() is
          expected to always return a real number, but this is checked
          explicitly rather than assumed).
        - "zero_original_log_rank": the most common cause in practice --
          the model ranked every token in the window #1 (e.g. a 1-2 token
          near-empty tail window), so log(rank) == 0 for every token and
          the window_npr ratio's denominator is exactly zero.
        - "unknown_invalid_window": window_npr is non-finite for a reason
          not covered by the checks above; kept as an explicit fallback so
          a future change to score_window_real() cannot silently produce an
          invalid window with no recorded reason.
    """
    window_npr = float(scored.get("window_npr", float("nan")))
    if math.isfinite(window_npr):
        return True, None

    valid_perturbation_scores = int(scored.get("valid_perturbation_scores", 0))
    mean_perturbed = float(scored.get("mean_perturbed_log_rank", float("nan")))
    original_log_rank = float(scored.get("original_log_rank", float("nan")))

    if valid_perturbation_scores == 0:
        return False, "no_valid_perturbation_scores"
    if not math.isfinite(mean_perturbed):
        return False, "nonfinite_mean_perturbed_log_rank"
    if not math.isfinite(original_log_rank):
        return False, "nonfinite_original_log_rank"
    if original_log_rank == 0.0:
        return False, "zero_original_log_rank"
    return False, "unknown_invalid_window"


def sanitize_window_for_json(scored: dict[str, Any]) -> dict[str, Any]:
    """Replace non-finite float fields with None (JSON null) so a window's
    raw diagnostic values can be embedded in a body result without breaking
    atomic_json(..., allow_nan=False). See classify_window_validity() for
    why a window can be non-finite, and score_one_body() for why this must
    only run *after* aggregate_weighted() has already consumed the raw
    (pre-sanitization) values.
    """
    sanitized = dict(scored)
    for key in ("original_log_rank", "mean_perturbed_log_rank", "window_npr"):
        if key in sanitized:
            sanitized[key] = sanitize_float(sanitized[key])
    return sanitized


def score_window_real(
    text: str,
    seed: int,
    config: DetectorConfig,
    runtime: RuntimeBundle,
) -> dict[str, Any]:
    set_all_seeds(seed, runtime.torch)
    started = time.perf_counter()
    original_log_rank = runtime.get_rank(text, runtime.args, runtime.model_config, log=True)
    perturbed = runtime.detector_main.perturb_texts(
        [text for _ in range(config.perturbations_per_window)],
        runtime.args,
        runtime.model_config,
    )
    perturbed_ranks = runtime.get_ranks(perturbed, runtime.args, runtime.model_config, log=True)
    valid = [float(value) for value in perturbed_ranks if math.isfinite(float(value))]
    mean_perturbed = float(np.mean(valid)) if valid else float("nan")
    # original_log_rank can be exactly 0.0 for a very short or highly
    # predictable window (every token ranked #1 by the model), most often
    # seen in a near-empty tail window left over just past a window_size
    # boundary. Division by zero is deliberately guarded here and produces
    # NaN rather than raising -- classify_window_validity() records why,
    # and sanitize_window_for_json() converts it to a JSON-safe null before
    # this window's raw dict is ever written to disk.
    npr = mean_perturbed / float(original_log_rank) if original_log_rank else float("nan")
    return {
        "original_log_rank": float(original_log_rank),
        "mean_perturbed_log_rank": mean_perturbed,
        "window_npr": float(npr),
        "expected_perturbations": int(config.perturbations_per_window),
        "valid_perturbation_scores": int(len(valid)),
        "scoring_seconds": float(time.perf_counter() - started),
    }


def score_window_mock(
    text: str,
    seed: int,
    config: DetectorConfig,
    runtime: RuntimeBundle | None,
) -> dict[str, Any]:
    del text, runtime
    original = 1.2 + ((seed >> 8) % 1000) / 10000.0
    ratio = 1.0 + (seed % 800) / 1000.0
    mean_perturbed = original * ratio
    return {
        "original_log_rank": float(original),
        "mean_perturbed_log_rank": float(mean_perturbed),
        "window_npr": float(ratio),
        "expected_perturbations": int(config.perturbations_per_window),
        "valid_perturbation_scores": int(config.perturbations_per_window),
        "scoring_seconds": 0.001,
    }


def score_one_body(
    row: pd.Series,
    text: str,
    config: DetectorConfig,
    fingerprint: str,
    score_window: Callable[[str, int, DetectorConfig, RuntimeBundle | None], dict[str, Any]],
    runtime: RuntimeBundle | None,
) -> dict[str, Any]:
    """Score every window of one implementation body and combine them into a
    single function-level result.

    Partial-body scoring policy
    ----------------------------
    A window's window_npr can be non-finite (see classify_window_validity()
    for the possible reasons). aggregate_weighted() always excludes
    non-finite windows from the token-weighted function_npr computation, so
    a body with at least one finite window can still receive a valid,
    finite function_npr. Whether that is treated as an acceptable partial
    result depends on WHICH window was invalid:

    - Partial success is allowed only when the sole invalid window is the
      final window, that final window contains fewer than window_size tokens,
      and its invalid reason is exactly zero_original_log_rank. This is the
      known zero-denominator edge case for a very short tail window.
    - A non-final invalid window, a full-size final invalid window, an
      incomplete tail invalid for any other reason, or a body whose every
      window is invalid is treated as a body scoring failure. See
      NonTailWindowInvalidNprError, DisallowedTailWindowInvalidNprError, and
      AllWindowsInvalidNprError.
    """
    body_sha = str(row["function_body_sha256"])
    started = time.perf_counter()
    chunks_out: list[dict[str, Any]] = []
    for chunk_index, (chunk_text, n_tokens, start, end) in enumerate(
        chunk_literal_space(text, config.window_size)
    ):
        seed = derive_window_seed(config.random_seed, body_sha, chunk_index)
        scored = score_window(chunk_text, seed, config, runtime)
        window_npr_valid, window_npr_invalid_reason = classify_window_validity(scored)
        chunks_out.append(
            {
                "chunk_index": int(chunk_index),
                "start_token_body": int(start),
                "end_token_body": int(end),
                "chunk_token_count": int(n_tokens),
                "window_seed": int(seed),
                **scored,
                "window_npr_valid": bool(window_npr_valid),
                "window_npr_invalid_reason": window_npr_invalid_reason,
            }
        )

    last_chunk_index = len(chunks_out) - 1
    for chunk in chunks_out:
        chunk["is_last_window"] = bool(chunk["chunk_index"] == last_chunk_index)
        chunk["is_incomplete_tail_window"] = bool(
            chunk["is_last_window"]
            and int(chunk["chunk_token_count"]) < int(config.window_size)
        )

    invalid_chunks = [chunk for chunk in chunks_out if not chunk["window_npr_valid"]]
    invalid_non_incomplete_tail_chunks = [
        chunk for chunk in invalid_chunks if not chunk["is_incomplete_tail_window"]
    ]
    invalid_tail_reason_chunks = [
        chunk
        for chunk in invalid_chunks
        if chunk["is_incomplete_tail_window"]
        and chunk["window_npr_invalid_reason"] != "zero_original_log_rank"
    ]

    # aggregate_weighted() must see the raw (pre-sanitization) window_npr
    # values -- still real Python NaN at this point, not yet sanitized to
    # None -- so its own math.isfinite() filter decides which windows
    # contribute to the body's function_npr. Sanitization for JSON embedding
    # happens further below, strictly after this call.
    function_npr = aggregate_weighted(chunks_out)

    if invalid_chunks and len(invalid_chunks) == len(chunks_out):
        raise AllWindowsInvalidNprError(
            f"All {len(chunks_out)} window(s) have a non-finite window_npr; "
            "no valid function-level NPR can be computed."
        )
    if invalid_non_incomplete_tail_chunks:
        offending = ", ".join(
            (
                f"chunk_index={chunk['chunk_index']} "
                f"chunk_token_count={chunk['chunk_token_count']} "
                f"reason={chunk['window_npr_invalid_reason']}"
            )
            for chunk in invalid_non_incomplete_tail_chunks
        )
        raise NonTailWindowInvalidNprError(
            f"{len(invalid_non_incomplete_tail_chunks)} invalid window(s) are "
            f"not true incomplete final tails ({offending}); treated as a "
            "scoring failure rather than a partial-body success."
        )
    if invalid_tail_reason_chunks:
        offending = ", ".join(
            (
                f"chunk_index={chunk['chunk_index']} "
                f"chunk_token_count={chunk['chunk_token_count']} "
                f"reason={chunk['window_npr_invalid_reason']}"
            )
            for chunk in invalid_tail_reason_chunks
        )
        raise DisallowedTailWindowInvalidNprError(
            f"{len(invalid_tail_reason_chunks)} incomplete tail window(s) are "
            f"invalid for a disallowed reason ({offending}); only "
            "zero_original_log_rank is accepted as a partial-body success."
        )
    if len(invalid_chunks) > 1:
        raise RuntimeError(
            "More than one invalid window remained after partial-body policy "
            "checks; only one incomplete final tail can be accepted."
        )
    if not math.isfinite(function_npr):
        # Defensive: should be unreachable given the two checks above, but
        # kept so an aggregation bug fails loudly instead of silently
        # caching a non-finite function-level score.
        raise RuntimeError("Function NPR is not finite despite passing window validity checks.")

    agc_like = int(function_npr > config.agc_threshold)

    n_attempted_windows = len(chunks_out)
    n_invalid_npr_windows = len(invalid_chunks)
    n_valid_npr_windows = n_attempted_windows - n_invalid_npr_windows
    valid_npr_token_count = sum(
        int(chunk["chunk_token_count"]) for chunk in chunks_out if chunk["window_npr_valid"]
    )
    invalid_npr_token_count = sum(
        int(chunk["chunk_token_count"]) for chunk in chunks_out if not chunk["window_npr_valid"]
    )
    partial_body_score = int(
        n_invalid_npr_windows == 1
        and invalid_chunks[0]["is_incomplete_tail_window"]
        and invalid_chunks[0]["window_npr_invalid_reason"] == "zero_original_log_rank"
    ) if invalid_chunks else 0

    # Sanitize NaN-prone per-window fields (e.g. window_npr of a degenerate
    # tail window) to None/JSON-null *after* aggregation and the validity
    # checks above, so the body-level result -- which already has a valid,
    # finite function_npr -- can be written with atomic_json(...,
    # allow_nan=False) without the whole body being discarded.
    sanitized_chunks_out = [sanitize_window_for_json(chunk) for chunk in chunks_out]

    return {
        "status": "success",
        "script_version": SCRIPT_VERSION,
        "config_fingerprint": fingerprint,
        "profile_name": str(row["profile_name"]),
        "stratum_name": str(row["stratum_name"]),
        "sample_rank": int(row["sample_rank"]),
        "function_body_sha256": body_sha,
        "function_body_relative_path": str(row["function_body_relative_path"]),
        "function_body_split_space_token_count": int(
            row["function_body_split_space_token_count"]
        ),
        "n_expected_windows": int(row["n_expected_windows"]),
        "n_scored_windows": int(len(chunks_out)),
        "n_attempted_windows": int(n_attempted_windows),
        "n_valid_npr_windows": int(n_valid_npr_windows),
        "n_invalid_npr_windows": int(n_invalid_npr_windows),
        "valid_npr_token_count": int(valid_npr_token_count),
        "invalid_npr_token_count": int(invalid_npr_token_count),
        "partial_body_score": int(partial_body_score),
        "referencing_function_event_count": int(row["referencing_function_event_count"]),
        "function_npr": float(function_npr),
        "agc_threshold": float(config.agc_threshold),
        "agc_like": agc_like,
        "hwc_like": 1 - agc_like,
        "scoring_seconds": float(time.perf_counter() - started),
        "created_at_utc": utc_now(),
        "chunks": sanitized_chunks_out,
    }


def result_cache_path(cache_dir: Path, body_sha: str) -> Path:
    return cache_dir / "body_results" / body_sha[:2] / f"{body_sha}.json"


def failure_cache_path(cache_dir: Path, body_sha: str) -> Path:
    return cache_dir / "failures" / body_sha[:2] / f"{body_sha}.json"


def load_valid_cached_result(path: Path, body_sha: str, fingerprint: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as stream:
            result = json.load(stream)
    except Exception:
        return None
    if result.get("status") != "success":
        return None
    if result.get("function_body_sha256") != body_sha:
        return None
    if result.get("config_fingerprint") != fingerprint:
        return None
    return result


def score_pending_bodies(
    manifest: pd.DataFrame,
    paths: Paths,
    config: DetectorConfig,
    fingerprint: str,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], RuntimeBundle | None, float]:
    completed: list[dict[str, Any]] = []
    pending_rows: list[pd.Series] = []
    for _, row in manifest.iterrows():
        body_sha = str(row["function_body_sha256"])
        cached = load_valid_cached_result(result_cache_path(paths.cache_dir, body_sha), body_sha, fingerprint)
        if cached is not None:
            completed.append(cached)
        else:
            pending_rows.append(row)

    if args.require_all_completed and pending_rows:
        raise RuntimeError(
            f"Resume validation requires all bodies to be complete, but {len(pending_rows)} are pending."
        )
    if args.prepare_only:
        return completed, [], None, 0.0
    if not pending_rows:
        return completed, [], None, 0.0

    runtime: RuntimeBundle | None = None
    score_window: Callable[[str, int, DetectorConfig, RuntimeBundle | None], dict[str, Any]]
    if args.mock_scoring:
        score_window = score_window_mock
    else:
        runtime = load_runtime(config, args)
        score_window = score_window_real

    failures: list[dict[str, Any]] = []
    scoring_started = time.perf_counter()
    total_pending = len(pending_rows)
    for offset, row in enumerate(pending_rows, start=1):
        body_sha = str(row["function_body_sha256"])
        relative = str(row["function_body_relative_path"])
        try:
            text = (paths.body_artifact_base / relative).read_text(encoding="utf-8")
            result = score_one_body(row, text, config, fingerprint, score_window, runtime)
            destination = result_cache_path(paths.cache_dir, body_sha)
            atomic_json(result, destination)
            destination_bytes = destination.stat().st_size
            result["cache_result_bytes"] = int(destination_bytes)
            atomic_json(result, destination)
            completed.append(result)
            failure_path = failure_cache_path(paths.cache_dir, body_sha)
            if failure_path.exists():
                failure_path.unlink()
        except Exception as error:  # Continue to produce a complete failure audit.
            failure = {
                "profile_name": str(row["profile_name"]),
                "stratum_name": str(row["stratum_name"]),
                "sample_rank": int(row["sample_rank"]),
                "function_body_sha256": body_sha,
                "stage": "score_body",
                "error_type": type(error).__name__,
                "error_message": str(error),
                "created_at_utc": utc_now(),
                "config_fingerprint": fingerprint,
            }
            atomic_json(failure, failure_cache_path(paths.cache_dir, body_sha))
            failures.append(failure)
        if offset == 1 or offset % args.progress_every_bodies == 0 or offset == total_pending:
            print(
                f"Progress: {offset}/{total_pending} pending bodies processed; "
                f"success_total={len(completed)}, failures_this_run={len(failures)}"
            )

    return completed, failures, runtime, float(time.perf_counter() - scoring_started)


def flatten_results(
    manifest: pd.DataFrame,
    paths: Paths,
    fingerprint: str,
    pending_is_failure: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    manifest_by_sha = manifest.set_index("function_body_sha256", drop=False)
    body_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []

    for body_sha in manifest["function_body_sha256"].astype(str):
        body_path = result_cache_path(paths.cache_dir, body_sha)
        result = load_valid_cached_result(body_path, body_sha, fingerprint)
        manifest_row = manifest_by_sha.loc[body_sha]
        if result is None:
            failure_path = failure_cache_path(paths.cache_dir, body_sha)
            if failure_path.is_file():
                with failure_path.open("r", encoding="utf-8") as stream:
                    failure = json.load(stream)
                failure_rows.append({column: failure.get(column, "") for column in FAILURE_COLUMNS})
                checkpoint_status = "failure"
            else:
                if pending_is_failure:
                    failure_rows.append(
                        {
                            "profile_name": manifest_row["profile_name"],
                            "stratum_name": manifest_row["stratum_name"],
                            "sample_rank": manifest_row["sample_rank"],
                            "function_body_sha256": body_sha,
                            "stage": "checkpoint",
                            "error_type": "MissingResult",
                            "error_message": "No valid success or failure cache artifact exists.",
                        }
                    )
                    checkpoint_status = "missing"
                else:
                    checkpoint_status = "pending"
            checkpoint_rows.append(
                {
                    "function_body_sha256": body_sha,
                    "profile_name": manifest_row["profile_name"],
                    "sample_rank": int(manifest_row["sample_rank"]),
                    "checkpoint_status": checkpoint_status,
                    "checkpoint_path": str(body_path),
                    "checkpoint_bytes": 0,
                    "config_fingerprint": fingerprint,
                }
            )
            continue

        cache_bytes = body_path.stat().st_size
        result["cache_result_bytes"] = int(cache_bytes)
        body_rows.append({column: result.get(column, "") for column in BODY_SCORE_COLUMNS})
        for chunk in result["chunks"]:
            window_rows.append(
                {
                    "profile_name": result["profile_name"],
                    "stratum_name": result["stratum_name"],
                    "sample_rank": result["sample_rank"],
                    "function_body_sha256": body_sha,
                    **{column: chunk.get(column, "") for column in WINDOW_SCORE_COLUMNS if column in chunk},
                }
            )
        checkpoint_rows.append(
            {
                "function_body_sha256": body_sha,
                "profile_name": result["profile_name"],
                "sample_rank": int(result["sample_rank"]),
                "checkpoint_status": "success",
                "checkpoint_path": str(body_path),
                "checkpoint_bytes": int(cache_bytes),
                "config_fingerprint": fingerprint,
            }
        )

    body_scores = pd.DataFrame(body_rows, columns=BODY_SCORE_COLUMNS)
    window_scores = pd.DataFrame(window_rows, columns=WINDOW_SCORE_COLUMNS)
    failures = pd.DataFrame(failure_rows, columns=FAILURE_COLUMNS)
    checkpoints = pd.DataFrame(checkpoint_rows)
    if not body_scores.empty:
        body_scores = body_scores.sort_values(["profile_name", "sample_rank"])
    if not window_scores.empty:
        window_scores = window_scores.sort_values(
            ["profile_name", "sample_rank", "chunk_index"]
        )
    return body_scores, window_scores, failures, checkpoints


def nullable_float_matches(left: Any, right: Any, tolerance: float) -> bool:
    """Compare two window-score fields that may legitimately be None (after
    sanitize_window_for_json()) while still comparing finite values with the
    usual numeric tolerance.

    Problem this fixes
    -------------------
    Before this helper, compare_results() called float(left[key]) directly.
    Once score_one_body() started sanitizing a degenerate window's
    window_npr/original_log_rank/mean_perturbed_log_rank to None (so the
    body-level JSON write would succeed -- see sanitize_window_for_json()),
    any reproducibility-check re-scoring of a partial-body result would hit
    `float(None)` and raise:
        TypeError: float() argument must be a string or a real number, not
        'NoneType'
    This meant the JSON-write bug was fixed, but a body with a partial
    (tail-window-only) failure could still crash run-1c the moment it was
    selected for the reproducibility sample, rather than at cache-write time.

    Comparison semantics
    ---------------------
    - Both None: treated as equal (both runs agree the window is
      unscoreable -- same seed, same input, so this should be
      deterministic).
    - Exactly one None: treated as a mismatch. A reproducibility run that
      disagrees about *whether* a window is scoreable at all is a more
      serious inconsistency than a small numeric difference and must not be
      silently ignored.
    - Both finite: compared with the existing absolute-difference tolerance.
    """
    left_value = sanitize_float(left)
    right_value = sanitize_float(right)
    if left_value is None or right_value is None:
        return left_value is None and right_value is None
    return abs(left_value - right_value) <= tolerance


def compare_results(original: dict[str, Any], rerun: dict[str, Any], tolerance: float) -> dict[str, Any]:
    original_npr = float(original["function_npr"])
    rerun_npr = float(rerun["function_npr"])
    chunks_a = original["chunks"]
    chunks_b = rerun["chunks"]
    count_match = len(chunks_a) == len(chunks_b)
    score_match = count_match
    if count_match:
        for left, right in zip(chunks_a, chunks_b):
            for key in ("window_npr", "original_log_rank", "mean_perturbed_log_rank"):
                if not nullable_float_matches(left.get(key), right.get(key), tolerance):
                    score_match = False
                    break
            # A reproducibility run must also agree on *why* a window is
            # invalid, not just that it is. If the reason differs (e.g. one
            # run reports "zero_original_log_rank" and the other reports
            # "no_valid_perturbation_scores" for the same window), that is a
            # reproducibility mismatch even though window_npr is None on
            # both sides.
            if left.get("window_npr_valid") != right.get("window_npr_valid"):
                score_match = False
            if left.get("window_npr_invalid_reason") != right.get("window_npr_invalid_reason"):
                score_match = False
            if not score_match:
                break
    passed = abs(original_npr - rerun_npr) <= tolerance and count_match and score_match
    return {
        "original_function_npr": original_npr,
        "rerun_function_npr": rerun_npr,
        "absolute_difference": abs(original_npr - rerun_npr),
        "window_count_match": bool(count_match),
        "all_window_scores_match": bool(score_match),
        "passed": bool(passed),
    }


def run_reproducibility_checks(
    manifest: pd.DataFrame,
    paths: Paths,
    config: DetectorConfig,
    fingerprint: str,
    args: argparse.Namespace,
    runtime: RuntimeBundle | None,
) -> pd.DataFrame:
    output_path = paths.qc_dir / "commit_function_npr_reproducibility_checks.csv"
    if args.reproducibility_check_per_profile <= 0:
        frame = pd.DataFrame(columns=REPRO_COLUMNS)
        atomic_csv(frame, output_path, REPRO_COLUMNS)
        return frame
    if runtime is None and not args.mock_scoring:
        if output_path.is_file():
            return pd.read_csv(output_path)
        return pd.DataFrame(columns=REPRO_COLUMNS)

    score_window = score_window_mock if args.mock_scoring else score_window_real
    ordered_manifest = manifest.sort_values(["profile_name", "sample_rank"])
    selected = (
        ordered_manifest.groupby("profile_name", group_keys=False)
        .head(args.reproducibility_check_per_profile)
        .copy()
    )
    selected["selection_reason"] = "standard"

    extra_partial_rows: list[pd.Series] = []
    selected_hashes = set(selected["function_body_sha256"].astype(str))
    for profile_name, profile_group in ordered_manifest.groupby("profile_name", sort=False):
        for _, candidate in profile_group.iterrows():
            body_sha = str(candidate["function_body_sha256"])
            cached = load_valid_cached_result(
                result_cache_path(paths.cache_dir, body_sha), body_sha, fingerprint
            )
            if cached is None or int(cached.get("partial_body_score", 0)) != 1:
                continue
            if body_sha not in selected_hashes:
                candidate = candidate.copy()
                candidate["selection_reason"] = "partial_body"
                extra_partial_rows.append(candidate)
                selected_hashes.add(body_sha)
            break
    if extra_partial_rows:
        selected = pd.concat([selected, pd.DataFrame(extra_partial_rows)], ignore_index=True)

    rows: list[dict[str, Any]] = []
    for _, row in selected.iterrows():
        body_sha = str(row["function_body_sha256"])
        original = load_valid_cached_result(
            result_cache_path(paths.cache_dir, body_sha), body_sha, fingerprint
        )
        if original is None:
            continue
        text = (paths.body_artifact_base / str(row["function_body_relative_path"])).read_text(
            encoding="utf-8"
        )
        rerun = score_one_body(row, text, config, fingerprint, score_window, runtime)
        comparison = compare_results(original, rerun, args.reproducibility_tolerance)
        rows.append(
            {
                "profile_name": str(row["profile_name"]),
                "function_body_sha256": body_sha,
                "selection_reason": str(row.get("selection_reason", "standard")),
                **comparison,
            }
        )
    frame = pd.DataFrame(rows, columns=REPRO_COLUMNS)
    atomic_csv(frame, output_path, REPRO_COLUMNS)
    return frame


def build_profile_summary(
    manifest: pd.DataFrame,
    body_scores: pd.DataFrame,
    window_scores: pd.DataFrame,
    failures: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    profiles = list(manifest["profile_name"].drop_duplicates())
    for profile in [*profiles, "all_profiles"]:
        if profile == "all_profiles":
            manifest_group = manifest
            body_group = body_scores
            window_group = window_scores
            failure_group = failures
        else:
            manifest_group = manifest.loc[manifest["profile_name"] == profile]
            body_group = body_scores.loc[body_scores["profile_name"] == profile]
            window_group = window_scores.loc[window_scores["profile_name"] == profile]
            failure_group = failures.loc[failures["profile_name"] == profile]
        scoring_seconds = pd.to_numeric(window_group.get("scoring_seconds"), errors="coerce").sum()
        windows = int(len(window_group))
        cache_bytes = pd.to_numeric(body_group.get("cache_result_bytes"), errors="coerce").sum()
        successful_bodies = int(len(body_group))
        attempted_windows = int(pd.to_numeric(body_group.get("n_attempted_windows"), errors="coerce").fillna(0).sum())
        valid_npr_windows = int(pd.to_numeric(body_group.get("n_valid_npr_windows"), errors="coerce").fillna(0).sum())
        invalid_npr_windows = int(pd.to_numeric(body_group.get("n_invalid_npr_windows"), errors="coerce").fillna(0).sum())
        valid_npr_tokens = int(pd.to_numeric(body_group.get("valid_npr_token_count"), errors="coerce").fillna(0).sum())
        invalid_npr_tokens = int(pd.to_numeric(body_group.get("invalid_npr_token_count"), errors="coerce").fillna(0).sum())
        partial_body_scores = int(pd.to_numeric(body_group.get("partial_body_score"), errors="coerce").fillna(0).sum())
        total_npr_tokens = valid_npr_tokens + invalid_npr_tokens
        rows.append(
            {
                "profile_name": profile,
                "selected_unique_bodies": int(len(manifest_group)),
                "successful_unique_bodies": successful_bodies,
                "failed_unique_bodies": int(len(failure_group)),
                "expected_windows": int(manifest_group["n_expected_windows"].sum()),
                "scored_windows": windows,
                "attempted_windows": attempted_windows,
                "valid_npr_windows": valid_npr_windows,
                "invalid_npr_windows": invalid_npr_windows,
                "partial_body_scores": partial_body_scores,
                "valid_npr_tokens": valid_npr_tokens,
                "invalid_npr_tokens": invalid_npr_tokens,
                "invalid_npr_window_share": (
                    invalid_npr_windows / attempted_windows if attempted_windows else math.nan
                ),
                "invalid_npr_token_share": (
                    invalid_npr_tokens / total_npr_tokens if total_npr_tokens else math.nan
                ),
                "mean_windows_per_successful_body": (
                    windows / successful_bodies if successful_bodies else math.nan
                ),
                "median_windows_per_successful_body": (
                    float(pd.to_numeric(body_group["n_scored_windows"], errors="coerce").median())
                    if successful_bodies
                    else math.nan
                ),
                "window_scoring_seconds": float(scoring_seconds),
                "measured_windows_per_second": (
                    windows / scoring_seconds if scoring_seconds > 0 else math.nan
                ),
                "measured_scoring_sequences_per_second": (
                    windows * 51 / scoring_seconds if scoring_seconds > 0 else math.nan
                ),
                "measured_bodies_per_minute": (
                    successful_bodies * 60 / scoring_seconds if scoring_seconds > 0 else math.nan
                ),
                "cache_result_bytes": int(cache_bytes),
                "cache_bytes_per_window": cache_bytes / windows if windows else math.nan,
                "agc_like_bodies": int(pd.to_numeric(body_group.get("agc_like"), errors="coerce").sum()),
                "hwc_like_bodies": int(pd.to_numeric(body_group.get("hwc_like"), errors="coerce").sum()),
            }
        )
    return pd.DataFrame(rows)


def build_full_run_estimates(
    profile_summary: pd.DataFrame,
    support: pd.DataFrame,
    calibration_profile_name: str,
    long_profile_name: str,
) -> pd.DataFrame:
    summary = profile_summary.set_index("profile_name")
    cal_wps = sanitize_float(summary.loc[calibration_profile_name, "measured_windows_per_second"])
    long_wps = sanitize_float(summary.loc[long_profile_name, "measured_windows_per_second"])
    cal_bytes = sanitize_float(summary.loc[calibration_profile_name, "cache_bytes_per_window"])
    long_bytes = sanitize_float(summary.loc[long_profile_name, "cache_bytes_per_window"])
    support_index = support.set_index("spec_name")
    rows: list[dict[str, Any]] = []

    for spec_name in ("range100_200", "min100"):
        if spec_name not in support_index.index:
            continue
        total_windows = int(support_index.loc[spec_name, "total_windows"])
        if spec_name == "range100_200":
            calibration_windows = total_windows
            long_windows = 0
        else:
            range_windows = int(support_index.loc["range100_200", "total_windows"])
            calibration_windows = range_windows
            long_windows = max(0, total_windows - range_windows)
        seconds = 0.0
        estimated_cache_bytes = 0.0
        feasible = True
        if calibration_windows:
            if not cal_wps or cal_wps <= 0:
                feasible = False
            else:
                seconds += calibration_windows / cal_wps
            if cal_bytes:
                estimated_cache_bytes += calibration_windows * cal_bytes
        if long_windows:
            if not long_wps or long_wps <= 0:
                feasible = False
            else:
                seconds += long_windows / long_wps
            if long_bytes:
                estimated_cache_bytes += long_windows * long_bytes
        rows.append(
            {
                "spec_name": spec_name,
                "total_windows": total_windows,
                "calibration_range_windows": calibration_windows,
                "long_body_windows": long_windows,
                "calibration_profile_windows_per_second": cal_wps,
                "long_profile_windows_per_second": long_wps,
                "estimated_gpu_seconds": seconds if feasible else math.nan,
                "estimated_gpu_hours": seconds / 3600 if feasible else math.nan,
                "estimated_cache_bytes": estimated_cache_bytes,
                "estimated_cache_gib": estimated_cache_bytes / (1024**3),
                "estimation_method": "profile_specific_pilot_throughput",
            }
        )
    return pd.DataFrame(rows)


def check_row(name: str, passed: bool, observed: Any, expected: Any, note: str = "") -> dict[str, Any]:
    return {
        "check_name": name,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
        "note": note,
    }


def build_checks(
    config: DetectorConfig,
    manifest: pd.DataFrame,
    profile_support: pd.DataFrame,
    artifact_errors: pd.DataFrame,
    body_scores: pd.DataFrame,
    window_scores: pd.DataFrame,
    failures: pd.DataFrame,
    reproducibility: pd.DataFrame,
    args: argparse.Namespace,
) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []
    selected_expected = args.calibration_profile_size + args.long_profile_size
    checks.append(check_row("specification_is_frozen", config.specification_status == "frozen", config.specification_status, "frozen"))
    checks.append(check_row("scoring_model_is_starcoder2_7b", config.scoring_model == "bigcode/starcoder2-7b", config.scoring_model, "bigcode/starcoder2-7b"))
    checks.append(check_row("window_size_is_128", config.window_size == 128, config.window_size, 128))
    checks.append(check_row("perturbations_per_window_is_50", config.perturbations_per_window == 50, config.perturbations_per_window, 50))
    checks.append(check_row("agc_threshold_is_fixed", abs(config.agc_threshold - 1.5183) < 1e-12, config.agc_threshold, 1.5183))
    checks.append(check_row("selected_body_count", len(manifest) == selected_expected, len(manifest), selected_expected))
    checks.append(check_row("selected_body_hashes_unique", manifest["function_body_sha256"].is_unique, int(manifest["function_body_sha256"].duplicated().sum()), 0))
    reference_counts_match = pd.to_numeric(
        manifest["context_reference_events"], errors="coerce"
    ).eq(
        pd.to_numeric(manifest["referencing_function_event_count"], errors="coerce")
    )
    checks.append(
        check_row(
            "selected_body_event_reference_counts_match",
            bool(reference_counts_match.all()),
            int((~reference_counts_match).sum()),
            0,
            "Event-manifest references must reconcile with the unique-body manifest.",
        )
    )
    profile_counts = manifest["profile_name"].value_counts().to_dict()
    checks.append(check_row("calibration_profile_size", profile_counts.get(args.calibration_profile_name, 0) == args.calibration_profile_size, profile_counts.get(args.calibration_profile_name, 0), args.calibration_profile_size))
    checks.append(check_row("long_profile_size", profile_counts.get(args.long_profile_name, 0) == args.long_profile_size, profile_counts.get(args.long_profile_name, 0), args.long_profile_size))
    checks.append(check_row("calibration_strata_targets_met", bool(profile_support.loc[profile_support["profile_name"] == args.calibration_profile_name, "target_met"].all()), int((~profile_support.loc[profile_support["profile_name"] == args.calibration_profile_name, "target_met"].astype(bool)).sum()), 0))
    checks.append(check_row("selected_artifacts_valid", artifact_errors.empty, len(artifact_errors), 0))
    if not args.prepare_only:
        checks.append(check_row("successful_body_count", len(body_scores) == selected_expected, len(body_scores), selected_expected))
        checks.append(check_row("failed_body_count", failures.empty, len(failures), 0))
        expected_windows = int(manifest["n_expected_windows"].sum())
        checks.append(check_row("scored_window_count", len(window_scores) == expected_windows, len(window_scores), expected_windows))
        if not window_scores.empty:
            valid_perturbations = pd.to_numeric(window_scores["valid_perturbation_scores"], errors="coerce")
            checks.append(check_row("all_windows_have_50_valid_perturbations", bool(valid_perturbations.eq(config.perturbations_per_window).all()), int((~valid_perturbations.eq(config.perturbations_per_window)).sum()), 0))
        checks.append(check_row("agc_hwc_body_arithmetic", int(pd.to_numeric(body_scores.get("agc_like"), errors="coerce").sum() + pd.to_numeric(body_scores.get("hwc_like"), errors="coerce").sum()) == len(body_scores), int(pd.to_numeric(body_scores.get("agc_like"), errors="coerce").sum() + pd.to_numeric(body_scores.get("hwc_like"), errors="coerce").sum()), len(body_scores)))

        # --- Partial-body scoring policy checks -------------------------
        # These guard the reviewer-requested distinction between the known,
        # benign tail-window numerical edge case (partial success) and a
        # genuine model-scoring problem (body failure). See score_one_body()
        # and classify_window_validity() for the underlying policy.
        if not body_scores.empty:
            valid_windows = pd.to_numeric(body_scores.get("n_valid_npr_windows"), errors="coerce")
            checks.append(
                check_row(
                    "all_bodies_have_at_least_one_valid_npr_window",
                    bool(valid_windows.ge(1).all()),
                    int((valid_windows.lt(1)).sum()),
                    0,
                    "Every successful body must have at least one window with a finite window_npr.",
                )
            )
            function_npr_values = pd.to_numeric(body_scores.get("function_npr"), errors="coerce")
            checks.append(
                check_row(
                    "all_function_npr_values_are_finite",
                    bool(np.isfinite(function_npr_values.to_numpy(dtype=float)).all()) if len(function_npr_values) else True,
                    int((~np.isfinite(function_npr_values.to_numpy(dtype=float))).sum()) if len(function_npr_values) else 0,
                    0,
                    "A cached success result must never carry a non-finite function_npr.",
                )
            )
            partial_body_score_count = int(pd.to_numeric(body_scores.get("partial_body_score"), errors="coerce").fillna(0).sum())
            checks.append(
                check_row(
                    "partial_body_score_count_reported",
                    True,
                    partial_body_score_count,
                    None,
                    "Informational: number of successful bodies that excluded at least one invalid tail window from aggregation.",
                )
            )
        if not window_scores.empty:
            # A non-tail invalid window should never reach the final window
            # table for a *successful* body, since score_one_body() raises
            # NonTailWindowInvalidNprError before returning success in that
            # case. This check reads the output table directly as an
            # independent, defensive audit of that policy rather than
            # trusting the code path alone.
            is_invalid = ~window_scores["window_npr_valid"].astype(bool)
            is_incomplete_tail = window_scores["is_incomplete_tail_window"].astype(bool)
            invalid_non_incomplete_tail = window_scores.loc[is_invalid & ~is_incomplete_tail]
            checks.append(
                check_row(
                    "invalid_non_incomplete_tail_window_count_is_zero",
                    invalid_non_incomplete_tail.empty,
                    int(len(invalid_non_incomplete_tail)),
                    0,
                    "An invalid non-final or full-size final window must fail the body and must not appear in a successful body's window table.",
                )
            )
            invalid_tail_wrong_reason = window_scores.loc[
                is_invalid
                & is_incomplete_tail
                & ~window_scores["window_npr_invalid_reason"].astype(str).eq(
                    "zero_original_log_rank"
                )
            ]
            checks.append(
                check_row(
                    "invalid_incomplete_tail_reason_is_allowed",
                    invalid_tail_wrong_reason.empty,
                    int(len(invalid_tail_wrong_reason)),
                    0,
                    "Only zero_original_log_rank is permitted for an invalid incomplete final tail in a successful body.",
                )
            )
            # Every null (invalid) window_npr must carry an explicit reason,
            # so "null" alone never has to be interpreted as "unexplained".
            invalid_rows = window_scores.loc[is_invalid]
            missing_reason = invalid_rows["window_npr_invalid_reason"].isna() | invalid_rows["window_npr_invalid_reason"].astype(str).eq("")
            checks.append(
                check_row(
                    "null_window_npr_values_have_reason",
                    bool((~missing_reason).all()) if len(invalid_rows) else True,
                    int(missing_reason.sum()),
                    0,
                    "Every window with window_npr_valid == False must record window_npr_invalid_reason.",
                )
            )
        if args.reproducibility_check_per_profile > 0:
            expected_repro_minimum = (
                len(manifest["profile_name"].unique())
                * args.reproducibility_check_per_profile
            )
            checks.append(
                check_row(
                    "reproducibility_check_minimum_count",
                    len(reproducibility) >= expected_repro_minimum,
                    len(reproducibility),
                    f">={expected_repro_minimum}",
                    "Additional partial-body cases are included when present.",
                )
            )
            checks.append(check_row("same_seed_reproducibility", bool(reproducibility["passed"].astype(bool).all()) if len(reproducibility) else False, int((~reproducibility["passed"].astype(bool)).sum()) if len(reproducibility) else expected_repro_minimum, 0))
            if len(reproducibility) and not body_scores.empty:
                passed_is_boolean = reproducibility["passed"].notna()
                checks.append(
                    check_row(
                        "reproducibility_comparisons_completed",
                        bool(passed_is_boolean.all()),
                        int((~passed_is_boolean).sum()),
                        0,
                        "Every selected reproducibility case must produce a boolean result.",
                    )
                )
                partial_by_profile = set(
                    body_scores.loc[
                        pd.to_numeric(body_scores["partial_body_score"], errors="coerce").eq(1),
                        "profile_name",
                    ].astype(str)
                )
                reproducibility_with_partial = reproducibility.merge(
                    body_scores[["function_body_sha256", "partial_body_score"]],
                    on="function_body_sha256",
                    how="left",
                )
                partial_repro_profiles = set(
                    reproducibility_with_partial.loc[
                        pd.to_numeric(
                            reproducibility_with_partial["partial_body_score"],
                            errors="coerce",
                        ).eq(1),
                        "profile_name",
                    ].astype(str)
                )
                missing_partial_profiles = sorted(partial_by_profile - partial_repro_profiles)
                checks.append(
                    check_row(
                        "partial_body_reproducibility_coverage",
                        not missing_partial_profiles,
                        ",".join(missing_partial_profiles),
                        "none",
                        "Each profile containing a partial-body success must contribute one partial-body reproducibility case unless it was already selected as a standard case.",
                    )
                )
    return pd.DataFrame(checks, columns=CHECK_COLUMNS)


def package_metadata(runtime: RuntimeBundle | None) -> dict[str, Any]:
    if runtime is None:
        return {
            "model_loaded": False,
            "python_version": sys.version.split()[0],
            "numpy_version": np.__version__,
            "pandas_version": pd.__version__,
        }
    torch = runtime.torch
    peak_allocated = int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0
    peak_reserved = int(torch.cuda.max_memory_reserved()) if torch.cuda.is_available() else 0
    return {
        "model_loaded": True,
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "torch_version": torch.__version__,
        "transformers_version": runtime.transformers.__version__,
        "scipy_version": runtime.scipy.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_version": torch.version.cuda,
        "gpu_name": runtime.gpu_name,
        "gpu_total_memory_bytes": runtime.gpu_total_memory_bytes,
        "peak_gpu_memory_allocated_bytes": peak_allocated,
        "peak_gpu_memory_reserved_bytes": peak_reserved,
        "model_load_seconds": runtime.model_load_seconds,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }


def write_outputs(
    paths: Paths,
    manifest: pd.DataFrame,
    profile_support: pd.DataFrame,
    artifact_errors: pd.DataFrame,
    body_scores: pd.DataFrame,
    window_scores: pd.DataFrame,
    failures: pd.DataFrame,
    checkpoints: pd.DataFrame,
    profile_summary: pd.DataFrame,
    estimates: pd.DataFrame,
    reproducibility: pd.DataFrame,
    checks: pd.DataFrame,
    summary: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    atomic_csv(manifest, paths.output_dir / "commit_function_npr_pilot_manifest.csv")
    atomic_csv(profile_support, paths.output_dir / "commit_function_npr_pilot_profile_support.csv")
    atomic_csv(body_scores, paths.output_dir / "commit_function_npr_body_scores.csv", BODY_SCORE_COLUMNS)
    atomic_csv(window_scores, paths.output_dir / "commit_function_npr_window_scores.csv", WINDOW_SCORE_COLUMNS)
    atomic_csv(failures, paths.output_dir / "commit_function_npr_failures.csv", FAILURE_COLUMNS)
    atomic_csv(checkpoints, paths.output_dir / "commit_function_npr_checkpoint_index.csv")
    atomic_csv(profile_summary, paths.output_dir / "commit_function_npr_runtime_metrics.csv")
    atomic_csv(estimates, paths.output_dir / "commit_function_npr_full_run_estimates.csv")
    atomic_csv(artifact_errors, paths.qc_dir / "commit_function_npr_artifact_errors.csv", ARTIFACT_ERROR_COLUMNS)
    atomic_csv(reproducibility, paths.qc_dir / "commit_function_npr_reproducibility_checks.csv", REPRO_COLUMNS)
    atomic_csv(checks, paths.qc_dir / "commit_function_npr_checks.csv", CHECK_COLUMNS)
    atomic_json(summary, paths.qc_dir / "commit_function_npr_summary.json")
    atomic_json(metadata, paths.qc_dir / "commit_function_npr_metadata.json")


def run_analysis(args: argparse.Namespace) -> int:
    invocation_started = time.perf_counter()
    invocation_started_utc = utc_now()
    paths = Paths(
        input_unique_bodies=args.input_unique_bodies,
        input_events=args.input_events,
        input_panel=args.input_panel,
        input_support=args.input_support,
        input_specification=args.input_specification,
        body_artifact_base=args.body_artifact_base,
        output_dir=args.output_dir,
        qc_dir=args.qc_dir or args.output_dir / "qc",
        cache_dir=args.cache_dir or args.output_dir / "cache",
    )

    if args.overwrite_output and paths.output_dir.exists():
        shutil.rmtree(paths.output_dir)
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.qc_dir.mkdir(parents=True, exist_ok=True)
    paths.cache_dir.mkdir(parents=True, exist_ok=True)

    config = load_detector_config(paths.input_specification)
    calibration_spec = find_spec(config, args.calibration_spec_name)
    long_spec = find_spec(config, args.long_spec_name)
    if int(calibration_spec["minimum_literal_space_tokens"]) != 100 or int(calibration_spec["maximum_literal_space_tokens"]) != 200:
        raise ValueError("range100_200 specification does not match 100-200 tokens.")
    if int(long_spec["minimum_literal_space_tokens"]) != 100 or long_spec.get("maximum_literal_space_tokens") is not None:
        raise ValueError("min100 specification does not match an open-ended minimum of 100 tokens.")

    unique_bodies = pd.read_csv(paths.input_unique_bodies, low_memory=False)
    events = pd.read_csv(paths.input_events, low_memory=False)
    panel = pd.read_csv(paths.input_panel, low_memory=False)
    support = pd.read_csv(paths.input_support, low_memory=False)
    require_columns(unique_bodies, UNIQUE_BODY_REQUIRED, "Unique-body manifest")
    require_columns(events, EVENT_REQUIRED, "Event manifest")
    require_columns(panel, PANEL_REQUIRED, "Matched panel")
    require_columns(support, SUPPORT_REQUIRED, "run-1b support")

    numeric_body_columns = [
        "function_body_character_count",
        "function_body_utf8_byte_count",
        "function_body_line_count",
        "function_body_split_space_token_count",
        "function_body_nonempty_whitespace_token_count",
        "n_128_token_windows",
        "tail_window_token_count",
        "referencing_function_event_count",
    ]
    for column in numeric_body_columns:
        unique_bodies[column] = pd.to_numeric(unique_bodies[column], errors="raise").astype(int)
    unique_bodies["function_body_sha256"] = unique_bodies["function_body_sha256"].astype(str)
    if not unique_bodies["function_body_sha256"].is_unique:
        raise ValueError("Unique-body manifest contains duplicate SHA-256 rows.")

    profile_definition = build_profile_definition(args)
    fingerprint = config_fingerprint(config, profile_definition)
    manifest, profile_support = prepare_manifest(unique_bodies, events, panel, config, args)
    manifest["config_fingerprint"] = fingerprint
    artifact_errors = verify_selected_artifacts(manifest, paths.body_artifact_base, config.window_size)
    if not artifact_errors.empty:
        empty_body = pd.DataFrame(columns=BODY_SCORE_COLUMNS)
        empty_window = pd.DataFrame(columns=WINDOW_SCORE_COLUMNS)
        empty_failure = pd.DataFrame(columns=FAILURE_COLUMNS)
        empty_checkpoint = pd.DataFrame()
        empty_runtime = pd.DataFrame()
        empty_estimates = pd.DataFrame()
        empty_repro = pd.DataFrame(columns=REPRO_COLUMNS)
        checks = build_checks(config, manifest, profile_support, artifact_errors, empty_body, empty_window, empty_failure, empty_repro, args)
        failed_checks = int((~checks["passed"].astype(bool)).sum())
        summary = {
            "status": "FAIL",
            "failed_checks": failed_checks,
            "selected_unique_bodies": int(len(manifest)),
            "artifact_errors": int(len(artifact_errors)),
            "bodies_scored_this_run": 0,
            "bodies_reused_this_run": 0,
        }
        metadata = {
            "analysis_stage": "run-1c-dual-profile-npr-pilot",
            "script_version": SCRIPT_VERSION,
            "config_fingerprint": fingerprint,
            "detector_configuration": config.fingerprint_payload(profile_definition),
        }
        write_outputs(paths, manifest, profile_support, artifact_errors, empty_body, empty_window, empty_failure, empty_checkpoint, empty_runtime, empty_estimates, empty_repro, checks, summary, metadata)
        return 4

    valid_before = 0
    for body_sha in manifest["function_body_sha256"].astype(str):
        if load_valid_cached_result(result_cache_path(paths.cache_dir, body_sha), body_sha, fingerprint):
            valid_before += 1

    completed, failures_this_run, runtime, scoring_wall_seconds = score_pending_bodies(
        manifest, paths, config, fingerprint, args
    )
    valid_after = 0
    for body_sha in manifest["function_body_sha256"].astype(str):
        if load_valid_cached_result(result_cache_path(paths.cache_dir, body_sha), body_sha, fingerprint):
            valid_after += 1
    bodies_scored_this_run = max(0, valid_after - valid_before)
    bodies_reused_this_run = valid_before

    body_scores, window_scores, failures, checkpoints = flatten_results(
        manifest,
        paths,
        fingerprint,
        pending_is_failure=not args.prepare_only,
    )
    reproducibility = run_reproducibility_checks(
        manifest, paths, config, fingerprint, args, runtime
    )
    profile_summary = build_profile_summary(manifest, body_scores, window_scores, failures)
    estimates = build_full_run_estimates(
        profile_summary,
        support,
        args.calibration_profile_name,
        args.long_profile_name,
    )
    checks = build_checks(
        config,
        manifest,
        profile_support,
        artifact_errors,
        body_scores,
        window_scores,
        failures,
        reproducibility,
        args,
    )
    failed_checks = int((~checks["passed"].astype(bool)).sum())
    if args.prepare_only:
        status = "PREPARED_ONLY" if failed_checks == 0 else "FAIL"
    else:
        status = "PASS" if failed_checks == 0 else "FAIL"

    package_info = package_metadata(runtime)
    invocation_elapsed = float(time.perf_counter() - invocation_started)
    resume_validation_passed = bool(
        args.require_all_completed
        and bodies_scored_this_run == 0
        and bodies_reused_this_run == len(manifest)
        and failures.empty
    )
    summary = {
        "status": status,
        "failed_checks": failed_checks,
        "checks_total": int(len(checks)),
        "selected_unique_bodies": int(len(manifest)),
        "calibration_profile_selected": int((manifest["profile_name"] == args.calibration_profile_name).sum()),
        "long_profile_selected": int((manifest["profile_name"] == args.long_profile_name).sum()),
        "successful_unique_bodies": int(len(body_scores)),
        "failed_unique_bodies": int(len(failures)),
        "expected_windows": int(manifest["n_expected_windows"].sum()),
        "scored_windows": int(len(window_scores)),
        "partial_body_score_count": int(pd.to_numeric(body_scores.get("partial_body_score"), errors="coerce").fillna(0).sum()),
        "invalid_npr_window_count": int(pd.to_numeric(body_scores.get("n_invalid_npr_windows"), errors="coerce").fillna(0).sum()),
        "invalid_npr_token_count": int(pd.to_numeric(body_scores.get("invalid_npr_token_count"), errors="coerce").fillna(0).sum()),
        "agc_like_unique_bodies": int(pd.to_numeric(body_scores.get("agc_like"), errors="coerce").sum()),
        "hwc_like_unique_bodies": int(pd.to_numeric(body_scores.get("hwc_like"), errors="coerce").sum()),
        "bodies_scored_this_run": int(bodies_scored_this_run),
        "bodies_reused_this_run": int(bodies_reused_this_run),
        "failures_this_run": int(len(failures_this_run)),
        "model_loaded_this_run": bool(runtime is not None),
        "model_load_seconds": package_info.get("model_load_seconds", 0.0),
        "scoring_wall_seconds_this_run": scoring_wall_seconds,
        "invocation_elapsed_seconds": invocation_elapsed,
        "require_all_completed": bool(args.require_all_completed),
        "resume_validation_passed": resume_validation_passed,
        "config_fingerprint": fingerprint,
        "specification_input_status": config.specification_status,
        "specification_input_primary": config.specification_primary,
        "pilot_does_not_finalize_primary_specification": True,
    }
    input_hashes = {
        "input_unique_bodies_sha256": sha256_file(paths.input_unique_bodies),
        "input_events_sha256": sha256_file(paths.input_events),
        "input_panel_sha256": sha256_file(paths.input_panel),
        "input_support_sha256": sha256_file(paths.input_support),
        "input_specification_sha256": sha256_file(paths.input_specification),
    }
    metadata = {
        "status": status,
        "analysis_stage": "run-1c-dual-profile-npr-pilot",
        "script_version": SCRIPT_VERSION,
        "invocation_started_utc": invocation_started_utc,
        "invocation_completed_utc": utc_now(),
        "paths": {
            "input_unique_bodies": str(paths.input_unique_bodies.resolve()),
            "input_events": str(paths.input_events.resolve()),
            "input_panel": str(paths.input_panel.resolve()),
            "input_support": str(paths.input_support.resolve()),
            "input_specification": str(paths.input_specification.resolve()),
            "body_artifact_base": str(paths.body_artifact_base.resolve()),
            "output_dir": str(paths.output_dir.resolve()),
            "qc_dir": str(paths.qc_dir.resolve()),
            "cache_dir": str(paths.cache_dir.resolve()),
        },
        "input_hashes": input_hashes,
        "config_fingerprint": fingerprint,
        "detector_configuration": config.fingerprint_payload(profile_definition),
        "package_and_gpu_metadata": package_info,
        "column_semantics": {
            "n_scored_windows": "Windows for which model scoring was attempted.",
            "n_valid_npr_windows": "Attempted windows that produced a finite NPR value.",
            "n_invalid_npr_windows": "Attempted windows whose NPR value was undefined.",
            "partial_body_score": (
                "1 only when a single incomplete final tail window was excluded "
                "because original_log_rank was exactly zero."
            ),
        },
        "operational_note": (
            "This pilot measures computational feasibility for range100_200 and "
            "the >200-token extension needed by min100. It does not inspect DiD "
            "results or redefine the scientific primary specification."
        ),
    }
    write_outputs(
        paths,
        manifest,
        profile_support,
        artifact_errors,
        body_scores,
        window_scores,
        failures,
        checkpoints,
        profile_summary,
        estimates,
        reproducibility,
        checks,
        summary,
        metadata,
    )

    history_record = {
        "started_utc": invocation_started_utc,
        "completed_utc": utc_now(),
        "status": status,
        "bodies_scored_this_run": int(bodies_scored_this_run),
        "bodies_reused_this_run": int(bodies_reused_this_run),
        "failures_this_run": int(len(failures_this_run)),
        "model_loaded_this_run": bool(runtime is not None),
        "require_all_completed": bool(args.require_all_completed),
        "resume_validation_passed": resume_validation_passed,
        "elapsed_seconds": invocation_elapsed,
        "config_fingerprint": fingerprint,
    }
    append_jsonl(history_record, paths.qc_dir / "commit_function_npr_run_history.jsonl")

    print("=" * 76)
    print("Run dual-profile commit-function NPR pilot")
    print(f"Status:                         {status}")
    print(f"Selected unique bodies:         {len(manifest)}")
    print(f"Successful unique bodies:       {len(body_scores)}")
    print(f"Failed unique bodies:           {len(failures)}")
    print(f"Expected windows:               {int(manifest['n_expected_windows'].sum())}")
    print(f"Scored windows:                 {len(window_scores)}")
    print(f"Bodies scored this run:         {bodies_scored_this_run}")
    print(f"Bodies reused this run:         {bodies_reused_this_run}")
    print(f"Model loaded this run:          {int(runtime is not None)}")
    print(f"Resume validation passed:       {int(resume_validation_passed)}")
    print(f"Failed checks:                  {failed_checks}")
    print(f"Output directory:               {paths.output_dir}")
    print(f"QC directory:                   {paths.qc_dir}")
    print("=" * 76)
    return 0 if status in {"PASS", "PREPARED_ONLY"} else 5


def make_self_test_inputs(root: Path) -> argparse.Namespace:
    run1a = root / "run-1a" / "strict"
    bodies_dir = run1a / "function_bodies"
    run1b = root / "run-1b" / "strict"
    output = root / "run-1c" / "pilot"
    bodies_dir.mkdir(parents=True, exist_ok=True)
    run1b.mkdir(parents=True, exist_ok=True)

    calibration_tokens = [100, 105, 111, 115, 121, 125, 131, 135, 141, 145, 151, 155, 161, 165, 171, 175, 181, 185, 191, 195]
    long_tokens = [201, 220, 257, 300, 385, 450, 641, 800, 1100, 1500, 2100, 2300, 2600, 3000, 3500, 4000, 4500, 5000, 5500, 6000]
    token_counts = calibration_tokens + long_tokens
    unique_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    panel_rows: list[dict[str, Any]] = []

    for index, token_count in enumerate(token_counts):
        tokens = [f"t{index}_{j}" for j in range(token_count)]
        text = " ".join(tokens)
        raw = text.encode("utf-8")
        body_sha = sha256_bytes(raw)
        relative = Path("function_bodies") / body_sha[:2] / f"{body_sha}.pybody"
        path = run1a / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        n_windows = math.ceil(token_count / 128)
        unique_rows.append(
            {
                "function_body_sha256": body_sha,
                "function_body_relative_path": str(relative),
                "function_body_character_count": len(text),
                "function_body_utf8_byte_count": len(raw),
                "function_body_line_count": 1,
                "function_body_split_space_token_count": token_count,
                "function_body_nonempty_whitespace_token_count": token_count,
                "n_128_token_windows": n_windows,
                "tail_window_token_count": token_count - 128 * (n_windows - 1),
                "referencing_function_event_count": 1,
            }
        )
        source = "treatment" if index % 2 == 0 else "control"
        repo = f"owner/repo-{index % 4}"
        month = f"2025-{(index % 9) + 1:02d}"
        event_rows.append(
            {
                "function_event_id": f"event-{index}",
                "dataset_source": source,
                "repo_name": repo,
                "time": month,
                "function_body_sha256": body_sha,
                "input_preparation_complete": 1,
                "body_extraction_status": "prepared",
            }
        )
        panel_rows.append(
            {
                "dataset_source": source,
                "repo_name": repo,
                "time": month,
                "time_to_event": index % 3 - 1 if source == "treatment" else "",
            }
        )

    unique_path = run1a / "commit_function_detectcodegpt_unique_bodies.csv"
    events_path = run1a / "commit_function_detectcodegpt_input_events.csv"
    panel_path = root / "panel.csv"
    support_path = run1b / "commit_function_body_eligibility_support.csv"
    spec_path = run1b / "commit_function_detectcodegpt_scoring_spec.json"
    pd.DataFrame(unique_rows).to_csv(unique_path, index=False)
    pd.DataFrame(event_rows).to_csv(events_path, index=False)
    pd.DataFrame(panel_rows).drop_duplicates().to_csv(panel_path, index=False)
    pd.DataFrame(
        [
            {
                "spec_name": "range100_200",
                "eligible_unique_bodies": 20,
                "total_windows": sum(math.ceil(value / 128) for value in calibration_tokens),
                "total_scoring_sequences": sum(math.ceil(value / 128) for value in calibration_tokens) * 51,
            },
            {
                "spec_name": "min100",
                "eligible_unique_bodies": 40,
                "total_windows": sum(math.ceil(value / 128) for value in token_counts),
                "total_scoring_sequences": sum(math.ceil(value / 128) for value in token_counts) * 51,
            },
        ]
    ).to_csv(support_path, index=False)
    atomic_json(
        {
            "status": "frozen",
            "primary_spec": "range100_200",
            "scoring_model": "bigcode/starcoder2-7b",
            "window_size_literal_space_tokens": 128,
            "perturbations_per_window": 50,
            "perturbation_type": "random-insert-space+newline",
            "function_aggregation": "token-weighted mean",
            "agc_threshold": 1.5183,
            "random_seed": 20260723,
            "eligibility_specifications": [
                {
                    "name": "range100_200",
                    "role": "primary_candidate",
                    "minimum_literal_space_tokens": 100,
                    "maximum_literal_space_tokens": 200,
                },
                {
                    "name": "min100",
                    "role": "sensitivity",
                    "minimum_literal_space_tokens": 100,
                    "maximum_literal_space_tokens": None,
                },
            ],
        },
        spec_path,
    )

    return argparse.Namespace(
        input_unique_bodies=unique_path,
        input_events=events_path,
        input_panel=panel_path,
        input_support=support_path,
        input_specification=spec_path,
        body_artifact_base=run1a,
        output_dir=output,
        qc_dir=None,
        cache_dir=None,
        calibration_spec_name="range100_200",
        long_spec_name="min100",
        calibration_profile_name="calibration_range_100_200",
        long_profile_name="long_body_gt200",
        calibration_profile_size=20,
        long_profile_size=20,
        calibration_bands="100:110,111:120,121:130,131:140,141:150,151:160,161:170,171:180,181:190,191:200",
        long_window_strata="2:2,3:4,5:8,9:16,17:",
        device="cuda",
        model_cache_dir=Path("~/.cache/huggingface/hub").expanduser(),
        detector_output_name="run1c_self_test",
        pct_words_masked=0.5,
        span_length=2,
        perturbation_chunk_size=10,
        n_perturbation_rounds=1,
        quiet_internal_progress=True,
        detector_log_level="WARNING",
        progress_every_bodies=10,
        reproducibility_check_per_profile=1,
        reproducibility_tolerance=1e-12,
        overwrite_output=True,
        prepare_only=False,
        require_all_completed=False,
        mock_scoring=True,
    )


def _scripted_score_window(
    responses: list[dict[str, Any]],
) -> Callable[[str, int, DetectorConfig, RuntimeBundle | None], dict[str, Any]]:
    """Build a score_window-compatible callable that returns one pre-scripted
    response per call (one per window, in call order), used only by
    run_partial_body_policy_self_test() to exercise score_one_body()'s
    partial-body policy directly, without real or mock model scoring."""
    state = {"index": 0}

    def _score_window(
        text: str, seed: int, config: DetectorConfig, runtime: RuntimeBundle | None
    ) -> dict[str, Any]:
        del text, seed, config, runtime
        response = responses[state["index"]]
        state["index"] += 1
        return dict(response)

    return _score_window


def _valid_window_response(window_npr: float = 1.3) -> dict[str, Any]:
    return {
        "original_log_rank": 1.5,
        "mean_perturbed_log_rank": 1.5 * window_npr,
        "window_npr": float(window_npr),
        "expected_perturbations": 50,
        "valid_perturbation_scores": 50,
        "scoring_seconds": 0.001,
    }


def _degenerate_window_response(reason: str) -> dict[str, Any]:
    """A window response engineered to be non-finite for a specific,
    named reason, matching classify_window_validity()'s branches."""
    if reason == "zero_original_log_rank":
        return {
            "original_log_rank": 0.0,
            "mean_perturbed_log_rank": 1.2,
            "window_npr": float("nan"),
            "expected_perturbations": 50,
            "valid_perturbation_scores": 50,
            "scoring_seconds": 0.001,
        }
    if reason == "no_valid_perturbation_scores":
        return {
            "original_log_rank": 1.5,
            "mean_perturbed_log_rank": float("nan"),
            "window_npr": float("nan"),
            "expected_perturbations": 50,
            "valid_perturbation_scores": 0,
            "scoring_seconds": 0.001,
        }
    raise ValueError(f"Unsupported test reason: {reason}")


def _make_policy_test_row(body_sha: str, n_expected_windows: int) -> pd.Series:
    return pd.Series(
        {
            "profile_name": "unit_test_profile",
            "stratum_name": "unit_test_stratum",
            "sample_rank": 1,
            "function_body_sha256": body_sha,
            "function_body_relative_path": "unused.txt",
            "function_body_split_space_token_count": 3,
            "n_expected_windows": n_expected_windows,
            "referencing_function_event_count": 1,
        }
    )


def run_partial_body_policy_self_test() -> None:
    """Directly unit-test score_one_body()'s partial-body scoring policy
    (Cases 1-6) and the null-safe reproducibility comparison (Case 7), using
    a scripted score_window callable instead of real or mock model scoring.
    These are exactly the edge cases raised in code review; see
    score_one_body(), classify_window_validity(), and compare_results() for
    the behavior under test.
    """
    config = DetectorConfig(
        specification_status="frozen",
        specification_primary="unit_test",
        scoring_model="bigcode/starcoder2-7b",
        window_size=2,
        perturbations_per_window=50,
        perturbation_type="random-insert-space+newline",
        function_aggregation="token_weighted_mean",
        agc_threshold=1.5183,
        random_seed=20260723,
        eligibility_specifications=(),
    )
    # chunk_literal_space("a b c", window_size=2) -> window 0 = ["a","b"]
    # (2 tokens), window 1 = ["c"] (1 token, the tail window).
    text = "a b c"

    # Case 1: every window valid -> ordinary success, no partial-body flag.
    row = _make_policy_test_row("case1", 2)
    result = score_one_body(
        row, text, config, "fp",
        _scripted_score_window([_valid_window_response(1.1), _valid_window_response(1.7)]),
        None,
    )
    if result["partial_body_score"] != 0 or result["n_invalid_npr_windows"] != 0:
        raise AssertionError(f"Case 1 (all valid) unexpectedly marked as partial: {result}")
    if not math.isfinite(result["function_npr"]):
        raise AssertionError("Case 1 function_npr must be finite")

    # Case 2: main window valid, tail window degenerate -> partial success.
    row = _make_policy_test_row("case2", 2)
    result = score_one_body(
        row, text, config, "fp",
        _scripted_score_window(
            [_valid_window_response(1.1), _degenerate_window_response("zero_original_log_rank")]
        ),
        None,
    )
    if result["partial_body_score"] != 1:
        raise AssertionError(f"Case 2 (tail-only degenerate) must be a partial success: {result}")
    if result["n_valid_npr_windows"] != 1 or result["n_invalid_npr_windows"] != 1:
        raise AssertionError(f"Case 2 valid/invalid window counts wrong: {result}")
    tail_chunk = result["chunks"][1]
    if tail_chunk["window_npr"] is not None:
        raise AssertionError("Case 2 tail window_npr must be sanitized to None, not left as NaN")
    if tail_chunk["window_npr_valid"] is not False or tail_chunk["window_npr_invalid_reason"] != "zero_original_log_rank":
        raise AssertionError(f"Case 2 tail window validity/reason wrong: {tail_chunk}")
    if not math.isfinite(result["function_npr"]):
        raise AssertionError("Case 2 function_npr must still be finite (computed from the valid window only)")
    case2_result = result  # reused for the Case 5 reproducibility check below

    # Case 3: every window degenerate -> body failure (AllWindowsInvalidNprError).
    row = _make_policy_test_row("case3", 2)
    try:
        score_one_body(
            row, text, config, "fp",
            _scripted_score_window(
                [
                    _degenerate_window_response("zero_original_log_rank"),
                    _degenerate_window_response("no_valid_perturbation_scores"),
                ]
            ),
            None,
        )
        raise AssertionError("Case 3 (all windows invalid) should have raised AllWindowsInvalidNprError")
    except AllWindowsInvalidNprError:
        pass

    # Case 4: the *non-tail* (main) window is degenerate, tail window valid
    # -> a body failure (NonTailWindowInvalidNprError), not a partial
    # success, per the policy that a non-tail invalid window is treated as
    # a likely genuine scoring problem rather than the known tail-window
    # edge case.
    row = _make_policy_test_row("case4", 2)
    try:
        score_one_body(
            row, text, config, "fp",
            _scripted_score_window(
                [_degenerate_window_response("zero_original_log_rank"), _valid_window_response(1.2)]
            ),
            None,
        )
        raise AssertionError("Case 4 (non-tail window invalid) should have raised NonTailWindowInvalidNprError")
    except NonTailWindowInvalidNprError:
        pass

    # Case 5: exact-multiple body, so the final window is full-size rather
    # than an incomplete tail. An invalid final full-size window must fail.
    exact_multiple_text = "a b c d"  # window_size=2 -> two full windows
    row = _make_policy_test_row("case5", 2)
    try:
        score_one_body(
            row, exact_multiple_text, config, "fp",
            _scripted_score_window(
                [_valid_window_response(1.1), _degenerate_window_response("zero_original_log_rank")]
            ),
            None,
        )
        raise AssertionError(
            "Case 5 (invalid full-size final window) should have raised "
            "NonTailWindowInvalidNprError"
        )
    except NonTailWindowInvalidNprError:
        pass

    # Case 6: a true incomplete tail is invalid because no perturbed variant
    # produced a finite rank. This is not the accepted zero-denominator edge
    # case and must fail conservatively.
    row = _make_policy_test_row("case6", 2)
    try:
        score_one_body(
            row, text, config, "fp",
            _scripted_score_window(
                [_valid_window_response(1.1), _degenerate_window_response("no_valid_perturbation_scores")]
            ),
            None,
        )
        raise AssertionError(
            "Case 6 (disallowed invalid-tail reason) should have raised "
            "DisallowedTailWindowInvalidNprError"
        )
    except DisallowedTailWindowInvalidNprError:
        pass

    # Case 7: a cached result containing sanitized None values (from Case 2)
    # must (a) round-trip through JSON without raising -- this alone is an
    # implicit regression check for the original bug, since an
    # un-sanitized NaN would fail this exact json.dumps(allow_nan=False)
    # call -- and (b) compare correctly via compare_results()/
    # nullable_float_matches() without raising TypeError on the None
    # values, both when identical and when a rerun disagrees.
    identical_rerun = json.loads(json.dumps(case2_result, allow_nan=False))
    comparison = compare_results(case2_result, identical_rerun, tolerance=1e-9)
    if not comparison["passed"]:
        raise AssertionError(f"Case 7 (identical rerun) should match, got: {comparison}")

    diverged_rerun = json.loads(json.dumps(case2_result, allow_nan=False))
    diverged_rerun["chunks"][1]["window_npr"] = 2.5
    diverged_rerun["chunks"][1]["window_npr_valid"] = True
    diverged_rerun["chunks"][1]["window_npr_invalid_reason"] = None
    diverged_comparison = compare_results(case2_result, diverged_rerun, tolerance=1e-9)
    if diverged_comparison["passed"]:
        raise AssertionError(
            "Case 7 (rerun disagrees about window validity) must not be reported as a "
            f"match: {diverged_comparison}"
        )

    print("Partial-body scoring policy self-test: PASS")


def run_self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="run1c-self-test-") as tmp:
        root = Path(tmp)
        run_partial_body_policy_self_test()

        first = make_self_test_inputs(root)
        exit_code = run_analysis(first)
        if exit_code != 0:
            raise RuntimeError(f"First self-test run failed with exit code {exit_code}")
        summary_path = first.output_dir / "qc" / "commit_function_npr_summary.json"
        with summary_path.open("r", encoding="utf-8") as stream:
            summary = json.load(stream)
        if summary["status"] != "PASS" or summary["successful_unique_bodies"] != 40:
            raise RuntimeError(f"Unexpected first-run self-test summary: {summary}")

        second = make_self_test_inputs(root)
        second.overwrite_output = False
        second.require_all_completed = True
        exit_code = run_analysis(second)
        if exit_code != 0:
            raise RuntimeError(f"Resume self-test failed with exit code {exit_code}")
        with summary_path.open("r", encoding="utf-8") as stream:
            resumed = json.load(stream)
        if not resumed["resume_validation_passed"]:
            raise RuntimeError(f"Resume validation did not pass: {resumed}")
        if resumed["bodies_scored_this_run"] != 0 or resumed["bodies_reused_this_run"] != 40:
            raise RuntimeError(f"Unexpected resume counts: {resumed}")
        print("Self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Score a deterministic dual-profile pilot of unique implementation "
            "bodies with the StarCoder2 perturbation-based NPR detector."
        )
    )
    parser.add_argument(
        "--input-unique-bodies",
        type=Path,
        default=Path(
            "output/commit_function/run-1a/strict/"
            "commit_function_detectcodegpt_unique_bodies.csv"
        ),
    )
    parser.add_argument(
        "--input-events",
        type=Path,
        default=Path(
            "output/commit_function/run-1a/strict/"
            "commit_function_detectcodegpt_input_events.csv"
        ),
    )
    parser.add_argument(
        "--input-panel",
        type=Path,
        default=Path(
            "../ai_code_complexity_study_python/ai-code-complexity-study/"
            "repo_python/run-py-4a/strict/"
            "panel_event_monthly_agc_changed_block_py.csv"
        ),
    )
    parser.add_argument(
        "--input-support",
        type=Path,
        default=Path(
            "output/commit_function/run-1b/strict/"
            "commit_function_body_eligibility_support.csv"
        ),
    )
    parser.add_argument(
        "--input-specification",
        type=Path,
        default=Path(
            "output/commit_function/run-1b/strict/"
            "commit_function_detectcodegpt_scoring_spec.json"
        ),
    )
    parser.add_argument(
        "--body-artifact-base",
        type=Path,
        default=Path("output/commit_function/run-1a/strict"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/commit_function/run-1c/pilot200-dual-profile-v4"),
    )
    parser.add_argument("--qc-dir", type=Path, default=None)
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--calibration-spec-name", default="range100_200")
    parser.add_argument("--long-spec-name", default="min100")
    parser.add_argument("--calibration-profile-name", default="calibration_range_100_200")
    parser.add_argument("--long-profile-name", default="long_body_gt200")
    parser.add_argument("--calibration-profile-size", type=int, default=100)
    parser.add_argument("--long-profile-size", type=int, default=100)
    parser.add_argument(
        "--calibration-bands",
        default=(
            "100:110,111:120,121:130,131:140,141:150,151:160,"
            "161:170,171:180,181:190,191:200"
        ),
    )
    parser.add_argument(
        "--long-window-strata",
        default="2:2,3:4,5:8,9:16,17:",
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument(
        "--model-cache-dir",
        type=Path,
        default=Path("~/.cache/huggingface/hub").expanduser(),
    )
    parser.add_argument("--detector-output-name", default="run1c_commit_function_npr_pilot_v4")
    parser.add_argument("--pct-words-masked", type=float, default=0.5)
    parser.add_argument("--span-length", type=int, default=2)
    parser.add_argument("--perturbation-chunk-size", type=int, default=10)
    parser.add_argument("--n-perturbation-rounds", type=int, default=1)
    parser.add_argument(
        "--quiet-internal-progress",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--detector-log-level", default="WARNING")
    parser.add_argument("--progress-every-bodies", type=int, default=5)
    parser.add_argument("--reproducibility-check-per-profile", type=int, default=1)
    parser.add_argument("--reproducibility-tolerance", type=float, default=1e-12)
    parser.add_argument("--overwrite-output", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
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
    exit_code = run_analysis(args)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
