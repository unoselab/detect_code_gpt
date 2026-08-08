#!/usr/bin/env python3
"""Aggregate A02 NPR measurements from code units to files and snapshots.

A03 is a CPU-only aggregation stage. It does not parse Python source and does
not run the language model. The authoritative hierarchy is:

    A01 primary code-unit occurrences
        -> A02 code-unit NPR scores
        -> file-level continuous NPR summaries
        -> snapshot-level continuous NPR summaries

The primary aggregation coordinate is the original DetectCodeGPT-style
space-by-token coordinate. LLM-token counts are retained only as diagnostics.
Both ratio-weighted NPR and component-pooled NPR are preserved because they
are generally not mathematically identical.

This program intentionally performs no AGC/HWC classification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

IMPLEMENTATION_VERSION = "run-x-a03-v1"
PRIMARY_ROLE = "primary"
DEFAULT_TOLERANCE = 1e-12

CODE_UNIT_KEY = ["snapshot_id", "relative_path", "code_unit_id", "code_unit_sha256"]
FILE_KEY = ["snapshot_id", "relative_path", "file_sha256"]
SNAPSHOT_KEY = ["snapshot_id"]

A01_SNAPSHOT_REQUIRED = [
    "snapshot_order",
    "snapshot_id",
    "dataset_source",
    "repo_name",
    "repo_key",
    "snapshot_time",
    "snapshot_commit",
    "python_files_discovered",
    "python_files_prepared",
    "primary_code_units",
    "space_by_tokens_primary",
]

A01_FILE_REQUIRED = [
    "snapshot_order",
    "snapshot_id",
    "dataset_source",
    "repo_name",
    "repo_key",
    "snapshot_time",
    "snapshot_commit",
    "relative_path",
    "file_sha256",
    "physical_line_count",
    "parse_status",
    "primary_code_units",
]

A01_CODE_REQUIRED = [
    "snapshot_id",
    "relative_path",
    "file_sha256",
    "code_unit_id",
    "code_unit_type",
    "aggregation_role",
    "code_unit_sha256",
    "space_by_token_count",
    "physical_line_count",
]

A02_CODE_REQUIRED = [
    "snapshot_id",
    "relative_path",
    "file_sha256",
    "code_unit_id",
    "code_unit_sha256",
    "space_by_tokens_total",
    "space_by_tokens_scored",
    "npr_coverage_ratio",
    "original_llm_tokens_all_windows",
    "original_llm_tokens_valid_windows",
    "code_unit_npr_space_by_token_weighted",
    "code_unit_original_log_rank_weighted",
    "code_unit_mean_perturbed_log_rank_weighted",
    "code_unit_npr_pooled_components",
    "status",
    "config_fingerprint",
]

A02_WINDOW_REQUIRED = [
    "code_unit_sha256",
    "window_index",
    "window_space_by_token_count",
    "window_aggregation_weight_space_by_tokens",
    "original_llm_token_count",
    "window_npr",
    "window_npr_valid",
    "config_fingerprint",
]

SCORE_COLUMNS = [
    "space_by_tokens_total",
    "space_by_tokens_scored",
    "npr_coverage_ratio",
    "original_llm_tokens_all_windows",
    "original_llm_tokens_valid_windows",
    "code_unit_npr_space_by_token_weighted",
    "code_unit_original_log_rank_weighted",
    "code_unit_mean_perturbed_log_rank_weighted",
    "code_unit_npr_pooled_components",
    "partial_code_unit_score",
    "status",
    "config_fingerprint",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate A02 NPR scores to file and snapshot levels.")
    parser.add_argument("--a01-snapshot-manifest", required=True, type=Path)
    parser.add_argument("--a01-file-manifest", required=True, type=Path)
    parser.add_argument("--a01-code-unit-manifest", required=True, type=Path)
    parser.add_argument("--a02-code-unit-scores", required=True, type=Path)
    parser.add_argument("--a02-window-scores", required=True, type=Path)
    parser.add_argument("--a02-metadata", type=Path, default=None)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-snapshots", type=int, default=None)
    parser.add_argument("--require-full-coverage", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_if_exists(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def require_columns(df: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def finite_number(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def atomic_write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent) as handle:
        temp_path = Path(handle.name)
        df.to_csv(handle, index=False)
    os.replace(temp_path, path)


def atomic_write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        temp_path = Path(handle.name)
        json.dump(json_safe(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temp_path, path)


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
    severity: str = "hard",
) -> None:
    checks.append(
        {
            "severity": severity,
            "check_name": name,
            "passed": bool(passed),
            "observed": json.dumps(json_safe(observed), ensure_ascii=False, sort_keys=True),
            "expected": json.dumps(json_safe(expected), ensure_ascii=False, sort_keys=True),
            "detail": detail,
        }
    )


def aggregate_group(group: pd.DataFrame) -> dict[str, Any]:
    total = int(group["_space_by_tokens_total"].sum())
    scored = int(group["_space_by_tokens_scored"].sum())

    usable_mask = (
        group["_space_by_tokens_scored"].gt(0)
        & np.isfinite(pd.to_numeric(group["code_unit_npr_space_by_token_weighted"], errors="coerce"))
        & np.isfinite(pd.to_numeric(group["code_unit_original_log_rank_weighted"], errors="coerce"))
        & np.isfinite(pd.to_numeric(group["code_unit_mean_perturbed_log_rank_weighted"], errors="coerce"))
    )
    usable = group.loc[usable_mask].copy()
    used = int(usable["_space_by_tokens_scored"].sum()) if not usable.empty else 0

    if used > 0:
        weights = usable["_space_by_tokens_scored"].astype(float)
        npr_ratio_weighted = float(
            np.average(usable["code_unit_npr_space_by_token_weighted"].astype(float), weights=weights)
        )
        original_weighted = float(
            np.average(usable["code_unit_original_log_rank_weighted"].astype(float), weights=weights)
        )
        perturbed_weighted = float(
            np.average(usable["code_unit_mean_perturbed_log_rank_weighted"].astype(float), weights=weights)
        )
        pooled = float(perturbed_weighted / original_weighted) if original_weighted != 0 else float("nan")
    else:
        npr_ratio_weighted = float("nan")
        original_weighted = float("nan")
        perturbed_weighted = float("nan")
        pooled = float("nan")

    coverage = float(scored / total) if total > 0 else float("nan")
    effective_coverage = float(used / total) if total > 0 else float("nan")

    matched = group["_a02_score_present"].astype(bool)
    fully_scored = matched & group["_space_by_tokens_scored"].eq(group["_space_by_tokens_total"])
    partial = matched & group["_space_by_tokens_scored"].gt(0) & ~fully_scored
    unscored = ~matched | group["_space_by_tokens_scored"].eq(0)

    return {
        "primary_code_units": int(len(group)),
        "primary_code_units_with_a02_record": int(matched.sum()),
        "primary_code_units_fully_scored": int(fully_scored.sum()),
        "primary_code_units_partially_scored": int(partial.sum()),
        "primary_code_units_unscored": int(unscored.sum()),
        "space_by_tokens_total": total,
        "space_by_tokens_scored": scored,
        "space_by_tokens_used_for_npr": used,
        "npr_coverage_ratio": coverage,
        "npr_effective_coverage_ratio": effective_coverage,
        "llm_tokens_original_total": int(group["_llm_tokens_all"].sum()),
        "llm_tokens_original_valid_windows_total": int(group["_llm_tokens_valid"].sum()),
        "npr_space_by_token_weighted": npr_ratio_weighted,
        "original_log_rank_space_by_token_weighted": original_weighted,
        "mean_perturbed_log_rank_space_by_token_weighted": perturbed_weighted,
        "npr_pooled_components": pooled,
    }


def aggregate_by(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouper: Any = keys[0] if len(keys) == 1 else keys
    for group_key, group in df.groupby(grouper, sort=False, dropna=False):
        values = group_key if isinstance(group_key, tuple) else (group_key,)
        row = {key: value for key, value in zip(keys, values)}
        row.update(aggregate_group(group))
        rows.append(row)
    return pd.DataFrame(rows)


def prepare_unit_table(a01_code: pd.DataFrame, a02_code: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    primary = a01_code.loc[a01_code["aggregation_role"].astype(str).eq(PRIMARY_ROLE)].copy()
    if primary.duplicated(CODE_UNIT_KEY).any():
        duplicates = primary.loc[primary.duplicated(CODE_UNIT_KEY, keep=False), CODE_UNIT_KEY]
        raise ValueError(f"A01 primary code-unit key duplicates found: {duplicates.head(10).to_dict('records')}")
    if a02_code.duplicated(CODE_UNIT_KEY).any():
        duplicates = a02_code.loc[a02_code.duplicated(CODE_UNIT_KEY, keep=False), CODE_UNIT_KEY]
        raise ValueError(f"A02 code-unit score key duplicates found: {duplicates.head(10).to_dict('records')}")

    a01_keys = primary[CODE_UNIT_KEY].drop_duplicates()
    a02_keys = a02_code[CODE_UNIT_KEY].drop_duplicates()
    a02_extra = a02_keys.merge(a01_keys, on=CODE_UNIT_KEY, how="left", indicator=True)
    a02_extra = a02_extra.loc[a02_extra["_merge"].eq("left_only"), CODE_UNIT_KEY]

    available_score_columns = [column for column in SCORE_COLUMNS if column in a02_code.columns]
    score_input = a02_code[CODE_UNIT_KEY + available_score_columns].copy()
    merged = primary.merge(score_input, on=CODE_UNIT_KEY, how="left", validate="one_to_one", indicator="_score_merge")

    merged["_a02_score_present"] = merged["_score_merge"].eq("both")
    merged["_space_by_tokens_total"] = pd.to_numeric(merged["space_by_token_count"], errors="raise").astype(int)
    merged["_space_by_tokens_scored"] = pd.to_numeric(
        merged.get("space_by_tokens_scored", pd.Series(0, index=merged.index)), errors="coerce"
    ).fillna(0).astype(int)
    merged["_llm_tokens_all"] = pd.to_numeric(
        merged.get("original_llm_tokens_all_windows", pd.Series(0, index=merged.index)), errors="coerce"
    ).fillna(0).astype(int)
    merged["_llm_tokens_valid"] = pd.to_numeric(
        merged.get("original_llm_tokens_valid_windows", pd.Series(0, index=merged.index)), errors="coerce"
    ).fillna(0).astype(int)

    matched = merged["_a02_score_present"]
    if "space_by_tokens_total" in merged.columns:
        a02_total = pd.to_numeric(merged["space_by_tokens_total"], errors="coerce")
        token_total_mismatch = matched & a02_total.notna() & a02_total.ne(merged["_space_by_tokens_total"])
    else:
        token_total_mismatch = pd.Series(False, index=merged.index)

    score_finite_mask = (
        np.isfinite(pd.to_numeric(merged["code_unit_npr_space_by_token_weighted"], errors="coerce"))
        & np.isfinite(pd.to_numeric(merged["code_unit_original_log_rank_weighted"], errors="coerce"))
        & np.isfinite(pd.to_numeric(merged["code_unit_mean_perturbed_log_rank_weighted"], errors="coerce"))
        & np.isfinite(pd.to_numeric(merged["code_unit_npr_pooled_components"], errors="coerce"))
    )
    scored_positive = merged["_space_by_tokens_scored"].gt(0)

    diagnostics = {
        "a01_primary_rows": int(len(primary)),
        "a02_score_rows": int(len(a02_code)),
        "a02_extra_rows": int(len(a02_extra)),
        "a01_primary_rows_with_a02_score": int(matched.sum()),
        "a01_primary_rows_without_a02_score": int((~matched).sum()),
        "token_total_mismatch_rows": int(token_total_mismatch.sum()),
        "scored_rows_with_nonfinite_components": int((scored_positive & ~score_finite_mask).sum()),
        "scored_tokens_exceed_total_rows": int((merged["_space_by_tokens_scored"] > merged["_space_by_tokens_total"]).sum()),
        "a02_extra_examples": a02_extra.head(10).to_dict("records"),
    }
    return merged, diagnostics


def build_file_scores(a01_files: pd.DataFrame, unit_table: pd.DataFrame) -> pd.DataFrame:
    agg = aggregate_by(unit_table, FILE_KEY) if not unit_table.empty else pd.DataFrame(columns=FILE_KEY)
    files = a01_files.copy().rename(columns={"primary_code_units": "a01_primary_code_units_manifest"})
    if files.duplicated(FILE_KEY).any():
        raise ValueError("A01 file manifest contains duplicate snapshot/file keys.")
    output = files.merge(agg, on=FILE_KEY, how="left", validate="one_to_one")

    integer_fill = [
        "primary_code_units",
        "primary_code_units_with_a02_record",
        "primary_code_units_fully_scored",
        "primary_code_units_partially_scored",
        "primary_code_units_unscored",
        "space_by_tokens_total",
        "space_by_tokens_scored",
        "space_by_tokens_used_for_npr",
        "llm_tokens_original_total",
        "llm_tokens_original_valid_windows_total",
    ]
    for column in integer_fill:
        if column not in output.columns:
            output[column] = 0
        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0).astype(int)

    output["python_lines"] = pd.to_numeric(output["physical_line_count"], errors="coerce").fillna(0).astype(int)
    output["file_npr_space_by_token_weighted"] = output.get("npr_space_by_token_weighted")
    output["file_original_log_rank_space_by_token_weighted"] = output.get(
        "original_log_rank_space_by_token_weighted"
    )
    output["file_mean_perturbed_log_rank_space_by_token_weighted"] = output.get(
        "mean_perturbed_log_rank_space_by_token_weighted"
    )
    output["file_npr_pooled_components"] = output.get("npr_pooled_components")

    drop_columns = [
        "npr_space_by_token_weighted",
        "original_log_rank_space_by_token_weighted",
        "mean_perturbed_log_rank_space_by_token_weighted",
        "npr_pooled_components",
    ]
    output = output.drop(columns=[column for column in drop_columns if column in output.columns])
    return output


def build_snapshot_scores(a01_snapshots: pd.DataFrame, a01_files: pd.DataFrame, unit_table: pd.DataFrame) -> pd.DataFrame:
    agg = aggregate_by(unit_table, SNAPSHOT_KEY) if not unit_table.empty else pd.DataFrame(columns=SNAPSHOT_KEY)
    file_counts = (
        a01_files.groupby("snapshot_id", sort=False)
        .agg(
            python_files=("relative_path", "size"),
            python_files_prepared_from_file_manifest=("parse_status", lambda values: int(values.astype(str).eq("prepared").sum())),
        )
        .reset_index()
    )

    snapshots = a01_snapshots.copy().rename(columns={"primary_code_units": "a01_primary_code_units_manifest"})
    if snapshots.duplicated(SNAPSHOT_KEY).any():
        raise ValueError("A01 snapshot manifest contains duplicate snapshot_id values.")
    output = snapshots.merge(file_counts, on="snapshot_id", how="left", validate="one_to_one")
    output = output.merge(agg, on="snapshot_id", how="left", validate="one_to_one")

    integer_fill = [
        "python_files",
        "python_files_prepared_from_file_manifest",
        "primary_code_units",
        "primary_code_units_with_a02_record",
        "primary_code_units_fully_scored",
        "primary_code_units_partially_scored",
        "primary_code_units_unscored",
        "space_by_tokens_total",
        "space_by_tokens_scored",
        "space_by_tokens_used_for_npr",
        "llm_tokens_original_total",
        "llm_tokens_original_valid_windows_total",
    ]
    for column in integer_fill:
        if column not in output.columns:
            output[column] = 0
        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0).astype(int)

    output["snapshot_npr_space_by_token_weighted"] = output.get("npr_space_by_token_weighted")
    output["snapshot_original_log_rank_space_by_token_weighted"] = output.get(
        "original_log_rank_space_by_token_weighted"
    )
    output["snapshot_mean_perturbed_log_rank_space_by_token_weighted"] = output.get(
        "mean_perturbed_log_rank_space_by_token_weighted"
    )
    output["snapshot_npr_pooled_components"] = output.get("npr_pooled_components")

    drop_columns = [
        "npr_space_by_token_weighted",
        "original_log_rank_space_by_token_weighted",
        "mean_perturbed_log_rank_space_by_token_weighted",
        "npr_pooled_components",
    ]
    output = output.drop(columns=[column for column in drop_columns if column in output.columns])
    return output


def build_reconciliation(
    a01_snapshots: pd.DataFrame,
    a01_files: pd.DataFrame,
    unit_table: pd.DataFrame,
    file_scores: pd.DataFrame,
    snapshot_scores: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    file_expected = a01_files.set_index(FILE_KEY)
    file_observed = file_scores.set_index(FILE_KEY)
    unit_file = (
        unit_table.groupby(FILE_KEY, sort=False)
        .agg(
            primary_units_from_code_manifest=("code_unit_id", "size"),
            space_by_tokens_from_code_manifest=("_space_by_tokens_total", "sum"),
        )
        if not unit_table.empty
        else pd.DataFrame()
    )

    for key, file_row in file_expected.iterrows():
        observed = file_observed.loc[key]
        if key in unit_file.index:
            unit_count = int(unit_file.loc[key, "primary_units_from_code_manifest"])
            token_count = int(unit_file.loc[key, "space_by_tokens_from_code_manifest"])
        else:
            unit_count = 0
            token_count = 0
        rows.append(
            {
                "level": "file",
                "snapshot_id": key[0],
                "relative_path": key[1],
                "file_sha256": key[2],
                "expected_primary_code_units": int(file_row["primary_code_units"]),
                "observed_primary_code_units": unit_count,
                "expected_space_by_tokens": token_count,
                "observed_space_by_tokens": int(observed["space_by_tokens_total"]),
                "primary_code_unit_difference": unit_count - int(file_row["primary_code_units"]),
                "space_by_token_difference": int(observed["space_by_tokens_total"]) - token_count,
            }
        )

    snapshot_unit = (
        unit_table.groupby("snapshot_id", sort=False)
        .agg(
            primary_units_from_code_manifest=("code_unit_id", "size"),
            space_by_tokens_from_code_manifest=("_space_by_tokens_total", "sum"),
        )
        .reset_index()
        if not unit_table.empty
        else pd.DataFrame(columns=["snapshot_id", "primary_units_from_code_manifest", "space_by_tokens_from_code_manifest"])
    )
    snapshot_file = (
        file_scores.groupby("snapshot_id", sort=False)
        .agg(
            primary_units_from_files=("primary_code_units", "sum"),
            space_by_tokens_from_files=("space_by_tokens_total", "sum"),
            space_by_tokens_scored_from_files=("space_by_tokens_scored", "sum"),
        )
        .reset_index()
    )
    snapshot_lookup = snapshot_scores.set_index("snapshot_id")
    unit_lookup = snapshot_unit.set_index("snapshot_id")
    file_lookup = snapshot_file.set_index("snapshot_id")

    for _, snapshot in a01_snapshots.iterrows():
        snapshot_id = snapshot["snapshot_id"]
        observed = snapshot_lookup.loc[snapshot_id]
        unit_count = int(unit_lookup.loc[snapshot_id, "primary_units_from_code_manifest"]) if snapshot_id in unit_lookup.index else 0
        unit_tokens = int(unit_lookup.loc[snapshot_id, "space_by_tokens_from_code_manifest"]) if snapshot_id in unit_lookup.index else 0
        file_units = int(file_lookup.loc[snapshot_id, "primary_units_from_files"]) if snapshot_id in file_lookup.index else 0
        file_tokens = int(file_lookup.loc[snapshot_id, "space_by_tokens_from_files"]) if snapshot_id in file_lookup.index else 0
        file_scored = int(file_lookup.loc[snapshot_id, "space_by_tokens_scored_from_files"]) if snapshot_id in file_lookup.index else 0
        rows.append(
            {
                "level": "snapshot",
                "snapshot_id": snapshot_id,
                "relative_path": "",
                "file_sha256": "",
                "expected_primary_code_units": int(snapshot["primary_code_units"]),
                "observed_primary_code_units": int(observed["primary_code_units"]),
                "expected_space_by_tokens": int(snapshot["space_by_tokens_primary"]),
                "observed_space_by_tokens": int(observed["space_by_tokens_total"]),
                "primary_code_unit_difference": int(observed["primary_code_units"]) - int(snapshot["primary_code_units"]),
                "space_by_token_difference": int(observed["space_by_tokens_total"]) - int(snapshot["space_by_tokens_primary"]),
                "code_manifest_primary_units": unit_count,
                "code_manifest_space_by_tokens": unit_tokens,
                "file_aggregate_primary_units": file_units,
                "file_aggregate_space_by_tokens": file_tokens,
                "file_aggregate_space_by_tokens_scored": file_scored,
                "snapshot_space_by_tokens_scored": int(observed["space_by_tokens_scored"]),
            }
        )

    return pd.DataFrame(rows)


def build_checks(
    a01_snapshots: pd.DataFrame,
    a01_files: pd.DataFrame,
    a01_code: pd.DataFrame,
    a02_code: pd.DataFrame,
    a02_windows: pd.DataFrame,
    unit_table: pd.DataFrame,
    diagnostics: dict[str, Any],
    file_scores: pd.DataFrame,
    snapshot_scores: pd.DataFrame,
    reconciliation: pd.DataFrame,
    expected_snapshots: int | None,
    require_full_coverage: bool,
    tolerance: float,
) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []
    primary = a01_code.loc[a01_code["aggregation_role"].astype(str).eq(PRIMARY_ROLE)].copy()

    add_check(checks, "snapshot_output_row_count", len(snapshot_scores) == len(a01_snapshots), len(snapshot_scores), len(a01_snapshots), "A03 must preserve every A01 snapshot row.")
    if expected_snapshots is not None:
        add_check(checks, "expected_snapshot_count", len(snapshot_scores) == expected_snapshots, len(snapshot_scores), expected_snapshots, "Prototype/full-run expected snapshot count supplied by wrapper.")
    add_check(checks, "file_output_row_count", len(file_scores) == len(a01_files), len(file_scores), len(a01_files), "A03 must preserve every A01 file row.")
    add_check(checks, "a01_primary_code_units_nonempty", len(primary) > 0, len(primary), "> 0", "Primary aggregation must have A01 primary code-unit occurrences.")
    add_check(checks, "a02_no_extra_occurrence_scores", diagnostics["a02_extra_rows"] == 0, diagnostics["a02_extra_rows"], 0, "A02 occurrence scores must belong to A01 primary code units.")
    add_check(checks, "a01_a02_space_by_token_total_match", diagnostics["token_total_mismatch_rows"] == 0, diagnostics["token_total_mismatch_rows"], 0, "A02 code-unit token totals must equal A01 space-by-token counts.")
    add_check(checks, "a02_scored_components_finite", diagnostics["scored_rows_with_nonfinite_components"] == 0, diagnostics["scored_rows_with_nonfinite_components"], 0, "Every positively scored code unit must retain finite NPR numerator/denominator components.")
    add_check(checks, "a02_scored_tokens_not_above_total", diagnostics["scored_tokens_exceed_total_rows"] == 0, diagnostics["scored_tokens_exceed_total_rows"], 0, "Scored space-by tokens cannot exceed source tokens.")

    file_recon = reconciliation.loc[reconciliation["level"].eq("file")]
    snapshot_recon = reconciliation.loc[reconciliation["level"].eq("snapshot")]
    add_check(checks, "file_primary_code_unit_reconciliation", bool(file_recon["primary_code_unit_difference"].eq(0).all()), int((~file_recon["primary_code_unit_difference"].eq(0)).sum()), 0, "A01 file manifest primary counts must reconcile with primary code-unit occurrences.")
    add_check(checks, "file_space_by_token_reconciliation", bool(file_recon["space_by_token_difference"].eq(0).all()), int((~file_recon["space_by_token_difference"].eq(0)).sum()), 0, "File output token totals must reconcile with primary code units.")
    add_check(checks, "snapshot_primary_code_unit_reconciliation", bool(snapshot_recon["primary_code_unit_difference"].eq(0).all()), int((~snapshot_recon["primary_code_unit_difference"].eq(0)).sum()), 0, "Snapshot output primary-unit counts must reconcile with A01 snapshot manifest.")
    add_check(checks, "snapshot_space_by_token_reconciliation", bool(snapshot_recon["space_by_token_difference"].eq(0).all()), int((~snapshot_recon["space_by_token_difference"].eq(0)).sum()), 0, "Snapshot output token totals must reconcile with A01 snapshot manifest.")

    file_to_snapshot_tokens_ok = bool(
        snapshot_recon["file_aggregate_space_by_tokens"].astype(int).eq(snapshot_recon["observed_space_by_tokens"].astype(int)).all()
    )
    file_to_snapshot_scored_ok = bool(
        snapshot_recon["file_aggregate_space_by_tokens_scored"].astype(int).eq(snapshot_recon["snapshot_space_by_tokens_scored"].astype(int)).all()
    )
    add_check(checks, "file_to_snapshot_total_token_reconciliation", file_to_snapshot_tokens_ok, int((~snapshot_recon["file_aggregate_space_by_tokens"].astype(int).eq(snapshot_recon["observed_space_by_tokens"].astype(int))).sum()), 0, "File totals must sum exactly to snapshot totals.")
    add_check(checks, "file_to_snapshot_scored_token_reconciliation", file_to_snapshot_scored_ok, int((~snapshot_recon["file_aggregate_space_by_tokens_scored"].astype(int).eq(snapshot_recon["snapshot_space_by_tokens_scored"].astype(int))).sum()), 0, "File scored-token totals must sum exactly to snapshot scored-token totals.")

    file_coverage = pd.to_numeric(file_scores["npr_coverage_ratio"], errors="coerce")
    snapshot_coverage = pd.to_numeric(snapshot_scores["npr_coverage_ratio"], errors="coerce")
    file_nonempty = file_scores["space_by_tokens_total"].gt(0)
    snapshot_nonempty = snapshot_scores["space_by_tokens_total"].gt(0)
    file_coverage_ok = bool(file_coverage.loc[file_nonempty].between(0.0, 1.0, inclusive="both").all())
    snapshot_coverage_ok = bool(snapshot_coverage.loc[snapshot_nonempty].between(0.0, 1.0, inclusive="both").all())
    add_check(checks, "file_coverage_bounds", file_coverage_ok, int((~file_coverage.loc[file_nonempty].between(0.0, 1.0, inclusive="both")).sum()), 0, "Nonempty file coverage must lie in [0,1].")
    add_check(checks, "snapshot_coverage_bounds", snapshot_coverage_ok, int((~snapshot_coverage.loc[snapshot_nonempty].between(0.0, 1.0, inclusive="both")).sum()), 0, "Nonempty snapshot coverage must lie in [0,1].")

    scored_vs_used_file = file_scores["space_by_tokens_scored"].astype(int).eq(file_scores["space_by_tokens_used_for_npr"].astype(int))
    scored_vs_used_snapshot = snapshot_scores["space_by_tokens_scored"].astype(int).eq(snapshot_scores["space_by_tokens_used_for_npr"].astype(int))
    add_check(checks, "all_scored_file_tokens_used_for_npr", bool(scored_vs_used_file.all()), int((~scored_vs_used_file).sum()), 0, "No scored tokens should be dropped because of nonfinite aggregate components.")
    add_check(checks, "all_scored_snapshot_tokens_used_for_npr", bool(scored_vs_used_snapshot.all()), int((~scored_vs_used_snapshot).sum()), 0, "No scored tokens should be dropped because of nonfinite aggregate components.")

    finite_snapshot = snapshot_scores.loc[snapshot_scores["space_by_tokens_used_for_npr"].gt(0)]
    finite_columns = ["snapshot_npr_space_by_token_weighted", "snapshot_npr_pooled_components"]
    finite_ok = all(np.isfinite(pd.to_numeric(finite_snapshot[column], errors="coerce")).all() for column in finite_columns)
    add_check(checks, "finite_snapshot_npr", bool(finite_ok), int(len(finite_snapshot)), "all finite", "Every snapshot with scored source must have finite continuous NPR summaries.")

    pooled_expected = pd.to_numeric(snapshot_scores["snapshot_mean_perturbed_log_rank_space_by_token_weighted"], errors="coerce") / pd.to_numeric(snapshot_scores["snapshot_original_log_rank_space_by_token_weighted"], errors="coerce")
    pooled_actual = pd.to_numeric(snapshot_scores["snapshot_npr_pooled_components"], errors="coerce")
    pooled_mask = snapshot_scores["space_by_tokens_used_for_npr"].gt(0)
    pooled_diff = (pooled_expected.loc[pooled_mask] - pooled_actual.loc[pooled_mask]).abs()
    pooled_ok = bool((pooled_diff <= tolerance).all()) if not pooled_diff.empty else True
    add_check(checks, "snapshot_pooled_component_formula", pooled_ok, float(pooled_diff.max()) if not pooled_diff.empty else 0.0, f"<= {tolerance}", "Pooled NPR must equal aggregated perturbed log-rank divided by aggregated original log-rank.")

    fingerprint_values = sorted(set(a02_code["config_fingerprint"].dropna().astype(str)))
    window_fingerprint_values = sorted(set(a02_windows["config_fingerprint"].dropna().astype(str)))
    add_check(checks, "single_a02_code_unit_config_fingerprint", len(fingerprint_values) == 1, fingerprint_values, "exactly one", "All A02 occurrence scores should use one scoring configuration.")
    add_check(checks, "single_a02_window_config_fingerprint", len(window_fingerprint_values) == 1, window_fingerprint_values, "exactly one", "All A02 window scores should use one scoring configuration.")
    add_check(checks, "a02_code_window_fingerprint_match", fingerprint_values == window_fingerprint_values, {"code": fingerprint_values, "window": window_fingerprint_values}, "equal", "A02 code-unit and window outputs must refer to the same scoring configuration.")

    forbidden = [column for column in list(a02_code.columns) + list(file_scores.columns) + list(snapshot_scores.columns) if column.lower() in {"agc_like", "hwc_like", "agc_threshold", "decision_rule"}]
    add_check(checks, "no_agc_hwc_classification_columns", len(forbidden) == 0, forbidden, [], "A03 is continuous NPR measurement only.")

    if require_full_coverage:
        missing_scores = diagnostics["a01_primary_rows_without_a02_score"]
        full_file = bool(file_scores.loc[file_nonempty, "space_by_tokens_scored"].astype(int).eq(file_scores.loc[file_nonempty, "space_by_tokens_total"].astype(int)).all())
        full_snapshot = bool(snapshot_scores.loc[snapshot_nonempty, "space_by_tokens_scored"].astype(int).eq(snapshot_scores.loc[snapshot_nonempty, "space_by_tokens_total"].astype(int)).all())
        add_check(checks, "full_a02_occurrence_coverage_required", missing_scores == 0, missing_scores, 0, "Prototype wrapper requires every A01 primary occurrence to have an A02 score.")
        add_check(checks, "full_file_token_coverage_required", full_file, int((file_scores.loc[file_nonempty, "space_by_tokens_scored"].astype(int) != file_scores.loc[file_nonempty, "space_by_tokens_total"].astype(int)).sum()), 0, "Prototype wrapper requires 100% file-level source-token coverage.")
        add_check(checks, "full_snapshot_token_coverage_required", full_snapshot, int((snapshot_scores.loc[snapshot_nonempty, "space_by_tokens_scored"].astype(int) != snapshot_scores.loc[snapshot_nonempty, "space_by_tokens_total"].astype(int)).sum()), 0, "Prototype wrapper requires 100% snapshot-level source-token coverage.")

    return pd.DataFrame(checks)


def run_self_test() -> None:
    snapshots = pd.DataFrame(
        [
            {
                "snapshot_order": 0,
                "snapshot_id": "s1",
                "dataset_source": "control",
                "repo_name": "owner/repo",
                "repo_key": "owner/repo",
                "snapshot_time": "2025-01",
                "snapshot_commit": "abc",
                "python_files_discovered": 2,
                "python_files_prepared": 2,
                "primary_code_units": 3,
                "space_by_tokens_primary": 175,
            }
        ]
    )
    files = pd.DataFrame(
        [
            {
                "snapshot_order": 0,
                "snapshot_id": "s1",
                "dataset_source": "control",
                "repo_name": "owner/repo",
                "repo_key": "owner/repo",
                "snapshot_time": "2025-01",
                "snapshot_commit": "abc",
                "relative_path": "a.py",
                "file_sha256": "fa",
                "physical_line_count": 20,
                "parse_status": "ok",
                "primary_code_units": 2,
            },
            {
                "snapshot_order": 0,
                "snapshot_id": "s1",
                "dataset_source": "control",
                "repo_name": "owner/repo",
                "repo_key": "owner/repo",
                "snapshot_time": "2025-01",
                "snapshot_commit": "abc",
                "relative_path": "b.py",
                "file_sha256": "fb",
                "physical_line_count": 10,
                "parse_status": "ok",
                "primary_code_units": 1,
            },
        ]
    )
    code = pd.DataFrame(
        [
            {"snapshot_id": "s1", "relative_path": "a.py", "file_sha256": "fa", "code_unit_id": "u1", "code_unit_type": "function_body", "aggregation_role": "primary", "code_unit_sha256": "h1", "space_by_token_count": 100, "physical_line_count": 10},
            {"snapshot_id": "s1", "relative_path": "a.py", "file_sha256": "fa", "code_unit_id": "u2", "code_unit_type": "module_block", "aggregation_role": "primary", "code_unit_sha256": "h2", "space_by_token_count": 50, "physical_line_count": 5},
            {"snapshot_id": "s1", "relative_path": "b.py", "file_sha256": "fb", "code_unit_id": "u3", "code_unit_type": "function_body", "aggregation_role": "primary", "code_unit_sha256": "h3", "space_by_token_count": 25, "physical_line_count": 5},
        ]
    )
    scores = pd.DataFrame(
        [
            {"snapshot_id": "s1", "relative_path": "a.py", "file_sha256": "fa", "code_unit_id": "u1", "code_unit_sha256": "h1", "space_by_tokens_total": 100, "space_by_tokens_scored": 100, "npr_coverage_ratio": 1.0, "original_llm_tokens_all_windows": 120, "original_llm_tokens_valid_windows": 120, "code_unit_npr_space_by_token_weighted": 1.2, "code_unit_original_log_rank_weighted": 2.0, "code_unit_mean_perturbed_log_rank_weighted": 2.4, "code_unit_npr_pooled_components": 1.2, "partial_code_unit_score": 0, "status": "scored", "config_fingerprint": "fp"},
            {"snapshot_id": "s1", "relative_path": "a.py", "file_sha256": "fa", "code_unit_id": "u2", "code_unit_sha256": "h2", "space_by_tokens_total": 50, "space_by_tokens_scored": 25, "npr_coverage_ratio": 0.5, "original_llm_tokens_all_windows": 80, "original_llm_tokens_valid_windows": 40, "code_unit_npr_space_by_token_weighted": 1.4, "code_unit_original_log_rank_weighted": 1.0, "code_unit_mean_perturbed_log_rank_weighted": 1.4, "code_unit_npr_pooled_components": 1.4, "partial_code_unit_score": 1, "status": "scored", "config_fingerprint": "fp"},
            {"snapshot_id": "s1", "relative_path": "b.py", "file_sha256": "fb", "code_unit_id": "u3", "code_unit_sha256": "h3", "space_by_tokens_total": 25, "space_by_tokens_scored": 25, "npr_coverage_ratio": 1.0, "original_llm_tokens_all_windows": 30, "original_llm_tokens_valid_windows": 30, "code_unit_npr_space_by_token_weighted": 0.8, "code_unit_original_log_rank_weighted": 2.0, "code_unit_mean_perturbed_log_rank_weighted": 1.6, "code_unit_npr_pooled_components": 0.8, "partial_code_unit_score": 0, "status": "scored", "config_fingerprint": "fp"},
        ]
    )

    unit_table, diagnostics = prepare_unit_table(code, scores)
    assert diagnostics["a02_extra_rows"] == 0
    file_scores = build_file_scores(files, unit_table)
    snapshot_scores = build_snapshot_scores(snapshots, files, unit_table)

    a = file_scores.loc[file_scores["relative_path"].eq("a.py")].iloc[0]
    assert int(a["space_by_tokens_total"]) == 150
    assert int(a["space_by_tokens_scored"]) == 125
    assert math.isclose(float(a["file_npr_space_by_token_weighted"]), 1.24, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(float(a["file_npr_pooled_components"]), 2.2 / 1.8, rel_tol=0, abs_tol=1e-12)

    s = snapshot_scores.iloc[0]
    assert int(s["space_by_tokens_total"]) == 175
    assert int(s["space_by_tokens_scored"]) == 150
    assert math.isclose(float(s["snapshot_npr_space_by_token_weighted"]), 175.0 / 150.0, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(float(s["snapshot_npr_pooled_components"]), 2.1 / (275.0 / 150.0), rel_tol=0, abs_tol=1e-12)

    # Diagnostic overlap must never enter primary aggregation.
    diagnostic = code.iloc[[0]].copy()
    diagnostic["aggregation_role"] = "diagnostic_overlap"
    diagnostic["code_unit_id"] = "u4"
    diagnostic["code_unit_sha256"] = "h4"
    code_with_diagnostic = pd.concat([code, diagnostic], ignore_index=True)
    unit_table2, _ = prepare_unit_table(code_with_diagnostic, scores)
    assert len(unit_table2) == 3

    print("SELF-TEST PASS: A03 weighted aggregation, pooled components, partial coverage, and primary-role filtering.")


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0

    started = time.perf_counter()
    input_paths = {
        "a01_snapshot_manifest": args.a01_snapshot_manifest,
        "a01_file_manifest": args.a01_file_manifest,
        "a01_code_unit_manifest": args.a01_code_unit_manifest,
        "a02_code_unit_scores": args.a02_code_unit_scores,
        "a02_window_scores": args.a02_window_scores,
    }
    for label, path in input_paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"Missing {label}: {path}")

    output_dir = args.output_dir
    qc_dir = output_dir / "qc"
    outputs = {
        "file_scores": output_dir / "python_file_npr_scores.csv",
        "snapshot_scores": output_dir / "python_snapshot_npr_scores.csv",
        "reconciliation": qc_dir / "python_snapshot_npr_aggregation_reconciliation.csv",
        "checks": qc_dir / "python_snapshot_npr_aggregation_checks.csv",
        "summary": qc_dir / "python_snapshot_npr_aggregation_summary.json",
        "metadata": qc_dir / "python_snapshot_npr_aggregation_metadata.json",
    }

    existing = [path for path in outputs.values() if path.exists()]
    if existing and not args.overwrite:
        raise FileExistsError(
            "A03 output files already exist. Use --overwrite after reviewing them: "
            + ", ".join(str(path) for path in existing)
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    qc_dir.mkdir(parents=True, exist_ok=True)

    a01_snapshots = pd.read_csv(args.a01_snapshot_manifest)
    a01_files = pd.read_csv(args.a01_file_manifest)
    a01_code = pd.read_csv(args.a01_code_unit_manifest)
    a02_code = pd.read_csv(args.a02_code_unit_scores)
    a02_windows = pd.read_csv(args.a02_window_scores)

    require_columns(a01_snapshots, A01_SNAPSHOT_REQUIRED, "A01 snapshot manifest")
    require_columns(a01_files, A01_FILE_REQUIRED, "A01 file manifest")
    require_columns(a01_code, A01_CODE_REQUIRED, "A01 code-unit manifest")
    require_columns(a02_code, A02_CODE_REQUIRED, "A02 code-unit scores")
    require_columns(a02_windows, A02_WINDOW_REQUIRED, "A02 window scores")

    unit_table, diagnostics = prepare_unit_table(a01_code, a02_code)
    file_scores = build_file_scores(a01_files, unit_table)
    snapshot_scores = build_snapshot_scores(a01_snapshots, a01_files, unit_table)
    reconciliation = build_reconciliation(a01_snapshots, a01_files, unit_table, file_scores, snapshot_scores)
    checks = build_checks(
        a01_snapshots,
        a01_files,
        a01_code,
        a02_code,
        a02_windows,
        unit_table,
        diagnostics,
        file_scores,
        snapshot_scores,
        reconciliation,
        args.expected_snapshots,
        args.require_full_coverage,
        args.tolerance,
    )

    hard_failures = checks.loc[checks["severity"].eq("hard") & ~checks["passed"]]
    warning_failures = checks.loc[checks["severity"].eq("warning") & ~checks["passed"]]
    status = "PASS" if hard_failures.empty else "FAIL"

    # Stable and analysis-friendly column order. Additional A01 provenance columns
    # remain available after these preferred columns.
    file_front = [
        "snapshot_order", "snapshot_id", "dataset_source", "repo_name", "repo_key",
        "snapshot_time", "snapshot_commit", "relative_path", "file_sha256", "python_lines",
        "parse_status", "primary_code_units", "primary_code_units_with_a02_record",
        "primary_code_units_fully_scored", "primary_code_units_partially_scored",
        "primary_code_units_unscored", "space_by_tokens_total", "space_by_tokens_scored",
        "space_by_tokens_used_for_npr", "npr_coverage_ratio", "npr_effective_coverage_ratio",
        "llm_tokens_original_total", "llm_tokens_original_valid_windows_total",
        "file_npr_space_by_token_weighted", "file_original_log_rank_space_by_token_weighted",
        "file_mean_perturbed_log_rank_space_by_token_weighted", "file_npr_pooled_components",
    ]
    file_scores = file_scores[[column for column in file_front if column in file_scores.columns] + [column for column in file_scores.columns if column not in file_front]]

    snapshot_front = [
        "snapshot_order", "snapshot_id", "dataset_source", "repo_name", "repo_key",
        "snapshot_time", "snapshot_commit", "repo_month_rows", "first_panel_month", "last_panel_month",
        "python_files", "python_files_prepared_from_file_manifest", "primary_code_units",
        "primary_code_units_with_a02_record", "primary_code_units_fully_scored",
        "primary_code_units_partially_scored", "primary_code_units_unscored",
        "space_by_tokens_total", "space_by_tokens_scored", "space_by_tokens_used_for_npr",
        "npr_coverage_ratio", "npr_effective_coverage_ratio", "llm_tokens_original_total",
        "llm_tokens_original_valid_windows_total", "snapshot_npr_space_by_token_weighted",
        "snapshot_original_log_rank_space_by_token_weighted",
        "snapshot_mean_perturbed_log_rank_space_by_token_weighted", "snapshot_npr_pooled_components",
    ]
    snapshot_scores = snapshot_scores[[column for column in snapshot_front if column in snapshot_scores.columns] + [column for column in snapshot_scores.columns if column not in snapshot_front]]

    atomic_write_csv(file_scores, outputs["file_scores"])
    atomic_write_csv(snapshot_scores, outputs["snapshot_scores"])
    atomic_write_csv(reconciliation, outputs["reconciliation"])
    atomic_write_csv(checks, outputs["checks"])

    total_tokens = int(snapshot_scores["space_by_tokens_total"].sum())
    scored_tokens = int(snapshot_scores["space_by_tokens_scored"].sum())
    used_tokens = int(snapshot_scores["space_by_tokens_used_for_npr"].sum())
    fingerprints = sorted(set(a02_code["config_fingerprint"].dropna().astype(str)))
    a02_metadata = read_json_if_exists(args.a02_metadata)

    summary = {
        "status": status,
        "implementation_version": IMPLEMENTATION_VERSION,
        "snapshots": int(len(snapshot_scores)),
        "python_files": int(len(file_scores)),
        "primary_code_unit_occurrences": int(len(unit_table)),
        "primary_occurrences_with_a02_score": int(unit_table["_a02_score_present"].sum()),
        "primary_occurrences_without_a02_score": int((~unit_table["_a02_score_present"]).sum()),
        "space_by_tokens_total": total_tokens,
        "space_by_tokens_scored": scored_tokens,
        "space_by_tokens_used_for_npr": used_tokens,
        "npr_coverage_ratio": float(scored_tokens / total_tokens) if total_tokens else None,
        "npr_effective_coverage_ratio": float(used_tokens / total_tokens) if total_tokens else None,
        "file_rows_with_npr": int(file_scores["file_npr_space_by_token_weighted"].notna().sum()),
        "snapshot_rows_with_npr": int(snapshot_scores["snapshot_npr_space_by_token_weighted"].notna().sum()),
        "a02_config_fingerprints": fingerprints,
        "expected_snapshots": args.expected_snapshots,
        "require_full_coverage": bool(args.require_full_coverage),
        "hard_checks_failed": int(len(hard_failures)),
        "warning_checks_failed": int(len(warning_failures)),
        "elapsed_seconds": float(time.perf_counter() - started),
    }

    metadata = {
        "implementation_version": IMPLEMENTATION_VERSION,
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
        "aggregation_semantics": {
            "primary_source_role": PRIMARY_ROLE,
            "primary_weight_coordinate": "space-by tokens",
            "space_by_token_definition": "text.split(\" \") coordinate produced by A01/A02",
            "file_ratio_weighted_npr": "sum(code_unit_npr * code_unit_space_by_tokens_scored) / sum(code_unit_space_by_tokens_scored)",
            "snapshot_ratio_weighted_npr": "same rule applied across primary code-unit occurrences in a snapshot",
            "pooled_component_npr": "weighted mean perturbed log-rank / weighted mean original log-rank using scored space-by-token weights",
            "llm_token_counts": "diagnostic workload counts summed from A02 windows; overlap windows may repeat source context and these counts are not aggregation weights",
            "direct_whole_file_or_snapshot_scoring": False,
            "agc_hwc_classification": False,
        },
        "input_files": {
            label: {"path": str(path), "sha256": sha256_file(path)} for label, path in input_paths.items()
        },
        "a02_metadata_path": str(args.a02_metadata) if args.a02_metadata else None,
        "a02_metadata": a02_metadata,
        "a02_config_fingerprints": fingerprints,
        "output_files": {label: str(path) for label, path in outputs.items()},
        "diagnostics": diagnostics,
        "expected_snapshots": args.expected_snapshots,
        "require_full_coverage": bool(args.require_full_coverage),
        "tolerance": float(args.tolerance),
    }

    atomic_write_json(summary, outputs["summary"])
    atomic_write_json(metadata, outputs["metadata"])

    print("============================================================================")
    print("run-x-a03: file/snapshot NPR aggregation")
    print(f"Status:                         {status}")
    print(f"Snapshots:                      {len(snapshot_scores)}")
    print(f"Python files:                   {len(file_scores)}")
    print(f"Primary code-unit occurrences:  {len(unit_table)}")
    print(f"A02 score records matched:      {int(unit_table['_a02_score_present'].sum())}")
    print(f"Space-by tokens total:          {total_tokens}")
    print(f"Space-by tokens scored:         {scored_tokens}")
    print(f"NPR coverage ratio:             {(scored_tokens / total_tokens) if total_tokens else float('nan'):.12f}")
    print(f"Hard QC failures:               {len(hard_failures)}")
    print(f"Warning QC failures:            {len(warning_failures)}")
    print(f"File output:                    {outputs['file_scores']}")
    print(f"Snapshot output:                {outputs['snapshot_scores']}")
    print("============================================================================")

    if not hard_failures.empty:
        print("Hard QC failures:", file=sys.stderr)
        print(hard_failures[["check_name", "observed", "expected", "detail"]].to_string(index=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
