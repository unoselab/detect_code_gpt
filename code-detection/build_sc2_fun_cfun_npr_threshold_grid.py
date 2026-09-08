#!/usr/bin/env python3
"""Build and audit the combined FUN+C_FUN historical NPR detector.

Scientific contract
-------------------
- Inputs are the frozen A12 FUN and A15 C_FUN repo-month/file continuous NPR artifacts.
- FUN and C_FUN are combined before thresholding using scored space-by-token counts.
- Primary metric: file_npr_fun_cfun_space_by_token_weighted.
- If only one category has finite NPR, the combined NPR equals that category NPR.
- If neither category has finite NPR, combined NPR is missing, never zero.
- No cross-category SHA deduplication is performed; semantic category occurrences are retained.
- Primary threshold comes from C01 and uses the strict rule NPR > threshold.
- The 21-point sensitivity grid is T +/- 0.50 in 0.05 increments.
- 1.5183 and 1.571637 are audit anchors only.
- No quality or SonarQube outcome is consumed.

Outputs
-------
- python_fun_cfun_repo_month_file_npr_scores.csv
- fun_cfun_npr_threshold_spec.csv
- fun_cfun_npr_threshold_audit.csv
- fun_cfun_npr_threshold_by_treatment_timing.csv
- fun_cfun_npr_threshold_repo_month_audit.csv
- fun_cfun_npr_distribution_summary.csv
- fun_cfun_npr_threshold_checks.csv
- summary.json
- metadata.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCRIPT_VERSION = "run-x-c04-v2"
METRIC_COLUMN = "file_npr_fun_cfun_space_by_token_weighted"
COMPARISON_OPERATOR = ">"
DEFAULT_PRIMARY_THRESHOLD = Decimal("1.515059")
DEFAULT_GRID_STEP = Decimal("0.05")
DEFAULT_GRID_RADIUS = Decimal("0.50")
DEFAULT_LEGACY_THRESHOLD = Decimal("1.5183")
DEFAULT_PRIOR_PRIMARY_THRESHOLD = Decimal("1.571637")
EXPECTED_SCORING_MODEL = "bigcode/starcoder2-7b"
EXPECTED_MODEL_REVISION = "bb9afde76d7945da5745592525db122d4d729eb1"
EXPECTED_A12_SHA256 = "0fcd6b4dfacdf6e013d834667cbe742b60fa3cff30ef7d53a432690a7791523c"
EXPECTED_A15_SHA256 = "93ecedf72ce75aacfb2b2139a2b3123a5cb6ae36ce68c1d7522ffdd578aec7e1"
EXPECTED_A12_SUMMARY_SHA256 = "25ab2a6858c18f9adfa03cab78432215870e0d725ed5ffc62b96dbdf30a74f97"
EXPECTED_A15_SUMMARY_SHA256 = "19e5486cdae1570e392664fe1b289b035d28f1513834d2434e59705c6a006d75"
EXPECTED_A05_MANIFEST_SHA256 = "1acb3726f5c62e6154672f1aff592973c65a13e58dbfd37f8058560d1a474e6c"

COMMON_COLUMNS = [
    "repo_id", "dataset_source", "repo_name", "repo_month", "time_index", "event",
    "event_index", "snapshot_id", "snapshot_commit", "relative_path", "file_sha256",
    "python_lines", "parse_status",
]
FUN_COLUMNS = {
    "fun_occurrences_total", "fun_occurrences_scored", "fun_occurrences_excluded",
    "fun_space_by_tokens_total", "fun_space_by_tokens_scored", "fun_space_by_tokens_excluded",
    "fun_npr_coverage_ratio", "file_npr_fun_space_by_token_weighted",
    "file_fun_original_log_rank_space_by_token_weighted",
    "file_fun_mean_perturbed_log_rank_space_by_token_weighted", "file_npr_fun_status",
}
CFUN_COLUMNS = {
    "cfun_occurrences_total", "cfun_occurrences_scored", "cfun_occurrences_excluded",
    "cfun_space_by_tokens_total", "cfun_space_by_tokens_scored", "cfun_space_by_tokens_excluded",
    "cfun_npr_coverage_ratio", "file_npr_cfun_space_by_token_weighted",
    "file_cfun_original_log_rank_space_by_token_weighted",
    "file_cfun_mean_perturbed_log_rank_space_by_token_weighted", "file_npr_cfun_status",
}

COMBINED_OUTPUT_COLUMNS = COMMON_COLUMNS + [
    "fun_occurrences_total", "fun_occurrences_scored", "fun_occurrences_excluded",
    "fun_space_by_tokens_total", "fun_space_by_tokens_scored", "fun_space_by_tokens_excluded",
    "fun_npr_coverage_ratio", "file_npr_fun_space_by_token_weighted", "file_npr_fun_status",
    "cfun_occurrences_total", "cfun_occurrences_scored", "cfun_occurrences_excluded",
    "cfun_space_by_tokens_total", "cfun_space_by_tokens_scored", "cfun_space_by_tokens_excluded",
    "cfun_npr_coverage_ratio", "file_npr_cfun_space_by_token_weighted", "file_npr_cfun_status",
    "fun_cfun_occurrences_total", "fun_cfun_occurrences_scored", "fun_cfun_occurrences_excluded",
    "fun_cfun_space_by_tokens_total", "fun_cfun_space_by_tokens_scored", "fun_cfun_space_by_tokens_excluded",
    "fun_cfun_npr_coverage_ratio", METRIC_COLUMN,
    "file_fun_cfun_original_log_rank_space_by_token_weighted",
    "file_fun_cfun_mean_perturbed_log_rank_space_by_token_weighted",
    "file_npr_fun_cfun_pooled_components", "file_npr_fun_cfun_status",
]

THRESHOLD_SPEC_COLUMNS = [
    "threshold_id", "threshold_role", "grid_order", "delta_from_primary",
    "threshold", "comparison_operator", "metric", "note",
]
CHECK_COLUMNS = ["check_name", "severity", "passed", "observed", "expected", "note"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def parse_int(value: Any, label: str) -> int:
    text = clean(value)
    if text == "":
        raise ValueError(f"Missing integer: {label}")
    return int(text)


def parse_float(value: Any, label: str, allow_blank: bool = False) -> float | None:
    text = clean(value)
    if text == "" and allow_blank:
        return None
    if text == "":
        raise ValueError(f"Missing float: {label}")
    value_f = float(text)
    if not math.isfinite(value_f):
        raise ValueError(f"Non-finite float: {label}={text}")
    return value_f


def parse_decimal(value: Any, label: str, allow_blank: bool = False) -> Decimal | None:
    text = clean(value)
    if text == "" and allow_blank:
        return None
    if text == "":
        raise ValueError(f"Missing decimal: {label}")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal: {label}={text}") from exc
    if not result.is_finite():
        raise ValueError(f"Non-finite decimal: {label}={text}")
    return result


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def finite_text(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return ""
    return repr(float(value))


def require_columns(path: Path, required: set[str], label: str) -> None:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
    if header is None:
        raise ValueError(f"Empty CSV: {path}")
    missing = sorted(required - set(header))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def atomic_csv_rows(rows: Iterable[Mapping[str, Any]], path: Path, columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with temp_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(columns), extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def atomic_json(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with temp_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


@dataclass(frozen=True)
class ThresholdSpec:
    threshold_id: str
    threshold_role: str
    grid_order: int | str
    delta: Decimal
    threshold: Decimal
    note: str

    def as_row(self) -> dict[str, Any]:
        return {
            "threshold_id": self.threshold_id,
            "threshold_role": self.threshold_role,
            "grid_order": self.grid_order,
            "delta_from_primary": decimal_text(self.delta),
            "threshold": decimal_text(self.threshold),
            "comparison_operator": COMPARISON_OPERATOR,
            "metric": METRIC_COLUMN,
            "note": self.note,
        }


def build_threshold_specs(primary: Decimal, step: Decimal, radius: Decimal,
                          legacy: Decimal, prior: Decimal) -> list[ThresholdSpec]:
    if radius % step != 0:
        raise ValueError("grid radius must be divisible by grid step")
    half = int(radius / step)
    specs: list[ThresholdSpec] = []
    for offset in range(-half, half + 1):
        delta = step * offset
        threshold = primary + delta
        if offset == 0:
            threshold_id, role, note = "primary", "primary", "Frozen C01 pooled SC2-7B primary threshold"
        elif offset < 0:
            threshold_id, role, note = f"grid_m{abs(offset) * 5:03d}", "sensitivity_grid", "Symmetric sensitivity threshold"
        else:
            threshold_id, role, note = f"grid_p{offset * 5:03d}", "sensitivity_grid", "Symmetric sensitivity threshold"
        specs.append(ThresholdSpec(threshold_id, role, offset + half, delta, threshold, note))
    specs.append(ThresholdSpec("legacy_15183", "legacy_anchor", "", legacy - primary, legacy,
                               "Legacy pre-overlap benchmark threshold; audit comparator only"))
    specs.append(ThresholdSpec("prior_primary_1571637", "prior_primary_anchor", "", prior - primary, prior,
                               "Previous paper primary threshold; audit comparator only"))
    return specs


def normalized_stratum(time_index: int, event_index: int) -> str:
    if event_index <= 0:
        return "control"
    return "treatment_post" if time_index >= event_index else "treatment_pre"


def event_time_normalized(time_index: int, event_index: int) -> int | None:
    return None if event_index <= 0 else time_index - event_index


def safe_ratio(num: int, den: int) -> float | str:
    return "" if den == 0 else num / den


def percentile(values: Sequence[float], q: float) -> float | str:
    if not values:
        return ""
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return values[lo]
    return values[lo] * (hi - pos) + values[hi] * (pos - lo)


def validate_branch_summary(path: Path, branch: str) -> dict[str, Any]:
    payload = load_json(path)
    if payload.get("hard_check_failures") != 0:
        raise ValueError(f"{branch} summary hard_check_failures != 0")
    c01 = payload.get("c01", {})
    if clean(c01.get("scoring_model")) != EXPECTED_SCORING_MODEL:
        raise ValueError(f"{branch} C01 scoring model mismatch")
    if Decimal(str(c01.get("threshold"))) != DEFAULT_PRIMARY_THRESHOLD:
        raise ValueError(f"{branch} C01 threshold mismatch")
    text = json.dumps(payload, sort_keys=True)
    if EXPECTED_MODEL_REVISION not in text:
        raise ValueError(f"{branch} summary does not preserve expected historical model revision")
    return payload


def validate_upstream_summary(path: Path, expected_version: str, label: str) -> dict[str, Any]:
    payload = load_json(path)
    if clean(payload.get("script_version")) != expected_version:
        raise ValueError(f"{label} script version mismatch: {payload.get('script_version')!r}")
    if payload.get("hard_check_failures") != 0:
        raise ValueError(f"{label} hard_check_failures != 0")
    status = clean(payload.get("status"))
    if status not in {"PASS", "PASS_WITH_EXPECTED_EXCLUSIONS"}:
        raise ValueError(f"{label} unsuccessful status: {status}")
    if clean(payload.get("a05_code_manifest_sha256")) != EXPECTED_A05_MANIFEST_SHA256:
        raise ValueError(f"{label} A05 manifest SHA mismatch")
    return payload


def combine_value(fun_npr: float | None, fun_w: int, cfun_npr: float | None, cfun_w: int) -> float | None:
    numerator = 0.0
    denominator = 0
    if fun_npr is not None:
        if fun_w <= 0:
            raise ValueError("Finite FUN NPR has non-positive scored weight")
        numerator += fun_w * fun_npr
        denominator += fun_w
    if cfun_npr is not None:
        if cfun_w <= 0:
            raise ValueError("Finite C_FUN NPR has non-positive scored weight")
        numerator += cfun_w * cfun_npr
        denominator += cfun_w
    return None if denominator == 0 else numerator / denominator


def combine_rows(fun_path: Path, cfun_path: Path, output_path: Path) -> dict[str, Any]:
    require_columns(fun_path, set(COMMON_COLUMNS) | FUN_COLUMNS, "A12 FUN input")
    require_columns(cfun_path, set(COMMON_COLUMNS) | CFUN_COLUMNS, "A15 C_FUN input")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    finite_fun = finite_cfun = finite_combined = 0
    pattern_counts = defaultdict(int)
    status_counts = defaultdict(int)
    row_key_mismatch = 0
    unexpected_missing = 0

    with fun_path.open("r", encoding="utf-8", newline="") as f_fun, \
         cfun_path.open("r", encoding="utf-8", newline="") as f_cfun, \
         output_path.open("w", encoding="utf-8", newline="") as f_out:
        fun_reader = csv.DictReader(f_fun)
        cfun_reader = csv.DictReader(f_cfun)
        writer = csv.DictWriter(f_out, fieldnames=COMBINED_OUTPUT_COLUMNS)
        writer.writeheader()

        while True:
            try:
                fr = next(fun_reader)
            except StopIteration:
                fr = None
            try:
                cr = next(cfun_reader)
            except StopIteration:
                cr = None
            if fr is None and cr is None:
                break
            if fr is None or cr is None:
                raise ValueError("A12/A15 row counts differ")
            total += 1
            for col in COMMON_COLUMNS:
                if clean(fr[col]) != clean(cr[col]):
                    row_key_mismatch += 1
                    raise ValueError(f"A12/A15 row alignment mismatch at row {total}, column {col}")

            fun_npr = parse_float(fr["file_npr_fun_space_by_token_weighted"], f"FUN NPR row {total}", True)
            cfun_npr = parse_float(cr["file_npr_cfun_space_by_token_weighted"], f"C_FUN NPR row {total}", True)
            fun_w = parse_int(fr["fun_space_by_tokens_scored"], f"FUN scored weight row {total}")
            cfun_w = parse_int(cr["cfun_space_by_tokens_scored"], f"C_FUN scored weight row {total}")
            fun_total = parse_int(fr["fun_space_by_tokens_total"], f"FUN total weight row {total}")
            cfun_total = parse_int(cr["cfun_space_by_tokens_total"], f"C_FUN total weight row {total}")
            fun_exc = parse_int(fr["fun_space_by_tokens_excluded"], f"FUN excluded weight row {total}")
            cfun_exc = parse_int(cr["cfun_space_by_tokens_excluded"], f"C_FUN excluded weight row {total}")

            combined_npr = combine_value(fun_npr, fun_w, cfun_npr, cfun_w)
            combined_total = fun_total + cfun_total
            combined_scored = fun_w + cfun_w
            combined_excluded = fun_exc + cfun_exc
            coverage = None if combined_total == 0 else combined_scored / combined_total

            fun_orig = parse_float(fr["file_fun_original_log_rank_space_by_token_weighted"], "FUN original", True)
            cfun_orig = parse_float(cr["file_cfun_original_log_rank_space_by_token_weighted"], "C_FUN original", True)
            fun_pert = parse_float(fr["file_fun_mean_perturbed_log_rank_space_by_token_weighted"], "FUN perturbed", True)
            cfun_pert = parse_float(cr["file_cfun_mean_perturbed_log_rank_space_by_token_weighted"], "C_FUN perturbed", True)
            combined_orig = combine_value(fun_orig, fun_w if fun_orig is not None else 0, cfun_orig, cfun_w if cfun_orig is not None else 0)
            combined_pert = combine_value(fun_pert, fun_w if fun_pert is not None else 0, cfun_pert, cfun_w if cfun_pert is not None else 0)
            pooled = None
            if combined_orig is not None and combined_pert is not None and combined_orig != 0:
                pooled = combined_pert / combined_orig

            fun_status = clean(fr["file_npr_fun_status"])
            cfun_status = clean(cr["file_npr_cfun_status"])
            if fun_status == "file_not_prepared" and cfun_status == "file_not_prepared":
                status = "file_not_prepared"
            elif combined_npr is not None:
                status = "scored_with_expected_exclusions" if (coverage is not None and coverage < 1.0 - 1e-12) else "scored"
            elif combined_total == 0:
                status = "no_fun_cfun"
            else:
                status = "fun_cfun_all_excluded"

            if fun_npr is not None:
                finite_fun += 1
            if cfun_npr is not None:
                finite_cfun += 1
            if combined_npr is not None:
                finite_combined += 1
            if fun_npr is not None and cfun_npr is not None:
                pattern_counts["fun_and_cfun"] += 1
            elif fun_npr is not None:
                pattern_counts["fun_only"] += 1
            elif cfun_npr is not None:
                pattern_counts["cfun_only"] += 1
            else:
                pattern_counts["neither"] += 1
            status_counts[status] += 1
            if combined_npr is None and status in {"scored", "scored_with_expected_exclusions"}:
                unexpected_missing += 1

            row = {col: fr[col] for col in COMMON_COLUMNS}
            for col in [
                "fun_occurrences_total", "fun_occurrences_scored", "fun_occurrences_excluded",
                "fun_space_by_tokens_total", "fun_space_by_tokens_scored", "fun_space_by_tokens_excluded",
                "fun_npr_coverage_ratio", "file_npr_fun_space_by_token_weighted", "file_npr_fun_status",
            ]:
                row[col] = fr[col]
            for col in [
                "cfun_occurrences_total", "cfun_occurrences_scored", "cfun_occurrences_excluded",
                "cfun_space_by_tokens_total", "cfun_space_by_tokens_scored", "cfun_space_by_tokens_excluded",
                "cfun_npr_coverage_ratio", "file_npr_cfun_space_by_token_weighted", "file_npr_cfun_status",
            ]:
                row[col] = cr[col]
            row.update({
                "fun_cfun_occurrences_total": parse_int(fr["fun_occurrences_total"], "fun occurrences") + parse_int(cr["cfun_occurrences_total"], "cfun occurrences"),
                "fun_cfun_occurrences_scored": parse_int(fr["fun_occurrences_scored"], "fun scored occurrences") + parse_int(cr["cfun_occurrences_scored"], "cfun scored occurrences"),
                "fun_cfun_occurrences_excluded": parse_int(fr["fun_occurrences_excluded"], "fun excluded occurrences") + parse_int(cr["cfun_occurrences_excluded"], "cfun excluded occurrences"),
                "fun_cfun_space_by_tokens_total": combined_total,
                "fun_cfun_space_by_tokens_scored": combined_scored,
                "fun_cfun_space_by_tokens_excluded": combined_excluded,
                "fun_cfun_npr_coverage_ratio": finite_text(coverage),
                METRIC_COLUMN: finite_text(combined_npr),
                "file_fun_cfun_original_log_rank_space_by_token_weighted": finite_text(combined_orig),
                "file_fun_cfun_mean_perturbed_log_rank_space_by_token_weighted": finite_text(combined_pert),
                "file_npr_fun_cfun_pooled_components": finite_text(pooled),
                "file_npr_fun_cfun_status": status,
            })
            writer.writerow(row)

    return {
        "rows": total,
        "finite_fun": finite_fun,
        "finite_cfun": finite_cfun,
        "finite_combined": finite_combined,
        "pattern_counts": dict(sorted(pattern_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "row_key_mismatch": row_key_mismatch,
        "unexpected_missing": unexpected_missing,
    }


def audit_combined(path: Path, specs: list[ThresholdSpec]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    required = set(COMMON_COLUMNS) | {METRIC_COLUMN, "fun_cfun_npr_coverage_ratio", "file_npr_fun_cfun_status"}
    require_columns(path, required, "C04 combined input")
    n = len(specs)
    selected = [0] * n
    selected_partial = [0] * n
    selected_repos = [set() for _ in specs]
    selected_repo_months = [set() for _ in specs]
    equal_counts = [0] * n
    unique: dict[tuple[str, str, str], Decimal | None] = {}
    repo_group: dict[str, bool] = {}
    repo_month_meta: dict[tuple[str, str], tuple[str, str, int, int, str]] = {}
    rm_total = defaultdict(int); rm_eligible = defaultdict(int); rm_partial = defaultdict(int)
    rm_selected = {spec.threshold_id: defaultdict(int) for spec in specs}
    group_names = ["all", "control", "treatment_pre", "treatment_post", "treatment_all"]
    g_total = defaultdict(int); g_eligible = defaultdict(int)
    g_selected = {spec.threshold_id: defaultdict(int) for spec in specs}
    distributions = defaultdict(list)
    status_counts = defaultdict(int)
    total_rows = eligible = partial_rows = 0

    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            total_rows += 1
            repo_id = clean(row["repo_id"]); repo_month = clean(row["repo_month"])
            source = clean(row["dataset_source"]); repo_name = clean(row["repo_name"])
            time_index = parse_int(row["time_index"], "time_index"); event_index = parse_int(row["event_index"], "event_index")
            stratum = normalized_stratum(time_index, event_index)
            treatment = event_index > 0
            if repo_id in repo_group and repo_group[repo_id] != treatment:
                raise ValueError(f"Repository treatment identity changed: {repo_id}")
            repo_group[repo_id] = treatment
            rm_key = (repo_id, repo_month)
            meta = (source, repo_name, time_index, event_index, stratum)
            if rm_key in repo_month_meta and repo_month_meta[rm_key] != meta:
                raise ValueError(f"Repo-month metadata mismatch: {rm_key}")
            repo_month_meta[rm_key] = meta
            rm_total[rm_key] += 1
            names = ["all", stratum] + (["treatment_all"] if treatment else [])
            for name in names:
                g_total[name] += 1

            status = clean(row["file_npr_fun_cfun_status"]); status_counts[status] += 1
            npr = parse_decimal(row[METRIC_COLUMN], METRIC_COLUMN, True)
            coverage = parse_float(row["fun_cfun_npr_coverage_ratio"], "coverage", True)
            snapshot_key = (clean(row["snapshot_id"]), clean(row["relative_path"]), clean(row["file_sha256"]).casefold())
            prior = unique.get(snapshot_key, "__missing__")
            if prior != "__missing__" and prior != npr:
                raise ValueError(f"Repeated snapshot/file has inconsistent combined NPR: {snapshot_key}")
            unique[snapshot_key] = npr
            if npr is None:
                continue
            eligible += 1; rm_eligible[rm_key] += 1
            is_partial = coverage is not None and coverage < 1.0 - 1e-12
            if is_partial:
                partial_rows += 1; rm_partial[rm_key] += 1
            for name in names:
                g_eligible[name] += 1; distributions[name].append(float(npr))
            for i, spec in enumerate(specs):
                if npr == spec.threshold:
                    equal_counts[i] += 1
                if npr > spec.threshold:
                    selected[i] += 1; selected_repos[i].add(repo_id); selected_repo_months[i].add(rm_key)
                    rm_selected[spec.threshold_id][rm_key] += 1
                    if is_partial:
                        selected_partial[i] += 1
                    for name in names:
                        g_selected[spec.threshold_id][name] += 1

    unique_eligible = [v for v in unique.values() if isinstance(v, Decimal)]
    unique_selected = [sum(1 for v in unique_eligible if v > spec.threshold) for spec in specs]
    global_rows = []
    for i, spec in enumerate(specs):
        global_rows.append(spec.as_row() | {
            "repo_month_file_rows_total": total_rows,
            "eligible_finite_fun_cfun_rows": eligible,
            "ineligible_rows": total_rows - eligible,
            "selected_file_rows": selected[i],
            "selected_share_of_eligible": safe_ratio(selected[i], eligible),
            "selected_share_of_all_python_rows": safe_ratio(selected[i], total_rows),
            "eligible_full_coverage_rows": eligible - partial_rows,
            "eligible_partial_coverage_rows": partial_rows,
            "selected_full_coverage_rows": selected[i] - selected_partial[i],
            "selected_partial_coverage_rows": selected_partial[i],
            "unique_snapshot_files_total": len(unique),
            "eligible_unique_snapshot_files": len(unique_eligible),
            "selected_unique_snapshot_files": unique_selected[i],
            "selected_unique_snapshot_file_share": safe_ratio(unique_selected[i], len(unique_eligible)),
            "repositories_with_selected_files": len(selected_repos[i]),
            "repo_months_with_selected_files": len(selected_repo_months[i]),
        })

    group_rows = []
    for spec in specs:
        for name in group_names:
            group_rows.append(spec.as_row() | {
                "stratum": name,
                "repo_month_file_rows_total": g_total[name],
                "eligible_finite_fun_cfun_rows": g_eligible[name],
                "selected_file_rows": g_selected[spec.threshold_id][name],
                "selected_share_of_eligible": safe_ratio(g_selected[spec.threshold_id][name], g_eligible[name]),
                "selected_share_of_all_python_rows": safe_ratio(g_selected[spec.threshold_id][name], g_total[name]),
            })

    repo_month_rows = []
    for spec in specs:
        for rm_key in sorted(repo_month_meta):
            repo_id, repo_month = rm_key
            source, repo_name, time_index, event_index, stratum = repo_month_meta[rm_key]
            selected_rm = rm_selected[spec.threshold_id][rm_key]
            repo_month_rows.append(spec.as_row() | {
                "repo_id": repo_id, "dataset_source": source, "repo_name": repo_name, "repo_month": repo_month,
                "time_index": time_index, "event_index": event_index,
                "event_time_normalized": "" if event_index <= 0 else time_index - event_index,
                "treatment_group": 1 if event_index > 0 else 0,
                "absorbing_treated": 1 if event_index > 0 and time_index >= event_index else 0,
                "repo_month_file_rows_total": rm_total[rm_key],
                "eligible_finite_fun_cfun_rows": rm_eligible[rm_key],
                "selected_file_rows": selected_rm,
                "selected_share_of_eligible": safe_ratio(selected_rm, rm_eligible[rm_key]),
                "selected_share_of_all_python_rows": safe_ratio(selected_rm, rm_total[rm_key]),
                "eligible_partial_coverage_rows": rm_partial[rm_key],
            })

    distribution_rows = []
    for scope, values in [(name, distributions[name]) for name in group_names] + [("unique_snapshot_file", [float(v) for v in unique_eligible])]:
        distribution_rows.append({
            "scope": scope, "n": len(values),
            "mean": "" if not values else statistics.fmean(values),
            "sd": "" if len(values) < 2 else statistics.stdev(values),
            "min": "" if not values else min(values), "p25": percentile(values, 0.25),
            "median": percentile(values, 0.5), "p75": percentile(values, 0.75),
            "max": "" if not values else max(values),
        })

    rm_strata = defaultdict(int)
    for _, _, _, _, stratum in repo_month_meta.values(): rm_strata[stratum] += 1
    diagnostics = {
        "input_rows": total_rows, "eligible_finite_fun_cfun_rows": eligible,
        "unique_snapshot_files": len(unique), "eligible_unique_snapshot_files": len(unique_eligible),
        "repo_months": len(repo_month_meta), "repositories": len(repo_group),
        "control_repositories": sum(1 for v in repo_group.values() if not v),
        "treatment_repositories": sum(1 for v in repo_group.values() if v),
        "repo_month_group_counts": {
            "control": rm_strata["control"], "treatment_pre": rm_strata["treatment_pre"],
            "treatment_post": rm_strata["treatment_post"],
        },
        "status_counts": dict(sorted(status_counts.items())),
        "eligible_partial_coverage_rows": partial_rows,
        "rows_equal_threshold": {spec.threshold_id: equal_counts[i] for i, spec in enumerate(specs)},
    }
    return diagnostics, global_rows, group_rows, repo_month_rows, distribution_rows


def add_check(rows: list[dict[str, Any]], name: str, passed: bool, observed: Any, expected: Any, note: str) -> None:
    rows.append({"check_name": name, "severity": "hard", "passed": 1 if passed else 0,
                 "observed": observed if not isinstance(observed, (dict, list)) else json.dumps(observed, sort_keys=True),
                 "expected": expected if not isinstance(expected, (dict, list)) else json.dumps(expected, sort_keys=True),
                 "note": note})


def add_selection_reconciliation_checks(
    checks: list[dict[str, Any]],
    diag: Mapping[str, Any],
    globals_: list[dict[str, Any]],
    group_rows: list[dict[str, Any]],
    repo_month_rows: list[dict[str, Any]],
    specs: list[ThresholdSpec],
) -> None:
    """Add hard checks that reconcile every threshold across audit views.

    The global selected count must equal both (1) the sum of the mutually
    exclusive control/treatment-pre/treatment-post strata and (2) the sum of
    selected counts across all repo-month rows. Exact NPR equality with any
    frozen threshold is also required to be zero for this production artifact,
    making the strict ``NPR > threshold`` boundary fully auditable.
    """
    global_by_id = {clean(row["threshold_id"]): row for row in globals_}

    groups_by_threshold: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in group_rows:
        groups_by_threshold[clean(row["threshold_id"])][clean(row["stratum"])] = row

    required_strata = ("control", "treatment_pre", "treatment_post")
    for spec in specs:
        rows = groups_by_threshold.get(spec.threshold_id, {})
        missing = [name for name in required_strata if name not in rows]
        global_selected = int(global_by_id[spec.threshold_id]["selected_file_rows"])
        if missing:
            add_check(
                checks,
                f"group_selected_reconcile::{spec.threshold_id}",
                False,
                {"missing_strata": missing},
                global_selected,
                "Control + treatment-pre + treatment-post selected rows must equal the global selected count.",
            )
        else:
            selected_sum = sum(int(rows[name]["selected_file_rows"]) for name in required_strata)
            add_check(
                checks,
                f"group_selected_reconcile::{spec.threshold_id}",
                selected_sum == global_selected,
                selected_sum,
                global_selected,
                "Control + treatment-pre + treatment-post selected rows must equal the global selected count.",
            )

    repo_month_selected: dict[str, int] = defaultdict(int)
    for row in repo_month_rows:
        repo_month_selected[clean(row["threshold_id"])] += int(row["selected_file_rows"])
    for spec in specs:
        global_selected = int(global_by_id[spec.threshold_id]["selected_file_rows"])
        observed = repo_month_selected[spec.threshold_id]
        add_check(
            checks,
            f"repo_month_selected_reconcile::{spec.threshold_id}",
            observed == global_selected,
            observed,
            global_selected,
            "Summed repo-month selected rows must equal the global selected count.",
        )

    equal_counts = {spec.threshold_id: int(diag["rows_equal_threshold"].get(spec.threshold_id, 0)) for spec in specs}
    add_check(
        checks,
        "rows_equal_threshold_all_zero",
        all(value == 0 for value in equal_counts.values()),
        equal_counts,
        {spec.threshold_id: 0 for spec in specs},
        "No frozen combined NPR row may equal any audited threshold in this production artifact; strict > boundary handling remains explicit.",
    )


def make_checks(
    combine: dict[str, Any],
    diag: dict[str, Any],
    globals_: list[dict[str, Any]],
    group_rows: list[dict[str, Any]],
    repo_month_rows: list[dict[str, Any]],
    specs: list[ThresholdSpec],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    expected = {
        "rows": 510297, "finite_fun": 204508, "finite_cfun": 202027, "finite_combined": 359057,
        "unique_snapshot_files": 494592, "eligible_unique_snapshot_files": 347173,
        "repo_months": 1954, "repositories": 167, "control_repositories": 104,
        "treatment_repositories": 63, "control_repo_months": 1040,
        "treatment_pre_repo_months": 551, "treatment_post_repo_months": 363,
    }
    add_check(checks, "threshold_grid_count", len([s for s in specs if s.threshold_role in {"primary", "sensitivity_grid"}]) == 21, 21, 21, "Main grid count")
    add_check(checks, "threshold_total_count_with_anchors", len(specs) == 23, len(specs), 23, "21-point grid plus two audit anchors")
    add_check(checks, "combined_rows", combine["rows"] == expected["rows"], combine["rows"], expected["rows"], "A12/A15 row reconciliation")
    add_check(checks, "finite_fun_rows", combine["finite_fun"] == expected["finite_fun"], combine["finite_fun"], expected["finite_fun"], "Frozen A12 finite count")
    add_check(checks, "finite_cfun_rows", combine["finite_cfun"] == expected["finite_cfun"], combine["finite_cfun"], expected["finite_cfun"], "Frozen A15 finite count")
    add_check(checks, "finite_combined_rows", combine["finite_combined"] == expected["finite_combined"], combine["finite_combined"], expected["finite_combined"], "Frozen I01 combined finite count")
    add_check(checks, "combined_pattern_counts", combine["pattern_counts"] == {"cfun_only":154549,"fun_and_cfun":47478,"fun_only":157030,"neither":151240}, combine["pattern_counts"], {"cfun_only":154549,"fun_and_cfun":47478,"fun_only":157030,"neither":151240}, "Must reproduce prior I01 finite patterns")
    add_check(checks, "combined_status_counts", combine["status_counts"] == {"file_not_prepared":298,"fun_cfun_all_excluded":409,"no_fun_cfun":150533,"scored":357370,"scored_with_expected_exclusions":1687}, combine["status_counts"], {"file_not_prepared":298,"fun_cfun_all_excluded":409,"no_fun_cfun":150533,"scored":357370,"scored_with_expected_exclusions":1687}, "Must reproduce prior I01 status counts")
    add_check(checks, "row_key_mismatch", combine["row_key_mismatch"] == 0, combine["row_key_mismatch"], 0, "A12/A15 keys must align exactly")
    for key in ["unique_snapshot_files","eligible_unique_snapshot_files","repo_months","repositories","control_repositories","treatment_repositories"]:
        add_check(checks, key, diag[key] == expected[key], diag[key], expected[key], "Frozen combined sample invariant")
    for name, key in [("control_repo_months","control"),("treatment_pre_repo_months","treatment_pre"),("treatment_post_repo_months","treatment_post")]:
        observed = diag["repo_month_group_counts"][key]
        add_check(checks, name, observed == expected[name], observed, expected[name], "Frozen repo-month timing invariant")
    main = [r for r in globals_ if r["threshold_role"] in {"primary", "sensitivity_grid"}]
    counts = [int(r["selected_file_rows"]) for r in main]
    add_check(checks, "grid_selected_count_monotone", all(a >= b for a,b in zip(counts, counts[1:])), counts, "non-increasing", "Selected count must weakly decrease with threshold")
    for anchor_id in ["legacy_15183", "prior_primary_1571637"]:
        anchor = next(r for r in globals_ if r["threshold_id"] == anchor_id)
        t = Decimal(str(anchor["threshold"])); s = int(anchor["selected_file_rows"])
        lower = max((r for r in main if Decimal(str(r["threshold"])) <= t), key=lambda r: Decimal(str(r["threshold"])))
        upper = min((r for r in main if Decimal(str(r["threshold"])) >= t), key=lambda r: Decimal(str(r["threshold"])))
        ok = int(lower["selected_file_rows"]) >= s >= int(upper["selected_file_rows"])
        add_check(checks, f"{anchor_id}_selected_count_bracket", ok,
                  {"anchor":s,"lower":int(lower["selected_file_rows"]),"upper":int(upper["selected_file_rows"])}, "bracketed", "Anchor must be bracketed by adjacent grid thresholds")

    add_selection_reconciliation_checks(checks, diag, globals_, group_rows, repo_month_rows, specs)
    return checks


def self_test() -> None:
    assert combine_value(2.0, 10, 1.0, 30) == 1.25
    assert combine_value(2.0, 10, None, 0) == 2.0
    assert combine_value(None, 0, None, 0) is None
    specs = build_threshold_specs(DEFAULT_PRIMARY_THRESHOLD, DEFAULT_GRID_STEP, DEFAULT_GRID_RADIUS, DEFAULT_LEGACY_THRESHOLD, DEFAULT_PRIOR_PRIMARY_THRESHOLD)
    assert len(specs) == 23
    assert sum(1 for s in specs if s.threshold_id == "primary") == 1

    # Exercise the v2 reconciliation logic with a minimal threshold view.
    test_spec = [ThresholdSpec("test", "primary", 0, Decimal("0"), Decimal("1.5"), "self-test")]
    test_checks: list[dict[str, Any]] = []
    test_diag = {"rows_equal_threshold": {"test": 0}}
    test_globals = [{"threshold_id": "test", "selected_file_rows": 6}]
    test_groups = [
        {"threshold_id": "test", "stratum": "control", "selected_file_rows": 1},
        {"threshold_id": "test", "stratum": "treatment_pre", "selected_file_rows": 2},
        {"threshold_id": "test", "stratum": "treatment_post", "selected_file_rows": 3},
    ]
    test_repo_months = [
        {"threshold_id": "test", "selected_file_rows": 4},
        {"threshold_id": "test", "selected_file_rows": 2},
    ]
    add_selection_reconciliation_checks(
        test_checks, test_diag, test_globals, test_groups, test_repo_months, test_spec
    )
    assert len(test_checks) == 3
    assert all(int(row["passed"]) == 1 for row in test_checks)
    print("build_sc2_fun_cfun_npr_threshold_grid self-test: PASS")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--a12-input", type=Path)
    p.add_argument("--a12-summary", type=Path)
    p.add_argument("--a15-input", type=Path)
    p.add_argument("--a15-summary", type=Path)
    p.add_argument("--c02-summary", type=Path)
    p.add_argument("--c03-summary", type=Path)
    p.add_argument("--c01-spec", type=Path)
    p.add_argument("--c01-summary", type=Path)
    p.add_argument("--output-dir", type=Path)
    p.add_argument("--primary-threshold", type=Decimal, default=DEFAULT_PRIMARY_THRESHOLD)
    p.add_argument("--grid-step", type=Decimal, default=DEFAULT_GRID_STEP)
    p.add_argument("--grid-radius", type=Decimal, default=DEFAULT_GRID_RADIUS)
    p.add_argument("--legacy-threshold", type=Decimal, default=DEFAULT_LEGACY_THRESHOLD)
    p.add_argument("--prior-primary-threshold", type=Decimal, default=DEFAULT_PRIOR_PRIMARY_THRESHOLD)
    p.add_argument("--strict-expected-counts", action="store_true")
    p.add_argument("--self-test", action="store_true")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test(); return 0
    required_paths = [args.a12_input,args.a12_summary,args.a15_input,args.a15_summary,args.c02_summary,args.c03_summary,args.c01_spec,args.c01_summary,args.output_dir]
    if any(p is None for p in required_paths):
        raise SystemExit("All production input/output arguments are required")
    started = utc_now()

    if args.strict_expected_counts:
        expected_hashes = [(args.a12_input,EXPECTED_A12_SHA256),(args.a15_input,EXPECTED_A15_SHA256),(args.a12_summary,EXPECTED_A12_SUMMARY_SHA256),(args.a15_summary,EXPECTED_A15_SUMMARY_SHA256)]
        for path, expected in expected_hashes:
            observed = sha256_file(path)
            if observed != expected:
                raise ValueError(f"Frozen SHA mismatch for {path}: {observed} != {expected}")

    a12 = validate_upstream_summary(args.a12_summary, "run-x-a12-v2", "A12")
    a15 = validate_upstream_summary(args.a15_summary, "run-x-a15-v1", "A15")
    c02 = validate_branch_summary(args.c02_summary, "C02")
    c03 = validate_branch_summary(args.c03_summary, "C03")
    c01_spec = load_json(args.c01_spec); c01_summary = load_json(args.c01_summary)
    if Decimal(str(c01_spec.get("agc_threshold"))) != args.primary_threshold:
        raise ValueError("C01 threshold specification does not match requested C04 primary threshold")
    if clean(c01_spec.get("scoring_model")) != EXPECTED_SCORING_MODEL:
        raise ValueError("C01 scoring model mismatch")
    if c01_summary.get("hard_failed_checks") != 0:
        raise ValueError("C01 calibration hard checks failed")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    combined_path = args.output_dir / "python_fun_cfun_repo_month_file_npr_scores.csv"
    combine_diag = combine_rows(args.a12_input, args.a15_input, combined_path)
    specs = build_threshold_specs(args.primary_threshold,args.grid_step,args.grid_radius,args.legacy_threshold,args.prior_primary_threshold)
    diag, global_rows, group_rows, repo_month_rows, dist_rows = audit_combined(combined_path, specs)
    checks = make_checks(combine_diag, diag, global_rows, group_rows, repo_month_rows, specs)
    failures = [r for r in checks if int(r["passed"]) == 0]

    spec_path = args.output_dir / "fun_cfun_npr_threshold_spec.csv"
    audit_path = args.output_dir / "fun_cfun_npr_threshold_audit.csv"
    group_path = args.output_dir / "fun_cfun_npr_threshold_by_treatment_timing.csv"
    rm_path = args.output_dir / "fun_cfun_npr_threshold_repo_month_audit.csv"
    dist_path = args.output_dir / "fun_cfun_npr_distribution_summary.csv"
    checks_path = args.output_dir / "fun_cfun_npr_threshold_checks.csv"
    atomic_csv_rows((s.as_row() for s in specs), spec_path, THRESHOLD_SPEC_COLUMNS)
    atomic_csv_rows(global_rows, audit_path, list(global_rows[0].keys()))
    atomic_csv_rows(group_rows, group_path, list(group_rows[0].keys()))
    atomic_csv_rows(repo_month_rows, rm_path, list(repo_month_rows[0].keys()))
    atomic_csv_rows(dist_rows, dist_path, list(dist_rows[0].keys()))
    atomic_csv_rows(checks, checks_path, CHECK_COLUMNS)

    primary = next(r for r in global_rows if r["threshold_id"] == "primary")
    legacy = next(r for r in global_rows if r["threshold_id"] == "legacy_15183")
    prior = next(r for r in global_rows if r["threshold_id"] == "prior_primary_1571637")
    summary = {
        "script_version": SCRIPT_VERSION,
        "status": "PASS" if not failures else "FAIL",
        "started_utc": started, "completed_utc": utc_now(),
        "hard_check_failures": len(failures), "hard_check_failure_names": [r["check_name"] for r in failures],
        "scope": "combined FUN + C_FUN procedure-body file NPR",
        "methodology": {
            "primary_metric": METRIC_COLUMN,
            "combined_weighting": "scored space-by-token weighted recomputation across finite FUN and C_FUN category NPR values",
            "single_category_policy": "if exactly one category has finite NPR, combined NPR equals that category NPR",
            "no_coverage_policy": "if neither category has finite NPR, combined NPR is blank, never zero",
            "cross_category_sha_policy": "semantic occurrences retained; no cross-category SHA deduplication",
            "decision_rule": "NPR > threshold",
            "quality_outcomes": "not consumed",
        },
        "threshold": {
            "source": "run-x-c01-v1", "primary": float(args.primary_threshold),
            "legacy": float(args.legacy_threshold), "prior_primary": float(args.prior_primary_threshold),
            "grid_step": float(args.grid_step), "grid_radius": float(args.grid_radius),
        },
        "combine": combine_diag, "audit": diag,
        "primary_result": primary, "legacy_result": legacy, "prior_primary_result": prior,
        "delta_selected_vs_prior_primary": int(primary["selected_file_rows"]) - int(prior["selected_file_rows"]),
        "inputs": {
            "a12_input": str(args.a12_input), "a12_input_sha256": sha256_file(args.a12_input),
            "a15_input": str(args.a15_input), "a15_input_sha256": sha256_file(args.a15_input),
            "c02_summary": str(args.c02_summary), "c02_summary_sha256": sha256_file(args.c02_summary),
            "c03_summary": str(args.c03_summary), "c03_summary_sha256": sha256_file(args.c03_summary),
            "c01_spec": str(args.c01_spec), "c01_spec_sha256": sha256_file(args.c01_spec),
        },
    }
    metadata = {
        "script_version": SCRIPT_VERSION, "created_utc": utc_now(),
        "scoring_model": EXPECTED_SCORING_MODEL, "historical_model_revision": EXPECTED_MODEL_REVISION,
        "a05_code_manifest_sha256": EXPECTED_A05_MANIFEST_SHA256,
        "a12_script_version": a12.get("script_version"), "a15_script_version": a15.get("script_version"),
        "c02_script_version": c02.get("script_version"), "c03_script_version": c03.get("script_version"),
        "c01_script_version": c01_spec.get("script_version"),
        "output_combined_sha256": sha256_file(combined_path),
    }
    atomic_json(summary, args.output_dir / "summary.json")
    atomic_json(metadata, args.output_dir / "metadata.json")

    print("=" * 80)
    print("run-x-c04 combined FUN+C_FUN NPR build + threshold-grid audit")
    print(f"Status:                              {summary['status']}")
    print(f"Input repo-month/file rows:          {diag['input_rows']}")
    print(f"Finite FUN / C_FUN / combined:       {combine_diag['finite_fun']} / {combine_diag['finite_cfun']} / {combine_diag['finite_combined']}")
    print(f"Eligible unique snapshot/files:      {diag['eligible_unique_snapshot_files']}")
    print(f"Repositories / repo-months:          {diag['repositories']} / {diag['repo_months']}")
    print(f"Primary threshold:                   {decimal_text(args.primary_threshold)}")
    print(f"Primary selected rows:               {primary['selected_file_rows']}")
    print(f"Legacy selected rows @ 1.5183:       {legacy['selected_file_rows']}")
    print(f"Prior primary rows @ 1.571637:       {prior['selected_file_rows']}")
    print(f"Delta selected vs prior primary:     {summary['delta_selected_vs_prior_primary']}")
    print(f"Hard QC failures:                    {len(failures)}")
    print(f"Combined continuous output:          {combined_path}")
    print(f"Threshold audit:                     {audit_path}")
    print("=" * 80)
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
