#!/usr/bin/env python3
"""Run sharded full StarCoder2 NPR scoring for one frozen eligibility specification.

This experiment follows run-1a, run-1b, and run-1b2.

Purpose:
    1. Select every unique implementation body admitted by one frozen
       run-1b eligibility specification.
    2. Score each selected body with the calibrated overlap-window NPR
       detector and frozen run-1c0b threshold.
    3. Save one resumable cache artifact per body and produce complete
       body-, window-, failure-, runtime-, and QC-level outputs.
    4. Deterministically partition the SHA-256-sorted manifest across one or
       more independent GPU workers.
    5. Merge shard outputs with explicit duplicate, omission, and workload
       checks while preserving resumable per-body cache artifacts.

Scientific unit:
    One approved commit-function change event.

Computational unit:
    One unique implementation body identified by SHA-256.

The program does not aggregate repository-month outcomes or run DiD. It scores
all bodies in the explicitly selected frozen eligibility specification and
records the selection and detector configuration for later aggregation.
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


SCRIPT_VERSION = "run-1d-gt200-sharded-v2"
GT200_SPEC_NAME = "gt200"
GT200_MINIMUM_LITERAL_SPACE_TOKENS = 201
GT200_MAXIMUM_LITERAL_SPACE_TOKENS = None
EXPECTED_AGC_THRESHOLD = 1.571637
EXPECTED_ALGORITHM_VERSION = (
    "overlap_final_full_window_valid_frontier_weighting-v1"
)
EXPECTED_FUNCTION_AGGREGATION = "valid_frontier_weighted_mean"
EXPECTED_DECISION_RULE = "function_npr > agc_threshold"
EXPECTED_WINDOW_POLICY = "full_size_final_window_shifted_backward_with_overlap"
EXPECTED_PARTIAL_BODY_POLICY = "any_valid_window_partial_success_full_windows-v2"
# Policy label history (embedded in the config fingerprint, so any change
# here also invalidates prior caches):
#   incomplete_tail_zero_original_rank_only-v1  (run-1c-v4 and earlier):
#       only a short trailing window invalid for exactly
#       "zero_original_log_rank" allowed a partial body success.
#   any_valid_window_partial_success_full_windows-v2  (run-1c-v5+):
#       chunk_literal_space() never produces a short trailing window, so a
#       body succeeds (partial_body_score=1) whenever at least one window
#       is valid, regardless of the invalid window's position or reason,
#       and fails only when every window is invalid. run-1c-v5 shipped this
#       policy but still carried the stale -v1 label; the label is
#       corrected here.
PARTIAL_BODY_POLICY = "any_valid_window_partial_success_full_windows-v2"

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
    # marginal_token_count is the number of *new* body tokens this window
    # contributes that no earlier window already covered, as a static
    # property of the windowing alone (all windows assumed valid). See
    # compute_marginal_token_counts().
    "marginal_token_count",
    # aggregation_weight_token_count is the weight actually used by
    # aggregate_weighted() for the body's function_npr: the number of body
    # tokens this window covers that no earlier VALID window covers
    # (0 for every invalid window). Equal to marginal_token_count whenever
    # every window in the body is valid. See compute_aggregation_weights().
    "aggregation_weight_token_count",
    "window_seed",
    "is_last_window",
    # True only for a final window that was shifted backward to reach a
    # full window_size (i.e. marginal_token_count < chunk_token_count).
    # See chunk_literal_space().
    "overlaps_previous_window",
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
    input_eligibility_specification: Path
    input_threshold_specification: Path
    body_artifact_base: Path
    output_dir: Path
    qc_dir: Path
    cache_dir: Path


@dataclass(frozen=True)
class DetectorConfig:
    eligibility_status: str
    specification_primary: str
    threshold_status: str
    scoring_model: str
    window_size: int
    perturbations_per_window: int
    perturbation_type: str
    function_aggregation: str
    agc_threshold: float
    random_seed: int
    algorithm_version: str
    decision_rule: str
    window_policy: str
    partial_body_policy: str
    calibration_dataset: str
    calibration_bodies: int
    calibration_auroc: float
    eligibility_specification_sha256: str
    threshold_specification_sha256: str
    eligibility_specifications: tuple[dict[str, Any], ...]

    def fingerprint_payload(self, profile_definition: dict[str, Any]) -> dict[str, Any]:
        return {
            "script_version": SCRIPT_VERSION,
            "eligibility_status": self.eligibility_status,
            "specification_primary": self.specification_primary,
            "threshold_status": self.threshold_status,
            "scoring_model": self.scoring_model,
            "window_size": self.window_size,
            "perturbations_per_window": self.perturbations_per_window,
            "perturbation_type": self.perturbation_type,
            "function_aggregation": self.function_aggregation,
            "agc_threshold": self.agc_threshold,
            "random_seed": self.random_seed,
            "algorithm_version": self.algorithm_version,
            "decision_rule": self.decision_rule,
            "window_policy": self.window_policy,
            "partial_body_policy": self.partial_body_policy,
            "calibration_dataset": self.calibration_dataset,
            "calibration_bodies": self.calibration_bodies,
            "calibration_auroc": self.calibration_auroc,
            "eligibility_specification_sha256": self.eligibility_specification_sha256,
            "threshold_specification_sha256": self.threshold_specification_sha256,
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


def load_detector_config(
    eligibility_path: Path,
    threshold_path: Path,
) -> DetectorConfig:
    with eligibility_path.open("r", encoding="utf-8") as stream:
        eligibility = json.load(stream)
    with threshold_path.open("r", encoding="utf-8") as stream:
        threshold = json.load(stream)

    eligibility_required = {
        "status",
        "primary_spec",
        "scoring_model",
        "window_size_literal_space_tokens",
        "perturbations_per_window",
        "perturbation_type",
        "random_seed",
        "eligibility_specifications",
    }
    threshold_required = {
        "status",
        "scoring_model",
        "window_size_literal_space_tokens",
        "perturbations_per_window",
        "perturbation_type",
        "function_aggregation",
        "agc_threshold",
        "random_seed",
        "algorithm_version",
        "decision_rule",
        "window_policy",
        "partial_body_policy",
        "threshold_calibration_dataset",
        "benchmark_bodies",
        "overall_auroc",
    }
    missing_eligibility = sorted(eligibility_required - set(eligibility))
    missing_threshold = sorted(threshold_required - set(threshold))
    if missing_eligibility:
        raise ValueError(
            f"Eligibility specification JSON is missing keys: {missing_eligibility}"
        )
    if missing_threshold:
        raise ValueError(
            f"Threshold specification JSON is missing keys: {missing_threshold}"
        )

    consistency_fields = {
        "scoring_model": str,
        "window_size_literal_space_tokens": int,
        "perturbations_per_window": int,
        "perturbation_type": str,
        "random_seed": int,
    }
    mismatches = []
    for field, caster in consistency_fields.items():
        left = caster(eligibility[field])
        right = caster(threshold[field])
        if left != right:
            mismatches.append(f"{field}: eligibility={left!r}, threshold={right!r}")
    if mismatches:
        raise ValueError(
            "Eligibility and threshold specifications are inconsistent: "
            + "; ".join(mismatches)
        )

    return DetectorConfig(
        eligibility_status=str(eligibility["status"]),
        specification_primary=str(eligibility["primary_spec"]),
        threshold_status=str(threshold["status"]),
        scoring_model=str(threshold["scoring_model"]),
        window_size=int(threshold["window_size_literal_space_tokens"]),
        perturbations_per_window=int(threshold["perturbations_per_window"]),
        perturbation_type=str(threshold["perturbation_type"]),
        function_aggregation=str(threshold["function_aggregation"]),
        agc_threshold=float(threshold["agc_threshold"]),
        random_seed=int(threshold["random_seed"]),
        algorithm_version=str(threshold["algorithm_version"]),
        decision_rule=str(threshold["decision_rule"]),
        window_policy=str(threshold["window_policy"]),
        partial_body_policy=str(threshold["partial_body_policy"]),
        calibration_dataset=str(threshold["threshold_calibration_dataset"]),
        calibration_bodies=int(threshold["benchmark_bodies"]),
        calibration_auroc=float(threshold["overall_auroc"]),
        eligibility_specification_sha256=sha256_file(eligibility_path),
        threshold_specification_sha256=sha256_file(threshold_path),
        eligibility_specifications=tuple(eligibility["eligibility_specifications"]),
    )


def find_spec(config: DetectorConfig, name: str) -> dict[str, Any]:
    matches = [spec for spec in config.eligibility_specifications if str(spec.get("name")) == name]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one eligibility specification named {name!r}; found {len(matches)}")
    return matches[0]


def validate_gt200_detector_configuration(
    config: DetectorConfig,
    spec_name: str,
) -> dict[str, Any]:
    """Fail before scoring if either frozen production specification drifted."""
    if spec_name != GT200_SPEC_NAME:
        raise ValueError(
            f"This scorer is frozen for spec_name={GT200_SPEC_NAME!r}; "
            f"received {spec_name!r}."
        )
    if config.eligibility_status != "frozen":
        raise ValueError(
            "Eligibility specification must be frozen; "
            f"observed {config.eligibility_status!r}."
        )
    if config.threshold_status != "frozen":
        raise ValueError(
            "Threshold specification must be frozen; "
            f"observed {config.threshold_status!r}."
        )
    if config.specification_primary != GT200_SPEC_NAME:
        raise ValueError(
            f"Eligibility primary_spec must be {GT200_SPEC_NAME!r}; "
            f"observed {config.specification_primary!r}."
        )
    if len(config.eligibility_specifications) != 1:
        raise ValueError(
            "The frozen gt200 production file must contain exactly one "
            "eligibility specification; "
            f"observed {len(config.eligibility_specifications)}."
        )

    selected_spec = find_spec(config, spec_name)
    if str(selected_spec.get("role")) != "primary_candidate":
        raise ValueError(
            "gt200 role must be 'primary_candidate'; "
            f"observed {selected_spec.get('role')!r}."
        )
    minimum = int(selected_spec["minimum_literal_space_tokens"])
    maximum_raw = selected_spec.get("maximum_literal_space_tokens")
    maximum = None if maximum_raw is None else int(maximum_raw)
    if minimum != GT200_MINIMUM_LITERAL_SPACE_TOKENS:
        raise ValueError(
            "gt200 minimum_literal_space_tokens must be 201; "
            f"observed {minimum}."
        )
    if maximum is not GT200_MAXIMUM_LITERAL_SPACE_TOKENS:
        raise ValueError(
            "gt200 maximum_literal_space_tokens must be null; "
            f"observed {maximum!r}."
        )

    policy_mismatches: list[str] = []
    expected_values = {
        "scoring_model": "bigcode/starcoder2-7b",
        "window_size": 128,
        "perturbations_per_window": 50,
        "perturbation_type": "random-insert-space+newline",
        "random_seed": 20260723,
        "algorithm_version": EXPECTED_ALGORITHM_VERSION,
        "function_aggregation": EXPECTED_FUNCTION_AGGREGATION,
        "decision_rule": EXPECTED_DECISION_RULE,
        "window_policy": EXPECTED_WINDOW_POLICY,
        "partial_body_policy": EXPECTED_PARTIAL_BODY_POLICY,
    }
    for field, expected in expected_values.items():
        observed = getattr(config, field)
        if observed != expected:
            policy_mismatches.append(
                f"{field}: observed={observed!r}, expected={expected!r}"
            )
    if not math.isclose(
        config.agc_threshold,
        EXPECTED_AGC_THRESHOLD,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        policy_mismatches.append(
            "agc_threshold: "
            f"observed={config.agc_threshold!r}, "
            f"expected={EXPECTED_AGC_THRESHOLD!r}"
        )
    if policy_mismatches:
        raise ValueError(
            "Frozen overlap detector specification does not match the "
            "approved production policy: "
            + "; ".join(policy_mismatches)
        )
    return selected_spec


def build_profile_definition(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "full_spec_name": args.spec_name,
        "full_profile_name": args.profile_name,
        "selection_method": "all_unique_bodies_within_frozen_eligibility_bounds",
        "ordering_method": "function_body_sha256",
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
    """Select every unique body admitted by one frozen run-1b specification."""
    specification = find_spec(config, args.spec_name)
    minimum = int(specification["minimum_literal_space_tokens"])
    maximum_raw = specification.get("maximum_literal_space_tokens")
    maximum = None if maximum_raw is None else int(maximum_raw)

    token_count = unique_bodies["function_body_split_space_token_count"]
    mask = token_count.ge(minimum)
    if maximum is not None:
        mask &= token_count.le(maximum)

    manifest = unique_bodies.loc[mask].copy()
    manifest = manifest.sort_values("function_body_sha256", kind="mergesort").reset_index(drop=True)
    manifest["profile_name"] = args.profile_name
    manifest["stratum_name"] = args.spec_name
    manifest["stratum_order"] = 0
    manifest["stratum_sample_target"] = len(manifest)
    manifest["sampling_fill_mode"] = "full_specification"
    manifest["deterministic_sample_key"] = manifest["function_body_sha256"]
    manifest["sample_rank"] = np.arange(1, len(manifest) + 1)
    manifest["n_expected_windows"] = manifest["n_128_token_windows"].astype(int)
    manifest["selected_for_full_scoring"] = 1
    manifest = enrich_manifest_context(manifest, events, panel)
    global_eligible_unique_bodies = int(len(manifest))
    global_total_windows = int(manifest["n_expected_windows"].sum())

    # The full manifest is already sorted by SHA-256. Round-robin assignment
    # keeps sharding deterministic and generally balances body counts better
    # than contiguous slices while guaranteeing disjoint coverage.
    manifest["num_shards"] = int(args.num_shards)
    manifest["shard_index"] = np.arange(len(manifest), dtype=int) % int(args.num_shards)
    manifest = manifest.loc[manifest["shard_index"].eq(int(args.shard_index))].copy()
    if args.max_bodies_per_shard is not None:
        manifest = manifest.head(int(args.max_bodies_per_shard)).copy()
    manifest = manifest.reset_index(drop=True)

    support = pd.DataFrame([{
        "profile_name": args.profile_name,
        "spec_name": args.spec_name,
        "minimum_literal_space_tokens": minimum,
        "maximum_literal_space_tokens": maximum,
        "eligible_unique_bodies": int(len(manifest)),
        "total_windows": int(manifest["n_expected_windows"].sum()),
        "total_scoring_sequences": int(manifest["n_expected_windows"].sum()) * (config.perturbations_per_window + 1),
        "selection_complete": True,
        "num_shards": int(args.num_shards),
        "shard_index": int(args.shard_index),
        "max_bodies_per_shard": args.max_bodies_per_shard,
        "global_eligible_unique_bodies": global_eligible_unique_bodies,
        "global_total_windows": global_total_windows,
    }])
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
    """Partition `text` (already split on literal spaces) into consecutive
    windows of up to `window_size` tokens, with NO short trailing window.

    Redesign rationale (2026-07-23)
    ---------------------------------
    The original implementation produced a final "tail" window containing
    whatever tokens were left over -- which could be as few as 1-2 tokens
    when a body's token count was just above a multiple of window_size
    (e.g. a 129-token body produced a 128-token window plus a 1-token
    tail). That near-empty tail window was the root cause of an entire
    class of downstream problems seen in the run-1c v1 and v4 pilots:
      - the model ranking every token in a 1-2 token window #1, giving
        original_log_rank == 0 and an undefined (NaN) window_npr ratio
        (see classify_window_validity's "zero_original_log_rank");
      - perturbing a 1-token window sometimes producing zero finite
        perturbation ranks at all ("no_valid_perturbation_scores");
      - a growing amount of exception-handling machinery (formerly
        NonTailWindowInvalidNprError / DisallowedTailWindowInvalidNprError
        / is_incomplete_tail_window) whose only job was to decide, case by
        case, whether a given short tail window's failure was "benign"
        enough to still allow a partial body success.

    Rather than continuing to refine that classification, this function
    removes the underlying condition. If the naive non-overlapping
    windowing would leave a final window shorter than window_size (and
    there is more than one window in total), that final window is shifted
    backward so it ends at the same position but covers exactly
    window_size tokens, overlapping with the previous window instead of
    being short. Every window that reaches the scoring model is therefore
    always exactly window_size tokens, except when the *entire* body has
    fewer than window_size tokens, in which case there is exactly one
    window covering the whole body (a short whole body is a real,
    unavoidable input, not an artifact of windowing).

    Overlap and double-counting
    -----------------------------
    Shifting the final window backward means it can share tokens with the
    previous window. Both windows are still independently perturbed and
    scored (the model needs the full window_size of context either way),
    but the token-weighted aggregation must not count an overlapping
    token's contribution twice. Two related per-window quantities handle
    this: compute_marginal_token_counts() assigns each window its static
    coverage (tokens not covered by ANY earlier window; always sums to the
    body's total token count), and compute_aggregation_weights() assigns
    the weight actually used by aggregate_weighted() (tokens not covered
    by any earlier VALID window; identical to the static marginals when
    every window is valid). Aggregation never uses chunk_token_count, so
    no token is double-counted or dropped.

    With this construction, only the final window can ever end up
    overlapping its predecessor (every earlier window always advances by
    exactly window_size with no shift), so in practice every window's
    marginal_token_count equals window_size except possibly the last one.

    Returns
    -------
    A list of (chunk_text, chunk_token_count, start_token_body,
    end_token_body) tuples, in left-to-right order. chunk_token_count is
    always the actual number of tokens fed to the model for that window
    (== window_size for every window except a single window covering a
    body shorter than window_size). start_token_body/end_token_body are
    absolute token offsets into the body and MAY overlap between the final
    two windows -- callers must weight by compute_aggregation_weights()
    (or compute_marginal_token_counts() for static coverage accounting),
    never by chunk_token_count, when aggregating across windows.
    """
    tokens = text.split(" ")
    total_tokens = len(tokens)

    if total_tokens <= window_size:
        # The whole body fits in a single window; there is nothing to
        # shift and no overlap is possible or needed.
        return [(text, total_tokens, 0, total_tokens)]

    chunks: list[tuple[str, int, int, int]] = []
    start = 0
    while start < total_tokens:
        end = min(start + window_size, total_tokens)
        if end - start < window_size and chunks:
            # This would be a short trailing window (only possible for the
            # final window under this simple non-overlapping advance).
            # Shift it backward so it still ends at end == total_tokens but
            # covers exactly window_size tokens.
            start = end - window_size
        selected = tokens[start:end]
        chunks.append((" ".join(selected), len(selected), start, end))
        if end >= total_tokens:
            break
        start = end
    return chunks


def compute_marginal_token_counts(chunks: list[tuple[str, int, int, int]]) -> list[int]:
    """Compute each window's marginal token count: the number of tokens in
    that window not already covered by an earlier window in the same body,
    in left-to-right (chunk_index) order.

    This is a plain advancing-frontier scan: each window contributes
    max(0, window_end - max(window_start, frontier)) new tokens, and the
    frontier then advances to window_end. Summing the returned list always
    equals the body's total token count (the last window's
    end_token_body), since every token position is counted exactly once,
    at the first window that reaches it.

    With chunk_literal_space()'s windowing, only the final window can ever
    overlap with its predecessor, so in practice every returned value
    equals that window's own token count except possibly the last -- but
    this function does not assume that, and would remain correct if a
    future windowing scheme produced overlap elsewhere.
    """
    marginal_counts: list[int] = []
    frontier = 0
    for _, _, start, end in chunks:
        marginal_start = max(start, frontier)
        marginal_counts.append(max(0, end - marginal_start))
        frontier = max(frontier, end)
    return marginal_counts


def compute_aggregation_weights(chunks: list[dict[str, Any]]) -> list[int]:
    """Compute each window's aggregation weight for the function-level NPR:
    the number of body tokens covered by that window that no EARLIER VALID
    window already covers. Invalid windows always receive weight 0.

    Why this is not the same as marginal_token_count
    --------------------------------------------------
    marginal_token_count is a static property of the windowing alone: it
    attributes every overlapped token to the first window that covers it,
    assuming all windows contribute. That assumption breaks in a partial
    body. Concrete production-scale example (window_size=128, 257-token
    body): windows A=[0,128), B=[128,256), C=[129,257) have static
    marginals [128, 128, 1]. If B is invalid but A and C are valid,
    weighting C by its static marginal of 1 discards C's valid signal over
    tokens 129-255 -- 127 tokens that C actually scored and that no other
    VALID window covers -- and the body's function_npr collapses to
    essentially A's value alone. Recomputing the frontier over valid
    windows only gives C a weight of 128, so the body's estimate uses all
    the valid signal that exists: (a*128 + c*128) / 256, with exactly one
    token (index 128, covered only by invalid B) carrying no valid signal.

    Properties
    ------------
    - When every window is valid, the returned weights are identical to
      compute_marginal_token_counts() (the frontier scans are the same),
      so the ordinary all-valid path is numerically unchanged.
    - sum(weights) equals the number of body tokens covered by at least
      one valid window, counted once each; total_tokens - sum(weights) is
      the number of tokens with no valid signal at all.
    - Windows are scanned in chunk_index (left-to-right) order, so an
      overlapped token is attributed to the first valid window covering
      it, mirroring compute_marginal_token_counts()'s convention.

    Each chunk dict must already carry "start_token_body",
    "end_token_body", and "window_npr_valid".
    """
    weights: list[int] = []
    frontier = 0
    for chunk in chunks:
        if not bool(chunk["window_npr_valid"]):
            weights.append(0)
            continue
        start = int(chunk["start_token_body"])
        end = int(chunk["end_token_body"])
        marginal_start = max(start, frontier)
        weights.append(max(0, end - marginal_start))
        frontier = max(frontier, end)
    return weights


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
    """Token-weighted mean of window_npr across a body's windows, weighting
    each window by its aggregation_weight_token_count -- the number of body
    tokens it covers that no earlier VALID window covers (see
    compute_aggregation_weights()). Invalid windows carry weight 0 by
    construction, and a window can also carry weight 0 when every token it
    covers is already represented by an earlier valid window (fully
    shadowed overlap); both are excluded from the mean. With every window
    valid, the weights equal the static marginal token counts and this
    reduces to the previous behavior exactly."""
    valid = [
        chunk
        for chunk in chunks
        if math.isfinite(float(chunk["window_npr"]))
        and int(chunk["aggregation_weight_token_count"]) > 0
    ]
    if not valid:
        return float("nan")
    numerator = sum(
        float(chunk["window_npr"]) * int(chunk["aggregation_weight_token_count"])
        for chunk in valid
    )
    denominator = sum(int(chunk["aggregation_weight_token_count"]) for chunk in valid)
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


# NonTailWindowInvalidNprError and DisallowedTailWindowInvalidNprError
# (2026-07-23 removal): these existed only to distinguish a "benign" short
# trailing-window failure from a "suspicious" full-size-window failure.
# Now that chunk_literal_space() never produces a short trailing window
# (see its docstring), that distinction no longer has a basis: every
# window is always exactly window_size tokens (except a single window
# covering a whole body shorter than window_size), so an invalid window is
# equally uninterpretable regardless of its position. See score_one_body()
# for the simplified policy that replaces the three-way exception split.


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
    # original_log_rank can be exactly 0.0 when the model ranks every
    # token in the window #1. Since chunk_literal_space() no longer
    # produces near-empty trailing windows, this can now only occur for a
    # single-window body shorter than window_size, or for a genuinely
    # degenerate full-size window. Division by zero is deliberately
    # guarded here and produces NaN rather than raising --
    # classify_window_validity() records why, and
    # sanitize_window_for_json() converts it to a JSON-safe null before
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

    Partial-body scoring policy (simplified 2026-07-23)
    ------------------------------------------------------
    A window's window_npr can be non-finite (see classify_window_validity()
    for the possible reasons). aggregate_weighted() always excludes
    non-finite windows from the token-weighted function_npr computation, so
    a body with at least one finite window still receives a valid, finite
    function_npr from the remaining window(s).

    Earlier revisions of this function tried to decide WHICH invalid window
    was acceptable to exclude (only a true, short "incomplete tail" window
    invalid for exactly one specific reason) versus which indicated a
    likely genuine model-scoring problem (any other window, or any other
    reason). That distinction existed only because a short trailing window
    was structurally common and needed to be told apart from a suspicious
    full-size window. Now that chunk_literal_space() never produces a short
    trailing window -- every window is always exactly window_size tokens,
    except a single window covering a whole body shorter than window_size
    -- an invalid window is equally uninterpretable regardless of its
    position or reason, so the position/reason-specific carve-out is no
    longer meaningful and has been removed.

    Current policy: a body succeeds, with partial_body_score=1, whenever at
    least one window is valid, using aggregate_weighted() over the valid
    window(s). Each valid window is weighted by the number of body tokens
    it covers that no earlier valid window covers
    (compute_aggregation_weights()), so a valid window overlapping an
    INVALID neighbor represents the shared tokens itself rather than
    having its weight capped at the static marginal_token_count. A body
    fails (AllWindowsInvalidNprError) only when every one of its windows
    is invalid, i.e. there is no scoreable signal left at all.
    """
    body_sha = str(row["function_body_sha256"])
    started = time.perf_counter()

    raw_chunks = chunk_literal_space(text, config.window_size)
    marginal_counts = compute_marginal_token_counts(raw_chunks)
    last_chunk_index = len(raw_chunks) - 1

    chunks_out: list[dict[str, Any]] = []
    for chunk_index, ((chunk_text, n_tokens, start, end), marginal_count) in enumerate(
        zip(raw_chunks, marginal_counts)
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
                "marginal_token_count": int(marginal_count),
                "window_seed": int(seed),
                "is_last_window": bool(chunk_index == last_chunk_index),
                # True exactly when chunk_literal_space() shifted this
                # (necessarily final) window backward to reach a full
                # window_size, i.e. it shares tokens with the previous
                # window. See chunk_literal_space()/
                # compute_marginal_token_counts().
                "overlaps_previous_window": bool(marginal_count < n_tokens),
                **scored,
                "window_npr_valid": bool(window_npr_valid),
                "window_npr_invalid_reason": window_npr_invalid_reason,
            }
        )

    invalid_chunks = [chunk for chunk in chunks_out if not chunk["window_npr_valid"]]

    # Aggregation weights can only be assigned after every window's
    # validity is known: each window's weight is the number of body tokens
    # it covers that no earlier VALID window covers (invalid windows get
    # 0). See compute_aggregation_weights() for why the static
    # marginal_token_count is the wrong weight in a partial body.
    aggregation_weights = compute_aggregation_weights(chunks_out)
    for chunk, weight in zip(chunks_out, aggregation_weights):
        chunk["aggregation_weight_token_count"] = int(weight)

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
    if not math.isfinite(function_npr):
        # Defensive: should be unreachable given the check above (at least
        # one window is finite whenever we reach this line), but kept so an
        # aggregation bug fails loudly instead of silently caching a
        # non-finite function-level score.
        raise RuntimeError("Function NPR is not finite despite at least one valid window.")

    agc_like = int(function_npr > config.agc_threshold)

    n_attempted_windows = len(chunks_out)
    n_invalid_npr_windows = len(invalid_chunks)
    n_valid_npr_windows = n_attempted_windows - n_invalid_npr_windows
    # Token-count audit fields (semantics revised together with
    # compute_aggregation_weights()):
    #   valid_npr_token_count   = body tokens covered by at least one VALID
    #                             window, each counted exactly once (the sum
    #                             of the aggregation weights).
    #   invalid_npr_token_count = body tokens with no valid signal at all,
    #                             i.e. covered only by invalid window(s).
    # The two always sum to the body's total literal-space token count.
    # (The earlier revision summed static marginal_token_count by validity
    # instead, which attributed a token to an invalid window even when a
    # later valid overlapping window had scored that same token.)
    total_body_tokens = int(raw_chunks[-1][3])
    valid_npr_token_count = int(sum(aggregation_weights))
    if not 0 <= valid_npr_token_count <= total_body_tokens:
        raise RuntimeError(
            "Token accounting invariant violated: aggregation weights sum to "
            f"{valid_npr_token_count} for a {total_body_tokens}-token body."
        )
    invalid_npr_token_count = total_body_tokens - valid_npr_token_count
    partial_body_score = int(bool(invalid_chunks))

    # Sanitize NaN-prone per-window fields (e.g. window_npr of an invalid
    # window) to None/JSON-null *after* aggregation, so the body-level
    # result -- which already has a valid, finite function_npr -- can be
    # written with atomic_json(..., allow_nan=False) without the whole body
    # being discarded.
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
            elapsed = max(time.perf_counter() - scoring_started, 1e-9)
            bodies_per_second = offset / elapsed
            remaining_bodies = total_pending - offset
            eta_seconds = remaining_bodies / bodies_per_second if bodies_per_second > 0 else math.nan
            eta_hours = eta_seconds / 3600 if math.isfinite(eta_seconds) else math.nan
            print(
                f"Progress: {offset}/{total_pending} pending bodies processed; "
                f"success_total={len(completed)}, failures_this_run={len(failures)}, "
                f"rate_bodies_per_hour={bodies_per_second * 3600:.3f}, "
                f"eta_hours={eta_hours:.2f}"
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
    """Record the full workload and measured progress without pilot extrapolation."""
    del calibration_profile_name, long_profile_name
    summary = profile_summary.loc[profile_summary["profile_name"] == "all_profiles"].iloc[0]
    spec = support.iloc[0]
    completed_windows = int(summary["scored_windows"])
    total_windows = int(spec["total_windows"])
    remaining_windows = max(0, total_windows - completed_windows)
    rate = sanitize_float(summary["measured_windows_per_second"])
    remaining_seconds = remaining_windows / rate if rate and rate > 0 else math.nan
    return pd.DataFrame([{
        "spec_name": spec["spec_name"],
        "eligible_unique_bodies": int(spec["eligible_unique_bodies"]),
        "total_windows": total_windows,
        "completed_windows": completed_windows,
        "remaining_windows": remaining_windows,
        "measured_windows_per_second": rate,
        "estimated_remaining_seconds": remaining_seconds,
        "estimated_remaining_hours": remaining_seconds / 3600 if math.isfinite(remaining_seconds) else math.nan,
        "progress_fraction": completed_windows / total_windows if total_windows else math.nan,
        "estimation_method": "current_full_run_measured_throughput",
    }])

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
    expected_bodies = int(profile_support.iloc[0]["eligible_unique_bodies"])
    expected_windows = int(profile_support.iloc[0]["total_windows"])
    checks.append(check_row("eligibility_specification_is_frozen", config.eligibility_status == "frozen", config.eligibility_status, "frozen"))
    checks.append(check_row("threshold_specification_is_frozen", config.threshold_status == "frozen", config.threshold_status, "frozen"))
    checks.append(check_row("selected_specification_matches", args.spec_name in {str(x.get("name")) for x in config.eligibility_specifications}, args.spec_name, "existing frozen specification"))
    checks.append(check_row("scoring_model_is_starcoder2_7b", config.scoring_model == "bigcode/starcoder2-7b", config.scoring_model, "bigcode/starcoder2-7b"))
    checks.append(check_row("window_size_is_128", config.window_size == 128, config.window_size, 128))
    checks.append(check_row("perturbations_per_window_is_50", config.perturbations_per_window == 50, config.perturbations_per_window, 50))
    selected_spec = find_spec(config, args.spec_name)
    selected_minimum = int(selected_spec["minimum_literal_space_tokens"])
    selected_maximum_raw = selected_spec.get("maximum_literal_space_tokens")
    selected_maximum = (
        None if selected_maximum_raw is None else int(selected_maximum_raw)
    )
    checks.append(check_row("gt200_is_primary_specification", config.specification_primary == GT200_SPEC_NAME, config.specification_primary, GT200_SPEC_NAME))
    checks.append(check_row("gt200_specification_count_is_one", len(config.eligibility_specifications) == 1, len(config.eligibility_specifications), 1))
    checks.append(check_row("gt200_role_is_primary_candidate", str(selected_spec.get("role")) == "primary_candidate", selected_spec.get("role"), "primary_candidate"))
    checks.append(check_row("gt200_minimum_is_201", selected_minimum == GT200_MINIMUM_LITERAL_SPACE_TOKENS, selected_minimum, GT200_MINIMUM_LITERAL_SPACE_TOKENS))
    checks.append(check_row("gt200_maximum_is_unbounded", selected_maximum is GT200_MAXIMUM_LITERAL_SPACE_TOKENS, selected_maximum, GT200_MAXIMUM_LITERAL_SPACE_TOKENS))
    checks.append(check_row("agc_threshold_matches", math.isclose(config.agc_threshold, EXPECTED_AGC_THRESHOLD, rel_tol=0.0, abs_tol=1e-12), config.agc_threshold, EXPECTED_AGC_THRESHOLD))
    checks.append(check_row("algorithm_version_matches", config.algorithm_version == EXPECTED_ALGORITHM_VERSION, config.algorithm_version, EXPECTED_ALGORITHM_VERSION))
    checks.append(check_row("aggregation_matches", config.function_aggregation == EXPECTED_FUNCTION_AGGREGATION, config.function_aggregation, EXPECTED_FUNCTION_AGGREGATION))
    checks.append(check_row("partial_body_policy_matches", config.partial_body_policy == EXPECTED_PARTIAL_BODY_POLICY, config.partial_body_policy, EXPECTED_PARTIAL_BODY_POLICY))
    checks.append(check_row("decision_rule_matches", config.decision_rule == EXPECTED_DECISION_RULE, config.decision_rule, EXPECTED_DECISION_RULE))
    checks.append(check_row("window_policy_matches", config.window_policy == EXPECTED_WINDOW_POLICY, config.window_policy, EXPECTED_WINDOW_POLICY))
    checks.append(check_row("selected_body_count", len(manifest) == expected_bodies, len(manifest), expected_bodies))
    checks.append(check_row("selected_body_hashes_unique", manifest["function_body_sha256"].is_unique, int(manifest["function_body_sha256"].duplicated().sum()), 0))
    checks.append(check_row("selected_window_count", int(manifest["n_expected_windows"].sum()) == expected_windows, int(manifest["n_expected_windows"].sum()), expected_windows))
    checks.append(check_row("selected_artifacts_valid", artifact_errors.empty, len(artifact_errors), 0))
    if not args.prepare_only:
        checks.append(check_row("completed_or_failed_body_count", len(body_scores) + len(failures) == expected_bodies, len(body_scores) + len(failures), expected_bodies))
        checks.append(check_row("successful_body_count", len(body_scores) == expected_bodies, len(body_scores), expected_bodies))
        checks.append(check_row("failed_body_count", failures.empty, len(failures), 0))
        checks.append(check_row("scored_window_count", len(window_scores) == expected_windows, len(window_scores), expected_windows))
        if not body_scores.empty:
            fnpr = pd.to_numeric(body_scores["function_npr"], errors="coerce").to_numpy(dtype=float)
            checks.append(check_row("all_function_npr_values_are_finite", bool(np.isfinite(fnpr).all()), int((~np.isfinite(fnpr)).sum()), 0))
            arithmetic = int(pd.to_numeric(body_scores["agc_like"], errors="coerce").sum() + pd.to_numeric(body_scores["hwc_like"], errors="coerce").sum())
            checks.append(check_row("agc_hwc_body_arithmetic", arithmetic == len(body_scores), arithmetic, len(body_scores)))
        if not window_scores.empty:
            invalid_with_weight = window_scores.loc[(~window_scores["window_npr_valid"].astype(bool)) & (pd.to_numeric(window_scores["aggregation_weight_token_count"], errors="coerce").fillna(0) > 0)]
            checks.append(check_row("invalid_windows_have_zero_aggregation_weight", invalid_with_weight.empty, len(invalid_with_weight), 0))
            overlap_not_last = window_scores.loc[window_scores["overlaps_previous_window"].astype(bool) & ~window_scores["is_last_window"].astype(bool)]
            checks.append(check_row("overlap_only_on_final_window", overlap_not_last.empty, len(overlap_not_last), 0))
        if args.reproducibility_check_per_profile > 0:
            checks.append(check_row("same_seed_reproducibility", bool(reproducibility["passed"].astype(bool).all()) if len(reproducibility) else False, int((~reproducibility["passed"].astype(bool)).sum()) if len(reproducibility) else 1, 0))
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
    atomic_csv(manifest, paths.output_dir / "commit_function_npr_full_manifest.csv")
    atomic_csv(profile_support, paths.output_dir / "commit_function_npr_full_spec_support.csv")
    atomic_csv(body_scores, paths.output_dir / "commit_function_npr_body_scores.csv", BODY_SCORE_COLUMNS)
    atomic_csv(window_scores, paths.output_dir / "commit_function_npr_window_scores.csv", WINDOW_SCORE_COLUMNS)
    atomic_csv(failures, paths.output_dir / "commit_function_npr_failures.csv", FAILURE_COLUMNS)
    atomic_csv(checkpoints, paths.output_dir / "commit_function_npr_checkpoint_index.csv")
    atomic_csv(profile_summary, paths.output_dir / "commit_function_npr_runtime_metrics.csv")
    atomic_csv(estimates, paths.output_dir / "commit_function_npr_full_progress_estimates.csv")
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
        input_eligibility_specification=args.input_eligibility_specification,
        input_threshold_specification=args.input_threshold_specification,
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

    config = load_detector_config(
        paths.input_eligibility_specification,
        paths.input_threshold_specification,
    )
    validate_gt200_detector_configuration(config, args.spec_name)

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
            "num_shards": int(args.num_shards),
            "shard_index": int(args.shard_index),
            "max_bodies_per_shard": args.max_bodies_per_shard,
            "global_eligible_unique_bodies": int(profile_support.iloc[0]["global_eligible_unique_bodies"]),
            "global_expected_windows": int(profile_support.iloc[0]["global_total_windows"]),
        }
        metadata = {
            "analysis_stage": "run-1d-full-npr-scoring",
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
        args.profile_name,
        args.profile_name,
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
        "selected_spec_name": args.spec_name,
        "full_profile_selected": int((manifest["profile_name"] == args.profile_name).sum()),
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
        "eligibility_specification_status": config.eligibility_status,
        "threshold_specification_status": config.threshold_status,
        "agc_threshold": config.agc_threshold,
        "algorithm_version": config.algorithm_version,
        "calibration_auroc": config.calibration_auroc,
        "specification_input_primary": config.specification_primary,
        "selected_specification": args.spec_name,
        "full_run_uses_selected_specification": True,
        "num_shards": int(args.num_shards),
        "shard_index": int(args.shard_index),
        "max_bodies_per_shard": args.max_bodies_per_shard,
        "global_eligible_unique_bodies": int(profile_support.iloc[0]["global_eligible_unique_bodies"]),
        "global_expected_windows": int(profile_support.iloc[0]["global_total_windows"]),
    }
    input_hashes = {
        "input_unique_bodies_sha256": sha256_file(paths.input_unique_bodies),
        "input_events_sha256": sha256_file(paths.input_events),
        "input_panel_sha256": sha256_file(paths.input_panel),
        "input_support_sha256": sha256_file(paths.input_support),
        "input_eligibility_specification_sha256": sha256_file(paths.input_eligibility_specification),
        "input_threshold_specification_sha256": sha256_file(paths.input_threshold_specification),
    }
    metadata = {
        "status": status,
        "analysis_stage": "run-1d-full-npr-scoring",
        "script_version": SCRIPT_VERSION,
        "invocation_started_utc": invocation_started_utc,
        "invocation_completed_utc": utc_now(),
        "paths": {
            "input_unique_bodies": str(paths.input_unique_bodies.resolve()),
            "input_events": str(paths.input_events.resolve()),
            "input_panel": str(paths.input_panel.resolve()),
            "input_support": str(paths.input_support.resolve()),
            "input_eligibility_specification": str(paths.input_eligibility_specification.resolve()),
            "input_threshold_specification": str(paths.input_threshold_specification.resolve()),
            "body_artifact_base": str(paths.body_artifact_base.resolve()),
            "output_dir": str(paths.output_dir.resolve()),
            "qc_dir": str(paths.qc_dir.resolve()),
            "cache_dir": str(paths.cache_dir.resolve()),
        },
        "input_hashes": input_hashes,
        "config_fingerprint": fingerprint,
        "detector_configuration": config.fingerprint_payload(profile_definition),
        "sharding": {
            "assignment": "sha256_sorted_round_robin",
            "num_shards": int(args.num_shards),
            "shard_index": int(args.shard_index),
            "max_bodies_per_shard": args.max_bodies_per_shard,
            "global_eligible_unique_bodies": int(profile_support.iloc[0]["global_eligible_unique_bodies"]),
            "global_expected_windows": int(profile_support.iloc[0]["global_total_windows"]),
        },
        "package_and_gpu_metadata": package_info,
        "column_semantics": {
            "n_scored_windows": "Windows for which model scoring was attempted.",
            "n_valid_npr_windows": "Attempted windows that produced a finite NPR value.",
            "n_invalid_npr_windows": "Attempted windows whose NPR value was undefined.",
            "partial_body_score": (
                "1 when one or more windows were excluded because their NPR was invalid, "
                "while at least one valid window remained for function-level aggregation."
            ),
        },
        "operational_note": (
            "This full run scores every unique body in the selected frozen eligibility specification. "
            "It does not aggregate repository-month outcomes or run DiD."
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
        "num_shards": int(args.num_shards),
        "shard_index": int(args.shard_index),
    }
    append_jsonl(history_record, paths.qc_dir / "commit_function_npr_run_history.jsonl")

    print("=" * 76)
    print("Run full commit-function NPR scoring")
    print(f"Status:                         {status}")
    print(f"Selected full-run bodies:         {len(manifest)}")
    print(f"Successful unique bodies:       {len(body_scores)}")
    print(f"Failed unique bodies:           {len(failures)}")
    print(f"Expected windows:               {int(manifest['n_expected_windows'].sum())}")
    print(f"Scored windows:                 {len(window_scores)}")
    print(f"Bodies scored this run:         {bodies_scored_this_run}")
    print(f"Bodies reused this run:         {bodies_reused_this_run}")
    print(f"Model loaded this run:          {int(runtime is not None)}")
    print(f"Resume validation passed:       {int(resume_validation_passed)}")
    print(f"Shard:                          {args.shard_index}/{args.num_shards}")
    print(f"Global eligible bodies:         {int(profile_support.iloc[0]['global_eligible_unique_bodies'])}")
    print(f"Global expected windows:        {int(profile_support.iloc[0]['global_total_windows'])}")
    print(f"Failed checks:                  {failed_checks}")
    print(f"Output directory:               {paths.output_dir}")
    print(f"QC directory:                   {paths.qc_dir}")
    print("=" * 76)
    return 0 if status in {"PASS", "PREPARED_ONLY"} else 5


def make_self_test_inputs(root: Path) -> argparse.Namespace:
    run1a = root / "run-1a" / "strict"
    bodies_dir = run1a / "function_bodies"
    run1b = root / "run-1b" / "strict"
    output = root / "run-1d" / "full"
    bodies_dir.mkdir(parents=True, exist_ok=True)
    run1b.mkdir(parents=True, exist_ok=True)

    ineligible_tokens = [199, 200]
    gt200_tokens = list(range(201, 221))
    token_counts = ineligible_tokens + gt200_tokens
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
    eligibility_spec_path = run1b / "commit_function_detectcodegpt_scoring_spec.json"
    threshold_spec_path = run1b / "mixedcode_overlap_threshold_specification.json"
    pd.DataFrame(unique_rows).to_csv(unique_path, index=False)
    pd.DataFrame(event_rows).to_csv(events_path, index=False)
    pd.DataFrame(panel_rows).drop_duplicates().to_csv(panel_path, index=False)
    pd.DataFrame(
        [
            {
                "spec_name": "gt200",
                "eligible_unique_bodies": 20,
                "total_windows": sum(math.ceil(value / 128) for value in gt200_tokens),
                "total_scoring_sequences": sum(math.ceil(value / 128) for value in gt200_tokens) * 51,
            },
        ]
    ).to_csv(support_path, index=False)
    atomic_json(
        {
            "status": "frozen",
            "primary_spec": "gt200",
            "scoring_model": "bigcode/starcoder2-7b",
            "window_size_literal_space_tokens": 128,
            "perturbations_per_window": 50,
            "perturbation_type": "random-insert-space+newline",
            "function_aggregation": "token-weighted mean",
            "agc_threshold": 1.5183,
            "random_seed": 20260723,
            "eligibility_specifications": [
                {
                    "name": "gt200",
                    "role": "primary_candidate",
                    "minimum_literal_space_tokens": 201,
                    "maximum_literal_space_tokens": None,
                },
            ],
        },
        eligibility_spec_path,
    )
    atomic_json(
        {
            "status": "frozen",
            "scoring_model": "bigcode/starcoder2-7b",
            "window_size_literal_space_tokens": 128,
            "perturbations_per_window": 50,
            "perturbation_type": "random-insert-space+newline",
            "function_aggregation": "valid_frontier_weighted_mean",
            "agc_threshold": 1.571637,
            "random_seed": 20260723,
            "algorithm_version": "overlap_final_full_window_valid_frontier_weighting-v1",
            "decision_rule": "function_npr > agc_threshold",
            "window_policy": "full_size_final_window_shifted_backward_with_overlap",
            "partial_body_policy": PARTIAL_BODY_POLICY,
            "threshold_calibration_dataset": "table2_mixedcode_50_files_300_bodies",
            "benchmark_bodies": 300,
            "overall_auroc": 0.9132888888888889,
        },
        threshold_spec_path,
    )

    return argparse.Namespace(
        input_unique_bodies=unique_path,
        input_events=events_path,
        input_panel=panel_path,
        input_support=support_path,
        input_eligibility_specification=eligibility_spec_path,
        input_threshold_specification=threshold_spec_path,
        body_artifact_base=run1a,
        output_dir=output,
        qc_dir=None,
        cache_dir=None,
        spec_name="gt200",
        profile_name="gt200_full",
        device="cuda",
        model_cache_dir=Path("~/.cache/huggingface/hub").expanduser(),
        detector_output_name="run1d_gt200_v2_self_test",
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
        num_shards=1,
        shard_index=0,
        max_bodies_per_shard=None,
        merge_shards=False,
        shard_root=None,
        allow_partial_shards=False,
    )


def _test_chunk_literal_space_and_marginal_counts() -> None:
    """Directly verify chunk_literal_space()'s overlap-shifting behavior and
    compute_marginal_token_counts()'s frontier-tracking arithmetic, using
    the exact examples worked through with the user: a 3-token body one
    token past a window_size=2 boundary (produces overlap, analogous to a
    129-token body with window_size=128), and a 4-token body an exact
    multiple of window_size=2 (no overlap, analogous to a 256-token body).
    """
    # 3 tokens, window_size=2 -> the final window is shifted back to reach
    # a full 2 tokens, overlapping the first window's second token.
    chunks = chunk_literal_space("a b c", window_size=2)
    if len(chunks) != 2:
        raise AssertionError(f"Expected 2 windows for 3 tokens/window_size=2, got: {chunks}")
    (_, n0, s0, e0), (_, n1, s1, e1) = chunks
    if (n0, s0, e0) != (2, 0, 2):
        raise AssertionError(f"Window 0 should be tokens[0:2], got n={n0} s={s0} e={e0}")
    if (n1, s1, e1) != (2, 1, 3):
        raise AssertionError(
            "Window 1 should be shifted back to tokens[1:3] (full window_size, "
            f"overlapping window 0), got n={n1} s={s1} e={e1}"
        )
    marginals = compute_marginal_token_counts(chunks)
    if marginals != [2, 1]:
        raise AssertionError(f"Expected marginal counts [2, 1], got {marginals}")
    if sum(marginals) != 3:
        raise AssertionError("Marginal counts must sum to the body's total token count")

    # 4 tokens, window_size=2 -> exact multiple, no overlap or shifting.
    exact_chunks = chunk_literal_space("a b c d", window_size=2)
    if exact_chunks != [("a b", 2, 0, 2), ("c d", 2, 2, 4)]:
        raise AssertionError(f"Exact-multiple body must produce two non-overlapping full windows, got: {exact_chunks}")
    exact_marginals = compute_marginal_token_counts(exact_chunks)
    if exact_marginals != [2, 2]:
        raise AssertionError(f"Exact-multiple body must have no overlap (marginals == window sizes), got {exact_marginals}")

    # Body shorter than window_size -> single, unshifted window (unchanged
    # from the pre-redesign behavior; a short whole body is not a windowing
    # artifact).
    short_chunks = chunk_literal_space("a b", window_size=5)
    if short_chunks != [("a b", 2, 0, 2)]:
        raise AssertionError(f"Body shorter than window_size must be a single, unshifted window: {short_chunks}")
    if compute_marginal_token_counts(short_chunks) != [2]:
        raise AssertionError("Single-window body's marginal count must equal its own token count")

    # compute_aggregation_weights(): identical to the static marginals when
    # every window is valid, and reassigns an invalid window's coverage to
    # a later valid overlapping window when one exists.
    def _weight_stub(start: int, end: int, valid: bool) -> dict[str, Any]:
        return {
            "start_token_body": start,
            "end_token_body": end,
            "window_npr_valid": valid,
        }

    # All valid, with overlap ([0:2] + [1:3]) -> weights equal marginals.
    all_valid = [_weight_stub(0, 2, True), _weight_stub(1, 3, True)]
    if compute_aggregation_weights(all_valid) != [2, 1]:
        raise AssertionError("All-valid weights must equal the static marginal counts")

    # First window invalid, overlapping second valid -> the second window
    # represents ALL of its own tokens, not just the static marginal 1.
    first_invalid = [_weight_stub(0, 2, False), _weight_stub(1, 3, True)]
    if compute_aggregation_weights(first_invalid) != [0, 2]:
        raise AssertionError("A valid window overlapping an invalid one must carry its full uncovered span")

    # Middle window invalid in a 3-window overlapping body ([0:2],[2:4],
    # [3:5]): the final valid window expands from static marginal 1 to 2,
    # and exactly one token (index 2) is left with no valid signal.
    middle_invalid = [
        _weight_stub(0, 2, True),
        _weight_stub(2, 4, False),
        _weight_stub(3, 5, True),
    ]
    if compute_aggregation_weights(middle_invalid) != [2, 0, 2]:
        raise AssertionError("Middle-invalid weights must be [2, 0, 2]")

    # All invalid -> all-zero weights (score_one_body() raises before
    # aggregation can matter, but the function must stay well-defined).
    all_invalid = [_weight_stub(0, 2, False), _weight_stub(1, 3, False)]
    if compute_aggregation_weights(all_invalid) != [0, 0]:
        raise AssertionError("All-invalid weights must be all zero")

    print("chunk_literal_space / compute_marginal_token_counts self-test: PASS")


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


def _make_policy_test_row(
    body_sha: str, n_expected_windows: int, token_count: int = 3
) -> pd.Series:
    return pd.Series(
        {
            "profile_name": "unit_test_profile",
            "stratum_name": "unit_test_stratum",
            "sample_rank": 1,
            "function_body_sha256": body_sha,
            "function_body_relative_path": "unused.txt",
            "function_body_split_space_token_count": token_count,
            "n_expected_windows": n_expected_windows,
            "referencing_function_event_count": 1,
        }
    )


def run_partial_body_policy_self_test() -> None:
    """Directly unit-test score_one_body()'s simplified partial-body
    scoring policy (Cases 1-6) and the null-safe reproducibility comparison
    (Case 7), using a scripted score_window callable instead of real or
    mock model scoring. See score_one_body(), classify_window_validity(),
    chunk_literal_space(), and compare_results() for the behavior under
    test.
    """
    _test_chunk_literal_space_and_marginal_counts()

    config = DetectorConfig(
        eligibility_status="frozen",
        specification_primary="unit_test",
        threshold_status="frozen",
        scoring_model="bigcode/starcoder2-7b",
        window_size=2,
        perturbations_per_window=50,
        perturbation_type="random-insert-space+newline",
        function_aggregation="valid_frontier_weighted_mean",
        agc_threshold=1.571637,
        random_seed=20260723,
        algorithm_version="overlap_final_full_window_valid_frontier_weighting-v1",
        decision_rule="function_npr > agc_threshold",
        window_policy="full_size_final_window_shifted_backward_with_overlap",
        partial_body_policy=PARTIAL_BODY_POLICY,
        calibration_dataset="table2_mixedcode_50_files_300_bodies",
        calibration_bodies=300,
        calibration_auroc=0.9132888888888889,
        eligibility_specification_sha256="self-test-eligibility",
        threshold_specification_sha256="self-test-threshold",
        eligibility_specifications=(),
    )
    # chunk_literal_space("a b c", window_size=2) -> window 0 = tokens[0:2]
    # ("a b", marginal=2), window 1 = tokens[1:3] ("b c", marginal=1,
    # overlapping window 0's second token). This is the same shape as a
    # 129-token body with window_size=128.
    overlap_text = "a b c"
    # chunk_literal_space("a b c d", window_size=2) -> two full,
    # non-overlapping windows (exact multiple of window_size).
    exact_multiple_text = "a b c d"

    # Case 1: every window valid -> ordinary success, no partial-body flag,
    # and function_npr is the marginal-weighted mean (2*1.1 + 1*1.7) / 3,
    # not the naive (2*1.1 + 2*1.7) / 4 that double-counting would give.
    row = _make_policy_test_row("case1", 2)
    result = score_one_body(
        row, overlap_text, config, "fp",
        _scripted_score_window([_valid_window_response(1.1), _valid_window_response(1.7)]),
        None,
    )
    if result["partial_body_score"] != 0 or result["n_invalid_npr_windows"] != 0:
        raise AssertionError(f"Case 1 (all valid) unexpectedly marked as partial: {result}")
    expected_npr = (1.1 * 2 + 1.7 * 1) / 3
    if abs(result["function_npr"] - expected_npr) > 1e-9:
        raise AssertionError(
            f"Case 1 function_npr should be the marginal-weighted mean "
            f"{expected_npr}, got {result['function_npr']}"
        )
    if result["chunks"][0]["marginal_token_count"] != 2 or result["chunks"][1]["marginal_token_count"] != 1:
        raise AssertionError(f"Case 1 marginal_token_count values wrong: {result['chunks']}")
    if result["chunks"][0]["overlaps_previous_window"] is not False:
        raise AssertionError("Case 1 window 0 must not be marked as overlapping")
    if result["chunks"][1]["overlaps_previous_window"] is not True:
        raise AssertionError("Case 1 window 1 (shifted tail) must be marked as overlapping")

    # Case 2: the overlapping (shifted) tail window is invalid -> partial
    # success, function_npr computed from window 0 alone (its own npr,
    # since it is the only valid window and thus carries the full weight).
    row = _make_policy_test_row("case2", 2)
    result = score_one_body(
        row, overlap_text, config, "fp",
        _scripted_score_window(
            [_valid_window_response(1.1), _degenerate_window_response("zero_original_log_rank")]
        ),
        None,
    )
    if result["partial_body_score"] != 1:
        raise AssertionError(f"Case 2 (overlapping tail invalid) must be a partial success: {result}")
    if result["n_valid_npr_windows"] != 1 or result["n_invalid_npr_windows"] != 1:
        raise AssertionError(f"Case 2 valid/invalid window counts wrong: {result}")
    if abs(result["function_npr"] - 1.1) > 1e-9:
        raise AssertionError(f"Case 2 function_npr should equal window 0's own npr (1.1), got {result['function_npr']}")
    if [chunk["aggregation_weight_token_count"] for chunk in result["chunks"]] != [2, 0]:
        raise AssertionError(f"Case 2 aggregation weights must be [2, 0]: {result['chunks']}")
    if result["valid_npr_token_count"] != 2 or result["invalid_npr_token_count"] != 1:
        raise AssertionError(
            "Case 2 token accounting must be valid=2 (window 0's coverage), "
            f"invalid=1 (token 2, covered only by the invalid window): {result}"
        )
    tail_chunk = result["chunks"][1]
    if tail_chunk["window_npr"] is not None:
        raise AssertionError("Case 2 tail window_npr must be sanitized to None, not left as NaN")
    if tail_chunk["window_npr_valid"] is not False or tail_chunk["window_npr_invalid_reason"] != "zero_original_log_rank":
        raise AssertionError(f"Case 2 tail window validity/reason wrong: {tail_chunk}")
    case2_result = result  # reused for the Case 7 reproducibility check below

    # Case 3: every window invalid -> body failure (AllWindowsInvalidNprError),
    # the only remaining failure condition.
    row = _make_policy_test_row("case3", 2)
    try:
        score_one_body(
            row, overlap_text, config, "fp",
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

    # Case 4 (policy change from the pre-redesign behavior): the *first*,
    # non-overlapping window is invalid and the overlapping tail window is
    # valid -> now ALSO a partial success, since position no longer matters
    # once short trailing windows cannot occur. Previously this raised
    # NonTailWindowInvalidNprError; that exception no longer exists.
    row = _make_policy_test_row("case4", 2)
    result = score_one_body(
        row, overlap_text, config, "fp",
        _scripted_score_window(
            [_degenerate_window_response("zero_original_log_rank"), _valid_window_response(1.4)]
        ),
        None,
    )
    if result["partial_body_score"] != 1:
        raise AssertionError(f"Case 4 (first window invalid) must be a partial success under the simplified policy: {result}")
    if abs(result["function_npr"] - 1.4) > 1e-9:
        raise AssertionError(f"Case 4 function_npr should equal window 1's own npr (1.4), got {result['function_npr']}")
    # Weight reassignment (compute_aggregation_weights()): the valid
    # overlapping window represents its FULL uncovered span (2 tokens),
    # not its static marginal of 1, because the earlier window covering
    # token 1 is invalid. Token accounting follows: only token 0 has no
    # valid signal.
    if [chunk["aggregation_weight_token_count"] for chunk in result["chunks"]] != [0, 2]:
        raise AssertionError(f"Case 4 aggregation weights must be [0, 2]: {result['chunks']}")
    if result["valid_npr_token_count"] != 2 or result["invalid_npr_token_count"] != 1:
        raise AssertionError(f"Case 4 token accounting must be valid=2, invalid=1: {result}")

    # Case 4b (the quantitative reason aggregation weights exist at all):
    # a 5-token body with window_size=2 produces windows [0:2], [2:4],
    # [3:5] (static marginals [2, 2, 1]). With the MIDDLE window invalid
    # and both outer windows valid, static-marginal weighting would give
    # (1.0*2 + 2.0*1) / 3 = 4/3, treating the final window as worth one
    # token even though it validly scored tokens 3-4 and no other valid
    # window covers them. Frontier-over-valid weighting gives the final
    # window weight 2: (1.0*2 + 2.0*2) / 4 = 1.5, with exactly one token
    # (index 2) carrying no valid signal. At production scale
    # (window_size=128, second-to-last window invalid) this same
    # difference moves function_npr across the calibrated threshold region,
    # so it is asserted here exactly.
    row = _make_policy_test_row("case4b", 3, token_count=5)
    result = score_one_body(
        row, "a b c d e", config, "fp",
        _scripted_score_window(
            [
                _valid_window_response(1.0),
                _degenerate_window_response("zero_original_log_rank"),
                _valid_window_response(2.0),
            ]
        ),
        None,
    )
    if result["partial_body_score"] != 1:
        raise AssertionError(f"Case 4b (middle window invalid) must be a partial success: {result}")
    if [chunk["aggregation_weight_token_count"] for chunk in result["chunks"]] != [2, 0, 2]:
        raise AssertionError(f"Case 4b aggregation weights must be [2, 0, 2]: {result['chunks']}")
    expected_npr_4b = (1.0 * 2 + 2.0 * 2) / 4
    if abs(result["function_npr"] - expected_npr_4b) > 1e-9:
        raise AssertionError(
            f"Case 4b function_npr must be the valid-frontier weighted mean "
            f"{expected_npr_4b} (NOT the static-marginal 4/3): got {result['function_npr']}"
        )
    if result["valid_npr_token_count"] != 4 or result["invalid_npr_token_count"] != 1:
        raise AssertionError(f"Case 4b token accounting must be valid=4, invalid=1: {result}")
    if [chunk["marginal_token_count"] for chunk in result["chunks"]] != [2, 2, 1]:
        raise AssertionError(
            f"Case 4b static marginals must remain [2, 2, 1] (unchanged by validity): {result['chunks']}"
        )

    # Case 5 (policy change): an exact-multiple body (no overlap at all) has
    # its final, full-size window invalid -> now ALSO a partial success.
    # Previously a full-size final window could never be treated as a
    # benign tail and this raised NonTailWindowInvalidNprError; that
    # exception no longer exists because full-size-vs-tail is no longer a
    # distinction the policy makes.
    row = _make_policy_test_row("case5", 2, token_count=4)
    result = score_one_body(
        row, exact_multiple_text, config, "fp",
        _scripted_score_window(
            [_valid_window_response(1.1), _degenerate_window_response("zero_original_log_rank")]
        ),
        None,
    )
    if result["partial_body_score"] != 1:
        raise AssertionError(f"Case 5 (exact-multiple body, final window invalid) must be a partial success: {result}")
    if abs(result["function_npr"] - 1.1) > 1e-9:
        raise AssertionError(f"Case 5 function_npr should equal window 0's own npr (1.1), got {result['function_npr']}")
    if [chunk["aggregation_weight_token_count"] for chunk in result["chunks"]] != [2, 0]:
        raise AssertionError(f"Case 5 aggregation weights must be [2, 0]: {result['chunks']}")
    if result["valid_npr_token_count"] != 2 or result["invalid_npr_token_count"] != 2:
        raise AssertionError(
            "Case 5 token accounting must be valid=2, invalid=2 (no overlap, so the "
            f"invalid window's tokens have no valid signal): {result}"
        )

    # Case 6 (policy change): the overlapping tail window is invalid for
    # "no_valid_perturbation_scores" rather than "zero_original_log_rank"
    # -> now ALSO a partial success, since the invalid reason is no longer
    # restricted. Previously this raised DisallowedTailWindowInvalidNprError;
    # that exception no longer exists.
    row = _make_policy_test_row("case6", 2)
    result = score_one_body(
        row, overlap_text, config, "fp",
        _scripted_score_window(
            [_valid_window_response(1.1), _degenerate_window_response("no_valid_perturbation_scores")]
        ),
        None,
    )
    if result["partial_body_score"] != 1:
        raise AssertionError(f"Case 6 (disallowed-reason tail invalid) must now be a partial success: {result}")
    if result["chunks"][1]["window_npr_invalid_reason"] != "no_valid_perturbation_scores":
        raise AssertionError(f"Case 6 invalid reason not recorded correctly: {result['chunks'][1]}")

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
    with tempfile.TemporaryDirectory(prefix="run1d-gt200-v2-self-test-") as tmp:
        root = Path(tmp)
        run_partial_body_policy_self_test()

        first = make_self_test_inputs(root)
        exit_code = run_analysis(first)
        if exit_code != 0:
            raise RuntimeError(f"First self-test run failed with exit code {exit_code}")
        summary_path = first.output_dir / "qc" / "commit_function_npr_summary.json"
        with summary_path.open("r", encoding="utf-8") as stream:
            summary = json.load(stream)
        if summary["status"] != "PASS" or summary["successful_unique_bodies"] != 20:
            raise RuntimeError(f"Unexpected first-run self-test summary: {summary}")
        manifest = pd.read_csv(
            first.output_dir / "commit_function_npr_full_manifest.csv",
            low_memory=False,
        )
        selected_tokens = pd.to_numeric(
            manifest["function_body_split_space_token_count"],
            errors="raise",
        ).astype(int)
        if (
            len(manifest) != 20
            or int(selected_tokens.min()) != 201
            or int(selected_tokens.max()) != 220
            or bool(selected_tokens.lt(201).any())
        ):
            raise RuntimeError(
                "gt200 boundary self-test failed: expected exactly the "
                f"201-220 token fixtures, observed {sorted(selected_tokens.tolist())}."
            )

        with first.input_threshold_specification.open(
            "r", encoding="utf-8"
        ) as stream:
            drifted_threshold = json.load(stream)
        drifted_threshold["agc_threshold"] = 1.5
        drifted_path = root / "drifted_threshold_specification.json"
        atomic_json(drifted_threshold, drifted_path)
        drifted_config = load_detector_config(
            first.input_eligibility_specification,
            drifted_path,
        )
        try:
            validate_gt200_detector_configuration(
                drifted_config,
                first.spec_name,
            )
        except ValueError as exc:
            if "agc_threshold" not in str(exc):
                raise RuntimeError(
                    "Threshold-drift guard raised an unexpected error."
                ) from exc
        else:
            raise RuntimeError(
                "Threshold-drift guard accepted agc_threshold=1.5."
            )

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
        if resumed["bodies_scored_this_run"] != 0 or resumed["bodies_reused_this_run"] != 20:
            raise RuntimeError(f"Unexpected resume counts: {resumed}")

        shard_root = root / "run-1d" / "shards"
        for shard_index in range(3):
            shard_args = argparse.Namespace(**vars(make_self_test_inputs(root)))
            shard_args.output_dir = shard_root / f"shard-{shard_index:03d}-of-003"
            shard_args.qc_dir = shard_args.output_dir / "qc"
            shard_args.cache_dir = shard_args.output_dir / "cache"
            shard_args.num_shards = 3
            shard_args.shard_index = shard_index
            if run_analysis(shard_args) != 0:
                raise RuntimeError(f"Shard self-test failed for shard {shard_index}.")

        merge_args = argparse.Namespace(**vars(make_self_test_inputs(root)))
        merge_args.merge_shards = True
        merge_args.shard_root = shard_root
        merge_args.output_dir = root / "run-1d" / "merged"
        merge_args.qc_dir = merge_args.output_dir / "qc"
        merge_args.cache_dir = merge_args.output_dir / "cache"
        merge_args.num_shards = 3
        merge_args.shard_index = 0
        merge_args.overwrite_output = True
        if merge_shard_outputs(merge_args) != 0:
            raise RuntimeError("Shard merge self-test failed.")
        with (merge_args.qc_dir / "commit_function_npr_summary.json").open(
            "r", encoding="utf-8"
        ) as stream:
            merged = json.load(stream)
        if (
            merged["status"] != "PASS"
            or merged["selected_unique_bodies"] != 20
            or merged["duplicate_body_hashes"] != 0
        ):
            raise RuntimeError(f"Unexpected shard merge summary: {merged}")
        print("Self-test: PASS")


def _read_shard_csv(path: Path, columns: Sequence[str] | None = None) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Missing shard output: {path}")
    frame = pd.read_csv(path, low_memory=False)
    if columns is not None:
        for column in columns:
            if column not in frame.columns:
                frame[column] = pd.Series(dtype="object")
        frame = frame[list(columns)]
    return frame


def merge_shard_outputs(args: argparse.Namespace) -> int:
    """Merge independently written shard directories and verify exact coverage."""
    started = time.perf_counter()
    shard_root = args.shard_root
    output_dir = args.output_dir
    qc_dir = args.qc_dir or output_dir / "qc"
    if args.overwrite_output and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    qc_dir.mkdir(parents=True, exist_ok=True)

    config = load_detector_config(
        args.input_eligibility_specification,
        args.input_threshold_specification,
    )
    selected_spec = validate_gt200_detector_configuration(config, args.spec_name)

    manifests: list[pd.DataFrame] = []
    body_parts: list[pd.DataFrame] = []
    window_parts: list[pd.DataFrame] = []
    failure_parts: list[pd.DataFrame] = []
    checkpoint_parts: list[pd.DataFrame] = []
    artifact_parts: list[pd.DataFrame] = []
    repro_parts: list[pd.DataFrame] = []
    shard_summaries: list[dict[str, Any]] = []
    shard_metadata: list[dict[str, Any]] = []

    for shard_index in range(args.num_shards):
        shard_dir = shard_root / f"shard-{shard_index:03d}-of-{args.num_shards:03d}"
        shard_qc = shard_dir / "qc"
        summary_path = shard_qc / "commit_function_npr_summary.json"
        metadata_path = shard_qc / "commit_function_npr_metadata.json"
        if not summary_path.is_file() or not metadata_path.is_file():
            raise FileNotFoundError(f"Missing summary or metadata for shard {shard_index}: {shard_dir}")
        with summary_path.open("r", encoding="utf-8") as stream:
            summary = json.load(stream)
        with metadata_path.open("r", encoding="utf-8") as stream:
            metadata = json.load(stream)
        if int(summary.get("num_shards", -1)) != args.num_shards:
            raise ValueError(f"Shard {shard_index} reports an unexpected num_shards value.")
        if int(summary.get("shard_index", -1)) != shard_index:
            raise ValueError(f"Shard directory/index mismatch for shard {shard_index}.")
        shard_summaries.append(summary)
        shard_metadata.append(metadata)
        manifests.append(_read_shard_csv(shard_dir / "commit_function_npr_full_manifest.csv"))
        body_parts.append(_read_shard_csv(shard_dir / "commit_function_npr_body_scores.csv", BODY_SCORE_COLUMNS))
        window_parts.append(_read_shard_csv(shard_dir / "commit_function_npr_window_scores.csv", WINDOW_SCORE_COLUMNS))
        failure_parts.append(_read_shard_csv(shard_dir / "commit_function_npr_failures.csv", FAILURE_COLUMNS))
        checkpoint_parts.append(_read_shard_csv(shard_dir / "commit_function_npr_checkpoint_index.csv"))
        artifact_parts.append(_read_shard_csv(shard_qc / "commit_function_npr_artifact_errors.csv", ARTIFACT_ERROR_COLUMNS))
        repro_parts.append(_read_shard_csv(shard_qc / "commit_function_npr_reproducibility_checks.csv", REPRO_COLUMNS))

    manifest = pd.concat(manifests, ignore_index=True).sort_values(
        ["sample_rank", "function_body_sha256"], kind="mergesort"
    )
    body_scores = pd.concat(body_parts, ignore_index=True)
    window_scores = pd.concat(window_parts, ignore_index=True)
    failures = pd.concat(failure_parts, ignore_index=True)
    checkpoints = pd.concat(checkpoint_parts, ignore_index=True)
    artifact_errors = pd.concat(artifact_parts, ignore_index=True)
    reproducibility = pd.concat(repro_parts, ignore_index=True)
    if not body_scores.empty:
        body_scores = body_scores.sort_values(["profile_name", "sample_rank"], kind="mergesort")
    if not window_scores.empty:
        window_scores = window_scores.sort_values(
            ["profile_name", "sample_rank", "chunk_index"], kind="mergesort"
        )

    run1b_support = pd.read_csv(args.input_support, low_memory=False)
    require_columns(run1b_support, SUPPORT_REQUIRED, "run-1b support")
    support_match = run1b_support.loc[run1b_support["spec_name"].astype(str).eq(args.spec_name)]
    if len(support_match) != 1:
        raise ValueError(
            f"Expected one run-1b support row for {args.spec_name!r}; found {len(support_match)}."
        )
    expected_global_bodies = int(support_match.iloc[0]["eligible_unique_bodies"])
    expected_global_windows = int(support_match.iloc[0]["total_windows"])
    merged_bodies = int(len(manifest))
    merged_windows = int(manifest["n_expected_windows"].sum())
    duplicate_bodies = int(manifest["function_body_sha256"].duplicated().sum())
    shard_statuses = [str(summary.get("status")) for summary in shard_summaries]
    prepared_only = all(status == "PREPARED_ONLY" for status in shard_statuses)
    scored_run = all(status == "PASS" for status in shard_statuses)
    fingerprints = {str(summary.get("config_fingerprint")) for summary in shard_summaries}

    expected_bodies_for_merge = merged_bodies if args.allow_partial_shards else expected_global_bodies
    expected_windows_for_merge = merged_windows if args.allow_partial_shards else expected_global_windows
    checks = pd.DataFrame(
        [
            check_row("all_shards_present", len(shard_summaries) == args.num_shards, len(shard_summaries), args.num_shards),
            check_row("all_shards_qc_passed", prepared_only or scored_run, shard_statuses, "all PASS or all PREPARED_ONLY"),
            check_row("shard_fingerprints_match", len(fingerprints) == 1, len(fingerprints), 1),
            check_row("gt200_is_primary_specification", config.specification_primary == GT200_SPEC_NAME, config.specification_primary, GT200_SPEC_NAME),
            check_row("gt200_specification_count_is_one", len(config.eligibility_specifications) == 1, len(config.eligibility_specifications), 1),
            check_row("gt200_role_is_primary_candidate", str(selected_spec.get("role")) == "primary_candidate", selected_spec.get("role"), "primary_candidate"),
            check_row("gt200_minimum_is_201", int(selected_spec["minimum_literal_space_tokens"]) == GT200_MINIMUM_LITERAL_SPACE_TOKENS, int(selected_spec["minimum_literal_space_tokens"]), GT200_MINIMUM_LITERAL_SPACE_TOKENS),
            check_row("gt200_maximum_is_unbounded", selected_spec.get("maximum_literal_space_tokens") is GT200_MAXIMUM_LITERAL_SPACE_TOKENS, selected_spec.get("maximum_literal_space_tokens"), GT200_MAXIMUM_LITERAL_SPACE_TOKENS),
            check_row("agc_threshold_matches", math.isclose(config.agc_threshold, EXPECTED_AGC_THRESHOLD, rel_tol=0.0, abs_tol=1e-12), config.agc_threshold, EXPECTED_AGC_THRESHOLD),
            check_row("algorithm_version_matches", config.algorithm_version == EXPECTED_ALGORITHM_VERSION, config.algorithm_version, EXPECTED_ALGORITHM_VERSION),
            check_row("aggregation_matches", config.function_aggregation == EXPECTED_FUNCTION_AGGREGATION, config.function_aggregation, EXPECTED_FUNCTION_AGGREGATION),
            check_row("window_policy_matches", config.window_policy == EXPECTED_WINDOW_POLICY, config.window_policy, EXPECTED_WINDOW_POLICY),
            check_row("partial_body_policy_matches", config.partial_body_policy == EXPECTED_PARTIAL_BODY_POLICY, config.partial_body_policy, EXPECTED_PARTIAL_BODY_POLICY),
            check_row("merged_body_hashes_unique", duplicate_bodies == 0, duplicate_bodies, 0),
            check_row("merged_body_count", merged_bodies == expected_bodies_for_merge, merged_bodies, expected_bodies_for_merge),
            check_row("merged_window_count", merged_windows == expected_windows_for_merge, merged_windows, expected_windows_for_merge),
            check_row("artifact_errors_empty", artifact_errors.empty, len(artifact_errors), 0),
            check_row(
                "scored_or_prepared_body_count",
                prepared_only or len(body_scores) + len(failures) == merged_bodies,
                len(body_scores) + len(failures),
                0 if prepared_only else merged_bodies,
            ),
            check_row(
                "scored_or_prepared_window_count",
                prepared_only or len(window_scores) == merged_windows,
                len(window_scores),
                0 if prepared_only else merged_windows,
            ),
            check_row("failure_rows_empty", failures.empty, len(failures), 0),
        ],
        columns=CHECK_COLUMNS,
    )
    failed_checks = int((~checks["passed"].astype(bool)).sum())
    if failed_checks:
        status = "FAIL"
    elif args.allow_partial_shards:
        status = "SMOKE_PASS"
    elif prepared_only:
        status = "PREPARED_ONLY"
    else:
        status = "PASS"

    profile_support = pd.DataFrame(
        [{
            "profile_name": args.profile_name,
            "spec_name": args.spec_name,
            "eligible_unique_bodies": merged_bodies,
            "total_windows": merged_windows,
            "total_scoring_sequences": merged_windows * 51,
            "selection_complete": not args.allow_partial_shards,
            "num_shards": args.num_shards,
            "global_eligible_unique_bodies": expected_global_bodies,
            "global_total_windows": expected_global_windows,
        }]
    )
    profile_summary = build_profile_summary(manifest, body_scores, window_scores, failures)
    estimates = build_full_run_estimates(
        profile_summary,
        profile_support,
        args.profile_name,
        args.profile_name,
    )
    summary = {
        "status": status,
        "failed_checks": failed_checks,
        "checks_total": int(len(checks)),
        "num_shards": int(args.num_shards),
        "selected_specification": args.spec_name,
        "selected_specification_role": selected_spec.get("role"),
        "minimum_literal_space_tokens": int(
            selected_spec["minimum_literal_space_tokens"]
        ),
        "maximum_literal_space_tokens": selected_spec.get(
            "maximum_literal_space_tokens"
        ),
        "agc_threshold": config.agc_threshold,
        "algorithm_version": config.algorithm_version,
        "function_aggregation": config.function_aggregation,
        "decision_rule": config.decision_rule,
        "window_policy": config.window_policy,
        "partial_body_policy": config.partial_body_policy,
        "selected_unique_bodies": merged_bodies,
        "successful_unique_bodies": int(len(body_scores)),
        "failed_unique_bodies": int(len(failures)),
        "expected_windows": merged_windows,
        "scored_windows": int(len(window_scores)),
        "global_expected_unique_bodies": expected_global_bodies,
        "global_expected_windows": expected_global_windows,
        "duplicate_body_hashes": duplicate_bodies,
        "partial_body_score_count": int(pd.to_numeric(body_scores.get("partial_body_score"), errors="coerce").fillna(0).sum()),
        "invalid_npr_window_count": int(pd.to_numeric(body_scores.get("n_invalid_npr_windows"), errors="coerce").fillna(0).sum()),
        "invalid_npr_token_count": int(pd.to_numeric(body_scores.get("invalid_npr_token_count"), errors="coerce").fillna(0).sum()),
        "bodies_scored_this_run": int(sum(int(item.get("bodies_scored_this_run", 0)) for item in shard_summaries)),
        "bodies_reused_this_run": int(sum(int(item.get("bodies_reused_this_run", 0)) for item in shard_summaries)),
        "model_loaded_this_run": bool(any(bool(item.get("model_loaded_this_run")) for item in shard_summaries)),
        "resume_validation_passed": bool(all(bool(item.get("resume_validation_passed")) for item in shard_summaries)),
        "config_fingerprint": next(iter(fingerprints)) if len(fingerprints) == 1 else None,
        "allow_partial_shards": bool(args.allow_partial_shards),
    }
    metadata = {
        "status": status,
        "analysis_stage": "run-1d-full-npr-scoring-shard-merge",
        "script_version": SCRIPT_VERSION,
        "merge_completed_utc": utc_now(),
        "shard_root": str(shard_root.resolve()),
        "output_dir": str(output_dir.resolve()),
        "num_shards": int(args.num_shards),
        "assignment": "sha256_sorted_round_robin",
        "eligibility_configuration": {
            "primary_spec": config.specification_primary,
            "selected_spec": args.spec_name,
            "minimum_literal_space_tokens": int(
                selected_spec["minimum_literal_space_tokens"]
            ),
            "maximum_literal_space_tokens": selected_spec.get(
                "maximum_literal_space_tokens"
            ),
        },
        "detector_configuration": {
            "agc_threshold": config.agc_threshold,
            "algorithm_version": config.algorithm_version,
            "function_aggregation": config.function_aggregation,
            "decision_rule": config.decision_rule,
            "window_policy": config.window_policy,
            "partial_body_policy": config.partial_body_policy,
        },
        "shard_summaries": shard_summaries,
        "shard_metadata_sha256": [
            sha256_file(
                shard_root
                / f"shard-{index:03d}-of-{args.num_shards:03d}"
                / "qc"
                / "commit_function_npr_metadata.json"
            )
            for index in range(args.num_shards)
        ],
        "input_support_sha256": sha256_file(args.input_support),
        "input_eligibility_specification_sha256": sha256_file(args.input_eligibility_specification),
        "input_threshold_specification_sha256": sha256_file(args.input_threshold_specification),
    }

    atomic_csv(manifest, output_dir / "commit_function_npr_full_manifest.csv")
    atomic_csv(profile_support, output_dir / "commit_function_npr_full_spec_support.csv")
    atomic_csv(body_scores, output_dir / "commit_function_npr_body_scores.csv", BODY_SCORE_COLUMNS)
    atomic_csv(window_scores, output_dir / "commit_function_npr_window_scores.csv", WINDOW_SCORE_COLUMNS)
    atomic_csv(failures, output_dir / "commit_function_npr_failures.csv", FAILURE_COLUMNS)
    atomic_csv(checkpoints, output_dir / "commit_function_npr_checkpoint_index.csv")
    atomic_csv(profile_summary, output_dir / "commit_function_npr_runtime_metrics.csv")
    atomic_csv(estimates, output_dir / "commit_function_npr_full_progress_estimates.csv")
    atomic_csv(artifact_errors, qc_dir / "commit_function_npr_artifact_errors.csv", ARTIFACT_ERROR_COLUMNS)
    atomic_csv(reproducibility, qc_dir / "commit_function_npr_reproducibility_checks.csv", REPRO_COLUMNS)
    atomic_csv(checks, qc_dir / "commit_function_npr_checks.csv", CHECK_COLUMNS)
    atomic_json(summary, qc_dir / "commit_function_npr_summary.json")
    atomic_json(metadata, qc_dir / "commit_function_npr_metadata.json")
    append_jsonl(
        {
            "completed_utc": utc_now(),
            "status": status,
            "num_shards": int(args.num_shards),
            "selected_unique_bodies": merged_bodies,
            "expected_windows": merged_windows,
            "elapsed_seconds": float(time.perf_counter() - started),
        },
        qc_dir / "commit_function_npr_run_history.jsonl",
    )
    print("=" * 76)
    print("Merge commit-function NPR shards")
    print(f"Status:                         {status}")
    print(f"Shards merged:                  {args.num_shards}")
    print(f"Merged unique bodies:           {merged_bodies}")
    print(f"Global expected bodies:         {expected_global_bodies}")
    print(f"Merged expected windows:        {merged_windows}")
    print(f"Global expected windows:        {expected_global_windows}")
    print(f"Duplicate body hashes:          {duplicate_bodies}")
    print(f"Failed checks:                  {failed_checks}")
    print(f"Output directory:               {output_dir}")
    print("=" * 76)
    return 0 if status in {"PASS", "PREPARED_ONLY", "SMOKE_PASS"} else 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score every unique implementation body in one frozen eligibility specification."
    )
    parser.add_argument("--input-unique-bodies", type=Path, default=Path("output/commit_function/run-1a/strict/commit_function_detectcodegpt_unique_bodies.csv"))
    parser.add_argument("--input-events", type=Path, default=Path("output/commit_function/run-1a/strict/commit_function_detectcodegpt_input_events.csv"))
    parser.add_argument("--input-panel", type=Path, default=Path("../ai_code_complexity_study_python/ai-code-complexity-study/repo_python/run-py-4a/strict/panel_event_monthly_agc_changed_block_py.csv"))
    parser.add_argument("--input-support", type=Path, default=Path("output/commit_function/run-1b/gt200/commit_function_body_eligibility_support.csv"))
    parser.add_argument("--input-eligibility-specification", type=Path, default=Path("output/commit_function/run-1b/gt200/commit_function_detectcodegpt_scoring_spec.json"))
    parser.add_argument("--input-threshold-specification", type=Path, default=Path("output/commit_function/run-1c0b/mixedcode-overlap-threshold-v1/mixedcode_overlap_threshold_specification.json"))
    parser.add_argument("--body-artifact-base", type=Path, default=Path("output/commit_function/run-1a/strict"))
    parser.add_argument("--spec-name", default="gt200")
    parser.add_argument("--profile-name", default="gt200_full")
    parser.add_argument("--output-dir", type=Path, default=Path("output/commit_function/run-1d/gt200-overlap"))
    parser.add_argument("--qc-dir", type=Path, default=None)
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--model-cache-dir", type=Path, default=Path("~/.cache/huggingface/hub").expanduser())
    parser.add_argument("--detector-output-name", default="run1d_commit_function_npr_full_gt200_v2")
    parser.add_argument("--pct-words-masked", type=float, default=0.5)
    parser.add_argument("--span-length", type=int, default=2)
    parser.add_argument("--perturbation-chunk-size", type=int, default=10)
    parser.add_argument("--n-perturbation-rounds", type=int, default=1)
    parser.add_argument("--quiet-internal-progress", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--detector-log-level", default="WARNING")
    parser.add_argument("--progress-every-bodies", type=int, default=100)
    parser.add_argument("--reproducibility-check-per-profile", type=int, default=1)
    parser.add_argument("--reproducibility-tolerance", type=float, default=1e-12)
    parser.add_argument("--overwrite-output", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--require-all-completed", action="store_true")
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--max-bodies-per-shard", type=int, default=None)
    parser.add_argument("--merge-shards", action="store_true")
    parser.add_argument("--shard-root", type=Path, default=None)
    parser.add_argument("--allow-partial-shards", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--mock-scoring", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.qc_dir is None:
        args.qc_dir = args.output_dir / "qc"
    if args.cache_dir is None:
        args.cache_dir = args.output_dir / "cache"
    args.model_cache_dir = args.model_cache_dir.expanduser()
    if args.num_shards < 1:
        parser.error("--num-shards must be at least 1")
    if args.shard_index < 0 or args.shard_index >= args.num_shards:
        parser.error("--shard-index must satisfy 0 <= shard-index < num-shards")
    if args.max_bodies_per_shard is not None and args.max_bodies_per_shard < 1:
        parser.error("--max-bodies-per-shard must be at least 1")
    if args.merge_shards and args.shard_root is None:
        parser.error("--merge-shards requires --shard-root")
    return args

def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return
    if args.merge_shards:
        exit_code = merge_shard_outputs(args)
        raise SystemExit(exit_code)
    exit_code = run_analysis(args)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
