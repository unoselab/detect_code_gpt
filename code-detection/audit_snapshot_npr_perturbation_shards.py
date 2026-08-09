#!/usr/bin/env python3
"""Audit merged A09 perturbation shards and build exact staged scoring plans.

This CPU-only stage is the gate between A09 perturbation materialization and
long-running homogeneous GPU NPR scoring on R158.

The audit intentionally avoids re-parsing all 55.7 million perturbation texts.
A09 already records a SHA-256 for every deterministic gzip shard. A10 therefore
verifies every complete shard byte-for-byte against its A09 summary, reconciles
all shard summary totals against the A09 plan, and samples records from every
shard for semantic checks. Exact FUN/C_FUN/BLOCK workloads are computed from
A09's globally deduplicated 419,220-unit plan, where every unit already stores
its group membership and exact expected window count.

No StarCoder2 model is loaded and no NPR, threshold, AGC/HWC, SonarQube, or DiD
result is computed here.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import platform
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCRIPT_VERSION = "run-x-a10-v1"
A09_EXPECTED_VERSION = "run-x-a09-v3"
GROUPS = ("FUN", "C_FUN", "BLOCK")
CHECK_COLUMNS = ["check_name", "passed", "observed", "expected", "note"]


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


def derive_window_seed(global_seed: int, code_unit_sha: str, window_index: int) -> int:
    raw = f"{global_seed}|{code_unit_sha}|{window_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], "big", signed=False)


def stable_shard(code_unit_sha: str, data_shards: int) -> int:
    if len(code_unit_sha) != 64:
        raise ValueError(f"Invalid SHA-256 value: {code_unit_sha!r}")
    return int(code_unit_sha[:16], 16) % data_shards


def ordered_text_digest(texts: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for text in texts:
        raw = text.encode("utf-8")
        digest.update(len(raw).to_bytes(8, "big", signed=False))
        digest.update(raw)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def atomic_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    os.replace(tmp, path)


def atomic_csv(rows: list[dict[str, Any]], path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    os.replace(tmp, path)


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    note: str = "",
) -> None:
    checks.append(
        {
            "check_name": name,
            "passed": bool(passed),
            "observed": observed,
            "expected": expected,
            "note": note,
        }
    )


def parse_shard_id(path: Path) -> int:
    name = path.name
    if not name.startswith("shard-") or "-of-" not in name:
        raise ValueError(f"Unexpected shard filename: {name}")
    return int(name[len("shard-"): name.index("-of-")])


def read_csv_by_key(path: Path, key: str) -> dict[int, dict[str, str]]:
    result: dict[int, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or key not in reader.fieldnames:
            raise ValueError(f"Missing {key!r} in {path}")
        for row in reader:
            numeric_key = int(row[key])
            if numeric_key in result:
                raise ValueError(f"Duplicate {key}={numeric_key} in {path}")
            result[numeric_key] = row
    return result


def audit_sample_records(
    shard_path: Path,
    shard_id: int,
    sample_count: int,
    data_shards: int,
    random_seed: int,
    perturbations_per_window: int,
    config_fingerprint: str,
) -> tuple[int, list[str]]:
    """Inspect the first N JSONL records; full-file integrity is covered by gzip SHA."""
    checked = 0
    errors: list[str] = []
    if sample_count <= 0:
        return 0, errors

    with gzip.open(shard_path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if checked >= sample_count:
                break
            record = json.loads(line)
            code_sha = str(record.get("code_unit_sha256", ""))
            window_index = int(record.get("window_index", -1))
            groups = record.get("unit_groups")
            original_text = str(record.get("original_text", ""))
            perturbations = record.get("perturbations")

            if stable_shard(code_sha, data_shards) != shard_id:
                errors.append(f"sample row {line_number}: stable shard mismatch")
            if str(record.get("config_fingerprint")) != config_fingerprint:
                errors.append(f"sample row {line_number}: config fingerprint mismatch")
            if int(record.get("window_seed", -1)) != derive_window_seed(random_seed, code_sha, window_index):
                errors.append(f"sample row {line_number}: window seed mismatch")
            if sha256_bytes(original_text.encode("utf-8")) != str(record.get("window_text_sha256")):
                errors.append(f"sample row {line_number}: original text SHA mismatch")
            if len(original_text.split(" ")) != int(record.get("window_space_by_token_count", -1)):
                errors.append(f"sample row {line_number}: window token count mismatch")
            if not isinstance(groups, list) or not groups or any(str(group) not in GROUPS for group in groups):
                errors.append(f"sample row {line_number}: invalid unit_groups={groups!r}")
            if not isinstance(perturbations, list):
                errors.append(f"sample row {line_number}: perturbations is not a list")
            else:
                if len(perturbations) != perturbations_per_window:
                    errors.append(f"sample row {line_number}: perturbation count mismatch")
                if int(record.get("perturbation_count", -1)) != len(perturbations):
                    errors.append(f"sample row {line_number}: perturbation_count field mismatch")
                observed_digest = ordered_text_digest(str(value) for value in perturbations)
                if observed_digest != str(record.get("perturbations_ordered_sha256")):
                    errors.append(f"sample row {line_number}: perturbation ordered digest mismatch")
            checked += 1
    return checked, errors


def build_assignment(rows: list[dict[str, Any]], policy: str) -> list[dict[str, Any]]:
    if policy == "logical_shard_mod_3":
        assignment = {int(row["logical_shard"]): int(row["logical_shard"]) % 3 for row in rows}
    elif policy == "deterministic_lpt_by_fun_windows":
        loads = [0, 0, 0]
        assignment: dict[int, int] = {}
        for row in sorted(rows, key=lambda value: (-int(value["fun_windows"]), int(value["logical_shard"]))):
            gpu = min(range(3), key=lambda index: (loads[index], index))
            shard_id = int(row["logical_shard"])
            assignment[shard_id] = gpu
            loads[gpu] += int(row["fun_windows"])
    else:
        raise ValueError(f"Unknown assignment policy: {policy}")

    result: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda value: int(value["logical_shard"])):
        shard_id = int(row["logical_shard"])
        result.append(
            {
                "logical_shard": shard_id,
                "gpu_index": assignment[shard_id],
                "fun_unique_units": int(row["fun_unique_units"]),
                "fun_windows": int(row["fun_windows"]),
                "fun_perturbations": int(row["fun_perturbations"]),
                "assignment_policy": policy,
            }
        )
    return result


def gpu_window_loads(plan: list[dict[str, Any]]) -> list[int]:
    loads = [0, 0, 0]
    for row in plan:
        loads[int(row["gpu_index"])] += int(row["fun_windows"])
    return loads


def imbalance_fraction(loads: list[int]) -> float:
    if not loads or sum(loads) == 0:
        return 0.0
    mean = sum(loads) / len(loads)
    return (max(loads) - min(loads)) / mean


def run_self_test() -> None:
    assert stable_shard("0" * 64, 96) == 0
    assert derive_window_seed(20260723, "a" * 64, 3) == derive_window_seed(20260723, "a" * 64, 3)
    sample = ["a", "b c", ""]
    assert ordered_text_digest(sample) == ordered_text_digest(sample)
    synthetic = [
        {"logical_shard": 0, "fun_unique_units": 5, "fun_windows": 100, "fun_perturbations": 5000},
        {"logical_shard": 1, "fun_unique_units": 4, "fun_windows": 80, "fun_perturbations": 4000},
        {"logical_shard": 2, "fun_unique_units": 3, "fun_windows": 60, "fun_perturbations": 3000},
        {"logical_shard": 3, "fun_unique_units": 2, "fun_windows": 20, "fun_perturbations": 1000},
    ]
    assert sum(gpu_window_loads(build_assignment(synthetic, "deterministic_lpt_by_fun_windows"))) == 260
    print("audit_snapshot_npr_perturbation_shards self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--a09-root", type=Path, default=Path("output/snapshot_npr/run-x-a09"))
    parser.add_argument("--output-root", type=Path, default=Path("output/snapshot_npr/run-x-a10"))
    parser.add_argument("--data-shards", type=int, default=96)
    parser.add_argument("--prep-workers", type=int, default=2)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--perturbations-per-window", type=int, default=50)
    parser.add_argument("--random-seed", type=int, default=20260723)
    parser.add_argument("--expected-a09-version", default=A09_EXPECTED_VERSION)
    parser.add_argument("--expected-input-sha256", default="1acb3726f5c62e6154672f1aff592973c65a13e58dbfd37f8058560d1a474e6c")
    parser.add_argument("--expected-unique-units", type=int, default=419220)
    parser.add_argument("--expected-windows", type=int, default=1113866)
    parser.add_argument("--expected-perturbations", type=int, default=55693300)
    parser.add_argument("--sample-records-per-shard", type=int, default=2)
    parser.add_argument("--run-self-test", type=int, choices=(0, 1), default=1)
    parser.add_argument("--self-test-only", action="store_true")
    args = parser.parse_args()

    if args.run_self_test:
        run_self_test()
    if args.self_test_only:
        return 0

    args.project_root = args.project_root.resolve()
    if not args.a09_root.is_absolute():
        args.a09_root = args.project_root / args.a09_root
    if not args.output_root.is_absolute():
        args.output_root = args.project_root / args.output_root
    args.a09_root = args.a09_root.resolve()
    args.output_root = args.output_root.resolve()

    plan_dir = args.a09_root / "plan"
    shard_root = args.a09_root / "shards"
    plan_summary_path = plan_dir / "summary.json"
    unit_plan_path = plan_dir / "unique_primary_units.csv"
    shard_plan_path = plan_dir / "logical_shard_plan.csv"
    for path in (plan_summary_path, unit_plan_path, shard_plan_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing A09 plan artifact: {path}")
    if not shard_root.is_dir():
        raise FileNotFoundError(f"Missing A09 shard directory: {shard_root}")

    started = time.perf_counter()
    plan_summary = load_json(plan_summary_path)
    logical_plan = read_csv_by_key(shard_plan_path, "logical_shard")
    checks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    data_paths = sorted(shard_root.glob(f"shard-*-of-{args.data_shards:03d}.jsonl.gz"))
    summary_paths = sorted(shard_root.glob(f"shard-*-of-{args.data_shards:03d}.summary.json"))
    data_ids = [parse_shard_id(path) for path in data_paths]
    summary_ids = [parse_shard_id(path) for path in summary_paths]
    expected_ids = list(range(args.data_shards))

    add_check(checks, "data_shard_file_count", len(data_paths) == args.data_shards, len(data_paths), args.data_shards)
    add_check(checks, "summary_file_count", len(summary_paths) == args.data_shards, len(summary_paths), args.data_shards)
    add_check(checks, "data_shard_id_coverage", data_ids == expected_ids, f"{len(data_ids)} IDs", f"0..{args.data_shards - 1}")
    add_check(checks, "summary_shard_id_coverage", summary_ids == expected_ids, f"{len(summary_ids)} IDs", f"0..{args.data_shards - 1}")
    add_check(checks, "logical_plan_shard_count", sorted(logical_plan) == expected_ids, len(logical_plan), args.data_shards)
    add_check(checks, "plan_input_manifest_sha256", str(plan_summary.get("input_manifest_sha256")) == args.expected_input_sha256, plan_summary.get("input_manifest_sha256"), args.expected_input_sha256)
    add_check(checks, "plan_unique_units", int(plan_summary.get("unique_primary_units", -1)) == args.expected_unique_units, plan_summary.get("unique_primary_units"), args.expected_unique_units)
    add_check(checks, "plan_windows", int(plan_summary.get("expected_unique_windows", -1)) == args.expected_windows, plan_summary.get("expected_unique_windows"), args.expected_windows)
    add_check(checks, "plan_perturbations", int(plan_summary.get("expected_perturbations", -1)) == args.expected_perturbations, plan_summary.get("expected_perturbations"), args.expected_perturbations)

    if data_ids != expected_ids or summary_ids != expected_ids or sorted(logical_plan) != expected_ids:
        args.output_root.mkdir(parents=True, exist_ok=True)
        atomic_csv(checks, args.output_root / "checks.csv", CHECK_COLUMNS)
        atomic_json({"status": "FAIL", "script_version": SCRIPT_VERSION, "failed_checks": sum(not bool(row["passed"]) for row in checks), "completed_utc": utc_now()}, args.output_root / "summary.json")
        print("A10 hard stop: merged shard coverage is incomplete.")
        return 1

    summary_by_id = {parse_shard_id(path): path for path in summary_paths}
    shard_rows: list[dict[str, Any]] = []
    sampled_records = 0

    for position, data_path in enumerate(data_paths, start=1):
        shard_id = parse_shard_id(data_path)
        summary = load_json(summary_by_id[shard_id])
        planned = logical_plan[shard_id]
        shard_errors: list[str] = []

        if summary.get("status") != "PASS":
            shard_errors.append("summary status is not PASS")
        if str(summary.get("script_version")) != args.expected_a09_version:
            shard_errors.append(f"script version={summary.get('script_version')}")
        if int(summary.get("logical_shard", -1)) != shard_id:
            shard_errors.append("logical_shard mismatch")
        if int(summary.get("data_shards", -1)) != args.data_shards:
            shard_errors.append("data_shards mismatch")
        if int(summary.get("prep_worker_index", -1)) != shard_id % args.prep_workers:
            shard_errors.append("prep_worker_index mismatch")
        if str(summary.get("input_manifest_sha256")) != str(plan_summary.get("input_manifest_sha256")):
            shard_errors.append("input manifest SHA mismatch")
        if str(summary.get("config_fingerprint")) != str(plan_summary.get("config_fingerprint")):
            shard_errors.append("config fingerprint mismatch")
        if int(summary.get("unique_units", -1)) != int(planned["unique_units"]):
            shard_errors.append("unique_units mismatch vs logical plan")
        if int(summary.get("windows", -1)) != int(planned["expected_windows"]):
            shard_errors.append("windows mismatch vs logical plan")
        if int(summary.get("perturbations", -1)) != int(planned["expected_windows"]) * args.perturbations_per_window:
            shard_errors.append("perturbations mismatch vs logical plan")
        if int(summary.get("gzip_bytes", -1)) != data_path.stat().st_size:
            shard_errors.append("gzip byte size mismatch")

        observed_gzip_sha = sha256_file(data_path)
        if observed_gzip_sha != str(summary.get("gzip_sha256")):
            shard_errors.append("gzip SHA-256 mismatch")

        checked, sample_errors = audit_sample_records(
            data_path,
            shard_id,
            args.sample_records_per_shard,
            args.data_shards,
            args.random_seed,
            args.perturbations_per_window,
            str(plan_summary.get("config_fingerprint")),
        )
        sampled_records += checked
        shard_errors.extend(sample_errors)

        for message in shard_errors:
            failures.append({"logical_shard": shard_id, "message": message})

        shard_rows.append(
            {
                "logical_shard": shard_id,
                "prep_worker_index": int(summary.get("prep_worker_index", -1)),
                "unique_units": int(summary.get("unique_units", -1)),
                "windows": int(summary.get("windows", -1)),
                "perturbations": int(summary.get("perturbations", -1)),
                "gzip_bytes": data_path.stat().st_size,
                "gzip_sha256": observed_gzip_sha,
                "sample_records_checked": checked,
                "errors": len(shard_errors),
                "status": "PASS" if not shard_errors else "FAIL",
                "fun_unique_units": 0,
                "fun_windows": 0,
                "fun_perturbations": 0,
                "c_fun_unique_units": 0,
                "c_fun_windows": 0,
                "c_fun_perturbations": 0,
                "block_unique_units": 0,
                "block_windows": 0,
                "block_perturbations": 0,
            }
        )
        print(
            f"A10 shard integrity: {position}/{args.data_shards} "
            f"logical_shard={shard_id:03d} windows={summary.get('windows')} "
            f"errors={len(shard_errors)}",
            flush=True,
        )

    # Derive exact category workloads from the full globally deduplicated A09 unit plan.
    group_totals = defaultdict(int)
    plan_units = 0
    plan_windows = 0
    per_shard_group = {shard_id: defaultdict(int) for shard_id in expected_ids}
    with unit_plan_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"code_unit_sha256", "expected_windows", "unit_groups", "logical_shard"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"A09 unique unit plan missing columns: {sorted(missing)}")
        for row in reader:
            plan_units += 1
            shard_id = int(row["logical_shard"])
            expected_windows = int(row["expected_windows"])
            plan_windows += expected_windows
            groups = [value for value in str(row["unit_groups"]).split(",") if value]
            if stable_shard(str(row["code_unit_sha256"]), args.data_shards) != shard_id:
                failures.append({"logical_shard": shard_id, "message": "unit plan stable-shard mismatch"})
            for group in groups:
                if group not in GROUPS:
                    failures.append({"logical_shard": shard_id, "message": f"unknown group {group!r}"})
                    continue
                group_totals[f"{group}_units"] += 1
                group_totals[f"{group}_windows"] += expected_windows
                group_totals[f"{group}_perturbations"] += expected_windows * args.perturbations_per_window
                per_shard_group[shard_id][f"{group}_units"] += 1
                per_shard_group[shard_id][f"{group}_windows"] += expected_windows
                per_shard_group[shard_id][f"{group}_perturbations"] += expected_windows * args.perturbations_per_window

    shard_by_id = {int(row["logical_shard"]): row for row in shard_rows}
    for shard_id in expected_ids:
        target = shard_by_id[shard_id]
        counts = per_shard_group[shard_id]
        target["fun_unique_units"] = counts["FUN_units"]
        target["fun_windows"] = counts["FUN_windows"]
        target["fun_perturbations"] = counts["FUN_perturbations"]
        target["c_fun_unique_units"] = counts["C_FUN_units"]
        target["c_fun_windows"] = counts["C_FUN_windows"]
        target["c_fun_perturbations"] = counts["C_FUN_perturbations"]
        target["block_unique_units"] = counts["BLOCK_units"]
        target["block_windows"] = counts["BLOCK_windows"]
        target["block_perturbations"] = counts["BLOCK_perturbations"]

    total_summary_units = sum(int(row["unique_units"]) for row in shard_rows)
    total_summary_windows = sum(int(row["windows"]) for row in shard_rows)
    total_summary_perturbations = sum(int(row["perturbations"]) for row in shard_rows)
    total_gzip_bytes = sum(int(row["gzip_bytes"]) for row in shard_rows)

    add_check(checks, "merged_summary_unique_units", total_summary_units == args.expected_unique_units, total_summary_units, args.expected_unique_units)
    add_check(checks, "merged_summary_windows", total_summary_windows == args.expected_windows, total_summary_windows, args.expected_windows)
    add_check(checks, "merged_summary_perturbations", total_summary_perturbations == args.expected_perturbations, total_summary_perturbations, args.expected_perturbations)
    add_check(checks, "unit_plan_row_count", plan_units == args.expected_unique_units, plan_units, args.expected_unique_units)
    add_check(checks, "unit_plan_window_total", plan_windows == args.expected_windows, plan_windows, args.expected_windows)
    add_check(checks, "all_shard_integrity_checks", not failures, len(failures), 0)

    plan_group_counts = plan_summary.get("group_membership_unique_units", {})
    for group in GROUPS:
        observed = group_totals[f"{group}_units"]
        expected = int(plan_group_counts.get(group, -1))
        add_check(checks, f"{group.lower()}_unique_unit_membership", observed == expected, observed, expected)

    mod3 = build_assignment(shard_rows, "logical_shard_mod_3")
    lpt = build_assignment(shard_rows, "deterministic_lpt_by_fun_windows")
    mod3_loads = gpu_window_loads(mod3)
    lpt_loads = gpu_window_loads(lpt)
    mod3_imbalance = imbalance_fraction(mod3_loads)
    lpt_imbalance = imbalance_fraction(lpt_loads)
    recommended = "logical_shard_mod_3" if mod3_imbalance <= 0.03 else "deterministic_lpt_by_fun_windows"

    group_rows: list[dict[str, Any]] = []
    for group in GROUPS:
        windows = group_totals[f"{group}_windows"]
        group_rows.append(
            {
                "unit_group": group,
                "unique_unit_memberships": group_totals[f"{group}_units"],
                "windows": windows,
                "perturbations": group_totals[f"{group}_perturbations"],
                "rank_evaluations_original_plus_perturbed": windows * (1 + args.perturbations_per_window),
            }
        )

    args.output_root.mkdir(parents=True, exist_ok=True)
    shard_fields = [
        "logical_shard", "prep_worker_index", "unique_units", "windows", "perturbations",
        "gzip_bytes", "gzip_sha256", "sample_records_checked", "errors", "status",
        "fun_unique_units", "fun_windows", "fun_perturbations",
        "c_fun_unique_units", "c_fun_windows", "c_fun_perturbations",
        "block_unique_units", "block_windows", "block_perturbations",
    ]
    atomic_csv(shard_rows, args.output_root / "shard_audit.csv", shard_fields)
    atomic_csv(group_rows, args.output_root / "group_workload_summary.csv", [
        "unit_group", "unique_unit_memberships", "windows", "perturbations",
        "rank_evaluations_original_plus_perturbed",
    ])
    assignment_fields = ["logical_shard", "gpu_index", "fun_unique_units", "fun_windows", "fun_perturbations", "assignment_policy"]
    atomic_csv(mod3, args.output_root / "fun_gpu_mod3_plan.csv", assignment_fields)
    atomic_csv(lpt, args.output_root / "fun_gpu_lpt_plan.csv", assignment_fields)
    atomic_csv(checks, args.output_root / "checks.csv", CHECK_COLUMNS)
    atomic_csv(failures, args.output_root / "failures.csv", ["logical_shard", "message"])

    elapsed = time.perf_counter() - started
    failed_checks = [row for row in checks if not bool(row["passed"])]
    status = "PASS" if not failed_checks and not failures else "FAIL"
    summary = {
        "status": status,
        "script_version": SCRIPT_VERSION,
        "a09_root": str(args.a09_root),
        "a09_plan_config_fingerprint": plan_summary.get("config_fingerprint"),
        "a09_input_manifest_sha256": plan_summary.get("input_manifest_sha256"),
        "logical_shards": len(shard_rows),
        "unique_units": total_summary_units,
        "windows": total_summary_windows,
        "perturbations": total_summary_perturbations,
        "gzip_bytes": total_gzip_bytes,
        "group_workload": {
            group: {
                "unique_unit_memberships": group_totals[f"{group}_units"],
                "windows": group_totals[f"{group}_windows"],
                "perturbations": group_totals[f"{group}_perturbations"],
            }
            for group in GROUPS
        },
        "fun_gpu_mod3_window_loads": mod3_loads,
        "fun_gpu_lpt_window_loads": lpt_loads,
        "fun_gpu_mod3_imbalance_fraction": mod3_imbalance,
        "fun_gpu_lpt_imbalance_fraction": lpt_imbalance,
        "recommended_fun_gpu_assignment": recommended,
        "sample_records_checked": sampled_records,
        "failed_checks": len(failed_checks),
        "failures": len(failures),
        "elapsed_seconds": elapsed,
        "host": platform.node(),
        "python_version": platform.python_version(),
        "completed_utc": utc_now(),
    }
    atomic_json(summary, args.output_root / "summary.json")

    print("=" * 80)
    print("run-x-a10 merged A09 perturbation audit")
    print(f"Status:                           {status}")
    print(f"Logical shards:                   {len(shard_rows)}/{args.data_shards}")
    print(f"Unique units:                     {total_summary_units}/{args.expected_unique_units}")
    print(f"Windows:                          {total_summary_windows}/{args.expected_windows}")
    print(f"Perturbations:                    {total_summary_perturbations}/{args.expected_perturbations}")
    print(f"FUN unique-unit memberships:      {group_totals['FUN_units']}")
    print(f"FUN windows:                      {group_totals['FUN_windows']}")
    print(f"FUN perturbations:                {group_totals['FUN_perturbations']}")
    print(f"C_FUN windows:                    {group_totals['C_FUN_windows']}")
    print(f"BLOCK windows:                    {group_totals['BLOCK_windows']}")
    print(f"FUN mod3 GPU window loads:        {mod3_loads}")
    print(f"FUN LPT GPU window loads:         {lpt_loads}")
    print(f"Recommended FUN assignment:       {recommended}")
    print(f"Sample records checked:           {sampled_records}")
    print(f"Content failures:                 {len(failures)}")
    print(f"Failed checks:                    {len(failed_checks)}")
    print(f"Elapsed seconds:                  {elapsed:.3f}")
    print(f"Output root:                      {args.output_root}")
    print("=" * 80)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
