#!/usr/bin/env python3
"""Score the FUN subset of deterministic A09 NPR perturbation shards on R158.

A11 is the first long-running production scoring stage after A09/A10.  It does
not regenerate perturbations.  Instead, it reads A09's fixed original window
and ordered 50 perturbations, then delegates model loading and rank scoring to
the frozen A02 implementation.  This preserves the validated A02 scoring
configuration while separating expensive GPU scoring from CPU perturbation
materialization.

Scientific scope
----------------
- Category: FUN, i.e. unique primary code units whose A09 ``unit_groups``
  contains ``FUN``.  A unique SHA may also belong to another category; it is
  still scored only once here and can be reused downstream.
- GPU pool: the three homogeneous RTX A6000 devices on R158.
- Work assignment: A10 ``deterministic_lpt_by_fun_windows`` at whole logical-
  shard granularity.  A code unit never crosses logical shards, so all windows
  for a unit stay on one GPU.
- Perturbations: read exactly as prepared by A09.  A11 never calls perturbation
  generation during production scoring.
- NPR: mean perturbed log-rank / original log-rank, matching A02.
- Aggregation: preserve both space-by-token-weighted NPR and pooled log-rank
  components, matching A02.
- Classification: disabled.  No AGC/HWC or threshold columns are produced.

Resume/checkpoint policy
------------------------
Every attempted window is committed to a per-worker SQLite database.  A rerun
loads existing (code-unit SHA, window index) keys and skips them, so an
interruption loses at most the currently executing window.  Final CSV exports
are regenerated from SQLite after the selected workload is complete.

The production database contains scores and provenance only; it deliberately
omits the original/perturbed source strings because those remain frozen in A09.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
import platform
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np


SCRIPT_VERSION = "run-x-a11-v2"
CATEGORY = "FUN"
ASSIGNMENT_POLICY = "deterministic_lpt_by_fun_windows"
EXPECTED_A02_SHA256 = "57e0781a406d992fb045335a79b1cb97e5c0557de9582603401f6d402ef528a0"
EXPECTED_A02_CONFIG_FINGERPRINT = "78655715edc8699710a27f593cac5a8360067e803eac8c50a0765084edfa5fb2"
EXPECTED_A09_CONFIG_FINGERPRINT = "3f78c8c43aaa014cd0f5e1a5d1c2df7d4269deb55c4c999e4483d08a324dd9bb"
EXPECTED_A05_MANIFEST_SHA256 = "1acb3726f5c62e6154672f1aff592973c65a13e58dbfd37f8058560d1a474e6c"
EXPECTED_MODEL_REVISION = "bb9afde76d7945da5745592525db122d4d729eb1"
EXPECTED_FUN_WINDOWS = 307600
EXPECTED_FUN_PERTURBATIONS = 15380000
EXPECTED_FUN_UNIQUE_MEMBERSHIPS = 105635
EXPECTED_GPU_WINDOW_LOADS = [102541, 102505, 102554]

SCORING_MODEL = "bigcode/starcoder2-7b"
WINDOW_SIZE = 128
PERTURBATIONS_PER_WINDOW = 50
PERTURBATION_TYPE = "random-insert-space+newline"
RANDOM_SEED = 20260723
PCT_WORDS_MASKED = 0.5
SPAN_LENGTH = 2
PERTURBATION_CHUNK_SIZE = 10
N_PERTURBATION_ROUNDS = 1

CHECK_COLUMNS = ["check_name", "passed", "observed", "expected", "note"]
FAILURE_COLUMNS = [
    "logical_shard",
    "code_unit_sha256",
    "window_index",
    "stage",
    "error_type",
    "error_message",
]
REFERENCE_COLUMNS = [
    "logical_shard",
    "code_unit_sha256",
    "window_index",
    "prepared_perturbation_digest",
    "regenerated_perturbation_digest",
    "perturbations_exact_match",
    "fixed_original_log_rank",
    "regenerated_original_log_rank",
    "fixed_mean_perturbed_log_rank",
    "regenerated_mean_perturbed_log_rank",
    "fixed_window_npr",
    "regenerated_window_npr",
    "numeric_exact_match",
    "passed",
]

WINDOW_EXPORT_COLUMNS = [
    "logical_shard",
    "gpu_index",
    "system_label",
    "code_unit_sha256",
    "code_unit_relative_path",
    "code_unit_types",
    "unit_groups",
    "space_by_tokens_total",
    "window_index",
    "window_space_by_start",
    "window_space_by_end",
    "window_space_by_token_count",
    "window_marginal_space_by_token_count",
    "window_aggregation_weight_space_by_tokens",
    "overlaps_previous_window",
    "raw_char_start",
    "raw_char_end",
    "raw_char_count",
    "raw_utf8_byte_count",
    "window_text_sha256",
    "window_seed",
    "perturbation_count",
    "perturbations_ordered_sha256",
    "original_llm_token_count",
    "perturbed_llm_token_count_min",
    "perturbed_llm_token_count_mean",
    "perturbed_llm_token_count_max",
    "reported_model_context_limit",
    "original_llm_tokens_exceed_reported_context",
    "original_log_rank",
    "mean_perturbed_log_rank",
    "window_npr",
    "window_npr_valid",
    "window_npr_invalid_reason",
    "scoring_error_type",
    "scoring_error_message",
    "expected_perturbations",
    "valid_perturbation_scores",
    "scoring_seconds",
    "a09_config_fingerprint",
    "a02_config_fingerprint",
    "created_utc",
]

UNIQUE_EXPORT_COLUMNS = [
    "logical_shard",
    "gpu_index",
    "system_label",
    "code_unit_sha256",
    "code_unit_relative_path",
    "code_unit_types",
    "unit_groups",
    "space_by_tokens_total",
    "n_expected_windows",
    "n_attempted_windows",
    "n_valid_npr_windows",
    "n_invalid_npr_windows",
    "space_by_tokens_scored",
    "npr_coverage_ratio",
    "original_llm_tokens_all_windows",
    "original_llm_tokens_valid_windows",
    "code_unit_npr_space_by_token_weighted",
    "code_unit_original_log_rank_weighted",
    "code_unit_mean_perturbed_log_rank_weighted",
    "code_unit_npr_pooled_components",
    "partial_code_unit_score",
    "scoring_seconds",
    "status",
    "a09_config_fingerprint",
    "a02_config_fingerprint",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ordered_text_digest(texts: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for text in texts:
        raw = text.encode("utf-8")
        digest.update(len(raw).to_bytes(8, "big", signed=False))
        digest.update(raw)
    return digest.hexdigest()


def atomic_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    os.replace(tmp, path)


def atomic_csv(rows: Iterable[dict[str, Any]], path: Path, fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})
    os.replace(tmp, path)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def load_a02_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("run_x_a02_score_snapshot_npr", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import A02 module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    note: str = "",
) -> None:
    checks.append(
        {
            "check_name": name,
            "passed": bool(passed),
            "observed": observed,
            "expected": expected,
            "note": note,
        }
    )


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def nullable_exact_float(left: Any, right: Any) -> bool:
    try:
        left_value = float(left)
        right_value = float(right)
    except (TypeError, ValueError):
        return left is None and right is None
    if not math.isfinite(left_value) or not math.isfinite(right_value):
        return (not math.isfinite(left_value)) and (not math.isfinite(right_value))
    return left_value == right_value


def open_database(path: Path, overwrite: bool) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and path.exists():
        path.unlink()
    connection = sqlite3.connect(path, timeout=120)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA temp_store=MEMORY")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS window_scores (
            logical_shard INTEGER NOT NULL,
            gpu_index INTEGER NOT NULL,
            system_label TEXT NOT NULL,
            code_unit_sha256 TEXT NOT NULL,
            code_unit_relative_path TEXT NOT NULL,
            code_unit_types TEXT NOT NULL,
            unit_groups TEXT NOT NULL,
            space_by_tokens_total INTEGER NOT NULL,
            window_index INTEGER NOT NULL,
            window_space_by_start INTEGER NOT NULL,
            window_space_by_end INTEGER NOT NULL,
            window_space_by_token_count INTEGER NOT NULL,
            window_marginal_space_by_token_count INTEGER NOT NULL,
            window_aggregation_weight_space_by_tokens INTEGER NOT NULL DEFAULT 0,
            overlaps_previous_window INTEGER NOT NULL,
            raw_char_start INTEGER NOT NULL,
            raw_char_end INTEGER NOT NULL,
            raw_char_count INTEGER NOT NULL,
            raw_utf8_byte_count INTEGER NOT NULL,
            window_text_sha256 TEXT NOT NULL,
            window_seed INTEGER NOT NULL,
            perturbation_count INTEGER NOT NULL,
            perturbations_ordered_sha256 TEXT NOT NULL,
            original_llm_token_count INTEGER,
            perturbed_llm_token_count_min INTEGER,
            perturbed_llm_token_count_mean REAL,
            perturbed_llm_token_count_max INTEGER,
            reported_model_context_limit INTEGER,
            original_llm_tokens_exceed_reported_context INTEGER NOT NULL,
            original_log_rank REAL,
            mean_perturbed_log_rank REAL,
            window_npr REAL,
            window_npr_valid INTEGER NOT NULL,
            window_npr_invalid_reason TEXT,
            scoring_error_type TEXT,
            scoring_error_message TEXT,
            expected_perturbations INTEGER NOT NULL,
            valid_perturbation_scores INTEGER NOT NULL,
            scoring_seconds REAL NOT NULL,
            a09_config_fingerprint TEXT NOT NULL,
            a02_config_fingerprint TEXT NOT NULL,
            created_utc TEXT NOT NULL,
            PRIMARY KEY (code_unit_sha256, window_index)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_window_scores_shard ON window_scores(logical_shard)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_window_scores_valid ON window_scores(window_npr_valid)"
    )
    connection.commit()
    return connection


def load_completed_keys(connection: sqlite3.Connection) -> set[tuple[str, int]]:
    return {
        (str(row[0]), int(row[1]))
        for row in connection.execute("SELECT code_unit_sha256, window_index FROM window_scores")
    }


def insert_window(connection: sqlite3.Connection, row: dict[str, Any]) -> None:
    columns = WINDOW_EXPORT_COLUMNS
    placeholders = ",".join("?" for _ in columns)
    connection.execute(
        f"INSERT OR REPLACE INTO window_scores ({','.join(columns)}) VALUES ({placeholders})",
        [row.get(column) for column in columns],
    )
    connection.commit()


def read_lpt_plan(path: Path, gpu_index: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "logical_shard",
            "gpu_index",
            "fun_unique_units",
            "fun_windows",
            "fun_perturbations",
            "assignment_policy",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"A10 LPT plan missing columns: {sorted(missing)}")
        for raw in reader:
            if int(raw["gpu_index"]) != gpu_index:
                continue
            if str(raw["assignment_policy"]) != ASSIGNMENT_POLICY:
                raise ValueError(f"Unexpected assignment policy: {raw['assignment_policy']}")
            rows.append(
                {
                    "logical_shard": int(raw["logical_shard"]),
                    "gpu_index": int(raw["gpu_index"]),
                    "fun_unique_units": int(raw["fun_unique_units"]),
                    "fun_windows": int(raw["fun_windows"]),
                    "fun_perturbations": int(raw["fun_perturbations"]),
                    "assignment_policy": str(raw["assignment_policy"]),
                }
            )
    rows.sort(key=lambda row: row["logical_shard"])
    return rows


def read_fun_unit_plan(path: Path, assigned_shards: set[int]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "code_unit_sha256",
            "code_unit_relative_path",
            "space_by_token_count",
            "expected_windows",
            "code_unit_types",
            "unit_groups",
            "logical_shard",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"A09 unique unit plan missing columns: {sorted(missing)}")
        for row in reader:
            shard_id = int(row["logical_shard"])
            if shard_id not in assigned_shards:
                continue
            groups = [value for value in str(row["unit_groups"]).split(",") if value]
            if CATEGORY not in groups:
                continue
            sha = str(row["code_unit_sha256"])
            result[sha] = {
                "code_unit_sha256": sha,
                "code_unit_relative_path": str(row["code_unit_relative_path"]),
                "space_by_tokens_total": int(row["space_by_token_count"]),
                "n_expected_windows": int(row["expected_windows"]),
                "code_unit_types": str(row["code_unit_types"]),
                "unit_groups": str(row["unit_groups"]),
                "logical_shard": shard_id,
            }
    return result


def shard_paths(a09_root: Path, shard_id: int) -> tuple[Path, Path]:
    data_path = a09_root / "shards" / f"shard-{shard_id:03d}-of-096.jsonl.gz"
    summary_path = a09_root / "shards" / f"shard-{shard_id:03d}-of-096.summary.json"
    return data_path, summary_path


def validate_assigned_shards(
    a09_root: Path,
    plan_rows: list[dict[str, Any]],
    a09_config_fingerprint: str,
) -> list[dict[str, Any]]:
    audit_rows: list[dict[str, Any]] = []
    for plan in plan_rows:
        shard_id = int(plan["logical_shard"])
        data_path, summary_path = shard_paths(a09_root, shard_id)
        errors: list[str] = []
        if not data_path.is_file():
            errors.append("missing data shard")
        if not summary_path.is_file():
            errors.append("missing summary shard")
        summary: dict[str, Any] = {}
        if not errors:
            summary = load_json(summary_path)
            if summary.get("status") != "PASS":
                errors.append("A09 shard summary status is not PASS")
            if str(summary.get("config_fingerprint")) != a09_config_fingerprint:
                errors.append("A09 config fingerprint mismatch")
            if int(summary.get("logical_shard", -1)) != shard_id:
                errors.append("logical shard mismatch")
            if int(summary.get("windows", -1)) < int(plan["fun_windows"]):
                errors.append("total shard windows smaller than planned FUN windows")
            if data_path.stat().st_size != int(summary.get("gzip_bytes", -1)):
                errors.append("gzip byte count mismatch")
            observed_sha = sha256_file(data_path)
            if observed_sha != str(summary.get("gzip_sha256")):
                errors.append("gzip SHA-256 mismatch")
        audit_rows.append(
            {
                "logical_shard": shard_id,
                "fun_windows": int(plan["fun_windows"]),
                "data_path": str(data_path),
                "summary_path": str(summary_path),
                "errors": len(errors),
                "error_messages": "; ".join(errors),
                "status": "PASS" if not errors else "FAIL",
            }
        )
    return audit_rows


def iter_fun_records(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            groups = record.get("unit_groups")
            if isinstance(groups, list) and CATEGORY in [str(value) for value in groups]:
                yield record


def score_prepared_window(
    record: dict[str, Any],
    a02: Any,
    config: Any,
    runtime: Any,
) -> dict[str, Any]:
    seed = int(record["window_seed"])
    a02.set_all_seeds(seed, runtime.torch)
    started = time.perf_counter()
    tokenizer = runtime.model_config["base_tokenizer"]
    original_text = str(record["original_text"])
    perturbations_raw = record.get("perturbations")
    if not isinstance(perturbations_raw, list):
        raise ValueError("A09 record perturbations is not a list")
    perturbations = [str(value) for value in perturbations_raw]

    original_llm_tokens: int | None = None
    perturbed_lengths: list[int] = []
    try:
        original_llm_tokens = a02.tokenizer_input_length(tokenizer, original_text)
        original_log_rank = runtime.get_rank(original_text, runtime.args, runtime.model_config, log=True)
        perturbed_lengths = a02.tokenizer_lengths(tokenizer, perturbations)
        perturbed_ranks = runtime.get_ranks(perturbations, runtime.args, runtime.model_config, log=True)
        valid_ranks = [float(value) for value in perturbed_ranks if math.isfinite(float(value))]
        mean_perturbed = float(np.mean(valid_ranks)) if valid_ranks else float("nan")
        npr = mean_perturbed / float(original_log_rank) if float(original_log_rank) else float("nan")
        return {
            "original_llm_token_count": original_llm_tokens,
            "perturbed_llm_token_count_min": min(perturbed_lengths) if perturbed_lengths else None,
            "perturbed_llm_token_count_mean": float(np.mean(perturbed_lengths)) if perturbed_lengths else None,
            "perturbed_llm_token_count_max": max(perturbed_lengths) if perturbed_lengths else None,
            "original_log_rank": float(original_log_rank),
            "mean_perturbed_log_rank": mean_perturbed,
            "window_npr": float(npr),
            "expected_perturbations": int(config.perturbations_per_window),
            "valid_perturbation_scores": int(len(valid_ranks)),
            "scoring_error_type": None,
            "scoring_error_message": None,
            "scoring_seconds": float(time.perf_counter() - started),
        }
    except Exception as error:
        if runtime.torch.cuda.is_available() and "out of memory" in str(error).lower():
            runtime.torch.cuda.empty_cache()
        return {
            "original_llm_token_count": original_llm_tokens,
            "perturbed_llm_token_count_min": min(perturbed_lengths) if perturbed_lengths else None,
            "perturbed_llm_token_count_mean": float(np.mean(perturbed_lengths)) if perturbed_lengths else None,
            "perturbed_llm_token_count_max": max(perturbed_lengths) if perturbed_lengths else None,
            "original_log_rank": None,
            "mean_perturbed_log_rank": None,
            "window_npr": None,
            "expected_perturbations": int(config.perturbations_per_window),
            "valid_perturbation_scores": 0,
            "scoring_error_type": type(error).__name__,
            "scoring_error_message": str(error)[:4000],
            "scoring_seconds": float(time.perf_counter() - started),
        }


def make_window_row(
    record: dict[str, Any],
    scored: dict[str, Any],
    a02: Any,
    runtime: Any,
    gpu_index: int,
    system_label: str,
    a09_config_fingerprint: str,
    a02_config_fingerprint: str,
) -> dict[str, Any]:
    valid, reason = a02.classify_window_validity(scored)
    original_llm_count = scored.get("original_llm_token_count")
    reported_context = runtime.reported_model_context_limit
    exceeds = (
        bool(int(original_llm_count) > int(reported_context))
        if original_llm_count is not None and reported_context is not None
        else False
    )
    original_text = str(record["original_text"])
    groups = record.get("unit_groups") or []
    types = record.get("code_unit_types") or []
    return {
        "logical_shard": int(record["logical_shard"]),
        "gpu_index": int(gpu_index),
        "system_label": system_label,
        "code_unit_sha256": str(record["code_unit_sha256"]),
        "code_unit_relative_path": str(record["code_unit_relative_path"]),
        "code_unit_types": ",".join(str(value) for value in types),
        "unit_groups": ",".join(str(value) for value in groups),
        "space_by_tokens_total": int(record["space_by_tokens_total"]),
        "window_index": int(record["window_index"]),
        "window_space_by_start": int(record["window_space_by_start"]),
        "window_space_by_end": int(record["window_space_by_end"]),
        "window_space_by_token_count": int(record["window_space_by_token_count"]),
        "window_marginal_space_by_token_count": int(record["window_marginal_space_by_token_count"]),
        "window_aggregation_weight_space_by_tokens": 0,
        "overlaps_previous_window": int(parse_bool(record.get("overlaps_previous_window"))),
        "raw_char_start": int(record["raw_char_start"]),
        "raw_char_end": int(record["raw_char_end"]),
        "raw_char_count": len(original_text),
        "raw_utf8_byte_count": len(original_text.encode("utf-8")),
        "window_text_sha256": str(record["window_text_sha256"]),
        "window_seed": int(record["window_seed"]),
        "perturbation_count": int(record["perturbation_count"]),
        "perturbations_ordered_sha256": str(record["perturbations_ordered_sha256"]),
        "original_llm_token_count": scored.get("original_llm_token_count"),
        "perturbed_llm_token_count_min": scored.get("perturbed_llm_token_count_min"),
        "perturbed_llm_token_count_mean": scored.get("perturbed_llm_token_count_mean"),
        "perturbed_llm_token_count_max": scored.get("perturbed_llm_token_count_max"),
        "reported_model_context_limit": reported_context,
        "original_llm_tokens_exceed_reported_context": int(exceeds),
        "original_log_rank": a02.sanitize_float(scored.get("original_log_rank")),
        "mean_perturbed_log_rank": a02.sanitize_float(scored.get("mean_perturbed_log_rank")),
        "window_npr": a02.sanitize_float(scored.get("window_npr")),
        "window_npr_valid": int(bool(valid)),
        "window_npr_invalid_reason": reason,
        "scoring_error_type": scored.get("scoring_error_type"),
        "scoring_error_message": scored.get("scoring_error_message"),
        "expected_perturbations": int(scored.get("expected_perturbations", PERTURBATIONS_PER_WINDOW)),
        "valid_perturbation_scores": int(scored.get("valid_perturbation_scores", 0)),
        "scoring_seconds": float(scored.get("scoring_seconds", 0.0)),
        "a09_config_fingerprint": a09_config_fingerprint,
        "a02_config_fingerprint": a02_config_fingerprint,
        "created_utc": utc_now(),
    }


def reference_check(
    record: dict[str, Any],
    fixed_scored: dict[str, Any],
    a02: Any,
    config: Any,
    runtime: Any,
) -> dict[str, Any]:
    seed = int(record["window_seed"])
    original_text = str(record["original_text"])
    prepared = [str(value) for value in record["perturbations"]]
    a02.set_all_seeds(seed, runtime.torch)
    regenerated = runtime.detector_main.perturb_texts(
        [original_text for _ in range(config.perturbations_per_window)],
        runtime.args,
        runtime.model_config,
    )
    prepared_digest = ordered_text_digest(prepared)
    regenerated_digest = ordered_text_digest(regenerated)
    perturbation_match = prepared == regenerated and prepared_digest == regenerated_digest

    regenerated_scored = a02.score_window_real(original_text, seed, config, runtime)
    numeric_match = all(
        nullable_exact_float(fixed_scored.get(key), regenerated_scored.get(key))
        for key in ("original_log_rank", "mean_perturbed_log_rank", "window_npr")
    )
    return {
        "logical_shard": int(record["logical_shard"]),
        "code_unit_sha256": str(record["code_unit_sha256"]),
        "window_index": int(record["window_index"]),
        "prepared_perturbation_digest": prepared_digest,
        "regenerated_perturbation_digest": regenerated_digest,
        "perturbations_exact_match": bool(perturbation_match),
        "fixed_original_log_rank": fixed_scored.get("original_log_rank"),
        "regenerated_original_log_rank": regenerated_scored.get("original_log_rank"),
        "fixed_mean_perturbed_log_rank": fixed_scored.get("mean_perturbed_log_rank"),
        "regenerated_mean_perturbed_log_rank": regenerated_scored.get("mean_perturbed_log_rank"),
        "fixed_window_npr": fixed_scored.get("window_npr"),
        "regenerated_window_npr": regenerated_scored.get("window_npr"),
        "numeric_exact_match": bool(numeric_match),
        "passed": bool(perturbation_match and numeric_match),
    }


def sqlite_rows(connection: sqlite3.Connection) -> Iterator[dict[str, Any]]:
    cursor = connection.execute(
        f"SELECT {','.join(WINDOW_EXPORT_COLUMNS)} FROM window_scores "
        "ORDER BY code_unit_sha256, window_index"
    )
    for values in cursor:
        yield dict(zip(WINDOW_EXPORT_COLUMNS, values))


def export_window_csv(connection: sqlite3.Connection, path: Path) -> int:
    count = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=WINDOW_EXPORT_COLUMNS)
        writer.writeheader()
        for row in sqlite_rows(connection):
            writer.writerow(row)
            count += 1
    os.replace(tmp, path)
    return count


def aggregate_and_export_units(
    connection: sqlite3.Connection,
    unit_plan: dict[str, dict[str, Any]],
    a02: Any,
    gpu_index: int,
    system_label: str,
    a09_config_fingerprint: str,
    a02_config_fingerprint: str,
    output_path: Path,
    failure_path: Path,
    skip_units_missing_from_plan: bool = False,
) -> tuple[int, int, int, list[dict[str, Any]]]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    failures: list[dict[str, Any]] = []
    units_written = 0
    partial_units = 0
    invalid_windows_total = 0

    query_columns = [
        "logical_shard",
        "code_unit_sha256",
        "code_unit_relative_path",
        "code_unit_types",
        "unit_groups",
        "space_by_tokens_total",
        "window_index",
        "window_space_by_start",
        "window_space_by_end",
        "window_npr_valid",
        "original_llm_token_count",
        "original_log_rank",
        "mean_perturbed_log_rank",
        "window_npr",
        "scoring_seconds",
    ]
    cursor = connection.execute(
        f"SELECT {','.join(query_columns)} FROM window_scores ORDER BY code_unit_sha256, window_index"
    )

    with tmp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=UNIQUE_EXPORT_COLUMNS)
        writer.writeheader()
        current_sha: str | None = None
        current_rows: list[dict[str, Any]] = []

        def flush_unit() -> None:
            nonlocal units_written, partial_units, invalid_windows_total, current_rows, current_sha
            if current_sha is None or not current_rows:
                return
            meta = unit_plan.get(current_sha)
            if meta is None:
                # Limited smoke runs intentionally score only the first few windows
                # from each selected shard. Units that are incomplete by design are
                # excluded from the temporary aggregate plan and must be skipped
                # here rather than reported as production integrity failures.
                if skip_units_missing_from_plan:
                    return
                failures.append(
                    {
                        "logical_shard": current_rows[0]["logical_shard"],
                        "code_unit_sha256": current_sha,
                        "window_index": "",
                        "stage": "aggregate_unit",
                        "error_type": "MissingUnitPlan",
                        "error_message": "Scored FUN unit is missing from assigned A09 unit plan.",
                    }
                )
                return
            expected_windows = int(meta["n_expected_windows"])
            attempted = len(current_rows)
            invalid = sum(not bool(row["window_npr_valid"]) for row in current_rows)
            invalid_windows_total += invalid
            if attempted != expected_windows:
                failures.append(
                    {
                        "logical_shard": meta["logical_shard"],
                        "code_unit_sha256": current_sha,
                        "window_index": "",
                        "stage": "aggregate_unit",
                        "error_type": "WindowCoverageMismatch",
                        "error_message": f"attempted={attempted}; expected={expected_windows}",
                    }
                )
                return
            a02_rows = [
                {
                    "window_space_by_start": int(row["window_space_by_start"]),
                    "window_space_by_end": int(row["window_space_by_end"]),
                    "window_npr_valid": bool(row["window_npr_valid"]),
                    "window_aggregation_weight_space_by_tokens": 0,
                    "original_log_rank": row["original_log_rank"],
                    "mean_perturbed_log_rank": row["mean_perturbed_log_rank"],
                    "window_npr": row["window_npr"],
                }
                for row in current_rows
            ]
            try:
                aggregate = a02.aggregate_code_unit(a02_rows, int(meta["space_by_tokens_total"]))
            except Exception as error:
                failures.append(
                    {
                        "logical_shard": meta["logical_shard"],
                        "code_unit_sha256": current_sha,
                        "window_index": "",
                        "stage": "aggregate_unit",
                        "error_type": type(error).__name__,
                        "error_message": str(error)[:4000],
                    }
                )
                return

            valid_rows = [row for row in current_rows if bool(row["window_npr_valid"])]
            partial = int(invalid > 0)
            partial_units += partial
            out = {
                "logical_shard": int(meta["logical_shard"]),
                "gpu_index": int(gpu_index),
                "system_label": system_label,
                "code_unit_sha256": current_sha,
                "code_unit_relative_path": str(meta["code_unit_relative_path"]),
                "code_unit_types": str(meta["code_unit_types"]),
                "unit_groups": str(meta["unit_groups"]),
                "space_by_tokens_total": int(meta["space_by_tokens_total"]),
                "n_expected_windows": expected_windows,
                "n_attempted_windows": attempted,
                "n_valid_npr_windows": len(valid_rows),
                "n_invalid_npr_windows": invalid,
                "space_by_tokens_scored": int(aggregate["space_by_tokens_scored"]),
                "npr_coverage_ratio": float(aggregate["npr_coverage_ratio"]),
                "original_llm_tokens_all_windows": sum(int(row["original_llm_token_count"] or 0) for row in current_rows),
                "original_llm_tokens_valid_windows": sum(int(row["original_llm_token_count"] or 0) for row in valid_rows),
                "code_unit_npr_space_by_token_weighted": float(aggregate["code_unit_npr_space_by_token_weighted"]),
                "code_unit_original_log_rank_weighted": float(aggregate["code_unit_original_log_rank_weighted"]),
                "code_unit_mean_perturbed_log_rank_weighted": float(aggregate["code_unit_mean_perturbed_log_rank_weighted"]),
                "code_unit_npr_pooled_components": float(aggregate["code_unit_npr_pooled_components"]),
                "partial_code_unit_score": partial,
                "scoring_seconds": sum(float(row["scoring_seconds"] or 0.0) for row in current_rows),
                "status": "partial" if partial else "scored",
                "a09_config_fingerprint": a09_config_fingerprint,
                "a02_config_fingerprint": a02_config_fingerprint,
            }
            writer.writerow(out)
            units_written += 1

        for values in cursor:
            row = dict(zip(query_columns, values))
            sha = str(row["code_unit_sha256"])
            if current_sha is not None and sha != current_sha:
                flush_unit()
                current_rows = []
            current_sha = sha
            current_rows.append(row)
        flush_unit()
    os.replace(tmp, output_path)
    atomic_csv(failures, failure_path, FAILURE_COLUMNS)
    return units_written, partial_units, invalid_windows_total, failures


def count_db(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT
            COUNT(*),
            SUM(CASE WHEN window_npr_valid = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN scoring_error_type IS NOT NULL THEN 1 ELSE 0 END),
            COUNT(DISTINCT code_unit_sha256),
            SUM(CASE WHEN original_llm_tokens_exceed_reported_context = 1 THEN 1 ELSE 0 END)
        FROM window_scores
        """
    ).fetchone()
    return {
        "windows": int(row[0] or 0),
        "invalid_windows": int(row[1] or 0),
        "scoring_errors": int(row[2] or 0),
        "unique_units": int(row[3] or 0),
        "context_exceed_windows": int(row[4] or 0),
    }


def write_progress(
    path: Path,
    gpu_index: int,
    system_label: str,
    expected_windows: int,
    completed_windows: int,
    newly_scored: int,
    reused: int,
    started: float,
    last_shard: int | None,
    last_code_sha: str | None,
    last_window_index: int | None,
) -> None:
    elapsed = max(0.000001, time.perf_counter() - started)
    rate = newly_scored / elapsed if newly_scored else 0.0
    remaining = max(0, expected_windows - completed_windows)
    eta_seconds = remaining / rate if rate > 0 else None
    atomic_json(
        {
            "script_version": SCRIPT_VERSION,
            "category": CATEGORY,
            "gpu_index": gpu_index,
            "system_label": system_label,
            "expected_selected_windows": expected_windows,
            "completed_windows": completed_windows,
            "newly_scored_windows_this_invocation": newly_scored,
            "resume_reused_windows": reused,
            "elapsed_seconds": elapsed,
            "new_windows_per_second": rate,
            "eta_seconds_at_current_rate": eta_seconds,
            "last_logical_shard": last_shard,
            "last_code_unit_sha256": last_code_sha,
            "last_window_index": last_window_index,
            "updated_utc": utc_now(),
        },
        path,
    )


def run_self_test() -> None:
    sample = ["a", "b c", ""]
    assert ordered_text_digest(sample) == ordered_text_digest(sample)
    assert parse_bool(True)
    assert parse_bool("1")
    assert not parse_bool("false")
    assert nullable_exact_float(1.0, 1.0)
    assert not nullable_exact_float(1.0, 1.0000000001)

    import tempfile

    with tempfile.TemporaryDirectory(prefix="a11-self-test-") as tmp_text:
        db_path = Path(tmp_text) / "scores.sqlite3"
        connection = open_database(db_path, overwrite=True)
        row = {column: None for column in WINDOW_EXPORT_COLUMNS}
        row.update(
            {
                "logical_shard": 0,
                "gpu_index": 0,
                "system_label": "mock",
                "code_unit_sha256": "a" * 64,
                "code_unit_relative_path": "code_units/mock.txt",
                "code_unit_types": "function_body",
                "unit_groups": "FUN",
                "space_by_tokens_total": 2,
                "window_index": 0,
                "window_space_by_start": 0,
                "window_space_by_end": 2,
                "window_space_by_token_count": 2,
                "window_marginal_space_by_token_count": 2,
                "window_aggregation_weight_space_by_tokens": 0,
                "overlaps_previous_window": 0,
                "raw_char_start": 0,
                "raw_char_end": 3,
                "raw_char_count": 3,
                "raw_utf8_byte_count": 3,
                "window_text_sha256": "b" * 64,
                "window_seed": 1,
                "perturbation_count": 50,
                "perturbations_ordered_sha256": "c" * 64,
                "original_llm_tokens_exceed_reported_context": 0,
                "window_npr_valid": 1,
                "expected_perturbations": 50,
                "valid_perturbation_scores": 50,
                "scoring_seconds": 0.1,
                "a09_config_fingerprint": "d" * 64,
                "a02_config_fingerprint": "e" * 64,
                "created_utc": utc_now(),
            }
        )
        insert_window(connection, row)
        assert count_db(connection)["windows"] == 1
        assert ("a" * 64, 0) in load_completed_keys(connection)

        # Regression test for v1 smoke aggregation: a limited smoke sample may
        # contain a complete unit plus another unit with only its first window.
        # The incomplete-by-design unit is absent from the temporary aggregate
        # plan and must be skipped without creating a MissingUnitPlan failure.
        second = dict(row)
        second["code_unit_sha256"] = "f" * 64
        second["window_text_sha256"] = "1" * 64
        insert_window(connection, second)

        class MockA02:
            @staticmethod
            def aggregate_code_unit(rows, space_by_tokens_total):
                assert len(rows) == 1
                return {
                    "space_by_tokens_scored": int(space_by_tokens_total),
                    "npr_coverage_ratio": 1.0,
                    "code_unit_npr_space_by_token_weighted": 1.0,
                    "code_unit_original_log_rank_weighted": 2.0,
                    "code_unit_mean_perturbed_log_rank_weighted": 2.0,
                    "code_unit_npr_pooled_components": 1.0,
                }

        aggregate_plan = {
            "a" * 64: {
                "logical_shard": 0,
                "code_unit_relative_path": "code_units/mock.txt",
                "code_unit_types": "function_body",
                "unit_groups": "FUN",
                "space_by_tokens_total": 2,
                "n_expected_windows": 1,
            }
        }
        aggregate_csv = Path(tmp_text) / "aggregate.csv"
        aggregate_failures_csv = Path(tmp_text) / "aggregate_failures.csv"
        written, partial, invalid, aggregate_failures = aggregate_and_export_units(
            connection,
            aggregate_plan,
            MockA02(),
            0,
            "mock",
            "d" * 64,
            "e" * 64,
            aggregate_csv,
            aggregate_failures_csv,
            skip_units_missing_from_plan=True,
        )
        assert written == 1
        assert partial == 0
        assert invalid == 0
        assert aggregate_failures == []
        connection.close()
    print("score_snapshot_npr_fun_shards self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score A09 FUN perturbation shards with fixed inputs.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--a09-root", type=Path, default=Path("output/snapshot_npr/run-x-a09"))
    parser.add_argument("--a10-root", type=Path, default=Path("output/snapshot_npr/run-x-a10"))
    parser.add_argument("--a02-script", type=Path, default=Path("code-detection/score_snapshot_npr.py"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gpu-index", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--system-label", required=True)
    parser.add_argument("--scoring-model", default=SCORING_MODEL)
    parser.add_argument("--model-cache-dir", type=Path, default=Path("~/.cache/huggingface/hub").expanduser())
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--detector-output-name", default="run_x_a11_fun_npr")
    parser.add_argument("--detector-log-level", default="WARNING")
    parser.add_argument("--quiet-internal-progress", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--progress-every-windows", type=int, default=100)
    parser.add_argument("--reference-check-windows", type=int, default=0)
    parser.add_argument("--max-shards", type=int, default=None)
    parser.add_argument("--max-windows-per-shard", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--retry-error-windows", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-all-valid", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--allow-non-a6000", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--self-test-only", action="store_true")
    return parser.parse_args()


def resolve_under_project(project_root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def main() -> int:
    args = parse_args()
    if args.self_test or args.self_test_only:
        run_self_test()
    if args.self_test_only:
        return 0

    project_root = args.project_root.resolve()
    args.a09_root = resolve_under_project(project_root, args.a09_root)
    args.a10_root = resolve_under_project(project_root, args.a10_root)
    args.a02_script = resolve_under_project(project_root, args.a02_script)
    args.output_dir = resolve_under_project(project_root, args.output_dir)
    args.model_cache_dir = args.model_cache_dir.expanduser().resolve()

    started_utc = utc_now()
    invocation_started = time.perf_counter()
    checks: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    runtime: Any | None = None

    if not args.a02_script.is_file():
        raise FileNotFoundError(f"Missing A02 script: {args.a02_script}")
    a02_sha = sha256_file(args.a02_script)
    add_check(checks, "a02_script_sha256", a02_sha == EXPECTED_A02_SHA256, a02_sha, EXPECTED_A02_SHA256)
    if a02_sha != EXPECTED_A02_SHA256:
        raise RuntimeError("A02 script SHA-256 mismatch; refusing production scoring.")
    a02 = load_a02_module(args.a02_script)

    a09_summary_path = args.a09_root / "plan" / "summary.json"
    a09_unit_plan_path = args.a09_root / "plan" / "unique_primary_units.csv"
    a10_summary_path = args.a10_root / "summary.json"
    a10_plan_path = args.a10_root / "fun_gpu_lpt_plan.csv"
    for path in (a09_summary_path, a09_unit_plan_path, a10_summary_path, a10_plan_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing required input: {path}")

    a09_summary = load_json(a09_summary_path)
    a10_summary = load_json(a10_summary_path)
    a09_config_fingerprint = str(a09_summary.get("config_fingerprint"))

    add_check(checks, "a09_plan_status", a09_summary.get("status") == "PASS", a09_summary.get("status"), "PASS")
    add_check(checks, "a10_status", a10_summary.get("status") == "PASS", a10_summary.get("status"), "PASS")
    add_check(checks, "a10_assignment_policy", a10_summary.get("recommended_fun_gpu_assignment") == ASSIGNMENT_POLICY, a10_summary.get("recommended_fun_gpu_assignment"), ASSIGNMENT_POLICY)
    add_check(checks, "a09_config_fingerprint", a09_config_fingerprint == EXPECTED_A09_CONFIG_FINGERPRINT, a09_config_fingerprint, EXPECTED_A09_CONFIG_FINGERPRINT)
    add_check(checks, "a09_input_manifest_sha256", str(a09_summary.get("input_manifest_sha256")) == EXPECTED_A05_MANIFEST_SHA256, a09_summary.get("input_manifest_sha256"), EXPECTED_A05_MANIFEST_SHA256)
    add_check(checks, "a10_fun_windows", int(a10_summary.get("group_workload", {}).get("FUN", {}).get("windows", -1)) == EXPECTED_FUN_WINDOWS, a10_summary.get("group_workload", {}).get("FUN", {}).get("windows"), EXPECTED_FUN_WINDOWS)
    add_check(checks, "a10_fun_perturbations", int(a10_summary.get("group_workload", {}).get("FUN", {}).get("perturbations", -1)) == EXPECTED_FUN_PERTURBATIONS, a10_summary.get("group_workload", {}).get("FUN", {}).get("perturbations"), EXPECTED_FUN_PERTURBATIONS)
    add_check(checks, "a10_fun_unique_memberships", int(a10_summary.get("group_workload", {}).get("FUN", {}).get("unique_unit_memberships", -1)) == EXPECTED_FUN_UNIQUE_MEMBERSHIPS, a10_summary.get("group_workload", {}).get("FUN", {}).get("unique_unit_memberships"), EXPECTED_FUN_UNIQUE_MEMBERSHIPS)
    add_check(checks, "a10_lpt_gpu_loads", list(a10_summary.get("fun_gpu_lpt_window_loads", [])) == EXPECTED_GPU_WINDOW_LOADS, a10_summary.get("fun_gpu_lpt_window_loads"), EXPECTED_GPU_WINDOW_LOADS)

    if any(not bool(row["passed"]) for row in checks):
        args.output_dir.mkdir(parents=True, exist_ok=True)
        atomic_csv(checks, args.output_dir / "checks.csv", CHECK_COLUMNS)
        raise RuntimeError("Pre-scoring provenance checks failed.")

    lpt_plan = read_lpt_plan(a10_plan_path, args.gpu_index)
    if not lpt_plan:
        raise RuntimeError(f"No A10 LPT shards assigned to GPU {args.gpu_index}")
    if args.max_shards is not None:
        if args.max_shards < 1:
            raise ValueError("max-shards must be positive")
        lpt_plan = lpt_plan[: args.max_shards]
    assigned_shards = {int(row["logical_shard"]) for row in lpt_plan}
    full_expected_windows = sum(int(row["fun_windows"]) for row in lpt_plan)
    full_expected_units = sum(int(row["fun_unique_units"]) for row in lpt_plan)

    shard_audit = validate_assigned_shards(args.a09_root, lpt_plan, a09_config_fingerprint)
    atomic_csv(
        shard_audit,
        args.output_dir / "assigned_shard_audit.csv",
        ["logical_shard", "fun_windows", "data_path", "summary_path", "errors", "error_messages", "status"],
    )
    shard_failures = [row for row in shard_audit if row["status"] != "PASS"]
    add_check(checks, "assigned_shard_integrity", not shard_failures, len(shard_failures), 0)
    if shard_failures:
        atomic_csv(checks, args.output_dir / "checks.csv", CHECK_COLUMNS)
        raise RuntimeError("Assigned A09 shard integrity validation failed.")

    unit_plan = read_fun_unit_plan(a09_unit_plan_path, assigned_shards)
    add_check(checks, "assigned_fun_unit_plan_count", len(unit_plan) == full_expected_units, len(unit_plan), full_expected_units)
    add_check(checks, "assigned_fun_unit_plan_windows", sum(int(row["n_expected_windows"]) for row in unit_plan.values()) == full_expected_windows, sum(int(row["n_expected_windows"]) for row in unit_plan.values()), full_expected_windows)
    if any(not bool(row["passed"]) for row in checks):
        atomic_csv(checks, args.output_dir / "checks.csv", CHECK_COLUMNS)
        raise RuntimeError("Assigned FUN unit-plan reconciliation failed.")

    config = a02.DetectorConfig(
        scoring_model=args.scoring_model,
        window_size=WINDOW_SIZE,
        perturbations_per_window=PERTURBATIONS_PER_WINDOW,
        perturbation_type=PERTURBATION_TYPE,
        random_seed=RANDOM_SEED,
        pct_words_masked=PCT_WORDS_MASKED,
        span_length=SPAN_LENGTH,
        perturbation_chunk_size=PERTURBATION_CHUNK_SIZE,
        n_perturbation_rounds=N_PERTURBATION_ROUNDS,
    )
    source_hashes = a02.collect_detector_source_hashes(project_root)
    package_versions = a02.collect_package_versions()
    a02_config_payload = config.payload(source_hashes, package_versions)
    a02_config_fingerprint = a02.stable_json_hash(a02_config_payload)
    add_check(checks, "a02_config_fingerprint", a02_config_fingerprint == EXPECTED_A02_CONFIG_FINGERPRINT, a02_config_fingerprint, EXPECTED_A02_CONFIG_FINGERPRINT)
    if a02_config_fingerprint != EXPECTED_A02_CONFIG_FINGERPRINT:
        atomic_csv(checks, args.output_dir / "checks.csv", CHECK_COLUMNS)
        raise RuntimeError("A02 scoring fingerprint mismatch; package/source drift detected.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    db_path = args.output_dir / "window_scores.sqlite3"
    connection = open_database(db_path, overwrite=args.overwrite)
    if args.retry_error_windows:
        connection.execute("DELETE FROM window_scores WHERE scoring_error_type IS NOT NULL")
        connection.commit()

    existing_bad_provenance = connection.execute(
        """
        SELECT COUNT(*) FROM window_scores
        WHERE gpu_index != ?
           OR a09_config_fingerprint != ?
           OR a02_config_fingerprint != ?
        """,
        (args.gpu_index, a09_config_fingerprint, a02_config_fingerprint),
    ).fetchone()[0]
    existing_bad_shards = connection.execute(
        "SELECT DISTINCT logical_shard FROM window_scores"
    ).fetchall()
    existing_bad_shards = [int(row[0]) for row in existing_bad_shards if int(row[0]) not in assigned_shards]
    add_check(checks, "resume_database_provenance", int(existing_bad_provenance) == 0, int(existing_bad_provenance), 0)
    add_check(checks, "resume_database_assigned_shards", not existing_bad_shards, ",".join(map(str, existing_bad_shards)), "none")
    if existing_bad_provenance or existing_bad_shards:
        atomic_csv(checks, args.output_dir / "checks.csv", CHECK_COLUMNS)
        raise RuntimeError("Existing A11 checkpoint database has incompatible provenance or shard assignment.")

    completed_keys = load_completed_keys(connection)
    reused_at_start = len(completed_keys)

    # A02 load_runtime expects these argument attributes.
    runtime_args = argparse.Namespace(
        project_root=project_root,
        device=args.device,
        model_cache_dir=args.model_cache_dir,
        detector_output_name=args.detector_output_name,
        quiet_internal_progress=args.quiet_internal_progress,
        detector_log_level=args.detector_log_level,
    )
    runtime = a02.load_runtime(config, runtime_args)
    gpu_name = str(runtime.gpu_name)
    add_check(checks, "cuda_visible_device_count", int(runtime.torch.cuda.device_count()) == 1, runtime.torch.cuda.device_count(), 1)
    add_check(checks, "gpu_is_rtx_a6000", args.allow_non_a6000 or "RTX A6000" in gpu_name, gpu_name, "NVIDIA RTX A6000")
    model_revision = str(getattr(runtime.model_config["base_model"].config, "_commit_hash", ""))
    add_check(checks, "model_revision", model_revision == EXPECTED_MODEL_REVISION, model_revision, EXPECTED_MODEL_REVISION)
    if any(not bool(row["passed"]) for row in checks):
        atomic_csv(checks, args.output_dir / "checks.csv", CHECK_COLUMNS)
        raise RuntimeError("GPU/model provenance checks failed.")

    selected_expected_windows = full_expected_windows
    limited_run = args.max_shards is not None or args.max_windows_per_shard is not None
    if args.max_windows_per_shard is not None and args.max_windows_per_shard < 1:
        raise ValueError("max-windows-per-shard must be positive")

    newly_scored = 0
    candidate_records_seen = 0
    reference_remaining = args.reference_check_windows
    failure_rows: list[dict[str, Any]] = []
    progress_path = args.output_dir / "progress.json"
    scoring_started = time.perf_counter()
    last_shard: int | None = None
    last_sha: str | None = None
    last_window_index: int | None = None

    for plan_row in lpt_plan:
        shard_id = int(plan_row["logical_shard"])
        data_path, _ = shard_paths(args.a09_root, shard_id)
        per_shard_seen = 0
        for record in iter_fun_records(data_path):
            if args.max_windows_per_shard is not None and per_shard_seen >= args.max_windows_per_shard:
                break
            per_shard_seen += 1
            candidate_records_seen += 1
            record["logical_shard"] = shard_id
            sha = str(record["code_unit_sha256"])
            window_index = int(record["window_index"])
            last_shard, last_sha, last_window_index = shard_id, sha, window_index
            key = (sha, window_index)
            if key in completed_keys:
                continue

            if str(record.get("config_fingerprint")) != a09_config_fingerprint:
                raise RuntimeError(f"A09 record fingerprint mismatch in shard {shard_id:03d}")
            if int(record.get("perturbation_count", -1)) != PERTURBATIONS_PER_WINDOW:
                raise RuntimeError(f"A09 perturbation count mismatch for {sha}/{window_index}")
            prepared = record.get("perturbations")
            if not isinstance(prepared, list) or ordered_text_digest(str(value) for value in prepared) != str(record.get("perturbations_ordered_sha256")):
                raise RuntimeError(f"A09 perturbation digest mismatch for {sha}/{window_index}")

            scored = score_prepared_window(record, a02, config, runtime)
            if reference_remaining > 0:
                check_row = reference_check(record, scored, a02, config, runtime)
                reference_rows.append(check_row)
                reference_remaining -= 1
                if not bool(check_row["passed"]):
                    atomic_csv(reference_rows, args.output_dir / "reference_scoring_checks.csv", REFERENCE_COLUMNS)
                    raise RuntimeError("A11 fixed-perturbation scoring differs from A02 regeneration reference.")

            out = make_window_row(
                record,
                scored,
                a02,
                runtime,
                args.gpu_index,
                args.system_label,
                a09_config_fingerprint,
                a02_config_fingerprint,
            )
            insert_window(connection, out)
            completed_keys.add(key)
            newly_scored += 1
            if out["scoring_error_type"]:
                failure_rows.append(
                    {
                        "logical_shard": shard_id,
                        "code_unit_sha256": sha,
                        "window_index": window_index,
                        "stage": "score_prepared_window",
                        "error_type": out["scoring_error_type"],
                        "error_message": out["scoring_error_message"],
                    }
                )

            if args.progress_every_windows > 0 and newly_scored % args.progress_every_windows == 0:
                expected_for_progress = full_expected_windows if not limited_run else max(candidate_records_seen, len(completed_keys))
                counts = count_db(connection)
                write_progress(
                    progress_path,
                    args.gpu_index,
                    args.system_label,
                    expected_for_progress,
                    counts["windows"],
                    newly_scored,
                    reused_at_start,
                    scoring_started,
                    last_shard,
                    last_sha,
                    last_window_index,
                )
                elapsed = time.perf_counter() - scoring_started
                rate = newly_scored / elapsed if elapsed > 0 else 0.0
                print(
                    f"A11 progress: gpu={args.gpu_index} new={newly_scored} "
                    f"db={counts['windows']} shard={shard_id:03d} "
                    f"rate={rate:.6f} windows/s errors={counts['scoring_errors']}",
                    flush=True,
                )

    if limited_run:
        selected_expected_windows = candidate_records_seen
    else:
        add_check(checks, "streamed_fun_windows_match_plan", candidate_records_seen == full_expected_windows, candidate_records_seen, full_expected_windows)

    counts = count_db(connection)
    add_check(checks, "selected_windows_complete", counts["windows"] == selected_expected_windows, counts["windows"], selected_expected_windows)
    add_check(checks, "scoring_errors_zero", counts["scoring_errors"] == 0, counts["scoring_errors"], 0)
    if args.require_all_valid:
        add_check(checks, "invalid_windows_zero", counts["invalid_windows"] == 0, counts["invalid_windows"], 0)

    if reference_rows:
        atomic_csv(reference_rows, args.output_dir / "reference_scoring_checks.csv", REFERENCE_COLUMNS)
        add_check(checks, "reference_scoring_exact", all(bool(row["passed"]) for row in reference_rows), sum(bool(row["passed"]) for row in reference_rows), len(reference_rows))
    else:
        atomic_csv([], args.output_dir / "reference_scoring_checks.csv", REFERENCE_COLUMNS)

    window_csv_path = args.output_dir / "python_fun_window_npr_scores.csv"
    unique_csv_path = args.output_dir / "python_fun_unique_code_unit_npr_scores.csv"
    failure_csv_path = args.output_dir / "python_fun_npr_failures.csv"
    window_export_rows = export_window_csv(connection, window_csv_path)

    # For a limited smoke run, the full unit plan contains incomplete units. Build
    # a temporary plan containing only units for which every expected window was
    # selected, so aggregation is strict rather than silently partial-by-design.
    aggregate_plan = unit_plan
    if limited_run:
        db_counts_by_unit = {
            str(sha): int(count)
            for sha, count in connection.execute(
                "SELECT code_unit_sha256, COUNT(*) FROM window_scores GROUP BY code_unit_sha256"
            )
        }
        aggregate_plan = {
            sha: meta
            for sha, meta in unit_plan.items()
            if db_counts_by_unit.get(sha, 0) == int(meta["n_expected_windows"])
        }

    units_written, partial_units, invalid_windows_agg, aggregate_failures = aggregate_and_export_units(
        connection,
        aggregate_plan,
        a02,
        args.gpu_index,
        args.system_label,
        a09_config_fingerprint,
        a02_config_fingerprint,
        unique_csv_path,
        failure_csv_path,
        skip_units_missing_from_plan=limited_run,
    )
    failure_rows.extend(aggregate_failures)
    if failure_rows:
        atomic_csv(failure_rows, failure_csv_path, FAILURE_COLUMNS)
    else:
        atomic_csv([], failure_csv_path, FAILURE_COLUMNS)

    add_check(checks, "window_csv_rows_match_database", window_export_rows == counts["windows"], window_export_rows, counts["windows"])
    if not limited_run:
        add_check(checks, "unique_fun_units_complete", units_written == full_expected_units, units_written, full_expected_units)
    add_check(checks, "no_agc_hwc_classification", True, "none", "none", "A11 output schema contains no threshold/classification columns.")

    failed_checks = [row for row in checks if not bool(row["passed"])]
    status = "PASS" if not failed_checks and not failure_rows else "FAIL"
    atomic_csv(checks, args.output_dir / "checks.csv", CHECK_COLUMNS)

    scoring_elapsed = time.perf_counter() - scoring_started
    invocation_elapsed = time.perf_counter() - invocation_started
    new_rate = newly_scored / scoring_elapsed if newly_scored and scoring_elapsed > 0 else 0.0
    peak_allocated = int(runtime.torch.cuda.max_memory_allocated()) if runtime.torch.cuda.is_available() else 0
    peak_reserved = int(runtime.torch.cuda.max_memory_reserved()) if runtime.torch.cuda.is_available() else 0

    summary = {
        "status": status,
        "script_version": SCRIPT_VERSION,
        "category": CATEGORY,
        "assignment_policy": ASSIGNMENT_POLICY,
        "gpu_index": args.gpu_index,
        "system_label": args.system_label,
        "hostname": platform.node(),
        "limited_run": limited_run,
        "assigned_logical_shards": sorted(assigned_shards),
        "assigned_shard_count": len(assigned_shards),
        "full_expected_fun_unique_units": full_expected_units,
        "full_expected_fun_windows": full_expected_windows,
        "selected_expected_windows": selected_expected_windows,
        "database_windows": counts["windows"],
        "database_unique_units": counts["unique_units"],
        "newly_scored_windows_this_invocation": newly_scored,
        "resume_reused_windows_at_start": reused_at_start,
        "retry_error_windows": bool(args.retry_error_windows),
        "invalid_windows": counts["invalid_windows"],
        "scoring_errors": counts["scoring_errors"],
        "windows_exceeding_reported_model_context": counts["context_exceed_windows"],
        "exported_unique_units": units_written,
        "partial_unique_units": partial_units,
        "aggregate_invalid_windows": invalid_windows_agg,
        "failed_checks": len(failed_checks),
        "failure_rows": len(failure_rows),
        "reference_checks": len(reference_rows),
        "reference_failures": sum(not bool(row["passed"]) for row in reference_rows),
        "model_load_seconds": float(runtime.model_load_seconds),
        "scoring_elapsed_seconds": scoring_elapsed,
        "invocation_elapsed_seconds": invocation_elapsed,
        "new_windows_per_second": new_rate,
        "peak_cuda_allocated_bytes": peak_allocated,
        "peak_cuda_reserved_bytes": peak_reserved,
        "a09_config_fingerprint": a09_config_fingerprint,
        "a02_script_sha256": a02_sha,
        "a02_config_fingerprint": a02_config_fingerprint,
        "model_revision": model_revision,
        "started_utc": started_utc,
        "completed_utc": utc_now(),
    }
    atomic_json(summary, args.output_dir / "summary.json")

    metadata = {
        "script_version": SCRIPT_VERSION,
        "methodology": {
            "category": "FUN = primary function_body membership",
            "input_perturbations": "A09 pregenerated fixed ordered perturbations; no regeneration during production scoring",
            "window_coordinate": "128 literal-space tokens prepared by A09",
            "npr_definition": "mean perturbed log-rank / original log-rank",
            "unit_aggregation": "A02 valid-frontier space-by-token weighting plus pooled components",
            "classification": "disabled",
            "resume": "per-window SQLite primary key checkpoint",
        },
        "inputs": {
            "a09_root": str(args.a09_root),
            "a10_root": str(args.a10_root),
            "a02_script": str(args.a02_script),
            "a02_script_sha256": a02_sha,
        },
        "scoring_configuration": a02_config_payload,
        "package_versions": package_versions,
        "detector_source_hashes": source_hashes,
        "runtime": {
            "python_version": platform.python_version(),
            "gpu_name": gpu_name,
            "gpu_total_memory_bytes": int(runtime.gpu_total_memory_bytes),
            "tokenizer_model_max_length": runtime.tokenizer_model_max_length,
            "model_context_fields": runtime.model_context_fields,
            "reported_model_context_limit": runtime.reported_model_context_limit,
            "model_revision": model_revision,
            "explicit_llm_truncation": False,
        },
    }
    atomic_json(metadata, args.output_dir / "metadata.json")
    write_progress(
        progress_path,
        args.gpu_index,
        args.system_label,
        selected_expected_windows,
        counts["windows"],
        newly_scored,
        reused_at_start,
        scoring_started,
        last_shard,
        last_sha,
        last_window_index,
    )
    connection.close()

    print("=" * 80)
    print("run-x-a11 FUN fixed-perturbation NPR scoring")
    print(f"Status:                          {status}")
    print(f"GPU index:                       {args.gpu_index}")
    print(f"System label:                    {args.system_label}")
    print(f"GPU:                             {gpu_name}")
    print(f"Limited/smoke run:               {int(limited_run)}")
    print(f"Assigned logical shards:         {len(assigned_shards)}")
    print(f"Full planned FUN windows:        {full_expected_windows}")
    print(f"Selected expected windows:       {selected_expected_windows}")
    print(f"Database window scores:          {counts['windows']}")
    print(f"Newly scored this invocation:    {newly_scored}")
    print(f"Resume-reused at start:          {reused_at_start}")
    print(f"Invalid NPR windows:             {counts['invalid_windows']}")
    print(f"Scoring errors:                  {counts['scoring_errors']}")
    print(f"Exported complete unique units:  {units_written}")
    print(f"Partial unique units:            {partial_units}")
    print(f"Reference exact checks:          {len(reference_rows)}")
    print(f"A02 script SHA256:               {a02_sha}")
    print(f"A02 config fingerprint:          {a02_config_fingerprint}")
    print(f"Model revision:                  {model_revision}")
    print(f"Model load seconds:              {runtime.model_load_seconds:.3f}")
    print(f"Scoring elapsed seconds:         {scoring_elapsed:.3f}")
    print(f"New windows/second:              {new_rate:.6f}")
    print(f"Peak CUDA allocated bytes:       {peak_allocated}")
    print(f"Peak CUDA reserved bytes:        {peak_reserved}")
    print(f"Failed checks:                   {len(failed_checks)}")
    print(f"Failure rows:                    {len(failure_rows)}")
    print(f"Output directory:                {args.output_dir}")
    print("=" * 80)
    return 0 if status == "PASS" else 5


if __name__ == "__main__":
    raise SystemExit(main())
