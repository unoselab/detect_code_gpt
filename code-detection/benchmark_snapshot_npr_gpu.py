#!/usr/bin/env python3
"""Prepare and run a deterministic cross-GPU NPR throughput benchmark.

This experiment is intentionally separate from production A02 scoring.
It reuses the canonical A02 Python implementation directly so the benchmark
measures the same window construction, perturbation, rank, and NPR logic that
will be used in production.

Modes
-----
prepare:
    Read the A06 unique-unit workload table, select a deterministic stratified
    benchmark sample, verify and copy only the selected A05 code-unit artifacts,
    and create a self-contained benchmark bundle. The bundle can be copied to
    another server before either benchmark run starts. No server-to-server
    communication is required during scoring.

run:
    Load the self-contained benchmark bundle, import the canonical A02 scoring
    implementation, load the configured model on one visible GPU, score every
    selected code unit without cache reuse, and write detailed timing and NPR
    results for later cross-system comparison.

The benchmark does not classify code as AI-generated/human-written and does not
change any A02 production cache or output.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import shutil
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_VERSION = "run-x-a07-v1"
DEFAULT_BUCKET_QUOTAS = {
    "1": 3,
    "2": 2,
    "3-4": 2,
    "5-8": 1,
    "9-16": 1,
    "17-32": 1,
    "33-64": 1,
}
BUNDLE_MANIFEST_COLUMNS = [
    "benchmark_order",
    "benchmark_bucket",
    "code_unit_sha256",
    "code_unit_relative_path",
    "code_unit_type",
    "space_by_token_count",
    "expected_windows",
    "manifest_occurrence_count",
    "treatment_occurrence_count",
    "control_occurrence_count",
]


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


def atomic_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    os.replace(tmp, path)


def atomic_csv(frame: pd.DataFrame, path: Path, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = frame.copy()
    if columns is not None:
        for column in columns:
            if column not in output.columns:
                output[column] = pd.Series(dtype="object")
        output = output[columns]
    tmp = path.with_suffix(path.suffix + ".tmp")
    output.to_csv(tmp, index=False, quoting=csv.QUOTE_MINIMAL)
    os.replace(tmp, path)


def window_bucket(expected_windows: int) -> str:
    if expected_windows == 1:
        return "1"
    if expected_windows == 2:
        return "2"
    if 3 <= expected_windows <= 4:
        return "3-4"
    if 5 <= expected_windows <= 8:
        return "5-8"
    if 9 <= expected_windows <= 16:
        return "9-16"
    if 17 <= expected_windows <= 32:
        return "17-32"
    if 33 <= expected_windows <= 64:
        return "33-64"
    if 65 <= expected_windows <= 128:
        return "65-128"
    return "129+"


def evenly_spaced_indices(length: int, count: int) -> list[int]:
    if count <= 0 or length <= 0:
        return []
    count = min(count, length)
    if count == 1:
        return [length // 2]
    raw = np.linspace(0, length - 1, num=count)
    indices = sorted({int(round(value)) for value in raw})
    if len(indices) < count:
        for index in range(length):
            if index not in indices:
                indices.append(index)
                if len(indices) == count:
                    break
    return sorted(indices[:count])


def select_benchmark_units(workload: pd.DataFrame, quotas: dict[str, int]) -> pd.DataFrame:
    required = {
        "code_unit_sha256",
        "code_unit_relative_path",
        "code_unit_type_representative",
        "space_by_token_count",
        "expected_windows",
        "manifest_occurrence_count",
        "treatment_occurrence_count",
        "control_occurrence_count",
    }
    missing = sorted(required - set(workload.columns))
    if missing:
        raise ValueError(f"A06 unique-unit workload is missing columns: {missing}")

    frame = workload.copy()
    frame["expected_windows"] = pd.to_numeric(frame["expected_windows"], errors="raise").astype(int)
    frame["space_by_token_count"] = pd.to_numeric(frame["space_by_token_count"], errors="raise").astype(int)
    frame["benchmark_bucket"] = frame["expected_windows"].map(window_bucket)

    selected_frames: list[pd.DataFrame] = []
    for bucket_name, quota in quotas.items():
        candidates = frame[frame["benchmark_bucket"] == bucket_name].sort_values(
            ["space_by_token_count", "code_unit_sha256"], kind="mergesort"
        )
        if len(candidates) < quota:
            raise ValueError(
                f"Benchmark bucket {bucket_name!r} has only {len(candidates)} units; quota={quota}."
            )
        indices = evenly_spaced_indices(len(candidates), quota)
        selected_frames.append(candidates.iloc[indices].copy())

    selected = pd.concat(selected_frames, ignore_index=True)
    if selected["code_unit_sha256"].duplicated().any():
        raise AssertionError("Benchmark selection contains duplicate code-unit SHA values.")
    selected = selected.sort_values(
        ["expected_windows", "space_by_token_count", "code_unit_sha256"],
        kind="mergesort",
    ).reset_index(drop=True)
    selected.insert(0, "benchmark_order", range(1, len(selected) + 1))
    selected = selected.rename(columns={"code_unit_type_representative": "code_unit_type"})
    return selected[BUNDLE_MANIFEST_COLUMNS]


def verify_and_copy_artifacts(selected: pd.DataFrame, artifact_base: Path, bundle_dir: Path) -> int:
    copied_bytes = 0
    for row in selected.itertuples(index=False):
        source = artifact_base / str(row.code_unit_relative_path)
        if not source.is_file():
            raise FileNotFoundError(f"Missing selected A05 artifact: {source}")
        raw = source.read_bytes()
        observed_sha = sha256_bytes(raw)
        if observed_sha != str(row.code_unit_sha256):
            raise ValueError(
                f"Selected artifact SHA mismatch: {source}; observed={observed_sha}; expected={row.code_unit_sha256}"
            )
        text = raw.decode("utf-8")
        observed_tokens = len(text.split(" "))
        if observed_tokens != int(row.space_by_token_count):
            raise ValueError(
                f"Selected artifact token-count mismatch: {source}; observed={observed_tokens}; expected={row.space_by_token_count}"
            )
        destination = bundle_dir / str(row.code_unit_relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        copied_bytes += len(raw)
    return copied_bytes


def prepare_bundle(args: argparse.Namespace) -> int:
    workload = pd.read_csv(args.a06_unique_workload)
    selected = select_benchmark_units(workload, DEFAULT_BUCKET_QUOTAS)

    if args.bundle_dir.exists():
        if not args.overwrite:
            raise FileExistsError(
                f"Benchmark bundle already exists: {args.bundle_dir}. Use --overwrite to replace it."
            )
        shutil.rmtree(args.bundle_dir)
    args.bundle_dir.mkdir(parents=True, exist_ok=True)

    copied_bytes = verify_and_copy_artifacts(selected, args.artifact_base, args.bundle_dir)
    manifest_path = args.bundle_dir / "benchmark_units.csv"
    atomic_csv(selected, manifest_path, BUNDLE_MANIFEST_COLUMNS)

    expected_windows = int(selected["expected_windows"].sum())
    bucket_summary = (
        selected.groupby("benchmark_bucket", sort=False)
        .agg(unique_units=("code_unit_sha256", "size"), expected_windows=("expected_windows", "sum"))
        .reset_index()
    )
    atomic_csv(bucket_summary, args.bundle_dir / "benchmark_bucket_summary.csv")

    payload = {
        "status": "PASS",
        "implementation_version": SCRIPT_VERSION,
        "prepared_utc": utc_now(),
        "a06_unique_workload": str(args.a06_unique_workload.resolve()),
        "a06_unique_workload_sha256": sha256_file(args.a06_unique_workload),
        "artifact_base": str(args.artifact_base.resolve()),
        "benchmark_units": int(len(selected)),
        "benchmark_expected_windows": expected_windows,
        "benchmark_estimated_rank_evaluations": int(expected_windows * (1 + args.perturbations_per_window)),
        "perturbations_per_window": int(args.perturbations_per_window),
        "window_size_space_by_tokens": int(args.window_size),
        "selected_artifact_bytes": int(copied_bytes),
        "selection_policy": {
            "bucket_quotas": DEFAULT_BUCKET_QUOTAS,
            "within_bucket_order": "space_by_token_count,code_unit_sha256",
            "within_bucket_selection": "evenly_spaced_indices",
            "excluded_large_buckets": ["65-128", "129+"],
            "note": "Very large code units are excluded because A02 cost is per 128-space-by-token window; including them would lengthen the benchmark without changing window semantics.",
        },
        "bundle_manifest": "benchmark_units.csv",
        "bundle_manifest_sha256": sha256_file(manifest_path),
    }
    atomic_json(payload, args.bundle_dir / "benchmark_bundle_metadata.json")

    print("=" * 78)
    print("run-x-a07 benchmark bundle preparation")
    print(f"Status:                         PASS")
    print(f"Selected unique units:          {len(selected)}")
    print(f"Expected windows:               {expected_windows}")
    print(f"Estimated rank evaluations:     {expected_windows * (1 + args.perturbations_per_window)}")
    print(f"Selected artifact bytes:        {copied_bytes}")
    print(f"Bundle directory:               {args.bundle_dir}")
    print("Bucket plan:")
    for row in bucket_summary.itertuples(index=False):
        print(f"  {row.benchmark_bucket}: units={row.unique_units}; windows={row.expected_windows}")
    print("=" * 78)
    return 0


def import_a02_module(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Canonical A02 Python implementation not found: {path}")
    spec = importlib.util.spec_from_file_location("a02_score_snapshot_npr", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create import specification for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def quantile_summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "p50": None, "p90": None, "p95": None, "max": None, "mean": None}
    array = np.asarray(values, dtype=float)
    return {
        "min": float(np.min(array)),
        "p50": float(np.quantile(array, 0.50)),
        "p90": float(np.quantile(array, 0.90)),
        "p95": float(np.quantile(array, 0.95)),
        "max": float(np.max(array)),
        "mean": float(np.mean(array)),
    }


def run_benchmark(args: argparse.Namespace) -> int:
    manifest_path = args.bundle_dir / "benchmark_units.csv"
    metadata_path = args.bundle_dir / "benchmark_bundle_metadata.json"
    if not manifest_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(
            f"Benchmark bundle is incomplete: expected {manifest_path} and {metadata_path}."
        )
    selected = pd.read_csv(manifest_path)
    missing = sorted(set(BUNDLE_MANIFEST_COLUMNS) - set(selected.columns))
    if missing:
        raise ValueError(f"Benchmark bundle manifest is missing columns: {missing}")

    project_root = args.project_root.resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    a02 = import_a02_module(args.a02_script.resolve())

    config = a02.DetectorConfig(
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
    package_versions = a02.collect_package_versions()
    detector_source_hashes = a02.collect_detector_source_hashes(project_root)
    fingerprint_payload = config.payload(detector_source_hashes, package_versions)
    fingerprint = a02.stable_json_hash(fingerprint_payload)

    runtime_args = argparse.Namespace(
        project_root=project_root,
        quiet_internal_progress=True,
        detector_log_level=args.detector_log_level,
        device="cuda",
        model_cache_dir=args.model_cache_dir.expanduser(),
        detector_output_name=f"run_x_a07_{args.system_label}",
    )

    output_dir = args.output_dir
    if output_dir.exists() and args.overwrite:
        shutil.rmtree(output_dir)
    elif output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Benchmark output already exists and is non-empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Verify the exact bundle before loading a large model.
    artifact_errors: list[dict[str, Any]] = []
    for row in selected.itertuples(index=False):
        path = args.bundle_dir / str(row.code_unit_relative_path)
        if not path.is_file():
            artifact_errors.append({"code_unit_sha256": row.code_unit_sha256, "error": "missing_artifact"})
            continue
        raw = path.read_bytes()
        observed_sha = sha256_bytes(raw)
        if observed_sha != str(row.code_unit_sha256):
            artifact_errors.append({"code_unit_sha256": row.code_unit_sha256, "error": "sha256_mismatch"})
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            artifact_errors.append({"code_unit_sha256": row.code_unit_sha256, "error": "utf8_decode_error"})
            continue
        if len(text.split(" ")) != int(row.space_by_token_count):
            artifact_errors.append({"code_unit_sha256": row.code_unit_sha256, "error": "space_by_token_count_mismatch"})
    atomic_csv(pd.DataFrame(artifact_errors), output_dir / "benchmark_artifact_errors.csv")
    if artifact_errors:
        raise RuntimeError(f"Benchmark artifact verification failed for {len(artifact_errors)} units.")

    total_started = time.perf_counter()
    runtime = a02.load_runtime(config, runtime_args)
    scoring_started = time.perf_counter()
    unique_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for position, row in enumerate(selected.itertuples(index=False), start=1):
        row_series = pd.Series({
            "code_unit_sha256": str(row.code_unit_sha256),
            "code_unit_relative_path": str(row.code_unit_relative_path),
            "code_unit_type": str(row.code_unit_type),
            "space_by_token_count": int(row.space_by_token_count),
        })
        text = (args.bundle_dir / str(row.code_unit_relative_path)).read_bytes().decode("utf-8")
        try:
            unique_score, unit_windows = a02.score_code_unit(
                row_series,
                text,
                config,
                fingerprint,
                a02.score_window_real,
                runtime,
            )
            unique_score["benchmark_order"] = int(row.benchmark_order)
            unique_score["benchmark_bucket"] = str(row.benchmark_bucket)
            unique_rows.append(unique_score)
            for item in unit_windows:
                item["benchmark_order"] = int(row.benchmark_order)
                item["benchmark_bucket"] = str(row.benchmark_bucket)
            window_rows.extend(unit_windows)
        except Exception as error:
            failures.append({
                "benchmark_order": int(row.benchmark_order),
                "benchmark_bucket": str(row.benchmark_bucket),
                "code_unit_sha256": str(row.code_unit_sha256),
                "error_type": type(error).__name__,
                "error_message": str(error)[:4000],
            })
        print(
            f"Benchmark progress: unit={position}/{len(selected)}; windows_so_far={len(window_rows)}; failures={len(failures)}",
            flush=True,
        )

    scoring_wall_seconds = time.perf_counter() - scoring_started
    total_wall_seconds = time.perf_counter() - total_started
    unique_frame = pd.DataFrame(unique_rows)
    window_frame = pd.DataFrame(window_rows)
    failure_frame = pd.DataFrame(failures)
    atomic_csv(unique_frame, output_dir / "benchmark_unique_scores.csv")
    atomic_csv(window_frame, output_dir / "benchmark_window_scores.csv")
    atomic_csv(failure_frame, output_dir / "benchmark_failures.csv")

    valid_windows = int(window_frame["window_npr_valid"].astype(bool).sum()) if not window_frame.empty else 0
    invalid_windows = int(len(window_frame) - valid_windows)
    expected_windows = int(selected["expected_windows"].sum())
    expected_rank_evaluations = int(expected_windows * (1 + args.perturbations_per_window))
    valid_perturbation_scores = int(window_frame["valid_perturbation_scores"].sum()) if not window_frame.empty else 0
    window_seconds = [float(value) for value in window_frame.get("scoring_seconds", pd.Series(dtype=float)).dropna().tolist()]

    peak_allocated = 0
    peak_reserved = 0
    if runtime.torch.cuda.is_available():
        peak_allocated = int(runtime.torch.cuda.max_memory_allocated())
        peak_reserved = int(runtime.torch.cuda.max_memory_reserved())

    status = "PASS" if not failures and len(window_frame) == expected_windows and invalid_windows == 0 else "FAIL"
    summary = {
        "status": status,
        "implementation_version": SCRIPT_VERSION,
        "system_label": args.system_label,
        "hostname": socket.gethostname(),
        "completed_utc": utc_now(),
        "benchmark_bundle_manifest_sha256": sha256_file(manifest_path),
        "a02_script": str(args.a02_script.resolve()),
        "a02_script_sha256": sha256_file(args.a02_script),
        "scoring_config_fingerprint": fingerprint,
        "scoring_configuration": fingerprint_payload,
        "gpu_name": runtime.gpu_name,
        "gpu_total_memory_bytes": int(runtime.gpu_total_memory_bytes),
        "reported_model_context_limit": runtime.reported_model_context_limit,
        "model_load_seconds": float(runtime.model_load_seconds),
        "benchmark_unique_units_expected": int(len(selected)),
        "benchmark_unique_units_successful": int(len(unique_frame)),
        "benchmark_unique_units_failed": int(len(failure_frame)),
        "benchmark_windows_expected": expected_windows,
        "benchmark_windows_observed": int(len(window_frame)),
        "benchmark_valid_windows": valid_windows,
        "benchmark_invalid_windows": invalid_windows,
        "perturbations_per_window": int(args.perturbations_per_window),
        "valid_perturbation_scores": valid_perturbation_scores,
        "expected_rank_evaluations": expected_rank_evaluations,
        "scoring_wall_seconds_excluding_model_load": float(scoring_wall_seconds),
        "total_wall_seconds_including_model_load": float(total_wall_seconds),
        "windows_per_second": float(len(window_frame) / scoring_wall_seconds) if scoring_wall_seconds > 0 else None,
        "estimated_rank_evaluations_per_second": float(expected_rank_evaluations / scoring_wall_seconds) if scoring_wall_seconds > 0 else None,
        "window_scoring_seconds_distribution": quantile_summary(window_seconds),
        "peak_cuda_memory_allocated_bytes": peak_allocated,
        "peak_cuda_memory_reserved_bytes": peak_reserved,
        "package_versions": package_versions,
        "detector_source_hashes": detector_source_hashes,
        "notes": {
            "cache_policy": "disabled for benchmark; each selected unit is scored exactly once",
            "server_communication": "none; benchmark bundle is prepared before scoring and can be copied independently to each server",
            "comparison_gate": "Before production sharding, require identical bundle manifest SHA, A02 script SHA, detector source hashes, scoring configuration, and compatible package versions across systems.",
        },
    }
    atomic_json(summary, output_dir / "benchmark_summary.json")

    print("=" * 78)
    print("run-x-a07 cross-GPU NPR benchmark")
    print(f"Status:                         {status}")
    print(f"System label:                   {args.system_label}")
    print(f"Hostname:                       {socket.gethostname()}")
    print(f"GPU:                            {runtime.gpu_name}")
    print(f"A02 script SHA:                 {sha256_file(args.a02_script)}")
    print(f"Config fingerprint:             {fingerprint}")
    print(f"Unique units:                   {len(unique_frame)}/{len(selected)}")
    print(f"Windows:                        {len(window_frame)}/{expected_windows}")
    print(f"Invalid windows:                {invalid_windows}")
    print(f"Model load seconds:             {runtime.model_load_seconds:.3f}")
    print(f"Scoring wall seconds:           {scoring_wall_seconds:.3f}")
    print(f"Windows/second:                 {len(window_frame) / scoring_wall_seconds:.6f}")
    print(f"Estimated rank evals/second:    {expected_rank_evaluations / scoring_wall_seconds:.3f}")
    print(f"Peak CUDA allocated bytes:      {peak_allocated}")
    print(f"Peak CUDA reserved bytes:       {peak_reserved}")
    print(f"Output directory:               {output_dir}")
    print("=" * 78)
    return 0 if status == "PASS" else 5


def run_self_test() -> None:
    cases = {
        1: "1",
        2: "2",
        3: "3-4",
        4: "3-4",
        5: "5-8",
        8: "5-8",
        9: "9-16",
        16: "9-16",
        17: "17-32",
        32: "17-32",
        33: "33-64",
        64: "33-64",
        65: "65-128",
        128: "65-128",
        129: "129+",
    }
    for value, expected in cases.items():
        observed = window_bucket(value)
        if observed != expected:
            raise AssertionError(f"window_bucket({value})={observed!r}, expected={expected!r}")
    if evenly_spaced_indices(10, 3) != [0, 4, 9]:
        raise AssertionError("evenly_spaced_indices self-test failed")
    print("benchmark_snapshot_npr_gpu self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare or run the A07 cross-GPU NPR benchmark.")
    parser.add_argument("--mode", choices=("prepare", "run"), required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--a06-unique-workload",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a06/npr_scoring_unique_unit_workload.csv"),
    )
    parser.add_argument(
        "--artifact-base",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a05"),
    )
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a07/benchmark_bundle"),
    )
    parser.add_argument(
        "--a02-script",
        type=Path,
        default=Path("code-detection/score_snapshot_npr.py"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a07/results/local"),
    )
    parser.add_argument("--system-label", default=socket.gethostname().replace(".", "_"))
    parser.add_argument("--scoring-model", default="bigcode/starcoder2-7b")
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--perturbations-per-window", type=int, default=50)
    parser.add_argument("--perturbation-type", default="random-insert-space+newline")
    parser.add_argument("--random-seed", type=int, default=20260723)
    parser.add_argument("--pct-words-masked", type=float, default=0.5)
    parser.add_argument("--span-length", type=int, default=2)
    parser.add_argument("--perturbation-chunk-size", type=int, default=10)
    parser.add_argument("--n-perturbation-rounds", type=int, default=1)
    parser.add_argument("--model-cache-dir", type=Path, default=Path("~/.cache/huggingface/hub"))
    parser.add_argument("--detector-log-level", default="WARNING")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    args.project_root = args.project_root.resolve()
    args.model_cache_dir = args.model_cache_dir.expanduser()
    return args


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return
    if args.mode == "prepare":
        raise SystemExit(prepare_bundle(args))
    raise SystemExit(run_benchmark(args))


if __name__ == "__main__":
    main()
