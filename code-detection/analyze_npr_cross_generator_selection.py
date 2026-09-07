#!/usr/bin/env python3
"""Analyze NPR cross-generator transfer and select a scoring model.

This analysis uses the 5 x 5 NPR cross-generator score matrix produced by the
run-1c0d/run-1c0e experiments. It mirrors the statistical decision framework
used for the ML detector-selection analysis while adapting the bootstrap unit
to the NPR mixed-authorship benchmark structure.

Primary inputs
--------------
Each input root must contain per-procedure CSV files named like:
    npr_scores_npr-xgen_score-<SCORER>_target-<TARGET>.csv

Across all input roots, the script expects exactly one file for each of the
five NPR scoring models crossed with the five AGC generation sources.

Optional input
--------------
A legacy Gemma same-generator per-procedure score CSV can be supplied to audit
small differences between the earlier same-generator experiment and the new
cross-generator experiment.

Bootstrap design
----------------
Within each target generation source, the mixed-authorship benchmark contains
10 length buckets, 5 mixed-authorship files per bucket, and 6 procedures per
file (3 HWC and 3 AGC). Each bootstrap replicate samples 5 files with
replacement within each bucket. All procedures in a sampled file are retained
with the sampled multiplicity. The same sampled-file multiplicities are reused
across all five NPR scoring models for a given target source.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


CANDIDATES: Tuple[str, ...] = (
    "codellama-7b",
    "starcoder2-7b",
    "starcoder2-15b-instruct-v0.1",
    "gpt-oss",
    "gemma",
)

TARGETS: Tuple[str, ...] = CANDIDATES

DISPLAY_NAMES: Mapping[str, str] = {
    "codellama-7b": "CodeLlama-7B",
    "starcoder2-7b": "StarCoder2-7B",
    "starcoder2-15b-instruct-v0.1": "StarCoder2-15B",
    "gpt-oss": "GPT-OSS-120B",
    "gemma": "Gemma4-31B",
}

EXPECTED_BUCKETS = 10
EXPECTED_FILES_PER_BUCKET = 5
EXPECTED_PROCEDURES_PER_FILE = 6
EXPECTED_HWC_PER_FILE = 3
EXPECTED_AGC_PER_FILE = 3
EXPECTED_ROWS_PER_TARGET = 300

SCORE_FILE_RE = re.compile(
    r"^npr_scores_npr-xgen_score-(?P<scorer>.+)_target-(?P<target>.+)\.csv$"
)
ROW_SUMMARY_RE = re.compile(r"^npr_xgen_row_summary_score-(?P<scorer>.+)\.csv$")

ROW_KEY_COLUMNS = ("benchmark_type", "file_id", "filename", "function_id")
CLUSTER_KEY_COLUMNS = ("benchmark_type", "file_id", "filename")


@dataclass(frozen=True)
class CellData:
    scorer: str
    target: str
    path: Path
    frame: pd.DataFrame
    row_keys: Tuple[str, ...]
    cluster_keys: Tuple[str, ...]
    cluster_index: np.ndarray
    labels: np.ndarray
    scores: np.ndarray


@dataclass(frozen=True)
class TargetBootstrapDesign:
    target: str
    reference_rows: pd.DataFrame
    cluster_keys: Tuple[str, ...]
    bucket_to_cluster_indices: Mapping[str, Tuple[int, ...]]
    counts: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NPR cross-generator transfer, bootstrap uncertainty, and minimax-regret selection"
    )
    parser.add_argument(
        "--input-root",
        action="append",
        required=True,
        help="Input directory containing NPR cross-generator per-procedure CSV files; repeat as needed.",
    )
    parser.add_argument(
        "--legacy-gemma-score-csv",
        default=None,
        help="Optional legacy Gemma same-generator per-procedure score CSV for reproducibility audit.",
    )
    parser.add_argument(
        "--output-root",
        required=True,
        help="Directory for analysis outputs.",
    )
    parser.add_argument(
        "--bootstrap-reps",
        type=int,
        default=20000,
        help="Number of stratified cluster-bootstrap replicates (default: 20000).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260723,
        help="Random seed (default: 20260723).",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.95,
        help="Percentile confidence level (default: 0.95).",
    )
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def make_row_key(df: pd.DataFrame) -> pd.Series:
    return (
        df["benchmark_type"].astype(str)
        + "|"
        + df["file_id"].astype(str)
        + "|"
        + df["filename"].astype(str)
        + "|"
        + df["function_id"].astype(str)
    )


def make_cluster_key(df: pd.DataFrame) -> pd.Series:
    return (
        df["benchmark_type"].astype(str)
        + "|"
        + df["file_id"].astype(str)
        + "|"
        + df["filename"].astype(str)
    )


def normalize_score_frame(path: Path, expected_scorer: Optional[str] = None, expected_target: Optional[str] = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {
        "benchmark_type",
        "file_id",
        "filename",
        "function_id",
        "role",
        "label",
        "npr",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{path}: missing required columns: {missing}")

    df = df.copy()
    df["label"] = pd.to_numeric(df["label"], errors="raise").astype(int)
    df["npr"] = pd.to_numeric(df["npr"], errors="coerce")
    if df["npr"].isna().any():
        bad = int(df["npr"].isna().sum())
        raise ValueError(f"{path}: {bad} rows have missing/non-numeric NPR scores")

    if expected_scorer is not None:
        if "scoring_model_key" in df.columns:
            observed = set(df["scoring_model_key"].dropna().astype(str).unique())
            if observed != {expected_scorer}:
                raise ValueError(f"{path}: scoring_model_key mismatch: {sorted(observed)} != {expected_scorer}")
        else:
            df.insert(0, "scoring_model_key", expected_scorer)

    if expected_target is not None:
        if "target_source" in df.columns:
            observed = set(df["target_source"].dropna().astype(str).unique())
            if observed != {expected_target}:
                raise ValueError(f"{path}: target_source mismatch: {sorted(observed)} != {expected_target}")
        else:
            df.insert(0, "target_source", expected_target)

    df["_row_key"] = make_row_key(df)
    df["_cluster_key"] = make_cluster_key(df)

    if df["_row_key"].duplicated().any():
        dup = df.loc[df["_row_key"].duplicated(keep=False), "_row_key"].head(10).tolist()
        raise ValueError(f"{path}: duplicate procedure row keys detected, examples={dup}")

    df = df.sort_values(list(ROW_KEY_COLUMNS), kind="mergesort").reset_index(drop=True)
    return df


def parse_cell_from_filename(path: Path) -> Optional[Tuple[str, str]]:
    m = SCORE_FILE_RE.match(path.name)
    if not m:
        return None
    scorer = m.group("scorer")
    target = m.group("target")
    if scorer not in CANDIDATES or target not in TARGETS:
        return None
    return scorer, target


def frames_equivalent(a: pd.DataFrame, b: pd.DataFrame, atol: float = 1e-12) -> bool:
    cols = ["_row_key", "label", "role", "npr"]
    if len(a) != len(b):
        return False
    aa = a[cols].sort_values("_row_key").reset_index(drop=True)
    bb = b[cols].sort_values("_row_key").reset_index(drop=True)
    if not aa["_row_key"].equals(bb["_row_key"]):
        return False
    if not aa["label"].equals(bb["label"]):
        return False
    if not aa["role"].astype(str).equals(bb["role"].astype(str)):
        return False
    return bool(np.allclose(aa["npr"].to_numpy(float), bb["npr"].to_numpy(float), atol=atol, rtol=0.0))


def discover_cells(input_roots: Sequence[Path]) -> Tuple[Dict[Tuple[str, str], pd.DataFrame], Dict[Tuple[str, str], Path]]:
    cells: Dict[Tuple[str, str], pd.DataFrame] = {}
    paths: Dict[Tuple[str, str], Path] = {}

    for root in input_roots:
        if not root.exists():
            raise FileNotFoundError(f"Input root does not exist: {root}")
        for path in sorted(root.glob("npr_scores_npr-xgen_score-*_target-*.csv")):
            if path.name.endswith("_bucket_summary.csv") or path.name.endswith("_overall_summary.csv"):
                continue
            key = parse_cell_from_filename(path)
            if key is None:
                continue
            scorer, target = key
            df = normalize_score_frame(path, scorer, target)
            if key in cells:
                if frames_equivalent(cells[key], df):
                    continue
                raise ValueError(
                    "Conflicting duplicate cell files detected for "
                    f"scorer={scorer}, target={target}: {paths[key]} vs {path}. "
                    "Provide input roots containing only the intended production results."
                )
            cells[key] = df
            paths[key] = path

    expected = {(c, t) for c in CANDIDATES for t in TARGETS}
    observed = set(cells)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing or extra:
        raise ValueError(
            f"Expected exactly 25 production cells. Missing={missing}; extra={extra}; observed={len(observed)}"
        )
    return cells, paths


def validate_target_alignment(cells: Mapping[Tuple[str, str], pd.DataFrame]) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    qc_rows: List[dict] = []
    target_references: Dict[str, pd.DataFrame] = {}

    for target in TARGETS:
        ref = cells[(CANDIDATES[0], target)].copy()
        if len(ref) != EXPECTED_ROWS_PER_TARGET:
            raise ValueError(f"Target {target}: expected {EXPECTED_ROWS_PER_TARGET} rows, observed {len(ref)}")

        ref_keys = ref["_row_key"].tolist()
        target_references[target] = ref

        for scorer in CANDIDATES:
            df = cells[(scorer, target)]
            same_keys = ref_keys == df["_row_key"].tolist()
            same_labels = ref["label"].tolist() == df["label"].tolist()
            same_roles = ref["role"].astype(str).tolist() == df["role"].astype(str).tolist()
            same_source_idx = True
            if "source_idx" in ref.columns and "source_idx" in df.columns:
                same_source_idx = ref["source_idx"].astype(str).tolist() == df["source_idx"].astype(str).tolist()
            qc_rows.append(
                {
                    "scoring_model_key": scorer,
                    "target_source": target,
                    "n_rows": len(df),
                    "n_hwc": int((df["label"] == 0).sum()),
                    "n_agc": int((df["label"] == 1).sum()),
                    "row_keys_match_target_reference": same_keys,
                    "labels_match_target_reference": same_labels,
                    "roles_match_target_reference": same_roles,
                    "source_idx_match_target_reference": same_source_idx,
                }
            )
            if not (same_keys and same_labels and same_roles and same_source_idx):
                raise ValueError(f"Target alignment failed for scorer={scorer}, target={target}")

    return pd.DataFrame(qc_rows), target_references


def validate_cluster_structure(reference: pd.DataFrame, target: str) -> Tuple[Tuple[str, ...], Dict[str, Tuple[int, ...]], np.ndarray]:
    cluster_summary = (
        reference.groupby(["benchmark_type", "_cluster_key"], sort=True)
        .agg(n=("label", "size"), n_hwc=("label", lambda x: int((x == 0).sum())), n_agc=("label", lambda x: int((x == 1).sum())))
        .reset_index()
    )

    buckets = sorted(cluster_summary["benchmark_type"].astype(str).unique())
    if len(buckets) != EXPECTED_BUCKETS:
        raise ValueError(f"Target {target}: expected {EXPECTED_BUCKETS} buckets, observed {len(buckets)}")

    bad_cluster = cluster_summary[
        (cluster_summary["n"] != EXPECTED_PROCEDURES_PER_FILE)
        | (cluster_summary["n_hwc"] != EXPECTED_HWC_PER_FILE)
        | (cluster_summary["n_agc"] != EXPECTED_AGC_PER_FILE)
    ]
    if not bad_cluster.empty:
        raise ValueError(f"Target {target}: invalid mixed-authorship file composition:\n{bad_cluster.head(20)}")

    cluster_keys: List[str] = []
    bucket_to_indices: Dict[str, Tuple[int, ...]] = {}
    for bucket in buckets:
        keys = sorted(cluster_summary.loc[cluster_summary["benchmark_type"] == bucket, "_cluster_key"].astype(str).tolist())
        if len(keys) != EXPECTED_FILES_PER_BUCKET:
            raise ValueError(
                f"Target {target}, bucket {bucket}: expected {EXPECTED_FILES_PER_BUCKET} files, observed {len(keys)}"
            )
        idxs: List[int] = []
        for key in keys:
            idxs.append(len(cluster_keys))
            cluster_keys.append(key)
        bucket_to_indices[bucket] = tuple(idxs)

    cluster_to_idx = {key: i for i, key in enumerate(cluster_keys)}
    row_cluster_idx = reference["_cluster_key"].astype(str).map(cluster_to_idx).to_numpy(dtype=int)
    if np.any(row_cluster_idx < 0):
        raise ValueError(f"Target {target}: failed to map all rows to bootstrap clusters")
    return tuple(cluster_keys), bucket_to_indices, row_cluster_idx


def generate_stratified_cluster_counts(
    bucket_to_cluster_indices: Mapping[str, Tuple[int, ...]],
    n_clusters: int,
    reps: int,
    rng: np.random.Generator,
) -> np.ndarray:
    counts = np.zeros((reps, n_clusters), dtype=np.int16)
    for bucket in sorted(bucket_to_cluster_indices):
        idxs = bucket_to_cluster_indices[bucket]
        k = len(idxs)
        draws = rng.multinomial(k, np.full(k, 1.0 / k), size=reps).astype(np.int16)
        counts[:, list(idxs)] = draws
    return counts


def auc_from_cluster_counts(
    scores: np.ndarray,
    labels: np.ndarray,
    row_cluster_idx: np.ndarray,
    counts: np.ndarray,
) -> np.ndarray:
    """Compute weighted AUROC for many cluster-bootstrap replicates.

    The score order is fixed across replicates. Cluster multiplicities act as
    observation weights. Exact score ties receive half credit, matching the
    Mann-Whitney definition of AUROC.
    """
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels, dtype=int)
    row_cluster_idx = np.asarray(row_cluster_idx, dtype=int)
    if not (len(scores) == len(labels) == len(row_cluster_idx)):
        raise ValueError("scores, labels, and row_cluster_idx must have equal length")
    if set(np.unique(labels)) != {0, 1}:
        raise ValueError("AUROC requires both HWC (0) and AGC (1) labels")

    unique_scores, group_idx = np.unique(scores, return_inverse=True)
    n_groups = len(unique_scores)
    n_clusters = counts.shape[1]

    pos_inc = np.zeros((n_clusters, n_groups), dtype=np.int16)
    neg_inc = np.zeros((n_clusters, n_groups), dtype=np.int16)
    for r in range(len(scores)):
        c = row_cluster_idx[r]
        g = group_idx[r]
        if labels[r] == 1:
            pos_inc[c, g] += 1
        else:
            neg_inc[c, g] += 1

    pos_w = counts @ pos_inc
    neg_w = counts @ neg_inc
    neg_before = np.cumsum(neg_w, axis=1, dtype=np.int32) - neg_w
    numerator = np.sum(pos_w * (neg_before + 0.5 * neg_w), axis=1, dtype=np.float64)
    n_pos = np.sum(pos_w, axis=1, dtype=np.float64)
    n_neg = np.sum(neg_w, axis=1, dtype=np.float64)
    denominator = n_pos * n_neg
    if np.any(denominator <= 0):
        raise ValueError("A bootstrap replicate lacks one class; benchmark balance validation should prevent this")
    return numerator / denominator


def auc_from_scores(scores: np.ndarray, labels: np.ndarray) -> float:
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels, dtype=int)
    order = np.argsort(scores, kind="mergesort")
    s = scores[order]
    y = labels[order]

    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))
    if n_pos == 0 or n_neg == 0:
        raise ValueError("AUROC requires both classes")

    numerator = 0.0
    neg_before = 0
    start = 0
    while start < len(s):
        end = start + 1
        while end < len(s) and s[end] == s[start]:
            end += 1
        group = y[start:end]
        g_pos = int(np.sum(group == 1))
        g_neg = int(np.sum(group == 0))
        numerator += g_pos * (neg_before + 0.5 * g_neg)
        neg_before += g_neg
        start = end
    return float(numerator / (n_pos * n_neg))


def build_bootstrap_designs(
    target_references: Mapping[str, pd.DataFrame],
    reps: int,
    seed: int,
) -> Dict[str, TargetBootstrapDesign]:
    rng = np.random.default_rng(seed)
    designs: Dict[str, TargetBootstrapDesign] = {}
    for target in TARGETS:
        reference = target_references[target]
        cluster_keys, bucket_to_indices, _ = validate_cluster_structure(reference, target)
        counts = generate_stratified_cluster_counts(
            bucket_to_cluster_indices=bucket_to_indices,
            n_clusters=len(cluster_keys),
            reps=reps,
            rng=rng,
        )
        designs[target] = TargetBootstrapDesign(
            target=target,
            reference_rows=reference,
            cluster_keys=cluster_keys,
            bucket_to_cluster_indices=bucket_to_indices,
            counts=counts,
        )
    return designs


def compute_all_auc_draws(
    cells: Mapping[Tuple[str, str], pd.DataFrame],
    designs: Mapping[str, TargetBootstrapDesign],
) -> Tuple[np.ndarray, np.ndarray]:
    c_idx = {c: i for i, c in enumerate(CANDIDATES)}
    t_idx = {t: i for i, t in enumerate(TARGETS)}
    reps = next(iter(designs.values())).counts.shape[0]
    point = np.empty((len(CANDIDATES), len(TARGETS)), dtype=float)
    boot = np.empty((reps, len(CANDIDATES), len(TARGETS)), dtype=np.float64)

    for target in TARGETS:
        design = designs[target]
        cluster_to_idx = {key: i for i, key in enumerate(design.cluster_keys)}
        for scorer in CANDIDATES:
            df = cells[(scorer, target)]
            row_cluster_idx = df["_cluster_key"].astype(str).map(cluster_to_idx).to_numpy(dtype=int)
            if np.any(row_cluster_idx < 0):
                raise ValueError(f"Cluster mapping failed for scorer={scorer}, target={target}")
            scores = df["npr"].to_numpy(float)
            labels = df["label"].to_numpy(int)
            observed_counts = np.ones((1, len(design.cluster_keys)), dtype=np.int16)
            point[c_idx[scorer], t_idx[target]] = auc_from_cluster_counts(
                scores, labels, row_cluster_idx, observed_counts
            )[0]
            boot[:, c_idx[scorer], t_idx[target]] = auc_from_cluster_counts(
                scores, labels, row_cluster_idx, design.counts
            )
    return point, boot


def summarize_candidate_metrics(point: np.ndarray, boot: np.ndarray) -> Tuple[pd.DataFrame, Dict[str, np.ndarray]]:
    candidate_to_target_idx = np.array([TARGETS.index(c) for c in CANDIDATES], dtype=int)
    c_indices = np.arange(len(CANDIDATES))

    point_same = point[c_indices, candidate_to_target_idx]
    point_transfer = np.array(
        [np.mean(np.delete(point[i, :], candidate_to_target_idx[i])) for i in c_indices],
        dtype=float,
    )

    boot_same = boot[:, c_indices, candidate_to_target_idx]
    boot_transfer = np.column_stack(
        [
            np.mean(np.delete(boot[:, i, :], candidate_to_target_idx[i], axis=1), axis=1)
            for i in c_indices
        ]
    )

    point_best_same = float(np.max(point_same))
    point_best_transfer = float(np.max(point_transfer))
    point_same_regret = point_best_same - point_same
    point_transfer_regret = point_best_transfer - point_transfer
    point_max_regret = np.maximum(point_same_regret, point_transfer_regret)

    boot_best_same = np.max(boot_same, axis=1)
    boot_best_transfer = np.max(boot_transfer, axis=1)
    boot_same_regret = boot_best_same[:, None] - boot_same
    boot_transfer_regret = boot_best_transfer[:, None] - boot_transfer
    boot_max_regret = np.maximum(boot_same_regret, boot_transfer_regret)

    ranks = pd.DataFrame(boot_max_regret).rank(axis=1, method="min", ascending=True).to_numpy(float)
    min_regret = np.min(boot_max_regret, axis=1)
    is_minimax = np.isclose(boot_max_regret, min_regret[:, None], atol=1e-12, rtol=0.0)

    pareto = np.ones_like(boot_same, dtype=bool)
    tol = 1e-12
    for i in range(len(CANDIDATES)):
        dominated = np.zeros(boot_same.shape[0], dtype=bool)
        for j in range(len(CANDIDATES)):
            if i == j:
                continue
            ge_same = boot_same[:, j] >= boot_same[:, i] - tol
            ge_transfer = boot_transfer[:, j] >= boot_transfer[:, i] - tol
            strict = (boot_same[:, j] > boot_same[:, i] + tol) | (
                boot_transfer[:, j] > boot_transfer[:, i] + tol
            )
            dominated |= ge_same & ge_transfer & strict
        pareto[:, i] = ~dominated

    point_rank = pd.Series(point_max_regret).rank(method="min", ascending=True).to_numpy(float)
    point_selected = np.isclose(point_max_regret, np.min(point_max_regret), atol=1e-12, rtol=0.0)

    point_pareto = np.ones(len(CANDIDATES), dtype=bool)
    for i in range(len(CANDIDATES)):
        for j in range(len(CANDIDATES)):
            if i == j:
                continue
            if (
                point_same[j] >= point_same[i] - tol
                and point_transfer[j] >= point_transfer[i] - tol
                and (
                    point_same[j] > point_same[i] + tol
                    or point_transfer[j] > point_transfer[i] + tol
                )
            ):
                point_pareto[i] = False
                break

    rows = []
    for i, c in enumerate(CANDIDATES):
        rows.append(
            {
                "scoring_model_key": c,
                "display_name": DISPLAY_NAMES[c],
                "same_generator_auc": point_same[i],
                "transfer_auc": point_transfer[i],
                "same_generator_regret": point_same_regret[i],
                "transfer_regret": point_transfer_regret[i],
                "max_regret": point_max_regret[i],
                "observed_rank_by_max_regret": point_rank[i],
                "observed_pareto_nondominated": bool(point_pareto[i]),
                "selected_by_observed_minimax_regret": bool(point_selected[i]),
            }
        )

    arrays = {
        "point_same": point_same,
        "point_transfer": point_transfer,
        "point_same_regret": point_same_regret,
        "point_transfer_regret": point_transfer_regret,
        "point_max_regret": point_max_regret,
        "boot_same": boot_same,
        "boot_transfer": boot_transfer,
        "boot_same_regret": boot_same_regret,
        "boot_transfer_regret": boot_transfer_regret,
        "boot_max_regret": boot_max_regret,
        "ranks": ranks,
        "is_minimax": is_minimax,
        "pareto": pareto,
    }
    return pd.DataFrame(rows), arrays


def percentile_interval(x: np.ndarray, confidence: float) -> Tuple[float, float]:
    alpha = 1.0 - confidence
    lo, hi = np.quantile(np.asarray(x, dtype=float), [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lo), float(hi)


def bootstrap_metric_summary(
    observed: np.ndarray,
    draws: np.ndarray,
    confidence: float,
    value_name: str,
) -> pd.DataFrame:
    rows = []
    for i, c in enumerate(CANDIDATES):
        lo, hi = percentile_interval(draws[:, i], confidence)
        rows.append(
            {
                "scoring_model_key": c,
                "display_name": DISPLAY_NAMES[c],
                f"observed_{value_name}": observed[i],
                f"bootstrap_mean_{value_name}": float(np.mean(draws[:, i])),
                f"bootstrap_sd_{value_name}": float(np.std(draws[:, i], ddof=1)),
                f"ci_lower_{value_name}": lo,
                f"ci_upper_{value_name}": hi,
            }
        )
    return pd.DataFrame(rows)


def pairwise_summary(
    observed: np.ndarray,
    draws: np.ndarray,
    confidence: float,
    estimand: str,
) -> pd.DataFrame:
    rows = []
    for i in range(len(CANDIDATES)):
        for j in range(i + 1, len(CANDIDATES)):
            diff = draws[:, i] - draws[:, j]
            lo, hi = percentile_interval(diff, confidence)
            rows.append(
                {
                    "candidate_a": CANDIDATES[i],
                    "candidate_b": CANDIDATES[j],
                    "display_a": DISPLAY_NAMES[CANDIDATES[i]],
                    "display_b": DISPLAY_NAMES[CANDIDATES[j]],
                    "estimand": estimand,
                    "observed_difference_a_minus_b": float(observed[i] - observed[j]),
                    "bootstrap_mean_difference": float(np.mean(diff)),
                    "ci_lower": lo,
                    "ci_upper": hi,
                    "p_a_gt_b": float(np.mean(diff > 0.0)),
                }
            )
    return pd.DataFrame(rows)


def pairwise_transfer_common_targets(
    point: np.ndarray,
    boot: np.ndarray,
    confidence: float,
) -> pd.DataFrame:
    rows = []
    for i in range(len(CANDIDATES)):
        for j in range(i + 1, len(CANDIDATES)):
            own_i = TARGETS.index(CANDIDATES[i])
            own_j = TARGETS.index(CANDIDATES[j])
            common = [k for k in range(len(TARGETS)) if k not in {own_i, own_j}]
            observed_a = float(np.mean(point[i, common]))
            observed_b = float(np.mean(point[j, common]))
            draws_a = np.mean(boot[:, i, common], axis=1)
            draws_b = np.mean(boot[:, j, common], axis=1)
            diff = draws_a - draws_b
            lo, hi = percentile_interval(diff, confidence)
            rows.append(
                {
                    "candidate_a": CANDIDATES[i],
                    "candidate_b": CANDIDATES[j],
                    "display_a": DISPLAY_NAMES[CANDIDATES[i]],
                    "display_b": DISPLAY_NAMES[CANDIDATES[j]],
                    "common_targets": ",".join(TARGETS[k] for k in common),
                    "n_common_targets": len(common),
                    "observed_common_target_auc_a": observed_a,
                    "observed_common_target_auc_b": observed_b,
                    "observed_difference_a_minus_b": observed_a - observed_b,
                    "bootstrap_mean_difference": float(np.mean(diff)),
                    "ci_lower": lo,
                    "ci_upper": hi,
                    "p_a_gt_b": float(np.mean(diff > 0.0)),
                }
            )
    return pd.DataFrame(rows)


def find_row_summaries(input_roots: Sequence[Path]) -> Dict[str, Path]:
    result: Dict[str, Path] = {}
    for root in input_roots:
        for path in sorted(root.glob("npr_xgen_row_summary_score-*.csv")):
            m = ROW_SUMMARY_RE.match(path.name)
            if not m:
                continue
            scorer = m.group("scorer")
            if scorer in CANDIDATES and scorer not in result:
                result[scorer] = path
    return result


def count_cross_class_score_ties(df: pd.DataFrame) -> int:
    """Count HWC-AGC pairs tied after persisted NPR score rounding."""
    hwc = df.loc[df["label"] == 0, "npr"].value_counts()
    agc = df.loc[df["label"] == 1, "npr"].value_counts()
    shared = hwc.index.intersection(agc.index)
    return int(sum(int(hwc.loc[x]) * int(agc.loc[x]) for x in shared))


def row_summary_qc(
    row_summaries: Mapping[str, Path],
    point: np.ndarray,
    cells: Mapping[Tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    """Compare persisted-score AUROC with scorer-row summaries.

    The scorer-row AUROC is computed before the per-procedure CSV rounds NPR
    scores to six decimals. Rounding can convert a cross-class near-tie into an
    exact tie and change Mann-Whitney AUROC by half a positive-negative pair.
    The QC therefore reports both a strict 1e-6 comparison and a data-derived
    rounding bound based on the number of cross-class ties in the persisted
    score CSV.
    """
    rows: List[dict] = []
    c_idx = {c: i for i, c in enumerate(CANDIDATES)}
    t_idx = {t: i for i, t in enumerate(TARGETS)}
    for scorer in CANDIDATES:
        path = row_summaries.get(scorer)
        if path is None:
            for target in TARGETS:
                rows.append(
                    {
                        "scoring_model_key": scorer,
                        "target_source": target,
                        "row_summary_found": False,
                        "row_summary_auc": np.nan,
                        "recomputed_auc_from_persisted_scores": point[c_idx[scorer], t_idx[target]],
                        "absolute_difference": np.nan,
                        "n_cross_class_score_ties": count_cross_class_score_ties(cells[(scorer, target)]),
                        "rounding_auc_bound": np.nan,
                        "strict_match_within_1e-6": False,
                        "match_within_rounding_bound": False,
                        "qc_status": "MISSING_ROW_SUMMARY",
                    }
                )
            continue
        summary = pd.read_csv(path)
        for target in TARGETS:
            sub = summary[summary["target_source"].astype(str) == target]
            if len(sub) != 1:
                raise ValueError(f"{path}: expected one row for target={target}, observed {len(sub)}")
            reported = float(sub.iloc[0]["auc"])
            recomputed = float(point[c_idx[scorer], t_idx[target]])
            diff = abs(reported - recomputed)
            df = cells[(scorer, target)]
            n_hwc = int((df["label"] == 0).sum())
            n_agc = int((df["label"] == 1).sum())
            n_cross_ties = count_cross_class_score_ties(df)
            # Each cross-class tie can move full-precision AUROC by at most
            # half of one positive-negative comparison after six-decimal
            # persistence. Add 0.5e-6 for the six-decimal row-summary AUROC.
            rounding_bound = 0.5 * n_cross_ties / float(n_hwc * n_agc) + 0.5e-6
            strict_match = bool(diff <= 1e-6 + 1e-12)
            rounding_match = bool(diff <= max(1e-6, rounding_bound) + 1e-12)
            status = "EXACT" if strict_match else ("PASS_ROUNDING_BOUND" if rounding_match else "FAIL")
            rows.append(
                {
                    "scoring_model_key": scorer,
                    "target_source": target,
                    "row_summary_found": True,
                    "row_summary_auc": reported,
                    "recomputed_auc_from_persisted_scores": recomputed,
                    "absolute_difference": diff,
                    "n_cross_class_score_ties": n_cross_ties,
                    "rounding_auc_bound": rounding_bound,
                    "strict_match_within_1e-6": strict_match,
                    "match_within_rounding_bound": rounding_match,
                    "qc_status": status,
                }
            )
    return pd.DataFrame(rows)


def point_matrix_from_row_summaries(row_summaries: Mapping[str, Path]) -> np.ndarray:
    """Build the paper-facing 5 x 5 AUROC matrix from scorer-row summaries."""
    point = np.empty((len(CANDIDATES), len(TARGETS)), dtype=float)
    for i, scorer in enumerate(CANDIDATES):
        path = row_summaries.get(scorer)
        if path is None:
            raise ValueError(f"Missing row-summary CSV for scorer={scorer}")
        summary = pd.read_csv(path)
        for j, target in enumerate(TARGETS):
            sub = summary[summary["target_source"].astype(str) == target]
            if len(sub) != 1:
                raise ValueError(f"{path}: expected one row for target={target}, observed {len(sub)}")
            point[i, j] = float(sub.iloc[0]["auc"])
    return point


def rank_average(values: np.ndarray) -> np.ndarray:
    return pd.Series(values).rank(method="average").to_numpy(float)


def audit_gemma(new_df: pd.DataFrame, legacy_path: Path, output_root: Path) -> pd.DataFrame:
    legacy = normalize_score_frame(legacy_path)
    new = new_df.copy()

    legacy_idx = legacy.set_index("_row_key", drop=False)
    new_idx = new.set_index("_row_key", drop=False)
    common = sorted(set(legacy_idx.index) & set(new_idx.index))

    old_aligned = legacy_idx.loc[common].copy()
    new_aligned = new_idx.loc[common].copy()
    old_scores = old_aligned["npr"].to_numpy(float)
    new_scores = new_aligned["npr"].to_numpy(float)
    diff = new_scores - old_scores
    abs_diff = np.abs(diff)

    labels_match = old_aligned["label"].to_numpy(int) == new_aligned["label"].to_numpy(int)
    roles_match = old_aligned["role"].astype(str).to_numpy() == new_aligned["role"].astype(str).to_numpy()
    source_idx_mismatch = np.zeros(len(common), dtype=bool)
    if "source_idx" in old_aligned.columns and "source_idx" in new_aligned.columns:
        source_idx_mismatch = old_aligned["source_idx"].astype(str).to_numpy() != new_aligned["source_idx"].astype(str).to_numpy()

    pearson = float(np.corrcoef(old_scores, new_scores)[0, 1]) if len(common) > 1 else np.nan
    old_rank = rank_average(old_scores)
    new_rank = rank_average(new_scores)
    spearman = float(np.corrcoef(old_rank, new_rank)[0, 1]) if len(common) > 1 else np.nan

    old_auc = auc_from_scores(old_scores, old_aligned["label"].to_numpy(int))
    new_auc = auc_from_scores(new_scores, new_aligned["label"].to_numpy(int))

    detail = pd.DataFrame(
        {
            "row_key": common,
            "label": new_aligned["label"].to_numpy(int),
            "role": new_aligned["role"].astype(str).to_numpy(),
            "legacy_npr": old_scores,
            "current_npr": new_scores,
            "current_minus_legacy": diff,
            "absolute_difference": abs_diff,
        }
    )
    detail.to_csv(output_root / "gemma_diagonal_score_differences.csv.gz", index=False, compression="gzip")

    row = {
        "legacy_score_csv": str(legacy_path),
        "n_legacy": len(legacy),
        "n_current": len(new),
        "n_matched": len(common),
        "n_legacy_only": len(set(legacy_idx.index) - set(new_idx.index)),
        "n_current_only": len(set(new_idx.index) - set(legacy_idx.index)),
        "n_label_mismatch": int(np.sum(~labels_match)),
        "n_role_mismatch": int(np.sum(~roles_match)),
        "n_source_idx_mismatch": int(np.sum(source_idx_mismatch)),
        "legacy_auc": old_auc,
        "current_auc": new_auc,
        "auc_difference_current_minus_legacy": new_auc - old_auc,
        "mean_absolute_score_difference": float(np.mean(abs_diff)),
        "median_absolute_score_difference": float(np.median(abs_diff)),
        "p95_absolute_score_difference": float(np.quantile(abs_diff, 0.95)),
        "max_absolute_score_difference": float(np.max(abs_diff)),
        "n_exact_equal_scores": int(np.sum(abs_diff == 0.0)),
        "n_within_1e-6": int(np.sum(abs_diff <= 1e-6)),
        "pearson_score_correlation": pearson,
        "spearman_score_correlation": spearman,
    }
    return pd.DataFrame([row])


def write_methodology(
    output_root: Path,
    args: argparse.Namespace,
    selected: Sequence[str],
    gemma_audit_run: bool,
) -> None:
    text = f"""run-1c0f v2 NPR cross-generator scoring-model selection methodology
================================================================

Evaluation regimes
------------------
E1 = same-generator AUROC, obtained from the five diagonal cells of the current
     5 x 5 NPR cross-generator experiment.
E2 = cross-generator Transfer AUROC, defined for scoring model c as the
     arithmetic mean of its four off-diagonal target-generation-source AUROCs.

Primary decision criterion: minimax AUROC regret
------------------------------------------------
For each evaluation regime e and scoring model c:

  regret(c,e) = max_j AUROC(j,e) - AUROC(c,e)
  max_regret(c) = max_e regret(c,e)

The point-estimate selection is argmin_c max_regret(c). The criterion uses
magnitude in AUROC points rather than ordinal rank and introduces no
regime-specific weights. E1 and E2 are directly comparable because both are
AUROC on the same [0,1] scale.

Bootstrap uncertainty
---------------------
Bootstrap replicates : {args.bootstrap_reps}
Random seed          : {args.seed}
Confidence level     : {args.confidence:.4f}
Resampling unit      : mixed-authorship file, stratified by implementation-length bucket
Buckets per target   : {EXPECTED_BUCKETS}
Files per bucket     : {EXPECTED_FILES_PER_BUCKET}
Procedures per file  : {EXPECTED_PROCEDURES_PER_FILE} ({EXPECTED_HWC_PER_FILE} HWC + {EXPECTED_AGC_PER_FILE} AGC)
Procedures per target: {EXPECTED_ROWS_PER_TARGET}

Within each target generation source, five mixed-authorship files are sampled
with replacement separately within each of the ten implementation-length
buckets. All six procedures from a sampled file are retained with the same
multiplicity. The same sampled-file multiplicities are reused for all five NPR
scoring models on that target. This preserves the benchmark's length
composition and HWC/AGC balance while retaining dependence among procedures
co-located in the same mixed-authorship file.

Pairwise transfer effect sizes
------------------------------
The paper-facing Transfer mean omits a different own-source target for each
scoring model. Pairwise transfer inference therefore additionally uses a
common-target estimand. For scoring models A and B, target A and target B are
both removed, and the mean AUROC difference A-B is computed over the remaining
three target generation sources using the same bootstrap file multiplicities.

Supporting decision diagnostics
-------------------------------
* expected rank and P(top-2) under bootstrap uncertainty;
* pairwise AUROC-difference percentile confidence intervals;
* P(A > B) from bootstrap draws;
* probability of Pareto non-dominance across E1 and E2;
* probability of minimizing maximum regret.

Gemma reproducibility audit
---------------------------
Legacy Gemma same-generator score audit executed: {gemma_audit_run}
The legacy same-generator result is used only for reproducibility/sensitivity
audit. The primary candidate-selection analysis uses the diagonal and
off-diagonal cells from the current cross-generator experiment so that E1 and
E2 come from one internally consistent evaluation pipeline.

Point-estimate selected scoring model(s)
----------------------------------------
{', '.join(DISPLAY_NAMES.get(x, x) for x in selected)}

Interpretation constraint
-------------------------
This analysis does not create a weighted composite AUROC and does not use raw
rank sum as the primary selection rule. Scoring-model selection should be
reported using the observed minimax-regret criterion together with bootstrap
uncertainty and pairwise effect-size evidence.
"""
    (output_root / "methodology.txt").write_text(text, encoding="utf-8")


def write_candidate_summary(
    output_root: Path,
    point_df: pd.DataFrame,
    minimax_df: pd.DataFrame,
    confidence: float,
) -> None:
    selected_rows = point_df[point_df["selected_by_observed_minimax_regret"]]
    selected_names = selected_rows["display_name"].tolist()
    best_same = point_df.loc[point_df["same_generator_auc"].idxmax()]
    best_transfer = point_df.loc[point_df["transfer_auc"].idxmax()]

    ranked = minimax_df.sort_values(["observed_max_regret", "scoring_model_key"])
    lines = [
        "run-1c0f v2 NPR cross-generator scoring-model selection summary",
        "===========================================================",
        "",
        f"Observed minimax-regret selection: {', '.join(selected_names)}",
        f"Highest same-generator AUROC: {best_same['display_name']} ({best_same['same_generator_auc']:.6f})",
        f"Highest mean transfer AUROC: {best_transfer['display_name']} ({best_transfer['transfer_auc']:.6f})",
        "",
        "Observed minimax-regret ranking:",
    ]
    for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
        lines.append(
            f"  {rank}. {row['display_name']}: same={row['observed_same_generator_auc']:.6f}, "
            f"transfer={row['observed_transfer_auc']:.6f}, max_regret={row['observed_max_regret']:.6f}, "
            f"P(min max regret)={row['p_minimize_max_regret']:.4f}, P(top-2)={row['p_top2']:.4f}"
        )
    lines.extend(
        [
            "",
            f"Bootstrap percentile intervals use a {confidence:.1%} confidence level.",
            "The primary selection uses the current cross-generator experiment's diagonal and off-diagonal cells. Paper-facing point AUROCs are taken from scorer-row summaries computed before per-procedure score rounding when all five summaries are available.",
            "Legacy Gemma same-generator scores, when supplied, are analyzed separately as a reproducibility audit.",
        ]
    )
    (output_root / "candidate_selection_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.bootstrap_reps <= 0:
        raise ValueError("--bootstrap-reps must be positive")
    if not (0.0 < args.confidence < 1.0):
        raise ValueError("--confidence must be between 0 and 1")

    input_roots = [Path(x).expanduser().resolve() for x in args.input_root]
    output_root = Path(args.output_root).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("run-1c0f: NPR cross-generator scoring-model selection")
    print("=" * 80)
    print(f"Input roots         : {', '.join(str(x) for x in input_roots)}")
    print(f"Output root         : {output_root}")
    print(f"Bootstrap replicates: {args.bootstrap_reps}")
    print(f"Random seed         : {args.seed}")
    print(f"Confidence level    : {args.confidence}")
    print("Bootstrap unit      : mixed-authorship file within length bucket")
    print("=" * 80)

    cells, cell_paths = discover_cells(input_roots)
    support_qc, target_references = validate_target_alignment(cells)
    support_qc.to_csv(output_root / "prediction_support_qc.csv", index=False)

    designs = build_bootstrap_designs(target_references, args.bootstrap_reps, args.seed)
    persisted_point, boot = compute_all_auc_draws(cells, designs)

    # Validate scorer-row summaries against AUROC recomputed from persisted
    # six-decimal NPR scores before producing paper-facing point estimates.
    row_summaries = find_row_summaries(input_roots)
    summary_qc = row_summary_qc(row_summaries, persisted_point, cells)
    summary_qc.to_csv(output_root / "row_summary_qc.csv", index=False)
    failed_qc = summary_qc[summary_qc["qc_status"] == "FAIL"]
    if not failed_qc.empty:
        raise ValueError(f"Row-summary AUROC QC failed beyond the rounding bound:\n{failed_qc}")

    if summary_qc["row_summary_found"].all():
        # Use scorer-row AUROCs for the paper-facing point matrix because they
        # were computed from full-precision NPR values before CSV rounding.
        point = point_matrix_from_row_summaries(row_summaries)
        point_source = "row_summary_full_precision_auc"
    else:
        # Fall back consistently to persisted-score AUROCs only when a complete
        # set of row summaries is unavailable.
        point = persisted_point
        point_source = "recomputed_from_persisted_six_decimal_scores"
        print("WARNING: Incomplete row summaries; using persisted-score AUROCs for all 25 point estimates.")

    matrix = pd.DataFrame(point, index=CANDIDATES, columns=TARGETS)
    matrix.index.name = "scoring_model_key"
    matrix.reset_index().to_csv(output_root / "cross_generator_auroc_matrix.csv", index=False)

    point_df, arrays = summarize_candidate_metrics(point, boot)
    point_df.to_csv(output_root / "point_estimates.csv", index=False)

    same_summary = bootstrap_metric_summary(
        arrays["point_same"], arrays["boot_same"], args.confidence, "same_generator_auc"
    )
    transfer_summary = bootstrap_metric_summary(
        arrays["point_transfer"], arrays["boot_transfer"], args.confidence, "transfer_auc"
    )
    same_summary.to_csv(output_root / "bootstrap_same_generator_summary.csv", index=False)
    transfer_summary.to_csv(output_root / "bootstrap_transfer_summary.csv", index=False)

    pairwise_same = pairwise_summary(
        arrays["point_same"], arrays["boot_same"], args.confidence, "same_generator_auc"
    )
    pairwise_same.to_csv(output_root / "pairwise_same_generator_differences.csv", index=False)

    pairwise_transfer = pairwise_transfer_common_targets(point, boot, args.confidence)
    pairwise_transfer.to_csv(output_root / "pairwise_transfer_common_targets.csv", index=False)

    minimax_rows = []
    for i, c in enumerate(CANDIDATES):
        lo, hi = percentile_interval(arrays["boot_max_regret"][:, i], args.confidence)
        minimax_rows.append(
            {
                "scoring_model_key": c,
                "display_name": DISPLAY_NAMES[c],
                "observed_same_generator_auc": arrays["point_same"][i],
                "observed_transfer_auc": arrays["point_transfer"][i],
                "observed_same_generator_regret": arrays["point_same_regret"][i],
                "observed_transfer_regret": arrays["point_transfer_regret"][i],
                "observed_max_regret": arrays["point_max_regret"][i],
                "bootstrap_mean_max_regret": float(np.mean(arrays["boot_max_regret"][:, i])),
                "bootstrap_sd_max_regret": float(np.std(arrays["boot_max_regret"][:, i], ddof=1)),
                "ci_lower_max_regret": lo,
                "ci_upper_max_regret": hi,
                "expected_rank": float(np.mean(arrays["ranks"][:, i])),
                "p_top2": float(np.mean(arrays["ranks"][:, i] <= 2.0)),
                "p_minimize_max_regret": float(np.mean(arrays["is_minimax"][:, i])),
            }
        )
    minimax_df = pd.DataFrame(minimax_rows)
    minimax_df.to_csv(output_root / "minimax_regret_summary.csv", index=False)

    pareto_df = pd.DataFrame(
        {
            "scoring_model_key": CANDIDATES,
            "display_name": [DISPLAY_NAMES[c] for c in CANDIDATES],
            "observed_pareto_nondominated": point_df["observed_pareto_nondominated"].to_numpy(bool),
            "p_pareto_nondominated": np.mean(arrays["pareto"], axis=0),
        }
    )
    pareto_df.to_csv(output_root / "pareto_summary.csv", index=False)

    long_parts = []
    for i, c in enumerate(CANDIDATES):
        long_parts.append(
            pd.DataFrame(
                {
                    "replicate": np.arange(1, args.bootstrap_reps + 1, dtype=int),
                    "scoring_model_key": c,
                    "same_generator_auc": arrays["boot_same"][:, i],
                    "transfer_auc": arrays["boot_transfer"][:, i],
                    "same_generator_regret": arrays["boot_same_regret"][:, i],
                    "transfer_regret": arrays["boot_transfer_regret"][:, i],
                    "max_regret": arrays["boot_max_regret"][:, i],
                    "rank_by_max_regret": arrays["ranks"][:, i],
                    "pareto_nondominated": arrays["pareto"][:, i],
                    "minimizes_max_regret": arrays["is_minimax"][:, i],
                }
            )
        )
    bootstrap_long = pd.concat(long_parts, ignore_index=True)
    bootstrap_long.to_csv(output_root / "bootstrap_candidate_metrics.csv.gz", index=False, compression="gzip")

    gemma_audit_run = False
    if args.legacy_gemma_score_csv:
        legacy_path = Path(args.legacy_gemma_score_csv).expanduser().resolve()
        if not legacy_path.exists():
            raise FileNotFoundError(f"Legacy Gemma score CSV does not exist: {legacy_path}")
        gemma_audit = audit_gemma(cells[("gemma", "gemma")], legacy_path, output_root)
        gemma_audit.to_csv(output_root / "gemma_diagonal_audit.csv", index=False)
        gemma_audit_run = True

    selected = point_df.loc[point_df["selected_by_observed_minimax_regret"], "scoring_model_key"].tolist()
    write_methodology(output_root, args, selected, gemma_audit_run)
    write_candidate_summary(output_root, point_df, minimax_df, args.confidence)

    metadata = {
        "analysis": "run-1c0f v2 NPR cross-generator scoring-model selection",
        "paper_facing_point_estimate_source": point_source,
        "bootstrap_reps": args.bootstrap_reps,
        "seed": args.seed,
        "confidence": args.confidence,
        "candidates": list(CANDIDATES),
        "targets": list(TARGETS),
        "input_roots": [str(x) for x in input_roots],
        "input_score_files": {
            f"{c}::{t}": {"path": str(cell_paths[(c, t)]), "sha256": file_sha256(cell_paths[(c, t)])}
            for c in CANDIDATES
            for t in TARGETS
        },
        "legacy_gemma_score_csv": str(Path(args.legacy_gemma_score_csv).expanduser().resolve())
        if args.legacy_gemma_score_csv
        else None,
        "selected_by_observed_minimax_regret": selected,
        "bootstrap_unit": "mixed-authorship file stratified by implementation-length bucket",
    }
    (output_root / "run_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("\nObserved AUROC matrix:")
    print(matrix.to_string(float_format=lambda x: f"{x:.6f}"))
    print("\nObserved same-generator / transfer / max-regret summary:")
    print(
        point_df[
            ["display_name", "same_generator_auc", "transfer_auc", "max_regret", "selected_by_observed_minimax_regret"]
        ].to_string(index=False, float_format=lambda x: f"{x:.6f}")
    )
    print("\nBootstrap decision summary:")
    print(
        minimax_df[
            ["display_name", "observed_max_regret", "expected_rank", "p_top2", "p_minimize_max_regret"]
        ].sort_values("observed_max_regret").to_string(index=False, float_format=lambda x: f"{x:.6f}")
    )
    print(f"\nSelected by observed minimax regret: {', '.join(DISPLAY_NAMES[c] for c in selected)}")
    print(f"Outputs written to: {output_root}")
    print("Status: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
