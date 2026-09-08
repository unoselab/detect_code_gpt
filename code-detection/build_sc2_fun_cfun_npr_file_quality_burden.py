#!/usr/bin/env python3
"""Build file-level SonarQube burden on the frozen C04 FUN+C_FUN NPR universe.

C05 is a CPU-only outcome-join stage. It does not score code, load an LLM, or
select/recalibrate an NPR threshold. It reuses the validated scientific logic of
the historical I03 combined FUN+C_FUN quality join while switching the detector
input lineage to the frozen C04 v2 artifact.

Primary semantics
-----------------
- File universe: all C04 repo-month/file rows.
- NPR metric preserved: file_npr_fun_cfun_space_by_token_weighted.
- Quality outcome: unresolved Python-file SonarQube issue stock from frozen B05.
- Join key: C04 snapshot_id == B05 snapshot_key and relative_path == component_path.
- B05 issue-bearing Python files outside the C04 file universe are explicit scope
  exclusions; they are never silently dropped from reconciliation.
- A C04 file with no matching B05 issue row receives zero issue burden.
- No NPR threshold is applied in C05. The frozen C04 threshold grid is consumed
  only by the next aggregation stage.
- Density is not computed because file-level SonarQube NCLOC is not available in
  the file-level join artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

SCRIPT_VERSION = "run-x-c05-v1"
EXPECTED_C04_SCRIPT_VERSION = "run-x-c04-v2"
EXPECTED_C04_SCOPE = "combined FUN + C_FUN procedure-body file NPR"
EXPECTED_NPR_METRIC = "file_npr_fun_cfun_space_by_token_weighted"
EXPECTED_C04_PRIMARY_THRESHOLD = 1.515059

EXPECTED_B05_SHA256 = {
    "raw_issues": "ad0f8a27c47ca0ac5e541a508b8e3f18f2c336b7cbe9d29b0bc9876529bbfd0c",
    "snapshot_counts": "cf5d3d8aaeaa8afc9678f9565af8eca9f599ce88789602acb36a0499bc7b8574",
    "qc": "0cdfaa0cf69fe9d4179ebe7e773152c553b62ba56f0ca05c67c11985ac59d460",
    "summary": "0edd9f723697a97c4eb45ed452e4a4a129289bb201f222962f1e425b0dd87c8e",
}

EXPECTED = {
    "c04_rows": 510297,
    "c04_unique_snapshot_files": 494592,
    "c04_finite_combined_rows": 359057,
    "snapshots": 1496,
    "repositories": 167,
    "repo_months": 1954,
    "raw_issue_rows": 554258,
    "issue_bearing_snapshot_files": 114770,
    "joined_issue_bearing_snapshot_files": 114646,
    "outside_c04_issue_bearing_files": 124,
    "outside_c04_issue_rows": 774,
    "outside_c04_affected_snapshots": 21,
    "outside_c04_code_smell": 772,
    "outside_c04_bug": 2,
    "outside_c04_vulnerability": 0,
    "outside_c04_high_severity": 216,
    "outside_c04_maintainability": 772,
    "outside_c04_reliability": 5,
    "outside_c04_security": 1,
    "repo_month_file_rows_with_any_issue": 121332,
    "repo_month_file_rows_with_zero_issues": 388965,
    "b05_code_smell": 537369,
    "b05_bug": 12040,
    "b05_vulnerability": 4849,
    "b05_maintainability": 533825,
    "b05_reliability": 31493,
    "b05_security": 7221,
}

C04_REQUIRED = {
    "repo_id",
    "dataset_source",
    "repo_name",
    "repo_month",
    "time_index",
    "event_index",
    "snapshot_id",
    "snapshot_commit",
    "relative_path",
    "file_sha256",
    "fun_occurrences_total",
    "fun_occurrences_scored",
    "fun_occurrences_excluded",
    "file_npr_fun_space_by_token_weighted",
    "cfun_occurrences_total",
    "cfun_occurrences_scored",
    "cfun_occurrences_excluded",
    "file_npr_cfun_space_by_token_weighted",
    "fun_cfun_occurrences_total",
    "fun_cfun_occurrences_scored",
    "fun_cfun_occurrences_excluded",
    "file_npr_fun_cfun_space_by_token_weighted",
    "file_npr_fun_cfun_status",
}

B05_RAW_REQUIRED = {
    "manifest_order",
    "dataset_source",
    "repo_name",
    "snapshot_key",
    "commit_sha",
    "issue_key",
    "type",
    "severity",
    "status",
    "resolution",
    "component_path",
    "component_scope",
    "impacts_json",
}

B05_SNAPSHOT_REQUIRED = {
    "dataset_source",
    "repo_name",
    "snapshot_key",
    "commit_sha",
    "issue_total_py_sonarqube",
    "issue_type_code_smell",
    "issue_type_bug",
    "issue_type_vulnerability",
    "issue_with_maintainability_impact",
    "issue_with_reliability_impact",
    "issue_with_security_impact",
}

QUALITY_COUNT_COLUMNS = [
    "sonar_issue_total",
    "sonar_issue_type_code_smell",
    "sonar_issue_type_bug",
    "sonar_issue_type_vulnerability",
    "sonar_issue_type_other",
    "sonar_issue_severity_blocker",
    "sonar_issue_severity_critical",
    "sonar_issue_severity_major",
    "sonar_issue_severity_minor",
    "sonar_issue_severity_info",
    "sonar_issue_severity_other",
    "sonar_issue_high_severity",
    "sonar_issue_with_maintainability_impact",
    "sonar_issue_with_reliability_impact",
    "sonar_issue_with_security_impact",
]


@dataclass
class Check:
    check: str
    observed: Any
    expected: Any
    status: str
    detail: str = ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require_columns(df: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def as_int_series(mask: pd.Series) -> pd.Series:
    return mask.fillna(False).astype(np.int64)


def parse_summary_csv(path: Path) -> dict[str, str]:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    require_columns(df, {"metric", "value"}, "B05 summary")
    return dict(zip(df["metric"], df["value"]))


def add_check(checks: list[Check], name: str, observed: Any, expected: Any, passed: bool, detail: str = "") -> None:
    checks.append(Check(name, observed, expected, "pass" if passed else "FAIL", detail))


def pattern_label(a: pd.Series, b: pd.Series, a_name: str, b_name: str) -> pd.Series:
    return np.select(
        [a & b, a & ~b, ~a & b],
        [f"{a_name}_and_{b_name}", f"{a_name}_only", f"{b_name}_only"],
        default="neither",
    )


def aggregate_issue_files(raw: pd.DataFrame) -> pd.DataFrame:
    """Aggregate one row per B05 issue-bearing snapshot/Python-file."""
    require_columns(raw, B05_RAW_REQUIRED, "B05 raw issues")

    if len(raw) == 0:
        cols = ["dataset_source", "repo_name", "snapshot_key", "commit_sha", "component_path"] + QUALITY_COUNT_COLUMNS
        return pd.DataFrame(columns=cols)

    impacts = raw["impacts_json"].fillna("").astype(str)
    work = raw[["dataset_source", "repo_name", "snapshot_key", "commit_sha", "component_path"]].copy()
    work["sonar_issue_total"] = 1

    issue_type = raw["type"].fillna("").astype(str).str.upper()
    for value, col in [
        ("CODE_SMELL", "sonar_issue_type_code_smell"),
        ("BUG", "sonar_issue_type_bug"),
        ("VULNERABILITY", "sonar_issue_type_vulnerability"),
    ]:
        work[col] = as_int_series(issue_type.eq(value))
    work["sonar_issue_type_other"] = as_int_series(~issue_type.isin(["CODE_SMELL", "BUG", "VULNERABILITY"]))

    severity = raw["severity"].fillna("").astype(str).str.upper()
    known_severity = ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]
    for value, col in [
        ("BLOCKER", "sonar_issue_severity_blocker"),
        ("CRITICAL", "sonar_issue_severity_critical"),
        ("MAJOR", "sonar_issue_severity_major"),
        ("MINOR", "sonar_issue_severity_minor"),
        ("INFO", "sonar_issue_severity_info"),
    ]:
        work[col] = as_int_series(severity.eq(value))
    work["sonar_issue_severity_other"] = as_int_series(~severity.isin(known_severity))
    work["sonar_issue_high_severity"] = as_int_series(severity.isin(["BLOCKER", "CRITICAL"]))

    # B05 stores SonarQube Clean Code impacts as compact JSON. String matching is
    # intentional here because only presence/absence of a softwareQuality label is
    # required, and it exactly reproduces the frozen I03 semantics.
    work["sonar_issue_with_maintainability_impact"] = as_int_series(impacts.str.contains("MAINTAINABILITY", regex=False))
    work["sonar_issue_with_reliability_impact"] = as_int_series(impacts.str.contains("RELIABILITY", regex=False))
    work["sonar_issue_with_security_impact"] = as_int_series(impacts.str.contains("SECURITY", regex=False))

    keys = ["dataset_source", "repo_name", "snapshot_key", "commit_sha", "component_path"]
    out = work.groupby(keys, sort=False, dropna=False)[QUALITY_COUNT_COLUMNS].sum().reset_index()
    return out


def prepare_c04_derived(c04: pd.DataFrame) -> pd.DataFrame:
    """Add transparent category-presence diagnostics without changing C04 NPR."""
    out = c04.copy()
    out["fun_present"] = as_int_series(pd.to_numeric(out["fun_occurrences_total"], errors="coerce").fillna(0).gt(0))
    out["cfun_present"] = as_int_series(pd.to_numeric(out["cfun_occurrences_total"], errors="coerce").fillna(0).gt(0))
    out["fun_finite_npr"] = as_int_series(pd.to_numeric(out["file_npr_fun_space_by_token_weighted"], errors="coerce").notna())
    out["cfun_finite_npr"] = as_int_series(pd.to_numeric(out["file_npr_cfun_space_by_token_weighted"], errors="coerce").notna())
    out["procedure_body_presence_pattern"] = pattern_label(
        out["fun_present"].astype(bool), out["cfun_present"].astype(bool), "fun", "cfun"
    )
    out["procedure_body_finite_npr_pattern"] = pattern_label(
        out["fun_finite_npr"].astype(bool), out["cfun_finite_npr"].astype(bool), "fun", "cfun"
    )
    total = pd.to_numeric(out["fun_cfun_occurrences_total"], errors="coerce").fillna(0)
    scored = pd.to_numeric(out["fun_cfun_occurrences_scored"], errors="coerce").fillna(0)
    excluded = pd.to_numeric(out["fun_cfun_occurrences_excluded"], errors="coerce").fillna(0)
    out["fun_cfun_occurrences_missing"] = (total - scored - excluded).astype(np.int64)
    return out


def build_snapshot_audit(
    c04_unique: pd.DataFrame,
    issue_files: pd.DataFrame,
    outside: pd.DataFrame,
    snapshot_counts: pd.DataFrame,
) -> pd.DataFrame:
    """Reconcile B05 snapshot totals = joined C04 file stock + outside-C04 stock."""
    key_map = c04_unique[["snapshot_id", "relative_path"]].drop_duplicates()
    joined_issue = issue_files.merge(
        key_map,
        left_on=["snapshot_key", "component_path"],
        right_on=["snapshot_id", "relative_path"],
        how="inner",
        validate="one_to_one",
    )

    def by_snapshot(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["snapshot_key"])
        agg = df.groupby("snapshot_key", sort=False)[QUALITY_COUNT_COLUMNS].sum().reset_index()
        suffix_map = {
            "sonar_issue_total": "total",
            "sonar_issue_type_code_smell": "code_smell",
            "sonar_issue_type_bug": "bug",
            "sonar_issue_type_vulnerability": "vulnerability",
            "sonar_issue_type_other": "type_other",
            "sonar_issue_severity_blocker": "severity_blocker",
            "sonar_issue_severity_critical": "severity_critical",
            "sonar_issue_severity_major": "severity_major",
            "sonar_issue_severity_minor": "severity_minor",
            "sonar_issue_severity_info": "severity_info",
            "sonar_issue_severity_other": "severity_other",
            "sonar_issue_high_severity": "high_severity",
            "sonar_issue_with_maintainability_impact": "maintainability_impact",
            "sonar_issue_with_reliability_impact": "reliability_impact",
            "sonar_issue_with_security_impact": "security_impact",
        }
        return agg.rename(columns={c: f"{prefix}{suffix_map[c]}" for c in QUALITY_COUNT_COLUMNS})

    joined_s = by_snapshot(joined_issue, "c05_joined_")
    outside_s = by_snapshot(outside, "outside_c04_")
    outside_file_counts = (
        outside.groupby("snapshot_key", sort=False).size().rename("outside_c04_issue_bearing_files").reset_index()
        if not outside.empty
        else pd.DataFrame(columns=["snapshot_key", "outside_c04_issue_bearing_files"])
    )

    base = snapshot_counts[
        [
            "snapshot_key",
            "dataset_source",
            "repo_name",
            "commit_sha",
            "issue_total_py_sonarqube",
            "issue_type_code_smell",
            "issue_type_bug",
            "issue_type_vulnerability",
            "issue_with_maintainability_impact",
            "issue_with_reliability_impact",
            "issue_with_security_impact",
        ]
    ].copy()
    base = base.rename(
        columns={
            "issue_total_py_sonarqube": "b05_issue_total",
            "issue_type_code_smell": "b05_code_smell",
            "issue_type_bug": "b05_bug",
            "issue_type_vulnerability": "b05_vulnerability",
            "issue_with_maintainability_impact": "b05_maintainability_impact",
            "issue_with_reliability_impact": "b05_reliability_impact",
            "issue_with_security_impact": "b05_security_impact",
        }
    )
    # B05 snapshot counts contain the severity components needed to recover high severity.
    sev_cols = ["issue_severity_blocker", "issue_severity_critical"]
    if all(c in snapshot_counts.columns for c in sev_cols):
        sev = snapshot_counts[["snapshot_key"] + sev_cols].copy()
        sev["b05_high_severity"] = pd.to_numeric(sev[sev_cols[0]], errors="coerce").fillna(0) + pd.to_numeric(
            sev[sev_cols[1]], errors="coerce"
        ).fillna(0)
        base = base.merge(sev[["snapshot_key", "b05_high_severity"]], on="snapshot_key", how="left", validate="one_to_one")
    else:
        base["b05_high_severity"] = 0

    audit = base.merge(joined_s, on="snapshot_key", how="left", validate="one_to_one")
    audit = audit.merge(outside_s, on="snapshot_key", how="left", validate="one_to_one")
    audit = audit.merge(outside_file_counts, on="snapshot_key", how="left", validate="one_to_one")
    numeric_cols = [c for c in audit.columns if c.startswith("c05_joined_") or c.startswith("outside_c04_")]
    numeric_cols += ["outside_c04_issue_bearing_files"]
    for c in numeric_cols:
        audit[c] = pd.to_numeric(audit[c], errors="coerce").fillna(0).astype(np.int64)

    mappings = [
        ("issue_total", "total"),
        ("code_smell", "code_smell"),
        ("bug", "bug"),
        ("vulnerability", "vulnerability"),
        ("high_severity", "high_severity"),
        ("maintainability_impact", "maintainability_impact"),
        ("reliability_impact", "reliability_impact"),
        ("security_impact", "security_impact"),
    ]
    for source_suffix, short in mappings:
        b05_col = f"b05_{source_suffix}"
        joined_col = f"c05_joined_{source_suffix if source_suffix != 'issue_total' else 'total'}"
        outside_col = f"outside_c04_{source_suffix if source_suffix != 'issue_total' else 'total'}"
        if b05_col not in audit.columns:
            continue
        if joined_col not in audit.columns:
            audit[joined_col] = 0
        if outside_col not in audit.columns:
            audit[outside_col] = 0
        accounted = f"accounted_{short}"
        matches = f"{short}_matches"
        audit[accounted] = pd.to_numeric(audit[joined_col], errors="coerce").fillna(0) + pd.to_numeric(
            audit[outside_col], errors="coerce"
        ).fillna(0)
        audit[matches] = audit[accounted].astype(np.int64).eq(
            pd.to_numeric(audit[b05_col], errors="coerce").fillna(0).astype(np.int64)
        )
    return audit


def write_csv(df: pd.DataFrame, path: Path, gzip: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if gzip:
        df.to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})
    else:
        df.to_csv(path, index=False)


def run_self_test() -> None:
    raw = pd.DataFrame(
        {
            "manifest_order": [1, 1, 1],
            "dataset_source": ["control"] * 3,
            "repo_name": ["o/r"] * 3,
            "snapshot_key": ["s1", "s1", "s1"],
            "commit_sha": ["abc"] * 3,
            "issue_key": ["i1", "i2", "i3"],
            "type": ["CODE_SMELL", "BUG", "CODE_SMELL"],
            "severity": ["CRITICAL", "MAJOR", "MINOR"],
            "status": ["OPEN"] * 3,
            "resolution": [np.nan] * 3,
            "component_path": ["a.py", "a.py", "outside.py"],
            "component_scope": ["python_file"] * 3,
            "impacts_json": [
                '[{"severity":"HIGH","softwareQuality":"MAINTAINABILITY"}]',
                '[{"severity":"MEDIUM","softwareQuality":"RELIABILITY"}]',
                '[{"severity":"LOW","softwareQuality":"SECURITY"}]',
            ],
        }
    )
    agg = aggregate_issue_files(raw)
    a = agg.loc[agg["component_path"].eq("a.py")].iloc[0]
    assert int(a["sonar_issue_total"]) == 2
    assert int(a["sonar_issue_type_code_smell"]) == 1
    assert int(a["sonar_issue_type_bug"]) == 1
    assert int(a["sonar_issue_high_severity"]) == 1
    assert int(a["sonar_issue_with_maintainability_impact"]) == 1
    assert int(a["sonar_issue_with_reliability_impact"]) == 1

    c04 = pd.DataFrame(
        {
            "repo_id": [1, 1],
            "dataset_source": ["control", "control"],
            "repo_name": ["o/r", "o/r"],
            "repo_month": ["2024-01", "2024-02"],
            "time_index": [1, 2],
            "event_index": [0, 0],
            "snapshot_id": ["s1", "s1"],
            "snapshot_commit": ["abc", "abc"],
            "relative_path": ["a.py", "zero.py"],
            "file_sha256": ["x", "y"],
            "fun_occurrences_total": [1, 0],
            "fun_occurrences_scored": [1, 0],
            "fun_occurrences_excluded": [0, 0],
            "file_npr_fun_space_by_token_weighted": [1.6, np.nan],
            "cfun_occurrences_total": [0, 1],
            "cfun_occurrences_scored": [0, 1],
            "cfun_occurrences_excluded": [0, 0],
            "file_npr_cfun_space_by_token_weighted": [np.nan, 1.4],
            "fun_cfun_occurrences_total": [1, 1],
            "fun_cfun_occurrences_scored": [1, 1],
            "fun_cfun_occurrences_excluded": [0, 0],
            "file_npr_fun_cfun_space_by_token_weighted": [1.6, 1.4],
            "file_npr_fun_cfun_status": ["scored", "scored"],
        }
    )
    d = prepare_c04_derived(c04)
    assert d["procedure_body_finite_npr_pattern"].tolist() == ["fun_only", "cfun_only"]
    print("build_sc2_fun_cfun_npr_file_quality_burden self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--c04-file", type=Path)
    parser.add_argument("--c04-summary-file", type=Path)
    parser.add_argument("--c04-checks-file", type=Path)
    parser.add_argument("--b05-raw-issues-file", type=Path)
    parser.add_argument("--b05-snapshot-counts-file", type=Path)
    parser.add_argument("--b05-qc-file", type=Path)
    parser.add_argument("--b05-summary-file", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--strict-expected-counts", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0

    required_args = [
        "c04_file",
        "c04_summary_file",
        "c04_checks_file",
        "b05_raw_issues_file",
        "b05_snapshot_counts_file",
        "b05_qc_file",
        "b05_summary_file",
        "output_dir",
    ]
    for name in required_args:
        if getattr(args, name) is None:
            parser.error(f"--{name.replace('_', '-')} is required unless --self-test is used")

    started = datetime.now(timezone.utc)
    outdir: Path = args.output_dir
    outdir.mkdir(parents=True, exist_ok=True)

    paths = {
        "c04_file": args.c04_file,
        "c04_summary": args.c04_summary_file,
        "c04_checks": args.c04_checks_file,
        "b05_raw_issues": args.b05_raw_issues_file,
        "b05_snapshot_counts": args.b05_snapshot_counts_file,
        "b05_qc": args.b05_qc_file,
        "b05_summary": args.b05_summary_file,
    }
    for label, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"{label} does not exist: {path}")

    with args.c04_summary_file.open() as f:
        c04_summary = json.load(f)
    c04_checks = pd.read_csv(args.c04_checks_file)
    b05_qc = pd.read_csv(args.b05_qc_file, dtype=str, keep_default_na=False)
    b05_summary = parse_summary_csv(args.b05_summary_file)

    c04 = pd.read_csv(args.c04_file, low_memory=False)
    require_columns(c04, C04_REQUIRED, "C04 continuous NPR")
    raw = pd.read_csv(args.b05_raw_issues_file, low_memory=False)
    require_columns(raw, B05_RAW_REQUIRED, "B05 raw issues")
    snapshot_counts = pd.read_csv(args.b05_snapshot_counts_file, low_memory=False)
    require_columns(snapshot_counts, B05_SNAPSHOT_REQUIRED, "B05 snapshot counts")

    checks: list[Check] = []

    # C04 provenance contract.
    add_check(checks, "c04_script_version", c04_summary.get("script_version"), EXPECTED_C04_SCRIPT_VERSION, c04_summary.get("script_version") == EXPECTED_C04_SCRIPT_VERSION)
    add_check(checks, "c04_status", c04_summary.get("status"), "PASS", c04_summary.get("status") == "PASS")
    add_check(checks, "c04_hard_check_failures", c04_summary.get("hard_check_failures"), 0, int(c04_summary.get("hard_check_failures", -1)) == 0)
    add_check(checks, "c04_scope", c04_summary.get("scope"), EXPECTED_C04_SCOPE, c04_summary.get("scope") == EXPECTED_C04_SCOPE)
    add_check(
        checks,
        "c04_primary_metric",
        c04_summary.get("methodology", {}).get("primary_metric"),
        EXPECTED_NPR_METRIC,
        c04_summary.get("methodology", {}).get("primary_metric") == EXPECTED_NPR_METRIC,
    )
    add_check(
        checks,
        "c04_quality_outcomes_not_consumed",
        c04_summary.get("methodology", {}).get("quality_outcomes"),
        "not consumed",
        c04_summary.get("methodology", {}).get("quality_outcomes") == "not consumed",
    )
    c04_primary = float(c04_summary.get("threshold", {}).get("primary", math.nan))
    add_check(checks, "c04_primary_threshold_provenance", c04_primary, EXPECTED_C04_PRIMARY_THRESHOLD, math.isclose(c04_primary, EXPECTED_C04_PRIMARY_THRESHOLD, rel_tol=0, abs_tol=1e-12), "Provenance only; C05 does not apply any threshold.")

    c04_hard = c04_checks.loc[c04_checks["severity"].astype(str).str.lower().eq("hard")].copy()
    c04_failed = c04_hard.loc[pd.to_numeric(c04_hard["passed"], errors="coerce").fillna(0).ne(1)]
    add_check(checks, "c04_threshold_checks_all_hard_pass", len(c04_hard) - len(c04_failed), len(c04_hard), len(c04_failed) == 0)

    # Freeze B05 exact artifact provenance and QC.
    observed_b05_hashes = {
        "raw_issues": sha256_file(args.b05_raw_issues_file),
        "snapshot_counts": sha256_file(args.b05_snapshot_counts_file),
        "qc": sha256_file(args.b05_qc_file),
        "summary": sha256_file(args.b05_summary_file),
    }
    for key, expected_hash in EXPECTED_B05_SHA256.items():
        add_check(checks, f"b05_sha256::{key}", observed_b05_hashes[key], expected_hash, observed_b05_hashes[key] == expected_hash)

    b05_qc_pass = b05_qc["status"].str.lower().eq("pass")
    add_check(checks, "b05_qc_all_pass", int(b05_qc_pass.sum()), len(b05_qc), bool(b05_qc_pass.all()))

    # B05 primary raw input must be unresolved Python-file issue stock.
    add_check(checks, "b05_component_scope_python_only", int(raw["component_scope"].astype(str).eq("python_file").sum()), len(raw), raw["component_scope"].astype(str).eq("python_file").all())
    add_check(checks, "b05_status_open_only", int(raw["status"].astype(str).str.upper().eq("OPEN").sum()), len(raw), raw["status"].astype(str).str.upper().eq("OPEN").all())
    add_check(checks, "b05_duplicate_issue_keys", int(raw.duplicated(["snapshot_key", "issue_key"]).sum()), 0, int(raw.duplicated(["snapshot_key", "issue_key"]).sum()) == 0)

    # C04 structural counts.
    finite_combined = pd.to_numeric(c04[EXPECTED_NPR_METRIC], errors="coerce").notna()
    unique_file_keys = ["snapshot_id", "relative_path"]
    c04_unique = c04.drop_duplicates(unique_file_keys, keep="first").copy()
    c04_unique_duplicate_value_mismatch = 0
    # Every repeated repo-month occurrence of the same snapshot/file must preserve its file identity.
    identity_cols = ["dataset_source", "repo_name", "snapshot_commit", "file_sha256"]
    grouped_nunique = c04.groupby(unique_file_keys, sort=False)[identity_cols].nunique(dropna=False)
    c04_unique_duplicate_value_mismatch = int((grouped_nunique > 1).any(axis=1).sum())

    structural = {
        "c04_rows": len(c04),
        "c04_unique_snapshot_files": len(c04_unique),
        "c04_finite_combined_rows": int(finite_combined.sum()),
        "snapshots": int(c04["snapshot_id"].nunique()),
        "repositories": int(c04[["dataset_source", "repo_name"]].drop_duplicates().shape[0]),
        "repo_months": int(c04[["dataset_source", "repo_name", "repo_month"]].drop_duplicates().shape[0]),
    }
    for key in ["c04_rows", "c04_unique_snapshot_files", "c04_finite_combined_rows", "snapshots", "repositories", "repo_months"]:
        add_check(checks, key, structural[key], EXPECTED[key], structural[key] == EXPECTED[key])
    add_check(checks, "c04_repeated_snapshot_file_identity_mismatch", c04_unique_duplicate_value_mismatch, 0, c04_unique_duplicate_value_mismatch == 0)

    # Recompute file-level B05 issue stock and join to the frozen C04 file universe.
    issue_files = aggregate_issue_files(raw)
    issue_file_count = len(issue_files)
    add_check(checks, "issue_bearing_snapshot_files", issue_file_count, EXPECTED["issue_bearing_snapshot_files"], issue_file_count == EXPECTED["issue_bearing_snapshot_files"])

    c04_key_map = c04_unique[["snapshot_id", "relative_path"]].copy()
    issue_marked = issue_files.merge(
        c04_key_map,
        left_on=["snapshot_key", "component_path"],
        right_on=["snapshot_id", "relative_path"],
        how="left",
        indicator=True,
        validate="one_to_one",
    )
    outside = issue_marked.loc[issue_marked["_merge"].eq("left_only")].drop(columns=["snapshot_id", "relative_path", "_merge"]).copy()
    joined_issue_files = issue_marked.loc[issue_marked["_merge"].eq("both")].copy()
    joined_issue_file_count = len(joined_issue_files)

    add_check(checks, "joined_issue_bearing_snapshot_files", joined_issue_file_count, EXPECTED["joined_issue_bearing_snapshot_files"], joined_issue_file_count == EXPECTED["joined_issue_bearing_snapshot_files"])
    add_check(checks, "outside_c04_issue_bearing_files", len(outside), EXPECTED["outside_c04_issue_bearing_files"], len(outside) == EXPECTED["outside_c04_issue_bearing_files"], "Frozen SonarQube path aliases outside the C04/A05 file universe remain explicit scope exclusions.")
    add_check(checks, "all_b05_issue_bearing_snapshot_files_accounted", joined_issue_file_count + len(outside), issue_file_count, joined_issue_file_count + len(outside) == issue_file_count)

    outside_sums = {c: int(pd.to_numeric(outside[c], errors="coerce").fillna(0).sum()) for c in QUALITY_COUNT_COLUMNS}
    outside_expected = {
        "sonar_issue_total": EXPECTED["outside_c04_issue_rows"],
        "sonar_issue_type_code_smell": EXPECTED["outside_c04_code_smell"],
        "sonar_issue_type_bug": EXPECTED["outside_c04_bug"],
        "sonar_issue_type_vulnerability": EXPECTED["outside_c04_vulnerability"],
        "sonar_issue_high_severity": EXPECTED["outside_c04_high_severity"],
        "sonar_issue_with_maintainability_impact": EXPECTED["outside_c04_maintainability"],
        "sonar_issue_with_reliability_impact": EXPECTED["outside_c04_reliability"],
        "sonar_issue_with_security_impact": EXPECTED["outside_c04_security"],
    }
    for col, exp in outside_expected.items():
        add_check(checks, f"outside_c04::{col}", outside_sums[col], exp, outside_sums[col] == exp)
    outside_snapshots = int(outside["snapshot_key"].nunique())
    add_check(checks, "outside_c04_affected_snapshots", outside_snapshots, EXPECTED["outside_c04_affected_snapshots"], outside_snapshots == EXPECTED["outside_c04_affected_snapshots"])

    # Join issue stock to every repo-month/file occurrence. Absent issue rows are true zero stock.
    issue_join = issue_files.rename(columns={"snapshot_key": "snapshot_id", "component_path": "relative_path"})
    join_cols = ["snapshot_id", "relative_path"] + QUALITY_COUNT_COLUMNS
    enriched = prepare_c04_derived(c04)
    enriched = enriched.merge(issue_join[join_cols], on=["snapshot_id", "relative_path"], how="left", validate="many_to_one")
    for c in QUALITY_COUNT_COLUMNS:
        enriched[c] = pd.to_numeric(enriched[c], errors="coerce").fillna(0).astype(np.int64)
    enriched["sonar_issue_file_has_any"] = enriched["sonar_issue_total"].gt(0).astype(np.int64)
    enriched["sonar_issue_join_status"] = np.where(enriched["sonar_issue_file_has_any"].eq(1), "matched_issue_file", "zero_issue_file")

    with_issue = int(enriched["sonar_issue_file_has_any"].sum())
    zero_issue = int(len(enriched) - with_issue)
    add_check(checks, "repo_month_file_rows_with_any_issue", with_issue, EXPECTED["repo_month_file_rows_with_any_issue"], with_issue == EXPECTED["repo_month_file_rows_with_any_issue"])
    add_check(checks, "repo_month_file_rows_with_zero_issues", zero_issue, EXPECTED["repo_month_file_rows_with_zero_issues"], zero_issue == EXPECTED["repo_month_file_rows_with_zero_issues"])
    add_check(checks, "joined_row_count_preserved", len(enriched), len(c04), len(enriched) == len(c04))

    # Snapshot-level reconciliation against the authoritative B05 snapshot counts.
    audit = build_snapshot_audit(c04_unique, issue_files, outside, snapshot_counts)
    match_cols = [c for c in audit.columns if c.endswith("_matches")]
    snapshot_mismatches = int(sum((~audit[c].astype(bool)).sum() for c in match_cols))
    add_check(checks, "snapshot_issue_totals_reconcile_joined_plus_scope_excluded", snapshot_mismatches, 0, snapshot_mismatches == 0)

    # Frozen B05 global totals.
    b05_expected_summary = {
        "raw_issue_rows": EXPECTED["raw_issue_rows"],
        "selected_snapshots": EXPECTED["snapshots"],
        "collected_repositories": EXPECTED["repositories"],
        "code_smell_issue_stock_sum": EXPECTED["b05_code_smell"],
        "bug_issue_stock_sum": EXPECTED["b05_bug"],
        "vulnerability_issue_stock_sum": EXPECTED["b05_vulnerability"],
        "maintainability_impact_issue_stock_sum": EXPECTED["b05_maintainability"],
        "reliability_impact_issue_stock_sum": EXPECTED["b05_reliability"],
        "security_impact_issue_stock_sum": EXPECTED["b05_security"],
    }
    for metric, exp in b05_expected_summary.items():
        obs_str = b05_summary.get(metric, "")
        try:
            obs = int(float(obs_str))
        except ValueError:
            obs = obs_str
        add_check(checks, f"b05_summary::{metric}", obs, exp, obs == exp)

    # Strict production mode turns every failed contract into a nonzero exit.
    failed = [c for c in checks if c.status != "pass"]
    hard_failures = len(failed)
    status = "PASS_WITH_SCOPE_EXCLUSIONS" if hard_failures == 0 else "FAIL"

    output_file = outdir / "python_fun_cfun_file_quality_burden.csv.gz"
    audit_file = outdir / "python_fun_cfun_file_quality_snapshot_audit.csv"
    outside_file = outdir / "python_sonarqube_issue_files_outside_c04.csv"
    checks_file = outdir / "python_fun_cfun_file_quality_checks.csv"
    summary_csv = outdir / "python_fun_cfun_file_quality_summary.csv"
    summary_json = outdir / "summary.json"
    metadata_file = outdir / "metadata.json"

    write_csv(enriched, output_file, gzip=True)
    write_csv(audit, audit_file)
    write_csv(outside, outside_file)
    checks_df = pd.DataFrame([c.__dict__ for c in checks])
    write_csv(checks_df, checks_file)

    summary_rows = [
        ("script_version", SCRIPT_VERSION),
        ("status", status),
        ("quality_semantics", "unresolved_python_sonarqube_issue_stock_at_historical_snapshot"),
        ("npr_metric_preserved", EXPECTED_NPR_METRIC),
        ("threshold_applied", 0),
        ("c04_primary_threshold_provenance_only", EXPECTED_C04_PRIMARY_THRESHOLD),
        ("density_computed", 0),
        ("c04_repo_month_file_rows", len(c04)),
        ("c04_unique_snapshot_files", len(c04_unique)),
        ("c04_finite_fun_cfun_rows", int(finite_combined.sum())),
        ("snapshots", structural["snapshots"]),
        ("repositories", structural["repositories"]),
        ("repo_months", structural["repo_months"]),
        ("b05_raw_issue_rows", len(raw)),
        ("b05_issue_bearing_snapshot_files", issue_file_count),
        ("b05_issue_bearing_snapshot_files_joined", joined_issue_file_count),
        ("b05_issue_bearing_snapshot_files_outside_c04", len(outside)),
        ("b05_issue_rows_outside_c04", outside_sums["sonar_issue_total"]),
        ("b05_snapshots_with_outside_c04_issue_files", outside_snapshots),
        ("repo_month_file_rows_with_any_issue", with_issue),
        ("repo_month_file_rows_with_zero_issues", zero_issue),
        ("snapshot_audit_mismatch_rows", snapshot_mismatches),
        ("hard_qc_failures", hard_failures),
    ]
    write_csv(pd.DataFrame(summary_rows, columns=["metric", "value"]), summary_csv)

    completed = datetime.now(timezone.utc)
    summary_obj = {
        "script_version": SCRIPT_VERSION,
        "status": status,
        "started_utc": started.isoformat(),
        "completed_utc": completed.isoformat(),
        "scope": "C04 combined FUN+C_FUN NPR x B05 unresolved Python-file SonarQube issue stock",
        "methodology": {
            "file_universe": "C04 v2 repo-month/file rows",
            "join_keys": ["snapshot_id == snapshot_key", "relative_path == component_path"],
            "npr_metric_preserved": EXPECTED_NPR_METRIC,
            "threshold": "not applied in C05; use frozen C04 threshold specification downstream",
            "quality_semantics": "unresolved Python-file SonarQube issue stock at historical snapshot",
            "zero_issue_policy": "left join from complete C04 file universe; absent B05 issue row means zero issue stock",
            "outside_c04_policy": "issue-bearing B05 Python file paths outside C04 are explicit scope exclusions and remain fully reconciled",
            "density": "not computed; file-level SonarQube NCLOC is required before density analysis",
        },
        "c04": {
            "script_version": c04_summary.get("script_version"),
            "status": c04_summary.get("status"),
            "hard_check_failures": c04_summary.get("hard_check_failures"),
            "primary_threshold_provenance_only": c04_primary,
            "rows": len(c04),
            "unique_snapshot_files": len(c04_unique),
            "finite_combined_rows": int(finite_combined.sum()),
        },
        "b05": {
            "raw_issue_rows": len(raw),
            "issue_bearing_snapshot_files": issue_file_count,
            "joined_issue_bearing_snapshot_files": joined_issue_file_count,
            "outside_c04_issue_bearing_files": len(outside),
            "outside_c04_issue_rows": outside_sums["sonar_issue_total"],
            "outside_c04_affected_snapshots": outside_snapshots,
            "sha256": observed_b05_hashes,
        },
        "output": {
            "repo_month_file_rows_with_any_issue": with_issue,
            "repo_month_file_rows_with_zero_issues": zero_issue,
            "snapshot_audit_mismatch_rows": snapshot_mismatches,
        },
        "hard_check_failures": hard_failures,
        "hard_check_failure_names": [c.check for c in failed],
        "inputs": {k: str(v) for k, v in paths.items()},
        "input_sha256": {k: sha256_file(v) for k, v in paths.items()},
        "outputs": {
            "file_quality_burden": str(output_file),
            "snapshot_audit": str(audit_file),
            "outside_c04_scope_exclusions": str(outside_file),
            "checks": str(checks_file),
            "summary_csv": str(summary_csv),
            "summary_json": str(summary_json),
            "metadata": str(metadata_file),
        },
    }
    summary_json.write_text(json.dumps(summary_obj, indent=2, sort_keys=True) + "\n")

    metadata = {
        "script_version": SCRIPT_VERSION,
        "status": status,
        "created_utc": completed.isoformat(),
        "inputs": {k: {"path": str(v), "sha256": sha256_file(v)} for k, v in paths.items()},
        "method": summary_obj["methodology"],
        "diagnostics": {
            "hard_qc_failures": hard_failures,
            "c04_repo_month_file_rows": len(c04),
            "c04_unique_snapshot_files": len(c04_unique),
            "c04_finite_fun_cfun_rows": int(finite_combined.sum()),
            "raw_issue_rows": len(raw),
            "issue_bearing_snapshot_files": issue_file_count,
            "issue_bearing_snapshot_files_seen_in_c04": joined_issue_file_count,
            "outside_c04_issue_bearing_snapshot_files": len(outside),
            "outside_c04_issue_rows": outside_sums["sonar_issue_total"],
            "outside_c04_affected_snapshots": outside_snapshots,
            "repo_month_file_rows_with_any_issue": with_issue,
            "repo_month_file_rows_with_zero_issues": zero_issue,
            "repositories": structural["repositories"],
            "repo_months": structural["repo_months"],
        },
    }
    metadata_file.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    print("=" * 80)
    print("run-x-c05 C04 FUN+C_FUN-NPR x file-level SonarQube burden join")
    print(f"Status:                              {status}")
    print(f"C04 repo-month/file rows:            {len(c04)}")
    print(f"C04 unique snapshot/files:           {len(c04_unique)}")
    print(f"C04 finite FUN+C_FUN NPR rows:       {int(finite_combined.sum())}")
    print(f"B05 snapshots:                       {structural['snapshots']}")
    print(f"B05 raw issue rows:                  {len(raw)}")
    print(f"Issue-bearing snapshot/files:        {issue_file_count}")
    print(f"Issue-bearing files joined to C04:   {joined_issue_file_count}")
    print(f"Issue-bearing files outside C04:     {len(outside)}")
    print(f"Issue rows outside C04:              {outside_sums['sonar_issue_total']}")
    print(f"Repo-month/file rows with issues:    {with_issue}")
    print(f"Repo-month/file rows with zero issue:{zero_issue}")
    print(f"Repositories / repo-months:          {structural['repositories']} / {structural['repo_months']}")
    print(f"Hard QC failures:                    {hard_failures}")
    print(f"Joined output:                       {output_file}")
    print(f"Snapshot audit:                      {audit_file}")
    print(f"Outside-C04 scope exclusions:        {outside_file}")
    print(f"QC checks:                           {checks_file}")
    print(f"Summary:                             {summary_csv}")
    print("Density:                             intentionally deferred; file-level NCLOC required")
    print("Thresholds:                          not applied; frozen C04 grid remains downstream")
    print("=" * 80)

    if args.strict_expected_counts and hard_failures:
        print("ERROR: hard QC failures detected:", file=sys.stderr)
        for c in failed:
            print(f"  - {c.check}: observed={c.observed!r}, expected={c.expected!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
