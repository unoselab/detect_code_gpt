#!/usr/bin/env python3
"""Calibrate the SC2-7B NPR threshold from the pooled five-source benchmark.

This run-x-c01 analysis reuses the established strict-threshold calibration rule
from the earlier NPR calibration workflow while changing only the calibration
population: all five cross-generator target sources scored by StarCoder2-7B are
pooled with equal source weight.

Inputs
------
Five per-procedure score CSVs produced by the completed cross-generator scorer
row for ``starcoder2-7b``. Each source must contribute exactly 300 procedures:
150 HWC and 150 AGC, arranged as 10 length buckets with 15 HWC and 15 AGC per
bucket.

Outputs
-------
A deterministic strict ``NPR > tau`` threshold, pooled/source/bucket metrics,
calibrated predictions, a full threshold-candidate table, input provenance, and
QC summaries. This script never loads an LLM and never rescales or modifies NPR
scores.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)

SCRIPT_VERSION = "run-x-c01-v1"
ALGORITHM_VERSION = "overlap_final_full_window_valid_frontier_weighting-v1"
PARTIAL_BODY_POLICY = "any_valid_window_partial_success_full_windows-v2"
SCORING_MODEL_KEY = "starcoder2-7b"
SCORING_MODEL_NAME = "bigcode/starcoder2-7b"
RANDOM_SEED = 20260723
REFERENCE_SAME_SOURCE_THRESHOLD = 1.571637

TARGET_SOURCES = (
    "codellama-7b",
    "starcoder2-7b",
    "starcoder2-15b-instruct-v0.1",
    "gpt-oss",
    "gemma",
)

SCORE_FILE_TEMPLATE = "npr_scores_npr-xgen_score-{scorer}_target-{target}.csv"


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of one input artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(data: object, path: Path) -> None:
    """Write JSON atomically so interrupted runs do not leave partial metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    tmp.replace(path)


def select_threshold(y_true: np.ndarray, y_score: np.ndarray) -> tuple[pd.DataFrame, pd.Series]:
    """Evaluate strict ``score > threshold`` candidates deterministically.

    The ranking rule intentionally matches the established NPR calibration:
    maximize Youden's J; on ties maximize balanced accuracy; on any remaining
    tie choose the smaller threshold.
    """
    unique_scores = sorted({float(value) for value in y_score if math.isfinite(float(value))})
    if not unique_scores:
        raise RuntimeError("No finite scores were available for calibration.")

    epsilon = np.finfo(float).eps
    thresholds = [unique_scores[0] - epsilon, *unique_scores, unique_scores[-1] + epsilon]
    positives = int((y_true == 1).sum())
    negatives = int((y_true == 0).sum())
    rows: list[dict[str, Any]] = []

    for threshold in thresholds:
        pred = (y_score > threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
        tpr = tp / positives if positives else float("nan")
        fpr = fp / negatives if negatives else float("nan")
        specificity = 1.0 - fpr
        balanced_accuracy = (tpr + specificity) / 2.0
        rows.append(
            {
                "threshold": float(threshold),
                "tn": int(tn),
                "fp": int(fp),
                "fn": int(fn),
                "tp": int(tp),
                "tpr": float(tpr),
                "fpr": float(fpr),
                "specificity": float(specificity),
                "youden_j": float(tpr - fpr),
                "balanced_accuracy": float(balanced_accuracy),
                "accuracy": float(accuracy_score(y_true, pred)),
                "hwc_f1": float(f1_score(y_true, pred, pos_label=0, zero_division=0)),
                "agc_f1": float(f1_score(y_true, pred, pos_label=1, zero_division=0)),
                "macro_f1": float(f1_score(y_true, pred, average="macro", zero_division=0)),
            }
        )

    candidates = pd.DataFrame(rows)
    ranked = candidates.sort_values(
        ["youden_j", "balanced_accuracy", "threshold"],
        ascending=[False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    return candidates, ranked.iloc[0]


def metric_row(frame: pd.DataFrame, threshold: float, scope: str, scope_value: str) -> dict[str, Any]:
    """Compute AUROC and operating-point metrics at the pooled threshold."""
    y_true = frame["label"].to_numpy(dtype=int)
    y_score = frame["npr"].to_numpy(dtype=float)
    pred = (y_score > threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    positives = int((y_true == 1).sum())
    negatives = int((y_true == 0).sum())
    tpr = tp / positives if positives else float("nan")
    fpr = fp / negatives if negatives else float("nan")
    specificity = 1.0 - fpr
    return {
        "scope": scope,
        "scope_value": scope_value,
        "n_total": int(len(frame)),
        "n_hwc": negatives,
        "n_agc": positives,
        "auroc": float(roc_auc_score(y_true, y_score)),
        "threshold": float(threshold),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "tpr": float(tpr),
        "fpr": float(fpr),
        "specificity": float(specificity),
        "youden_j": float(tpr - fpr),
        "balanced_accuracy": float((tpr + specificity) / 2.0),
        "accuracy": float(accuracy_score(y_true, pred)),
        "hwc_f1": float(f1_score(y_true, pred, pos_label=0, zero_division=0)),
        "agc_f1": float(f1_score(y_true, pred, pos_label=1, zero_division=0)),
        "macro_f1": float(f1_score(y_true, pred, average="macro", zero_division=0)),
        "hwc_mean_npr": float(frame.loc[frame["label"] == 0, "npr"].mean()),
        "agc_mean_npr": float(frame.loc[frame["label"] == 1, "npr"].mean()),
    }


def load_source_csv(path: Path, expected_target: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Load and hard-QC one 300-procedure target-source score file."""
    frame = pd.read_csv(path, low_memory=False)
    required = {
        "target_source",
        "scoring_model_key",
        "scoring_model_name",
        "benchmark_type",
        "file_id",
        "function_id",
        "role",
        "label",
        "npr",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path}: missing required columns: {missing}")

    frame = frame.copy()
    frame["label"] = pd.to_numeric(frame["label"], errors="raise").astype(int)
    frame["npr"] = pd.to_numeric(frame["npr"], errors="coerce")
    valid = frame.loc[frame["label"].isin([0, 1]) & np.isfinite(frame["npr"])].copy()

    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, observed: Any, expected: Any, severity: str = "hard") -> None:
        checks.append(
            {
                "target_source": expected_target,
                "check_name": name,
                "severity": severity,
                "passed": bool(passed),
                "observed": observed,
                "expected": expected,
            }
        )

    add_check("row_count", len(frame) == 300, len(frame), 300)
    add_check("valid_score_count", len(valid) == 300, len(valid), 300)
    n_hwc = int((valid["label"] == 0).sum())
    n_agc = int((valid["label"] == 1).sum())
    add_check("balanced_classes", n_hwc == 150 and n_agc == 150, f"{n_hwc}/{n_agc}", "150/150")

    target_values = sorted({str(x) for x in valid["target_source"].dropna().unique()})
    add_check("target_source_identity", target_values == [expected_target], target_values, [expected_target])

    scorer_values = sorted({str(x) for x in valid["scoring_model_key"].dropna().unique()})
    add_check("scoring_model_key_identity", scorer_values == [SCORING_MODEL_KEY], scorer_values, [SCORING_MODEL_KEY])

    model_values = sorted({str(x) for x in valid["scoring_model_name"].dropna().unique()})
    add_check("scoring_model_name_identity", model_values == [SCORING_MODEL_NAME], model_values, [SCORING_MODEL_NAME])

    labels_roles_ok = bool(
        (((valid["label"] == 0) & (valid["role"].astype(str) == "HWC")) |
         ((valid["label"] == 1) & (valid["role"].astype(str) == "AGC"))).all()
    )
    add_check("label_role_consistency", labels_roles_ok, labels_roles_ok, True)

    buckets = sorted(valid["benchmark_type"].astype(str).unique())
    add_check("bucket_count", len(buckets) == 10, len(buckets), 10)
    bad_buckets: list[str] = []
    for bucket, group in valid.groupby("benchmark_type", sort=True):
        b_hwc = int((group["label"] == 0).sum())
        b_agc = int((group["label"] == 1).sum())
        if b_hwc != 15 or b_agc != 15:
            bad_buckets.append(f"{bucket}:{b_hwc}/{b_agc}")
    add_check("bucket_balance", not bad_buckets, ";".join(bad_buckets) if bad_buckets else "all 15/15", "all 15/15")

    identity_cols = ["benchmark_type", "file_id", "function_id", "label"]
    unique_identity_count = int(valid[identity_cols].drop_duplicates().shape[0])
    add_check("within_source_unique_procedure_identity", unique_identity_count == 300, unique_identity_count, 300)

    hard_failures = [row for row in checks if row["severity"] == "hard" and not row["passed"]]
    if hard_failures:
        failed = ", ".join(row["check_name"] for row in hard_failures)
        raise RuntimeError(f"Input QC failed for {expected_target}: {failed}")

    valid["calibration_source"] = expected_target
    valid["input_file"] = str(path.resolve())
    return valid, checks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate a pooled five-source strict NPR threshold for StarCoder2-7B."
    )
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reference-same-source-threshold", type=float, default=REFERENCE_SAME_SOURCE_THRESHOLD)
    parser.add_argument("--reference-threshold-tolerance", type=float, default=1e-6)
    args = parser.parse_args()

    input_root = args.input_root.resolve()
    output_dir = args.output_dir.resolve()
    qc_dir = output_dir / "qc"
    output_dir.mkdir(parents=True, exist_ok=True)
    qc_dir.mkdir(parents=True, exist_ok=True)

    frames: list[pd.DataFrame] = []
    source_checks: list[dict[str, Any]] = []
    input_manifest: list[dict[str, Any]] = []

    for target in TARGET_SOURCES:
        path = input_root / SCORE_FILE_TEMPLATE.format(scorer=SCORING_MODEL_KEY, target=target)
        if not path.is_file():
            raise FileNotFoundError(f"Missing required input score file: {path}")
        valid, checks = load_source_csv(path, target)
        frames.append(valid)
        source_checks.extend(checks)
        input_manifest.append(
            {
                "target_source": target,
                "path": str(path),
                "sha256": sha256_file(path),
                "rows": int(len(valid)),
                "n_hwc": int((valid["label"] == 0).sum()),
                "n_agc": int((valid["label"] == 1).sum()),
            }
        )

    pooled = pd.concat(frames, ignore_index=True)
    y_true = pooled["label"].to_numpy(dtype=int)
    y_score = pooled["npr"].to_numpy(dtype=float)

    pooled_n_hwc = int((pooled["label"] == 0).sum())
    pooled_n_agc = int((pooled["label"] == 1).sum())
    hard_checks: list[dict[str, Any]] = [
        {
            "target_source": "POOLED",
            "check_name": "source_count",
            "severity": "hard",
            "passed": len(frames) == 5,
            "observed": len(frames),
            "expected": 5,
        },
        {
            "target_source": "POOLED",
            "check_name": "pooled_valid_count",
            "severity": "hard",
            "passed": len(pooled) == 1500,
            "observed": len(pooled),
            "expected": 1500,
        },
        {
            "target_source": "POOLED",
            "check_name": "pooled_balanced_classes",
            "severity": "hard",
            "passed": pooled_n_hwc == 750 and pooled_n_agc == 750,
            "observed": f"{pooled_n_hwc}/{pooled_n_agc}",
            "expected": "750/750",
        },
        {
            "target_source": "POOLED",
            "check_name": "equal_source_weight",
            "severity": "hard",
            "passed": all(len(frame) == 300 for frame in frames),
            "observed": "/".join(str(len(frame)) for frame in frames),
            "expected": "300/300/300/300/300",
        },
    ]

    candidates, best = select_threshold(y_true, y_score)
    threshold = float(best["threshold"])
    pooled_pred = (y_score > threshold).astype(int)
    pooled_auc = float(roc_auc_score(y_true, y_score))

    # Recompute the SC2 same-source threshold with the same strict rule as a
    # non-blocking audit against the prior 1.571637 longitudinal threshold.
    same_source = pooled.loc[pooled["calibration_source"] == "starcoder2-7b"].copy()
    _, same_best = select_threshold(
        same_source["label"].to_numpy(dtype=int),
        same_source["npr"].to_numpy(dtype=float),
    )
    same_source_threshold = float(same_best["threshold"])
    reference_delta = same_source_threshold - float(args.reference_same_source_threshold)
    reference_match = abs(reference_delta) <= float(args.reference_threshold_tolerance)

    warning_checks = [
        {
            "target_source": "starcoder2-7b",
            "check_name": "prior_same_source_threshold_reproduction",
            "severity": "warning",
            "passed": reference_match,
            "observed": same_source_threshold,
            "expected": float(args.reference_same_source_threshold),
        }
    ]

    candidates.to_csv(output_dir / "sc2_pooled_threshold_candidates.csv", index=False)
    pooled.assign(predict_agc_sc2_pooled_threshold=pooled_pred).to_csv(
        output_dir / "sc2_pooled_calibrated_predictions.csv", index=False
    )

    pooled_metrics = metric_row(pooled, threshold, "pooled", "all-five-sources")
    pd.DataFrame([pooled_metrics]).to_csv(output_dir / "sc2_pooled_overall_metrics.csv", index=False)

    source_metric_rows = [
        metric_row(group, threshold, "target_source", str(source))
        for source, group in pooled.groupby("calibration_source", sort=False)
    ]
    pd.DataFrame(source_metric_rows).to_csv(output_dir / "sc2_pooled_source_metrics.csv", index=False)

    source_bucket_rows: list[dict[str, Any]] = []
    for (source, bucket), group in pooled.groupby(["calibration_source", "benchmark_type"], sort=True):
        source_bucket_rows.append(metric_row(group, threshold, "source_bucket", f"{source}::{bucket}"))
    pd.DataFrame(source_bucket_rows).to_csv(output_dir / "sc2_pooled_source_bucket_metrics.csv", index=False)

    pooled_bucket_rows = [
        metric_row(group, threshold, "pooled_bucket", str(bucket))
        for bucket, group in pooled.groupby("benchmark_type", sort=True)
    ]
    pd.DataFrame(pooled_bucket_rows).to_csv(output_dir / "sc2_pooled_bucket_metrics.csv", index=False)

    pd.DataFrame(input_manifest).to_csv(output_dir / "input_manifest.csv", index=False)

    all_checks = pd.DataFrame(source_checks + hard_checks + warning_checks)
    all_checks.to_csv(qc_dir / "sc2_pooled_calibration_checks.csv", index=False)

    hard_failed = int(((all_checks["severity"] == "hard") & (~all_checks["passed"])).sum())
    warning_failed = int(((all_checks["severity"] == "warning") & (~all_checks["passed"])).sum())
    if hard_failed:
        status = "FAIL"
    elif warning_failed:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"

    # Count exact objective ties before the deterministic smallest-threshold tie break.
    same_objective = candidates.loc[
        np.isclose(candidates["youden_j"], float(best["youden_j"]), rtol=0.0, atol=1e-15)
        & np.isclose(candidates["balanced_accuracy"], float(best["balanced_accuracy"]), rtol=0.0, atol=1e-15)
    ]

    specification = {
        "status": "frozen_candidate" if hard_failed == 0 else "failed",
        "script_version": SCRIPT_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "partial_body_policy": PARTIAL_BODY_POLICY,
        "scoring_model_key": SCORING_MODEL_KEY,
        "scoring_model": SCORING_MODEL_NAME,
        "window_size_literal_space_tokens": 128,
        "window_policy": "full_size_final_window_shifted_backward_with_overlap",
        "function_aggregation": "valid_frontier_weighted_mean",
        "perturbations_per_window": 50,
        "perturbation_type": "random-insert-space+newline",
        "random_seed": RANDOM_SEED,
        "calibration_population": "pooled_equal_weight_five_generation_sources",
        "target_sources": list(TARGET_SOURCES),
        "benchmark_bodies": int(len(pooled)),
        "human_bodies": pooled_n_hwc,
        "generated_bodies": pooled_n_agc,
        "bodies_per_source": 300,
        "human_bodies_per_source": 150,
        "generated_bodies_per_source": 150,
        "agc_threshold": threshold,
        "decision_rule": "procedure_npr > agc_threshold",
        "calibration_method": "maximum_youden_j",
        "tie_breaking_rule": [
            "maximum_youden_j",
            "maximum_balanced_accuracy",
            "smallest_threshold",
        ],
        "objective_tie_count_before_threshold_tiebreak": int(len(same_objective)),
        "overall_auroc": pooled_auc,
        "tpr": float(best["tpr"]),
        "fpr": float(best["fpr"]),
        "specificity": float(best["specificity"]),
        "balanced_accuracy": float(best["balanced_accuracy"]),
        "youden_j": float(best["youden_j"]),
        "tn": int(best["tn"]),
        "fp": int(best["fp"]),
        "fn": int(best["fn"]),
        "tp": int(best["tp"]),
        "same_source_sc2_threshold_recomputed": same_source_threshold,
        "prior_same_source_threshold_reference": float(args.reference_same_source_threshold),
        "prior_same_source_threshold_delta": reference_delta,
        "prior_same_source_threshold_match_within_tolerance": reference_match,
        "reference_threshold_tolerance": float(args.reference_threshold_tolerance),
        "input_root": str(input_root),
        "input_manifest": input_manifest,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    atomic_json(specification, output_dir / "sc2_pooled_threshold_specification.json")

    summary = {
        "status": status,
        "hard_failed_checks": hard_failed,
        "warning_failed_checks": warning_failed,
        "threshold": threshold,
        "decision_rule": "NPR_proc > threshold",
        "auroc": pooled_auc,
        "tpr": float(best["tpr"]),
        "specificity": float(best["specificity"]),
        "balanced_accuracy": float(best["balanced_accuracy"]),
        "youden_j": float(best["youden_j"]),
        "tn": int(best["tn"]),
        "fp": int(best["fp"]),
        "fn": int(best["fn"]),
        "tp": int(best["tp"]),
        "valid_bodies": int(len(pooled)),
        "n_hwc": pooled_n_hwc,
        "n_agc": pooled_n_agc,
        "same_source_sc2_threshold_recomputed": same_source_threshold,
        "prior_same_source_threshold_reference": float(args.reference_same_source_threshold),
        "prior_same_source_threshold_delta": reference_delta,
        "objective_tie_count_before_threshold_tiebreak": int(len(same_objective)),
    }
    atomic_json(summary, qc_dir / "sc2_pooled_calibration_summary.json")

    print("=" * 78)
    print("run-x-c01 SC2-7B pooled five-source NPR threshold calibration")
    print("=" * 78)
    print(f"status                         : {status}")
    print(f"valid procedures               : {len(pooled)} (HWC={pooled_n_hwc}, AGC={pooled_n_agc})")
    print(f"pooled AUROC                   : {pooled_auc:.6f}")
    print(f"selected strict threshold tau  : {threshold:.9f}")
    print(f"decision rule                  : NPR_proc > {threshold:.9f}")
    print(f"TPR / specificity              : {float(best['tpr']):.6f} / {float(best['specificity']):.6f}")
    print(f"balanced accuracy / Youden J   : {float(best['balanced_accuracy']):.6f} / {float(best['youden_j']):.6f}")
    print(f"confusion TN/FP/FN/TP          : {int(best['tn'])}/{int(best['fp'])}/{int(best['fn'])}/{int(best['tp'])}")
    print(f"same-source SC2 tau recomputed : {same_source_threshold:.9f}")
    print(f"prior SC2 tau reference        : {float(args.reference_same_source_threshold):.9f}")
    print(f"reference delta                : {reference_delta:+.9f}")
    print(f"hard / warning failed checks   : {hard_failed} / {warning_failed}")
    print(f"output directory               : {output_dir}")
    print("=" * 78)

    raise SystemExit(0 if hard_failed == 0 else 5)


if __name__ == "__main__":
    main()
