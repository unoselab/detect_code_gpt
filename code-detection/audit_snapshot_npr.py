#!/usr/bin/env python3
"""Audit the A01 -> A02 -> A03 snapshot NPR measurement pipeline.

A04 is an independent, CPU-only reconciliation stage. It does not parse Python
source with AST and does not run the scoring model. It verifies source artifacts,
space-by-token windows, NPR score formulas, cache consistency, aggregation, and
cross-stage provenance.

Delivery name:
    code-detection/audit_snapshot_npr-v1.py

Canonical server name after removing the delivery version suffix:
    code-detection/audit_snapshot_npr.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

IMPLEMENTATION_VERSION = "run-x-a04-v1"
PRIMARY_ROLE = "primary"
DEFAULT_TOLERANCE = 1e-12

CODE_UNIT_KEY = ["snapshot_id", "relative_path", "file_sha256", "code_unit_id"]
FILE_KEY = ["snapshot_id", "relative_path", "file_sha256"]

CHECK_COLUMNS = [
    "severity",
    "stage",
    "check_name",
    "passed",
    "observed",
    "expected",
    "detail",
]

RECON_COLUMNS = [
    "stage",
    "level",
    "snapshot_id",
    "relative_path",
    "code_unit_sha256",
    "metric",
    "expected",
    "observed",
    "difference",
    "passed",
]

ANOMALY_COLUMNS = [
    "severity",
    "stage",
    "entity_type",
    "entity_id",
    "issue_type",
    "observed",
    "expected",
    "detail",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit A01/A02/A03 snapshot NPR outputs.")
    parser.add_argument("--a01-dir", required=False, type=Path)
    parser.add_argument("--a02-dir", required=False, type=Path)
    parser.add_argument("--a03-dir", required=False, type=Path)
    parser.add_argument("--output-dir", required=False, type=Path)
    parser.add_argument("--expected-snapshots", type=int, default=None)
    parser.add_argument("--require-full-coverage", action="store_true")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def encode_json(value: Any) -> str:
    return json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return read_json(path)


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")


def require_columns(df: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def as_bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "pass", "passed"}


def finite(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def close_number(expected: Any, observed: Any, tolerance: float) -> tuple[bool, float | None]:
    if not finite(expected) or not finite(observed):
        if pd.isna(expected) and pd.isna(observed):
            return True, None
        return False, None
    exp = float(expected)
    obs = float(observed)
    diff = obs - exp
    scale = max(1.0, abs(exp), abs(obs))
    return abs(diff) <= tolerance * scale, diff


def add_check(
    checks: list[dict[str, Any]],
    severity: str,
    stage: str,
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> None:
    checks.append(
        {
            "severity": severity,
            "stage": stage,
            "check_name": name,
            "passed": bool(passed),
            "observed": encode_json(observed),
            "expected": encode_json(expected),
            "detail": detail,
        }
    )


def add_recon(
    reconciliation: list[dict[str, Any]],
    stage: str,
    level: str,
    metric: str,
    expected: Any,
    observed: Any,
    passed: bool,
    difference: Any = None,
    snapshot_id: str = "",
    relative_path: str = "",
    code_unit_sha256: str = "",
) -> None:
    reconciliation.append(
        {
            "stage": stage,
            "level": level,
            "snapshot_id": snapshot_id,
            "relative_path": relative_path,
            "code_unit_sha256": code_unit_sha256,
            "metric": metric,
            "expected": json_safe(expected),
            "observed": json_safe(observed),
            "difference": json_safe(difference),
            "passed": bool(passed),
        }
    )


def add_anomaly(
    anomalies: list[dict[str, Any]],
    severity: str,
    stage: str,
    entity_type: str,
    entity_id: str,
    issue_type: str,
    observed: Any,
    expected: Any,
    detail: str,
) -> None:
    anomalies.append(
        {
            "severity": severity,
            "stage": stage,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "issue_type": issue_type,
            "observed": encode_json(observed),
            "expected": encode_json(expected),
            "detail": detail,
        }
    )


def count_physical_lines(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines()) or 1


def literal_space_token_spans(text: str) -> tuple[list[int], list[int]]:
    spaces = [index for index, char in enumerate(text) if char == " "]
    starts = [0] + [index + 1 for index in spaces]
    ends = spaces + [len(text)]
    if len(starts) != len(text.split(" ")) or len(ends) != len(starts):
        raise AssertionError("Literal-space token spans are inconsistent with text.split(' ').")
    return starts, ends


def expected_window_rows(text: str, window_size: int) -> list[dict[str, Any]]:
    starts, ends = literal_space_token_spans(text)
    total = len(starts)
    intervals: list[tuple[int, int]] = []
    if total <= window_size:
        intervals.append((0, total))
    else:
        start = 0
        while start < total:
            end = min(start + window_size, total)
            if end - start < window_size and intervals:
                start = end - window_size
            intervals.append((start, end))
            if end >= total:
                break
            start = end

    rows: list[dict[str, Any]] = []
    frontier = 0
    for index, (start_token, end_token) in enumerate(intervals):
        char_start = starts[start_token]
        char_end = ends[end_token - 1]
        raw_text = text[char_start:char_end]
        marginal_start = max(start_token, frontier)
        marginal_count = max(0, end_token - marginal_start)
        frontier = max(frontier, end_token)
        rows.append(
            {
                "window_index": index,
                "window_space_by_start": start_token,
                "window_space_by_end": end_token,
                "window_space_by_token_count": end_token - start_token,
                "window_marginal_space_by_token_count": marginal_count,
                "overlaps_previous_window": marginal_count < (end_token - start_token),
                "raw_char_start": char_start,
                "raw_char_end": char_end,
                "raw_char_count": len(raw_text),
                "raw_utf8_byte_count": len(raw_text.encode("utf-8")),
                "window_text_sha256": sha256_bytes(raw_text.encode("utf-8")),
            }
        )
    return rows


def valid_frontier_weights(window_df: pd.DataFrame) -> list[int]:
    weights: list[int] = []
    frontier = 0
    for _, row in window_df.sort_values("window_index").iterrows():
        if not as_bool(row["window_npr_valid"]):
            weights.append(0)
            continue
        start = int(row["window_space_by_start"])
        end = int(row["window_space_by_end"])
        marginal_start = max(start, frontier)
        weights.append(max(0, end - marginal_start))
        frontier = max(frontier, end)
    return weights


def aggregate_windows(window_df: pd.DataFrame, total_tokens: int) -> dict[str, Any]:
    ordered = window_df.sort_values("window_index").copy()
    weights = valid_frontier_weights(ordered)
    ordered["_audit_weight"] = weights
    valid = ordered.loc[
        ordered["window_npr_valid"].map(as_bool)
        & ordered["_audit_weight"].gt(0)
        & pd.to_numeric(ordered["window_npr"], errors="coerce").notna()
        & pd.to_numeric(ordered["original_log_rank"], errors="coerce").notna()
        & pd.to_numeric(ordered["mean_perturbed_log_rank"], errors="coerce").notna()
    ].copy()
    scored = int(valid["_audit_weight"].sum()) if not valid.empty else 0
    if scored == 0:
        return {
            "space_by_tokens_scored": 0,
            "npr_coverage_ratio": 0.0 if total_tokens else float("nan"),
            "code_unit_npr_space_by_token_weighted": float("nan"),
            "code_unit_original_log_rank_weighted": float("nan"),
            "code_unit_mean_perturbed_log_rank_weighted": float("nan"),
            "code_unit_npr_pooled_components": float("nan"),
        }
    w = valid["_audit_weight"].astype(float)
    npr = float(np.average(valid["window_npr"].astype(float), weights=w))
    original = float(np.average(valid["original_log_rank"].astype(float), weights=w))
    perturbed = float(np.average(valid["mean_perturbed_log_rank"].astype(float), weights=w))
    pooled = float(perturbed / original) if original != 0 else float("nan")
    return {
        "space_by_tokens_scored": scored,
        "npr_coverage_ratio": float(scored / total_tokens) if total_tokens else float("nan"),
        "code_unit_npr_space_by_token_weighted": npr,
        "code_unit_original_log_rank_weighted": original,
        "code_unit_mean_perturbed_log_rank_weighted": perturbed,
        "code_unit_npr_pooled_components": pooled,
    }


def aggregate_occurrences(group: pd.DataFrame) -> dict[str, Any]:
    total = int(pd.to_numeric(group["space_by_tokens_total"], errors="coerce").fillna(0).sum())
    scored = int(pd.to_numeric(group["space_by_tokens_scored"], errors="coerce").fillna(0).sum())
    usable = group.loc[
        pd.to_numeric(group["space_by_tokens_scored"], errors="coerce").fillna(0).gt(0)
        & pd.to_numeric(group["code_unit_npr_space_by_token_weighted"], errors="coerce").notna()
        & pd.to_numeric(group["code_unit_original_log_rank_weighted"], errors="coerce").notna()
        & pd.to_numeric(group["code_unit_mean_perturbed_log_rank_weighted"], errors="coerce").notna()
    ].copy()
    used = int(pd.to_numeric(usable["space_by_tokens_scored"], errors="coerce").fillna(0).sum()) if not usable.empty else 0
    if used:
        w = usable["space_by_tokens_scored"].astype(float)
        npr = float(np.average(usable["code_unit_npr_space_by_token_weighted"].astype(float), weights=w))
        original = float(np.average(usable["code_unit_original_log_rank_weighted"].astype(float), weights=w))
        perturbed = float(np.average(usable["code_unit_mean_perturbed_log_rank_weighted"].astype(float), weights=w))
        pooled = float(perturbed / original) if original != 0 else float("nan")
    else:
        npr = original = perturbed = pooled = float("nan")
    return {
        "primary_code_units": int(len(group)),
        "space_by_tokens_total": total,
        "space_by_tokens_scored": scored,
        "space_by_tokens_used_for_npr": used,
        "npr_coverage_ratio": float(scored / total) if total else float("nan"),
        "npr_effective_coverage_ratio": float(used / total) if total else float("nan"),
        "npr_space_by_token_weighted": npr,
        "original_log_rank_space_by_token_weighted": original,
        "mean_perturbed_log_rank_space_by_token_weighted": perturbed,
        "npr_pooled_components": pooled,
    }


def primary_overlap_count(code_df: pd.DataFrame) -> tuple[int, list[dict[str, Any]]]:
    primary = code_df.loc[code_df["aggregation_role"].astype(str).eq(PRIMARY_ROLE)].copy()
    count = 0
    examples: list[dict[str, Any]] = []
    for (snapshot_id, relative_path), group in primary.groupby(["snapshot_id", "relative_path"], sort=False):
        intervals = group[["code_unit_id", "start_char_offset", "end_char_offset"]].copy()
        intervals = intervals.sort_values(["start_char_offset", "end_char_offset"])
        active_end = -1
        active_id = ""
        for _, row in intervals.iterrows():
            start = int(row["start_char_offset"])
            end = int(row["end_char_offset"])
            if start < active_end:
                count += 1
                if len(examples) < 10:
                    examples.append(
                        {
                            "snapshot_id": snapshot_id,
                            "relative_path": relative_path,
                            "previous_code_unit_id": active_id,
                            "code_unit_id": row["code_unit_id"],
                            "start": start,
                            "previous_end": active_end,
                        }
                    )
            if end > active_end:
                active_end = end
                active_id = str(row["code_unit_id"])
    return count, examples


def compare_value(
    reconciliation: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
    tolerance: float,
    stage: str,
    level: str,
    metric: str,
    expected: Any,
    observed: Any,
    snapshot_id: str = "",
    relative_path: str = "",
    code_unit_sha256: str = "",
    severity: str = "hard",
) -> bool:
    if isinstance(expected, (str, bool, np.bool_)) or isinstance(observed, (str, bool, np.bool_)):
        passed = str(observed) == str(expected)
        difference = None
    else:
        passed, difference = close_number(expected, observed, tolerance)
    add_recon(
        reconciliation,
        stage,
        level,
        metric,
        expected,
        observed,
        passed,
        difference,
        snapshot_id,
        relative_path,
        code_unit_sha256,
    )
    if not passed:
        entity_id = code_unit_sha256 or ":".join(item for item in (snapshot_id, relative_path) if item)
        add_anomaly(
            anomalies,
            severity,
            stage,
            level,
            entity_id,
            f"reconciliation_mismatch:{metric}",
            observed,
            expected,
            "Independent A04 recomputation did not match the upstream output.",
        )
    return passed


def audit_pipeline(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    started = time.time()
    tolerance = float(args.tolerance)
    checks: list[dict[str, Any]] = []
    reconciliation: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []

    a01 = args.a01_dir
    a02 = args.a02_dir
    a03 = args.a03_dir
    if a01 is None or a02 is None or a03 is None:
        raise ValueError("--a01-dir, --a02-dir, and --a03-dir are required outside --self-test.")

    paths = {
        "a01_snapshot": a01 / "python_snapshot_manifest.csv",
        "a01_file": a01 / "python_file_manifest.csv",
        "a01_code": a01 / "python_code_unit_manifest.csv",
        "a01_checks": a01 / "qc/python_snapshot_input_checks.csv",
        "a01_summary": a01 / "qc/python_snapshot_input_summary.json",
        "a01_metadata": a01 / "qc/python_snapshot_input_metadata.json",
        "a02_occ": a02 / "python_code_unit_npr_scores.csv",
        "a02_unique": a02 / "python_unique_code_unit_npr_scores.csv",
        "a02_window": a02 / "python_window_npr_scores.csv",
        "a02_failures": a02 / "python_snapshot_npr_failures.csv",
        "a02_checks": a02 / "qc/python_snapshot_npr_checks.csv",
        "a02_artifact_errors": a02 / "qc/python_snapshot_npr_artifact_errors.csv",
        "a02_repro": a02 / "qc/python_snapshot_npr_reproducibility_checks.csv",
        "a02_resume": a02 / "qc/python_snapshot_npr_resume_check.json",
        "a02_summary": a02 / "qc/python_snapshot_npr_summary.json",
        "a02_metadata": a02 / "qc/python_snapshot_npr_metadata.json",
        "a03_file": a03 / "python_file_npr_scores.csv",
        "a03_snapshot": a03 / "python_snapshot_npr_scores.csv",
        "a03_checks": a03 / "qc/python_snapshot_npr_aggregation_checks.csv",
        "a03_recon": a03 / "qc/python_snapshot_npr_aggregation_reconciliation.csv",
        "a03_summary": a03 / "qc/python_snapshot_npr_aggregation_summary.json",
        "a03_metadata": a03 / "qc/python_snapshot_npr_aggregation_metadata.json",
    }
    for label, path in paths.items():
        require_file(path, label)

    snap = pd.read_csv(paths["a01_snapshot"])
    files = pd.read_csv(paths["a01_file"])
    code = pd.read_csv(paths["a01_code"])
    a01_checks = pd.read_csv(paths["a01_checks"])
    a01_summary = read_json(paths["a01_summary"])
    a01_metadata = read_json(paths["a01_metadata"])

    occ = pd.read_csv(paths["a02_occ"])
    unique = pd.read_csv(paths["a02_unique"])
    windows = pd.read_csv(paths["a02_window"])
    failures = pd.read_csv(paths["a02_failures"])
    a02_checks = pd.read_csv(paths["a02_checks"])
    artifact_errors = pd.read_csv(paths["a02_artifact_errors"])
    repro = pd.read_csv(paths["a02_repro"])
    resume = read_json(paths["a02_resume"])
    a02_summary = read_json(paths["a02_summary"])
    a02_metadata = read_json(paths["a02_metadata"])

    file_scores = pd.read_csv(paths["a03_file"])
    snapshot_scores = pd.read_csv(paths["a03_snapshot"])
    a03_checks = pd.read_csv(paths["a03_checks"])
    a03_recon = pd.read_csv(paths["a03_recon"])
    a03_summary = read_json(paths["a03_summary"])
    a03_metadata = read_json(paths["a03_metadata"])

    require_columns(snap, ["snapshot_id", "metadata_complete", "python_files_prepared", "primary_code_units", "space_by_tokens_primary"], "A01 snapshot manifest")
    require_columns(files, FILE_KEY + ["parse_status", "primary_code_units"], "A01 file manifest")
    require_columns(code, CODE_UNIT_KEY + ["aggregation_role", "code_unit_sha256", "code_unit_relative_path", "character_count", "utf8_byte_count", "physical_line_count", "space_by_token_count", "start_char_offset", "end_char_offset"], "A01 code-unit manifest")
    require_columns(occ, CODE_UNIT_KEY + ["code_unit_sha256", "space_by_tokens_total", "space_by_tokens_scored", "code_unit_npr_space_by_token_weighted", "code_unit_original_log_rank_weighted", "code_unit_mean_perturbed_log_rank_weighted", "code_unit_npr_pooled_components", "config_fingerprint"], "A02 occurrence scores")
    require_columns(unique, ["code_unit_sha256", "space_by_tokens_total", "space_by_tokens_scored", "code_unit_npr_space_by_token_weighted", "code_unit_original_log_rank_weighted", "code_unit_mean_perturbed_log_rank_weighted", "code_unit_npr_pooled_components", "config_fingerprint"], "A02 unique scores")
    require_columns(windows, ["code_unit_sha256", "window_index", "window_space_by_start", "window_space_by_end", "window_space_by_token_count", "window_marginal_space_by_token_count", "window_aggregation_weight_space_by_tokens", "raw_char_start", "raw_char_end", "raw_char_count", "raw_utf8_byte_count", "window_text_sha256", "window_npr_valid", "original_log_rank", "mean_perturbed_log_rank", "window_npr", "expected_perturbations", "valid_perturbation_scores", "config_fingerprint"], "A02 window scores")

    primary = code.loc[code["aggregation_role"].astype(str).eq(PRIMARY_ROLE)].copy()

    # A01 upstream and source integrity checks.
    a01_failed = int((~a01_checks["passed"].map(as_bool)).sum())
    add_check(checks, "hard", "A01", "upstream_a01_checks_pass", a01_failed == 0, a01_failed, 0, "All A01 checks must pass before NPR scoring is trusted.")
    add_check(checks, "hard", "A01", "upstream_a01_summary_pass", str(a01_summary.get("status")) == "PASS", a01_summary.get("status"), "PASS", "A01 summary status must be PASS.")
    if args.expected_snapshots is not None:
        add_check(checks, "hard", "A01", "expected_snapshot_count", len(snap) == args.expected_snapshots, len(snap), args.expected_snapshots, "Prototype snapshot count must match the requested expectation.")
    metadata_complete = int(snap["metadata_complete"].map(as_bool).sum())
    add_check(checks, "hard", "A01", "snapshot_metadata_complete", metadata_complete == len(snap), metadata_complete, len(snap), "All snapshots must have complete provenance metadata.")
    prepared_files = int(files["parse_status"].astype(str).eq("prepared").sum())
    add_check(checks, "hard", "A01", "all_file_rows_prepared", prepared_files == len(files), prepared_files, len(files), "All A01 file rows must be prepared successfully.")

    overlap_count, overlap_examples = primary_overlap_count(code)
    add_check(checks, "hard", "A01", "primary_source_overlap_zero", overlap_count == 0, overlap_count, 0, f"Primary source intervals must not double-count source. Examples: {overlap_examples}")

    artifact_mismatches = 0
    artifact_rows_checked = 0
    artifact_texts: dict[str, str] = {}
    artifact_paths: dict[str, Path] = {}
    for sha, group in primary.groupby("code_unit_sha256", sort=False):
        row = group.iloc[0]
        relative = Path(str(row["code_unit_relative_path"]))
        path = a01 / relative
        artifact_paths[str(sha)] = path
        if not path.is_file():
            artifact_mismatches += 1
            add_anomaly(anomalies, "hard", "A01", "code_unit", str(sha), "artifact_missing", str(path), "existing file", "A01 content-addressed code-unit artifact is missing.")
            continue
        payload = path.read_bytes()
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            artifact_mismatches += 1
            add_anomaly(anomalies, "hard", "A01", "code_unit", str(sha), "artifact_utf8_decode_failure", str(error), "valid UTF-8", "A01 code-unit artifacts are expected to be UTF-8 encoded raw slices.")
            continue
        artifact_texts[str(sha)] = text
        artifact_rows_checked += 1
        expected_values = {
            "sha256": str(sha),
            "character_count": int(row["character_count"]),
            "utf8_byte_count": int(row["utf8_byte_count"]),
            "physical_line_count": int(row["physical_line_count"]),
            "space_by_token_count": int(row["space_by_token_count"]),
        }
        observed_values = {
            "sha256": sha256_bytes(payload),
            "character_count": len(text),
            "utf8_byte_count": len(payload),
            "physical_line_count": count_physical_lines(text),
            "space_by_token_count": len(text.split(" ")),
        }
        for metric in expected_values:
            if observed_values[metric] != expected_values[metric]:
                artifact_mismatches += 1
                add_anomaly(anomalies, "hard", "A01", "code_unit", str(sha), f"artifact_{metric}_mismatch", observed_values[metric], expected_values[metric], "Raw A01 artifact content does not match its manifest.")
    add_check(checks, "hard", "A01", "raw_artifact_integrity", artifact_mismatches == 0, artifact_mismatches, 0, f"Checked {artifact_rows_checked} unique primary artifacts for SHA, length, lines, and space-by tokens.")

    # A02 occurrence and uniqueness alignment.
    primary_keys = primary[CODE_UNIT_KEY + ["code_unit_sha256", "space_by_token_count"]].copy()
    occ_keys = occ[CODE_UNIT_KEY + ["code_unit_sha256", "space_by_tokens_total"]].copy()
    key_merge = primary_keys.merge(occ_keys, on=CODE_UNIT_KEY, how="outer", suffixes=("_a01", "_a02"), indicator=True)
    missing_occ = int((key_merge["_merge"] == "left_only").sum())
    extra_occ = int((key_merge["_merge"] == "right_only").sum())
    aligned = key_merge.loc[key_merge["_merge"].eq("both")].copy()
    sha_mismatch = int((aligned["code_unit_sha256_a01"].astype(str) != aligned["code_unit_sha256_a02"].astype(str)).sum())
    token_mismatch = int((pd.to_numeric(aligned["space_by_token_count"], errors="coerce") != pd.to_numeric(aligned["space_by_tokens_total"], errors="coerce")).sum())
    add_check(checks, "hard", "A02", "a01_a02_occurrence_key_alignment", missing_occ == 0 and extra_occ == 0, {"missing": missing_occ, "extra": extra_occ}, {"missing": 0, "extra": 0}, "A02 occurrence scores must cover exactly the A01 primary occurrences.")
    add_check(checks, "hard", "A02", "a01_a02_occurrence_sha_alignment", sha_mismatch == 0, sha_mismatch, 0, "A02 occurrence code-unit SHA must match A01.")
    add_check(checks, "hard", "A02", "a01_a02_occurrence_token_alignment", token_mismatch == 0, token_mismatch, 0, "A02 space-by-token totals must match A01.")

    expected_unique_shas = set(primary["code_unit_sha256"].astype(str))
    observed_unique_shas = set(unique["code_unit_sha256"].astype(str))
    add_check(checks, "hard", "A02", "unique_code_unit_set_alignment", expected_unique_shas == observed_unique_shas, {"expected": len(expected_unique_shas), "observed": len(observed_unique_shas), "missing": len(expected_unique_shas - observed_unique_shas), "extra": len(observed_unique_shas - expected_unique_shas)}, {"missing": 0, "extra": 0}, "A02 unique scores must cover each unique A01 primary content hash exactly once.")

    upstream_a02_failed = int((~a02_checks["passed"].map(as_bool)).sum())
    add_check(checks, "hard", "A02", "upstream_a02_checks_pass", upstream_a02_failed == 0, upstream_a02_failed, 0, "All A02 built-in checks must pass.")
    add_check(checks, "hard", "A02", "upstream_a02_summary_pass", str(a02_summary.get("status")) == "PASS", a02_summary.get("status"), "PASS", "A02 summary status must be PASS.")
    add_check(checks, "hard", "A02", "a02_failures_zero", len(failures) == 0, len(failures), 0, "No unique code-unit scoring failures are allowed in the full-coverage prototype.")
    add_check(checks, "hard", "A02", "a02_artifact_errors_zero", len(artifact_errors) == 0, len(artifact_errors), 0, "A02 must not report source-artifact errors.")
    repro_failures = int((~repro["passed"].map(as_bool)).sum()) if not repro.empty else 0
    add_check(checks, "hard", "A02", "same_seed_reproducibility", repro_failures == 0 and len(repro) > 0, {"rows": len(repro), "failures": repro_failures}, {"rows_min": 1, "failures": 0}, "A02 same-seed reproducibility check must exist and pass.")
    add_check(checks, "hard", "A02", "resume_cache_check_pass", str(resume.get("status")) == "PASS" and bool(resume.get("canonical_outputs_unchanged")), {"status": resume.get("status"), "canonical_outputs_unchanged": resume.get("canonical_outputs_unchanged")}, {"status": "PASS", "canonical_outputs_unchanged": True}, "A02 resume validation must reuse cache without changing canonical outputs.")

    scoring_config = a02_metadata.get("scoring_configuration", {})
    window_size = int(scoring_config.get("window_size_space_by_tokens", 128))
    expected_perturbations = int(scoring_config.get("perturbations_per_window", 50))
    config_fingerprint = str(a02_metadata.get("config_fingerprint", ""))
    explicit_truncation = bool(scoring_config.get("explicit_llm_truncation", a02_metadata.get("runtime", {}).get("explicit_llm_truncation", False)))
    add_check(checks, "hard", "A02", "no_explicit_llm_truncation", not explicit_truncation, explicit_truncation, False, "A02 must preserve the original scorer API behavior without adding LLM-token truncation.")
    add_check(checks, "hard", "A02", "classification_disabled", not bool(scoring_config.get("classification_enabled", False)), scoring_config.get("classification_enabled"), False, "A02 NPR remains a continuous measurement.")

    manifest_hash_matches = str(a02_metadata.get("input_code_unit_manifest_sha256", "")) == sha256_file(paths["a01_code"])
    add_check(checks, "hard", "PROVENANCE", "a02_input_manifest_sha256_matches", manifest_hash_matches, a02_metadata.get("input_code_unit_manifest_sha256"), sha256_file(paths["a01_code"]), "A02 metadata must fingerprint the exact A01 code-unit manifest audited here.")

    fingerprints = set(occ["config_fingerprint"].dropna().astype(str)) | set(unique["config_fingerprint"].dropna().astype(str)) | set(windows["config_fingerprint"].dropna().astype(str))
    add_check(checks, "hard", "A02", "single_config_fingerprint", len(fingerprints) == 1 and config_fingerprint in fingerprints, sorted(fingerprints), [config_fingerprint], "Occurrence, unique, window, and metadata fingerprints must identify one scoring configuration.")

    # Rebuild every window directly from the A01 raw code-unit artifact.
    window_structure_mismatches = 0
    window_hash_mismatches = 0
    window_weight_mismatches = 0
    unit_formula_mismatches = 0
    context_exceeded = 0
    perturbation_incomplete = 0
    unique_index = unique.set_index("code_unit_sha256", drop=False)

    for sha in sorted(expected_unique_shas):
        if sha not in artifact_texts:
            continue
        actual = windows.loc[windows["code_unit_sha256"].astype(str).eq(sha)].sort_values("window_index").copy()
        expected_rows = expected_window_rows(artifact_texts[sha], window_size)
        if len(actual) != len(expected_rows):
            window_structure_mismatches += 1
            add_anomaly(anomalies, "hard", "A02", "code_unit", sha, "window_count_mismatch", len(actual), len(expected_rows), "A04 independently rebuilt the 128-space-by-token windows.")
            continue

        for expected_row, (_, actual_row) in zip(expected_rows, actual.iterrows()):
            for metric in [
                "window_index",
                "window_space_by_start",
                "window_space_by_end",
                "window_space_by_token_count",
                "window_marginal_space_by_token_count",
                "raw_char_start",
                "raw_char_end",
                "raw_char_count",
                "raw_utf8_byte_count",
                "window_text_sha256",
            ]:
                exp = expected_row[metric]
                obs = actual_row[metric]
                passed = str(obs) == str(exp) if metric == "window_text_sha256" else int(obs) == int(exp)
                if not passed:
                    if metric == "window_text_sha256":
                        window_hash_mismatches += 1
                    else:
                        window_structure_mismatches += 1
                    add_anomaly(anomalies, "hard", "A02", "window", f"{sha}:{expected_row['window_index']}", f"window_{metric}_mismatch", obs, exp, "A02 window must be an exact raw substring of the A01 artifact using the 128 space-by-token coordinate.")

        audit_weights = valid_frontier_weights(actual)
        observed_weights = [int(value) for value in actual["window_aggregation_weight_space_by_tokens"].tolist()]
        if audit_weights != observed_weights:
            window_weight_mismatches += 1
            add_anomaly(anomalies, "hard", "A02", "code_unit", sha, "window_aggregation_weight_mismatch", observed_weights, audit_weights, "Final overlap windows must not double-count source tokens in NPR aggregation.")

        for _, row in actual.iterrows():
            if as_bool(row.get("original_llm_tokens_exceed_reported_context", False)):
                context_exceeded += 1
            exp_pert = int(row["expected_perturbations"])
            val_pert = int(row["valid_perturbation_scores"])
            if exp_pert != expected_perturbations or val_pert > exp_pert or (args.require_full_coverage and val_pert != exp_pert):
                perturbation_incomplete += 1
            if as_bool(row["window_npr_valid"]):
                original = float(row["original_log_rank"])
                perturbed = float(row["mean_perturbed_log_rank"])
                expected_npr = perturbed / original if original != 0 else float("nan")
                passed, _ = close_number(expected_npr, row["window_npr"], tolerance)
                if not passed:
                    unit_formula_mismatches += 1
                    add_anomaly(anomalies, "hard", "A02", "window", f"{sha}:{int(row['window_index'])}", "window_npr_formula_mismatch", row["window_npr"], expected_npr, "Window NPR must equal mean perturbed log-rank divided by original log-rank.")

        expected_aggregate = aggregate_windows(actual, len(artifact_texts[sha].split(" ")))
        if sha in unique_index.index:
            unique_row = unique_index.loc[sha]
            if isinstance(unique_row, pd.DataFrame):
                unique_row = unique_row.iloc[0]
            for metric, exp in expected_aggregate.items():
                obs = unique_row[metric]
                passed, diff = close_number(exp, obs, tolerance)
                add_recon(reconciliation, "A02", "code_unit", metric, exp, obs, passed, diff, code_unit_sha256=sha)
                if not passed:
                    unit_formula_mismatches += 1
                    add_anomaly(anomalies, "hard", "A02", "code_unit", sha, f"code_unit_formula_mismatch:{metric}", obs, exp, "A04 independently aggregated valid A02 window scores using frontier space-by-token weights.")

    add_check(checks, "hard", "A02", "raw_window_reconstruction", window_structure_mismatches == 0, window_structure_mismatches, 0, "All A02 windows must exactly match windows independently rebuilt from A01 raw artifacts.")
    add_check(checks, "hard", "A02", "window_text_sha256_integrity", window_hash_mismatches == 0, window_hash_mismatches, 0, "All window SHA-256 values must match the direct raw source slices.")
    add_check(checks, "hard", "A02", "window_aggregation_weights_reconcile", window_weight_mismatches == 0, window_weight_mismatches, 0, "Valid-frontier weights must cover source once despite final-window overlap.")
    add_check(checks, "hard", "A02", "window_and_code_unit_npr_formulas_reconcile", unit_formula_mismatches == 0, unit_formula_mismatches, 0, "Window ratios and code-unit aggregates must reproduce independently.")
    add_check(checks, "hard", "A02", "perturbation_score_coverage", perturbation_incomplete == 0, perturbation_incomplete, 0, f"Each valid pilot window is expected to retain all {expected_perturbations} perturbation scores when full coverage is required.")
    add_check(checks, "hard" if args.require_full_coverage else "warning", "A02", "reported_model_context_not_exceeded", context_exceeded == 0, context_exceeded, 0, "No pilot window should exceed the model-reported context limit.")

    # Occurrence rows must be exact repetitions of the unique content score.
    unique_compare = unique.set_index("code_unit_sha256")
    occurrence_mismatches = 0
    compare_columns = [
        "space_by_tokens_total",
        "space_by_tokens_scored",
        "npr_coverage_ratio",
        "code_unit_npr_space_by_token_weighted",
        "code_unit_original_log_rank_weighted",
        "code_unit_mean_perturbed_log_rank_weighted",
        "code_unit_npr_pooled_components",
    ]
    for _, row in occ.iterrows():
        sha = str(row["code_unit_sha256"])
        if sha not in unique_compare.index:
            occurrence_mismatches += 1
            continue
        urow = unique_compare.loc[sha]
        if isinstance(urow, pd.DataFrame):
            urow = urow.iloc[0]
        for metric in compare_columns:
            passed, _ = close_number(urow[metric], row[metric], tolerance)
            if not passed:
                occurrence_mismatches += 1
                add_anomaly(anomalies, "hard", "A02", "occurrence", f"{row['snapshot_id']}:{row['code_unit_id']}", f"unique_occurrence_score_mismatch:{metric}", row[metric], urow[metric], "Content-identical code-unit occurrences must reuse the same NPR score.")
    add_check(checks, "hard", "A02", "unique_to_occurrence_score_consistency", occurrence_mismatches == 0, occurrence_mismatches, 0, "Each A02 occurrence score must equal its unique content-hash score.")

    # Cache integrity and cache/output equality.
    cache_files = sorted((a02 / "cache").rglob("*.json")) if (a02 / "cache").is_dir() else []
    cache_by_sha: dict[str, dict[str, Any]] = {}
    cache_errors = 0
    for path in cache_files:
        try:
            payload = read_json(path)
        except Exception as error:
            cache_errors += 1
            add_anomaly(anomalies, "hard", "A02", "cache", str(path), "cache_json_error", str(error), "valid cache JSON", "Cache files must remain readable for production reuse.")
            continue
        sha = str(payload.get("code_unit_sha256", ""))
        if not sha or sha in cache_by_sha:
            cache_errors += 1
            add_anomaly(anomalies, "hard", "A02", "cache", str(path), "cache_key_duplicate_or_missing", sha, "unique code-unit SHA", "Each cache record must identify one unique code-unit content hash.")
            continue
        cache_by_sha[sha] = payload
        if str(payload.get("config_fingerprint")) != config_fingerprint:
            cache_errors += 1
            add_anomaly(anomalies, "hard", "A02", "cache", sha, "cache_fingerprint_mismatch", payload.get("config_fingerprint"), config_fingerprint, "Cache entries must be bound to the scoring configuration.")
    if set(cache_by_sha) != expected_unique_shas:
        cache_errors += len(set(cache_by_sha) ^ expected_unique_shas)
    cache_score_mismatches = 0
    for sha in expected_unique_shas & set(cache_by_sha):
        payload = cache_by_sha[sha]
        unique_score = payload.get("unique_score", {})
        if sha not in unique_compare.index:
            continue
        urow = unique_compare.loc[sha]
        if isinstance(urow, pd.DataFrame):
            urow = urow.iloc[0]
        for metric in compare_columns:
            if metric not in unique_score:
                cache_score_mismatches += 1
                continue
            passed, _ = close_number(unique_score[metric], urow[metric], tolerance)
            if not passed:
                cache_score_mismatches += 1
        cached_windows = payload.get("windows", [])
        observed_count = int((windows["code_unit_sha256"].astype(str) == sha).sum())
        if len(cached_windows) != observed_count:
            cache_score_mismatches += 1
    add_check(checks, "hard", "A02", "cache_set_integrity", cache_errors == 0, {"cache_files": len(cache_files), "unique_cache_keys": len(cache_by_sha), "errors": cache_errors}, {"unique_cache_keys": len(expected_unique_shas), "errors": 0}, "A02 cache must have exactly one valid record per unique primary code-unit SHA for this fingerprint.")
    add_check(checks, "hard", "A02", "cache_score_output_consistency", cache_score_mismatches == 0, cache_score_mismatches, 0, "Cached unique scores and window counts must match canonical A02 outputs.")

    # A03 upstream checks and independent aggregation.
    upstream_a03_failed = int((~a03_checks["passed"].map(as_bool)).sum())
    add_check(checks, "hard", "A03", "upstream_a03_checks_pass", upstream_a03_failed == 0, upstream_a03_failed, 0, "All A03 built-in aggregation checks must pass.")
    add_check(checks, "hard", "A03", "upstream_a03_summary_pass", str(a03_summary.get("status")) == "PASS", a03_summary.get("status"), "PASS", "A03 summary status must be PASS.")
    if {"primary_code_unit_difference", "space_by_token_difference"}.issubset(a03_recon.columns):
        recon_nonzero = int((pd.to_numeric(a03_recon["primary_code_unit_difference"], errors="coerce").fillna(0).ne(0) | pd.to_numeric(a03_recon["space_by_token_difference"], errors="coerce").fillna(0).ne(0)).sum())
    else:
        recon_nonzero = len(a03_recon)
    add_check(checks, "hard", "A03", "a03_reconciliation_differences_zero", recon_nonzero == 0, recon_nonzero, 0, "A03 file/snapshot source counts must reconcile to A01/A02.")

    a03_input_hash_errors = 0
    input_files_meta = a03_metadata.get("input_files", {})
    actual_lineage_paths = {
        "a01_code_unit_manifest": paths["a01_code"],
        "a01_file_manifest": paths["a01_file"],
        "a01_snapshot_manifest": paths["a01_snapshot"],
        "a02_code_unit_scores": paths["a02_occ"],
        "a02_window_scores": paths["a02_window"],
    }
    for key, path in actual_lineage_paths.items():
        recorded = str(input_files_meta.get(key, {}).get("sha256", ""))
        actual_hash = sha256_file(path)
        if recorded != actual_hash:
            a03_input_hash_errors += 1
            add_anomaly(anomalies, "hard", "PROVENANCE", "input_file", key, "a03_input_sha256_mismatch", recorded, actual_hash, "A03 must aggregate the exact A01/A02 files audited by A04.")
    add_check(checks, "hard", "PROVENANCE", "a03_input_sha256_lineage", a03_input_hash_errors == 0, a03_input_hash_errors, 0, "A03 metadata input hashes must match the current A01/A02 artifacts.")

    # Independently recompute A03 file and snapshot outputs from A02 occurrence rows.
    file_index = file_scores.set_index(FILE_KEY, drop=False)
    snapshot_index = snapshot_scores.set_index("snapshot_id", drop=False)
    a03_formula_mismatches = 0
    file_metric_map = {
        "primary_code_units": "primary_code_units",
        "space_by_tokens_total": "space_by_tokens_total",
        "space_by_tokens_scored": "space_by_tokens_scored",
        "space_by_tokens_used_for_npr": "space_by_tokens_used_for_npr",
        "npr_coverage_ratio": "npr_coverage_ratio",
        "npr_effective_coverage_ratio": "npr_effective_coverage_ratio",
        "npr_space_by_token_weighted": "file_npr_space_by_token_weighted",
        "original_log_rank_space_by_token_weighted": "file_original_log_rank_space_by_token_weighted",
        "mean_perturbed_log_rank_space_by_token_weighted": "file_mean_perturbed_log_rank_space_by_token_weighted",
        "npr_pooled_components": "file_npr_pooled_components",
    }
    snapshot_metric_map = {
        "primary_code_units": "primary_code_units",
        "space_by_tokens_total": "space_by_tokens_total",
        "space_by_tokens_scored": "space_by_tokens_scored",
        "space_by_tokens_used_for_npr": "space_by_tokens_used_for_npr",
        "npr_coverage_ratio": "npr_coverage_ratio",
        "npr_effective_coverage_ratio": "npr_effective_coverage_ratio",
        "npr_space_by_token_weighted": "snapshot_npr_space_by_token_weighted",
        "original_log_rank_space_by_token_weighted": "snapshot_original_log_rank_space_by_token_weighted",
        "mean_perturbed_log_rank_space_by_token_weighted": "snapshot_mean_perturbed_log_rank_space_by_token_weighted",
        "npr_pooled_components": "snapshot_npr_pooled_components",
    }

    for key, group in occ.groupby(FILE_KEY, sort=False, dropna=False):
        expected = aggregate_occurrences(group)
        if key not in file_index.index:
            a03_formula_mismatches += 1
            add_anomaly(anomalies, "hard", "A03", "file", ":".join(map(str, key)), "file_output_missing", "missing", "present", "A03 file output must cover each file containing primary code units.")
            continue
        row = file_index.loc[key]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        for exp_metric, out_metric in file_metric_map.items():
            passed = compare_value(reconciliation, anomalies, tolerance, "A03", "file", out_metric, expected[exp_metric], row[out_metric], snapshot_id=str(key[0]), relative_path=str(key[1]))
            if not passed:
                a03_formula_mismatches += 1

    for snapshot_id, group in occ.groupby("snapshot_id", sort=False, dropna=False):
        expected = aggregate_occurrences(group)
        if snapshot_id not in snapshot_index.index:
            a03_formula_mismatches += 1
            add_anomaly(anomalies, "hard", "A03", "snapshot", str(snapshot_id), "snapshot_output_missing", "missing", "present", "A03 snapshot output must cover each A01 snapshot.")
            continue
        row = snapshot_index.loc[snapshot_id]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        for exp_metric, out_metric in snapshot_metric_map.items():
            passed = compare_value(reconciliation, anomalies, tolerance, "A03", "snapshot", out_metric, expected[exp_metric], row[out_metric], snapshot_id=str(snapshot_id))
            if not passed:
                a03_formula_mismatches += 1

    add_check(checks, "hard", "A03", "independent_file_snapshot_aggregation", a03_formula_mismatches == 0, a03_formula_mismatches, 0, "A04 independently recomputes file and snapshot NPR from A02 occurrences.")

    # Same-content invariance: identical historical Python file/snapshot content should yield identical NPR.
    file_invariance_failures = 0
    for (_, file_sha), group in file_scores.groupby(["relative_path", "file_sha256"], sort=False):
        if len(group) < 2:
            continue
        for metric in ["file_npr_space_by_token_weighted", "file_npr_pooled_components"]:
            values = pd.to_numeric(group[metric], errors="coerce").dropna().to_numpy(dtype=float)
            if len(values) > 1 and np.max(values) - np.min(values) > tolerance * max(1.0, float(np.max(np.abs(values)))):
                file_invariance_failures += 1
                add_anomaly(anomalies, "hard", "A03", "file_content", f"{file_sha}", f"same_content_invariance:{metric}", values.tolist(), "identical", "Identical file content under the same scoring configuration must have identical aggregated NPR.")
    add_check(checks, "hard", "A03", "same_file_content_same_npr", file_invariance_failures == 0, file_invariance_failures, 0, "Repeated identical file contents across snapshots must reproduce the same NPR.")

    snapshot_signatures: dict[str, str] = {}
    for snapshot_id, group in files.groupby("snapshot_id", sort=False):
        parts = [f"{row.relative_path}\0{row.file_sha256}" for row in group.sort_values("relative_path").itertuples()]
        snapshot_signatures[str(snapshot_id)] = sha256_bytes("\n".join(parts).encode("utf-8"))
    snapshot_invariance_failures = 0
    by_signature: defaultdict[str, list[str]] = defaultdict(list)
    for snapshot_id, signature in snapshot_signatures.items():
        by_signature[signature].append(snapshot_id)
    for signature, snapshot_ids in by_signature.items():
        if len(snapshot_ids) < 2:
            continue
        subset = snapshot_scores.loc[snapshot_scores["snapshot_id"].astype(str).isin(snapshot_ids)]
        for metric in ["snapshot_npr_space_by_token_weighted", "snapshot_npr_pooled_components"]:
            values = pd.to_numeric(subset[metric], errors="coerce").dropna().to_numpy(dtype=float)
            if len(values) > 1 and np.max(values) - np.min(values) > tolerance * max(1.0, float(np.max(np.abs(values)))):
                snapshot_invariance_failures += 1
                add_anomaly(anomalies, "hard", "A03", "snapshot_content", signature, f"same_content_invariance:{metric}", values.tolist(), "identical", "Snapshots with identical Python file-content signatures must have identical NPR.")
    add_check(checks, "hard", "A03", "same_snapshot_python_content_same_npr", snapshot_invariance_failures == 0, snapshot_invariance_failures, 0, "Repeated historical snapshots with identical Python source content must reproduce identical NPR.")

    # Classification must remain absent through A03.
    all_columns = set(code.columns) | set(occ.columns) | set(unique.columns) | set(windows.columns) | set(file_scores.columns) | set(snapshot_scores.columns)
    forbidden = [column for column in all_columns if any(token in column.lower() for token in ("agc", "hwc", "likely_ai", "ai_generated", "ai_assisted", "threshold"))]
    add_check(checks, "hard", "METHOD", "continuous_npr_only_no_classification_columns", len(forbidden) == 0, sorted(forbidden), [], "A01-A03 must remain continuous NPR measurement stages with no AGC/HWC classification.")

    # Full-coverage checks at the end of the chain.
    full_coverage_failures = 0
    if args.require_full_coverage:
        if int((pd.to_numeric(occ["space_by_tokens_scored"], errors="coerce") != pd.to_numeric(occ["space_by_tokens_total"], errors="coerce")).sum()) != 0:
            full_coverage_failures += 1
        if int((pd.to_numeric(snapshot_scores["space_by_tokens_scored"], errors="coerce") != pd.to_numeric(snapshot_scores["space_by_tokens_total"], errors="coerce")).sum()) != 0:
            full_coverage_failures += 1
        if int((pd.to_numeric(snapshot_scores["space_by_tokens_used_for_npr"], errors="coerce") != pd.to_numeric(snapshot_scores["space_by_tokens_total"], errors="coerce")).sum()) != 0:
            full_coverage_failures += 1
    add_check(checks, "hard", "PIPELINE", "full_primary_source_coverage", full_coverage_failures == 0, full_coverage_failures, 0, "When requested, every primary space-by token must reach the final snapshot NPR aggregation.")

    checks_df = pd.DataFrame(checks, columns=CHECK_COLUMNS)
    recon_df = pd.DataFrame(reconciliation, columns=RECON_COLUMNS)
    anomaly_df = pd.DataFrame(anomalies, columns=ANOMALY_COLUMNS)
    hard_failed = int(((checks_df["severity"] == "hard") & (~checks_df["passed"])).sum()) if not checks_df.empty else 0
    warning_failed = int(((checks_df["severity"] == "warning") & (~checks_df["passed"])).sum()) if not checks_df.empty else 0
    hard_anomalies = int((anomaly_df["severity"] == "hard").sum()) if not anomaly_df.empty else 0

    summary = {
        "implementation_version": IMPLEMENTATION_VERSION,
        "status": "PASS" if hard_failed == 0 and hard_anomalies == 0 else "FAIL",
        "elapsed_seconds": time.time() - started,
        "hard_checks_failed": hard_failed,
        "warning_checks_failed": warning_failed,
        "hard_anomaly_rows": hard_anomalies,
        "anomaly_rows": int(len(anomaly_df)),
        "audit_checks": int(len(checks_df)),
        "reconciliation_rows": int(len(recon_df)),
        "snapshots": int(len(snap)),
        "python_files": int(len(files)),
        "primary_code_unit_occurrences": int(len(primary)),
        "unique_primary_code_units": int(len(expected_unique_shas)),
        "window_rows": int(len(windows)),
        "a02_failure_rows": int(len(failures)),
        "a02_artifact_error_rows": int(len(artifact_errors)),
        "space_by_tokens_primary": int(pd.to_numeric(primary["space_by_token_count"], errors="coerce").fillna(0).sum()),
        "space_by_tokens_scored_occurrences": int(pd.to_numeric(occ["space_by_tokens_scored"], errors="coerce").fillna(0).sum()),
        "snapshot_npr_rows": int(len(snapshot_scores)),
        "config_fingerprint": config_fingerprint,
        "window_size_space_by_tokens": window_size,
        "perturbations_per_window": expected_perturbations,
        "cache_records": int(len(cache_by_sha)),
        "same_content_snapshot_groups": int(sum(1 for ids in by_signature.values() if len(ids) > 1)),
    }

    metadata = {
        "implementation_version": IMPLEMENTATION_VERSION,
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "expected_snapshots": args.expected_snapshots,
        "require_full_coverage": bool(args.require_full_coverage),
        "tolerance": tolerance,
        "input_directories": {"a01": str(a01), "a02": str(a02), "a03": str(a03)},
        "input_files": {key: {"path": str(path), "sha256": sha256_file(path)} for key, path in paths.items() if path.is_file()},
        "a01_implementation_version": a01_summary.get("implementation_version", a01_metadata.get("implementation_version")),
        "a02_script_version": a02_metadata.get("script_version"),
        "a02_cache_scoring_version": a02_metadata.get("cache_scoring_version"),
        "a02_config_fingerprint": config_fingerprint,
        "a03_implementation_version": a03_summary.get("implementation_version", a03_metadata.get("implementation_version")),
        "audit_semantics": {
            "ast_parsing": False,
            "model_scoring": False,
            "primary_window_coordinate": "space-by tokens defined by text.split(\" \")",
            "window_policy": scoring_config.get("window_policy"),
            "window_raw_source_policy": "reconstructed independently from A01 UTF-8 artifact character offsets",
            "npr_formula": "mean_perturbed_log_rank / original_log_rank",
            "aggregation_weight": "valid-frontier space-by-token weight",
            "llm_token_counts": "diagnostic only; never used as A03 aggregation weights",
            "classification": "disabled",
        },
    }
    return checks_df, recon_df, anomaly_df, summary, metadata


def run_self_test() -> None:
    text = "a  b c d e"
    assert len(text.split(" ")) == 6
    rows = expected_window_rows(text, 4)
    assert [(row["window_space_by_start"], row["window_space_by_end"]) for row in rows] == [(0, 4), (2, 6)]
    assert [row["window_marginal_space_by_token_count"] for row in rows] == [4, 2]
    df = pd.DataFrame(
        [
            {
                "window_index": 0,
                "window_space_by_start": 0,
                "window_space_by_end": 4,
                "window_npr_valid": True,
                "window_npr": 2.0,
                "original_log_rank": 2.0,
                "mean_perturbed_log_rank": 4.0,
            },
            {
                "window_index": 1,
                "window_space_by_start": 2,
                "window_space_by_end": 6,
                "window_npr_valid": True,
                "window_npr": 1.5,
                "original_log_rank": 4.0,
                "mean_perturbed_log_rank": 6.0,
            },
        ]
    )
    result = aggregate_windows(df, 6)
    assert result["space_by_tokens_scored"] == 6
    assert abs(result["code_unit_npr_space_by_token_weighted"] - ((2.0 * 4 + 1.5 * 2) / 6)) < 1e-12
    assert abs(result["code_unit_original_log_rank_weighted"] - ((2.0 * 4 + 4.0 * 2) / 6)) < 1e-12
    assert abs(result["code_unit_mean_perturbed_log_rank_weighted"] - ((4.0 * 4 + 6.0 * 2) / 6)) < 1e-12
    print("A04 self-test: PASS")


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0
    if args.output_dir is None:
        raise ValueError("--output-dir is required outside --self-test.")

    if args.output_dir.exists() and not args.overwrite:
        if any(path.is_file() for path in args.output_dir.rglob("*")):
            raise FileExistsError(f"Output directory already contains files: {args.output_dir}; use --overwrite after review.")

    checks_df, recon_df, anomaly_df, summary, metadata = audit_pipeline(args)
    qc_dir = args.output_dir / "qc"
    atomic_write_csv(checks_df, qc_dir / "python_snapshot_npr_audit_checks.csv")
    atomic_write_csv(recon_df, qc_dir / "python_snapshot_npr_audit_reconciliation.csv")
    atomic_write_csv(anomaly_df, qc_dir / "python_snapshot_npr_audit_anomalies.csv")
    atomic_write_json(summary, qc_dir / "python_snapshot_npr_audit_summary.json")
    atomic_write_json(metadata, qc_dir / "python_snapshot_npr_audit_metadata.json")

    print("A04 snapshot NPR audit")
    print(f"  status: {summary['status']}")
    print(f"  snapshots: {summary['snapshots']}")
    print(f"  python files: {summary['python_files']}")
    print(f"  primary code-unit occurrences: {summary['primary_code_unit_occurrences']}")
    print(f"  unique primary code units: {summary['unique_primary_code_units']}")
    print(f"  windows: {summary['window_rows']}")
    print(f"  hard checks failed: {summary['hard_checks_failed']}")
    print(f"  hard anomalies: {summary['hard_anomaly_rows']}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
