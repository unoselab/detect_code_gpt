#!/usr/bin/env python3
"""Audit run-1a perturbation-detector inputs before NPR scoring.

This program analyzes the original-source implementation-body inputs prepared
by run-1a. It does not load StarCoder2, generate perturbations, calculate NPR,
classify AGC/HWC, aggregate final repository-month outcomes, or run DiD.

The analysis has four goals:
1. Reconcile all run-1a events and audit explicit exclusions.
2. Characterize implementation-body size support at event and unique-body levels.
3. Compare pre-specified detector eligibility rules across cohorts and periods.
4. Estimate perturbation-scoring workload before the GPU scoring experiment.

Statistical unit:
    One approved commit-function change event.

Computational unit:
    One unique implementation body identified by SHA-256.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


EVENT_REQUIRED = {
    "function_event_id",
    "dataset_source",
    "repo_name",
    "time",
    "change_type",
    "function_kind",
    "function_body_sha256",
    "function_body_relative_path",
    "function_body_character_count",
    "function_body_utf8_byte_count",
    "function_body_line_count",
    "function_body_split_space_token_count",
    "function_body_nonempty_whitespace_token_count",
    "n_128_token_windows",
    "tail_window_token_count",
    "input_preparation_complete",
    "body_extraction_status",
    "body_exclusion_reason",
}

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

EXCLUSION_REQUIRED = {
    "function_event_id",
    "dataset_source",
    "repo_name",
    "time",
    "function_kind",
    "stage",
    "error_type",
    "error_message",
}

PANEL_REQUIRED = {"dataset_source", "repo_name", "time", "time_to_event"}

CHECK_COLUMNS = ["check_name", "passed", "observed", "expected", "note"]

SIZE_BINS = [
    ("1-20", 1, 20),
    ("21-35", 21, 35),
    ("36-77", 36, 77),
    ("78-99", 78, 99),
    ("100-127", 100, 127),
    ("128-255", 128, 255),
    ("256+", 256, None),
]


@dataclass(frozen=True)
class EligibilitySpec:
    """One pre-specified implementation-body eligibility rule."""

    name: str
    min_tokens: int
    max_tokens: int | None
    role: str

    def mask(self, token_count: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(token_count, errors="coerce")
        selected = numeric.ge(self.min_tokens)
        if self.max_tokens is not None:
            selected &= numeric.le(self.max_tokens)
        return selected.fillna(False)


@dataclass(frozen=True)
class AnalysisPaths:
    input_events: Path
    input_unique_bodies: Path
    input_exclusions: Path
    input_summary: Path
    input_panel: Path
    body_artifact_base: Path
    output_dir: Path
    qc_dir: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit run-1a commit-function inputs, analyze implementation-body "
            "size support, and estimate perturbation-scoring workload."
        )
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
        "--input-unique-bodies",
        type=Path,
        default=Path(
            "output/commit_function/run-1a/strict/"
            "commit_function_detectcodegpt_unique_bodies.csv"
        ),
    )
    parser.add_argument(
        "--input-exclusions",
        type=Path,
        default=Path(
            "output/commit_function/run-1a/strict/qc/"
            "commit_function_detectcodegpt_exclusions.csv"
        ),
    )
    parser.add_argument(
        "--input-summary",
        type=Path,
        default=Path(
            "output/commit_function/run-1a/strict/qc/"
            "commit_function_detectcodegpt_summary.json"
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
        "--body-artifact-base",
        type=Path,
        default=Path("output/commit_function/run-1a/strict"),
        help=(
            "Directory against which function_body_relative_path is resolved. "
            "The default is the run-1a strict output directory."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/commit_function/run-1b/strict"),
    )
    parser.add_argument(
        "--qc-dir",
        type=Path,
        default=None,
        help="Defaults to <output-dir>/qc.",
    )
    parser.add_argument(
        "--minimum-token-thresholds",
        default="36,78,100",
        help="Comma-separated inclusive minimum literal-space token thresholds.",
    )
    parser.add_argument(
        "--bounded-token-ranges",
        default="100:200",
        help=(
            "Comma-separated inclusive token ranges written as MIN:MAX. "
            "Use an empty string to disable bounded ranges."
        ),
    )
    parser.add_argument(
        "--primary-spec",
        default="min100",
        help=(
            "Candidate primary specification name. It is recorded but is not "
            "frozen unless --freeze-specification is supplied."
        ),
    )
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--perturbations-per-window", type=int, default=50)
    parser.add_argument("--scoring-model", default="bigcode/starcoder2-7b")
    parser.add_argument("--agc-threshold", type=float, default=1.5183)
    parser.add_argument("--random-seed", type=int, default=20260723)
    parser.add_argument(
        "--measured-windows-per-second",
        type=float,
        default=0.0,
        help=(
            "Optional pilot throughput. When positive, estimated GPU hours are "
            "reported for each eligibility specification."
        ),
    )
    parser.add_argument(
        "--estimated-cache-bytes-per-window",
        type=float,
        default=0.0,
        help=(
            "Optional pilot estimate. When positive, estimated cache storage is "
            "reported for each eligibility specification."
        ),
    )
    parser.add_argument("--expected-total-events", type=int, default=450548)
    parser.add_argument("--expected-prepared-events", type=int, default=449547)
    parser.add_argument("--expected-excluded-events", type=int, default=1001)
    parser.add_argument("--expected-unique-bodies", type=int, default=343192)
    parser.add_argument(
        "--verify-body-artifacts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Verify every unique body artifact path and SHA-256.",
    )
    parser.add_argument(
        "--freeze-specification",
        action="store_true",
        help=(
            "Write commit_function_detectcodegpt_scoring_spec.json after all "
            "checks pass. Otherwise a candidate specification JSON is written."
        ),
    )
    parser.add_argument("--overwrite-output", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False, quoting=csv.QUOTE_MINIMAL)
    os.replace(temporary, path)


def atomic_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def normalize_bool(series: pd.Series) -> pd.Series:
    truthy = {"1", "1.0", "true", "t", "yes", "y"}
    falsy = {"0", "0.0", "false", "f", "no", "n", "", "nan", "none"}

    def convert(value: Any) -> bool | None:
        text = str(value).strip().lower()
        if text in truthy:
            return True
        if text in falsy:
            return False
        return None

    return series.map(convert).astype("boolean")


def clean_key(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in ("dataset_source", "repo_name", "time"):
        if column in out.columns:
            out[column] = out[column].fillna("").astype(str).str.strip()
    if "time" in out.columns:
        out["time"] = out["time"].str[:7]
    return out


def read_csv_checked(path: Path, required: set[str], label: str) -> pd.DataFrame:
    require_file(path, label)
    frame = pd.read_csv(path, dtype=str, low_memory=False)
    require_columns(frame, required, label)
    return clean_key(frame)


def parse_specs(args: argparse.Namespace) -> list[EligibilitySpec]:
    specs = [EligibilitySpec("all_positive", 1, None, "diagnostic")]

    seen_names = {"all_positive"}
    thresholds: list[int] = []
    for raw in str(args.minimum_token_thresholds).split(","):
        text = raw.strip()
        if not text:
            continue
        value = int(text)
        if value < 1:
            raise ValueError(f"Minimum token threshold must be positive: {value}")
        thresholds.append(value)

    for value in sorted(set(thresholds)):
        name = f"min{value}"
        role = "primary_candidate" if name == args.primary_spec else "sensitivity"
        if name not in seen_names:
            specs.append(EligibilitySpec(name, value, None, role))
            seen_names.add(name)

    ranges_text = str(args.bounded_token_ranges).strip()
    if ranges_text:
        for raw in ranges_text.split(","):
            item = raw.strip()
            if not item:
                continue
            if ":" not in item:
                raise ValueError(f"Invalid bounded token range: {item}")
            lower_text, upper_text = item.split(":", 1)
            lower = int(lower_text)
            upper = int(upper_text)
            if lower < 1 or upper < lower:
                raise ValueError(f"Invalid bounded token range: {item}")
            name = f"range{lower}_{upper}"
            role = "primary_candidate" if name == args.primary_spec else "robustness"
            if name not in seen_names:
                specs.append(EligibilitySpec(name, lower, upper, role))
                seen_names.add(name)

    if args.primary_spec not in {spec.name for spec in specs}:
        raise ValueError(
            f"Primary specification {args.primary_spec!r} is not among "
            f"{[spec.name for spec in specs]}"
        )
    return specs


def treatment_period(dataset_source: pd.Series, time_to_event: pd.Series) -> pd.Series:
    source = dataset_source.fillna("").astype(str).str.strip().str.lower()
    relative = pd.to_numeric(time_to_event, errors="coerce")
    result = pd.Series("unknown", index=dataset_source.index, dtype="string")
    result.loc[source.eq("control")] = "control"
    treatment = source.eq("treatment")
    result.loc[treatment & relative.lt(0)] = "pre"
    result.loc[treatment & relative.eq(0)] = "event"
    result.loc[treatment & relative.gt(0)] = "post"
    return result


def enrich_with_panel(frame: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    panel_key = ["dataset_source", "repo_name", "time"]
    duplicates = panel.duplicated(panel_key, keep=False)
    if duplicates.any():
        sample = panel.loc[duplicates, panel_key].head(10).to_dict("records")
        raise ValueError(f"Input panel has duplicate repository-month keys: {sample}")

    context_columns = panel_key + ["time_to_event"]
    for optional in ("event", "cursor", "post_event"):
        if optional in panel.columns:
            context_columns.append(optional)

    merged = frame.merge(
        panel[context_columns],
        on=panel_key,
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    merged["panel_key_matched"] = merged["_merge"].eq("both")
    merged = merged.drop(columns=["_merge"])
    merged["treatment_period"] = treatment_period(
        merged["dataset_source"], merged["time_to_event"]
    )
    return merged


def add_numeric_columns(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def size_distribution(frame: pd.DataFrame, unit: str) -> pd.DataFrame:
    token_count = pd.to_numeric(
        frame["function_body_split_space_token_count"], errors="coerce"
    )
    total = int(len(frame))
    rows: list[dict[str, Any]] = []
    for label, lower, upper in SIZE_BINS:
        selected = token_count.ge(lower)
        if upper is not None:
            selected &= token_count.le(upper)
        count = int(selected.fillna(False).sum())
        rows.append(
            {
                "unit": unit,
                "size_bin": label,
                "lower_inclusive": lower,
                "upper_inclusive": upper,
                "rows": count,
                "share": count / total if total else math.nan,
            }
        )
    return pd.DataFrame(rows)


def exclusion_summary(exclusions: pd.DataFrame) -> pd.DataFrame:
    total = len(exclusions)
    rows: list[dict[str, Any]] = []
    dimensions = [
        "stage",
        "error_type",
        "error_message",
        "dataset_source",
        "treatment_period",
        "function_kind",
    ]
    if "change_type" in exclusions.columns:
        dimensions.append("change_type")

    for dimension in dimensions:
        counts = (
            exclusions[dimension]
            .fillna("<missing>")
            .astype(str)
            .replace("", "<empty>")
            .value_counts(dropna=False)
        )
        for category, count in counts.items():
            rows.append(
                {
                    "dimension": dimension,
                    "category": category,
                    "exclusion_records": int(count),
                    "share_of_exclusions": int(count) / total if total else math.nan,
                }
            )
    return pd.DataFrame(rows)


def verify_body_artifacts(
    unique_bodies: pd.DataFrame,
    base_dir: Path,
) -> tuple[pd.DataFrame, dict[str, int]]:
    errors: list[dict[str, Any]] = []
    missing = 0
    hash_mismatch = 0
    size_mismatch = 0

    for row in unique_bodies.itertuples(index=False):
        body_sha = str(row.function_body_sha256)
        relative = Path(str(row.function_body_relative_path))
        path = base_dir / relative
        if not path.is_file():
            missing += 1
            errors.append(
                {
                    "function_body_sha256": body_sha,
                    "function_body_relative_path": relative.as_posix(),
                    "error_type": "missing_body_artifact",
                    "observed": "missing",
                    "expected": body_sha,
                }
            )
            continue

        payload = path.read_bytes()
        observed_sha = sha256_bytes(payload)
        if observed_sha != body_sha:
            hash_mismatch += 1
            errors.append(
                {
                    "function_body_sha256": body_sha,
                    "function_body_relative_path": relative.as_posix(),
                    "error_type": "body_sha256_mismatch",
                    "observed": observed_sha,
                    "expected": body_sha,
                }
            )

        expected_size = int(float(row.function_body_utf8_byte_count))
        if len(payload) != expected_size:
            size_mismatch += 1
            errors.append(
                {
                    "function_body_sha256": body_sha,
                    "function_body_relative_path": relative.as_posix(),
                    "error_type": "body_byte_count_mismatch",
                    "observed": len(payload),
                    "expected": expected_size,
                }
            )

    summary = {
        "body_artifacts_checked": int(len(unique_bodies)),
        "missing_body_artifacts": missing,
        "body_sha256_mismatches": hash_mismatch,
        "body_byte_count_mismatches": size_mismatch,
    }
    return pd.DataFrame(errors), summary


def aggregate_eligibility(
    spec: EligibilitySpec,
    prepared_events: pd.DataFrame,
    unique_bodies: pd.DataFrame,
    total_panel_months: int,
    base_event_positive_months: int,
    window_size: int,
    perturbations_per_window: int,
    measured_windows_per_second: float,
    estimated_cache_bytes_per_window: float,
) -> dict[str, Any]:
    event_mask = spec.mask(prepared_events["function_body_split_space_token_count"])
    body_mask = spec.mask(unique_bodies["function_body_split_space_token_count"])
    eligible_events = prepared_events.loc[event_mask].copy()
    eligible_bodies = unique_bodies.loc[body_mask].copy()

    total_windows = int(
        pd.to_numeric(eligible_bodies["n_128_token_windows"], errors="coerce")
        .fillna(0)
        .sum()
    )
    single_window = int(
        pd.to_numeric(eligible_bodies["n_128_token_windows"], errors="coerce")
        .fillna(0)
        .eq(1)
        .sum()
    )
    multi_window = int(
        pd.to_numeric(eligible_bodies["n_128_token_windows"], errors="coerce")
        .fillna(0)
        .gt(1)
        .sum()
    )
    event_months = int(
        eligible_events[["dataset_source", "repo_name", "time"]]
        .drop_duplicates()
        .shape[0]
    )
    total_scoring_sequences = total_windows * (1 + perturbations_per_window)
    estimated_gpu_hours = (
        total_windows / measured_windows_per_second / 3600
        if measured_windows_per_second > 0
        else math.nan
    )
    estimated_cache_gib = (
        total_windows * estimated_cache_bytes_per_window / (1024**3)
        if estimated_cache_bytes_per_window > 0
        else math.nan
    )

    return {
        "spec_name": spec.name,
        "spec_role": spec.role,
        "minimum_literal_space_tokens": spec.min_tokens,
        "maximum_literal_space_tokens": spec.max_tokens,
        "eligible_event_rows": int(len(eligible_events)),
        "event_retention_rate": (
            len(eligible_events) / len(prepared_events) if len(prepared_events) else math.nan
        ),
        "eligible_unique_bodies": int(len(eligible_bodies)),
        "unique_body_retention_rate": (
            len(eligible_bodies) / len(unique_bodies) if len(unique_bodies) else math.nan
        ),
        "eligible_event_references_from_unique_bodies": int(
            pd.to_numeric(
                eligible_bodies["referencing_function_event_count"], errors="coerce"
            )
            .fillna(0)
            .sum()
        ),
        "event_positive_repository_months": event_months,
        "newly_zero_eligible_repository_months": (
            base_event_positive_months - event_months
        ),
        "zero_eligible_repository_months_in_complete_panel": total_panel_months - event_months,
        "single_window_unique_bodies": single_window,
        "multi_window_unique_bodies": multi_window,
        "total_windows": total_windows,
        "window_size": window_size,
        "original_scoring_sequences": total_windows,
        "perturbed_scoring_sequences": total_windows * perturbations_per_window,
        "total_scoring_sequences": total_scoring_sequences,
        "perturbations_per_window": perturbations_per_window,
        "measured_windows_per_second": measured_windows_per_second,
        "estimated_gpu_hours": estimated_gpu_hours,
        "estimated_cache_bytes_per_window": estimated_cache_bytes_per_window,
        "estimated_cache_gib": estimated_cache_gib,
    }


def support_by_dimension(
    specs: list[EligibilitySpec],
    events: pd.DataFrame,
    dimension: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    groups = events[dimension].fillna("<missing>").astype(str)
    for category in sorted(groups.unique()):
        group = events.loc[groups.eq(category)]
        for spec in specs:
            eligible = spec.mask(group["function_body_split_space_token_count"])
            count = int(eligible.sum())
            rows.append(
                {
                    "dimension": dimension,
                    "category": category,
                    "spec_name": spec.name,
                    "spec_role": spec.role,
                    "total_prepared_events": int(len(group)),
                    "eligible_events": count,
                    "retention_rate": count / len(group) if len(group) else math.nan,
                }
            )
    return pd.DataFrame(rows)


def make_checks(
    events: pd.DataFrame,
    prepared: pd.DataFrame,
    exclusions: pd.DataFrame,
    unique_bodies: pd.DataFrame,
    panel: pd.DataFrame,
    summary: dict[str, Any],
    body_verification: dict[str, int],
    expected: dict[str, int],
) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, observed: Any, expected_value: Any, note: str) -> None:
        checks.append(
            {
                "check_name": name,
                "passed": bool(passed),
                "observed": observed,
                "expected": expected_value,
                "note": note,
            }
        )

    prepared_ids = set(prepared["function_event_id"].astype(str))
    exclusion_ids = set(exclusions["function_event_id"].astype(str))
    all_ids = set(events["function_event_id"].astype(str))

    add(
        "event_rows_match_expected_total",
        len(events) == expected["total"],
        len(events),
        expected["total"],
        "run-1a event output preserves every selected event row.",
    )
    add(
        "prepared_rows_match_expected",
        len(prepared) == expected["prepared"],
        len(prepared),
        expected["prepared"],
        "Prepared rows are eligible for support analysis before size filtering.",
    )
    add(
        "exclusion_rows_match_expected",
        len(exclusions) == expected["excluded"],
        len(exclusions),
        expected["excluded"],
        "Every explicit run-1a exclusion must remain auditable.",
    )
    add(
        "event_reconciliation",
        len(prepared) + len(exclusions) == len(events),
        len(prepared) + len(exclusions),
        len(events),
        "Prepared plus excluded events must equal all run-1a event rows.",
    )
    add(
        "event_ids_unique",
        events["function_event_id"].is_unique,
        int(events["function_event_id"].duplicated().sum()),
        0,
        "One row is required per approved commit-function event.",
    )
    add(
        "prepared_and_excluded_ids_disjoint",
        prepared_ids.isdisjoint(exclusion_ids),
        len(prepared_ids & exclusion_ids),
        0,
        "An event cannot be both prepared and excluded.",
    )
    add(
        "prepared_and_excluded_cover_all_ids",
        prepared_ids | exclusion_ids == all_ids,
        len(prepared_ids | exclusion_ids),
        len(all_ids),
        "No event may silently disappear from run-1a reconciliation.",
    )
    add(
        "unique_body_rows_match_expected",
        len(unique_bodies) == expected["unique"],
        len(unique_bodies),
        expected["unique"],
        "Unique bodies define the computational scoring unit.",
    )
    add(
        "unique_body_hashes_unique",
        unique_bodies["function_body_sha256"].is_unique,
        int(unique_bodies["function_body_sha256"].duplicated().sum()),
        0,
        "Each content-addressed implementation body must appear once.",
    )
    unique_ref_count = int(
        pd.to_numeric(
            unique_bodies["referencing_function_event_count"], errors="coerce"
        )
        .fillna(0)
        .sum()
    )
    add(
        "unique_body_reference_count_matches_prepared",
        unique_ref_count == len(prepared),
        unique_ref_count,
        len(prepared),
        "Unique-body reference counts must reconstruct prepared event rows.",
    )
    add(
        "prepared_body_hashes_in_unique_manifest",
        set(prepared["function_body_sha256"].astype(str)).issubset(
            set(unique_bodies["function_body_sha256"].astype(str))
        ),
        len(
            set(prepared["function_body_sha256"].astype(str))
            - set(unique_bodies["function_body_sha256"].astype(str))
        ),
        0,
        "Every prepared event must map to a unique-body row.",
    )
    add(
        "prepared_panel_keys_matched",
        bool(prepared["panel_key_matched"].all()),
        int((~prepared["panel_key_matched"]).sum()),
        0,
        "Prepared events require treatment-period context from the matched panel.",
    )
    add(
        "exclusion_panel_keys_matched",
        bool(exclusions["panel_key_matched"].all()),
        int((~exclusions["panel_key_matched"]).sum()),
        0,
        "Exclusions require treatment-period context for distribution checks.",
    )
    add(
        "panel_keys_unique",
        not panel.duplicated(["dataset_source", "repo_name", "time"]).any(),
        int(panel.duplicated(["dataset_source", "repo_name", "time"]).sum()),
        0,
        "The matched repository-month panel must have unique keys.",
    )
    add(
        "body_artifacts_missing_zero",
        body_verification["missing_body_artifacts"] == 0,
        body_verification["missing_body_artifacts"],
        0,
        "All unique body artifacts must exist before scoring.",
    )
    add(
        "body_sha256_mismatches_zero",
        body_verification["body_sha256_mismatches"] == 0,
        body_verification["body_sha256_mismatches"],
        0,
        "Body file content must match its content-addressed SHA-256.",
    )
    add(
        "body_byte_count_mismatches_zero",
        body_verification["body_byte_count_mismatches"] == 0,
        body_verification["body_byte_count_mismatches"],
        0,
        "Body artifact byte counts must match the run-1a manifest.",
    )

    for field, expected_value in (
        ("selected_event_rows", expected["total"]),
        ("prepared_events", expected["prepared"]),
        ("excluded_events", expected["excluded"]),
        ("unique_bodies", expected["unique"]),
    ):
        observed = summary.get(field)
        add(
            f"run1a_summary_{field}_matches_expected",
            int(observed) == int(expected_value) if observed is not None else False,
            observed,
            expected_value,
            "Cross-check against the frozen run-1a summary.",
        )

    return pd.DataFrame(checks, columns=CHECK_COLUMNS)


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    qc_dir = args.qc_dir or args.output_dir / "qc"
    paths = AnalysisPaths(
        input_events=args.input_events,
        input_unique_bodies=args.input_unique_bodies,
        input_exclusions=args.input_exclusions,
        input_summary=args.input_summary,
        input_panel=args.input_panel,
        body_artifact_base=args.body_artifact_base,
        output_dir=args.output_dir,
        qc_dir=qc_dir,
    )

    if args.window_size <= 0:
        raise ValueError("--window-size must be positive")
    if args.perturbations_per_window <= 0:
        raise ValueError("--perturbations-per-window must be positive")

    for path, label in (
        (paths.input_events, "run-1a event output"),
        (paths.input_unique_bodies, "run-1a unique-body output"),
        (paths.input_exclusions, "run-1a exclusion output"),
        (paths.input_summary, "run-1a summary"),
        (paths.input_panel, "matched repository-month panel"),
    ):
        require_file(path, label)
    if not paths.body_artifact_base.is_dir():
        raise FileNotFoundError(
            f"Missing body artifact base directory: {paths.body_artifact_base}"
        )

    if paths.output_dir.exists() and any(paths.output_dir.iterdir()):
        if not args.overwrite_output:
            raise FileExistsError(
                f"Output directory is not empty: {paths.output_dir}. "
                "Use --overwrite-output to replace it."
            )
        shutil.rmtree(paths.output_dir)
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.qc_dir.mkdir(parents=True, exist_ok=True)

    events = read_csv_checked(paths.input_events, EVENT_REQUIRED, "run-1a events")
    unique_bodies = read_csv_checked(
        paths.input_unique_bodies, UNIQUE_BODY_REQUIRED, "run-1a unique bodies"
    )
    exclusions = read_csv_checked(
        paths.input_exclusions, EXCLUSION_REQUIRED, "run-1a exclusions"
    )
    panel = read_csv_checked(paths.input_panel, PANEL_REQUIRED, "matched panel")
    summary = json.loads(paths.input_summary.read_text(encoding="utf-8"))

    events["input_preparation_complete"] = normalize_bool(
        events["input_preparation_complete"]
    )
    prepared_mask = (
        events["body_extraction_status"].fillna("").astype(str).str.strip().eq("prepared")
        & events["input_preparation_complete"].fillna(False)
    )
    prepared = events.loc[prepared_mask].copy()

    numeric_event_columns = [
        "function_body_character_count",
        "function_body_utf8_byte_count",
        "function_body_line_count",
        "function_body_split_space_token_count",
        "function_body_nonempty_whitespace_token_count",
        "n_128_token_windows",
        "tail_window_token_count",
    ]
    numeric_body_columns = numeric_event_columns + ["referencing_function_event_count"]
    prepared = add_numeric_columns(prepared, numeric_event_columns)
    unique_bodies = add_numeric_columns(unique_bodies, numeric_body_columns)

    prepared = enrich_with_panel(prepared, panel)
    exclusions = enrich_with_panel(exclusions, panel)

    specs = parse_specs(args)
    total_panel_months = int(
        panel[["dataset_source", "repo_name", "time"]].drop_duplicates().shape[0]
    )
    base_event_positive_months = int(
        prepared[["dataset_source", "repo_name", "time"]]
        .drop_duplicates()
        .shape[0]
    )

    if args.verify_body_artifacts:
        artifact_errors, body_verification = verify_body_artifacts(
            unique_bodies, paths.body_artifact_base
        )
    else:
        artifact_errors = pd.DataFrame(
            columns=[
                "function_body_sha256",
                "function_body_relative_path",
                "error_type",
                "observed",
                "expected",
            ]
        )
        body_verification = {
            "body_artifacts_checked": 0,
            "missing_body_artifacts": 0,
            "body_sha256_mismatches": 0,
            "body_byte_count_mismatches": 0,
        }

    expected = {
        "total": args.expected_total_events,
        "prepared": args.expected_prepared_events,
        "excluded": args.expected_excluded_events,
        "unique": args.expected_unique_bodies,
    }
    checks = make_checks(
        events,
        prepared,
        exclusions,
        unique_bodies,
        panel,
        summary,
        body_verification,
        expected,
    )

    event_distribution = size_distribution(prepared, "event_reference")
    body_distribution = size_distribution(unique_bodies, "unique_body")
    exclusions_enriched = exclusions.copy()
    exclusions_summary = exclusion_summary(exclusions_enriched)

    support_rows = [
        aggregate_eligibility(
            spec,
            prepared,
            unique_bodies,
            total_panel_months,
            base_event_positive_months,
            args.window_size,
            args.perturbations_per_window,
            args.measured_windows_per_second,
            args.estimated_cache_bytes_per_window,
        )
        for spec in specs
    ]
    eligibility_support = pd.DataFrame(support_rows)
    by_cohort = support_by_dimension(specs, prepared, "dataset_source")
    by_period = support_by_dimension(specs, prepared, "treatment_period")
    by_function = support_by_dimension(specs, prepared, "function_kind")
    by_change = support_by_dimension(specs, prepared, "change_type")

    failed_checks = int((~checks["passed"].astype(bool)).sum())
    status = "PASS" if failed_checks == 0 else "FAIL"

    input_hashes = {
        "input_events_sha256": sha256_file(paths.input_events),
        "input_unique_bodies_sha256": sha256_file(paths.input_unique_bodies),
        "input_exclusions_sha256": sha256_file(paths.input_exclusions),
        "input_summary_sha256": sha256_file(paths.input_summary),
        "input_panel_sha256": sha256_file(paths.input_panel),
    }

    metadata = {
        "status": status,
        "analysis_stage": "run-1b-input-support-preflight",
        "inputs": {
            "events": str(paths.input_events.resolve()),
            "unique_bodies": str(paths.input_unique_bodies.resolve()),
            "exclusions": str(paths.input_exclusions.resolve()),
            "run1a_summary": str(paths.input_summary.resolve()),
            "matched_panel": str(paths.input_panel.resolve()),
            "body_artifact_base": str(paths.body_artifact_base.resolve()),
        },
        "input_hashes": input_hashes,
        "detector_configuration": {
            "scoring_model": args.scoring_model,
            "window_size_literal_space_tokens": args.window_size,
            "perturbations_per_window": args.perturbations_per_window,
            "perturbation_type": "random-insert-space+newline",
            "function_aggregation": "token-weighted mean",
            "agc_threshold": args.agc_threshold,
            "random_seed": args.random_seed,
            "primary_spec_candidate": args.primary_spec,
            "specifications_frozen": bool(args.freeze_specification),
        },
        "eligibility_specifications": [
            {
                "name": spec.name,
                "role": spec.role,
                "minimum_literal_space_tokens": spec.min_tokens,
                "maximum_literal_space_tokens": spec.max_tokens,
            }
            for spec in specs
        ],
        "body_artifact_verification": body_verification,
    }

    summary_out = {
        "status": status,
        "failed_checks": failed_checks,
        "checks_total": int(len(checks)),
        "total_event_rows": int(len(events)),
        "prepared_event_rows": int(len(prepared)),
        "explicit_exclusion_rows": int(len(exclusions)),
        "unique_body_rows": int(len(unique_bodies)),
        "total_panel_repository_months": total_panel_months,
        "prepared_event_positive_repository_months": base_event_positive_months,
        "eligibility_specifications": int(len(specs)),
        "primary_spec_candidate": args.primary_spec,
        "specifications_frozen": bool(args.freeze_specification),
        **body_verification,
    }

    output_files = {
        "exclusions_enriched": paths.output_dir
        / "commit_function_input_exclusions_enriched.csv",
        "exclusion_summary": paths.output_dir
        / "commit_function_input_exclusion_summary.csv",
        "event_size_distribution": paths.output_dir
        / "commit_function_body_size_distribution_events.csv",
        "unique_body_size_distribution": paths.output_dir
        / "commit_function_body_size_distribution_unique_bodies.csv",
        "eligibility_support": paths.output_dir
        / "commit_function_body_eligibility_support.csv",
        "eligibility_by_cohort": paths.output_dir
        / "commit_function_body_eligibility_by_cohort.csv",
        "eligibility_by_period": paths.output_dir
        / "commit_function_body_eligibility_by_period.csv",
        "eligibility_by_function": paths.output_dir
        / "commit_function_body_eligibility_by_function_category.csv",
        "eligibility_by_change": paths.output_dir
        / "commit_function_body_eligibility_by_change_type.csv",
        "scoring_cost": paths.output_dir
        / "commit_function_npr_scoring_cost_estimates.csv",
        "checks": paths.qc_dir / "commit_function_input_support_checks.csv",
        "artifact_errors": paths.qc_dir
        / "commit_function_body_artifact_errors.csv",
        "summary": paths.qc_dir / "commit_function_input_support_summary.json",
        "metadata": paths.qc_dir / "commit_function_input_support_metadata.json",
    }

    atomic_csv(exclusions_enriched, output_files["exclusions_enriched"])
    atomic_csv(exclusions_summary, output_files["exclusion_summary"])
    atomic_csv(event_distribution, output_files["event_size_distribution"])
    atomic_csv(body_distribution, output_files["unique_body_size_distribution"])
    atomic_csv(eligibility_support, output_files["eligibility_support"])
    atomic_csv(by_cohort, output_files["eligibility_by_cohort"])
    atomic_csv(by_period, output_files["eligibility_by_period"])
    atomic_csv(by_function, output_files["eligibility_by_function"])
    atomic_csv(by_change, output_files["eligibility_by_change"])
    atomic_csv(eligibility_support, output_files["scoring_cost"])
    atomic_csv(checks, output_files["checks"])
    atomic_csv(artifact_errors, output_files["artifact_errors"])
    atomic_json(summary_out, output_files["summary"])
    atomic_json(metadata, output_files["metadata"])

    spec_filename = (
        "commit_function_detectcodegpt_scoring_spec.json"
        if args.freeze_specification
        else "commit_function_detectcodegpt_candidate_scoring_spec.json"
    )
    spec_path = paths.output_dir / spec_filename
    atomic_json(
        {
            "status": "frozen" if args.freeze_specification else "candidate",
            "primary_spec": args.primary_spec,
            "scoring_model": args.scoring_model,
            "window_size_literal_space_tokens": args.window_size,
            "perturbations_per_window": args.perturbations_per_window,
            "perturbation_type": "random-insert-space+newline",
            "function_aggregation": "token-weighted mean",
            "agc_threshold": args.agc_threshold,
            "random_seed": args.random_seed,
            "input_hashes": input_hashes,
            "eligibility_specifications": metadata["eligibility_specifications"],
            "note": (
                "This file freezes the pre-scoring detector specification."
                if args.freeze_specification
                else (
                    "Candidate specification only. Review run-1b support outputs "
                    "before rerunning with --freeze-specification."
                )
            ),
        },
        spec_path,
    )

    print("=" * 76)
    print("Analyze commit-function perturbation-detector input support")
    print(f"Status:                         {status}")
    print(f"Total run-1a event rows:        {len(events)}")
    print(f"Prepared event rows:            {len(prepared)}")
    print(f"Explicit exclusions:            {len(exclusions)}")
    print(f"Unique implementation bodies:   {len(unique_bodies)}")
    print(f"Complete panel repo-months:      {total_panel_months}")
    print(f"Event-positive repo-months:      {base_event_positive_months}")
    print(f"Eligibility specifications:     {len(specs)}")
    print(f"Body artifacts checked:         {body_verification['body_artifacts_checked']}")
    print(f"Failed checks:                   {failed_checks}")
    print(f"Output directory:                {paths.output_dir}")
    print(f"QC directory:                    {paths.qc_dir}")
    print(f"Specification file:              {spec_path}")
    print("=" * 76)

    return {
        "status": status,
        "failed_checks": failed_checks,
        "summary": summary_out,
        "output_files": {key: str(value) for key, value in output_files.items()},
        "spec_path": str(spec_path),
    }


def run_self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="run1b-self-test-") as temporary:
        root = Path(temporary)
        run1a = root / "run-1a" / "strict"
        qc = run1a / "qc"
        body_dir = run1a / "function_bodies" / "aa"
        body_dir.mkdir(parents=True)
        qc.mkdir(parents=True)

        body_a = "    return value\n"
        body_b = "    result = value + 1\n    return result\n"
        sha_a = hashlib.sha256(body_a.encode("utf-8")).hexdigest()
        sha_b = hashlib.sha256(body_b.encode("utf-8")).hexdigest()
        path_a = body_dir / f"{sha_a}.txt"
        path_b = body_dir / f"{sha_b}.txt"
        path_a.write_text(body_a, encoding="utf-8")
        path_b.write_text(body_b, encoding="utf-8")

        events = pd.DataFrame(
            [
                {
                    "function_event_id": "e1",
                    "dataset_source": "treatment",
                    "repo_name": "org/repo",
                    "time": "2025-01",
                    "change_type": "added",
                    "function_kind": "module_function",
                    "function_body_sha256": sha_a,
                    "function_body_relative_path": path_a.relative_to(run1a).as_posix(),
                    "function_body_character_count": len(body_a),
                    "function_body_utf8_byte_count": len(body_a.encode("utf-8")),
                    "function_body_line_count": 1,
                    "function_body_split_space_token_count": 5,
                    "function_body_nonempty_whitespace_token_count": 2,
                    "n_128_token_windows": 1,
                    "tail_window_token_count": 5,
                    "input_preparation_complete": True,
                    "body_extraction_status": "prepared",
                    "body_exclusion_reason": "",
                },
                {
                    "function_event_id": "e2",
                    "dataset_source": "treatment",
                    "repo_name": "org/repo",
                    "time": "2025-02",
                    "change_type": "modified",
                    "function_kind": "method",
                    "function_body_sha256": sha_b,
                    "function_body_relative_path": path_b.relative_to(run1a).as_posix(),
                    "function_body_character_count": len(body_b),
                    "function_body_utf8_byte_count": len(body_b.encode("utf-8")),
                    "function_body_line_count": 2,
                    "function_body_split_space_token_count": 40,
                    "function_body_nonempty_whitespace_token_count": 7,
                    "n_128_token_windows": 1,
                    "tail_window_token_count": 40,
                    "input_preparation_complete": True,
                    "body_extraction_status": "prepared",
                    "body_exclusion_reason": "",
                },
                {
                    "function_event_id": "e3",
                    "dataset_source": "control",
                    "repo_name": "org/control",
                    "time": "2025-01",
                    "change_type": "added",
                    "function_kind": "module_function",
                    "function_body_sha256": "",
                    "function_body_relative_path": "",
                    "function_body_character_count": "",
                    "function_body_utf8_byte_count": "",
                    "function_body_line_count": "",
                    "function_body_split_space_token_count": "",
                    "function_body_nonempty_whitespace_token_count": "",
                    "n_128_token_windows": "",
                    "tail_window_token_count": "",
                    "input_preparation_complete": False,
                    "body_extraction_status": "excluded",
                    "body_exclusion_reason": "docstring_only_after_prompt_removal",
                },
            ]
        )
        unique = pd.DataFrame(
            [
                {
                    "function_body_sha256": sha_a,
                    "function_body_relative_path": path_a.relative_to(run1a).as_posix(),
                    "function_body_character_count": len(body_a),
                    "function_body_utf8_byte_count": len(body_a.encode("utf-8")),
                    "function_body_line_count": 1,
                    "function_body_split_space_token_count": 5,
                    "function_body_nonempty_whitespace_token_count": 2,
                    "n_128_token_windows": 1,
                    "tail_window_token_count": 5,
                    "referencing_function_event_count": 1,
                },
                {
                    "function_body_sha256": sha_b,
                    "function_body_relative_path": path_b.relative_to(run1a).as_posix(),
                    "function_body_character_count": len(body_b),
                    "function_body_utf8_byte_count": len(body_b.encode("utf-8")),
                    "function_body_line_count": 2,
                    "function_body_split_space_token_count": 40,
                    "function_body_nonempty_whitespace_token_count": 7,
                    "n_128_token_windows": 1,
                    "tail_window_token_count": 40,
                    "referencing_function_event_count": 1,
                },
            ]
        )
        exclusion = pd.DataFrame(
            [
                {
                    "function_event_id": "e3",
                    "dataset_source": "control",
                    "repo_name": "org/control",
                    "time": "2025-01",
                    "function_kind": "module_function",
                    "stage": "implementation_body_extract",
                    "error_type": "StageError",
                    "error_message": "docstring_only_after_prompt_removal",
                }
            ]
        )
        panel = pd.DataFrame(
            [
                {
                    "dataset_source": "treatment",
                    "repo_name": "org/repo",
                    "time": "2025-01",
                    "time_to_event": -1,
                },
                {
                    "dataset_source": "treatment",
                    "repo_name": "org/repo",
                    "time": "2025-02",
                    "time_to_event": 0,
                },
                {
                    "dataset_source": "control",
                    "repo_name": "org/control",
                    "time": "2025-01",
                    "time_to_event": -1,
                },
            ]
        )

        events_path = run1a / "commit_function_detectcodegpt_input_events.csv"
        unique_path = run1a / "commit_function_detectcodegpt_unique_bodies.csv"
        exclusion_path = qc / "commit_function_detectcodegpt_exclusions.csv"
        summary_path = qc / "commit_function_detectcodegpt_summary.json"
        panel_path = root / "panel.csv"
        events.to_csv(events_path, index=False)
        unique.to_csv(unique_path, index=False)
        exclusion.to_csv(exclusion_path, index=False)
        panel.to_csv(panel_path, index=False)
        summary_path.write_text(
            json.dumps(
                {
                    "selected_event_rows": 3,
                    "prepared_events": 2,
                    "excluded_events": 1,
                    "unique_bodies": 2,
                }
            ),
            encoding="utf-8",
        )

        namespace = argparse.Namespace(
            input_events=events_path,
            input_unique_bodies=unique_path,
            input_exclusions=exclusion_path,
            input_summary=summary_path,
            input_panel=panel_path,
            body_artifact_base=run1a,
            output_dir=root / "run-1b" / "strict",
            qc_dir=None,
            minimum_token_thresholds="36,78,100",
            bounded_token_ranges="100:200",
            primary_spec="min100",
            window_size=128,
            perturbations_per_window=50,
            scoring_model="bigcode/starcoder2-7b",
            agc_threshold=1.5183,
            random_seed=20260723,
            measured_windows_per_second=0.0,
            estimated_cache_bytes_per_window=0.0,
            expected_total_events=3,
            expected_prepared_events=2,
            expected_excluded_events=1,
            expected_unique_bodies=2,
            verify_body_artifacts=True,
            freeze_specification=False,
            overwrite_output=True,
            self_test=False,
        )
        result = analyze(namespace)
        if result["status"] != "PASS":
            raise AssertionError(f"Self-test analysis failed: {result}")
        support = pd.read_csv(
            namespace.output_dir / "commit_function_body_eligibility_support.csv"
        )
        min36 = support.loc[support["spec_name"].eq("min36")].iloc[0]
        if int(min36["eligible_event_rows"]) != 1:
            raise AssertionError("Self-test min36 event support mismatch")
        print("Self-test: PASS")


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0
    result = analyze(args)
    return 0 if result["failed_checks"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
