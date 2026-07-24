#!/usr/bin/env python3
"""Calibrate the v6 overlap-window NPR threshold from the 300-body benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    roc_auc_score,
    roc_curve,
)

SCRIPT_VERSION = "run-1c0b-v1"
ALGORITHM_VERSION = "overlap_final_full_window_valid_frontier_weighting-v1"
PARTIAL_BODY_POLICY = "any_valid_window_partial_success_full_windows-v2"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(data: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    tmp.replace(path)


def select_threshold(y_true: np.ndarray, y_score: np.ndarray) -> tuple[pd.DataFrame, pd.Series]:
    """Evaluate strict `score > threshold` candidates deterministically."""
    unique_scores = sorted({float(value) for value in y_score if math.isfinite(float(value))})
    if not unique_scores:
        raise RuntimeError("No finite scores were available for calibration.")
    epsilon = np.finfo(float).eps
    thresholds = [unique_scores[0] - epsilon, *unique_scores, unique_scores[-1] + epsilon]
    rows = []
    positives = int((y_true == 1).sum())
    negatives = int((y_true == 0).sum())
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-scores", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    frame = pd.read_csv(args.input_scores, low_memory=False)
    required = {"label", "npr", "benchmark_type", "role"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    frame["label"] = pd.to_numeric(frame["label"], errors="raise").astype(int)
    frame["npr"] = pd.to_numeric(frame["npr"], errors="coerce")
    valid = frame.loc[frame["label"].isin([0, 1]) & np.isfinite(frame["npr"])].copy()
    if len(valid) != 300:
        raise RuntimeError(f"Expected 300 valid benchmark bodies, observed {len(valid)}")
    if int((valid["label"] == 0).sum()) != 150 or int((valid["label"] == 1).sum()) != 150:
        raise RuntimeError("Expected exactly 150 HWC and 150 AGC bodies.")

    y_true = valid["label"].to_numpy(dtype=int)
    y_score = valid["npr"].to_numpy(dtype=float)
    candidates, best = select_threshold(y_true, y_score)
    threshold = float(best["threshold"])
    pred = (y_score > threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    auc = float(roc_auc_score(y_true, y_score))

    out = args.output_dir
    qc = out / "qc"
    out.mkdir(parents=True, exist_ok=True)
    qc.mkdir(parents=True, exist_ok=True)

    candidates.to_csv(out / "mixedcode_overlap_threshold_candidates.csv", index=False)
    valid.assign(predict_agc_overlap_threshold=pred).to_csv(
        out / "mixedcode_overlap_calibrated_predictions.csv", index=False
    )
    pd.DataFrame(
        [{
            "threshold": threshold,
            "auroc": auc,
            "tpr": float(best["tpr"]),
            "fpr": float(best["fpr"]),
            "specificity": float(best["specificity"]),
            "youden_j": float(best["youden_j"]),
            "balanced_accuracy": float(best["balanced_accuracy"]),
            "accuracy": float(accuracy_score(y_true, pred)),
            "hwc_f1": float(f1_score(y_true, pred, pos_label=0)),
            "agc_f1": float(f1_score(y_true, pred, pos_label=1)),
            "macro_f1": float(f1_score(y_true, pred, average="macro")),
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        }]
    ).to_csv(out / "mixedcode_overlap_overall_metrics.csv", index=False)

    bucket_rows = []
    for bucket, group in valid.groupby("benchmark_type", sort=True):
        bucket_rows.append({
            "benchmark_type": bucket,
            "n_hwc": int((group["label"] == 0).sum()),
            "n_agc": int((group["label"] == 1).sum()),
            "auroc": float(roc_auc_score(group["label"], group["npr"])),
            "hwc_mean_npr": float(group.loc[group["label"] == 0, "npr"].mean()),
            "agc_mean_npr": float(group.loc[group["label"] == 1, "npr"].mean()),
        })
    pd.DataFrame(bucket_rows).to_csv(out / "mixedcode_overlap_bucket_metrics.csv", index=False)

    spec = {
        "status": "frozen",
        "script_version": SCRIPT_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "partial_body_policy": PARTIAL_BODY_POLICY,
        "scoring_model": "bigcode/starcoder2-7b",
        "window_size_literal_space_tokens": 128,
        "window_policy": "full_size_final_window_shifted_backward_with_overlap",
        "function_aggregation": "valid_frontier_weighted_mean",
        "perturbations_per_window": 50,
        "perturbation_type": "random-insert-space+newline",
        "random_seed": 20260723,
        "agc_threshold": threshold,
        "decision_rule": "function_npr > agc_threshold",
        "threshold_calibration_dataset": "table2_mixedcode_50_files_300_bodies",
        "benchmark_bodies": 300,
        "human_bodies": 150,
        "generated_bodies": 150,
        "calibration_method": "maximum_youden_j",
        "tie_breaking_rule": [
            "maximum_youden_j",
            "maximum_balanced_accuracy",
            "smallest_threshold",
        ],
        "overall_auroc": auc,
        "tpr": float(best["tpr"]),
        "fpr": float(best["fpr"]),
        "youden_j": float(best["youden_j"]),
        "input_scores": str(args.input_scores.resolve()),
        "input_scores_sha256": sha256_file(args.input_scores),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    atomic_json(spec, out / "mixedcode_overlap_threshold_specification.json")

    checks = pd.DataFrame([
        {"check_name": "valid_body_count", "passed": len(valid) == 300, "observed": len(valid), "expected": 300},
        {"check_name": "balanced_classes", "passed": int((valid.label == 0).sum()) == 150 and int((valid.label == 1).sum()) == 150, "observed": f"{int((valid.label == 0).sum())}/{int((valid.label == 1).sum())}", "expected": "150/150"},
        {"check_name": "finite_threshold", "passed": math.isfinite(threshold), "observed": threshold, "expected": "finite"},
        {"check_name": "finite_auroc", "passed": math.isfinite(auc), "observed": auc, "expected": "finite"},
        {"check_name": "confusion_total", "passed": int(tn+fp+fn+tp) == 300, "observed": int(tn+fp+fn+tp), "expected": 300},
    ])
    checks.to_csv(qc / "mixedcode_overlap_calibration_checks.csv", index=False)
    summary = {
        "status": "PASS" if bool(checks["passed"].all()) else "FAIL",
        "failed_checks": int((~checks["passed"]).sum()),
        "threshold": threshold,
        "auroc": auc,
        "valid_bodies": int(len(valid)),
    }
    atomic_json(summary, qc / "mixedcode_overlap_calibration_summary.json")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["status"] == "PASS" else 5)


if __name__ == "__main__":
    main()
