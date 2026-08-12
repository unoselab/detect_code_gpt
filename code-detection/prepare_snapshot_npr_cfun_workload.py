#!/usr/bin/env python3
"""Prepare the C_FUN NPR scoring workload and audit A11 FUN score reuse.

A13 is a CPU-only planning/audit stage for class-method NPR analysis on R158.
It does not load StarCoder2 and does not score any new NPR windows.

Scientific scope
----------------
- C_FUN means A09 unique primary code units whose ``unit_groups`` contains
  ``C_FUN``. A13 additionally requires ``method_body`` to appear in
  ``code_unit_types`` for every C_FUN membership.
- A09 remains the frozen source of original windows and ordered perturbations.
- A11 FUN results are reused by content SHA when the same unique source content
  also has FUN membership. This is scientifically exact because the code-unit
  SHA, prepared A09 windows/perturbations, frozen A02 scorer, model revision,
  and scoring configuration are identical.
- A14 only needs to score C_FUN units that do not have FUN membership and were
  therefore never part of the A11 workload.
- Whole logical shards are assigned to three R158 RTX A6000 workers with
  deterministic LPT using only the *new* C_FUN windows. Units never cross
  logical shards because A09 assigns each unique SHA to one stable shard.

Expected A11 exclusions are reused as exclusions rather than rescored. A13
requires every A11 invalid window to appear in A11's explicit expected-
exclusion CSV and rejects missing, unexpected-invalid, or scoring-error rows.

Outputs
-------
- python_cfun_workload_units.csv
    One row per unique C_FUN membership with A11 reuse/A14-new classification.
- python_cfun_reuse_from_a11.csv
    C_FUN SHA memberships already attempted by A11 because they also belong to
    FUN. Finite/partial/excluded A11 reuse status is preserved.
- python_cfun_new_scoring_units.csv
    C_FUN-only unique SHAs that A14 must score.
- cfun_new_gpu_lpt_plan.csv
    96-row whole-logical-shard 3-GPU deterministic LPT assignment for A14.
- cfun_new_gpu_summary.csv
    GPU-level new-unit/window/perturbation loads.
- checks.csv, summary.json, metadata.json
    Provenance and hard QC gate for A14.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import sqlite3
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

SCRIPT_VERSION = "run-x-a13-v1"
CATEGORY = "C_FUN"
CODE_UNIT_TYPE = "method_body"
A14_ASSIGNMENT_POLICY = "deterministic_lpt_by_new_cfun_windows"

EXPECTED_A09_CONFIG_FINGERPRINT = "3f78c8c43aaa014cd0f5e1a5d1c2df7d4269deb55c4c999e4483d08a324dd9bb"
EXPECTED_A05_MANIFEST_SHA256 = "1acb3726f5c62e6154672f1aff592973c65a13e58dbfd37f8058560d1a474e6c"
EXPECTED_A02_SHA256 = "57e0781a406d992fb045335a79b1cb97e5c0557de9582603401f6d402ef528a0"
EXPECTED_A02_CONFIG_FINGERPRINT = "78655715edc8699710a27f593cac5a8360067e803eac8c50a0765084edfa5fb2"
EXPECTED_MODEL_REVISION = "bb9afde76d7945da5745592525db122d4d729eb1"
EXPECTED_A11_SCRIPT_VERSION = "run-x-a11-v3"
EXPECTED_A11_FUN_UNITS = 105635
EXPECTED_A11_FUN_WINDOWS = 307600
EXPECTED_A11_EXCLUSION_WINDOWS = 4
EXPECTED_A11_EXCLUDED_UNITS = 4
EXPECTED_CFUN_WINDOWS = 567557
PERTURBATIONS_PER_WINDOW = 50
GPU_COUNT = 3
DATA_SHARDS = 96

CHECK_COLUMNS = ["check_name", "passed", "observed", "expected", "note"]
UNIT_COLUMNS = [
    "code_unit_sha256", "logical_shard", "code_unit_relative_path",
    "code_unit_types", "unit_groups", "space_by_token_count", "expected_windows",
    "cfun_membership", "fun_membership", "a11_reuse_class", "a11_gpu_index",
    "a11_database_windows", "a11_valid_windows", "a11_expected_exclusion_windows",
    "a11_unique_score_present", "a14_scoring_required", "a14_gpu_index",
]
REUSE_COLUMNS = UNIT_COLUMNS
NEW_COLUMNS = UNIT_COLUMNS
PLAN_COLUMNS = [
    "logical_shard", "gpu_index", "cfun_new_unique_units", "cfun_new_windows",
    "cfun_new_perturbations", "assignment_policy",
]
GPU_COLUMNS = [
    "gpu_index", "cfun_new_unique_units", "cfun_new_windows",
    "cfun_new_perturbations", "assigned_logical_shards", "assignment_policy",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
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


def atomic_csv(rows: Iterable[dict[str, Any]], path: Path, fieldnames: Sequence[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with tmp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})
            count += 1
    os.replace(tmp, path)
    return count


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    note: str = "",
) -> None:
    checks.append({
        "check_name": name,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
        "note": note,
    })


def split_memberships(value: Any) -> set[str]:
    return {item.strip() for item in str(value or "").split(",") if item.strip()}


def read_unique_plan(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "code_unit_sha256", "code_unit_relative_path", "space_by_token_count",
            "expected_windows", "code_unit_types", "unit_groups", "logical_shard",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"A09 unique-unit plan missing columns: {sorted(missing)}")
        seen: set[str] = set()
        for raw in reader:
            sha = str(raw["code_unit_sha256"])
            if sha in seen:
                raise ValueError(f"Duplicate unique-unit SHA in A09 plan: {sha}")
            seen.add(sha)
            rows.append({
                "code_unit_sha256": sha,
                "code_unit_relative_path": str(raw["code_unit_relative_path"]),
                "space_by_token_count": int(raw["space_by_token_count"]),
                "expected_windows": int(raw["expected_windows"]),
                "code_unit_types": str(raw["code_unit_types"]),
                "unit_groups": str(raw["unit_groups"]),
                "logical_shard": int(raw["logical_shard"]),
            })
    return rows


def read_unique_score_shas(path: Path) -> set[str]:
    result: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"code_unit_sha256", "status"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"A11 unique-score CSV missing columns: {sorted(missing)}")
        for row in reader:
            sha = str(row["code_unit_sha256"])
            if sha in result:
                raise ValueError(f"Duplicate A11 unique-score SHA within file: {sha}")
            status = str(row["status"])
            if status not in {"scored", "partial"}:
                raise ValueError(f"Unexpected A11 unique-score status={status!r} for {sha}")
            result.add(sha)
    return result


def read_exclusion_keys(path: Path) -> set[tuple[str, int]]:
    result: set[tuple[str, int]] = set()
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"code_unit_sha256", "window_index", "exclusion_class"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"A11 exclusion CSV missing columns: {sorted(missing)}")
        for row in reader:
            key = (str(row["code_unit_sha256"]), int(row["window_index"]))
            if key in result:
                raise ValueError(f"Duplicate A11 expected-exclusion key: {key}")
            if not str(row["exclusion_class"]).strip():
                raise ValueError(f"Empty A11 exclusion class for {key}")
            result.add(key)
    return result


def read_a11_database(path: Path, gpu_index: int) -> dict[str, dict[str, Any]]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        required_columns = {
            "gpu_index", "code_unit_sha256", "window_index", "window_npr_valid",
            "scoring_error_type", "a09_config_fingerprint", "a02_config_fingerprint",
        }
        info = connection.execute("PRAGMA table_info(window_scores)").fetchall()
        columns = {str(row[1]) for row in info}
        missing = required_columns - columns
        if missing:
            raise ValueError(f"A11 database missing columns {sorted(missing)}: {path}")
        result: dict[str, dict[str, Any]] = {}
        query = """
            SELECT code_unit_sha256,
                   COUNT(*) AS windows,
                   SUM(CASE WHEN window_npr_valid = 1 THEN 1 ELSE 0 END) AS valid_windows,
                   SUM(CASE WHEN window_npr_valid = 0 THEN 1 ELSE 0 END) AS invalid_windows,
                   SUM(CASE WHEN scoring_error_type IS NOT NULL THEN 1 ELSE 0 END) AS scoring_errors,
                   MIN(gpu_index), MAX(gpu_index),
                   COUNT(DISTINCT a09_config_fingerprint), MIN(a09_config_fingerprint),
                   COUNT(DISTINCT a02_config_fingerprint), MIN(a02_config_fingerprint)
              FROM window_scores
             GROUP BY code_unit_sha256
        """
        for row in connection.execute(query):
            sha = str(row[0])
            if int(row[5]) != gpu_index or int(row[6]) != gpu_index:
                raise ValueError(f"A11 DB GPU provenance mismatch for {sha}: {path}")
            if int(row[7]) != 1 or str(row[8]) != EXPECTED_A09_CONFIG_FINGERPRINT:
                raise ValueError(f"A11 DB A09 fingerprint mismatch for {sha}: {path}")
            if int(row[9]) != 1 or str(row[10]) != EXPECTED_A02_CONFIG_FINGERPRINT:
                raise ValueError(f"A11 DB A02 fingerprint mismatch for {sha}: {path}")
            result[sha] = {
                "gpu_index": gpu_index,
                "windows": int(row[1] or 0),
                "valid_windows": int(row[2] or 0),
                "invalid_windows": int(row[3] or 0),
                "scoring_errors": int(row[4] or 0),
            }
        return result
    finally:
        connection.close()


def build_lpt_plan(per_shard: dict[int, dict[str, int]]) -> list[dict[str, Any]]:
    loads = [0] * GPU_COUNT
    assignment: dict[int, int] = {}
    for shard_id in sorted(range(DATA_SHARDS), key=lambda sid: (-per_shard[sid]["windows"], sid)):
        gpu = min(range(GPU_COUNT), key=lambda index: (loads[index], index))
        assignment[shard_id] = gpu
        loads[gpu] += per_shard[shard_id]["windows"]
    rows: list[dict[str, Any]] = []
    for shard_id in range(DATA_SHARDS):
        counts = per_shard[shard_id]
        rows.append({
            "logical_shard": shard_id,
            "gpu_index": assignment[shard_id],
            "cfun_new_unique_units": counts["units"],
            "cfun_new_windows": counts["windows"],
            "cfun_new_perturbations": counts["windows"] * PERTURBATIONS_PER_WINDOW,
            "assignment_policy": A14_ASSIGNMENT_POLICY,
        })
    return rows


def run_self_test() -> None:
    assert split_memberships("FUN,C_FUN") == {"FUN", "C_FUN"}
    synthetic = {sid: {"units": 0, "windows": 0} for sid in range(DATA_SHARDS)}
    synthetic[0] = {"units": 2, "windows": 100}
    synthetic[1] = {"units": 1, "windows": 70}
    synthetic[2] = {"units": 1, "windows": 30}
    plan = build_lpt_plan(synthetic)
    assert len(plan) == DATA_SHARDS
    assert sum(int(row["cfun_new_windows"]) for row in plan) == 200
    loads = [0, 0, 0]
    for row in plan:
        loads[int(row["gpu_index"])] += int(row["cfun_new_windows"])
    assert sum(loads) == 200

    with tempfile.TemporaryDirectory(prefix="a13-cfun-self-test-") as tmp_text:
        db_path = Path(tmp_text) / "window_scores.sqlite3"
        con = sqlite3.connect(db_path)
        con.execute("""
            CREATE TABLE window_scores (
                gpu_index INTEGER, code_unit_sha256 TEXT, window_index INTEGER,
                window_npr_valid INTEGER, scoring_error_type TEXT,
                a09_config_fingerprint TEXT, a02_config_fingerprint TEXT
            )
        """)
        con.execute(
            "INSERT INTO window_scores VALUES (0, ?, 0, 1, NULL, ?, ?)",
            ("a" * 64, EXPECTED_A09_CONFIG_FINGERPRINT, EXPECTED_A02_CONFIG_FINGERPRINT),
        )
        con.commit()
        con.close()
        observed = read_a11_database(db_path, 0)
        assert observed["a" * 64]["valid_windows"] == 1
    print("prepare_snapshot_npr_cfun_workload self-test: PASS")


def resolve(project_root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare A13 C_FUN score-reuse audit and A14 3-GPU workload.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--a09-root", type=Path, default=Path("output/snapshot_npr/run-x-a09"))
    parser.add_argument("--a10-root", type=Path, default=Path("output/snapshot_npr/run-x-a10"))
    parser.add_argument("--a11-root", type=Path, default=Path("output/snapshot_npr/run-x-a11"))
    parser.add_argument("--output-root", type=Path, default=Path("output/snapshot_npr/run-x-a13"))
    parser.add_argument("--run-self-test", type=int, choices=(0, 1), default=1)
    parser.add_argument("--self-test-only", action="store_true")
    args = parser.parse_args()

    if args.run_self_test:
        run_self_test()
    if args.self_test_only:
        return 0

    project_root = args.project_root.resolve()
    a09_root = resolve(project_root, args.a09_root)
    a10_root = resolve(project_root, args.a10_root)
    a11_root = resolve(project_root, args.a11_root)
    output_root = resolve(project_root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    checks: list[dict[str, Any]] = []

    a09_summary_path = a09_root / "plan" / "summary.json"
    a09_units_path = a09_root / "plan" / "unique_primary_units.csv"
    a10_summary_path = a10_root / "summary.json"
    for path in (a09_summary_path, a09_units_path, a10_summary_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing required input: {path}")

    a09_summary = load_json(a09_summary_path)
    a10_summary = load_json(a10_summary_path)
    add_check(checks, "a09_status", str(a09_summary.get("status")) == "PASS", a09_summary.get("status"), "PASS")
    add_check(checks, "a10_status", str(a10_summary.get("status")) == "PASS", a10_summary.get("status"), "PASS")
    add_check(checks, "a09_config_fingerprint", str(a09_summary.get("config_fingerprint")) == EXPECTED_A09_CONFIG_FINGERPRINT, a09_summary.get("config_fingerprint"), EXPECTED_A09_CONFIG_FINGERPRINT)
    add_check(checks, "a09_input_manifest_sha256", str(a09_summary.get("input_manifest_sha256")) == EXPECTED_A05_MANIFEST_SHA256, a09_summary.get("input_manifest_sha256"), EXPECTED_A05_MANIFEST_SHA256)

    cfun_a10 = dict(a10_summary.get("group_workload", {}).get(CATEGORY, {}))
    add_check(checks, "a10_cfun_windows", int(cfun_a10.get("windows", -1)) == EXPECTED_CFUN_WINDOWS, cfun_a10.get("windows"), EXPECTED_CFUN_WINDOWS)
    add_check(checks, "a10_cfun_perturbations", int(cfun_a10.get("perturbations", -1)) == EXPECTED_CFUN_WINDOWS * PERTURBATIONS_PER_WINDOW, cfun_a10.get("perturbations"), EXPECTED_CFUN_WINDOWS * PERTURBATIONS_PER_WINDOW)

    plan_rows = read_unique_plan(a09_units_path)
    cfun_rows = [row for row in plan_rows if CATEGORY in split_memberships(row["unit_groups"])]
    fun_rows = [row for row in plan_rows if "FUN" in split_memberships(row["unit_groups"])]
    fun_shas = {str(row["code_unit_sha256"]) for row in fun_rows}
    cfun_shas = {str(row["code_unit_sha256"]) for row in cfun_rows}
    overlap_shas = cfun_shas & fun_shas

    cfun_windows = sum(int(row["expected_windows"]) for row in cfun_rows)
    cfun_units_expected = int(cfun_a10.get("unique_unit_memberships", -1))
    add_check(checks, "cfun_unique_memberships_reconcile_a10", len(cfun_rows) == cfun_units_expected, len(cfun_rows), cfun_units_expected)
    add_check(checks, "cfun_windows_reconcile_a10", cfun_windows == EXPECTED_CFUN_WINDOWS, cfun_windows, EXPECTED_CFUN_WINDOWS)
    bad_cfun_types = [row["code_unit_sha256"] for row in cfun_rows if CODE_UNIT_TYPE not in split_memberships(row["code_unit_types"])]
    add_check(checks, "cfun_memberships_include_method_body", not bad_cfun_types, len(bad_cfun_types), 0)
    add_check(checks, "a09_unique_plan_sha_uniqueness", len({row["code_unit_sha256"] for row in plan_rows}) == len(plan_rows), len({row["code_unit_sha256"] for row in plan_rows}), len(plan_rows))

    # Load and strictly validate all finalized A11 worker artifacts.
    a11_db_by_sha: dict[str, dict[str, Any]] = {}
    a11_unique_score_shas: set[str] = set()
    a11_exclusion_keys: set[tuple[str, int]] = set()
    a11_summary_totals = defaultdict(int)
    a11_input_hashes: dict[str, str] = {}
    for gpu_index in range(GPU_COUNT):
        worker = a11_root / "results" / f"gpu-{gpu_index}"
        summary_path = worker / "summary.json"
        db_path = worker / "window_scores.sqlite3"
        unique_path = worker / "python_fun_unique_code_unit_npr_scores.csv"
        exclusion_path = worker / "python_fun_npr_exclusions.csv"
        for path in (summary_path, db_path, unique_path, exclusion_path):
            if not path.is_file():
                raise FileNotFoundError(f"Missing finalized A11 worker input: {path}")
        summary = load_json(summary_path)
        add_check(checks, f"a11_gpu{gpu_index}_status", str(summary.get("status")) in {"PASS", "PASS_WITH_EXCLUSIONS"}, summary.get("status"), "PASS or PASS_WITH_EXCLUSIONS")
        add_check(checks, f"a11_gpu{gpu_index}_script_version", str(summary.get("script_version")) == EXPECTED_A11_SCRIPT_VERSION, summary.get("script_version"), EXPECTED_A11_SCRIPT_VERSION)
        add_check(checks, f"a11_gpu{gpu_index}_a09_fingerprint", str(summary.get("a09_config_fingerprint")) == EXPECTED_A09_CONFIG_FINGERPRINT, summary.get("a09_config_fingerprint"), EXPECTED_A09_CONFIG_FINGERPRINT)
        add_check(checks, f"a11_gpu{gpu_index}_a02_sha", str(summary.get("a02_script_sha256")) == EXPECTED_A02_SHA256, summary.get("a02_script_sha256"), EXPECTED_A02_SHA256)
        add_check(checks, f"a11_gpu{gpu_index}_a02_fingerprint", str(summary.get("a02_config_fingerprint")) == EXPECTED_A02_CONFIG_FINGERPRINT, summary.get("a02_config_fingerprint"), EXPECTED_A02_CONFIG_FINGERPRINT)
        add_check(checks, f"a11_gpu{gpu_index}_model_revision", str(summary.get("model_revision")) == EXPECTED_MODEL_REVISION, summary.get("model_revision"), EXPECTED_MODEL_REVISION)
        add_check(checks, f"a11_gpu{gpu_index}_unexpected_invalid_zero", int(summary.get("unexpected_invalid_windows", -1)) == 0, summary.get("unexpected_invalid_windows"), 0)
        add_check(checks, f"a11_gpu{gpu_index}_scoring_errors_zero", int(summary.get("scoring_errors", -1)) == 0, summary.get("scoring_errors"), 0)
        add_check(checks, f"a11_gpu{gpu_index}_partial_units_zero", int(summary.get("partial_unique_units", -1)) == 0, summary.get("partial_unique_units"), 0, "Frozen A11 production had no partial FUN units.")
        for key in (
            "full_expected_fun_unique_units",
            "full_expected_fun_windows",
            "database_windows",
            "expected_exclusion_windows",
            "expected_exclusion_unique_units",
            "excluded_unique_units",
            "exported_unique_units",
        ):
            a11_summary_totals[key] += int(summary.get(key, 0))
        a11_input_hashes[f"gpu{gpu_index}_summary_sha256"] = sha256_file(summary_path)
        a11_input_hashes[f"gpu{gpu_index}_database_sha256"] = sha256_file(db_path)
        a11_input_hashes[f"gpu{gpu_index}_unique_scores_sha256"] = sha256_file(unique_path)
        a11_input_hashes[f"gpu{gpu_index}_exclusions_sha256"] = sha256_file(exclusion_path)

        db_rows = read_a11_database(db_path, gpu_index)
        duplicate_db = set(a11_db_by_sha) & set(db_rows)
        if duplicate_db:
            raise RuntimeError(f"A11 SHA appears on multiple GPU databases: {next(iter(duplicate_db))}")
        a11_db_by_sha.update(db_rows)

        unique_shas = read_unique_score_shas(unique_path)
        duplicate_unique = a11_unique_score_shas & unique_shas
        if duplicate_unique:
            raise RuntimeError(f"A11 unique score appears on multiple GPUs: {next(iter(duplicate_unique))}")
        a11_unique_score_shas.update(unique_shas)

        exclusion_keys = read_exclusion_keys(exclusion_path)
        duplicate_exclusions = a11_exclusion_keys & exclusion_keys
        if duplicate_exclusions:
            raise RuntimeError(f"A11 exclusion key appears on multiple GPUs: {next(iter(duplicate_exclusions))}")
        a11_exclusion_keys.update(exclusion_keys)

    add_check(checks, "a11_fun_units_total", a11_summary_totals["full_expected_fun_unique_units"] == EXPECTED_A11_FUN_UNITS, a11_summary_totals["full_expected_fun_unique_units"], EXPECTED_A11_FUN_UNITS)
    add_check(checks, "a11_fun_windows_total", a11_summary_totals["full_expected_fun_windows"] == EXPECTED_A11_FUN_WINDOWS, a11_summary_totals["full_expected_fun_windows"], EXPECTED_A11_FUN_WINDOWS)
    add_check(checks, "a11_database_windows_total", a11_summary_totals["database_windows"] == EXPECTED_A11_FUN_WINDOWS, a11_summary_totals["database_windows"], EXPECTED_A11_FUN_WINDOWS)
    add_check(checks, "a11_expected_exclusion_windows_total", a11_summary_totals["expected_exclusion_windows"] == EXPECTED_A11_EXCLUSION_WINDOWS, a11_summary_totals["expected_exclusion_windows"], EXPECTED_A11_EXCLUSION_WINDOWS)
    add_check(checks, "a11_exclusion_csv_windows_total", len(a11_exclusion_keys) == EXPECTED_A11_EXCLUSION_WINDOWS, len(a11_exclusion_keys), EXPECTED_A11_EXCLUSION_WINDOWS)
    add_check(checks, "a11_expected_exclusion_units_total", a11_summary_totals["expected_exclusion_unique_units"] == EXPECTED_A11_EXCLUDED_UNITS, a11_summary_totals["expected_exclusion_unique_units"], EXPECTED_A11_EXCLUDED_UNITS)
    add_check(checks, "a11_excluded_units_total", a11_summary_totals["excluded_unique_units"] == EXPECTED_A11_EXCLUDED_UNITS, a11_summary_totals["excluded_unique_units"], EXPECTED_A11_EXCLUDED_UNITS)
    add_check(checks, "a11_exported_unique_rows_reconcile", len(a11_unique_score_shas) == a11_summary_totals["exported_unique_units"], len(a11_unique_score_shas), a11_summary_totals["exported_unique_units"])
    add_check(checks, "a11_unique_score_plus_excluded_units", len(a11_unique_score_shas) + EXPECTED_A11_EXCLUDED_UNITS == EXPECTED_A11_FUN_UNITS, len(a11_unique_score_shas) + EXPECTED_A11_EXCLUDED_UNITS, EXPECTED_A11_FUN_UNITS)
    add_check(checks, "a11_database_sha_set_matches_fun_membership", set(a11_db_by_sha) == fun_shas, len(set(a11_db_by_sha) ^ fun_shas), 0, "A11 database unit identity must exactly equal A09 FUN membership.")

    fun_expected_windows_by_sha = {str(row["code_unit_sha256"]): int(row["expected_windows"]) for row in fun_rows}
    a11_window_count_mismatches = [
        sha for sha, expected in fun_expected_windows_by_sha.items()
        if sha not in a11_db_by_sha or int(a11_db_by_sha[sha]["windows"]) != expected
    ]
    add_check(
        checks,
        "a11_per_unit_window_counts_match_a09_fun_plan",
        not a11_window_count_mismatches,
        len(a11_window_count_mismatches),
        0,
        "Every A11 FUN SHA must have exactly its A09 expected window count.",
    )

    a11_excluded_shas = {sha for sha, _ in a11_exclusion_keys}
    add_check(checks, "a11_exclusion_unique_sha_count", len(a11_excluded_shas) == EXPECTED_A11_EXCLUDED_UNITS, len(a11_excluded_shas), EXPECTED_A11_EXCLUDED_UNITS)
    add_check(checks, "a11_finite_and_excluded_sha_sets_disjoint", not (a11_unique_score_shas & a11_excluded_shas), len(a11_unique_score_shas & a11_excluded_shas), 0)
    add_check(
        checks,
        "a11_finite_plus_excluded_sha_set_matches_fun_membership",
        (a11_unique_score_shas | a11_excluded_shas) == fun_shas,
        len((a11_unique_score_shas | a11_excluded_shas) ^ fun_shas),
        0,
        "A11 finite-score and expected-exclusion identities must exactly partition A09 FUN membership.",
    )

    # Verify every invalid A11 window is one of the explicitly frozen exclusions.
    observed_invalid_keys: set[tuple[str, int]] = set()
    for gpu_index in range(GPU_COUNT):
        db_path = a11_root / "results" / f"gpu-{gpu_index}" / "window_scores.sqlite3"
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            for sha, window_index in con.execute("SELECT code_unit_sha256, window_index FROM window_scores WHERE window_npr_valid = 0"):
                observed_invalid_keys.add((str(sha), int(window_index)))
        finally:
            con.close()
    add_check(checks, "a11_invalid_windows_exactly_expected_exclusions", observed_invalid_keys == a11_exclusion_keys, len(observed_invalid_keys ^ a11_exclusion_keys), 0)

    unit_rows: list[dict[str, Any]] = []
    reuse_rows: list[dict[str, Any]] = []
    new_rows: list[dict[str, Any]] = []
    per_shard = {sid: {"units": 0, "windows": 0} for sid in range(DATA_SHARDS)}
    reuse_class_counts = defaultdict(int)
    overlap_windows = 0
    overlap_expected_exclusion_windows = 0
    overlap_missing = 0

    for source in sorted(cfun_rows, key=lambda row: (int(row["logical_shard"]), str(row["code_unit_sha256"]))):
        sha = str(source["code_unit_sha256"])
        fun_membership = sha in fun_shas
        expected_windows = int(source["expected_windows"])
        a11 = a11_db_by_sha.get(sha)
        reuse_class = "not_in_a11_new_cfun"
        a11_gpu: int | str = ""
        a11_windows = 0
        a11_valid = 0
        a11_excluded = 0
        unique_present = int(sha in a11_unique_score_shas)
        requires_a14 = 1

        if fun_membership:
            overlap_windows += expected_windows
            requires_a14 = 0
            if a11 is None:
                overlap_missing += 1
                reuse_class = "a11_missing_error"
            else:
                a11_gpu = int(a11["gpu_index"])
                a11_windows = int(a11["windows"])
                a11_valid = int(a11["valid_windows"])
                a11_excluded = int(a11["invalid_windows"])
                overlap_expected_exclusion_windows += a11_excluded
                if int(a11["scoring_errors"]) != 0 or a11_windows != expected_windows:
                    reuse_class = "a11_incomplete_error"
                elif a11_excluded == 0 and a11_valid == expected_windows and unique_present:
                    reuse_class = "reuse_a11_finite"
                elif a11_valid == 0 and a11_excluded == expected_windows and not unique_present:
                    reuse_class = "reuse_a11_expected_exclusion"
                elif a11_valid > 0 and a11_excluded > 0 and unique_present:
                    reuse_class = "reuse_a11_partial"
                else:
                    reuse_class = "a11_reuse_state_error"
            reuse_class_counts[reuse_class] += 1
        else:
            shard_id = int(source["logical_shard"])
            per_shard[shard_id]["units"] += 1
            per_shard[shard_id]["windows"] += expected_windows
            reuse_class_counts[reuse_class] += 1

        row = {
            **source,
            "cfun_membership": 1,
            "fun_membership": int(fun_membership),
            "a11_reuse_class": reuse_class,
            "a11_gpu_index": a11_gpu,
            "a11_database_windows": a11_windows,
            "a11_valid_windows": a11_valid,
            "a11_expected_exclusion_windows": a11_excluded,
            "a11_unique_score_present": unique_present,
            "a14_scoring_required": requires_a14,
            "a14_gpu_index": "",
        }
        unit_rows.append(row)
        if fun_membership:
            reuse_rows.append(row)
        else:
            new_rows.append(row)

    bad_reuse_classes = {name: count for name, count in reuse_class_counts.items() if name.endswith("_error")}
    add_check(checks, "cfun_fun_overlap_identity", len(reuse_rows) == len(overlap_shas), len(reuse_rows), len(overlap_shas))
    add_check(checks, "cfun_fun_overlap_a11_missing_zero", overlap_missing == 0, overlap_missing, 0)
    add_check(checks, "cfun_fun_overlap_reuse_state_errors_zero", not bad_reuse_classes, sum(bad_reuse_classes.values()), 0, json.dumps(bad_reuse_classes, sort_keys=True))
    add_check(checks, "cfun_overlap_windows_accounted_by_a11", sum(int(row["a11_database_windows"]) for row in reuse_rows) == overlap_windows, sum(int(row["a11_database_windows"]) for row in reuse_rows), overlap_windows)

    new_units = len(new_rows)
    new_windows = sum(int(row["expected_windows"]) for row in new_rows)
    add_check(checks, "cfun_partition_units", len(reuse_rows) + new_units == len(cfun_rows), len(reuse_rows) + new_units, len(cfun_rows))
    add_check(checks, "cfun_partition_windows", overlap_windows + new_windows == cfun_windows, overlap_windows + new_windows, cfun_windows)

    lpt_plan = build_lpt_plan(per_shard)
    shard_to_gpu = {int(row["logical_shard"]): int(row["gpu_index"]) for row in lpt_plan}
    for row in unit_rows:
        if int(row["a14_scoring_required"]) == 1:
            row["a14_gpu_index"] = shard_to_gpu[int(row["logical_shard"])]
    reuse_rows = [row for row in unit_rows if int(row["fun_membership"]) == 1]
    new_rows = [row for row in unit_rows if int(row["a14_scoring_required"]) == 1]

    gpu_summary: list[dict[str, Any]] = []
    for gpu_index in range(GPU_COUNT):
        assigned = [row for row in lpt_plan if int(row["gpu_index"]) == gpu_index]
        gpu_summary.append({
            "gpu_index": gpu_index,
            "cfun_new_unique_units": sum(int(row["cfun_new_unique_units"]) for row in assigned),
            "cfun_new_windows": sum(int(row["cfun_new_windows"]) for row in assigned),
            "cfun_new_perturbations": sum(int(row["cfun_new_perturbations"]) for row in assigned),
            "assigned_logical_shards": ",".join(f"{int(row['logical_shard']):03d}" for row in assigned),
            "assignment_policy": A14_ASSIGNMENT_POLICY,
        })
    gpu_loads = [int(row["cfun_new_windows"]) for row in gpu_summary]
    add_check(checks, "a14_lpt_new_units_reconcile", sum(int(row["cfun_new_unique_units"]) for row in gpu_summary) == new_units, sum(int(row["cfun_new_unique_units"]) for row in gpu_summary), new_units)
    add_check(checks, "a14_lpt_new_windows_reconcile", sum(gpu_loads) == new_windows, sum(gpu_loads), new_windows)
    add_check(checks, "a14_lpt_all_96_shards_assigned_once", len(lpt_plan) == DATA_SHARDS and len({int(row["logical_shard"]) for row in lpt_plan}) == DATA_SHARDS, len(lpt_plan), DATA_SHARDS)

    atomic_csv(unit_rows, output_root / "python_cfun_workload_units.csv", UNIT_COLUMNS)
    atomic_csv(reuse_rows, output_root / "python_cfun_reuse_from_a11.csv", REUSE_COLUMNS)
    atomic_csv(new_rows, output_root / "python_cfun_new_scoring_units.csv", NEW_COLUMNS)
    atomic_csv(lpt_plan, output_root / "cfun_new_gpu_lpt_plan.csv", PLAN_COLUMNS)
    atomic_csv(gpu_summary, output_root / "cfun_new_gpu_summary.csv", GPU_COLUMNS)
    atomic_csv(checks, output_root / "checks.csv", CHECK_COLUMNS)

    failed_checks = [row for row in checks if not bool(row["passed"])]
    elapsed = time.perf_counter() - started
    status = "PASS" if not failed_checks else "FAIL"
    summary = {
        "status": status,
        "script_version": SCRIPT_VERSION,
        "category": CATEGORY,
        "code_unit_type": CODE_UNIT_TYPE,
        "a09_unique_primary_units": len(plan_rows),
        "cfun_unique_unit_memberships": len(cfun_rows),
        "cfun_windows": cfun_windows,
        "cfun_perturbations": cfun_windows * PERTURBATIONS_PER_WINDOW,
        "cfun_fun_overlap_unique_units": len(reuse_rows),
        "cfun_fun_overlap_windows": overlap_windows,
        "cfun_overlap_expected_exclusion_windows": overlap_expected_exclusion_windows,
        "a11_reuse_finite_units": reuse_class_counts["reuse_a11_finite"],
        "a11_reuse_partial_units": reuse_class_counts["reuse_a11_partial"],
        "a11_reuse_expected_exclusion_units": reuse_class_counts["reuse_a11_expected_exclusion"],
        "a14_new_unique_units": new_units,
        "a14_new_windows": new_windows,
        "a14_new_perturbations": new_windows * PERTURBATIONS_PER_WINDOW,
        "a14_gpu_window_loads": gpu_loads,
        "a14_assignment_policy": A14_ASSIGNMENT_POLICY,
        "failed_checks": len(failed_checks),
        "elapsed_seconds": elapsed,
        "completed_utc": utc_now(),
    }
    atomic_json(summary, output_root / "summary.json")
    metadata = {
        "script_version": SCRIPT_VERSION,
        "methodology": {
            "category": "C_FUN = A09 primary method_body membership",
            "reuse_key": "code_unit_sha256",
            "a11_reuse_policy": "reuse identical A11 FUN score/exclusion when the unique SHA also has C_FUN membership",
            "a14_scoring_scope": "C_FUN memberships without FUN membership only",
            "a14_assignment": A14_ASSIGNMENT_POLICY,
            "prepared_perturbations": "reuse frozen A09 originals and ordered perturbations exactly; no regeneration in A13",
            "classification": "disabled",
            "model_loading": "disabled",
        },
        "inputs": {
            "a09_summary": str(a09_summary_path),
            "a09_summary_sha256": sha256_file(a09_summary_path),
            "a09_unique_units": str(a09_units_path),
            "a09_unique_units_sha256": sha256_file(a09_units_path),
            "a10_summary": str(a10_summary_path),
            "a10_summary_sha256": sha256_file(a10_summary_path),
            "a11_root": str(a11_root),
            **a11_input_hashes,
        },
        "frozen_provenance": {
            "a09_config_fingerprint": EXPECTED_A09_CONFIG_FINGERPRINT,
            "a05_manifest_sha256": EXPECTED_A05_MANIFEST_SHA256,
            "a02_script_sha256": EXPECTED_A02_SHA256,
            "a02_config_fingerprint": EXPECTED_A02_CONFIG_FINGERPRINT,
            "model_revision": EXPECTED_MODEL_REVISION,
        },
        "runtime": {
            "host": platform.node(),
            "python_version": platform.python_version(),
            "model_loaded": False,
            "gpu_used": False,
        },
        "summary": summary,
    }
    atomic_json(metadata, output_root / "metadata.json")

    print("=" * 80)
    print("run-x-a13 C_FUN workload preparation and A11 reuse audit")
    print(f"Status:                              {status}")
    print(f"C_FUN unique-unit memberships:      {len(cfun_rows)}")
    print(f"C_FUN windows:                      {cfun_windows}")
    print(f"C_FUN perturbations:                {cfun_windows * PERTURBATIONS_PER_WINDOW}")
    print(f"C_FUN/FUN overlap unique units:     {len(reuse_rows)}")
    print(f"C_FUN/FUN overlap windows:          {overlap_windows}")
    print(f"A11 finite scores reused:           {reuse_class_counts['reuse_a11_finite']}")
    print(f"A11 partial scores reused:          {reuse_class_counts['reuse_a11_partial']}")
    print(f"A11 expected exclusions reused:     {reuse_class_counts['reuse_a11_expected_exclusion']}")
    print(f"A14 new unique units to score:      {new_units}")
    print(f"A14 new windows to score:           {new_windows}")
    print(f"A14 new perturbations:              {new_windows * PERTURBATIONS_PER_WINDOW}")
    print(f"A14 LPT GPU window loads:           {gpu_loads}")
    print(f"A14 assignment policy:              {A14_ASSIGNMENT_POLICY}")
    print(f"Failed checks:                      {len(failed_checks)}")
    print(f"Elapsed seconds:                    {elapsed:.3f}")
    print(f"Output root:                        {output_root}")
    print("=" * 80)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
