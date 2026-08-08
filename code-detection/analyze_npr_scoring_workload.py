#!/usr/bin/env python3
"""Analyze full A01 NPR scoring workload and build deterministic worker assignments.

This planning stage does not run any LLM model and does not calculate NPR.
It reads the A01 code-unit manifest in chunks, keeps primary code units only,
deduplicates by code-unit SHA-256, derives the exact number of 128-space-by-token
windows expected by A02, and creates a deterministic multi-worker assignment.

The assignment balances expected window counts rather than code-unit counts.
This is the correct first-order workload coordinate for A02 because each window
receives one original-rank evaluation plus the configured number of perturbation
rank evaluations.

The output worker plan is intentionally hardware-neutral by default. Optional
worker capacity weights can be supplied after measuring real throughput on each
GPU. A larger capacity weight gives that worker a proportionally larger target
window budget.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_VERSION = "run-x-a06-v1"
PRIMARY_ROLE = "primary"
REQUIRED_COLUMNS = {
    "dataset_source",
    "repo_name",
    "aggregation_role",
    "code_unit_sha256",
    "code_unit_relative_path",
    "code_unit_type",
    "space_by_token_count",
}


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    capacity_weight: float


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


def parse_workers(names_raw: str, weights_raw: str) -> list[WorkerSpec]:
    names = [item.strip() for item in names_raw.split(",") if item.strip()]
    if not names:
        raise ValueError("At least one worker name is required.")
    if len(set(names)) != len(names):
        raise ValueError("Worker names must be unique.")

    if weights_raw.strip():
        weights = [float(item.strip()) for item in weights_raw.split(",") if item.strip()]
        if len(weights) != len(names):
            raise ValueError("Worker weight count must match worker name count.")
    else:
        weights = [1.0] * len(names)

    if any((not math.isfinite(weight)) or weight <= 0 for weight in weights):
        raise ValueError("All worker capacity weights must be finite and positive.")
    return [WorkerSpec(name=name, capacity_weight=weight) for name, weight in zip(names, weights)]


def expected_windows(space_by_tokens: int, window_size: int) -> int:
    if space_by_tokens <= 0:
        raise ValueError(f"space_by_token_count must be positive, found {space_by_tokens}")
    return int(math.ceil(space_by_tokens / window_size))


def load_unique_primary_units(manifest: Path, window_size: int, chunksize: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    header = pd.read_csv(manifest, nrows=0)
    missing = sorted(REQUIRED_COLUMNS - set(header.columns))
    if missing:
        raise ValueError(f"Input manifest is missing required columns: {missing}")

    usecols = sorted(REQUIRED_COLUMNS)
    unique: dict[str, dict[str, Any]] = {}
    total_rows = 0
    primary_rows = 0
    duplicate_primary_occurrences = 0
    source_occurrences = {"treatment": 0, "control": 0}
    started = time.perf_counter()

    for chunk_index, chunk in enumerate(pd.read_csv(manifest, usecols=usecols, chunksize=chunksize), start=1):
        total_rows += len(chunk)
        primary = chunk[chunk["aggregation_role"].astype(str) == PRIMARY_ROLE].copy()
        primary_rows += len(primary)
        for source, count in primary["dataset_source"].astype(str).value_counts().items():
            source_occurrences[source] = source_occurrences.get(source, 0) + int(count)

        for row in primary.itertuples(index=False):
            row_map = row._asdict()
            code_sha = str(row_map["code_unit_sha256"])
            token_count = int(row_map["space_by_token_count"])
            existing = unique.get(code_sha)
            if existing is None:
                unique[code_sha] = {
                    "code_unit_sha256": code_sha,
                    "code_unit_relative_path": str(row_map["code_unit_relative_path"]),
                    "code_unit_type_representative": str(row_map["code_unit_type"]),
                    "space_by_token_count": token_count,
                    "expected_windows": expected_windows(token_count, window_size),
                    "manifest_occurrence_count": 1,
                    "treatment_occurrence_count": int(str(row_map["dataset_source"]) == "treatment"),
                    "control_occurrence_count": int(str(row_map["dataset_source"]) == "control"),
                }
            else:
                if int(existing["space_by_token_count"]) != token_count:
                    raise ValueError(f"Duplicate SHA has inconsistent space_by_token_count: {code_sha}")
                if str(existing["code_unit_relative_path"]) != str(row_map["code_unit_relative_path"]):
                    raise ValueError(f"Duplicate SHA has inconsistent artifact path: {code_sha}")
                existing["manifest_occurrence_count"] += 1
                existing["treatment_occurrence_count"] += int(str(row_map["dataset_source"]) == "treatment")
                existing["control_occurrence_count"] += int(str(row_map["dataset_source"]) == "control")
                duplicate_primary_occurrences += 1

        if chunk_index % 10 == 0:
            elapsed = time.perf_counter() - started
            print(
                f"Progress: chunks={chunk_index}; manifest_rows={total_rows}; "
                f"primary_rows={primary_rows}; unique_primary_units={len(unique)}; elapsed_seconds={elapsed:.1f}",
                flush=True,
            )

    frame = pd.DataFrame(unique.values())
    if frame.empty:
        raise ValueError("No primary code units were found.")
    frame = frame.sort_values("code_unit_sha256", kind="mergesort").reset_index(drop=True)
    stats = {
        "manifest_rows": int(total_rows),
        "primary_occurrences": int(primary_rows),
        "duplicate_primary_occurrences_after_first_sha": int(duplicate_primary_occurrences),
        "unique_primary_code_units": int(len(frame)),
        "primary_occurrences_by_dataset_source": source_occurrences,
    }
    return frame, stats


def weighted_lpt_assignment(units: pd.DataFrame, workers: list[WorkerSpec]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assign units by largest expected-window jobs first using normalized load.

    normalized_load = assigned_windows / worker_capacity_weight.
    This deterministic greedy rule gives faster workers more work when measured
    throughput weights are supplied, while equal weights reduce to ordinary LPT.
    """
    state = {
        worker.name: {
            "capacity_weight": float(worker.capacity_weight),
            "assigned_windows": 0,
            "assigned_units": 0,
            "assigned_space_by_tokens": 0,
        }
        for worker in workers
    }
    ordered = units.sort_values(
        ["expected_windows", "space_by_token_count", "code_unit_sha256"],
        ascending=[False, False, True],
        kind="mergesort",
    )
    assignment_rows: list[dict[str, Any]] = []
    for row in ordered.itertuples(index=False):
        selected = min(
            workers,
            key=lambda worker: (
                state[worker.name]["assigned_windows"] / worker.capacity_weight,
                state[worker.name]["assigned_windows"],
                worker.name,
            ),
        )
        worker_state = state[selected.name]
        worker_state["assigned_windows"] += int(row.expected_windows)
        worker_state["assigned_units"] += 1
        worker_state["assigned_space_by_tokens"] += int(row.space_by_token_count)
        assignment_rows.append(
            {
                "worker_name": selected.name,
                "worker_capacity_weight": float(selected.capacity_weight),
                "code_unit_sha256": str(row.code_unit_sha256),
                "code_unit_relative_path": str(row.code_unit_relative_path),
                "code_unit_type_representative": str(row.code_unit_type_representative),
                "space_by_token_count": int(row.space_by_token_count),
                "expected_windows": int(row.expected_windows),
                "manifest_occurrence_count": int(row.manifest_occurrence_count),
                "treatment_occurrence_count": int(row.treatment_occurrence_count),
                "control_occurrence_count": int(row.control_occurrence_count),
            }
        )

    assignment = pd.DataFrame(assignment_rows).sort_values(
        ["worker_name", "code_unit_sha256"], kind="mergesort"
    ).reset_index(drop=True)
    total_windows = int(assignment["expected_windows"].sum())
    total_weight = float(sum(worker.capacity_weight for worker in workers))
    summary_rows: list[dict[str, Any]] = []
    for worker in workers:
        worker_state = state[worker.name]
        target_share = float(worker.capacity_weight / total_weight)
        actual_share = float(worker_state["assigned_windows"] / total_windows) if total_windows else 0.0
        summary_rows.append(
            {
                "worker_name": worker.name,
                "capacity_weight": float(worker.capacity_weight),
                "assigned_unique_units": int(worker_state["assigned_units"]),
                "assigned_expected_windows": int(worker_state["assigned_windows"]),
                "assigned_space_by_tokens": int(worker_state["assigned_space_by_tokens"]),
                "target_window_share": target_share,
                "actual_window_share": actual_share,
                "normalized_window_load": float(worker_state["assigned_windows"] / worker.capacity_weight),
            }
        )
    return assignment, pd.DataFrame(summary_rows)


def distribution_summary(series: pd.Series) -> dict[str, Any]:
    quantiles = series.quantile([0.0, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 0.999, 1.0])
    return {f"p{int(q * 1000):03d}": float(value) for q, value in quantiles.items()}


def build_window_buckets(units: pd.DataFrame) -> pd.DataFrame:
    bins = [0, 1, 2, 4, 8, 16, 32, 64, 128, math.inf]
    labels = ["1", "2", "3-4", "5-8", "9-16", "17-32", "33-64", "65-128", "129+"]
    bucket = pd.cut(units["expected_windows"], bins=bins, labels=labels, include_lowest=True)
    grouped = units.assign(window_bucket=bucket).groupby("window_bucket", observed=False)
    rows = []
    for name, group in grouped:
        rows.append(
            {
                "window_bucket": str(name),
                "unique_units": int(len(group)),
                "expected_windows": int(group["expected_windows"].sum()),
                "space_by_tokens": int(group["space_by_token_count"].sum()),
                "manifest_occurrences": int(group["manifest_occurrence_count"].sum()),
            }
        )
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze A02 full NPR scoring workload and plan workers.")
    parser.add_argument("--input-code-unit-manifest", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--perturbations-per-window", type=int, default=50)
    parser.add_argument("--chunksize", type=int, default=100_000)
    parser.add_argument(
        "--worker-names",
        default="s173-gpu0,s173-gpu1,r158-gpu0,r158-gpu1,r158-gpu2",
    )
    parser.add_argument(
        "--worker-capacity-weights",
        default="",
        help="Comma-separated positive relative throughput weights. Empty means equal weights.",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def run_self_test() -> None:
    assert expected_windows(1, 128) == 1
    assert expected_windows(128, 128) == 1
    assert expected_windows(129, 128) == 2
    assert expected_windows(256, 128) == 2
    assert expected_windows(257, 128) == 3
    workers = parse_workers("a,b", "1,2")
    units = pd.DataFrame(
        [
            {"code_unit_sha256": f"{i:064x}", "code_unit_relative_path": f"code_units/{i}.txt", "code_unit_type_representative": "function_body", "space_by_token_count": w * 128, "expected_windows": w, "manifest_occurrence_count": 1, "treatment_occurrence_count": 1, "control_occurrence_count": 0}
            for i, w in enumerate([9, 8, 7, 6, 5, 4, 3, 2, 1], start=1)
        ]
    )
    assignment, summary = weighted_lpt_assignment(units, workers)
    assert len(assignment) == len(units)
    assert int(summary["assigned_expected_windows"].sum()) == int(units["expected_windows"].sum())
    print("analyze_npr_scoring_workload self-test: PASS")


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0
    if args.window_size <= 0 or args.perturbations_per_window <= 0 or args.chunksize <= 0:
        raise ValueError("window size, perturbations per window, and chunksize must be positive.")
    workers = parse_workers(args.worker_names, args.worker_capacity_weights)
    if args.input_code_unit_manifest is None or args.output_dir is None:
        raise ValueError("--input-code-unit-manifest and --output-dir are required unless --self-test is used.")
    manifest = args.input_code_unit_manifest.resolve()
    if not manifest.is_file():
        raise FileNotFoundError(manifest)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    unique_units, manifest_stats = load_unique_primary_units(manifest, args.window_size, args.chunksize)
    assignment, worker_summary = weighted_lpt_assignment(unique_units, workers)
    buckets = build_window_buckets(unique_units)

    unique_output = args.output_dir / "npr_scoring_unique_unit_workload.csv"
    assignment_output = args.output_dir / "npr_scoring_worker_assignment.csv"
    worker_output = args.output_dir / "npr_scoring_worker_summary.csv"
    bucket_output = args.output_dir / "npr_scoring_window_buckets.csv"
    top_output = args.output_dir / "npr_scoring_top_units.csv"
    summary_output = args.output_dir / "npr_scoring_workload_summary.json"

    atomic_csv(unique_units, unique_output)
    atomic_csv(assignment, assignment_output)
    atomic_csv(worker_summary, worker_output)
    atomic_csv(buckets, bucket_output)
    atomic_csv(
        unique_units.sort_values(["expected_windows", "space_by_token_count"], ascending=False, kind="mergesort").head(1000),
        top_output,
    )

    total_windows = int(unique_units["expected_windows"].sum())
    total_space_by_tokens = int(unique_units["space_by_token_count"].sum())
    occurrence_count = int(unique_units["manifest_occurrence_count"].sum())
    dedup_ratio = float(len(unique_units) / occurrence_count)
    estimated_rank_evaluations = int(total_windows * (1 + args.perturbations_per_window))
    elapsed = time.perf_counter() - started
    summary = {
        "status": "PASS",
        "implementation_version": SCRIPT_VERSION,
        "input_manifest": str(manifest),
        "input_manifest_sha256": sha256_file(manifest),
        "window_size_space_by_tokens": int(args.window_size),
        "perturbations_per_window": int(args.perturbations_per_window),
        **manifest_stats,
        "unique_primary_space_by_tokens": total_space_by_tokens,
        "expected_unique_windows": total_windows,
        "estimated_original_rank_evaluations": total_windows,
        "estimated_perturbed_rank_evaluations": int(total_windows * args.perturbations_per_window),
        "estimated_total_rank_evaluations": estimated_rank_evaluations,
        "unique_unit_to_occurrence_ratio": dedup_ratio,
        "occurrence_reuse_fraction": float(1.0 - dedup_ratio),
        "space_by_token_distribution": distribution_summary(unique_units["space_by_token_count"]),
        "expected_window_distribution": distribution_summary(unique_units["expected_windows"]),
        "workers": [worker.__dict__ for worker in workers],
        "worker_capacity_weights_are_measured": bool(args.worker_capacity_weights.strip()),
        "elapsed_seconds": float(elapsed),
        "outputs": {
            "unique_unit_workload": str(unique_output),
            "worker_assignment": str(assignment_output),
            "worker_summary": str(worker_output),
            "window_buckets": str(bucket_output),
            "top_units": str(top_output),
        },
    }
    atomic_json(summary, summary_output)

    print("=" * 78)
    print("run-x-a06 NPR scoring workload analysis")
    print(f"Primary occurrences:           {occurrence_count}")
    print(f"Unique primary units:          {len(unique_units)}")
    print(f"Unique space-by tokens:        {total_space_by_tokens}")
    print(f"Expected unique windows:       {total_windows}")
    print(f"Perturbations per window:      {args.perturbations_per_window}")
    print(f"Estimated rank evaluations:    {estimated_rank_evaluations}")
    print(f"Occurrence reuse fraction:     {1.0 - dedup_ratio:.4%}")
    print("Worker plan:")
    for row in worker_summary.itertuples(index=False):
        print(
            f"  {row.worker_name}: units={row.assigned_unique_units}; "
            f"windows={row.assigned_expected_windows}; share={row.actual_window_share:.4%}; "
            f"weight={row.capacity_weight:g}"
        )
    print(f"Summary:                       {summary_output}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        raise
