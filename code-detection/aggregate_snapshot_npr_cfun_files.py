#!/usr/bin/env python3
"""Aggregate finalized C_FUN NPR scores to historical Python files and repo-month/file rows.

A15 consumes finalized A14 new-C_FUN scores plus A13-directed A11 reuse and expands the
content-deduplicated class-method measurements back to every primary
``method_body`` occurrence in the A05 historical snapshot manifest.

Scientific scope
----------------
- This stage is C_FUN-only. It does not aggregate regular functions (FUN) or blocks.
- A14 new-C_FUN scores plus A13-directed A11 reuse are expanded to A05 occurrences before file aggregation.
- File-level NPR is therefore based only on class-method bodies present in
  that exact historical Python file.
- Files with no class methods have no C_FUN coverage; their C_FUN NPR is left
  missing rather than set to zero.
- Expected reused A11 exclusions and any A14 exclusions remain exclusions. No truncation, re-windowing,
  epsilon denominator correction, or synthetic NPR is introduced here.
- Both ratio-weighted NPR and pooled-component NPR are preserved.
- Repo-month expansion uses the authoritative Model A repo-month panel. A15
  never infers the month mapping from first/last snapshot-month summaries.

The large A05 code-unit manifest is streamed rather than loaded into pandas so
this stage remains practical for the ~3.65 million occurrence rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping


SCRIPT_VERSION = "run-x-a15-v1"
PRIMARY_ROLE = "primary"
CFUN_CODE_UNIT_TYPE = "method_body"
EXPECTED_A05_CODE_MANIFEST_SHA256 = (
    "1acb3726f5c62e6154672f1aff592973c65a13e58dbfd37f8058560d1a474e6c"
)
EXPECTED_A11_SCRIPT_VERSION = "run-x-a11-v3"
EXPECTED_A13_SCRIPT_VERSION = "run-x-a13-v1"
EXPECTED_A14_SCRIPT_VERSION = "run-x-a14-v1"
EXPECTED_A09_CONFIG_FINGERPRINT = (
    "3f78c8c43aaa014cd0f5e1a5d1c2df7d4269deb55c4c999e4483d08a324dd9bb"
)
EXPECTED_A02_CONFIG_FINGERPRINT = (
    "78655715edc8699710a27f593cac5a8360067e803eac8c50a0765084edfa5fb2"
)
EXPECTED_MODEL_REVISION = "bb9afde76d7945da5745592525db122d4d729eb1"
EXPECTED_CFUN_UNIQUE_MEMBERSHIPS = 195193
EXPECTED_CFUN_WINDOWS = 567557
EXPECTED_A14_NEW_UNIQUE_UNITS = 195190
EXPECTED_A14_NEW_WINDOWS = 567554
EXPECTED_A11_REUSE_FINITE_UNITS = 2
EXPECTED_A11_REUSE_PARTIAL_UNITS = 0
EXPECTED_A11_REUSE_EXCLUDED_UNITS = 1
EXPECTED_EXCLUSION_CLASSES = {
    "model_context_exceeded",
    "zero_original_log_rank",
    "insufficient_llm_tokens_for_npr",
}

A05_SNAPSHOT_REQUIRED = {
    "snapshot_order",
    "snapshot_id",
    "dataset_source",
    "repo_name",
    "repo_key",
    "snapshot_time",
    "snapshot_commit",
    "repo_month_rows",
}
A05_FILE_REQUIRED = {
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
}
A05_CODE_REQUIRED = {
    "snapshot_id",
    "relative_path",
    "file_sha256",
    "code_unit_id",
    "code_unit_type",
    "aggregation_role",
    "code_unit_sha256",
    "space_by_token_count",
}
UNIQUE_SCORE_REQUIRED = {
    "code_unit_sha256",
    "code_unit_types",
    "unit_groups",
    "space_by_tokens_total",
    "space_by_tokens_scored",
    "npr_coverage_ratio",
    "code_unit_npr_space_by_token_weighted",
    "code_unit_original_log_rank_weighted",
    "code_unit_mean_perturbed_log_rank_weighted",
    "code_unit_npr_pooled_components",
    "partial_code_unit_score",
    "status",
    "a09_config_fingerprint",
    "a02_config_fingerprint",
}
EXCLUSION_REQUIRED = {
    "gpu_index",
    "code_unit_sha256",
    "unit_groups",
    "exclusion_class",
}
A13_UNIT_REQUIRED = {
    "code_unit_sha256",
    "logical_shard",
    "code_unit_types",
    "unit_groups",
    "space_by_token_count",
    "expected_windows",
    "cfun_membership",
    "fun_membership",
    "a11_reuse_class",
    "a11_gpu_index",
    "a14_scoring_required",
    "a14_gpu_index",
}

PANEL_REQUIRED = {
    "repo_name",
    "dataset_source",
    "time",
    "latest_commit_effective",
}

FILE_OUTPUT_COLUMNS = [
    "snapshot_order",
    "snapshot_id",
    "dataset_source",
    "repo_name",
    "repo_key",
    "snapshot_time",
    "snapshot_commit",
    "relative_path",
    "file_sha256",
    "python_lines",
    "parse_status",
    "cfun_occurrences_total",
    "cfun_occurrences_scored",
    "cfun_occurrences_excluded",
    "cfun_occurrences_missing",
    "cfun_unique_sha_total",
    "cfun_unique_sha_scored",
    "cfun_unique_sha_excluded",
    "cfun_space_by_tokens_total",
    "cfun_space_by_tokens_scored",
    "cfun_space_by_tokens_excluded",
    "cfun_npr_coverage_ratio",
    "file_npr_cfun_space_by_token_weighted",
    "file_cfun_original_log_rank_space_by_token_weighted",
    "file_cfun_mean_perturbed_log_rank_space_by_token_weighted",
    "file_npr_cfun_pooled_components",
    "cfun_expected_exclusion_classes",
    "file_npr_cfun_status",
]

REPO_MONTH_OUTPUT_COLUMNS = [
    "repo_id",
    "dataset_source",
    "repo_name",
    "repo_month",
    "time_index",
    "event",
    "event_index",
    "snapshot_id",
    "snapshot_commit",
    "relative_path",
    "file_sha256",
    "python_lines",
    "parse_status",
    "cfun_occurrences_total",
    "cfun_occurrences_scored",
    "cfun_occurrences_excluded",
    "cfun_occurrences_missing",
    "cfun_unique_sha_total",
    "cfun_unique_sha_scored",
    "cfun_unique_sha_excluded",
    "cfun_space_by_tokens_total",
    "cfun_space_by_tokens_scored",
    "cfun_space_by_tokens_excluded",
    "cfun_npr_coverage_ratio",
    "file_npr_cfun_space_by_token_weighted",
    "file_cfun_original_log_rank_space_by_token_weighted",
    "file_cfun_mean_perturbed_log_rank_space_by_token_weighted",
    "file_npr_cfun_pooled_components",
    "cfun_expected_exclusion_classes",
    "file_npr_cfun_status",
]

EXCLUSION_OCCURRENCE_COLUMNS = [
    "snapshot_id",
    "dataset_source",
    "repo_name",
    "relative_path",
    "file_sha256",
    "code_unit_id",
    "code_unit_sha256",
    "space_by_token_count",
    "exclusion_classes",
    "exclusion_sources",
    "source_gpu_indexes",
]

A11_REUSE_OCCURRENCE_COLUMNS = [
    "snapshot_id",
    "dataset_source",
    "repo_name",
    "relative_path",
    "file_sha256",
    "code_unit_id",
    "code_unit_sha256",
    "space_by_token_count",
    "a11_reuse_class",
    "a11_gpu_index",
]

CHECK_COLUMNS = ["check_name", "severity", "passed", "observed", "expected", "note"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_int(value: Any, label: str) -> int:
    text = clean(value)
    if text == "":
        raise ValueError(f"Missing integer value for {label}")
    parsed = int(text)
    if parsed < 0:
        raise ValueError(f"Negative integer value for {label}: {parsed}")
    return parsed


def parse_float(value: Any, label: str) -> float:
    parsed = float(clean(value))
    if not math.isfinite(parsed):
        raise ValueError(f"Non-finite value for {label}: {value!r}")
    return parsed


def parse_boolish(value: Any) -> bool:
    text = clean(value).casefold()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n", ""}:
        return False
    raise ValueError(f"Unsupported Boolean value: {value!r}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sanitize_key(value: str, max_length: int = 120) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "_", clean(value))
    cleaned = cleaned.strip("_.:-") or "unknown"
    return cleaned[:max_length]


def make_snapshot_key(dataset_source: str, repo_name: str, commit_sha: str) -> str:
    source = clean(dataset_source).casefold()
    repo = clean(repo_name)
    commit = clean(commit_sha).casefold()
    raw = f"{source}|{repo.lower()}|{commit}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return (
        f"{sanitize_key(source, 16)}__"
        f"{sanitize_key(repo, 70)}__{commit[:12]}__{digest}"
    )


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        return next(reader, [])


def require_columns(path: Path, required: set[str], label: str) -> None:
    header = set(read_header(path))
    missing = sorted(required - header)
    if missing:
        raise ValueError(f"{label} is missing required columns {missing}: {path}")


def iter_csv(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def atomic_json(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    tmp.replace(path)


def atomic_csv_rows(rows: Iterable[Mapping[str, Any]], path: Path, columns: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with tmp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
            count += 1
    tmp.replace(path)
    return count


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def add_check(
    rows: list[dict[str, Any]],
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    note: str,
    severity: str = "hard",
) -> None:
    rows.append(
        {
            "check_name": name,
            "severity": severity,
            "passed": bool(passed),
            "observed": json_text(observed),
            "expected": json_text(expected),
            "note": note,
        }
    )


@dataclass(frozen=True)
class UniqueScore:
    sha256: str
    space_by_tokens_total: int
    npr: float
    original: float
    perturbed: float
    pooled: float
    gpu_index: int
    source_stage: str
    a09_fingerprint: str
    a02_fingerprint: str


@dataclass
class ExcludedUnit:
    sha256: str
    classes: set[str] = field(default_factory=set)
    gpu_indexes: set[int] = field(default_factory=set)
    source_stages: set[str] = field(default_factory=set)


@dataclass
class FileAccumulator:
    occurrences_total: int = 0
    occurrences_scored: int = 0
    occurrences_excluded: int = 0
    occurrences_missing: int = 0
    tokens_total: int = 0
    tokens_scored: int = 0
    tokens_excluded: int = 0
    weighted_npr_sum: float = 0.0
    weighted_original_sum: float = 0.0
    weighted_perturbed_sum: float = 0.0
    all_shas: set[str] = field(default_factory=set)
    scored_shas: set[str] = field(default_factory=set)
    excluded_shas: set[str] = field(default_factory=set)
    exclusion_classes: set[str] = field(default_factory=set)

    def add_score(self, sha: str, tokens: int, score: UniqueScore) -> None:
        self.occurrences_total += 1
        self.occurrences_scored += 1
        self.tokens_total += tokens
        self.tokens_scored += tokens
        self.weighted_npr_sum += tokens * score.npr
        self.weighted_original_sum += tokens * score.original
        self.weighted_perturbed_sum += tokens * score.perturbed
        self.all_shas.add(sha)
        self.scored_shas.add(sha)

    def add_exclusion(self, sha: str, tokens: int, exclusion: ExcludedUnit) -> None:
        self.occurrences_total += 1
        self.occurrences_excluded += 1
        self.tokens_total += tokens
        self.tokens_excluded += tokens
        self.all_shas.add(sha)
        self.excluded_shas.add(sha)
        self.exclusion_classes.update(exclusion.classes)

    def add_missing(self, sha: str, tokens: int) -> None:
        self.occurrences_total += 1
        self.occurrences_missing += 1
        self.tokens_total += tokens
        self.all_shas.add(sha)

    def metrics(self, parse_status: str) -> dict[str, Any]:
        if self.tokens_scored > 0:
            npr = self.weighted_npr_sum / self.tokens_scored
            original = self.weighted_original_sum / self.tokens_scored
            perturbed = self.weighted_perturbed_sum / self.tokens_scored
            pooled = perturbed / original if original != 0 else math.nan
        else:
            npr = math.nan
            original = math.nan
            perturbed = math.nan
            pooled = math.nan

        coverage = self.tokens_scored / self.tokens_total if self.tokens_total > 0 else math.nan
        if clean(parse_status).casefold() != "prepared":
            status = "file_not_prepared"
        elif self.occurrences_total == 0:
            status = "no_cfun"
        elif self.occurrences_missing > 0:
            status = "unexpected_missing_score"
        elif self.occurrences_scored == 0 and self.occurrences_excluded > 0:
            status = "cfun_all_excluded"
        elif self.occurrences_scored > 0 and self.occurrences_excluded > 0:
            status = "scored_with_expected_exclusions"
        else:
            status = "scored"

        def finite_or_blank(value: float) -> Any:
            return value if math.isfinite(value) else ""

        return {
            "cfun_occurrences_total": self.occurrences_total,
            "cfun_occurrences_scored": self.occurrences_scored,
            "cfun_occurrences_excluded": self.occurrences_excluded,
            "cfun_occurrences_missing": self.occurrences_missing,
            "cfun_unique_sha_total": len(self.all_shas),
            "cfun_unique_sha_scored": len(self.scored_shas),
            "cfun_unique_sha_excluded": len(self.excluded_shas),
            "cfun_space_by_tokens_total": self.tokens_total,
            "cfun_space_by_tokens_scored": self.tokens_scored,
            "cfun_space_by_tokens_excluded": self.tokens_excluded,
            "cfun_npr_coverage_ratio": finite_or_blank(coverage),
            "file_npr_cfun_space_by_token_weighted": finite_or_blank(npr),
            "file_cfun_original_log_rank_space_by_token_weighted": finite_or_blank(original),
            "file_cfun_mean_perturbed_log_rank_space_by_token_weighted": finite_or_blank(perturbed),
            "file_npr_cfun_pooled_components": finite_or_blank(pooled),
            "cfun_expected_exclusion_classes": "|".join(sorted(self.exclusion_classes)),
            "file_npr_cfun_status": status,
        }


def split_memberships(value: Any) -> set[str]:
    return {item.strip() for item in clean(value).split(",") if item.strip()}


def load_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def build_unique_score(row: Mapping[str, Any], gpu_index: int, source_stage: str, label: str) -> UniqueScore:
    sha = clean(row["code_unit_sha256"]).casefold()
    if not sha:
        raise ValueError(f"Blank {label} score SHA")
    groups = split_memberships(row["unit_groups"])
    types = split_memberships(row.get("code_unit_types", ""))
    if source_stage == "A14":
        if "C_FUN" not in groups or "method_body" not in types:
            raise ValueError(f"A14 score lacks C_FUN/method_body membership: {sha}")
    elif source_stage == "A11_REUSE" and "FUN" not in groups:
        raise ValueError(f"Reused A11 score lacks FUN membership: {sha}")
    if clean(row["status"]).casefold() != "scored":
        raise ValueError(f"{label} finite score row is not status=scored: {sha} -> {row['status']}")
    if parse_boolish(row["partial_code_unit_score"]):
        raise ValueError(f"Partial unique score is not allowed in A15: {sha}")
    total = parse_int(row["space_by_tokens_total"], f"{label} {sha}.space_by_tokens_total")
    scored = parse_int(row["space_by_tokens_scored"], f"{label} {sha}.space_by_tokens_scored")
    coverage = parse_float(row["npr_coverage_ratio"], f"{label} {sha}.npr_coverage_ratio")
    if total <= 0 or scored != total or abs(coverage - 1.0) > 1e-12:
        raise ValueError(
            f"{label} finite score must be fully covered: {sha}; total={total}; scored={scored}; coverage={coverage}"
        )
    score = UniqueScore(
        sha256=sha,
        space_by_tokens_total=total,
        npr=parse_float(row["code_unit_npr_space_by_token_weighted"], f"{label} {sha}.npr"),
        original=parse_float(row["code_unit_original_log_rank_weighted"], f"{label} {sha}.original"),
        perturbed=parse_float(row["code_unit_mean_perturbed_log_rank_weighted"], f"{label} {sha}.perturbed"),
        pooled=parse_float(row["code_unit_npr_pooled_components"], f"{label} {sha}.pooled"),
        gpu_index=gpu_index,
        source_stage=source_stage,
        a09_fingerprint=clean(row["a09_config_fingerprint"]),
        a02_fingerprint=clean(row["a02_config_fingerprint"]),
    )
    if score.a09_fingerprint != EXPECTED_A09_CONFIG_FINGERPRINT:
        raise ValueError(f"Unexpected A09 fingerprint for {sha}: {score.a09_fingerprint}")
    if score.a02_fingerprint != EXPECTED_A02_CONFIG_FINGERPRINT:
        raise ValueError(f"Unexpected A02 fingerprint for {sha}: {score.a02_fingerprint}")
    if score.original == 0.0 or abs(score.pooled - (score.perturbed / score.original)) > 1e-12:
        raise ValueError(f"Pooled-component identity failed for {sha}")
    return score


def load_a13_contract(a13_root: Path, checks: list[dict[str, Any]]) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], dict[str, Any]]:
    summary_path = a13_root / "summary.json"
    units_path = a13_root / "python_cfun_workload_units.csv"
    reuse_path = a13_root / "python_cfun_reuse_from_a11.csv"
    for path in (summary_path, units_path, reuse_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    require_columns(units_path, A13_UNIT_REQUIRED, "A13 C_FUN workload units")
    require_columns(reuse_path, A13_UNIT_REQUIRED, "A13 C_FUN A11-reuse plan")
    summary = load_json_object(summary_path)

    add_check(checks, "a13_status", clean(summary.get("status")) == "PASS", summary.get("status"), "PASS", "A15 requires the frozen PASS A13 contract.")
    add_check(checks, "a13_script_version", clean(summary.get("script_version")) == EXPECTED_A13_SCRIPT_VERSION, summary.get("script_version"), EXPECTED_A13_SCRIPT_VERSION, "A15 consumes A13 v1 outputs.")
    add_check(checks, "a13_cfun_unique_memberships", int(summary.get("cfun_unique_unit_memberships", -1)) == EXPECTED_CFUN_UNIQUE_MEMBERSHIPS, summary.get("cfun_unique_unit_memberships"), EXPECTED_CFUN_UNIQUE_MEMBERSHIPS, "A13 must define the complete C_FUN unique-SHA membership universe.")
    add_check(checks, "a13_cfun_windows", int(summary.get("cfun_windows", -1)) == EXPECTED_CFUN_WINDOWS, summary.get("cfun_windows"), EXPECTED_CFUN_WINDOWS, "A13 C_FUN window accounting must remain frozen.")
    add_check(checks, "a13_a14_new_units", int(summary.get("a14_new_unique_units", -1)) == EXPECTED_A14_NEW_UNIQUE_UNITS, summary.get("a14_new_unique_units"), EXPECTED_A14_NEW_UNIQUE_UNITS, "A13 must direct exactly the frozen A14 new-scoring unit count.")
    add_check(checks, "a13_a14_new_windows", int(summary.get("a14_new_windows", -1)) == EXPECTED_A14_NEW_WINDOWS, summary.get("a14_new_windows"), EXPECTED_A14_NEW_WINDOWS, "A13 must direct exactly the frozen A14 new-scoring window count.")
    add_check(checks, "a13_a11_reuse_finite", int(summary.get("a11_reuse_finite_units", -1)) == EXPECTED_A11_REUSE_FINITE_UNITS, summary.get("a11_reuse_finite_units"), EXPECTED_A11_REUSE_FINITE_UNITS, "A13 finite A11 reuse count must remain frozen.")
    add_check(checks, "a13_a11_reuse_partial", int(summary.get("a11_reuse_partial_units", -1)) == EXPECTED_A11_REUSE_PARTIAL_UNITS, summary.get("a11_reuse_partial_units"), EXPECTED_A11_REUSE_PARTIAL_UNITS, "A15 does not accept partial A11 reuse.")
    add_check(checks, "a13_a11_reuse_excluded", int(summary.get("a11_reuse_expected_exclusion_units", -1)) == EXPECTED_A11_REUSE_EXCLUDED_UNITS, summary.get("a11_reuse_expected_exclusion_units"), EXPECTED_A11_REUSE_EXCLUDED_UNITS, "A13 expected-exclusion reuse count must remain frozen.")

    units: dict[str, dict[str, str]] = {}
    new_shas: set[str] = set()
    reuse_shas: set[str] = set()
    for row in iter_csv(units_path):
        sha = clean(row["code_unit_sha256"]).casefold()
        if not sha or sha in units:
            raise ValueError(f"Blank or duplicate A13 C_FUN SHA: {sha}")
        groups = split_memberships(row["unit_groups"])
        types = split_memberships(row["code_unit_types"])
        if not parse_boolish(row["cfun_membership"]) or "C_FUN" not in groups or "method_body" not in types:
            raise ValueError(f"A13 workload row lacks C_FUN/method_body membership: {sha}")
        requires_a14 = parse_boolish(row["a14_scoring_required"])
        fun_membership = parse_boolish(row["fun_membership"])
        if requires_a14 and fun_membership:
            raise ValueError(f"A13 new-scoring row unexpectedly has FUN membership: {sha}")
        if not requires_a14 and not fun_membership:
            raise ValueError(f"A13 reuse row lacks FUN membership: {sha}")
        units[sha] = row
        (new_shas if requires_a14 else reuse_shas).add(sha)

    reuse: dict[str, dict[str, str]] = {}
    for row in iter_csv(reuse_path):
        sha = clean(row["code_unit_sha256"]).casefold()
        if sha in reuse:
            raise ValueError(f"Duplicate A13 reuse SHA: {sha}")
        reuse[sha] = row

    add_check(checks, "a13_unit_rows", len(units) == EXPECTED_CFUN_UNIQUE_MEMBERSHIPS, len(units), EXPECTED_CFUN_UNIQUE_MEMBERSHIPS, "A13 workload unit table must contain the complete C_FUN universe.")
    add_check(checks, "a13_new_sha_count", len(new_shas) == EXPECTED_A14_NEW_UNIQUE_UNITS, len(new_shas), EXPECTED_A14_NEW_UNIQUE_UNITS, "A13 new-scoring SHA set must match the frozen A14 workload.")
    add_check(checks, "a13_reuse_sha_count", len(reuse_shas) == 3, len(reuse_shas), 3, "A13 must identify exactly three C_FUN/FUN overlap SHA memberships.")
    add_check(checks, "a13_reuse_file_matches_unit_table", set(reuse) == reuse_shas, {"reuse_only": sorted(set(reuse)-reuse_shas), "units_only": sorted(reuse_shas-set(reuse))}, {"reuse_only": [], "units_only": []}, "A13 reuse CSV must exactly match non-A14 C_FUN rows.")
    return units, reuse, summary


def load_a14_inputs(
    results_root: Path,
    gpu_indexes: list[int],
    a13_units: dict[str, dict[str, str]],
    checks: list[dict[str, Any]],
) -> tuple[dict[str, UniqueScore], dict[str, ExcludedUnit], list[dict[str, Any]], dict[str, Any]]:
    expected_new_shas = {sha for sha, row in a13_units.items() if parse_boolish(row["a14_scoring_required"])}
    scores: dict[str, UniqueScore] = {}
    exclusions: dict[str, ExcludedUnit] = {}
    summaries: list[dict[str, Any]] = []
    exclusion_rows_total = 0

    for gpu_index in gpu_indexes:
        gpu_dir = results_root / f"gpu-{gpu_index}"
        score_path = gpu_dir / "python_cfun_new_unique_code_unit_npr_scores.csv"
        exclusion_path = gpu_dir / "python_cfun_new_npr_exclusions.csv"
        summary_path = gpu_dir / "summary.json"
        for path in (score_path, exclusion_path, summary_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        require_columns(score_path, UNIQUE_SCORE_REQUIRED, f"A14 GPU{gpu_index} unique scores")
        require_columns(exclusion_path, EXCLUSION_REQUIRED, f"A14 GPU{gpu_index} exclusions")
        summary = load_json_object(summary_path)
        summaries.append(summary)

        for row in iter_csv(score_path):
            score = build_unique_score(row, gpu_index, "A14", f"A14 GPU{gpu_index}")
            if score.sha256 in scores:
                raise ValueError(f"Duplicate A14 finite SHA across GPUs: {score.sha256}")
            scores[score.sha256] = score

        for row in iter_csv(exclusion_path):
            exclusion_rows_total += 1
            sha = clean(row["code_unit_sha256"]).casefold()
            if not sha:
                raise ValueError(f"Blank A14 exclusion SHA in {exclusion_path}")
            groups = split_memberships(row["unit_groups"])
            if "C_FUN" not in groups:
                raise ValueError(f"A14 exclusion lacks C_FUN membership: {sha}")
            exclusion_class = clean(row["exclusion_class"])
            if exclusion_class not in EXPECTED_EXCLUSION_CLASSES:
                raise ValueError(f"Unexpected A14 exclusion class for {sha}: {exclusion_class}")
            item = exclusions.setdefault(sha, ExcludedUnit(sha256=sha))
            item.classes.add(exclusion_class)
            item.gpu_indexes.add(gpu_index)
            item.source_stages.add("A14")

    overlap = set(scores) & set(exclusions)
    if overlap:
        raise ValueError(f"A14 SHA appears in both finite scores and exclusions: {sorted(overlap)[:10]}")
    observed_new = set(scores) | set(exclusions)
    add_check(checks, "a14_sha_set_matches_a13_new", observed_new == expected_new_shas, {"a14_only": sorted(observed_new-expected_new_shas)[:10], "a13_only": sorted(expected_new_shas-observed_new)[:10]}, {"a14_only": [], "a13_only": []}, "A14 finite+excluded SHA identities must exactly equal A13 new-scoring SHA identities.")

    statuses = [clean(item.get("status")) for item in summaries]
    versions = [clean(item.get("script_version")) for item in summaries]
    add_check(checks, "a14_worker_status", all(value in {"PASS", "PASS_WITH_EXCLUSIONS"} for value in statuses), statuses, ["PASS or PASS_WITH_EXCLUSIONS"] * len(statuses), "All A14 workers must be terminal successful runs.")
    add_check(checks, "a14_script_version", all(value == EXPECTED_A14_SCRIPT_VERSION for value in versions), versions, [EXPECTED_A14_SCRIPT_VERSION] * len(versions), "A15 consumes A14 v1 finalized artifacts.")
    add_check(checks, "a14_database_windows", sum(int(item.get("database_windows", 0)) for item in summaries) == EXPECTED_A14_NEW_WINDOWS, sum(int(item.get("database_windows", 0)) for item in summaries), EXPECTED_A14_NEW_WINDOWS, "A14 database windows must reconcile to A13 new-C_FUN windows.")
    add_check(checks, "a14_full_expected_windows", sum(int(item.get("full_expected_cfun_new_windows", 0)) for item in summaries) == EXPECTED_A14_NEW_WINDOWS, sum(int(item.get("full_expected_cfun_new_windows", 0)) for item in summaries), EXPECTED_A14_NEW_WINDOWS, "A14 planned worker windows must reconcile to A13 new-C_FUN windows.")
    add_check(checks, "a14_full_expected_units", sum(int(item.get("full_expected_cfun_new_unique_units", 0)) for item in summaries) == EXPECTED_A14_NEW_UNIQUE_UNITS, sum(int(item.get("full_expected_cfun_new_unique_units", 0)) for item in summaries), EXPECTED_A14_NEW_UNIQUE_UNITS, "A14 planned worker unique units must reconcile to A13 new-C_FUN units.")
    add_check(checks, "a14_assigned_shards", sum(int(item.get("assigned_shard_count", 0)) for item in summaries) == 96, sum(int(item.get("assigned_shard_count", 0)) for item in summaries), 96, "A14 worker summaries must cover all 96 logical shards exactly in total.")
    add_check(checks, "a14_exported_unique_units", sum(int(item.get("exported_unique_units", 0)) for item in summaries) == len(scores), sum(int(item.get("exported_unique_units", 0)) for item in summaries), len(scores), "A14 summary finite-unit totals must match the actual unique-score CSVs.")
    add_check(checks, "a14_unexpected_invalid_windows", sum(int(item.get("unexpected_invalid_windows", -1)) for item in summaries) == 0, sum(int(item.get("unexpected_invalid_windows", -1)) for item in summaries), 0, "No unexpected A14 invalid windows are allowed.")
    add_check(checks, "a14_scoring_errors", sum(int(item.get("scoring_errors", -1)) for item in summaries) == 0, sum(int(item.get("scoring_errors", -1)) for item in summaries), 0, "No residual A14 scoring errors are allowed.")
    add_check(checks, "a14_partial_units", sum(int(item.get("partial_unique_units", -1)) for item in summaries) == 0, sum(int(item.get("partial_unique_units", -1)) for item in summaries), 0, "A15 does not accept partial A14 C_FUN units.")
    add_check(checks, "a14_failed_checks", sum(int(item.get("failed_checks", -1)) for item in summaries) == 0, sum(int(item.get("failed_checks", -1)) for item in summaries), 0, "All A14 worker checks must pass.")
    for label, expected in (("a09_config_fingerprint", EXPECTED_A09_CONFIG_FINGERPRINT), ("a02_config_fingerprint", EXPECTED_A02_CONFIG_FINGERPRINT), ("model_revision", EXPECTED_MODEL_REVISION)):
        values = [clean(item.get(label)) for item in summaries]
        add_check(checks, f"a14_{label}", all(value == expected for value in values), values, [expected] * len(values), f"All A14 workers must use the frozen {label}.")

    diagnostics = {
        "finite_unique_sha": len(scores),
        "excluded_unique_sha": len(exclusions),
        "exclusion_rows_total": exclusion_rows_total,
        "union_unique_sha": len(observed_new),
    }
    return scores, exclusions, summaries, diagnostics


def load_a11_reuse_inputs(
    results_root: Path,
    gpu_indexes: list[int],
    reuse_plan: dict[str, dict[str, str]],
    checks: list[dict[str, Any]],
) -> tuple[dict[str, UniqueScore], dict[str, ExcludedUnit], list[dict[str, Any]], dict[str, Any]]:
    target_shas = set(reuse_plan)
    scores: dict[str, UniqueScore] = {}
    exclusions: dict[str, ExcludedUnit] = {}
    summaries: list[dict[str, Any]] = []

    for gpu_index in gpu_indexes:
        gpu_dir = results_root / f"gpu-{gpu_index}"
        score_path = gpu_dir / "python_fun_unique_code_unit_npr_scores.csv"
        exclusion_path = gpu_dir / "python_fun_npr_exclusions.csv"
        summary_path = gpu_dir / "summary.json"
        for path in (score_path, exclusion_path, summary_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        require_columns(score_path, UNIQUE_SCORE_REQUIRED - {"code_unit_types"}, f"A11 GPU{gpu_index} unique scores")
        require_columns(exclusion_path, EXCLUSION_REQUIRED, f"A11 GPU{gpu_index} exclusions")
        summaries.append(load_json_object(summary_path))

        for row in iter_csv(score_path):
            sha = clean(row["code_unit_sha256"]).casefold()
            if sha not in target_shas:
                continue
            # A11 does not need code_unit_types for the reused lookup; provide a harmless value if absent.
            row_for_score = dict(row)
            row_for_score.setdefault("code_unit_types", "function_body")
            score = build_unique_score(row_for_score, gpu_index, "A11_REUSE", f"A11 GPU{gpu_index} reuse")
            if sha in scores:
                raise ValueError(f"Reused A11 finite SHA appears on multiple GPUs: {sha}")
            scores[sha] = score

        for row in iter_csv(exclusion_path):
            sha = clean(row["code_unit_sha256"]).casefold()
            if sha not in target_shas:
                continue
            exclusion_class = clean(row["exclusion_class"])
            if exclusion_class not in EXPECTED_EXCLUSION_CLASSES:
                raise ValueError(f"Unexpected reused A11 exclusion class for {sha}: {exclusion_class}")
            item = exclusions.setdefault(sha, ExcludedUnit(sha256=sha))
            item.classes.add(exclusion_class)
            item.gpu_indexes.add(gpu_index)
            item.source_stages.add("A11_REUSE")

    statuses = [clean(item.get("status")) for item in summaries]
    versions = [clean(item.get("script_version")) for item in summaries]
    add_check(checks, "a11_reuse_worker_status", all(value == "PASS_WITH_EXCLUSIONS" for value in statuses), statuses, ["PASS_WITH_EXCLUSIONS"] * len(statuses), "A13 reuse points into finalized A11 v3 results.")
    add_check(checks, "a11_reuse_script_version", all(value == EXPECTED_A11_SCRIPT_VERSION for value in versions), versions, [EXPECTED_A11_SCRIPT_VERSION] * len(versions), "A15 reuses only frozen A11 v3 artifacts.")
    for label, expected in (("a09_config_fingerprint", EXPECTED_A09_CONFIG_FINGERPRINT), ("a02_config_fingerprint", EXPECTED_A02_CONFIG_FINGERPRINT), ("model_revision", EXPECTED_MODEL_REVISION)):
        values = [clean(item.get(label)) for item in summaries]
        add_check(checks, f"a11_reuse_{label}", all(value == expected for value in values), values, [expected] * len(values), f"All reused A11 workers must use the frozen {label}.")

    overlap = set(scores) & set(exclusions)
    if overlap:
        raise ValueError(f"Reused A11 SHA appears in both finite scores and exclusions: {sorted(overlap)}")
    observed = set(scores) | set(exclusions)
    add_check(checks, "a11_reuse_sha_set", observed == target_shas, {"observed_only": sorted(observed-target_shas), "plan_only": sorted(target_shas-observed)}, {"observed_only": [], "plan_only": []}, "A11 finite+excluded reuse identities must exactly match A13 reuse plan.")

    finite_expected = {sha for sha, row in reuse_plan.items() if clean(row["a11_reuse_class"]) == "reuse_a11_finite"}
    excluded_expected = {sha for sha, row in reuse_plan.items() if clean(row["a11_reuse_class"]) == "reuse_a11_expected_exclusion"}
    partial_expected = {sha for sha, row in reuse_plan.items() if clean(row["a11_reuse_class"]) == "reuse_a11_partial"}
    add_check(checks, "a11_reuse_finite_identity", set(scores) == finite_expected, {"score_only": sorted(set(scores)-finite_expected), "plan_only": sorted(finite_expected-set(scores))}, {"score_only": [], "plan_only": []}, "A11 finite reuse must follow A13 classification exactly.")
    add_check(checks, "a11_reuse_exclusion_identity", set(exclusions) == excluded_expected, {"exclusion_only": sorted(set(exclusions)-excluded_expected), "plan_only": sorted(excluded_expected-set(exclusions))}, {"exclusion_only": [], "plan_only": []}, "A11 expected-exclusion reuse must follow A13 classification exactly.")
    add_check(checks, "a11_reuse_partial_zero", not partial_expected, len(partial_expected), 0, "A15 rejects partial A11 reuse by frozen design.")

    for sha, score in scores.items():
        planned_tokens = parse_int(reuse_plan[sha]["space_by_token_count"], f"A13 reuse {sha}.space_by_token_count")
        if score.space_by_tokens_total != planned_tokens:
            raise ValueError(f"A11 reuse token count differs from A13 for {sha}: score={score.space_by_tokens_total}; plan={planned_tokens}")
        planned_gpu = parse_int(reuse_plan[sha]["a11_gpu_index"], f"A13 reuse {sha}.a11_gpu_index")
        if score.gpu_index != planned_gpu:
            raise ValueError(f"A11 reuse GPU differs from A13 for {sha}: score={score.gpu_index}; plan={planned_gpu}")
    for sha, exclusion in exclusions.items():
        planned_gpu = parse_int(reuse_plan[sha]["a11_gpu_index"], f"A13 reuse {sha}.a11_gpu_index")
        if exclusion.gpu_indexes != {planned_gpu}:
            raise ValueError(f"A11 exclusion GPU differs from A13 for {sha}: observed={sorted(exclusion.gpu_indexes)}; plan={planned_gpu}")

    diagnostics = {
        "target_sha": len(target_shas),
        "finite_unique_sha": len(scores),
        "excluded_unique_sha": len(exclusions),
        "union_unique_sha": len(observed),
    }
    return scores, exclusions, summaries, diagnostics


def load_snapshot_manifest(path: Path) -> tuple[dict[str, dict[str, str]], dict[tuple[str, str, str], str]]:
    require_columns(path, A05_SNAPSHOT_REQUIRED, "A05 snapshot manifest")
    by_id: dict[str, dict[str, str]] = {}
    by_identity: dict[tuple[str, str, str], str] = {}
    for row in iter_csv(path):
        snapshot_id = clean(row["snapshot_id"])
        if snapshot_id in by_id:
            raise ValueError(f"Duplicate A05 snapshot_id: {snapshot_id}")
        source = clean(row["dataset_source"]).casefold()
        repo = clean(row["repo_name"])
        commit = clean(row["snapshot_commit"]).casefold()
        identity = (source, repo.casefold(), commit)
        if identity in by_identity:
            raise ValueError(f"Duplicate A05 snapshot identity: {identity}")
        by_id[snapshot_id] = row
        by_identity[identity] = snapshot_id
    return by_id, by_identity


def load_repo_month_mapping(
    panel_path: Path,
    snapshots_by_id: dict[str, dict[str, str]],
    snapshot_identity_to_id: dict[tuple[str, str, str], str],
) -> tuple[dict[str, list[dict[str, str]]], dict[str, Any]]:
    require_columns(panel_path, PANEL_REQUIRED, "repo-month panel")
    mapping: dict[str, list[dict[str, str]]] = defaultdict(list)
    repo_month_keys: set[tuple[str, str, str]] = set()
    repos: set[tuple[str, str]] = set()
    unresolved: list[dict[str, str]] = []
    row_count = 0

    for row in iter_csv(panel_path):
        row_count += 1
        source = clean(row["dataset_source"]).casefold()
        repo = clean(row["repo_name"])
        month = clean(row["time"])
        commit = clean(row["latest_commit_effective"]).casefold()
        key = (source, repo.casefold(), month)
        if key in repo_month_keys:
            raise ValueError(f"Duplicate repo-month row in authoritative panel: {key}")
        repo_month_keys.add(key)
        repos.add((source, repo.casefold()))
        identity = (source, repo.casefold(), commit)
        snapshot_id = snapshot_identity_to_id.get(identity, "")
        snapshot = snapshots_by_id.get(snapshot_id) if snapshot_id else None
        if snapshot is None:
            unresolved.append({"dataset_source": source, "repo_name": repo, "time": month, "latest_commit_effective": commit, "derived_snapshot_id": make_snapshot_key(source, repo, commit)})
            continue
        if clean(snapshot["snapshot_commit"]).casefold() != commit:
            raise ValueError(f"Snapshot commit mismatch for panel row {source}/{repo}/{month}")
        mapping[snapshot_id].append(row)

    if unresolved:
        raise ValueError(f"Repo-month panel has rows not mapped to A05 snapshots; examples={unresolved[:10]}")

    diagnostics = {
        "panel_rows": row_count,
        "panel_unique_repo_months": len(repo_month_keys),
        "panel_repositories": len(repos),
        "panel_unique_snapshots": len(mapping),
        "unresolved_rows": len(unresolved),
    }
    return mapping, diagnostics


def stream_cfun_occurrences(
    code_manifest: Path,
    scores: dict[str, UniqueScore],
    exclusions: dict[str, ExcludedUnit],
    a13_units: dict[str, dict[str, str]],
    reuse_plan: dict[str, dict[str, str]],
    snapshot_manifest: dict[str, dict[str, str]],
    occurrence_exclusion_output: Path,
    reuse_occurrence_output: Path,
) -> tuple[dict[tuple[str, str, str], FileAccumulator], dict[str, Any]]:
    """Expand the frozen unique C_FUN score universe back to every A05 method occurrence."""
    require_columns(code_manifest, A05_CODE_REQUIRED, "A05 code-unit manifest")
    accumulators: dict[tuple[str, str, str], FileAccumulator] = {}
    all_rows = 0
    primary_rows = 0
    cfun_occurrences = 0
    cfun_unique_shas: set[str] = set()
    missing_unique_shas: set[str] = set()
    token_mismatch_occurrences = 0
    snapshot_missing_occurrences = 0
    exclusion_occurrences = 0
    reuse_occurrences = 0

    occurrence_exclusion_output.parent.mkdir(parents=True, exist_ok=True)
    reuse_occurrence_output.parent.mkdir(parents=True, exist_ok=True)
    tmp_exclusions = occurrence_exclusion_output.with_suffix(occurrence_exclusion_output.suffix + ".tmp")
    tmp_reuse = reuse_occurrence_output.with_suffix(reuse_occurrence_output.suffix + ".tmp")
    with tmp_exclusions.open("w", encoding="utf-8", newline="") as exclusion_stream, tmp_reuse.open("w", encoding="utf-8", newline="") as reuse_stream:
        exclusion_writer = csv.DictWriter(exclusion_stream, fieldnames=EXCLUSION_OCCURRENCE_COLUMNS)
        reuse_writer = csv.DictWriter(reuse_stream, fieldnames=A11_REUSE_OCCURRENCE_COLUMNS)
        exclusion_writer.writeheader()
        reuse_writer.writeheader()
        for row in iter_csv(code_manifest):
            all_rows += 1
            if clean(row["aggregation_role"]) == PRIMARY_ROLE:
                primary_rows += 1
            if clean(row["aggregation_role"]) != PRIMARY_ROLE or clean(row["code_unit_type"]) != CFUN_CODE_UNIT_TYPE:
                continue
            cfun_occurrences += 1
            snapshot_id = clean(row["snapshot_id"])
            if snapshot_id not in snapshot_manifest:
                snapshot_missing_occurrences += 1
            relative_path = clean(row["relative_path"])
            file_sha = clean(row["file_sha256"]).casefold()
            sha = clean(row["code_unit_sha256"]).casefold()
            tokens = parse_int(row["space_by_token_count"], f"A05 C_FUN occurrence {sha}.space_by_token_count")
            if tokens <= 0:
                raise ValueError(f"A05 C_FUN occurrence has non-positive token count: {sha}")
            key = (snapshot_id, relative_path, file_sha)
            accumulator = accumulators.setdefault(key, FileAccumulator())
            cfun_unique_shas.add(sha)

            planned = a13_units.get(sha)
            if planned is None:
                accumulator.add_missing(sha, tokens)
                missing_unique_shas.add(sha)
                continue
            planned_tokens = parse_int(planned["space_by_token_count"], f"A13 C_FUN {sha}.space_by_token_count")
            if planned_tokens != tokens:
                token_mismatch_occurrences += 1

            if sha in reuse_plan:
                reuse_occurrences += 1
                snapshot = snapshot_manifest.get(snapshot_id, {})
                reuse_writer.writerow({
                    "snapshot_id": snapshot_id,
                    "dataset_source": snapshot.get("dataset_source", ""),
                    "repo_name": snapshot.get("repo_name", ""),
                    "relative_path": relative_path,
                    "file_sha256": file_sha,
                    "code_unit_id": row.get("code_unit_id", ""),
                    "code_unit_sha256": sha,
                    "space_by_token_count": tokens,
                    "a11_reuse_class": reuse_plan[sha].get("a11_reuse_class", ""),
                    "a11_gpu_index": reuse_plan[sha].get("a11_gpu_index", ""),
                })

            score = scores.get(sha)
            exclusion = exclusions.get(sha)
            if score is not None:
                if score.space_by_tokens_total != tokens:
                    token_mismatch_occurrences += 1
                accumulator.add_score(sha, tokens, score)
            elif exclusion is not None:
                accumulator.add_exclusion(sha, tokens, exclusion)
                exclusion_occurrences += 1
                snapshot = snapshot_manifest.get(snapshot_id, {})
                exclusion_writer.writerow({
                    "snapshot_id": snapshot_id,
                    "dataset_source": snapshot.get("dataset_source", ""),
                    "repo_name": snapshot.get("repo_name", ""),
                    "relative_path": relative_path,
                    "file_sha256": file_sha,
                    "code_unit_id": row.get("code_unit_id", ""),
                    "code_unit_sha256": sha,
                    "space_by_token_count": tokens,
                    "exclusion_classes": "|".join(sorted(exclusion.classes)),
                    "exclusion_sources": "|".join(sorted(exclusion.source_stages)),
                    "source_gpu_indexes": "|".join(str(value) for value in sorted(exclusion.gpu_indexes)),
                })
            else:
                accumulator.add_missing(sha, tokens)
                missing_unique_shas.add(sha)
    tmp_exclusions.replace(occurrence_exclusion_output)
    tmp_reuse.replace(reuse_occurrence_output)

    diagnostics = {
        "a05_code_manifest_rows": all_rows,
        "a05_primary_code_unit_occurrences": primary_rows,
        "cfun_occurrences": cfun_occurrences,
        "cfun_unique_sha": len(cfun_unique_shas),
        "cfun_unique_sha_values": cfun_unique_shas,
        "missing_unique_sha": len(missing_unique_shas),
        "missing_unique_sha_examples": sorted(missing_unique_shas)[:20],
        "token_mismatch_occurrences": token_mismatch_occurrences,
        "snapshot_missing_occurrences": snapshot_missing_occurrences,
        "expected_exclusion_occurrences": exclusion_occurrences,
        "a11_reuse_occurrences": reuse_occurrences,
        "files_with_cfun": len(accumulators),
    }
    return accumulators, diagnostics


def write_file_scores(
    file_manifest: Path,
    accumulators: dict[tuple[str, str, str], FileAccumulator],
    output_path: Path,
) -> dict[str, Any]:
    require_columns(file_manifest, A05_FILE_REQUIRED, "A05 file manifest")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    seen_keys: set[tuple[str, str, str]] = set()
    rows = 0
    status_counts: dict[str, int] = defaultdict(int)
    finite_rows = 0
    no_cfun_rows = 0
    unexpected_missing_rows = 0

    with tmp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FILE_OUTPUT_COLUMNS)
        writer.writeheader()
        for row in iter_csv(file_manifest):
            rows += 1
            key = (
                clean(row["snapshot_id"]),
                clean(row["relative_path"]),
                clean(row["file_sha256"]).casefold(),
            )
            if key in seen_keys:
                raise ValueError(f"Duplicate A05 file key: {key}")
            seen_keys.add(key)
            accumulator = accumulators.get(key, FileAccumulator())
            metrics = accumulator.metrics(clean(row["parse_status"]))
            status = clean(metrics["file_npr_cfun_status"])
            status_counts[status] += 1
            if status in {"scored", "scored_with_expected_exclusions"}:
                finite_rows += 1
            if status == "no_cfun":
                no_cfun_rows += 1
            if status == "unexpected_missing_score":
                unexpected_missing_rows += 1
            output = {
                "snapshot_order": row.get("snapshot_order", ""),
                "snapshot_id": row.get("snapshot_id", ""),
                "dataset_source": row.get("dataset_source", ""),
                "repo_name": row.get("repo_name", ""),
                "repo_key": row.get("repo_key", ""),
                "snapshot_time": row.get("snapshot_time", ""),
                "snapshot_commit": row.get("snapshot_commit", ""),
                "relative_path": row.get("relative_path", ""),
                "file_sha256": row.get("file_sha256", ""),
                "python_lines": row.get("physical_line_count", ""),
                "parse_status": row.get("parse_status", ""),
                **metrics,
            }
            writer.writerow(output)
    tmp.replace(output_path)

    orphan_cfun_file_keys = set(accumulators) - seen_keys
    return {
        "file_manifest_rows": rows,
        "file_unique_keys": len(seen_keys),
        "files_with_finite_cfun_npr": finite_rows,
        "files_with_no_cfun": no_cfun_rows,
        "files_with_unexpected_missing_cfun_score": unexpected_missing_rows,
        "file_status_counts": dict(sorted(status_counts.items())),
        "orphan_cfun_file_keys": len(orphan_cfun_file_keys),
        "orphan_cfun_file_key_examples": [list(item) for item in sorted(orphan_cfun_file_keys)[:20]],
    }


def write_repo_month_file_scores(
    file_score_path: Path,
    mapping: dict[str, list[dict[str, str]]],
    output_path: Path,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    rows = 0
    mapped_file_rows = 0
    unmapped_snapshot_file_rows = 0
    repo_months_seen: set[tuple[str, str, str]] = set()
    finite_rows = 0

    with tmp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REPO_MONTH_OUTPUT_COLUMNS)
        writer.writeheader()
        for file_row in iter_csv(file_score_path):
            snapshot_id = clean(file_row["snapshot_id"])
            panel_rows = mapping.get(snapshot_id, [])
            if not panel_rows:
                unmapped_snapshot_file_rows += 1
                continue
            mapped_file_rows += 1
            for panel_row in panel_rows:
                source = clean(panel_row.get("dataset_source")).casefold()
                repo = clean(panel_row.get("repo_name"))
                month = clean(panel_row.get("time"))
                repo_months_seen.add((source, repo.casefold(), month))
                output = {
                    "repo_id": panel_row.get("repo_id", ""),
                    "dataset_source": source,
                    "repo_name": repo,
                    "repo_month": month,
                    "time_index": panel_row.get("time_index", ""),
                    "event": panel_row.get("event", ""),
                    "event_index": panel_row.get("event_index", ""),
                    "snapshot_id": snapshot_id,
                    "snapshot_commit": file_row.get("snapshot_commit", ""),
                    "relative_path": file_row.get("relative_path", ""),
                    "file_sha256": file_row.get("file_sha256", ""),
                    "python_lines": file_row.get("python_lines", ""),
                    "parse_status": file_row.get("parse_status", ""),
                }
                for column in FILE_OUTPUT_COLUMNS:
                    if column.startswith("cfun_") or column.startswith("file_"):
                        output[column] = file_row.get(column, "")
                writer.writerow(output)
                rows += 1
                if clean(file_row.get("file_npr_cfun_status")) in {"scored", "scored_with_expected_exclusions"}:
                    finite_rows += 1
    tmp.replace(output_path)
    return {
        "repo_month_file_rows": rows,
        "snapshot_file_rows_with_panel_mapping": mapped_file_rows,
        "snapshot_file_rows_without_panel_mapping": unmapped_snapshot_file_rows,
        "repo_months_represented": len(repo_months_seen),
        "repo_month_file_rows_with_finite_cfun_npr": finite_rows,
    }


def run_self_test() -> None:
    score_a = UniqueScore("a", 10, 1.0, 2.0, 2.0, 1.0, 0, "A14", EXPECTED_A09_CONFIG_FINGERPRINT, EXPECTED_A02_CONFIG_FINGERPRINT)
    score_b = UniqueScore("b", 30, 2.0, 4.0, 8.0, 2.0, 1, "A14", EXPECTED_A09_CONFIG_FINGERPRINT, EXPECTED_A02_CONFIG_FINGERPRINT)
    exclusion = ExcludedUnit("x", {"zero_original_log_rank"}, {2}, {"A11_REUSE"})
    acc = FileAccumulator()
    acc.add_score("a", 10, score_a)
    acc.add_score("b", 30, score_b)
    acc.add_exclusion("x", 10, exclusion)
    metrics = acc.metrics("prepared")
    assert metrics["cfun_occurrences_total"] == 3
    assert metrics["cfun_occurrences_scored"] == 2
    assert metrics["cfun_occurrences_excluded"] == 1
    assert metrics["cfun_space_by_tokens_total"] == 50
    assert metrics["cfun_space_by_tokens_scored"] == 40
    assert math.isclose(float(metrics["cfun_npr_coverage_ratio"]), 0.8, abs_tol=1e-12)
    assert math.isclose(float(metrics["file_npr_cfun_space_by_token_weighted"]), 1.75, abs_tol=1e-12)
    expected_original = (10 * 2.0 + 30 * 4.0) / 40
    expected_perturbed = (10 * 2.0 + 30 * 8.0) / 40
    assert math.isclose(float(metrics["file_npr_cfun_pooled_components"]), expected_perturbed / expected_original, abs_tol=1e-12)
    assert metrics["file_npr_cfun_status"] == "scored_with_expected_exclusions"
    no_cfun = FileAccumulator().metrics("prepared")
    assert no_cfun["file_npr_cfun_status"] == "no_cfun"
    assert no_cfun["file_npr_cfun_space_by_token_weighted"] == ""
    assert split_memberships("C_FUN,BLOCK") == {"C_FUN", "BLOCK"}
    assert split_memberships("class_block,method_body") == {"class_block", "method_body"}
    assert make_snapshot_key("control", "Owner/Repo", "a" * 40) == make_snapshot_key("CONTROL", "Owner/Repo", "A" * 40)
    prohibited = {"threshold", "agc", "hwc", "classification"}
    assert not any(any(token in column.casefold() for token in prohibited) for column in FILE_OUTPUT_COLUMNS + REPO_MONTH_OUTPUT_COLUMNS)
    print("aggregate_snapshot_npr_cfun_files self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate finalized A14 C_FUN NPR plus A13-directed A11 reuse to snapshot/file and repo-month/file levels."
    )
    parser.add_argument("--a05-root", type=Path, default=Path("output/snapshot_npr/run-x-a05"))
    parser.add_argument("--a11-results-root", type=Path, default=Path("output/snapshot_npr/run-x-a11/results"))
    parser.add_argument("--a13-root", type=Path, default=Path("output/snapshot_npr/run-x-a13"))
    parser.add_argument("--a14-results-root", type=Path, default=Path("output/snapshot_npr/run-x-a14/results"))
    parser.add_argument("--repo-month-panel-file", type=Path, default=Path("../ai_code_complexity_study_python/ai-code-complexity-study/repo_x01/run-x-a05/velocity_did_panel_model_a.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/snapshot_npr/run-x-a15"))
    parser.add_argument("--gpu-indexes", default="0,1,2")
    parser.add_argument("--expected-snapshots", type=int, default=1496)
    parser.add_argument("--expected-python-files", type=int, default=494592)
    parser.add_argument("--expected-code-unit-rows", type=int, default=3650592)
    parser.add_argument("--expected-primary-occurrences", type=int, default=3480000)
    parser.add_argument("--expected-cfun-unique-memberships", type=int, default=EXPECTED_CFUN_UNIQUE_MEMBERSHIPS)
    parser.add_argument("--expected-finite-cfun-unique", type=int, default=195192)
    parser.add_argument("--expected-excluded-cfun-unique", type=int, default=1)
    parser.add_argument("--expected-cfun-windows", type=int, default=EXPECTED_CFUN_WINDOWS)
    parser.add_argument("--expected-a14-new-windows", type=int, default=EXPECTED_A14_NEW_WINDOWS)
    parser.add_argument("--expected-repo-month-rows", type=int, default=1954)
    parser.add_argument("--expected-repo-month-file-rows", type=int, default=510297)
    parser.add_argument("--expected-repositories", type=int, default=167)
    parser.add_argument("--expected-a05-code-manifest-sha256", default=EXPECTED_A05_CODE_MANIFEST_SHA256)
    parser.add_argument("--strict-expected-counts", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0

    started = utc_now()
    args.a05_root = args.a05_root.expanduser().resolve()
    args.a11_results_root = args.a11_results_root.expanduser().resolve()
    args.a13_root = args.a13_root.expanduser().resolve()
    args.a14_results_root = args.a14_results_root.expanduser().resolve()
    args.repo_month_panel_file = args.repo_month_panel_file.expanduser().resolve()
    args.output_dir = args.output_dir.expanduser().resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    snapshot_manifest_path = args.a05_root / "python_snapshot_manifest.csv"
    file_manifest_path = args.a05_root / "python_file_manifest.csv"
    code_manifest_path = args.a05_root / "python_code_unit_manifest.csv"
    for path in (snapshot_manifest_path, file_manifest_path, code_manifest_path, args.repo_month_panel_file):
        if not path.is_file():
            raise FileNotFoundError(path)

    checks: list[dict[str, Any]] = []
    code_manifest_sha = sha256_file(code_manifest_path)
    add_check(checks, "a05_code_manifest_sha256", code_manifest_sha == args.expected_a05_code_manifest_sha256, code_manifest_sha, args.expected_a05_code_manifest_sha256, "A15 must use the exact frozen A05 occurrence manifest used by A09/A13/A14.")

    gpu_indexes = [int(item.strip()) for item in args.gpu_indexes.split(",") if item.strip()]
    if sorted(gpu_indexes) != [0, 1, 2]:
        raise ValueError(f"Production A15 expects GPU indexes 0,1,2; found {gpu_indexes}")

    a13_units, reuse_plan, a13_summary = load_a13_contract(args.a13_root, checks)
    add_check(checks, "a13_cfun_windows_cli", int(a13_summary.get("cfun_windows", -1)) == args.expected_cfun_windows, a13_summary.get("cfun_windows"), args.expected_cfun_windows, "CLI expected C_FUN window count must match A13 summary.")
    add_check(checks, "a13_a14_new_windows_cli", int(a13_summary.get("a14_new_windows", -1)) == args.expected_a14_new_windows, a13_summary.get("a14_new_windows"), args.expected_a14_new_windows, "CLI expected A14 new-window count must match A13 summary.")
    a14_scores, a14_exclusions, a14_summaries, a14_diag = load_a14_inputs(
        args.a14_results_root, gpu_indexes, a13_units, checks
    )
    a11_scores, a11_exclusions, a11_summaries, a11_diag = load_a11_reuse_inputs(
        args.a11_results_root, gpu_indexes, reuse_plan, checks
    )

    if set(a14_scores) & set(a11_scores) or set(a14_scores) & set(a11_exclusions) or set(a14_exclusions) & set(a11_scores) or set(a14_exclusions) & set(a11_exclusions):
        raise ValueError("A14 new-C_FUN and A11 reused C_FUN SHA sets must be disjoint.")
    scores = {**a14_scores, **a11_scores}
    exclusions = {**a14_exclusions, **a11_exclusions}
    combined_universe = set(scores) | set(exclusions)
    a13_universe = set(a13_units)

    add_check(checks, "combined_finite_cfun_unique", len(scores) == args.expected_finite_cfun_unique, len(scores), args.expected_finite_cfun_unique, "A14 finite new C_FUN plus finite A11 reuse must reconcile.")
    add_check(checks, "combined_excluded_cfun_unique", len(exclusions) == args.expected_excluded_cfun_unique, len(exclusions), args.expected_excluded_cfun_unique, "Expected C_FUN exclusions must reconcile.")
    add_check(checks, "combined_cfun_unique_memberships", len(combined_universe) == args.expected_cfun_unique_memberships, len(combined_universe), args.expected_cfun_unique_memberships, "Finite and excluded C_FUN SHA sets must partition the full C_FUN universe.")
    add_check(checks, "combined_cfun_sha_set_matches_a13", combined_universe == a13_universe, {"combined_only": sorted(combined_universe-a13_universe)[:10], "a13_only": sorted(a13_universe-combined_universe)[:10]}, {"combined_only": [], "a13_only": []}, "A15 score/exclusion identities must exactly match A13 C_FUN membership identities.")

    snapshots_by_id, snapshot_identity_to_id = load_snapshot_manifest(snapshot_manifest_path)
    add_check(checks, "a05_snapshot_rows", len(snapshots_by_id) == args.expected_snapshots, len(snapshots_by_id), args.expected_snapshots, "A05 historical snapshot count must match production.")

    repo_month_mapping, panel_diag = load_repo_month_mapping(
        args.repo_month_panel_file, snapshots_by_id, snapshot_identity_to_id
    )
    add_check(checks, "repo_month_panel_rows", panel_diag["panel_rows"] == args.expected_repo_month_rows, panel_diag["panel_rows"], args.expected_repo_month_rows, "Authoritative Model A repo-month rows must match production.")
    add_check(checks, "repo_month_panel_unique_snapshots", panel_diag["panel_unique_snapshots"] == args.expected_snapshots, panel_diag["panel_unique_snapshots"], args.expected_snapshots, "All A05 snapshots must be represented by the authoritative repo-month panel.")
    add_check(checks, "repo_month_panel_repositories", panel_diag["panel_repositories"] == args.expected_repositories, panel_diag["panel_repositories"], args.expected_repositories, "Repository count must match the fixed Model A sample.")

    occurrence_exclusions_path = args.output_dir / "python_cfun_occurrence_exclusions.csv"
    reuse_occurrences_path = args.output_dir / "python_cfun_reuse_from_a11_occurrences.csv"
    accumulators, occurrence_diag = stream_cfun_occurrences(
        code_manifest_path,
        scores,
        exclusions,
        a13_units,
        reuse_plan,
        snapshots_by_id,
        occurrence_exclusions_path,
        reuse_occurrences_path,
    )
    cfun_universe = occurrence_diag.pop("cfun_unique_sha_values")
    add_check(checks, "a05_code_unit_rows", occurrence_diag["a05_code_manifest_rows"] == args.expected_code_unit_rows, occurrence_diag["a05_code_manifest_rows"], args.expected_code_unit_rows, "A05 consolidated code-unit occurrence count must match production.")
    add_check(checks, "a05_primary_occurrences", occurrence_diag["a05_primary_code_unit_occurrences"] == args.expected_primary_occurrences, occurrence_diag["a05_primary_code_unit_occurrences"], args.expected_primary_occurrences, "A05 primary occurrence count must match production.")
    add_check(checks, "a05_cfun_unique_memberships", occurrence_diag["cfun_unique_sha"] == args.expected_cfun_unique_memberships, occurrence_diag["cfun_unique_sha"], args.expected_cfun_unique_memberships, "A05 unique SHA values occurring as primary method_body must equal the A13 C_FUN membership universe.")
    add_check(checks, "a05_vs_a13_cfun_sha_set", cfun_universe == a13_universe, {"a05_only": sorted(cfun_universe-a13_universe)[:10], "a13_only": sorted(a13_universe-cfun_universe)[:10]}, {"a05_only": [], "a13_only": []}, "A05 primary method_body SHA values must exactly equal A13 C_FUN identities.")
    add_check(checks, "cfun_missing_unique_sha", occurrence_diag["missing_unique_sha"] == 0, occurrence_diag["missing_unique_sha"], 0, "Every primary method_body occurrence must resolve to either a finite C_FUN score or an expected exclusion.")
    add_check(checks, "cfun_token_mismatch_occurrences", occurrence_diag["token_mismatch_occurrences"] == 0, occurrence_diag["token_mismatch_occurrences"], 0, "A05 occurrence token counts must match the frozen A13/A14 unique-unit token counts.")
    add_check(checks, "cfun_snapshot_missing_occurrences", occurrence_diag["snapshot_missing_occurrences"] == 0, occurrence_diag["snapshot_missing_occurrences"], 0, "All C_FUN occurrences must belong to A05 snapshots.")

    file_scores_path = args.output_dir / "python_cfun_file_npr_scores.csv"
    file_diag = write_file_scores(file_manifest_path, accumulators, file_scores_path)
    add_check(checks, "a05_python_file_rows", file_diag["file_manifest_rows"] == args.expected_python_files, file_diag["file_manifest_rows"], args.expected_python_files, "A15 must emit one snapshot/file row for every A05 Python-file manifest row.")
    add_check(checks, "orphan_cfun_file_keys", file_diag["orphan_cfun_file_keys"] == 0, file_diag["orphan_cfun_file_keys"], 0, "Every A05 primary method_body occurrence must resolve to an A05 file-manifest row.")
    add_check(checks, "file_unexpected_missing_scores", file_diag["files_with_unexpected_missing_cfun_score"] == 0, file_diag["files_with_unexpected_missing_cfun_score"], 0, "No file may contain an unexpected missing C_FUN score.")

    repo_month_scores_path = args.output_dir / "python_cfun_repo_month_file_npr_scores.csv"
    repo_month_diag = write_repo_month_file_scores(file_scores_path, repo_month_mapping, repo_month_scores_path)
    add_check(checks, "repo_month_file_unmapped_snapshot_rows", repo_month_diag["snapshot_file_rows_without_panel_mapping"] == 0, repo_month_diag["snapshot_file_rows_without_panel_mapping"], 0, "Every snapshot/file result must map to at least one authoritative Model A repo-month row.")
    add_check(checks, "repo_months_represented", repo_month_diag["repo_months_represented"] == args.expected_repo_month_rows, repo_month_diag["repo_months_represented"], args.expected_repo_month_rows, "Expanded file output must represent every fixed Model A repo-month row.")
    add_check(checks, "repo_month_file_rows", repo_month_diag["repo_month_file_rows"] == args.expected_repo_month_file_rows, repo_month_diag["repo_month_file_rows"], args.expected_repo_month_file_rows, "C_FUN repo-month/file expansion must preserve the same A05 file universe and Model A mapping as A12.")

    output_columns = FILE_OUTPUT_COLUMNS + REPO_MONTH_OUTPUT_COLUMNS
    prohibited_tokens = ("threshold", "agc", "hwc", "classification", "likely_ai")
    prohibited_columns = sorted({column for column in output_columns if any(token in column.casefold() for token in prohibited_tokens)})
    add_check(checks, "no_threshold_or_classification_columns", not prohibited_columns, prohibited_columns, [], "A15 freezes continuous C_FUN NPR only; thresholding/classification is downstream.")

    hard_failures = [row for row in checks if row["severity"] == "hard" and not row["passed"]]
    if args.strict_expected_counts and hard_failures:
        status = "FAIL"
    elif hard_failures:
        status = "PASS_WITH_QC_WARNINGS"
    elif occurrence_diag["expected_exclusion_occurrences"] > 0:
        status = "PASS_WITH_EXPECTED_EXCLUSIONS"
    else:
        status = "PASS"

    checks_path = args.output_dir / "python_cfun_aggregation_checks.csv"
    atomic_csv_rows(checks, checks_path, CHECK_COLUMNS)

    summary = {
        "status": status,
        "script_version": SCRIPT_VERSION,
        "scope": "C_FUN-only file NPR from primary method_body occurrences",
        "started_utc": started,
        "completed_utc": utc_now(),
        "a05_code_manifest_sha256": code_manifest_sha,
        "a13": {
            "status": a13_summary.get("status"),
            "script_version": a13_summary.get("script_version"),
            "cfun_unique_unit_memberships": len(a13_units),
            "a11_reuse_sha": len(reuse_plan),
        },
        "a14": a14_diag,
        "a11_reuse": a11_diag,
        "combined": {
            "finite_unique_sha": len(scores),
            "excluded_unique_sha": len(exclusions),
            "union_unique_sha": len(combined_universe),
        },
        "repo_month_panel": panel_diag,
        "occurrences": occurrence_diag,
        "files": file_diag,
        "repo_month_files": repo_month_diag,
        "hard_check_failures": len(hard_failures),
        "hard_check_failure_names": [row["check_name"] for row in hard_failures],
        "methodology": {
            "category": "C_FUN = A05 primary method_body occurrences",
            "unique_score_expansion": "A14 new-C_FUN scores plus A13-directed A11 finite/exclusion reuse are expanded by code_unit_sha256 to every matching A05 method occurrence before file aggregation",
            "a11_reuse_boundary": "A13 python_cfun_reuse_from_a11.csv is authoritative; A15 does not rediscover overlap or rescore reused SHA values",
            "multi_membership_policy": "C_FUN/method_body membership is tested by membership inclusion, never exact comma-separated string equality",
            "file_weighting": "space-by-token weighted across class-method occurrences",
            "pooled_component_npr": "weighted mean perturbed log-rank divided by weighted mean original log-rank over finite C_FUN occurrences",
            "no_cfun_policy": "missing C_FUN coverage; file_npr_cfun is blank, never zero",
            "expected_exclusion_policy": "expected A11/A14 exclusions are propagated to occurrence/file coverage and are never imputed",
            "repo_month_mapping": "authoritative Model A repo-month panel via dataset_source + repo_name + latest_commit_effective; no month-range inference",
            "classification": "disabled; no threshold, AGC/HWC, or AI-likely labels are produced",
        },
        "outputs": {
            "snapshot_file_scores": str(file_scores_path),
            "repo_month_file_scores": str(repo_month_scores_path),
            "occurrence_exclusions": str(occurrence_exclusions_path),
            "a11_reuse_occurrences": str(reuse_occurrences_path),
            "checks": str(checks_path),
        },
    }
    atomic_json(summary, args.output_dir / "summary.json")

    input_hashes: dict[str, Any] = {
        "a05_root": str(args.a05_root),
        "a11_results_root": str(args.a11_results_root),
        "a13_root": str(args.a13_root),
        "a14_results_root": str(args.a14_results_root),
        "repo_month_panel_file": str(args.repo_month_panel_file),
        "a05_snapshot_manifest_sha256": sha256_file(snapshot_manifest_path),
        "a05_file_manifest_sha256": sha256_file(file_manifest_path),
        "a05_code_manifest_sha256": code_manifest_sha,
        "a13_summary_sha256": sha256_file(args.a13_root / "summary.json"),
        "a13_workload_units_sha256": sha256_file(args.a13_root / "python_cfun_workload_units.csv"),
        "a13_reuse_plan_sha256": sha256_file(args.a13_root / "python_cfun_reuse_from_a11.csv"),
        "repo_month_panel_sha256": sha256_file(args.repo_month_panel_file),
    }
    for gpu_index in gpu_indexes:
        input_hashes[f"a14_gpu{gpu_index}_unique_scores_sha256"] = sha256_file(args.a14_results_root / f"gpu-{gpu_index}" / "python_cfun_new_unique_code_unit_npr_scores.csv")
        input_hashes[f"a14_gpu{gpu_index}_exclusions_sha256"] = sha256_file(args.a14_results_root / f"gpu-{gpu_index}" / "python_cfun_new_npr_exclusions.csv")
        input_hashes[f"a14_gpu{gpu_index}_summary_sha256"] = sha256_file(args.a14_results_root / f"gpu-{gpu_index}" / "summary.json")
        input_hashes[f"a11_gpu{gpu_index}_unique_scores_sha256"] = sha256_file(args.a11_results_root / f"gpu-{gpu_index}" / "python_fun_unique_code_unit_npr_scores.csv")
        input_hashes[f"a11_gpu{gpu_index}_exclusions_sha256"] = sha256_file(args.a11_results_root / f"gpu-{gpu_index}" / "python_fun_npr_exclusions.csv")
        input_hashes[f"a11_gpu{gpu_index}_summary_sha256"] = sha256_file(args.a11_results_root / f"gpu-{gpu_index}" / "summary.json")
    atomic_json(
        {
            "script_version": SCRIPT_VERSION,
            "inputs": input_hashes,
            "frozen_provenance": {
                "a09_config_fingerprint": EXPECTED_A09_CONFIG_FINGERPRINT,
                "a02_config_fingerprint": EXPECTED_A02_CONFIG_FINGERPRINT,
                "model_revision": EXPECTED_MODEL_REVISION,
            },
            "created_utc": utc_now(),
        },
        args.output_dir / "metadata.json",
    )

    print("=" * 80)
    print("run-x-a15 C_FUN file NPR aggregation")
    print(f"Status:                                  {status}")
    print(f"A05 snapshots:                           {len(snapshots_by_id)}")
    print(f"A05 Python files:                        {file_diag['file_manifest_rows']}")
    print(f"A05 primary code-unit occurrences:       {occurrence_diag['a05_primary_code_unit_occurrences']}")
    print(f"C_FUN occurrences:                       {occurrence_diag['cfun_occurrences']}")
    print(f"C_FUN unique SHA memberships:            {occurrence_diag['cfun_unique_sha']}")
    print(f"Finite A14 new C_FUN units:              {len(a14_scores)}")
    print(f"Finite A11 reused C_FUN units:           {len(a11_scores)}")
    print(f"Expected-excluded A11 reused C_FUN units:{len(a11_exclusions):>12}")
    print(f"Expected exclusion occurrences:          {occurrence_diag['expected_exclusion_occurrences']}")
    print(f"A11 reuse occurrences:                   {occurrence_diag['a11_reuse_occurrences']}")
    print(f"Files with C_FUN:                         {occurrence_diag['files_with_cfun']}")
    print(f"Files with finite C_FUN NPR:              {file_diag['files_with_finite_cfun_npr']}")
    print(f"Files with no C_FUN:                      {file_diag['files_with_no_cfun']}")
    print(f"Repo-month rows represented:              {repo_month_diag['repo_months_represented']}")
    print(f"Repo-month/file output rows:              {repo_month_diag['repo_month_file_rows']}")
    print(f"Repo-month/file rows finite C_FUN NPR:    {repo_month_diag['repo_month_file_rows_with_finite_cfun_npr']}")
    print(f"Hard QC failures:                         {len(hard_failures)}")
    print(f"Snapshot/file output:                     {file_scores_path}")
    print(f"Repo-month/file output:                   {repo_month_scores_path}")
    print(f"Occurrence exclusions:                    {occurrence_exclusions_path}")
    print(f"A11 reuse occurrence audit:               {reuse_occurrences_path}")
    print("=" * 80)

    return 0 if status in {"PASS", "PASS_WITH_EXPECTED_EXCLUSIONS"} else 5


if __name__ == "__main__":
    raise SystemExit(main())
