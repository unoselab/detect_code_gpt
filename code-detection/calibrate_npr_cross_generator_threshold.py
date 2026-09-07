#!/usr/bin/env python3
"""Calibrate the pooled cross-generator NPR threshold for the selected GPT-OSS scorer.

This experiment records the threshold used after run-1c0f selected GPT-OSS-120B
as the NPR scoring model. The calibration sample pools the five balanced
mixed-authorship benchmarks scored by GPT-OSS-120B (5 x 300 procedures).

Primary decision rule:
    procedure_npr > threshold

Threshold selection rule:
    1. maximize Youden's J;
    2. maximize balanced accuracy;
    3. choose the smaller threshold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, roc_auc_score

SCRIPT_VERSION = "run-1c0fg-v1"
ALGORITHM_VERSION = "overlap_final_full_window_valid_frontier_weighting-v1"
PARTIAL_BODY_POLICY = "any_valid_window_partial_success_full_windows-v2"
SCORING_MODEL_KEY = "gpt-oss"
SCORING_MODEL_NAME = "openai/gpt-oss-120b"
RANDOM_SEED = 20260723
TARGET_SOURCES = (
    "codellama-7b",
    "starcoder2-7b",
    "starcoder2-15b-instruct-v0.1",
    "gpt-oss",
    "gemma",
)
EXPECTED_ROWS_PER_SOURCE = 300
EXPECTED_HWC_PER_SOURCE = 150
EXPECTED_AGC_PER_SOURCE = 150
EXPECTED_BUCKETS_PER_SOURCE = 10
EXPECTED_FILES_PER_BUCKET = 5
EXPECTED_PROCEDURES_PER_FILE = 6
EXPECTED_HWC_PER_FILE = 3
EXPECTED_AGC_PER_FILE = 3


def sha256_file(path: Path) -> str:
    """Return a SHA-256 digest for one input or output file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(data: object, path: Path) -> None:
    """Write JSON atomically so a failed run does not leave a partial record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    tmp.replace(path)


def as_bool(value: object) -> bool:
    """Convert common CSV boolean representations to a Python bool."""
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Cannot interpret boolean value: {value!r}")


def expected_score_path(input_root: Path, target_source: str) -> Path:
    """Construct the exact per-procedure score path for one target source."""
    return input_root / f"npr_scores_npr-xgen_score-{SCORING_MODEL_KEY}_target-{target_source}.csv"


def evaluate_threshold(y_true: np.ndarray, y_score: np.ndarray, threshold: float) -> dict[str, float | int]:
    """Evaluate the strict NPR > threshold decision rule."""
    pred = (y_score > threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    positives = int((y_true == 1).sum())
    negatives = int((y_true == 0).sum())
    tpr = tp / positives if positives else float("nan")
    fpr = fp / negatives if negatives else float("nan")
    specificity = tn / negatives if negatives else float("nan")
    balanced_accuracy = (tpr + specificity) / 2.0
    return {
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
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def select_threshold(y_true: np.ndarray, y_score: np.ndarray) -> tuple[pd.DataFrame, pd.Series]:
    """Evaluate strict score > threshold candidates and apply the prespecified ranking rule."""
    unique_scores = sorted({float(value) for value in y_score if math.isfinite(float(value))})
    if not unique_scores:
        raise RuntimeError("No finite NPR scores were available for calibration.")

    # Include two guard candidates so the all-positive and all-negative endpoints
    # are represented without changing the strict decision rule.
    thresholds = [
        float(np.nextafter(unique_scores[0], -np.inf)),
        *unique_scores,
        float(np.nextafter(unique_scores[-1], np.inf)),
    ]
    rows = [evaluate_threshold(y_true, y_score, threshold) for threshold in thresholds]
    candidates = pd.DataFrame(rows)
    ranked = candidates.sort_values(
        ["youden_j", "balanced_accuracy", "threshold"],
        ascending=[False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    return candidates, ranked.iloc[0]


def validate_selection(selection_path: Path) -> dict[str, object]:
    """Confirm that run-1c0f selected GPT-OSS-120B before calibrating its threshold."""
    frame = pd.read_csv(selection_path, low_memory=False)
    required = {"scoring_model_key", "selected_by_observed_minimax_regret"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Selection summary is missing required columns: {missing}")

    selected_mask = frame["selected_by_observed_minimax_regret"].map(as_bool)
    selected = frame.loc[selected_mask].copy()
    if len(selected) != 1:
        raise RuntimeError(f"Expected exactly one selected scoring model, observed {len(selected)}")

    selected_key = str(selected.iloc[0]["scoring_model_key"])
    if selected_key != SCORING_MODEL_KEY:
        raise RuntimeError(
            f"run-1c0f selected {selected_key!r}, but run-1c0fg expects {SCORING_MODEL_KEY!r}."
        )

    record: dict[str, object] = {
        "selection_summary": str(selection_path.resolve()),
        "selection_summary_sha256": sha256_file(selection_path),
        "selected_scoring_model_key": selected_key,
    }
    for column in ("display_name", "same_generator_auc", "transfer_auc", "max_regret"):
        if column in selected.columns:
            value = selected.iloc[0][column]
            record[column] = float(value) if column.endswith("auc") or column == "max_regret" else str(value)
    return record


def validate_source_frame(frame: pd.DataFrame, target_source: str, path: Path) -> list[dict[str, object]]:
    """Validate one 300-procedure generation-source benchmark and return QC rows."""
    required = {
        "target_source",
        "scoring_model_key",
        "benchmark_type",
        "file_id",
        "function_id",
        "role",
        "label",
        "npr",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path.name}: missing required columns: {missing}")

    frame["label"] = pd.to_numeric(frame["label"], errors="raise").astype(int)
    frame["npr"] = pd.to_numeric(frame["npr"], errors="coerce")

    qc: list[dict[str, object]] = []

    def add_check(name: str, passed: bool, observed: object, expected: object) -> None:
        qc.append(
            {
                "target_source": target_source,
                "check_name": name,
                "passed": bool(passed),
                "observed": observed,
                "expected": expected,
            }
        )

    add_check("row_count", len(frame) == EXPECTED_ROWS_PER_SOURCE, len(frame), EXPECTED_ROWS_PER_SOURCE)
    add_check(
        "finite_npr_count",
        int(np.isfinite(frame["npr"]).sum()) == EXPECTED_ROWS_PER_SOURCE,
        int(np.isfinite(frame["npr"]).sum()),
        EXPECTED_ROWS_PER_SOURCE,
    )
    add_check(
        "valid_binary_labels",
        bool(frame["label"].isin([0, 1]).all()),
        sorted(frame["label"].unique().tolist()),
        "[0, 1]",
    )
    n_hwc = int((frame["label"] == 0).sum())
    n_agc = int((frame["label"] == 1).sum())
    add_check("hwc_count", n_hwc == EXPECTED_HWC_PER_SOURCE, n_hwc, EXPECTED_HWC_PER_SOURCE)
    add_check("agc_count", n_agc == EXPECTED_AGC_PER_SOURCE, n_agc, EXPECTED_AGC_PER_SOURCE)
    add_check(
        "target_source_identity",
        set(frame["target_source"].astype(str)) == {target_source},
        ",".join(sorted(set(frame["target_source"].astype(str)))),
        target_source,
    )
    add_check(
        "scoring_model_identity",
        set(frame["scoring_model_key"].astype(str)) == {SCORING_MODEL_KEY},
        ",".join(sorted(set(frame["scoring_model_key"].astype(str)))),
        SCORING_MODEL_KEY,
    )

    bucket_count = int(frame["benchmark_type"].nunique())
    add_check(
        "length_bucket_count",
        bucket_count == EXPECTED_BUCKETS_PER_SOURCE,
        bucket_count,
        EXPECTED_BUCKETS_PER_SOURCE,
    )

    bucket_ok = True
    file_geometry_ok = True
    for _, bucket in frame.groupby("benchmark_type", sort=True):
        if len(bucket) != 30 or int((bucket["label"] == 0).sum()) != 15 or int((bucket["label"] == 1).sum()) != 15:
            bucket_ok = False
        if int(bucket["file_id"].nunique()) != EXPECTED_FILES_PER_BUCKET:
            file_geometry_ok = False
        for _, mixed_file in bucket.groupby("file_id", sort=True):
            if (
                len(mixed_file) != EXPECTED_PROCEDURES_PER_FILE
                or int((mixed_file["label"] == 0).sum()) != EXPECTED_HWC_PER_FILE
                or int((mixed_file["label"] == 1).sum()) != EXPECTED_AGC_PER_FILE
            ):
                file_geometry_ok = False

    add_check("bucket_class_balance", bucket_ok, bucket_ok, "10 buckets x (15 HWC + 15 AGC)")
    add_check(
        "mixed_authorship_file_geometry",
        file_geometry_ok,
        file_geometry_ok,
        "5 files/bucket x (3 HWC + 3 AGC)",
    )

    identity_cols = ["benchmark_type", "file_id", "function_id"]
    unique_identities = int(frame[identity_cols].drop_duplicates().shape[0])
    add_check(
        "unique_procedure_identity",
        unique_identities == EXPECTED_ROWS_PER_SOURCE,
        unique_identities,
        EXPECTED_ROWS_PER_SOURCE,
    )

    failed = [row for row in qc if not row["passed"]]
    if failed:
        raise RuntimeError(f"Input QC failed for {target_source}: {failed}")
    return qc


def load_inputs(input_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and validate the five GPT-OSS scorer outputs used for pooled calibration."""
    frames: list[pd.DataFrame] = []
    manifest_rows: list[dict[str, object]] = []
    qc_rows: list[dict[str, object]] = []

    for target_source in TARGET_SOURCES:
        path = expected_score_path(input_root, target_source)
        if not path.is_file():
            raise FileNotFoundError(f"Required score CSV not found: {path}")

        frame = pd.read_csv(path, low_memory=False)
        qc_rows.extend(validate_source_frame(frame, target_source, path))
        frame = frame.loc[frame["label"].isin([0, 1]) & np.isfinite(frame["npr"])].copy()
        frame.insert(0, "calibration_target_source", target_source)
        frames.append(frame)

        manifest_rows.append(
            {
                "target_source": target_source,
                "input_path": str(path.resolve()),
                "sha256": sha256_file(path),
                "rows": int(len(frame)),
                "n_hwc": int((frame["label"] == 0).sum()),
                "n_agc": int((frame["label"] == 1).sum()),
            }
        )

    pooled = pd.concat(frames, ignore_index=True)
    expected_total = EXPECTED_ROWS_PER_SOURCE * len(TARGET_SOURCES)
    if len(pooled) != expected_total:
        raise RuntimeError(f"Expected {expected_total} pooled procedures, observed {len(pooled)}")
    if int((pooled["label"] == 0).sum()) != EXPECTED_HWC_PER_SOURCE * len(TARGET_SOURCES):
        raise RuntimeError("Pooled HWC count is not 750.")
    if int((pooled["label"] == 1).sum()) != EXPECTED_AGC_PER_SOURCE * len(TARGET_SOURCES):
        raise RuntimeError("Pooled AGC count is not 750.")

    return pooled, pd.DataFrame(manifest_rows), pd.DataFrame(qc_rows)


def source_metrics(pooled: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Report threshold performance separately for each generation source."""
    rows: list[dict[str, object]] = []
    for source in TARGET_SOURCES:
        group = pooled.loc[pooled["calibration_target_source"] == source]
        y_true = group["label"].to_numpy(dtype=int)
        y_score = group["npr"].to_numpy(dtype=float)
        metrics = evaluate_threshold(y_true, y_score, threshold)
        rows.append(
            {
                "target_source": source,
                "n_total": int(len(group)),
                "n_hwc": int((y_true == 0).sum()),
                "n_agc": int((y_true == 1).sum()),
                "auroc": float(roc_auc_score(y_true, y_score)),
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def write_methodology(path: Path, threshold: float, metrics: dict[str, float | int]) -> None:
    """Write a compact human-readable record of the calibration design."""
    text = f"""run-1c0fg v1: pooled cross-generator NPR threshold calibration

Purpose
-------
Record the procedure that calibrates the NPR decision threshold after run-1c0f
selects GPT-OSS-120B as the NPR scoring model.

Calibration sample
------------------
Scoring model: {SCORING_MODEL_NAME}
Generation sources: {', '.join(TARGET_SOURCES)}
Each source contributes 300 procedures: 150 HWC and 150 AGC.
Pooled sample: 1,500 procedures: 750 HWC and 750 AGC.
Each source contributes equally to the pooled calibration sample.

Decision rule
-------------
AGC-like signal if procedure_npr > threshold.

Threshold selection
-------------------
1. Maximize Youden's J = TPR - FPR.
2. If tied, maximize balanced accuracy.
3. If still tied, choose the smaller threshold.

Selected threshold
------------------
threshold = {threshold:.6f}
TPR = {float(metrics['tpr']):.6f}
FPR = {float(metrics['fpr']):.6f}
Specificity = {float(metrics['specificity']):.6f}
Balanced accuracy = {float(metrics['balanced_accuracy']):.6f}
Youden's J = {float(metrics['youden_j']):.6f}
TN = {int(metrics['tn'])}
FP = {int(metrics['fp'])}
FN = {int(metrics['fn'])}
TP = {int(metrics['tp'])}

No historical-repository outcomes are used in scoring-model selection or
threshold calibration.
"""
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-root",
        type=Path,
        required=True,
        help="Directory containing the five GPT-OSS cross-generator per-procedure score CSVs.",
    )
    parser.add_argument(
        "--selection-summary",
        type=Path,
        required=True,
        help="run-1c0f point_estimates.csv used to verify that GPT-OSS-120B was selected.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--expected-threshold",
        type=float,
        default=None,
        help="Optional reproducibility assertion; does not participate in threshold selection.",
    )
    parser.add_argument(
        "--threshold-tolerance",
        type=float,
        default=1e-12,
        help="Absolute tolerance for --expected-threshold QC.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_root = args.input_root.resolve()
    selection_summary = args.selection_summary.resolve()
    output_dir = args.output_dir.resolve()
    qc_dir = output_dir / "qc"
    output_dir.mkdir(parents=True, exist_ok=True)
    qc_dir.mkdir(parents=True, exist_ok=True)

    if not selection_summary.is_file():
        raise FileNotFoundError(f"Selection summary not found: {selection_summary}")

    selection_record = validate_selection(selection_summary)
    pooled, manifest, input_qc = load_inputs(input_root)

    y_true = pooled["label"].to_numpy(dtype=int)
    y_score = pooled["npr"].to_numpy(dtype=float)
    candidates, best = select_threshold(y_true, y_score)
    threshold = float(best["threshold"])
    metrics = evaluate_threshold(y_true, y_score, threshold)
    pooled_auc = float(roc_auc_score(y_true, y_score))

    pred = (y_score > threshold).astype(int)
    pooled_predictions = pooled.copy()
    pooled_predictions["predict_agc_pooled_threshold"] = pred

    manifest.to_csv(output_dir / "npr_pooled_input_manifest.csv", index=False)
    candidates.to_csv(output_dir / "npr_pooled_threshold_candidates.csv", index=False)
    pooled_predictions.to_csv(output_dir / "npr_pooled_calibrated_predictions.csv", index=False)
    source_metrics(pooled, threshold).to_csv(output_dir / "npr_pooled_source_metrics.csv", index=False)

    overall_row = {
        "scoring_model_key": SCORING_MODEL_KEY,
        "scoring_model_name": SCORING_MODEL_NAME,
        "n_sources": len(TARGET_SOURCES),
        "n_total": int(len(pooled)),
        "n_hwc": int((y_true == 0).sum()),
        "n_agc": int((y_true == 1).sum()),
        "auroc": pooled_auc,
        **metrics,
    }
    pd.DataFrame([overall_row]).to_csv(output_dir / "npr_pooled_overall_metrics.csv", index=False)

    checks: list[dict[str, object]] = input_qc.to_dict("records")

    def add_global_check(name: str, passed: bool, observed: object, expected: object) -> None:
        checks.append(
            {
                "target_source": "ALL",
                "check_name": name,
                "passed": bool(passed),
                "observed": observed,
                "expected": expected,
            }
        )

    add_global_check("selected_scoring_model", True, selection_record["selected_scoring_model_key"], SCORING_MODEL_KEY)
    add_global_check("pooled_row_count", len(pooled) == 1500, len(pooled), 1500)
    add_global_check("pooled_hwc_count", int((y_true == 0).sum()) == 750, int((y_true == 0).sum()), 750)
    add_global_check("pooled_agc_count", int((y_true == 1).sum()) == 750, int((y_true == 1).sum()), 750)
    add_global_check("finite_threshold", math.isfinite(threshold), threshold, "finite")
    add_global_check("finite_pooled_auroc", math.isfinite(pooled_auc), pooled_auc, "finite")
    add_global_check("confusion_total", int(metrics["tn"] + metrics["fp"] + metrics["fn"] + metrics["tp"]) == 1500, int(metrics["tn"] + metrics["fp"] + metrics["fn"] + metrics["tp"]), 1500)

    max_j = float(candidates["youden_j"].max())
    max_j_count = int(np.isclose(candidates["youden_j"], max_j, rtol=0.0, atol=1e-15).sum())
    add_global_check("unique_maximum_youden_j", max_j_count == 1, max_j_count, 1)
    observed_score_match = bool(np.isclose(y_score, threshold, rtol=0.0, atol=0.0).any())
    add_global_check("selected_threshold_is_observed_score", observed_score_match, observed_score_match, True)

    if args.expected_threshold is not None:
        difference = abs(threshold - float(args.expected_threshold))
        add_global_check(
            "expected_threshold_reproduction",
            difference <= args.threshold_tolerance,
            f"{threshold:.12f} (abs_diff={difference:.3e})",
            f"{float(args.expected_threshold):.12f} +/- {args.threshold_tolerance:.1e}",
        )

    checks_frame = pd.DataFrame(checks)
    checks_frame.to_csv(qc_dir / "npr_pooled_threshold_checks.csv", index=False)

    specification = {
        "status": "selected_for_downstream_longitudinal_analysis",
        "script_version": SCRIPT_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "partial_body_policy": PARTIAL_BODY_POLICY,
        "scoring_model_key": SCORING_MODEL_KEY,
        "scoring_model": SCORING_MODEL_NAME,
        "selection_provenance": selection_record,
        "window_size_literal_space_tokens": 128,
        "window_policy": "full_size_final_window_shifted_backward_with_overlap",
        "procedure_aggregation": "valid_frontier_weighted_mean",
        "perturbations_per_window": 50,
        "perturbation_type": "random-insert-space+newline",
        "random_seed": RANDOM_SEED,
        "agc_threshold": threshold,
        "decision_rule": "procedure_npr > agc_threshold",
        "threshold_calibration_dataset": "five_generation_source_mixed_authorship_benchmarks",
        "generation_sources": list(TARGET_SOURCES),
        "benchmark_procedures_per_source": EXPECTED_ROWS_PER_SOURCE,
        "pooled_procedures": int(len(pooled)),
        "human_procedures": int((y_true == 0).sum()),
        "generated_procedures": int((y_true == 1).sum()),
        "calibration_method": "maximum_youden_j",
        "tie_breaking_rule": [
            "maximum_youden_j",
            "maximum_balanced_accuracy",
            "smallest_threshold",
        ],
        "pooled_auroc": pooled_auc,
        "tpr": float(metrics["tpr"]),
        "fpr": float(metrics["fpr"]),
        "specificity": float(metrics["specificity"]),
        "balanced_accuracy": float(metrics["balanced_accuracy"]),
        "youden_j": float(metrics["youden_j"]),
        "tn": int(metrics["tn"]),
        "fp": int(metrics["fp"]),
        "fn": int(metrics["fn"]),
        "tp": int(metrics["tp"]),
        "input_root": str(input_root),
        "input_manifest": manifest.to_dict("records"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    atomic_json(specification, output_dir / "npr_pooled_threshold_specification.json")
    write_methodology(output_dir / "methodology.txt", threshold, metrics)

    all_passed = bool(checks_frame["passed"].all())
    summary = {
        "status": "PASS" if all_passed else "FAIL",
        "failed_checks": int((~checks_frame["passed"]).sum()),
        "scoring_model_key": SCORING_MODEL_KEY,
        "threshold": threshold,
        "pooled_auroc": pooled_auc,
        "tpr": float(metrics["tpr"]),
        "specificity": float(metrics["specificity"]),
        "balanced_accuracy": float(metrics["balanced_accuracy"]),
        "youden_j": float(metrics["youden_j"]),
        "tn": int(metrics["tn"]),
        "fp": int(metrics["fp"]),
        "fn": int(metrics["fn"]),
        "tp": int(metrics["tp"]),
        "pooled_procedures": int(len(pooled)),
    }
    atomic_json(summary, qc_dir / "npr_pooled_threshold_summary.json")

    print("=" * 80)
    print("run-1c0fg: pooled cross-generator NPR threshold calibration")
    print("=" * 80)
    print(f"Selected scoring model : {SCORING_MODEL_NAME}")
    print(f"Generation sources     : {', '.join(TARGET_SOURCES)}")
    print(f"Pooled procedures      : {len(pooled)} (HWC=750, AGC=750)")
    print(f"Pooled AUROC           : {pooled_auc:.6f}")
    print(f"Selected threshold     : {threshold:.6f}")
    print(f"Decision rule          : NPR_proc > {threshold:.6f}")
    print(f"TPR                    : {float(metrics['tpr']):.6f}")
    print(f"Specificity            : {float(metrics['specificity']):.6f}")
    print(f"Balanced accuracy      : {float(metrics['balanced_accuracy']):.6f}")
    print(f"Youden J               : {float(metrics['youden_j']):.6f}")
    print(f"Confusion matrix       : TN={metrics['tn']} FP={metrics['fp']} FN={metrics['fn']} TP={metrics['tp']}")
    print(f"Output directory       : {output_dir}")
    print(f"Status                 : {summary['status']}")
    print("=" * 80)

    raise SystemExit(0 if all_passed else 5)


if __name__ == "__main__":
    main()
