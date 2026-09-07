#!/usr/bin/env python3
"""Score historical Python procedure windows with GPT-OSS-120B NPR.

run-x-b01 replaces the historical StarCoder2-7B NPR scoring stage while preserving
its measurement semantics:

* A09's frozen 128 literal-space-token windows are reused exactly.
* A09's ordered 50 perturbations per window are reused exactly; they are never
  regenerated during production scoring.
* Window NPR is mean perturbed log-rank divided by original log-rank.
* Procedure NPR uses the frozen valid-frontier marginal-coverage weighting from A02.
* No HWC/AGC classification or thresholding occurs in this stage.

The selected historical universe is the union of A09 FUN and C_FUN memberships.
This is important because downstream longitudinal analysis uses regular functions,
class methods, and their joint RF+CM scope. FUN/C_FUN overlap content is scored once
and retained with both memberships.

This script is intentionally standalone with respect to previous shell wrappers. It
reuses the frozen A02 Python measurement helpers and the existing DetectCodeGPT rank
implementation, but loads GPT-OSS-120B directly so the new experiment does not depend
on the old StarCoder-specific one-GPU A11/A14 runtime guards.

Versioned delivery filename:
    code-detection/score_historical_npr_gptoss-v1.py
Canonical server filename after deployment:
    code-detection/score_historical_npr_gptoss.py
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
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Iterator, Sequence

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

SCRIPT_VERSION = "run-x-b01-v1"
SCORING_MODEL = "openai/gpt-oss-120b"
WINDOW_SIZE = 128
PERTURBATIONS_PER_WINDOW = 50
RANDOM_SEED = 20260723
PERTURBATION_TYPE = "random-insert-space+newline"
AGGREGATION_POLICY = "valid_frontier_space_by_token_weighting_with_component_retention"
WINDOW_POLICY = "128_space_by_tokens_final_full_window_shifted_backward_with_overlap"

EXPECTED_A02_SHA256 = "57e0781a406d992fb045335a79b1cb97e5c0557de9582603401f6d402ef528a0"
EXPECTED_A09_CONFIG_FINGERPRINT = "3f78c8c43aaa014cd0f5e1a5d1c2df7d4269deb55c4c999e4483d08a324dd9bb"
EXPECTED_A05_MANIFEST_SHA256 = "1acb3726f5c62e6154672f1aff592973c65a13e58dbfd37f8058560d1a474e6c"

EXPECTED_SCOPE_COUNTS = {
    "fun": {"units": 105_635, "windows": 307_600},
    "cfun": {"units": 195_193, "windows": 567_557},
    "all": {"units": 300_825, "windows": 875_154},
}
EXPECTED_OVERLAP_UNITS = 3
EXPECTED_OVERLAP_WINDOWS = 3

WINDOW_COLUMNS = [
    "scoring_fingerprint",
    "code_unit_sha256",
    "code_unit_relative_path",
    "code_unit_types",
    "unit_groups",
    "fun_membership",
    "cfun_membership",
    "logical_shard",
    "window_index",
    "window_space_by_start",
    "window_space_by_end",
    "window_space_by_token_count",
    "window_marginal_space_by_token_count",
    "window_aggregation_weight_space_by_tokens",
    "original_llm_token_count",
    "perturbed_llm_token_count_min",
    "perturbed_llm_token_count_mean",
    "perturbed_llm_token_count_max",
    "reported_model_context_limit",
    "original_log_rank",
    "mean_perturbed_log_rank",
    "window_npr",
    "window_npr_valid",
    "window_npr_invalid_reason",
    "expected_perturbations",
    "valid_perturbation_scores",
    "scoring_error_type",
    "scoring_error_message",
    "scoring_seconds",
]

UNIT_COLUMNS = [
    "scoring_fingerprint",
    "code_unit_sha256",
    "code_unit_relative_path",
    "code_unit_types",
    "unit_groups",
    "fun_membership",
    "cfun_membership",
    "logical_shard",
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
    "status",
]

CHECK_COLUMNS = ["check_name", "passed", "observed", "expected", "note"]
FAILURE_COLUMNS = [
    "code_unit_sha256", "window_index", "logical_shard", "scoring_error_type",
    "scoring_error_message",
]
EXCLUSION_COLUMNS = [
    "code_unit_sha256", "window_index", "logical_shard", "window_npr_invalid_reason",
    "original_llm_token_count", "reported_model_context_limit", "original_log_rank",
    "valid_perturbation_scores",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def ordered_text_digest(texts: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for text in texts:
        encoded = text.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def atomic_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    temp.replace(path)


def atomic_csv(rows: Iterable[dict[str, Any]], path: Path, fieldnames: Sequence[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})
            count += 1
    temp.replace(path)
    return count


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    note: str = "",
) -> None:
    checks.append({
        "check_name": name,
        "passed": int(bool(passed)),
        "observed": observed,
        "expected": expected,
        "note": note,
    })


def parse_shard_ids(spec: str) -> set[int] | None:
    text = spec.strip().lower()
    if text in {"", "all"}:
        return None
    result: set[int] = set()
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            left, right = token.split("-", 1)
            start, end = int(left), int(right)
            if start > end:
                raise ValueError(f"Invalid shard range: {token}")
            result.update(range(start, end + 1))
        else:
            result.add(int(token))
    if not result:
        raise ValueError("No shard IDs selected")
    if min(result) < 0 or max(result) > 95:
        raise ValueError(f"Shard IDs must be in 0..95; got {sorted(result)}")
    return result


def split_groups(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    return {item.strip() for item in str(value or "").split(",") if item.strip()}


def scope_matches(groups: set[str], scope: str) -> bool:
    if scope == "fun":
        return "FUN" in groups
    if scope == "cfun":
        return "C_FUN" in groups
    return bool(groups & {"FUN", "C_FUN"})


def shard_paths(a09_root: Path, shard_id: int) -> tuple[Path, Path]:
    return (
        a09_root / "shards" / f"shard-{shard_id:03d}-of-096.jsonl.gz",
        a09_root / "shards" / f"shard-{shard_id:03d}-of-096.summary.json",
    )


def read_selected_unit_plan(
    path: Path,
    scope: str,
    selected_shards: set[int] | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "code_unit_sha256", "code_unit_relative_path", "space_by_token_count",
            "expected_windows", "code_unit_types", "unit_groups", "logical_shard",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"A09 unique unit plan missing columns: {sorted(missing)}")
        for row in reader:
            shard = int(row["logical_shard"])
            if selected_shards is not None and shard not in selected_shards:
                continue
            groups = split_groups(row["unit_groups"])
            if not scope_matches(groups, scope):
                continue
            sha = str(row["code_unit_sha256"])
            result[sha] = {
                "code_unit_sha256": sha,
                "code_unit_relative_path": str(row["code_unit_relative_path"]),
                "space_by_tokens_total": int(row["space_by_token_count"]),
                "n_expected_windows": int(row["expected_windows"]),
                "code_unit_types": str(row["code_unit_types"]),
                "unit_groups": str(row["unit_groups"]),
                "fun_membership": int("FUN" in groups),
                "cfun_membership": int("C_FUN" in groups),
                "logical_shard": shard,
            }
    return result


def validate_a09_shards(
    a09_root: Path,
    shard_ids: Sequence[int],
    expected_fingerprint: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for shard_id in shard_ids:
        data_path, summary_path = shard_paths(a09_root, shard_id)
        errors: list[str] = []
        summary: dict[str, Any] = {}
        if not data_path.is_file():
            errors.append("missing_data_shard")
        if not summary_path.is_file():
            errors.append("missing_summary_shard")
        if not errors:
            summary = load_json(summary_path)
            if summary.get("status") != "PASS":
                errors.append("summary_status_not_PASS")
            if str(summary.get("config_fingerprint")) != expected_fingerprint:
                errors.append("config_fingerprint_mismatch")
            if int(summary.get("logical_shard", -1)) != shard_id:
                errors.append("logical_shard_mismatch")
            if data_path.stat().st_size != int(summary.get("gzip_bytes", -1)):
                errors.append("gzip_size_mismatch")
            if sha256_file(data_path) != str(summary.get("gzip_sha256")):
                errors.append("gzip_sha256_mismatch")
        rows.append({
            "logical_shard": shard_id,
            "data_path": str(data_path),
            "summary_path": str(summary_path),
            "status": "PASS" if not errors else "FAIL",
            "error_messages": ";".join(errors),
        })
    return rows


def iter_selected_records(
    path: Path,
    selected_shas: set[str],
) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            sha = str(record.get("code_unit_sha256", ""))
            if sha in selected_shas:
                yield record


@dataclass
class RuntimeBundle:
    args: Any
    model_config: dict[str, Any]
    torch: Any
    get_rank: Any
    get_ranks: Any
    model_load_seconds: float
    gpu_names: list[str]
    gpu_memory_gib: list[float]
    reported_model_context_limit: int | None
    model_revision: str
    device_map: dict[str, Any] | None


def positive_context_value(value: Any) -> int | None:
    try:
        numeric = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if numeric <= 0 or numeric >= 10**12:
        return None
    return numeric


def load_gptoss_runtime(args: argparse.Namespace) -> RuntimeBundle:
    project_root = str(args.project_root.resolve())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    import torch
    import transformers
    from baselines.rank import get_rank, get_ranks

    if not torch.cuda.is_available():
        raise RuntimeError("GPT-OSS scoring requires CUDA; torch.cuda.is_available() is false")

    n_gpu = int(torch.cuda.device_count())
    gpu_names = [str(torch.cuda.get_device_name(i)) for i in range(n_gpu)]
    gpu_memory_gib = [float(torch.cuda.get_device_properties(i).total_memory / 1024**3) for i in range(n_gpu)]

    two_large_gpus = n_gpu == 2 and min(gpu_memory_gib) >= 47.0
    three_or_more = n_gpu >= 3
    if not (two_large_gpus or three_or_more or args.allow_unsupported_gpu_topology):
        raise RuntimeError(
            "GPT-OSS-120B B01 expects either 2 visible GPUs with >=47 GiB each "
            "(Server 173) or >=3 visible GPUs (r158-style). "
            f"Got n_gpu={n_gpu}, memory_gib={[round(x, 1) for x in gpu_memory_gib]}, "
            f"CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')}"
        )

    max_memory: dict[Any, str] = {}
    if two_large_gpus:
        for i in range(n_gpu):
            max_memory[i] = args.two_gpu_max_memory
    elif three_or_more:
        for i in range(n_gpu):
            max_memory[i] = args.per_gpu_max_memory
    else:
        for i, mem in enumerate(gpu_memory_gib):
            max_memory[i] = f"{max(1, int(mem - 5))}GiB"
    max_memory["cpu"] = args.cpu_max_memory

    print(f"CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')}")
    print(f"torch.cuda.device_count()={n_gpu}")
    print(f"Visible GPUs={gpu_names}")
    print(f"Visible GPU memory GiB={[round(x, 1) for x in gpu_memory_gib]}")
    print(f"GPT-OSS max_memory={max_memory}")
    if args.model_revision:
        print(f"Requested model revision={args.model_revision}")

    started = time.perf_counter()
    model = transformers.AutoModelForCausalLM.from_pretrained(
        args.scoring_model,
        revision=args.model_revision or None,
        cache_dir=str(args.model_cache_dir),
        torch_dtype="auto",
        device_map="auto",
        max_memory=max_memory,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        args.scoring_model,
        revision=args.model_revision or None,
        cache_dir=str(args.model_cache_dir),
        trust_remote_code=True,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    model.eval()
    model_load_seconds = time.perf_counter() - started

    revision = str(getattr(model.config, "_commit_hash", "") or "")
    if args.expected_model_revision and revision != args.expected_model_revision:
        raise RuntimeError(
            f"Model revision mismatch: observed={revision!r}, expected={args.expected_model_revision!r}"
        )

    tokenizer_limit = positive_context_value(getattr(tokenizer, "model_max_length", None))
    context_fields: list[int] = []
    for field in ("max_position_embeddings", "n_positions", "max_sequence_length", "seq_length"):
        value = positive_context_value(getattr(model.config, field, None))
        if value is not None:
            context_fields.append(value)
    candidates = list(context_fields)
    if tokenizer_limit is not None:
        candidates.append(tokenizer_limit)
    reported_context = min(candidates) if candidates else None

    device_map = getattr(model, "hf_device_map", None)
    rank_args = SimpleNamespace(DEVICE=args.device)
    return RuntimeBundle(
        args=rank_args,
        model_config={"base_model": model, "base_tokenizer": tokenizer},
        torch=torch,
        get_rank=get_rank,
        get_ranks=get_ranks,
        model_load_seconds=float(model_load_seconds),
        gpu_names=gpu_names,
        gpu_memory_gib=gpu_memory_gib,
        reported_model_context_limit=reported_context,
        model_revision=revision,
        device_map=device_map if isinstance(device_map, dict) else None,
    )


def score_prepared_window(record: dict[str, Any], a02: Any, runtime: RuntimeBundle) -> dict[str, Any]:
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
        if (
            runtime.reported_model_context_limit is not None
            and original_llm_tokens > runtime.reported_model_context_limit
        ):
            return {
                "original_llm_token_count": original_llm_tokens,
                "perturbed_llm_token_count_min": None,
                "perturbed_llm_token_count_mean": None,
                "perturbed_llm_token_count_max": None,
                "original_log_rank": None,
                "mean_perturbed_log_rank": None,
                "window_npr": None,
                "expected_perturbations": PERTURBATIONS_PER_WINDOW,
                "valid_perturbation_scores": 0,
                "deterministic_exclusion_reason": "model_context_exceeded",
                "scoring_error_type": None,
                "scoring_error_message": None,
                "scoring_seconds": float(time.perf_counter() - started),
            }

        original_log_rank = runtime.get_rank(original_text, runtime.args, runtime.model_config, log=True)
        perturbed_lengths = a02.tokenizer_lengths(tokenizer, perturbations)
        perturbed_ranks = runtime.get_ranks(perturbations, runtime.args, runtime.model_config, log=True)
        valid_ranks = [float(value) for value in perturbed_ranks if a02.sanitize_float(value) is not None]
        mean_perturbed = float(sum(valid_ranks) / len(valid_ranks)) if valid_ranks else None
        window_npr = None
        if mean_perturbed is not None and a02.sanitize_float(original_log_rank) not in (None, 0.0):
            window_npr = float(mean_perturbed / float(original_log_rank))
        return {
            "original_llm_token_count": original_llm_tokens,
            "perturbed_llm_token_count_min": min(perturbed_lengths) if perturbed_lengths else None,
            "perturbed_llm_token_count_mean": (sum(perturbed_lengths) / len(perturbed_lengths)) if perturbed_lengths else None,
            "perturbed_llm_token_count_max": max(perturbed_lengths) if perturbed_lengths else None,
            "original_log_rank": float(original_log_rank),
            "mean_perturbed_log_rank": mean_perturbed,
            "window_npr": window_npr,
            "expected_perturbations": PERTURBATIONS_PER_WINDOW,
            "valid_perturbation_scores": len(valid_ranks),
            "deterministic_exclusion_reason": None,
            "scoring_error_type": None,
            "scoring_error_message": None,
            "scoring_seconds": float(time.perf_counter() - started),
        }
    except Exception as error:
        return {
            "original_llm_token_count": original_llm_tokens,
            "perturbed_llm_token_count_min": min(perturbed_lengths) if perturbed_lengths else None,
            "perturbed_llm_token_count_mean": (sum(perturbed_lengths) / len(perturbed_lengths)) if perturbed_lengths else None,
            "perturbed_llm_token_count_max": max(perturbed_lengths) if perturbed_lengths else None,
            "original_log_rank": None,
            "mean_perturbed_log_rank": None,
            "window_npr": None,
            "expected_perturbations": PERTURBATIONS_PER_WINDOW,
            "valid_perturbation_scores": 0,
            "deterministic_exclusion_reason": None,
            "scoring_error_type": type(error).__name__,
            "scoring_error_message": str(error)[:2000],
            "scoring_seconds": float(time.perf_counter() - started),
        }


def make_window_row(
    record: dict[str, Any],
    unit: dict[str, Any],
    scored: dict[str, Any],
    a02: Any,
    scoring_fingerprint: str,
    reported_context: int | None,
) -> dict[str, Any]:
    deterministic_reason = scored.get("deterministic_exclusion_reason")
    if deterministic_reason:
        valid, reason = False, deterministic_reason
    else:
        valid, reason = a02.classify_window_validity(scored)

    start = int(record["window_space_by_start"])
    end = int(record["window_space_by_end"])
    marginal = int(record.get("window_marginal_space_by_token_count", end - start))
    return {
        "scoring_fingerprint": scoring_fingerprint,
        "code_unit_sha256": unit["code_unit_sha256"],
        "code_unit_relative_path": unit["code_unit_relative_path"],
        "code_unit_types": unit["code_unit_types"],
        "unit_groups": unit["unit_groups"],
        "fun_membership": unit["fun_membership"],
        "cfun_membership": unit["cfun_membership"],
        "logical_shard": int(record["logical_shard"]),
        "window_index": int(record["window_index"]),
        "window_space_by_start": start,
        "window_space_by_end": end,
        "window_space_by_token_count": int(record.get("window_space_by_token_count", end - start)),
        "window_marginal_space_by_token_count": marginal,
        "window_aggregation_weight_space_by_tokens": 0,
        "original_llm_token_count": scored.get("original_llm_token_count"),
        "perturbed_llm_token_count_min": scored.get("perturbed_llm_token_count_min"),
        "perturbed_llm_token_count_mean": scored.get("perturbed_llm_token_count_mean"),
        "perturbed_llm_token_count_max": scored.get("perturbed_llm_token_count_max"),
        "reported_model_context_limit": reported_context,
        "original_log_rank": a02.sanitize_float(scored.get("original_log_rank")),
        "mean_perturbed_log_rank": a02.sanitize_float(scored.get("mean_perturbed_log_rank")),
        "window_npr": a02.sanitize_float(scored.get("window_npr")),
        "window_npr_valid": int(bool(valid)),
        "window_npr_invalid_reason": reason,
        "expected_perturbations": int(scored.get("expected_perturbations", PERTURBATIONS_PER_WINDOW)),
        "valid_perturbation_scores": int(scored.get("valid_perturbation_scores", 0)),
        "scoring_error_type": scored.get("scoring_error_type"),
        "scoring_error_message": scored.get("scoring_error_message"),
        "scoring_seconds": float(scored.get("scoring_seconds", 0.0)),
    }


def open_database(path: Path, overwrite: bool) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    columns_sql = ",\n".join(
        f"{name} TEXT" if name in {
            "scoring_fingerprint", "code_unit_sha256", "code_unit_relative_path", "code_unit_types",
            "unit_groups", "window_npr_invalid_reason", "scoring_error_type", "scoring_error_message"
        } else f"{name} REAL"
        for name in WINDOW_COLUMNS
    )
    conn.execute(f"CREATE TABLE IF NOT EXISTS window_scores ({columns_sql}, PRIMARY KEY(code_unit_sha256, window_index))")
    conn.execute("CREATE TABLE IF NOT EXISTS run_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()
    return conn


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM run_meta WHERE key=?", (key,)).fetchone()
    return None if row is None else str(row[0])


def set_meta(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES(?,?)", (key, str(value)))
    conn.commit()


def load_completed_keys(conn: sqlite3.Connection) -> set[tuple[str, int]]:
    return {
        (str(row[0]), int(row[1]))
        for row in conn.execute("SELECT code_unit_sha256, window_index FROM window_scores")
    }


def insert_window(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    placeholders = ",".join("?" for _ in WINDOW_COLUMNS)
    conn.execute(
        f"INSERT OR REPLACE INTO window_scores ({','.join(WINDOW_COLUMNS)}) VALUES ({placeholders})",
        [row.get(column) for column in WINDOW_COLUMNS],
    )
    conn.commit()


def sqlite_window_rows(conn: sqlite3.Connection) -> Iterator[dict[str, Any]]:
    query = f"SELECT {','.join(WINDOW_COLUMNS)} FROM window_scores ORDER BY logical_shard, code_unit_sha256, window_index"
    for row in conn.execute(query):
        yield dict(row)


def aggregate_units(
    window_rows: list[dict[str, Any]],
    unit_plan: dict[str, dict[str, Any]],
    a02: Any,
    scoring_fingerprint: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows_by_sha: dict[str, list[dict[str, Any]]] = {}
    for row in window_rows:
        rows_by_sha.setdefault(str(row["code_unit_sha256"]), []).append(row)

    unit_rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for sha, unit in sorted(unit_plan.items(), key=lambda item: (item[1]["logical_shard"], item[0])):
        window_rows = sorted(rows_by_sha.get(sha, []), key=lambda row: int(row["window_index"]))
        for row in window_rows:
            if not bool(int(row["window_npr_valid"])):
                exclusions.append({column: row.get(column) for column in EXCLUSION_COLUMNS})
        if not window_rows:
            continue
        n_valid = sum(int(row["window_npr_valid"]) for row in window_rows)
        original_all = sum(int(row["original_llm_token_count"] or 0) for row in window_rows)
        original_valid = sum(
            int(row["original_llm_token_count"] or 0)
            for row in window_rows if int(row["window_npr_valid"])
        )
        base = {
            "scoring_fingerprint": scoring_fingerprint,
            **unit,
            "n_attempted_windows": len(window_rows),
            "n_valid_npr_windows": n_valid,
            "n_invalid_npr_windows": len(window_rows) - n_valid,
            "original_llm_tokens_all_windows": original_all,
            "original_llm_tokens_valid_windows": original_valid,
        }
        try:
            aggregate = a02.aggregate_code_unit(window_rows, int(unit["space_by_tokens_total"]))
            base.update(aggregate)
            base["partial_code_unit_score"] = int(len(window_rows) != int(unit["n_expected_windows"]) or n_valid != len(window_rows))
            base["status"] = "partial" if base["partial_code_unit_score"] else "scored"
        except Exception:
            base.update({
                "space_by_tokens_scored": 0,
                "npr_coverage_ratio": 0.0,
                "code_unit_npr_space_by_token_weighted": None,
                "code_unit_original_log_rank_weighted": None,
                "code_unit_mean_perturbed_log_rank_weighted": None,
                "code_unit_npr_pooled_components": None,
                "partial_code_unit_score": 1,
                "status": "all_windows_invalid",
            })
        unit_rows.append(base)
    return unit_rows, exclusions


def write_progress(
    path: Path,
    started: float,
    newly_scored: int,
    database_windows: int,
    expected_windows: int,
    last_shard: int | None,
    last_sha: str | None,
    last_window: int | None,
) -> None:
    elapsed = max(1e-9, time.perf_counter() - started)
    atomic_json({
        "script_version": SCRIPT_VERSION,
        "updated_utc": utc_now(),
        "newly_scored_windows_this_invocation": newly_scored,
        "database_windows": database_windows,
        "expected_selected_windows": expected_windows,
        "new_scoring_rate_windows_per_second": newly_scored / elapsed,
        "last_logical_shard": last_shard,
        "last_code_unit_sha256": last_sha,
        "last_window_index": last_window,
    }, path)


def run_self_test(a02_path: Path) -> None:
    assert parse_shard_ids("all") is None
    assert parse_shard_ids("0,2-4") == {0, 2, 3, 4}
    assert scope_matches({"FUN"}, "all")
    assert scope_matches({"C_FUN"}, "all")
    assert scope_matches({"FUN", "C_FUN"}, "fun")
    a02 = load_module(a02_path, "run_x_b01_a02_selftest")
    rows = [
        {"window_npr_valid": 1, "window_space_by_start": 0, "window_space_by_end": 3,
         "window_npr": 1.2, "original_log_rank": 2.0, "mean_perturbed_log_rank": 2.4},
        {"window_npr_valid": 1, "window_space_by_start": 2, "window_space_by_end": 5,
         "window_npr": 1.4, "original_log_rank": 2.0, "mean_perturbed_log_rank": 2.8},
    ]
    out = a02.aggregate_code_unit(rows, 5)
    assert math.isclose(out["code_unit_npr_space_by_token_weighted"], 1.28, abs_tol=1e-12)
    assert out["space_by_tokens_scored"] == 5
    print("score_historical_npr_gptoss self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run-x-b01 GPT-OSS historical NPR scoring")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--a02-script", type=Path, default=Path("code-detection/score_snapshot_npr.py"))
    parser.add_argument("--a09-root", type=Path, default=Path("output/snapshot_npr/run-x-a09"))
    parser.add_argument("--a10-root", type=Path, default=Path("output/snapshot_npr/run-x-a10"))
    parser.add_argument("--a13-root", type=Path, default=Path("output/snapshot_npr/run-x-a13"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scope", choices=("fun", "cfun", "all"), default="all")
    parser.add_argument("--shard-ids", default="all", help="all, comma list, or ranges such as 0-31,40,42")
    parser.add_argument("--scoring-model", default=SCORING_MODEL)
    parser.add_argument("--model-revision", default="")
    parser.add_argument("--expected-model-revision", default="")
    parser.add_argument("--model-cache-dir", type=Path, default=Path("~/.cache/huggingface/hub").expanduser())
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--two-gpu-max-memory", default="42GiB")
    parser.add_argument("--per-gpu-max-memory", default="44GiB")
    parser.add_argument("--cpu-max-memory", default="128GiB")
    parser.add_argument("--system-label", default="server173")
    parser.add_argument("--progress-every-windows", type=int, default=25)
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--retry-error-windows", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--finalize-only", action="store_true")
    parser.add_argument("--allow-unsupported-gpu-topology", action="store_true")
    parser.add_argument("--self-test-only", action="store_true")
    return parser.parse_args()


def resolve(project_root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    args.project_root = project_root
    args.a02_script = resolve(project_root, args.a02_script)
    args.a09_root = resolve(project_root, args.a09_root)
    args.a10_root = resolve(project_root, args.a10_root)
    args.a13_root = resolve(project_root, args.a13_root)
    args.output_dir = resolve(project_root, args.output_dir)
    args.model_cache_dir = args.model_cache_dir.expanduser().resolve()

    if args.self_test_only:
        run_self_test(args.a02_script)
        return 0

    started_utc = utc_now()
    invocation_started = time.perf_counter()
    checks: list[dict[str, Any]] = []

    if not args.a02_script.is_file():
        raise FileNotFoundError(f"Missing frozen A02 script: {args.a02_script}")
    a02_sha = sha256_file(args.a02_script)
    add_check(checks, "a02_script_sha256", a02_sha == EXPECTED_A02_SHA256, a02_sha, EXPECTED_A02_SHA256)
    if a02_sha != EXPECTED_A02_SHA256:
        raise RuntimeError("A02 script SHA-256 mismatch; refusing B01 scoring")
    a02 = load_module(args.a02_script, "run_x_b01_frozen_a02")

    a09_summary_path = args.a09_root / "plan" / "summary.json"
    a09_plan_path = args.a09_root / "plan" / "unique_primary_units.csv"
    for required in (a09_summary_path, a09_plan_path):
        if not required.is_file():
            raise FileNotFoundError(f"Missing required A09 input: {required}")
    a09_summary = load_json(a09_summary_path)
    a09_fingerprint = str(a09_summary.get("config_fingerprint", ""))
    add_check(checks, "a09_status", a09_summary.get("status") == "PASS", a09_summary.get("status"), "PASS")
    add_check(checks, "a09_config_fingerprint", a09_fingerprint == EXPECTED_A09_CONFIG_FINGERPRINT, a09_fingerprint, EXPECTED_A09_CONFIG_FINGERPRINT)
    add_check(checks, "a09_input_manifest_sha256", str(a09_summary.get("input_manifest_sha256")) == EXPECTED_A05_MANIFEST_SHA256, a09_summary.get("input_manifest_sha256"), EXPECTED_A05_MANIFEST_SHA256)

    # A10/A13 are not scoring dependencies in B01. They are checked when present to
    # document that B01 is replacing the same FUN/C_FUN workload used downstream.
    if (args.a10_root / "summary.json").is_file():
        a10_summary = load_json(args.a10_root / "summary.json")
        add_check(checks, "a10_status_reference", a10_summary.get("status") == "PASS", a10_summary.get("status"), "PASS", "reference-only")
    if (args.a13_root / "summary.json").is_file():
        a13_summary = load_json(args.a13_root / "summary.json")
        add_check(checks, "a13_status_reference", a13_summary.get("status") == "PASS", a13_summary.get("status"), "PASS", "reference-only")

    selected_shards = parse_shard_ids(args.shard_ids)
    shard_ids = sorted(selected_shards if selected_shards is not None else set(range(96)))
    unit_plan = read_selected_unit_plan(a09_plan_path, args.scope, selected_shards)
    selected_shas = set(unit_plan)
    expected_windows = sum(int(row["n_expected_windows"]) for row in unit_plan.values())
    fun_units = sum(int(row["fun_membership"]) for row in unit_plan.values())
    cfun_units = sum(int(row["cfun_membership"]) for row in unit_plan.values())
    overlap_units = sum(int(row["fun_membership"] and row["cfun_membership"]) for row in unit_plan.values())

    if selected_shards is None:
        expected = EXPECTED_SCOPE_COUNTS[args.scope]
        add_check(checks, "full_scope_unit_count", len(unit_plan) == expected["units"], len(unit_plan), expected["units"])
        add_check(checks, "full_scope_window_count", expected_windows == expected["windows"], expected_windows, expected["windows"])
        if args.scope == "all":
            add_check(checks, "fun_memberships", fun_units == EXPECTED_SCOPE_COUNTS["fun"]["units"], fun_units, EXPECTED_SCOPE_COUNTS["fun"]["units"])
            add_check(checks, "cfun_memberships", cfun_units == EXPECTED_SCOPE_COUNTS["cfun"]["units"], cfun_units, EXPECTED_SCOPE_COUNTS["cfun"]["units"])
            add_check(checks, "fun_cfun_overlap_units", overlap_units == EXPECTED_OVERLAP_UNITS, overlap_units, EXPECTED_OVERLAP_UNITS)

    shard_audit = validate_a09_shards(args.a09_root, shard_ids, a09_fingerprint)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_csv(shard_audit, args.output_dir / "assigned_shard_audit.csv", ["logical_shard", "data_path", "summary_path", "status", "error_messages"])
    shard_failures = [row for row in shard_audit if row["status"] != "PASS"]
    add_check(checks, "selected_shard_integrity", not shard_failures, len(shard_failures), 0)
    if any(not bool(row["passed"]) for row in checks):
        atomic_csv(checks, args.output_dir / "checks.csv", CHECK_COLUMNS)
        raise RuntimeError("B01 input/provenance validation failed")

    db_path = args.output_dir / "window_scores.sqlite3"
    if args.finalize_only and not db_path.is_file():
        raise FileNotFoundError(f"Finalize-only requires existing checkpoint: {db_path}")

    runtime: RuntimeBundle | None = None
    if not args.finalize_only:
        runtime = load_gptoss_runtime(args)
        model_revision = runtime.model_revision
        source_hashes = {
            "a02_sha256": a02_sha,
            "rank_sha256": sha256_file(project_root / "baselines" / "rank.py"),
            "b01_script_sha256": sha256_file(Path(__file__).resolve()),
        }
        scoring_fingerprint = stable_json_hash({
            "script_version": SCRIPT_VERSION,
            "scoring_model": args.scoring_model,
            "model_revision": model_revision,
            "window_size": WINDOW_SIZE,
            "perturbations_per_window": PERTURBATIONS_PER_WINDOW,
            "perturbation_type": PERTURBATION_TYPE,
            "random_seed": RANDOM_SEED,
            "window_policy": WINDOW_POLICY,
            "aggregation_policy": AGGREGATION_POLICY,
            "a09_config_fingerprint": a09_fingerprint,
            "source_hashes": source_hashes,
        })
    else:
        model_revision = ""
        scoring_fingerprint = ""

    conn = open_database(db_path, overwrite=args.overwrite and not args.finalize_only)
    existing_fp = get_meta(conn, "scoring_fingerprint")
    if args.finalize_only:
        if not existing_fp:
            raise RuntimeError("Finalize-only checkpoint lacks scoring_fingerprint metadata")
        scoring_fingerprint = existing_fp
        model_revision = get_meta(conn, "model_revision") or ""
    else:
        if existing_fp and existing_fp != scoring_fingerprint:
            raise RuntimeError(
                "Existing B01 checkpoint has incompatible scoring fingerprint; use OVERWRITE=1 for a fresh run"
            )
        if not existing_fp:
            set_meta(conn, "scoring_fingerprint", scoring_fingerprint)
            set_meta(conn, "model_revision", model_revision)
            set_meta(conn, "scoring_model", args.scoring_model)
            set_meta(conn, "script_version", SCRIPT_VERSION)
            set_meta(conn, "scope", args.scope)
            set_meta(conn, "shard_ids", args.shard_ids)

    if args.retry_error_windows and not args.finalize_only:
        conn.execute("DELETE FROM window_scores WHERE scoring_error_type IS NOT NULL")
        conn.commit()

    completed = load_completed_keys(conn)
    reused_at_start = len(completed)
    newly_scored = 0
    candidate_seen = 0
    last_shard = last_window = None
    last_sha: str | None = None
    progress_path = args.output_dir / "progress.json"
    scoring_started = time.perf_counter()

    if not args.finalize_only:
        assert runtime is not None
        stop = False
        for shard_id in shard_ids:
            data_path, _ = shard_paths(args.a09_root, shard_id)
            for record in iter_selected_records(data_path, selected_shas):
                candidate_seen += 1
                if args.max_windows is not None and candidate_seen > args.max_windows:
                    stop = True
                    break
                record["logical_shard"] = shard_id
                sha = str(record["code_unit_sha256"])
                window_index = int(record["window_index"])
                last_shard, last_sha, last_window = shard_id, sha, window_index
                key = (sha, window_index)
                if key in completed:
                    continue
                if str(record.get("config_fingerprint")) != a09_fingerprint:
                    raise RuntimeError(f"A09 record fingerprint mismatch: shard={shard_id}, sha={sha}, window={window_index}")
                if int(record.get("perturbation_count", -1)) != PERTURBATIONS_PER_WINDOW:
                    raise RuntimeError(f"A09 perturbation count mismatch: {sha}/{window_index}")
                perturbations = record.get("perturbations")
                if not isinstance(perturbations, list):
                    raise RuntimeError(f"A09 perturbations missing: {sha}/{window_index}")
                if ordered_text_digest(str(value) for value in perturbations) != str(record.get("perturbations_ordered_sha256")):
                    raise RuntimeError(f"A09 perturbation digest mismatch: {sha}/{window_index}")

                scored = score_prepared_window(record, a02, runtime)
                row = make_window_row(
                    record, unit_plan[sha], scored, a02, scoring_fingerprint,
                    runtime.reported_model_context_limit,
                )
                insert_window(conn, row)
                completed.add(key)
                newly_scored += 1
                if newly_scored % args.progress_every_windows == 0:
                    write_progress(
                        progress_path, scoring_started, newly_scored, len(completed), expected_windows,
                        last_shard, last_sha, last_window,
                    )
                    rate = newly_scored / max(1e-9, time.perf_counter() - scoring_started)
                    print(
                        f"progress new={newly_scored} db={len(completed)} expected={expected_windows} "
                        f"shard={shard_id:03d} rate={rate:.6f} windows/s",
                        flush=True,
                    )
            if stop:
                break

    database_windows = int(conn.execute("SELECT COUNT(*) FROM window_scores").fetchone()[0])
    scoring_errors = int(conn.execute("SELECT COUNT(*) FROM window_scores WHERE scoring_error_type IS NOT NULL").fetchone()[0])
    duplicate_keys = int(conn.execute(
        "SELECT COUNT(*) FROM (SELECT code_unit_sha256,window_index,COUNT(*) n FROM window_scores GROUP BY code_unit_sha256,window_index HAVING n>1)"
    ).fetchone()[0])

    # Export deterministic artifacts from the checkpoint. This also gives finalize-only
    # mode a way to rebuild CSV/QC without loading GPT-OSS or rescoring any window.
    window_rows = list(sqlite_window_rows(conn))
    unit_rows, exclusion_rows = aggregate_units(window_rows, unit_plan, a02, scoring_fingerprint)
    # aggregate_code_unit() assigns the frozen marginal coverage weights in-place.
    # Export after aggregation so the window CSV carries the actual weights used.
    atomic_csv(window_rows, args.output_dir / "python_historical_gptoss_window_npr_scores.csv", WINDOW_COLUMNS)
    atomic_csv(unit_rows, args.output_dir / "python_historical_gptoss_unique_code_unit_npr_scores.csv", UNIT_COLUMNS)
    atomic_csv((row for row in unit_rows if int(row["fun_membership"])), args.output_dir / "python_fun_unique_code_unit_npr_scores.csv", UNIT_COLUMNS)
    atomic_csv((row for row in unit_rows if int(row["cfun_membership"])), args.output_dir / "python_cfun_unique_code_unit_npr_scores.csv", UNIT_COLUMNS)
    atomic_csv(exclusion_rows, args.output_dir / "python_historical_gptoss_npr_exclusions.csv", EXCLUSION_COLUMNS)

    failure_rows = [
        {column: row.get(column) for column in FAILURE_COLUMNS}
        for row in window_rows if row.get("scoring_error_type")
    ]
    atomic_csv(failure_rows, args.output_dir / "python_historical_gptoss_npr_failures.csv", FAILURE_COLUMNS)

    limited = args.max_windows is not None
    expected_db = min(expected_windows, args.max_windows) if limited else expected_windows
    add_check(checks, "checkpoint_duplicate_keys", duplicate_keys == 0, duplicate_keys, 0)
    add_check(checks, "scoring_errors", scoring_errors == 0, scoring_errors, 0)
    if not limited and selected_shards is None:
        add_check(checks, "database_windows_complete", database_windows == expected_windows, database_windows, expected_windows)
    elif limited:
        add_check(checks, "limited_run_has_windows", database_windows > 0, database_windows, ">0")

    all_invalid_units = sum(1 for row in unit_rows if row["status"] == "all_windows_invalid")
    partial_units = sum(1 for row in unit_rows if int(row["partial_code_unit_score"]))
    valid_windows = sum(int(row["window_npr_valid"]) for row in window_rows)
    invalid_windows = database_windows - valid_windows
    failed_checks = sum(1 for row in checks if not bool(row["passed"]))
    status = "PASS" if failed_checks == 0 else "FAIL"

    atomic_csv(checks, args.output_dir / "checks.csv", CHECK_COLUMNS)
    write_progress(
        progress_path, scoring_started, newly_scored, database_windows, expected_windows,
        last_shard, last_sha, last_window,
    )

    runtime_payload: dict[str, Any] = {
        "system_label": args.system_label,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "model_revision": model_revision,
    }
    if runtime is not None:
        runtime_payload.update({
            "gpu_names": runtime.gpu_names,
            "gpu_memory_gib": [round(x, 3) for x in runtime.gpu_memory_gib],
            "model_load_seconds": runtime.model_load_seconds,
            "reported_model_context_limit": runtime.reported_model_context_limit,
            "device_map": runtime.device_map,
            "torch_version": str(runtime.torch.__version__),
            "torch_cuda_version": str(runtime.torch.version.cuda),
        })

    summary = {
        "status": status,
        "script_version": SCRIPT_VERSION,
        "started_utc": started_utc,
        "completed_utc": utc_now(),
        "scope": args.scope,
        "shard_ids": args.shard_ids,
        "selected_shards": len(shard_ids),
        "selected_unique_code_units": len(unit_plan),
        "selected_fun_memberships": fun_units,
        "selected_cfun_memberships": cfun_units,
        "selected_fun_cfun_overlap_units": overlap_units,
        "expected_selected_windows": expected_windows,
        "database_windows": database_windows,
        "valid_npr_windows": valid_windows,
        "invalid_npr_windows": invalid_windows,
        "scoring_errors": scoring_errors,
        "exported_unique_code_units": len(unit_rows),
        "partial_unique_code_units": partial_units,
        "all_windows_invalid_units": all_invalid_units,
        "newly_scored_windows_this_invocation": newly_scored,
        "checkpoint_rows_reused_at_start": reused_at_start,
        "scoring_model": args.scoring_model,
        "model_revision": model_revision,
        "scoring_fingerprint": scoring_fingerprint,
        "a02_sha256": a02_sha,
        "a09_config_fingerprint": a09_fingerprint,
        "window_policy": WINDOW_POLICY,
        "aggregation_policy": AGGREGATION_POLICY,
        "window_size": WINDOW_SIZE,
        "perturbations_per_window": PERTURBATIONS_PER_WINDOW,
        "perturbation_type": PERTURBATION_TYPE,
        "random_seed": RANDOM_SEED,
        "limited_run": limited,
        "max_windows": args.max_windows,
        "failed_checks": failed_checks,
        "runtime": runtime_payload,
        "elapsed_seconds": time.perf_counter() - invocation_started,
    }
    atomic_json(summary, args.output_dir / "summary.json")
    atomic_json({
        "script_version": SCRIPT_VERSION,
        "python_executable": sys.executable,
        "python_version": sys.version,
        "project_root": str(project_root),
        "a02_script": str(args.a02_script),
        "a09_root": str(args.a09_root),
        "a10_root": str(args.a10_root),
        "a13_root": str(args.a13_root),
        "output_dir": str(args.output_dir),
        "model_cache_dir": str(args.model_cache_dir),
        "environment": {key: os.environ.get(key) for key in (
            "CUDA_VISIBLE_DEVICES", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "CONDA_DEFAULT_ENV"
        )},
        "summary": summary,
    }, args.output_dir / "metadata.json")

    print("=" * 80)
    print("run-x-b01 GPT-OSS historical NPR scoring")
    print("=" * 80)
    print(f"Status:                       {status}")
    print(f"Scope:                        {args.scope}")
    print(f"Selected unique units:        {len(unit_plan)}")
    print(f"Expected selected windows:    {expected_windows}")
    print(f"Database windows:             {database_windows}")
    print(f"Valid NPR windows:            {valid_windows}")
    print(f"Invalid NPR windows:          {invalid_windows}")
    print(f"Scoring errors:               {scoring_errors}")
    print(f"Partial unique units:         {partial_units}")
    print(f"All-windows-invalid units:    {all_invalid_units}")
    print(f"Model revision:               {model_revision}")
    print(f"Scoring fingerprint:          {scoring_fingerprint}")
    print(f"Failed checks:                {failed_checks}")
    print(f"Output directory:             {args.output_dir}")
    print("=" * 80)
    conn.close()
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
