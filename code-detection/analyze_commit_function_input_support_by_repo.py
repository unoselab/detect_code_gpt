#!/usr/bin/env python3
"""Analyze repository-level concentration in detector eligibility retention.

This run-1b2 analysis is a pre-scoring diagnostic. It determines whether the
retention-rate differences observed between treatment and control events are
broadly distributed across repositories or driven by a small number of
high-volume repositories.

The script does not load a language model, calculate NPR, classify AGC/HWC,
aggregate repository-month outcomes, or run difference-in-differences models.

Statistical input unit:
    One prepared commit-function change event from run-1a.

Repository diagnostic unit:
    One repository within one detector eligibility specification.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


EVENT_REQUIRED = {
    "function_event_id",
    "dataset_source",
    "repo_name",
    "function_body_split_space_token_count",
    "input_preparation_complete",
    "body_extraction_status",
}

SUPPORT_REQUIRED = {
    "spec_name",
    "spec_role",
    "minimum_literal_space_tokens",
    "maximum_literal_space_tokens",
    "eligible_event_rows",
}

CHECK_COLUMNS = ["check_name", "passed", "observed", "expected", "note"]


@dataclass(frozen=True)
class EligibilitySpec:
    """One detector-specific implementation-body eligibility rule."""

    name: str
    role: str
    min_tokens: int
    max_tokens: int | None

    def mask(self, token_count: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(token_count, errors="coerce")
        selected = numeric.ge(self.min_tokens)
        if self.max_tokens is not None:
            selected &= numeric.le(self.max_tokens)
        return selected.fillna(False)


@dataclass(frozen=True)
class AnalysisPaths:
    input_events: Path
    input_support: Path
    input_specification: Path
    output_dir: Path
    qc_dir: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze repository-level concentration in perturbation-detector "
            "eligibility retention before NPR scoring."
        )
    )
    parser.add_argument(
        "--input-events",
        type=Path,
        default=Path(
            "output/commit_function/run-1a/strict/"
            "commit_function_detectcodegpt_input_events.csv"
        ),
    )
    parser.add_argument(
        "--input-support",
        type=Path,
        default=Path(
            "output/commit_function/run-1b/strict/"
            "commit_function_body_eligibility_support.csv"
        ),
    )
    parser.add_argument(
        "--input-specification",
        type=Path,
        default=Path(
            "output/commit_function/run-1b/strict/"
            "commit_function_detectcodegpt_scoring_spec.json"
        ),
        help=(
            "Frozen or provisional run-1b specification JSON. The file is read "
            "only to recover pre-outcome eligibility definitions and metadata."
        ),
    )
    parser.add_argument(
        "--analysis-specs",
        default="min100,range100_200",
        help="Comma-separated specification names to analyze.",
    )
    parser.add_argument(
        "--top-n-values",
        default="1,5,10",
        help=(
            "Comma-separated positive repository counts for concentration and "
            "leave-top-repositories-out diagnostics."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/commit_function/run-1b2/strict"),
    )
    parser.add_argument(
        "--qc-dir",
        type=Path,
        default=None,
        help="Defaults to <output-dir>/qc.",
    )
    parser.add_argument("--expected-prepared-events", type=int, default=449547)
    parser.add_argument(
        "--expected-dataset-sources",
        default="treatment,control",
        help="Comma-separated expected dataset_source values.",
    )
    parser.add_argument("--overwrite-output", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False, quoting=csv.QUOTE_MINIMAL)
    os.replace(temporary, path)


def atomic_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def read_csv_checked(path: Path, required: set[str], label: str) -> pd.DataFrame:
    require_file(path, label)
    frame = pd.read_csv(path, dtype=str, low_memory=False)
    require_columns(frame, required, label)
    return frame


def normalize_bool(series: pd.Series) -> pd.Series:
    truthy = {"1", "1.0", "true", "t", "yes", "y"}
    falsy = {"0", "0.0", "false", "f", "no", "n", "", "nan", "none"}

    def convert(value: Any) -> bool | None:
        text = str(value).strip().lower()
        if text in truthy:
            return True
        if text in falsy:
            return False
        return None

    return series.map(convert).astype("boolean")


def parse_csv_list(raw: str) -> list[str]:
    values = [item.strip() for item in str(raw).split(",") if item.strip()]
    if not values:
        raise ValueError("At least one value is required.")
    return values


def parse_top_n_values(raw: str) -> list[int]:
    values = sorted({int(item) for item in parse_csv_list(raw)})
    if any(value <= 0 for value in values):
        raise ValueError("All --top-n-values must be positive integers.")
    return values


def parse_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return int(float(text))


def load_specifications(
    specification_path: Path,
    requested_names: list[str],
) -> tuple[list[EligibilitySpec], dict[str, Any]]:
    require_file(specification_path, "run-1b specification")
    payload = json.loads(specification_path.read_text(encoding="utf-8"))
    definitions = payload.get("eligibility_specifications")
    if not isinstance(definitions, list):
        raise ValueError(
            "Specification JSON does not contain eligibility_specifications."
        )

    available: dict[str, EligibilitySpec] = {}
    for item in definitions:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        available[name] = EligibilitySpec(
            name=name,
            role=str(item.get("role", "unspecified")),
            min_tokens=int(item["minimum_literal_space_tokens"]),
            max_tokens=parse_optional_int(item.get("maximum_literal_space_tokens")),
        )

    missing = [name for name in requested_names if name not in available]
    if missing:
        raise ValueError(
            f"Requested specifications are absent from the JSON: {missing}; "
            f"available={sorted(available)}"
        )

    return [available[name] for name in requested_names], payload


def prepare_events(events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    out["function_event_id"] = out["function_event_id"].fillna("").astype(str).str.strip()
    out["dataset_source"] = (
        out["dataset_source"].fillna("").astype(str).str.strip().str.lower()
    )
    out["repo_name"] = out["repo_name"].fillna("").astype(str).str.strip()
    out["input_preparation_complete"] = normalize_bool(
        out["input_preparation_complete"]
    )
    prepared_mask = (
        out["body_extraction_status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("prepared")
        & out["input_preparation_complete"].fillna(False)
    )
    out = out.loc[prepared_mask].copy()
    out["function_body_split_space_token_count"] = pd.to_numeric(
        out["function_body_split_space_token_count"], errors="coerce"
    )
    return out


def gini(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    if array.size == 0:
        return math.nan
    if np.any(array < 0):
        raise ValueError("Gini values must be non-negative.")
    total = float(array.sum())
    if total == 0:
        return 0.0
    ordered = np.sort(array)
    index = np.arange(1, ordered.size + 1, dtype=float)
    return float(
        (2.0 * np.sum(index * ordered) / (ordered.size * total))
        - ((ordered.size + 1.0) / ordered.size)
    )


def hhi(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    total = float(array.sum())
    if array.size == 0 or total == 0:
        return math.nan
    shares = array / total
    return float(np.square(shares).sum())


def top_n_share(values: pd.Series, n: int) -> float:
    numeric = pd.to_numeric(values, errors="coerce").fillna(0)
    total = float(numeric.sum())
    if total == 0:
        return math.nan
    return float(numeric.nlargest(min(n, len(numeric))).sum() / total)


def quantile_or_nan(series: pd.Series, probability: float) -> float:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    return float(numeric.quantile(probability)) if len(numeric) else math.nan


def build_repository_table(
    prepared: pd.DataFrame,
    specs: list[EligibilitySpec],
) -> pd.DataFrame:
    base = (
        prepared.groupby(["dataset_source", "repo_name"], dropna=False)
        .agg(total_prepared_events=("function_event_id", "size"))
        .reset_index()
    )

    rows: list[pd.DataFrame] = []
    cohort_totals = base.groupby("dataset_source")["total_prepared_events"].sum()
    all_total = int(base["total_prepared_events"].sum())

    for spec in specs:
        event_copy = prepared[["dataset_source", "repo_name", "function_event_id"]].copy()
        event_copy["eligible"] = spec.mask(
            prepared["function_body_split_space_token_count"]
        ).astype(int)
        eligible = (
            event_copy.groupby(["dataset_source", "repo_name"], dropna=False)
            .agg(eligible_events=("eligible", "sum"))
            .reset_index()
        )
        table = base.merge(
            eligible,
            on=["dataset_source", "repo_name"],
            how="left",
            validate="one_to_one",
        )
        table["eligible_events"] = table["eligible_events"].fillna(0).astype(int)
        table["ineligible_events"] = (
            table["total_prepared_events"] - table["eligible_events"]
        )
        table["retention_rate"] = (
            table["eligible_events"] / table["total_prepared_events"]
        )
        table["total_event_share_within_cohort"] = table.apply(
            lambda row: row["total_prepared_events"] / cohort_totals[row["dataset_source"]],
            axis=1,
        )
        eligible_cohort_totals = table.groupby("dataset_source")["eligible_events"].sum()
        table["eligible_event_share_within_cohort"] = table.apply(
            lambda row: (
                row["eligible_events"] / eligible_cohort_totals[row["dataset_source"]]
                if eligible_cohort_totals[row["dataset_source"]] > 0
                else math.nan
            ),
            axis=1,
        )
        table["total_event_share_all_repositories"] = (
            table["total_prepared_events"] / all_total if all_total else math.nan
        )
        table["zero_eligible_repository"] = table["eligible_events"].eq(0)
        table.insert(2, "spec_name", spec.name)
        table.insert(3, "spec_role", spec.role)
        table.insert(4, "minimum_literal_space_tokens", spec.min_tokens)
        table.insert(5, "maximum_literal_space_tokens", spec.max_tokens)
        rows.append(table)

    out = pd.concat(rows, ignore_index=True)
    return out.sort_values(
        ["spec_name", "dataset_source", "total_prepared_events", "repo_name"],
        ascending=[True, True, False, True],
    ).reset_index(drop=True)


def build_retention_summary(
    repository_table: pd.DataFrame,
    top_n_values: list[int],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = [
        "spec_name",
        "spec_role",
        "minimum_literal_space_tokens",
        "maximum_literal_space_tokens",
        "dataset_source",
    ]
    for keys, group in repository_table.groupby(group_columns, dropna=False):
        spec_name, spec_role, minimum, maximum, source = keys
        retention = pd.to_numeric(group["retention_rate"], errors="coerce")
        total_events = int(group["total_prepared_events"].sum())
        eligible_events = int(group["eligible_events"].sum())
        row: dict[str, Any] = {
            "spec_name": spec_name,
            "spec_role": spec_role,
            "minimum_literal_space_tokens": minimum,
            "maximum_literal_space_tokens": maximum,
            "dataset_source": source,
            "repositories": int(len(group)),
            "total_prepared_events": total_events,
            "eligible_events": eligible_events,
            "event_weighted_retention_rate": (
                eligible_events / total_events if total_events else math.nan
            ),
            "repository_unweighted_mean_retention_rate": float(retention.mean()),
            "repository_median_retention_rate": float(retention.median()),
            "repository_retention_std": float(retention.std(ddof=1)),
            "repository_retention_q1": quantile_or_nan(retention, 0.25),
            "repository_retention_q3": quantile_or_nan(retention, 0.75),
            "repository_retention_iqr": (
                quantile_or_nan(retention, 0.75) - quantile_or_nan(retention, 0.25)
            ),
            "repository_retention_min": float(retention.min()),
            "repository_retention_max": float(retention.max()),
            "zero_eligible_repositories": int(group["zero_eligible_repository"].sum()),
            "zero_eligible_repository_share": float(
                group["zero_eligible_repository"].mean()
            ),
            "prepared_event_gini": gini(group["total_prepared_events"]),
            "eligible_event_gini": gini(group["eligible_events"]),
            "prepared_event_hhi": hhi(group["total_prepared_events"]),
            "eligible_event_hhi": hhi(group["eligible_events"]),
        }
        for n in top_n_values:
            row[f"top{n}_prepared_event_share"] = top_n_share(
                group["total_prepared_events"], n
            )
            row[f"top{n}_eligible_event_share"] = top_n_share(
                group["eligible_events"], n
            )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["spec_name", "dataset_source"])


def build_top_repository_table(
    repository_table: pd.DataFrame,
    top_n_values: list[int],
) -> pd.DataFrame:
    maximum_n = max(top_n_values)
    rows: list[dict[str, Any]] = []
    for (spec_name, source), group in repository_table.groupby(
        ["spec_name", "dataset_source"], dropna=False
    ):
        for metric in ("total_prepared_events", "eligible_events"):
            ordered = group.sort_values([metric, "repo_name"], ascending=[False, True]).copy()
            metric_total = float(ordered[metric].sum())
            ordered = ordered.head(maximum_n)
            cumulative = 0.0
            for rank, row in enumerate(ordered.itertuples(index=False), start=1):
                value = float(getattr(row, metric))
                share = value / metric_total if metric_total else math.nan
                cumulative += 0.0 if math.isnan(share) else share
                rows.append(
                    {
                        "spec_name": spec_name,
                        "dataset_source": source,
                        "ranking_metric": metric,
                        "rank": rank,
                        "repo_name": row.repo_name,
                        "total_prepared_events": int(row.total_prepared_events),
                        "eligible_events": int(row.eligible_events),
                        "retention_rate": float(row.retention_rate),
                        "metric_value": int(value),
                        "metric_share_within_cohort": share,
                        "cumulative_metric_share_within_cohort": cumulative,
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["spec_name", "dataset_source", "ranking_metric", "rank"]
    )


def weighted_retention(group: pd.DataFrame) -> float:
    total = int(group["total_prepared_events"].sum())
    eligible = int(group["eligible_events"].sum())
    return eligible / total if total else math.nan


def summarize_gap(
    table: pd.DataFrame,
    spec_name: str,
    removal_mode: str,
    top_n_removed: int,
) -> dict[str, Any]:
    treatment = table.loc[table["dataset_source"].eq("treatment")]
    control = table.loc[table["dataset_source"].eq("control")]

    treatment_weighted = weighted_retention(treatment)
    control_weighted = weighted_retention(control)
    treatment_unweighted = float(treatment["retention_rate"].mean())
    control_unweighted = float(control["retention_rate"].mean())

    return {
        "spec_name": spec_name,
        "removal_mode": removal_mode,
        "top_n_removed": top_n_removed,
        "treatment_repositories": int(len(treatment)),
        "control_repositories": int(len(control)),
        "treatment_total_prepared_events": int(treatment["total_prepared_events"].sum()),
        "control_total_prepared_events": int(control["total_prepared_events"].sum()),
        "treatment_eligible_events": int(treatment["eligible_events"].sum()),
        "control_eligible_events": int(control["eligible_events"].sum()),
        "treatment_event_weighted_retention_rate": treatment_weighted,
        "control_event_weighted_retention_rate": control_weighted,
        "event_weighted_retention_gap_treatment_minus_control": (
            treatment_weighted - control_weighted
        ),
        "treatment_repository_unweighted_mean_retention_rate": treatment_unweighted,
        "control_repository_unweighted_mean_retention_rate": control_unweighted,
        "repository_unweighted_mean_gap_treatment_minus_control": (
            treatment_unweighted - control_unweighted
        ),
    }


def build_leave_top_out_table(
    repository_table: pd.DataFrame,
    top_n_values: list[int],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec_name, spec_table in repository_table.groupby("spec_name", dropna=False):
        rows.append(summarize_gap(spec_table, spec_name, "none", 0))

        for n in top_n_values:
            # Remove the largest N repositories independently within each cohort.
            within_parts: list[pd.DataFrame] = []
            for _, cohort in spec_table.groupby("dataset_source", dropna=False):
                drop_index = cohort.nlargest(
                    min(n, len(cohort)), "total_prepared_events"
                ).index
                within_parts.append(cohort.drop(index=drop_index))
            within = pd.concat(within_parts, ignore_index=False)
            rows.append(
                summarize_gap(within, spec_name, "within_cohort_by_prepared_events", n)
            )

            # Remove the largest N repositories across treatment and control together.
            global_drop = spec_table.nlargest(
                min(n, len(spec_table)), "total_prepared_events"
            ).index
            global_table = spec_table.drop(index=global_drop)
            rows.append(
                summarize_gap(global_table, spec_name, "global_by_prepared_events", n)
            )

    return pd.DataFrame(rows).sort_values(
        ["spec_name", "removal_mode", "top_n_removed"]
    )


def build_zero_eligible_table(repository_table: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "dataset_source",
        "repo_name",
        "spec_name",
        "spec_role",
        "total_prepared_events",
        "eligible_events",
        "retention_rate",
        "total_event_share_within_cohort",
    ]
    return (
        repository_table.loc[repository_table["zero_eligible_repository"], columns]
        .sort_values(["spec_name", "dataset_source", "total_prepared_events"], ascending=[True, True, False])
        .reset_index(drop=True)
    )


def support_expected_map(support: pd.DataFrame) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in support.itertuples(index=False):
        result[str(row.spec_name)] = int(float(row.eligible_event_rows))
    return result


def make_checks(
    all_events: pd.DataFrame,
    prepared: pd.DataFrame,
    repository_table: pd.DataFrame,
    specs: list[EligibilitySpec],
    support: pd.DataFrame,
    expected_prepared_events: int,
    expected_sources: list[str],
) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, observed: Any, expected: Any, note: str) -> None:
        checks.append(
            {
                "check_name": name,
                "passed": bool(passed),
                "observed": observed,
                "expected": expected,
                "note": note,
            }
        )

    add(
        "prepared_event_rows_match_expected",
        len(prepared) == expected_prepared_events,
        len(prepared),
        expected_prepared_events,
        "run-1b2 must analyze the same prepared event population as run-1b.",
    )
    add(
        "prepared_event_ids_unique",
        prepared["function_event_id"].is_unique,
        int(prepared["function_event_id"].duplicated().sum()),
        0,
        "Each prepared commit-function event must appear once.",
    )
    add(
        "prepared_event_keys_nonempty",
        prepared["repo_name"].ne("").all() and prepared["dataset_source"].ne("").all(),
        int(prepared["repo_name"].eq("").sum() + prepared["dataset_source"].eq("").sum()),
        0,
        "Repository and cohort keys are required for concentration analysis.",
    )
    observed_sources = sorted(prepared["dataset_source"].unique().tolist())
    add(
        "dataset_sources_match_expected",
        observed_sources == sorted(expected_sources),
        observed_sources,
        sorted(expected_sources),
        "The diagnostic compares the treatment and control cohorts only.",
    )
    add(
        "literal_space_token_counts_present",
        prepared["function_body_split_space_token_count"].notna().all(),
        int(prepared["function_body_split_space_token_count"].isna().sum()),
        0,
        "Every prepared body must have a detector-specific size measure.",
    )

    expected_eligible = support_expected_map(support)
    for spec in specs:
        spec_rows = repository_table.loc[repository_table["spec_name"].eq(spec.name)]
        observed_total = int(spec_rows["total_prepared_events"].sum())
        observed_eligible = int(spec_rows["eligible_events"].sum())
        direct_eligible = int(spec.mask(prepared["function_body_split_space_token_count"]).sum())

        add(
            f"{spec.name}_repository_totals_match_prepared_events",
            observed_total == len(prepared),
            observed_total,
            len(prepared),
            "Repository groups must reconcile to the full prepared event population.",
        )
        add(
            f"{spec.name}_eligible_events_match_direct_mask",
            observed_eligible == direct_eligible,
            observed_eligible,
            direct_eligible,
            "Repository aggregation must preserve the direct eligibility count.",
        )
        add(
            f"{spec.name}_eligible_events_match_run1b_support",
            spec.name in expected_eligible and observed_eligible == expected_eligible[spec.name],
            observed_eligible,
            expected_eligible.get(spec.name, "missing"),
            "run-1b2 must reproduce the frozen pre-scoring run-1b support count.",
        )
        add(
            f"{spec.name}_repository_rows_unique",
            not spec_rows.duplicated(["dataset_source", "repo_name"]).any(),
            int(spec_rows.duplicated(["dataset_source", "repo_name"]).sum()),
            0,
            "One row is required per repository and specification.",
        )

    add(
        "all_input_rows_accounted_for",
        len(all_events) >= len(prepared),
        len(all_events),
        f">={len(prepared)}",
        "The run-1a input may include explicit exclusions in addition to prepared events.",
    )
    return pd.DataFrame(checks, columns=CHECK_COLUMNS)


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    qc_dir = args.qc_dir or args.output_dir / "qc"
    paths = AnalysisPaths(
        input_events=args.input_events,
        input_support=args.input_support,
        input_specification=args.input_specification,
        output_dir=args.output_dir,
        qc_dir=qc_dir,
    )

    for path, label in (
        (paths.input_events, "run-1a event output"),
        (paths.input_support, "run-1b eligibility support"),
        (paths.input_specification, "run-1b specification"),
    ):
        require_file(path, label)

    if paths.output_dir.exists() and any(paths.output_dir.iterdir()):
        if not args.overwrite_output:
            raise FileExistsError(
                f"Output directory is not empty: {paths.output_dir}. "
                "Use --overwrite-output to replace it."
            )
        shutil.rmtree(paths.output_dir)
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.qc_dir.mkdir(parents=True, exist_ok=True)

    all_events = read_csv_checked(paths.input_events, EVENT_REQUIRED, "run-1a events")
    support = read_csv_checked(paths.input_support, SUPPORT_REQUIRED, "run-1b support")
    requested_specs = parse_csv_list(args.analysis_specs)
    top_n_values = parse_top_n_values(args.top_n_values)
    expected_sources = [item.lower() for item in parse_csv_list(args.expected_dataset_sources)]
    specs, specification_payload = load_specifications(
        paths.input_specification, requested_specs
    )
    prepared = prepare_events(all_events)

    repository_table = build_repository_table(prepared, specs)
    retention_summary = build_retention_summary(repository_table, top_n_values)
    top_repositories = build_top_repository_table(repository_table, top_n_values)
    leave_top_out = build_leave_top_out_table(repository_table, top_n_values)
    zero_eligible = build_zero_eligible_table(repository_table)

    checks = make_checks(
        all_events=all_events,
        prepared=prepared,
        repository_table=repository_table,
        specs=specs,
        support=support,
        expected_prepared_events=args.expected_prepared_events,
        expected_sources=expected_sources,
    )
    failed_checks = int((~checks["passed"].astype(bool)).sum())
    status = "PASS" if failed_checks == 0 else "FAIL"

    output_files = {
        "repository_table": paths.output_dir
        / "commit_function_eligibility_by_repository.csv",
        "retention_summary": paths.output_dir
        / "commit_function_repository_retention_summary.csv",
        "concentration_summary": paths.output_dir
        / "commit_function_repository_concentration_summary.csv",
        "leave_top_out": paths.output_dir
        / "commit_function_retention_gap_leave_top_repos_out.csv",
        "zero_eligible": paths.output_dir
        / "commit_function_zero_eligible_repositories.csv",
        "checks": paths.qc_dir
        / "commit_function_repository_support_checks.csv",
        "summary": paths.qc_dir
        / "commit_function_repository_support_summary.json",
        "metadata": paths.qc_dir
        / "commit_function_repository_support_metadata.json",
    }

    # The concentration file contains the ranked repositories used to interpret
    # top-N shares and the leave-top-repositories-out sensitivity analysis.
    atomic_csv(repository_table, output_files["repository_table"])
    atomic_csv(retention_summary, output_files["retention_summary"])
    atomic_csv(top_repositories, output_files["concentration_summary"])
    atomic_csv(leave_top_out, output_files["leave_top_out"])
    atomic_csv(zero_eligible, output_files["zero_eligible"])
    atomic_csv(checks, output_files["checks"])

    input_hashes = {
        "input_events_sha256": sha256_file(paths.input_events),
        "input_support_sha256": sha256_file(paths.input_support),
        "input_specification_sha256": sha256_file(paths.input_specification),
    }
    summary = {
        "status": status,
        "failed_checks": failed_checks,
        "checks_total": int(len(checks)),
        "all_run1a_event_rows": int(len(all_events)),
        "prepared_event_rows": int(len(prepared)),
        "repositories": int(
            prepared[["dataset_source", "repo_name"]].drop_duplicates().shape[0]
        ),
        "analysis_specifications": requested_specs,
        "top_n_values": top_n_values,
        "specification_file_status": specification_payload.get("status"),
        "specification_primary_spec": specification_payload.get("primary_spec"),
        "note": (
            "This is a pre-NPR, pre-DiD repository-concentration diagnostic. "
            "It does not select or modify the final primary specification."
        ),
    }
    metadata = {
        "status": status,
        "analysis_stage": "run-1b2-repository-concentration-preflight",
        "inputs": {
            "events": str(paths.input_events.resolve()),
            "run1b_support": str(paths.input_support.resolve()),
            "run1b_specification": str(paths.input_specification.resolve()),
        },
        "input_hashes": input_hashes,
        "analysis_specifications": [
            {
                "name": spec.name,
                "role": spec.role,
                "minimum_literal_space_tokens": spec.min_tokens,
                "maximum_literal_space_tokens": spec.max_tokens,
            }
            for spec in specs
        ],
        "top_n_values": top_n_values,
        "leave_top_out_modes": [
            "none",
            "within_cohort_by_prepared_events",
            "global_by_prepared_events",
        ],
        "interpretation_boundary": (
            "The outputs describe event concentration and retention support. "
            "They do not measure detector accuracy or treatment effects."
        ),
    }
    atomic_json(summary, output_files["summary"])
    atomic_json(metadata, output_files["metadata"])

    print("=" * 76)
    print("Analyze repository-level detector eligibility concentration")
    print(f"Status:                         {status}")
    print(f"All run-1a event rows:          {len(all_events)}")
    print(f"Prepared event rows:            {len(prepared)}")
    print(
        "Repositories:                  "
        f"{prepared[['dataset_source', 'repo_name']].drop_duplicates().shape[0]}"
    )
    print(f"Specifications:                 {','.join(requested_specs)}")
    print(f"Top-N diagnostics:              {','.join(map(str, top_n_values))}")
    print(f"Failed checks:                  {failed_checks}")
    print(f"Output directory:               {paths.output_dir}")
    print(f"QC directory:                   {paths.qc_dir}")
    print("=" * 76)

    return {
        "status": status,
        "failed_checks": failed_checks,
        "summary": summary,
        "output_files": {key: str(value) for key, value in output_files.items()},
    }


def run_self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="run1b2-self-test-") as temporary:
        root = Path(temporary)
        events_path = root / "events.csv"
        support_path = root / "support.csv"
        specification_path = root / "specification.json"
        output_dir = root / "run-1b2" / "strict"

        rows: list[dict[str, Any]] = []
        event_id = 0
        synthetic = {
            ("treatment", "treat/large"): [90, 100, 120, 150, 220, 300],
            ("treatment", "treat/small"): [40, 80, 105, 180],
            ("control", "control/large"): [60, 100, 130, 190, 250],
            ("control", "control/small"): [20, 70, 110],
        }
        for (source, repo), token_counts in synthetic.items():
            for token_count in token_counts:
                event_id += 1
                rows.append(
                    {
                        "function_event_id": f"event-{event_id}",
                        "dataset_source": source,
                        "repo_name": repo,
                        "function_body_split_space_token_count": token_count,
                        "input_preparation_complete": "True",
                        "body_extraction_status": "prepared",
                    }
                )
        rows.append(
            {
                "function_event_id": "excluded-1",
                "dataset_source": "treatment",
                "repo_name": "treat/large",
                "function_body_split_space_token_count": "",
                "input_preparation_complete": "False",
                "body_extraction_status": "excluded",
            }
        )
        events = pd.DataFrame(rows)
        prepared = prepare_events(events)

        specs_payload = [
            {
                "name": "min100",
                "role": "sensitivity",
                "minimum_literal_space_tokens": 100,
                "maximum_literal_space_tokens": None,
            },
            {
                "name": "range100_200",
                "role": "primary_candidate",
                "minimum_literal_space_tokens": 100,
                "maximum_literal_space_tokens": 200,
            },
        ]
        support_rows = []
        for item in specs_payload:
            spec = EligibilitySpec(
                name=item["name"],
                role=item["role"],
                min_tokens=item["minimum_literal_space_tokens"],
                max_tokens=item["maximum_literal_space_tokens"],
            )
            support_rows.append(
                {
                    "spec_name": spec.name,
                    "spec_role": spec.role,
                    "minimum_literal_space_tokens": spec.min_tokens,
                    "maximum_literal_space_tokens": spec.max_tokens,
                    "eligible_event_rows": int(
                        spec.mask(
                            prepared["function_body_split_space_token_count"]
                        ).sum()
                    ),
                }
            )

        events.to_csv(events_path, index=False)
        pd.DataFrame(support_rows).to_csv(support_path, index=False)
        specification_path.write_text(
            json.dumps(
                {
                    "status": "frozen",
                    "primary_spec": "range100_200",
                    "eligibility_specifications": specs_payload,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        test_args = argparse.Namespace(
            input_events=events_path,
            input_support=support_path,
            input_specification=specification_path,
            analysis_specs="min100,range100_200",
            top_n_values="1,2",
            output_dir=output_dir,
            qc_dir=None,
            expected_prepared_events=len(prepared),
            expected_dataset_sources="treatment,control",
            overwrite_output=True,
            self_test=False,
        )
        result = analyze(test_args)
        if result["status"] != "PASS" or result["failed_checks"] != 0:
            raise AssertionError(f"Self-test failed: {result}")

        repository_table = pd.read_csv(
            output_dir / "commit_function_eligibility_by_repository.csv"
        )
        if len(repository_table) != 8:
            raise AssertionError(
                f"Expected 8 repository/spec rows; observed {len(repository_table)}"
            )
        leave_out = pd.read_csv(
            output_dir / "commit_function_retention_gap_leave_top_repos_out.csv"
        )
        expected_rows = 2 * (1 + 2 * 2)
        if len(leave_out) != expected_rows:
            raise AssertionError(
                f"Expected {expected_rows} leave-out rows; observed {len(leave_out)}"
            )
        print("Self-test: PASS")


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0
    result = analyze(args)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
