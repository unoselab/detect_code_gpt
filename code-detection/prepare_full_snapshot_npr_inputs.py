#!/usr/bin/env python3
"""Prepare full historical snapshot NPR inputs by reusing the validated A01 extractor.

This A05 production driver reads the frozen Model C snapshot manifest, materializes
one historical Git snapshot at a time as a detached temporary worktree, invokes
the already-validated A01 raw-source extractor for that one snapshot, promotes
content-addressed code-unit artifacts into a persistent shared store, and then
removes the temporary worktree.

The driver is intentionally orchestration-only. It does not reimplement A01 AST
extraction, source slicing, docstring handling, code-unit classification, token
counting, NPR scoring, or AGC/HWC classification.

Persistent outputs are compatible with downstream A02 by preserving the A01
filenames:
  python_snapshot_manifest.csv
  python_file_manifest.csv
  python_code_unit_manifest.csv
  code_units/<sha-prefix>/<sha256>.txt

Resume behavior is snapshot-granular. Per-snapshot A01 manifests and QC records
are retained under snapshot_chunks/, while full source trees are never retained.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


IMPLEMENTATION_VERSION = "v1"
RUN_NAME = "run-x-a05"
EXPECTED_DATASET_SOURCES = {"treatment", "control"}
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
REGULAR_GIT_MODES = {"100644", "100755"}
SYMLINK_GIT_MODE = "120000"

REQUIRED_MANIFEST_COLUMNS = {
    "dataset_source",
    "repo_name",
    "latest_commit_effective",
    "repo_month_rows",
    "first_panel_month",
    "last_panel_month",
    "clone_path",
    "python_file_count_all",
}

STATUS_COLUMNS = [
    "manifest_order",
    "snapshot_key",
    "dataset_source",
    "repo_name",
    "repo_key",
    "commit_sha",
    "clone_path",
    "repo_month_rows",
    "first_panel_month",
    "last_panel_month",
    "status",
    "a01_status",
    "attempt",
    "started_at",
    "completed_at",
    "runtime_seconds",
    "git_precheck_status",
    "python_file_count_manifest",
    "python_file_count_git_regular",
    "python_file_count_matches_manifest",
    "python_symlink_count_git",
    "python_files_discovered",
    "python_files_prepared",
    "python_files_excluded",
    "primary_code_units",
    "diagnostic_overlap_units",
    "space_by_tokens_primary",
    "artifact_files_promoted",
    "artifact_files_reused",
    "chunk_dir",
    "temporary_worktree_path",
    "a01_return_code",
    "error_stage",
    "error_message",
]

UNRESOLVED_COLUMNS = [
    "manifest_order",
    "snapshot_key",
    "dataset_source",
    "repo_name",
    "commit_sha",
    "stage",
    "error_type",
    "error_message",
]

CHECK_COLUMNS = [
    "check_name",
    "severity",
    "passed",
    "observed",
    "expected",
    "note",
]


@dataclass(frozen=True)
class SnapshotTarget:
    manifest_order: int
    snapshot_key: str
    dataset_source: str
    repo_name: str
    repo_key: str
    commit_sha: str
    clone_path: Path
    repo_month_rows: int
    first_panel_month: str
    last_panel_month: str
    python_file_count_manifest: int
    raw_row: dict[str, str]


@dataclass
class GitPythonInventory:
    regular_count: int = 0
    symlink_count: int = 0
    other_count: int = 0


@dataclass
class PromotionCounts:
    promoted: int = 0
    reused: int = 0


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def sanitize_key(value: str, max_length: int = 120) -> str:
    """Match the stable snapshot-key sanitization used by the quality pipeline."""
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value).strip())
    cleaned = cleaned.strip("_.:-") or "unknown"
    return cleaned[:max_length]


def make_snapshot_key(dataset_source: str, repo_name: str, commit_sha: str) -> str:
    """Build the same stable repository-snapshot identifier used in Model C scans."""
    raw = f"{dataset_source}|{repo_name.lower()}|{commit_sha.lower()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return (
        f"{sanitize_key(dataset_source, 16)}__"
        f"{sanitize_key(repo_name, 70)}__{commit_sha[:12].lower()}__{digest}"
    )


def make_worktree_container_name(manifest_order: int, snapshot_key: str) -> str:
    digest = hashlib.sha256(snapshot_key.encode("utf-8")).hexdigest()[:20]
    return f"snapshot_{manifest_order:04d}_{digest}"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [
            {str(key): str(value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(stream)
        ]


def write_csv_atomic(rows: Iterable[dict[str, Any]], columns: Sequence[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    temp.replace(path)


def write_json_atomic(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    temp.replace(path)


def copy_file_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copy2(source, temp)
    temp.replace(destination)


def parse_positive_int(value: str, label: str) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer; got {value!r}") from exc
    if parsed <= 0:
        raise ValueError(f"{label} must be positive; got {parsed}")
    return parsed


def parse_nonnegative_int(value: str, label: str) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer; got {value!r}") from exc
    if parsed < 0:
        raise ValueError(f"{label} must be non-negative; got {parsed}")
    return parsed


def run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    logging.debug("Running command: %s", " ".join(command))
    return subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=check,
        timeout=timeout,
    )


def normalize_manifest(path: Path) -> list[SnapshotTarget]:
    rows = read_csv(path)
    if not rows:
        raise ValueError(f"Input snapshot manifest is empty: {path}")
    missing = REQUIRED_MANIFEST_COLUMNS - set(rows[0])
    if missing:
        raise ValueError(f"Input manifest is missing required columns: {sorted(missing)}")

    targets: list[SnapshotTarget] = []
    seen: set[tuple[str, str, str]] = set()
    for order, row in enumerate(rows, start=1):
        source = row["dataset_source"].strip().lower()
        if source not in EXPECTED_DATASET_SOURCES:
            raise ValueError(f"Unexpected dataset_source at row {order}: {source!r}")
        repo_name = row["repo_name"].strip()
        if not repo_name or "/" not in repo_name:
            raise ValueError(f"Invalid repo_name at row {order}: {repo_name!r}")
        commit = row["latest_commit_effective"].strip().lower()
        if not FULL_SHA_RE.fullmatch(commit):
            raise ValueError(f"Invalid commit SHA at row {order}: {commit!r}")
        clone_value = row["clone_path"].strip()
        if not clone_value:
            raise ValueError(f"Missing clone_path at row {order}: {repo_name}")
        clone_path = Path(clone_value).expanduser().resolve(strict=False)
        repo_month_rows = parse_positive_int(row["repo_month_rows"], "repo_month_rows")
        python_file_count = parse_positive_int(
            row["python_file_count_all"], "python_file_count_all"
        )
        key = (source, repo_name, commit)
        if key in seen:
            raise ValueError(f"Duplicate repository-snapshot key at row {order}: {key}")
        seen.add(key)
        repo_key = row.get("repo_key", "").strip() or repo_name.lower()
        targets.append(
            SnapshotTarget(
                manifest_order=order,
                snapshot_key=make_snapshot_key(source, repo_name, commit),
                dataset_source=source,
                repo_name=repo_name,
                repo_key=repo_key,
                commit_sha=commit,
                clone_path=clone_path,
                repo_month_rows=repo_month_rows,
                first_panel_month=row["first_panel_month"].strip(),
                last_panel_month=row["last_panel_month"].strip(),
                python_file_count_manifest=python_file_count,
                raw_row=row,
            )
        )
    if len({target.snapshot_key for target in targets}) != len(targets):
        raise ValueError("Generated snapshot_key values are not unique.")
    return targets


def add_check(
    rows: list[dict[str, Any]],
    name: str,
    severity: str,
    passed: bool,
    observed: Any,
    expected: Any,
    note: str = "",
) -> None:
    rows.append(
        {
            "check_name": name,
            "severity": severity,
            "passed": bool(passed),
            "observed": observed,
            "expected": expected,
            "note": note,
        }
    )


def validate_expected_counts(targets: Sequence[SnapshotTarget], args: argparse.Namespace) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    source_counts = Counter(target.dataset_source for target in targets)
    repo_month_counts = Counter()
    source_repos: dict[str, set[str]] = {"treatment": set(), "control": set()}
    for target in targets:
        repo_month_counts[target.dataset_source] += target.repo_month_rows
        source_repos[target.dataset_source].add(target.repo_name)

    expected = [
        ("input_snapshot_rows", len(targets), args.expected_snapshots),
        ("treatment_snapshots", source_counts["treatment"], args.expected_treatment_snapshots),
        ("control_snapshots", source_counts["control"], args.expected_control_snapshots),
        ("repo_month_coverage", sum(t.repo_month_rows for t in targets), args.expected_repo_month_rows),
        ("treatment_repo_month_coverage", repo_month_counts["treatment"], args.expected_treatment_repo_month_rows),
        ("control_repo_month_coverage", repo_month_counts["control"], args.expected_control_repo_month_rows),
        ("unique_repositories", len({t.repo_name for t in targets}), args.expected_repositories),
        ("treatment_repositories", len(source_repos["treatment"]), args.expected_treatment_repositories),
        ("control_repositories", len(source_repos["control"]), args.expected_control_repositories),
    ]
    failures: list[str] = []
    for name, observed, expected_value in expected:
        passed = int(observed) == int(expected_value)
        add_check(checks, name, "hard", passed, observed, expected_value)
        if not passed:
            failures.append(f"{name}: observed={observed}, expected={expected_value}")
    if args.strict_expected_counts and failures:
        raise ValueError("Strict input count validation failed: " + " | ".join(failures))
    return checks


def select_targets(targets: Sequence[SnapshotTarget], args: argparse.Namespace) -> list[SnapshotTarget]:
    selected = [target for target in targets if target.manifest_order >= args.start_order]
    if args.dataset_source:
        selected = [target for target in selected if target.dataset_source == args.dataset_source]
    if args.repo_name:
        selected = [target for target in selected if target.repo_name == args.repo_name]
    if args.limit > 0:
        selected = selected[: args.limit]
    return selected


def validate_git_snapshot(target: SnapshotTarget, timeout: int) -> tuple[bool, str]:
    if not target.clone_path.is_dir():
        return False, "clone_path_missing"
    try:
        run_command(
            ["git", "-C", str(target.clone_path), "rev-parse", "--git-dir"],
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False, "not_git_repository"
    try:
        run_command(
            [
                "git",
                "-C",
                str(target.clone_path),
                "cat-file",
                "-e",
                f"{target.commit_sha}^{{commit}}",
            ],
            timeout=timeout,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False, "commit_not_found"
    return True, "ready"


def git_python_inventory(target: SnapshotTarget, timeout: int) -> GitPythonInventory:
    process = run_command(
        ["git", "-C", str(target.clone_path), "ls-tree", "-r", "-z", target.commit_sha],
        timeout=timeout,
    )
    inventory = GitPythonInventory()
    for entry in process.stdout.split("\0"):
        if not entry:
            continue
        try:
            meta, path = entry.split("\t", 1)
            mode, object_type, _oid = meta.split(" ", 2)
        except ValueError as exc:
            raise RuntimeError(f"Cannot parse git ls-tree entry: {entry!r}") from exc
        if not path.lower().endswith(".py"):
            continue
        if object_type == "blob" and mode in REGULAR_GIT_MODES:
            inventory.regular_count += 1
        elif object_type == "blob" and mode == SYMLINK_GIT_MODE:
            inventory.symlink_count += 1
        else:
            inventory.other_count += 1
    return inventory


def remove_worktree(clone_path: Path, worktree_path: Path, timeout: int) -> None:
    try:
        run_command(
            ["git", "-C", str(clone_path), "worktree", "remove", "--force", str(worktree_path)],
            check=False,
            timeout=timeout,
        )
        run_command(
            ["git", "-C", str(clone_path), "worktree", "prune"],
            check=False,
            timeout=timeout,
        )
    finally:
        shutil.rmtree(worktree_path, ignore_errors=True)
        parent = worktree_path.parent
        try:
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass


def create_worktree(target: SnapshotTarget, worktree_path: Path, timeout: int) -> None:
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    if worktree_path.exists() or worktree_path.is_symlink():
        remove_worktree(target.clone_path, worktree_path, timeout)
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
    process = run_command(
        [
            "git",
            "-C",
            str(target.clone_path),
            "worktree",
            "add",
            "--detach",
            str(worktree_path),
            target.commit_sha,
        ],
        check=False,
        timeout=timeout,
    )
    if process.returncode != 0:
        raise RuntimeError(
            "git worktree add failed: "
            + (process.stderr.strip() or process.stdout.strip() or f"exit={process.returncode}")
        )


def write_snapshot_metadata(target: SnapshotTarget, worktree_path: Path) -> Path:
    metadata_path = worktree_path / ".snapshot_metadata.json"
    payload = {
        "snapshot_id": target.snapshot_key,
        "dataset_source": target.dataset_source,
        "repo_name": target.repo_name,
        "repo_key": target.repo_key,
        "snapshot_time": target.first_panel_month,
        "snapshot_commit": target.commit_sha,
        "latest_commit_effective": target.commit_sha,
        "repo_month_rows": target.repo_month_rows,
        "first_panel_month": target.first_panel_month,
        "last_panel_month": target.last_panel_month,
    }
    write_json_atomic(payload, metadata_path)
    return metadata_path


def run_a01_for_snapshot(
    target: SnapshotTarget,
    *,
    python_bin: Path,
    a01_script: Path,
    worktree_container: Path,
    chunk_dir: Path,
    progress_every_files: int,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(python_bin),
        str(a01_script),
        "--snapshot-root",
        str(worktree_container),
        "--output-dir",
        str(chunk_dir),
        "--qc-dir",
        str(chunk_dir / "qc"),
        "--expected-snapshots",
        "1",
        "--progress-every-files",
        str(progress_every_files),
        "--overwrite-output",
        "--require-complete-metadata",
    ]
    logging.debug("A01 command: %s", " ".join(command))
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def read_one_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        raw = json.load(stream)
    if not isinstance(raw, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return raw


def validate_chunk(target: SnapshotTarget, chunk_dir: Path) -> dict[str, Any]:
    required = [
        chunk_dir / "python_snapshot_manifest.csv",
        chunk_dir / "python_file_manifest.csv",
        chunk_dir / "python_code_unit_manifest.csv",
        chunk_dir / "qc" / "python_snapshot_input_checks.csv",
        chunk_dir / "qc" / "python_snapshot_input_exclusions.csv",
        chunk_dir / "qc" / "python_snapshot_input_summary.json",
        chunk_dir / "qc" / "python_snapshot_input_metadata.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("A01 chunk is missing expected files: " + ", ".join(missing))
    snapshot_rows = read_csv(chunk_dir / "python_snapshot_manifest.csv")
    if len(snapshot_rows) != 1:
        raise RuntimeError(f"Expected one A01 snapshot row, found {len(snapshot_rows)}")
    row = snapshot_rows[0]
    if row.get("snapshot_id", "") != target.snapshot_key:
        raise RuntimeError(
            f"A01 snapshot_id mismatch: {row.get('snapshot_id')} != {target.snapshot_key}"
        )
    if row.get("snapshot_commit", "").lower() != target.commit_sha:
        raise RuntimeError("A01 snapshot commit does not match the source manifest.")
    if row.get("repo_name", "") != target.repo_name:
        raise RuntimeError("A01 repository identity does not match the source manifest.")
    summary = read_one_json(chunk_dir / "qc" / "python_snapshot_input_summary.json")
    if int(summary.get("failed_checks", 0)) != 0:
        raise RuntimeError(f"A01 hard QC failed for {target.snapshot_key}: {summary}")
    if str(summary.get("status", "")) not in {"PASS", "PASS_WITH_EXCLUSIONS"}:
        raise RuntimeError(f"Unexpected A01 status: {summary.get('status')}")
    return summary


def promote_artifacts(chunk_dir: Path, output_dir: Path) -> PromotionCounts:
    counts = PromotionCounts()
    chunk_code_root = chunk_dir / "code_units"
    if not chunk_code_root.exists():
        return counts
    global_code_root = output_dir / "code_units"
    for source in chunk_code_root.rglob("*.txt"):
        relative = source.relative_to(chunk_dir)
        destination = output_dir / relative
        expected_sha = source.stem
        actual_sha = sha256_file(source)
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"Chunk artifact hash mismatch: {source} has {actual_sha}, expected {expected_sha}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if sha256_file(destination) != expected_sha:
                raise RuntimeError(f"Existing global artifact hash mismatch: {destination}")
            counts.reused += 1
            continue
        try:
            os.link(source, destination)
        except OSError:
            copy_file_atomic(source, destination)
        if sha256_file(destination) != expected_sha:
            raise RuntimeError(f"Promoted artifact failed hash verification: {destination}")
        counts.promoted += 1
    shutil.rmtree(chunk_code_root, ignore_errors=True)
    if global_code_root.exists():
        global_code_root.mkdir(parents=True, exist_ok=True)
    return counts


def default_status_row(target: SnapshotTarget, attempt: int) -> dict[str, Any]:
    return {
        "manifest_order": target.manifest_order,
        "snapshot_key": target.snapshot_key,
        "dataset_source": target.dataset_source,
        "repo_name": target.repo_name,
        "repo_key": target.repo_key,
        "commit_sha": target.commit_sha,
        "clone_path": str(target.clone_path),
        "repo_month_rows": target.repo_month_rows,
        "first_panel_month": target.first_panel_month,
        "last_panel_month": target.last_panel_month,
        "status": "pending",
        "a01_status": "",
        "attempt": attempt,
        "started_at": utc_now(),
        "completed_at": "",
        "runtime_seconds": "",
        "git_precheck_status": "pending",
        "python_file_count_manifest": target.python_file_count_manifest,
        "python_file_count_git_regular": "",
        "python_file_count_matches_manifest": "",
        "python_symlink_count_git": "",
        "python_files_discovered": "",
        "python_files_prepared": "",
        "python_files_excluded": "",
        "primary_code_units": "",
        "diagnostic_overlap_units": "",
        "space_by_tokens_primary": "",
        "artifact_files_promoted": "",
        "artifact_files_reused": "",
        "chunk_dir": "",
        "temporary_worktree_path": "",
        "a01_return_code": "",
        "error_stage": "",
        "error_message": "",
    }


def load_status_map(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file() or path.stat().st_size == 0:
        return {}
    rows = read_csv(path)
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get("snapshot_key", "")
        if not key:
            raise ValueError(f"Status file contains a row without snapshot_key: {path}")
        if key in result:
            raise ValueError(f"Duplicate snapshot_key in status file: {key}")
        result[key] = row
    return result


def save_status_map(status_map: dict[str, dict[str, Any]], path: Path) -> None:
    rows = sorted(
        status_map.values(),
        key=lambda row: int(str(row.get("manifest_order", "0") or "0")),
    )
    write_csv_atomic(rows, STATUS_COLUMNS, path)


def record_unresolved(
    unresolved: list[dict[str, Any]],
    target: SnapshotTarget,
    stage: str,
    exc: BaseException | str,
) -> None:
    if isinstance(exc, BaseException):
        error_type = type(exc).__name__
        message = str(exc)
    else:
        error_type = stage
        message = str(exc)
    unresolved.append(
        {
            "manifest_order": target.manifest_order,
            "snapshot_key": target.snapshot_key,
            "dataset_source": target.dataset_source,
            "repo_name": target.repo_name,
            "commit_sha": target.commit_sha,
            "stage": stage,
            "error_type": error_type,
            "error_message": message[:4000],
        }
    )


def check_free_space(path: Path, min_free_bytes: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(path).free
    if free < min_free_bytes:
        raise RuntimeError(
            f"Insufficient free space under {path}: free={free} bytes, required={min_free_bytes}"
        )


def patch_snapshot_order(rows: Iterator[dict[str, str]], order: int) -> Iterator[dict[str, str]]:
    for row in rows:
        row = dict(row)
        row["snapshot_order"] = str(order)
        yield row


def concatenate_chunk_csvs(
    successful_targets: Sequence[SnapshotTarget],
    chunk_root: Path,
    relative_input: Path,
    output_path: Path,
    *,
    patch_order: bool,
) -> tuple[int, list[str]]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_suffix(output_path.suffix + ".tmp")
    header: list[str] | None = None
    row_count = 0
    with temp.open("w", encoding="utf-8", newline="") as out_stream:
        writer: csv.DictWriter[str] | None = None
        for target in successful_targets:
            path = chunk_root / target.snapshot_key / relative_input
            with path.open("r", encoding="utf-8-sig", newline="") as in_stream:
                reader = csv.DictReader(in_stream)
                fields = list(reader.fieldnames or [])
                if header is None:
                    header = fields
                    writer = csv.DictWriter(out_stream, fieldnames=header, extrasaction="ignore")
                    writer.writeheader()
                elif fields != header:
                    raise RuntimeError(
                        f"Chunk CSV schema mismatch for {path}: {fields} != {header}"
                    )
                assert writer is not None
                iterable: Iterable[dict[str, str]] = reader
                if patch_order:
                    iterable = patch_snapshot_order(iter(iterable), target.manifest_order)
                for row in iterable:
                    writer.writerow(row)
                    row_count += 1
    if header is None:
        header = []
        with temp.open("w", encoding="utf-8", newline="") as stream:
            pass
    temp.replace(output_path)
    return row_count, header


def collect_global_exclusions(
    successful_targets: Sequence[SnapshotTarget], chunk_root: Path, output_path: Path
) -> int:
    return concatenate_chunk_csvs(
        successful_targets,
        chunk_root,
        Path("qc/python_snapshot_input_exclusions.csv"),
        output_path,
        patch_order=False,
    )[0]


def bool_from_csv(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def consolidate_outputs(
    targets: Sequence[SnapshotTarget],
    status_map: dict[str, dict[str, Any]],
    args: argparse.Namespace,
    input_checks: list[dict[str, Any]],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    successful_targets = [
        target
        for target in targets
        if str(status_map.get(target.snapshot_key, {}).get("status", "")) == "success"
        and (args.output_dir / "snapshot_chunks" / target.snapshot_key).is_dir()
    ]
    successful_targets.sort(key=lambda target: target.manifest_order)
    chunk_root = args.output_dir / "snapshot_chunks"

    snapshot_count, snapshot_header = concatenate_chunk_csvs(
        successful_targets,
        chunk_root,
        Path("python_snapshot_manifest.csv"),
        args.output_dir / "python_snapshot_manifest.csv",
        patch_order=True,
    )
    file_count, file_header = concatenate_chunk_csvs(
        successful_targets,
        chunk_root,
        Path("python_file_manifest.csv"),
        args.output_dir / "python_file_manifest.csv",
        patch_order=True,
    )
    code_count, code_header = concatenate_chunk_csvs(
        successful_targets,
        chunk_root,
        Path("python_code_unit_manifest.csv"),
        args.output_dir / "python_code_unit_manifest.csv",
        patch_order=True,
    )
    exclusion_count = collect_global_exclusions(
        successful_targets,
        chunk_root,
        args.qc_dir / "python_snapshot_input_exclusions.csv",
    )

    snapshot_rows = read_csv(args.output_dir / "python_snapshot_manifest.csv") if snapshot_count else []
    file_rows = read_csv(args.output_dir / "python_file_manifest.csv") if file_count else []

    # Stream the code-unit manifest to avoid retaining every code-unit row in memory.
    primary_units = 0
    diagnostic_units = 0
    function_bodies = 0
    method_bodies = 0
    module_blocks = 0
    class_blocks = 0
    unique_unit_ids: set[str] = set()
    duplicate_unit_ids = 0
    unique_artifact_hashes: set[str] = set()
    artifact_integrity_failures = 0
    if code_count:
        with (args.output_dir / "python_code_unit_manifest.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as stream:
            for row in csv.DictReader(stream):
                role = row.get("aggregation_role", "")
                if role == "primary":
                    primary_units += 1
                else:
                    diagnostic_units += 1
                unit_type = row.get("code_unit_type", "")
                function_bodies += unit_type == "function_body"
                method_bodies += unit_type == "method_body"
                module_blocks += unit_type == "module_block"
                class_blocks += unit_type == "class_block"
                unit_id = row.get("code_unit_id", "")
                if unit_id in unique_unit_ids:
                    duplicate_unit_ids += 1
                unique_unit_ids.add(unit_id)
                artifact_sha = row.get("code_unit_sha256", "")
                if artifact_sha and artifact_sha not in unique_artifact_hashes:
                    unique_artifact_hashes.add(artifact_sha)
                    relative = row.get("code_unit_relative_path", "")
                    artifact = args.output_dir / relative
                    if not artifact.is_file() or sha256_file(artifact) != artifact_sha:
                        artifact_integrity_failures += 1

    duplicate_snapshot_ids = len(snapshot_rows) - len(
        {row.get("snapshot_id", "") for row in snapshot_rows}
    )
    duplicate_file_keys = len(file_rows) - len(
        {(row.get("snapshot_id", ""), row.get("relative_path", "")) for row in file_rows}
    )
    prepared_files = sum(row.get("parse_status", "") == "prepared" for row in file_rows)
    excluded_files = len(file_rows) - prepared_files
    incomplete_metadata = sum(
        not bool_from_csv(row.get("metadata_complete", "")) for row in snapshot_rows
    )

    # A01 already audits interval overlap within every per-snapshot chunk. Sum the
    # chunk summaries instead of re-parsing all source intervals here.
    primary_overlap_count = 0
    for target in successful_targets:
        summary = read_one_json(
            chunk_root
            / target.snapshot_key
            / "qc"
            / "python_snapshot_input_summary.json"
        )
        primary_overlap_count += int(summary.get("primary_source_overlap_count", 0))

    a01_checks = list(input_checks)
    add_check(
        a01_checks,
        "successful_snapshot_rows_unique",
        "hard",
        duplicate_snapshot_ids == 0,
        duplicate_snapshot_ids,
        0,
    )
    add_check(
        a01_checks,
        "python_file_keys_unique",
        "hard",
        duplicate_file_keys == 0,
        duplicate_file_keys,
        0,
    )
    add_check(
        a01_checks,
        "code_unit_ids_unique",
        "hard",
        duplicate_unit_ids == 0,
        duplicate_unit_ids,
        0,
    )
    add_check(
        a01_checks,
        "python_file_reconciliation",
        "hard",
        file_count == prepared_files + excluded_files,
        file_count,
        prepared_files + excluded_files,
    )
    add_check(
        a01_checks,
        "primary_source_overlap_count",
        "hard",
        primary_overlap_count == 0,
        primary_overlap_count,
        0,
    )
    add_check(
        a01_checks,
        "artifact_sha256_integrity",
        "hard",
        artifact_integrity_failures == 0,
        artifact_integrity_failures,
        0,
    )
    add_check(
        a01_checks,
        "snapshot_metadata_complete",
        "hard",
        incomplete_metadata == 0,
        incomplete_metadata,
        0,
    )
    add_check(
        a01_checks,
        "consolidated_snapshot_rows_match_success_status",
        "hard",
        snapshot_count == len(successful_targets),
        snapshot_count,
        len(successful_targets),
    )

    write_csv_atomic(a01_checks, CHECK_COLUMNS, args.qc_dir / "python_snapshot_input_checks.csv")

    hard_failures = sum(
        row["severity"] == "hard" and not bool(row["passed"]) for row in a01_checks
    )
    warning_failures = sum(
        row["severity"] == "warning" and not bool(row["passed"]) for row in a01_checks
    )
    if hard_failures:
        status = "FAIL"
    elif exclusion_count:
        status = "PASS_WITH_EXCLUSIONS"
    else:
        status = "PASS"

    summary = {
        "implementation_version": IMPLEMENTATION_VERSION,
        "upstream_stage": "A01",
        "status": status,
        "snapshots_discovered": snapshot_count,
        "snapshots_with_complete_metadata": snapshot_count - incomplete_metadata,
        "snapshots_with_incomplete_metadata": incomplete_metadata,
        "python_files_discovered": file_count,
        "python_files_prepared": prepared_files,
        "python_files_excluded": excluded_files,
        "primary_code_units": primary_units,
        "diagnostic_overlap_units": diagnostic_units,
        "function_bodies": function_bodies,
        "method_bodies": method_bodies,
        "module_blocks": module_blocks,
        "class_blocks": class_blocks,
        "exclusion_records": exclusion_count,
        "failed_checks": hard_failures,
        "warning_checks": warning_failures,
        "primary_source_overlap_count": primary_overlap_count,
        "artifact_integrity_failures": artifact_integrity_failures,
        "unique_code_unit_artifacts": len(unique_artifact_hashes),
    }
    write_json_atomic(summary, args.qc_dir / "python_snapshot_input_summary.json")

    metadata = {
        "implementation_version": IMPLEMENTATION_VERSION,
        "driver_run_name": RUN_NAME,
        "python_version": sys.version,
        "python_executable": sys.executable,
        "input_snapshot_manifest": str(args.input_manifest_file.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "qc_dir": str(args.qc_dir.resolve()),
        "worktree_root": str(args.worktree_root.resolve()),
        "worktrees_persisted": False,
        "snapshot_id_policy": "quality_pipeline_snapshot_key",
        "upstream_a01_script": str(args.a01_script.resolve()),
        "upstream_a01_script_sha256": provenance["a01_script_sha256"],
        "source_manifest_sha256": provenance["input_manifest_sha256"],
        "materialization_policy": {
            "method": "detached_temporary_git_worktree_one_snapshot_at_a_time",
            "main_clone_checkout_modified": False,
            "temporary_worktree_removed_after_each_snapshot": True,
            "persistent_full_snapshot_trees": False,
            "persistent_content_addressed_code_units": True,
        },
        "source_policy": {
            "a01_reused_without_reimplementation": True,
            "ast_python_required": "3.12+",
            "raw_source_slicing": True,
            "space_by_token_definition": "text.split(' ')",
            "scoring_windows_created": False,
            "npr_computed": False,
            "agc_hwc_classification": False,
        },
        "consolidated_schema": {
            "python_snapshot_manifest_columns": snapshot_header,
            "python_file_manifest_columns": file_header,
            "python_code_unit_manifest_columns": code_header,
        },
    }
    write_json_atomic(metadata, args.qc_dir / "python_snapshot_input_metadata.json")
    return {
        "successful_targets": len(successful_targets),
        "snapshot_count": snapshot_count,
        "file_count": file_count,
        "code_count": code_count,
        "exclusion_count": exclusion_count,
        "primary_units": primary_units,
        "diagnostic_units": diagnostic_units,
        "unique_artifacts": len(unique_artifact_hashes),
        "artifact_failures": artifact_integrity_failures,
        "hard_failures": hard_failures,
        "status": status,
    }


def prepare_output_root(args: argparse.Namespace, provenance: dict[str, Any]) -> None:
    metadata_path = args.qc_dir / "python_full_snapshot_driver_metadata.json"
    fingerprint_path = args.output_dir / "provenance" / "preparation_fingerprint.json"
    if args.overwrite_output and args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.qc_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "snapshot_chunks").mkdir(parents=True, exist_ok=True)
    (args.output_dir / "code_units").mkdir(parents=True, exist_ok=True)
    provenance_dir = args.output_dir / "provenance"
    provenance_dir.mkdir(parents=True, exist_ok=True)

    if fingerprint_path.is_file():
        previous = read_one_json(fingerprint_path)
        previous_fingerprint = previous.get("preparation_fingerprint", "")
        if previous_fingerprint != provenance["preparation_fingerprint"]:
            raise RuntimeError(
                "Existing A05 output was created with a different preparation fingerprint. "
                "Use a new output directory or OVERWRITE_OUTPUT=1."
            )
    elif metadata_path.is_file():
        previous = read_one_json(metadata_path)
        previous_fingerprint = previous.get("preparation_fingerprint", "")
        if previous_fingerprint and previous_fingerprint != provenance["preparation_fingerprint"]:
            raise RuntimeError(
                "Existing A05 output was created with a different preparation fingerprint. "
                "Use a new output directory or OVERWRITE_OUTPUT=1."
            )

    frozen_manifest = provenance_dir / "velocity_did_model_c_snapshot_manifest.csv"
    if frozen_manifest.is_file():
        existing_sha = sha256_file(frozen_manifest)
        if existing_sha != provenance["input_manifest_sha256"]:
            raise RuntimeError(
                "Frozen source manifest differs from the current input manifest. "
                "Use OVERWRITE_OUTPUT=1 or a new output directory."
            )
    else:
        copy_file_atomic(args.input_manifest_file, frozen_manifest)
    (provenance_dir / "velocity_did_model_c_snapshot_manifest.sha256").write_text(
        provenance["input_manifest_sha256"] + "  velocity_did_model_c_snapshot_manifest.csv\n",
        encoding="ascii",
    )
    write_json_atomic(
        {
            "implementation_version": IMPLEMENTATION_VERSION,
            "input_manifest_sha256": provenance["input_manifest_sha256"],
            "a01_script_sha256": provenance["a01_script_sha256"],
            "preparation_fingerprint": provenance["preparation_fingerprint"],
        },
        fingerprint_path,
    )


def run_self_test() -> None:
    key1 = make_snapshot_key("control", "owner/repo", "a" * 40)
    key2 = make_snapshot_key("control", "owner/repo", "a" * 40)
    key3 = make_snapshot_key("treatment", "owner/repo", "a" * 40)
    assert key1 == key2
    assert key1 != key3
    assert key1.startswith("control__owner_repo__")
    assert sanitize_key("a/b c") == "a_b_c"
    assert parse_positive_int("14", "x") == 14
    assert parse_nonnegative_int("0", "x") == 0
    print("Self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare full historical NPR inputs using temporary Git worktrees and A01."
    )
    parser.add_argument("--input-manifest-file", required=True, type=Path)
    parser.add_argument("--a01-script", required=True, type=Path)
    parser.add_argument("--python-bin", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--qc-dir", required=True, type=Path)
    parser.add_argument("--worktree-root", required=True, type=Path)
    parser.add_argument("--status-output", required=True, type=Path)
    parser.add_argument("--unresolved-output", required=True, type=Path)
    parser.add_argument("--driver-checks-output", required=True, type=Path)
    parser.add_argument("--driver-summary-output", required=True, type=Path)
    parser.add_argument("--driver-metadata-output", required=True, type=Path)
    parser.add_argument("--git-timeout-seconds", type=int, default=300)
    parser.add_argument("--a01-timeout-seconds", type=int, default=3600)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--progress-every-files", type=int, default=500)
    parser.add_argument("--start-order", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dataset-source", choices=["treatment", "control"], default="")
    parser.add_argument("--repo-name", default="")
    parser.add_argument("--analysis-again", action="store_true")
    parser.add_argument("--overwrite-output", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-unresolved", action="store_true")
    parser.add_argument("--strict-expected-counts", action="store_true")
    parser.add_argument("--require-python-file-count-match", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--expected-input-sha256", default="")
    parser.add_argument("--min-free-gb", type=float, default=20.0)
    parser.add_argument("--expected-snapshots", type=int, default=1496)
    parser.add_argument("--expected-treatment-snapshots", type=int, default=790)
    parser.add_argument("--expected-control-snapshots", type=int, default=706)
    parser.add_argument("--expected-repo-month-rows", type=int, default=1954)
    parser.add_argument("--expected-treatment-repo-month-rows", type=int, default=914)
    parser.add_argument("--expected-control-repo-month-rows", type=int, default=1040)
    parser.add_argument("--expected-repositories", type=int, default=167)
    parser.add_argument("--expected-treatment-repositories", type=int, default=63)
    parser.add_argument("--expected-control-repositories", type=int, default=104)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def validate_runtime(args: argparse.Namespace) -> None:
    if sys.version_info < (3, 12):
        raise SystemExit(
            "ERROR: A05 invokes the A01 AST extractor and therefore requires Python 3.12+; "
            f"found {sys.version.split()[0]}."
        )
    if args.start_order < 1:
        raise ValueError("--start-order must be at least 1")
    if args.limit < 0:
        raise ValueError("--limit must be non-negative")
    for name in ("git_timeout_seconds", "a01_timeout_seconds", "progress_every", "progress_every_files"):
        if getattr(args, name) < 0:
            raise ValueError(f"--{name.replace('_', '-')} must be non-negative")
    if args.min_free_gb < 0:
        raise ValueError("--min-free-gb must be non-negative")
    if not args.input_manifest_file.is_file():
        raise FileNotFoundError(f"Input manifest not found: {args.input_manifest_file}")
    if not args.a01_script.is_file():
        raise FileNotFoundError(f"A01 implementation not found: {args.a01_script}")
    if not args.python_bin.is_file() or not os.access(args.python_bin, os.X_OK):
        raise FileNotFoundError(f"Python executable is missing or not executable: {args.python_bin}")
    if shutil.which("git") is None:
        raise RuntimeError("git is required but was not found in PATH")


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    if args.self_test:
        run_self_test()
        return 0

    validate_runtime(args)
    input_sha = sha256_file(args.input_manifest_file)
    a01_sha = sha256_file(args.a01_script)
    if args.expected_input_sha256 and input_sha != args.expected_input_sha256.lower():
        raise RuntimeError(
            f"Input manifest SHA256 mismatch: observed={input_sha}, "
            f"expected={args.expected_input_sha256.lower()}"
        )
    fingerprint_material = json.dumps(
        {
            "implementation_version": IMPLEMENTATION_VERSION,
            "input_manifest_sha256": input_sha,
            "a01_script_sha256": a01_sha,
            "materialization": "detached_git_worktree_one_at_a_time",
            "snapshot_id_policy": "quality_pipeline_snapshot_key",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    provenance = {
        "input_manifest_sha256": input_sha,
        "a01_script_sha256": a01_sha,
        "preparation_fingerprint": hashlib.sha256(fingerprint_material).hexdigest(),
    }

    targets = normalize_manifest(args.input_manifest_file)
    input_checks = validate_expected_counts(targets, args)
    selected = select_targets(targets, args)
    if not selected:
        raise RuntimeError("No snapshots were selected by the requested filters.")

    prepare_output_root(args, provenance)
    status_map = load_status_map(args.status_output)
    unresolved: list[dict[str, Any]] = []
    if args.unresolved_output.is_file() and args.unresolved_output.stat().st_size > 0:
        unresolved = read_csv(args.unresolved_output)

    logging.info(
        "Selected %d snapshots from %d manifest rows; start_order=%d; limit=%d; source=%s; repo=%s",
        len(selected),
        len(targets),
        args.start_order,
        args.limit,
        args.dataset_source or "<all>",
        args.repo_name or "<all>",
    )

    if args.dry_run:
        failures = 0
        for index, target in enumerate(selected, start=1):
            ready, status = validate_git_snapshot(target, args.git_timeout_seconds)
            if not ready:
                failures += 1
                logging.error(
                    "Dry-run failure %d/%d: order=%d %s at %s -> %s",
                    index,
                    len(selected),
                    target.manifest_order,
                    target.repo_name,
                    target.commit_sha[:12],
                    status,
                )
            elif args.progress_every and index % args.progress_every == 0:
                logging.info("Dry-run progress: %d/%d", index, len(selected))
        logging.info("Dry run complete: selected=%d; failures=%d", len(selected), failures)
        return 1 if failures else 0

    started_all = time.monotonic()
    processed_this_run = 0
    skipped_success = 0
    successful_this_run = 0
    failed_this_run = 0
    min_free_bytes = int(args.min_free_gb * 1024**3)

    for position, target in enumerate(selected, start=1):
        prior = status_map.get(target.snapshot_key)
        if (
            prior
            and prior.get("status") == "success"
            and not args.analysis_again
            and (args.output_dir / "snapshot_chunks" / target.snapshot_key).is_dir()
        ):
            skipped_success += 1
            if args.progress_every and position % args.progress_every == 0:
                logging.info(
                    "Progress: %d/%d selected; skipped_success=%d; new_success=%d; failed=%d",
                    position,
                    len(selected),
                    skipped_success,
                    successful_this_run,
                    failed_this_run,
                )
            continue

        processed_this_run += 1
        prior_attempt = 0
        if prior:
            try:
                prior_attempt = int(float(prior.get("attempt", "0") or "0"))
            except ValueError:
                prior_attempt = 0
        status_row = default_status_row(target, prior_attempt + 1)
        status_map[target.snapshot_key] = status_row
        save_status_map(status_map, args.status_output)

        chunk_dir = args.output_dir / "snapshot_chunks" / target.snapshot_key
        container_dir = args.worktree_root / make_worktree_container_name(
            target.manifest_order, target.snapshot_key
        )
        worktree_path = container_dir / "snapshot"
        status_row["chunk_dir"] = str(chunk_dir)
        status_row["temporary_worktree_path"] = str(worktree_path)
        snapshot_started = time.monotonic()
        stage = "git_precheck"

        logging.info(
            "Target %d/%d: order=%d %s %s at %s (%d repo-month rows)",
            position,
            len(selected),
            target.manifest_order,
            target.dataset_source,
            target.repo_name,
            target.commit_sha[:12],
            target.repo_month_rows,
        )

        try:
            ready, precheck_status = validate_git_snapshot(target, args.git_timeout_seconds)
            status_row["git_precheck_status"] = precheck_status
            if not ready:
                raise RuntimeError(precheck_status)

            stage = "git_python_inventory"
            inventory = git_python_inventory(target, args.git_timeout_seconds)
            status_row["python_file_count_git_regular"] = inventory.regular_count
            status_row["python_symlink_count_git"] = inventory.symlink_count
            count_matches = inventory.regular_count == target.python_file_count_manifest
            status_row["python_file_count_matches_manifest"] = count_matches
            if inventory.symlink_count:
                raise RuntimeError(
                    f"Tracked .py symlinks detected ({inventory.symlink_count}); refusing to let A01 follow them."
                )
            if inventory.other_count:
                raise RuntimeError(
                    f"Unexpected non-regular tracked .py objects detected ({inventory.other_count})."
                )
            if args.require_python_file_count_match and not count_matches:
                raise RuntimeError(
                    "Git regular Python file count does not match the frozen manifest: "
                    f"git={inventory.regular_count}, manifest={target.python_file_count_manifest}"
                )

            stage = "free_space_check"
            check_free_space(args.worktree_root, min_free_bytes)

            stage = "worktree_create"
            create_worktree(target, worktree_path, args.git_timeout_seconds)
            metadata_path = write_snapshot_metadata(target, worktree_path)

            stage = "a01_extract"
            process = run_a01_for_snapshot(
                target,
                python_bin=args.python_bin,
                a01_script=args.a01_script,
                worktree_container=container_dir,
                chunk_dir=chunk_dir,
                progress_every_files=args.progress_every_files,
                timeout=args.a01_timeout_seconds,
            )
            status_row["a01_return_code"] = process.returncode
            if process.stdout:
                logging.debug("A01 stdout for %s:\n%s", target.snapshot_key, process.stdout.rstrip())
            if process.stderr:
                logging.debug("A01 stderr for %s:\n%s", target.snapshot_key, process.stderr.rstrip())
            if process.returncode != 0:
                tail = (process.stderr or process.stdout or "").strip()[-4000:]
                raise RuntimeError(f"A01 exited with code {process.returncode}: {tail}")

            stage = "a01_validate"
            summary = validate_chunk(target, chunk_dir)
            status_row["a01_status"] = str(summary.get("status", ""))
            status_row["python_files_discovered"] = int(summary.get("python_files_discovered", 0))
            status_row["python_files_prepared"] = int(summary.get("python_files_prepared", 0))
            status_row["python_files_excluded"] = int(summary.get("python_files_excluded", 0))
            status_row["primary_code_units"] = int(summary.get("primary_code_units", 0))
            status_row["diagnostic_overlap_units"] = int(summary.get("diagnostic_overlap_units", 0))
            snapshot_manifest_row = read_csv(chunk_dir / "python_snapshot_manifest.csv")[0]
            status_row["space_by_tokens_primary"] = snapshot_manifest_row.get(
                "space_by_tokens_primary", ""
            )

            stage = "artifact_promote"
            promotion = promote_artifacts(chunk_dir, args.output_dir)
            status_row["artifact_files_promoted"] = promotion.promoted
            status_row["artifact_files_reused"] = promotion.reused
            status_row["status"] = "success"
            successful_this_run += 1
            logging.info(
                "Success: order=%d %s at %s -> files=%s; primary_units=%s; "
                "space_by_tokens=%s; artifacts_new=%d; artifacts_reused=%d; a01_status=%s",
                target.manifest_order,
                target.repo_name,
                target.commit_sha[:12],
                status_row["python_files_discovered"],
                status_row["primary_code_units"],
                status_row["space_by_tokens_primary"],
                promotion.promoted,
                promotion.reused,
                status_row["a01_status"],
            )
            try:
                metadata_path.unlink(missing_ok=True)
            except OSError:
                pass
        except KeyboardInterrupt:
            status_row["status"] = "interrupted"
            status_row["error_stage"] = stage
            status_row["error_message"] = "KeyboardInterrupt"
            raise
        except Exception as exc:
            failed_this_run += 1
            status_row["status"] = "failed"
            status_row["error_stage"] = stage
            status_row["error_message"] = f"{type(exc).__name__}: {exc}"[:4000]
            record_unresolved(unresolved, target, stage, exc)
            logging.error(
                "Failure: order=%d %s at %s stage=%s: %s",
                target.manifest_order,
                target.repo_name,
                target.commit_sha[:12],
                stage,
                exc,
            )
        finally:
            try:
                if worktree_path.exists() or container_dir.exists():
                    remove_worktree(target.clone_path, worktree_path, args.git_timeout_seconds)
                    shutil.rmtree(container_dir, ignore_errors=True)
            except Exception as cleanup_exc:
                logging.error(
                    "Worktree cleanup warning for %s: %s", target.snapshot_key, cleanup_exc
                )
                if status_row["status"] == "success":
                    status_row["status"] = "failed"
                    status_row["error_stage"] = "worktree_cleanup"
                    status_row["error_message"] = f"{type(cleanup_exc).__name__}: {cleanup_exc}"[:4000]
                    successful_this_run -= 1
                    failed_this_run += 1
                    record_unresolved(unresolved, target, "worktree_cleanup", cleanup_exc)
            status_row["completed_at"] = utc_now()
            status_row["runtime_seconds"] = round(time.monotonic() - snapshot_started, 3)
            save_status_map(status_map, args.status_output)
            write_csv_atomic(unresolved, UNRESOLVED_COLUMNS, args.unresolved_output)

        if args.progress_every and position % args.progress_every == 0:
            elapsed = max(time.monotonic() - started_all, 0.001)
            rate = processed_this_run / elapsed * 3600.0
            remaining_to_process = max(
                0, len(selected) - position
            )
            eta_hours = remaining_to_process / rate if rate > 0 else float("inf")
            logging.info(
                "Progress: %d/%d selected; processed=%d; skipped_success=%d; success=%d; "
                "failed=%d; rate_snapshots_per_hour=%.2f; eta_hours=%.2f",
                position,
                len(selected),
                processed_this_run,
                skipped_success,
                successful_this_run,
                failed_this_run,
                rate,
                eta_hours,
            )

    # Remove resolved rows from unresolved output and keep only the current state.
    current_failed_keys = {
        key for key, row in status_map.items() if str(row.get("status", "")) == "failed"
    }
    unresolved = [row for row in unresolved if row.get("snapshot_key", "") in current_failed_keys]
    # Deduplicate unresolved rows by snapshot, keeping the most recent record.
    dedup_unresolved: dict[str, dict[str, Any]] = {}
    for row in unresolved:
        dedup_unresolved[row.get("snapshot_key", "")] = row
    unresolved = [
        dedup_unresolved[key]
        for key in sorted(
            dedup_unresolved,
            key=lambda key: int(dedup_unresolved[key].get("manifest_order", 0) or 0),
        )
    ]
    write_csv_atomic(unresolved, UNRESOLVED_COLUMNS, args.unresolved_output)

    consolidation = consolidate_outputs(targets, status_map, args, input_checks, provenance)
    all_success_count = sum(
        1 for target in targets if str(status_map.get(target.snapshot_key, {}).get("status", "")) == "success"
    )
    full_run_requested = (
        args.start_order == 1
        and args.limit == 0
        and not args.dataset_source
        and not args.repo_name
    )
    current_unresolved = len(unresolved)

    driver_checks = list(input_checks)
    add_check(
        driver_checks,
        "source_manifest_sha256",
        "hard",
        not args.expected_input_sha256 or input_sha == args.expected_input_sha256.lower(),
        input_sha,
        args.expected_input_sha256.lower() if args.expected_input_sha256 else "not_enforced",
    )
    add_check(
        driver_checks,
        "temporary_worktree_root_empty_after_run",
        "hard",
        not args.worktree_root.exists() or not any(args.worktree_root.iterdir()),
        "empty" if (not args.worktree_root.exists() or not any(args.worktree_root.iterdir())) else "nonempty",
        "empty",
    )
    add_check(
        driver_checks,
        "full_manifest_success_coverage",
        "hard" if (full_run_requested and args.fail_on_unresolved) else "warning",
        all_success_count == len(targets),
        all_success_count,
        len(targets),
        "Hard only when no START_ORDER/LIMIT/source/repository filter is active.",
    )
    add_check(
        driver_checks,
        "current_unresolved_snapshots",
        "hard" if args.fail_on_unresolved else "warning",
        current_unresolved == 0,
        current_unresolved,
        0,
    )
    add_check(
        driver_checks,
        "consolidated_a01_hard_failures",
        "hard",
        consolidation["hard_failures"] == 0,
        consolidation["hard_failures"],
        0,
    )
    write_csv_atomic(driver_checks, CHECK_COLUMNS, args.driver_checks_output)

    driver_hard_failures = sum(
        row["severity"] == "hard" and not bool(row["passed"]) for row in driver_checks
    )
    driver_warning_failures = sum(
        row["severity"] == "warning" and not bool(row["passed"]) for row in driver_checks
    )
    if driver_hard_failures:
        driver_status = "FAIL"
    elif current_unresolved:
        driver_status = "PASS_WITH_UNRESOLVED"
    elif consolidation["exclusion_count"]:
        driver_status = "PASS_WITH_EXCLUSIONS"
    elif not full_run_requested:
        driver_status = "PASS_PARTIAL_SELECTION"
    else:
        driver_status = "PASS"

    driver_summary = {
        "implementation_version": IMPLEMENTATION_VERSION,
        "status": driver_status,
        "manifest_snapshots": len(targets),
        "selected_snapshots": len(selected),
        "successful_snapshots_total": all_success_count,
        "successful_this_run": successful_this_run,
        "processed_this_run": processed_this_run,
        "skipped_existing_success": skipped_success,
        "failed_this_run": failed_this_run,
        "current_unresolved_snapshots": current_unresolved,
        "full_run_requested": full_run_requested,
        "consolidated_snapshots": consolidation["snapshot_count"],
        "consolidated_python_files": consolidation["file_count"],
        "consolidated_code_units": consolidation["code_count"],
        "consolidated_primary_code_units": consolidation["primary_units"],
        "consolidated_diagnostic_overlap_units": consolidation["diagnostic_units"],
        "unique_code_unit_artifacts": consolidation["unique_artifacts"],
        "a01_exclusion_records": consolidation["exclusion_count"],
        "driver_hard_check_failures": driver_hard_failures,
        "driver_warning_check_failures": driver_warning_failures,
        "elapsed_seconds": round(time.monotonic() - started_all, 3),
    }
    write_json_atomic(driver_summary, args.driver_summary_output)

    driver_metadata = {
        "implementation_version": IMPLEMENTATION_VERSION,
        "run_name": RUN_NAME,
        "python_version": sys.version,
        "python_executable": sys.executable,
        "input_manifest_file": str(args.input_manifest_file.resolve()),
        "input_manifest_sha256": input_sha,
        "expected_input_sha256": args.expected_input_sha256,
        "a01_script": str(args.a01_script.resolve()),
        "a01_script_sha256": a01_sha,
        "preparation_fingerprint": provenance["preparation_fingerprint"],
        "output_dir": str(args.output_dir.resolve()),
        "worktree_root": str(args.worktree_root.resolve()),
        "worktrees_persisted": False,
        "git_materialization": "detached temporary worktree, one snapshot at a time",
        "resume_unit": "repository snapshot",
        "snapshot_id_policy": "quality_pipeline_snapshot_key",
        "filters": {
            "start_order": args.start_order,
            "limit": args.limit,
            "dataset_source": args.dataset_source,
            "repo_name": args.repo_name,
        },
        "safety": {
            "tracked_python_symlinks_followed": False,
            "tracked_python_symlink_policy": "fail_snapshot_for_manual_review",
            "minimum_free_gb": args.min_free_gb,
            "require_python_file_count_match": args.require_python_file_count_match,
        },
    }
    write_json_atomic(driver_metadata, args.driver_metadata_output)

    logging.info(
        "Completed A05: status=%s; manifest=%d; success_total=%d; selected=%d; "
        "processed=%d; skipped=%d; unresolved=%d; consolidated_files=%d; "
        "primary_units=%d; unique_artifacts=%d; hard_failures=%d",
        driver_status,
        len(targets),
        all_success_count,
        len(selected),
        processed_this_run,
        skipped_success,
        current_unresolved,
        consolidation["file_count"],
        consolidation["primary_units"],
        consolidation["unique_artifacts"],
        driver_hard_failures,
    )

    if driver_hard_failures:
        return 1
    if args.fail_on_unresolved and current_unresolved:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
