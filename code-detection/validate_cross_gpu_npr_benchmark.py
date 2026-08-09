#!/usr/bin/env python3
"""Validate A07 cross-GPU NPR reproducibility and derive measured worker weights.

This experiment compares two completed A07 benchmark result directories that
were produced from the same offline benchmark bundle. It performs no model
loading and no NPR scoring. The purpose is to establish that two GPU systems
used identical inputs/configuration, produced structurally identical windows,
and returned numerically compatible NPR measurements before production shards
are created.

The script also converts measured windows/second throughput into capacity
weights for the planned five offline production workers:
  - two workers using the reference GPU architecture (Server 173 RTX 6000 Ada)
  - three workers using the candidate GPU architecture (R158 RTX A6000)

Inputs
------
Each A07 result directory must contain:
  benchmark_summary.json
  benchmark_window_scores.csv
  benchmark_unique_scores.csv

Outputs
-------
  cross_gpu_benchmark_checks.csv
  cross_gpu_window_numeric_differences.csv
  cross_gpu_unique_numeric_differences.csv
  measured_worker_capacity_plan.csv
  cross_gpu_benchmark_validation_summary.json

No server-to-server communication is assumed. Both A07 result directories must
already be present in the local workspace before this script starts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

SCRIPT_VERSION = "run-x-a08-v1"

WINDOW_ID_COLUMNS = ["code_unit_sha256", "window_index"]
WINDOW_EXACT_COLUMNS = [
    "code_unit_relative_path",
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
    "reported_model_context_limit",
    "original_llm_tokens_exceed_reported_context",
    "window_npr_valid",
    "window_npr_invalid_reason",
    "scoring_error_type",
    "scoring_error_message",
    "expected_perturbations",
    "valid_perturbation_scores",
    "config_fingerprint",
]
WINDOW_NUMERIC_COLUMNS = [
    "perturbed_llm_token_count_mean",
    "perturbed_llm_token_count_max",
    "original_log_rank",
    "mean_perturbed_log_rank",
    "window_npr",
]

UNIQUE_ID_COLUMNS = ["code_unit_sha256"]
UNIQUE_EXACT_COLUMNS = [
    "code_unit_relative_path",
    "code_unit_type_representative",
    "space_by_tokens_total",
    "n_expected_windows",
    "n_attempted_windows",
    "n_valid_npr_windows",
    "n_invalid_npr_windows",
    "space_by_tokens_scored",
    "original_llm_tokens_all_windows",
    "original_llm_tokens_valid_windows",
    "partial_code_unit_score",
    "cache_reused_this_run",
    "status",
    "config_fingerprint",
]
UNIQUE_NUMERIC_COLUMNS = [
    "npr_coverage_ratio",
    "code_unit_npr_space_by_token_weighted",
    "code_unit_original_log_rank_weighted",
    "code_unit_mean_perturbed_log_rank_weighted",
    "code_unit_npr_pooled_components",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    os.replace(tmp, path)


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, index=False, quoting=csv.QUOTE_MINIMAL)
    os.replace(tmp, path)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def normalize_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def values_equal(left: Any, right: Any) -> bool:
    left = normalize_scalar(left)
    right = normalize_scalar(right)
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, (bool, np.bool_)) or isinstance(right, (bool, np.bool_)):
        return bool(left) == bool(right)
    return str(left) == str(right)


def numeric_difference(left: Any, right: Any) -> tuple[float | None, float | None, bool]:
    left = normalize_scalar(left)
    right = normalize_scalar(right)
    if left is None or right is None:
        return None, None, left is None and right is None
    try:
        left_f = float(left)
        right_f = float(right)
    except (TypeError, ValueError):
        return None, None, False
    if not (math.isfinite(left_f) and math.isfinite(right_f)):
        return None, None, left_f == right_f
    abs_diff = abs(left_f - right_f)
    scale = max(abs(left_f), abs(right_f), 1e-30)
    rel_diff = abs_diff / scale
    return abs_diff, rel_diff, True


def ensure_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def compare_exact_columns(
    merged: pd.DataFrame,
    columns: list[str],
    left_suffix: str,
    right_suffix: str,
) -> tuple[int, dict[str, int]]:
    total_mismatch = 0
    per_column: dict[str, int] = {}
    for column in columns:
        left_col = f"{column}{left_suffix}"
        right_col = f"{column}{right_suffix}"
        if left_col not in merged.columns or right_col not in merged.columns:
            continue
        mismatch = int(
            sum(
                not values_equal(left, right)
                for left, right in zip(merged[left_col].tolist(), merged[right_col].tolist())
            )
        )
        per_column[column] = mismatch
        total_mismatch += mismatch
    return total_mismatch, per_column


def build_numeric_diff_table(
    merged: pd.DataFrame,
    id_columns: list[str],
    numeric_columns: list[str],
    left_suffix: str,
    right_suffix: str,
    abs_tol: float,
    rel_tol: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for merged_row in merged.to_dict(orient="records"):
        base = {column: merged_row[column] for column in id_columns}
        for column in numeric_columns:
            left_key = f"{column}{left_suffix}"
            right_key = f"{column}{right_suffix}"
            if left_key not in merged_row or right_key not in merged_row:
                continue
            left_value = normalize_scalar(merged_row[left_key])
            right_value = normalize_scalar(merged_row[right_key])
            abs_diff, rel_diff, numeric_comparable = numeric_difference(left_value, right_value)
            passed = bool(
                numeric_comparable
                and (
                    abs_diff is None
                    or abs_diff <= abs_tol
                    or (rel_diff is not None and rel_diff <= rel_tol)
                )
            )
            rows.append(
                {
                    **base,
                    "metric": column,
                    "reference_value": left_value,
                    "candidate_value": right_value,
                    "absolute_difference": abs_diff,
                    "relative_difference": rel_diff,
                    "within_abs_or_rel_tolerance": passed,
                }
            )
    return pd.DataFrame(rows)


def numeric_summary(diff_frame: pd.DataFrame, thresholds: list[float]) -> dict[str, Any]:
    if diff_frame.empty:
        return {
            "comparisons": 0,
            "max_absolute_difference": None,
            "max_relative_difference": None,
            "threshold_pass_counts": {},
        }
    finite_abs = pd.to_numeric(diff_frame["absolute_difference"], errors="coerce").dropna()
    finite_rel = pd.to_numeric(diff_frame["relative_difference"], errors="coerce").dropna()
    threshold_counts: dict[str, int] = {}
    for threshold in thresholds:
        key = f"abs_le_{threshold:.0e}"
        threshold_counts[key] = int((finite_abs <= threshold).sum())
    return {
        "comparisons": int(len(diff_frame)),
        "max_absolute_difference": float(finite_abs.max()) if not finite_abs.empty else None,
        "max_relative_difference": float(finite_rel.max()) if not finite_rel.empty else None,
        "threshold_pass_counts": threshold_counts,
    }


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    severity: str,
    passed: bool,
    observed: Any,
    expected: Any,
    note: str = "",
) -> None:
    checks.append(
        {
            "check_name": name,
            "severity": severity,
            "passed": bool(passed),
            "observed": observed,
            "expected": expected,
            "note": note,
        }
    )


def compare_summaries(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    checks: list[dict[str, Any]],
) -> None:
    exact_keys = [
        "benchmark_bundle_manifest_sha256",
        "a02_script_sha256",
        "scoring_config_fingerprint",
        "reported_model_context_limit",
        "benchmark_unique_units_expected",
        "benchmark_unique_units_successful",
        "benchmark_unique_units_failed",
        "benchmark_windows_expected",
        "benchmark_windows_observed",
        "benchmark_valid_windows",
        "benchmark_invalid_windows",
        "perturbations_per_window",
        "valid_perturbation_scores",
        "expected_rank_evaluations",
    ]
    for key in exact_keys:
        left = reference.get(key)
        right = candidate.get(key)
        add_check(checks, f"summary_{key}", "hard", values_equal(left, right), right, left)

    for key in ["detector_source_hashes", "package_versions", "scoring_configuration"]:
        left = reference.get(key)
        right = candidate.get(key)
        add_check(
            checks,
            f"summary_{key}",
            "hard",
            left == right,
            "match" if left == right else "different",
            "match",
        )

    add_check(checks, "reference_status", "hard", reference.get("status") == "PASS", reference.get("status"), "PASS")
    add_check(checks, "candidate_status", "hard", candidate.get("status") == "PASS", candidate.get("status"), "PASS")


def compare_frames(
    reference_path: Path,
    candidate_path: Path,
    id_columns: list[str],
    exact_columns: list[str],
    numeric_columns: list[str],
    label: str,
    checks: list[dict[str, Any]],
    abs_tol: float,
    rel_tol: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    reference = pd.read_csv(reference_path)
    candidate = pd.read_csv(candidate_path)
    required = id_columns + exact_columns + numeric_columns
    ensure_columns(reference, required, f"reference {label}")
    ensure_columns(candidate, required, f"candidate {label}")

    add_check(checks, f"{label}_row_count", "hard", len(reference) == len(candidate), len(candidate), len(reference))
    add_check(
        checks,
        f"{label}_reference_unique_keys",
        "hard",
        not reference.duplicated(id_columns).any(),
        int(reference.duplicated(id_columns).sum()),
        0,
    )
    add_check(
        checks,
        f"{label}_candidate_unique_keys",
        "hard",
        not candidate.duplicated(id_columns).any(),
        int(candidate.duplicated(id_columns).sum()),
        0,
    )

    merged = reference.merge(
        candidate,
        on=id_columns,
        how="outer",
        suffixes=("_reference", "_candidate"),
        indicator=True,
        validate="one_to_one",
    )
    key_mismatches = int((merged["_merge"] != "both").sum())
    add_check(checks, f"{label}_key_set", "hard", key_mismatches == 0, key_mismatches, 0)
    matched = merged[merged["_merge"] == "both"].drop(columns=["_merge"]).copy()

    exact_mismatch_count, exact_by_column = compare_exact_columns(
        matched,
        exact_columns,
        "_reference",
        "_candidate",
    )
    add_check(
        checks,
        f"{label}_exact_fields",
        "hard",
        exact_mismatch_count == 0,
        exact_mismatch_count,
        0,
        note=json.dumps(exact_by_column, sort_keys=True),
    )

    diff_frame = build_numeric_diff_table(
        matched,
        id_columns,
        numeric_columns,
        "_reference",
        "_candidate",
        abs_tol,
        rel_tol,
    )
    numeric_failures = int((~diff_frame["within_abs_or_rel_tolerance"].astype(bool)).sum()) if not diff_frame.empty else 0
    add_check(
        checks,
        f"{label}_numeric_tolerance",
        "hard",
        numeric_failures == 0,
        numeric_failures,
        0,
        note=f"Pass if abs_diff <= {abs_tol:g} OR rel_diff <= {rel_tol:g}.",
    )
    return matched, diff_frame, {
        "exact_mismatches": exact_mismatch_count,
        "exact_mismatches_by_column": exact_by_column,
        "numeric_failures": numeric_failures,
        "numeric_summary": numeric_summary(diff_frame, [1e-12, 1e-10, 1e-8, 1e-6, 1e-4]),
    }


def build_worker_plan(
    reference_summary: dict[str, Any],
    candidate_summary: dict[str, Any],
    total_windows: int,
) -> pd.DataFrame:
    reference_throughput = float(reference_summary["windows_per_second"])
    candidate_throughput = float(candidate_summary["windows_per_second"])
    workers = [
        ("s173-gpu0", "reference", reference_summary.get("gpu_name"), reference_throughput),
        ("s173-gpu1", "reference", reference_summary.get("gpu_name"), reference_throughput),
        ("r158-gpu0", "candidate", candidate_summary.get("gpu_name"), candidate_throughput),
        ("r158-gpu1", "candidate", candidate_summary.get("gpu_name"), candidate_throughput),
        ("r158-gpu2", "candidate", candidate_summary.get("gpu_name"), candidate_throughput),
    ]
    total_capacity = sum(item[3] for item in workers)
    rows: list[dict[str, Any]] = []
    floor_allocations: list[int] = []
    fractions: list[tuple[float, int]] = []
    for index, (name, architecture_group, gpu_name, throughput) in enumerate(workers):
        share = throughput / total_capacity
        exact_windows = total_windows * share
        floor_windows = math.floor(exact_windows)
        floor_allocations.append(floor_windows)
        fractions.append((exact_windows - floor_windows, index))
        rows.append(
            {
                "worker_name": name,
                "architecture_group": architecture_group,
                "gpu_name": gpu_name,
                "measured_windows_per_second": throughput,
                "capacity_weight_normalized_to_candidate": throughput / candidate_throughput,
                "target_window_share": share,
                "target_windows_exact": exact_windows,
                "target_windows_integer": floor_windows,
                "estimated_worker_seconds": exact_windows / throughput,
            }
        )
    remaining = total_windows - sum(floor_allocations)
    for _, index in sorted(fractions, reverse=True)[:remaining]:
        rows[index]["target_windows_integer"] += 1
    for row in rows:
        row["estimated_worker_seconds_using_integer_target"] = row["target_windows_integer"] / row["measured_windows_per_second"]
    return pd.DataFrame(rows)


def run(args: argparse.Namespace) -> int:
    reference_dir = args.reference_dir.resolve()
    candidate_dir = args.candidate_dir.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists() and args.overwrite:
        import shutil
        shutil.rmtree(output_dir)
    elif output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory exists and is non-empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    required_files = ["benchmark_summary.json", "benchmark_window_scores.csv", "benchmark_unique_scores.csv"]
    for directory, label in [(reference_dir, "reference"), (candidate_dir, "candidate")]:
        for filename in required_files:
            path = directory / filename
            if not path.is_file():
                raise FileNotFoundError(f"Missing {label} A07 output: {path}")

    reference_summary = load_json(reference_dir / "benchmark_summary.json")
    candidate_summary = load_json(candidate_dir / "benchmark_summary.json")
    checks: list[dict[str, Any]] = []
    compare_summaries(reference_summary, candidate_summary, checks)

    _, window_diffs, window_comparison = compare_frames(
        reference_dir / "benchmark_window_scores.csv",
        candidate_dir / "benchmark_window_scores.csv",
        WINDOW_ID_COLUMNS,
        WINDOW_EXACT_COLUMNS,
        WINDOW_NUMERIC_COLUMNS,
        "window",
        checks,
        args.numeric_abs_tolerance,
        args.numeric_rel_tolerance,
    )
    _, unique_diffs, unique_comparison = compare_frames(
        reference_dir / "benchmark_unique_scores.csv",
        candidate_dir / "benchmark_unique_scores.csv",
        UNIQUE_ID_COLUMNS,
        UNIQUE_EXACT_COLUMNS,
        UNIQUE_NUMERIC_COLUMNS,
        "unique",
        checks,
        args.numeric_abs_tolerance,
        args.numeric_rel_tolerance,
    )

    # Benchmark timing itself is intentionally excluded from cross-GPU numeric
    # equality checks; it is the measured quantity used for capacity planning.
    reference_throughput = float(reference_summary["windows_per_second"])
    candidate_throughput = float(candidate_summary["windows_per_second"])
    if reference_throughput <= 0 or candidate_throughput <= 0:
        raise ValueError("Both A07 summaries must report positive windows_per_second.")
    throughput_ratio = reference_throughput / candidate_throughput

    worker_plan = build_worker_plan(reference_summary, candidate_summary, args.production_windows)
    add_check(
        checks,
        "worker_plan_total_windows",
        "hard",
        int(worker_plan["target_windows_integer"].sum()) == args.production_windows,
        int(worker_plan["target_windows_integer"].sum()),
        args.production_windows,
    )

    checks_frame = pd.DataFrame(checks)
    hard_failures = int(((checks_frame["severity"] == "hard") & (~checks_frame["passed"].astype(bool))).sum())
    status = "PASS" if hard_failures == 0 else "FAIL"

    atomic_csv(checks_frame, output_dir / "cross_gpu_benchmark_checks.csv")
    atomic_csv(window_diffs, output_dir / "cross_gpu_window_numeric_differences.csv")
    atomic_csv(unique_diffs, output_dir / "cross_gpu_unique_numeric_differences.csv")
    atomic_csv(worker_plan, output_dir / "measured_worker_capacity_plan.csv")

    summary = {
        "status": status,
        "implementation_version": SCRIPT_VERSION,
        "completed_utc": utc_now(),
        "reference_result_dir": str(reference_dir),
        "candidate_result_dir": str(candidate_dir),
        "reference_summary_sha256": sha256_file(reference_dir / "benchmark_summary.json"),
        "candidate_summary_sha256": sha256_file(candidate_dir / "benchmark_summary.json"),
        "reference_system_label": reference_summary.get("system_label"),
        "candidate_system_label": candidate_summary.get("system_label"),
        "reference_gpu_name": reference_summary.get("gpu_name"),
        "candidate_gpu_name": candidate_summary.get("gpu_name"),
        "reference_windows_per_second": reference_throughput,
        "candidate_windows_per_second": candidate_throughput,
        "reference_to_candidate_throughput_ratio": throughput_ratio,
        "reference_faster_percent": (throughput_ratio - 1.0) * 100.0,
        "numeric_abs_tolerance": args.numeric_abs_tolerance,
        "numeric_rel_tolerance": args.numeric_rel_tolerance,
        "hard_check_failures": hard_failures,
        "window_comparison": window_comparison,
        "unique_comparison": unique_comparison,
        "production_expected_windows": args.production_windows,
        "worker_capacity_weights_are_measured": True,
        "worker_capacity_weights_order": ["s173-gpu0", "s173-gpu1", "r158-gpu0", "r158-gpu1", "r158-gpu2"],
        "worker_capacity_weights_windows_per_second": worker_plan["measured_windows_per_second"].tolist(),
        "worker_capacity_weights_normalized_to_candidate": worker_plan["capacity_weight_normalized_to_candidate"].tolist(),
        "worker_target_windows_integer": worker_plan["target_windows_integer"].astype(int).tolist(),
        "estimated_balanced_wall_seconds": float(worker_plan["estimated_worker_seconds_using_integer_target"].max()),
        "estimated_balanced_wall_hours": float(worker_plan["estimated_worker_seconds_using_integer_target"].max() / 3600.0),
        "estimated_balanced_wall_days": float(worker_plan["estimated_worker_seconds_using_integer_target"].max() / 86400.0),
        "notes": {
            "offline_execution": "A08 assumes both A07 result directories were copied into the same local workspace before validation; no runtime server communication is used.",
            "numeric_gate": "Cross-GPU scoring values pass when absolute difference is within the absolute tolerance OR relative difference is within the relative tolerance. Structural/provenance fields must match exactly.",
            "next_stage": "Only after PASS should the measured capacity plan be used to build five mutually exclusive offline production shards.",
        },
    }
    atomic_json(summary, output_dir / "cross_gpu_benchmark_validation_summary.json")

    print("=" * 78)
    print("run-x-a08 cross-GPU benchmark validation")
    print(f"Status:                         {status}")
    print(f"Hard check failures:            {hard_failures}")
    print(f"Reference GPU:                  {reference_summary.get('gpu_name')}")
    print(f"Candidate GPU:                  {candidate_summary.get('gpu_name')}")
    print(f"Reference windows/second:       {reference_throughput:.6f}")
    print(f"Candidate windows/second:       {candidate_throughput:.6f}")
    print(f"Reference/candidate ratio:      {throughput_ratio:.6f}")
    print(f"Reference faster percent:       {(throughput_ratio - 1.0) * 100.0:.3f}%")
    print(f"Window numeric max abs diff:    {window_comparison['numeric_summary']['max_absolute_difference']}")
    print(f"Unique numeric max abs diff:    {unique_comparison['numeric_summary']['max_absolute_difference']}")
    print(f"Production windows planned:     {args.production_windows}")
    print("Measured worker plan:")
    for row in worker_plan.itertuples(index=False):
        print(
            f"  {row.worker_name}: weight={row.capacity_weight_normalized_to_candidate:.6f}; "
            f"share={row.target_window_share * 100.0:.4f}%; target_windows={int(row.target_windows_integer)}"
        )
    print(f"Estimated balanced wall days:   {summary['estimated_balanced_wall_days']:.3f}")
    print(f"Output directory:               {output_dir}")
    print("=" * 78)
    return 0 if status == "PASS" else 1


def self_test() -> None:
    # Verify tolerance semantics and exact-value normalization without needing
    # any A07 files or GPU dependencies.
    assert values_equal(None, np.nan)
    assert values_equal(True, True)
    assert not values_equal(True, False)
    abs_diff, rel_diff, comparable = numeric_difference(1.0, 1.000001)
    assert comparable and abs_diff is not None and rel_diff is not None
    assert abs_diff < 2e-6
    mock_reference = {"windows_per_second": 0.6, "gpu_name": "ref"}
    mock_candidate = {"windows_per_second": 0.5, "gpu_name": "cand"}
    plan = build_worker_plan(mock_reference, mock_candidate, 1000)
    assert len(plan) == 5
    assert int(plan["target_windows_integer"].sum()) == 1000
    assert plan.iloc[0]["capacity_weight_normalized_to_candidate"] == 1.2
    print("validate_cross_gpu_npr_benchmark self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a07/results/s173-ada0"),
        help="A07 reference result directory, normally Server 173 RTX 6000 Ada.",
    )
    parser.add_argument(
        "--candidate-dir",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a07/results/r158-a6000-0"),
        help="A07 candidate result directory, normally R158 RTX A6000.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a08"),
        help="A08 validation output directory.",
    )
    parser.add_argument(
        "--numeric-abs-tolerance",
        type=float,
        default=1e-4,
        help="Hard cross-GPU absolute tolerance for NPR/rank numeric values.",
    )
    parser.add_argument(
        "--numeric-rel-tolerance",
        type=float,
        default=1e-4,
        help="Hard cross-GPU relative tolerance for NPR/rank numeric values.",
    )
    parser.add_argument(
        "--production-windows",
        type=int,
        default=1113866,
        help="A06 expected unique production windows used only for capacity planning.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing A08 output directory.")
    parser.add_argument("--self-test", action="store_true", help="Run internal tests and exit.")
    args = parser.parse_args()
    if args.numeric_abs_tolerance < 0 or args.numeric_rel_tolerance < 0:
        parser.error("Numeric tolerances must be non-negative.")
    if args.production_windows <= 0:
        parser.error("--production-windows must be positive.")
    return args


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
