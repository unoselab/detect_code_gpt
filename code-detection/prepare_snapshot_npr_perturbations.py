#!/usr/bin/env python3
"""Prepare deterministic perturbation shards for snapshot NPR scoring.

This stage separates perturbation generation from StarCoder2 rank scoring so
that CPU preparation may be distributed across two server systems while all
final rank/NPR measurements can later be executed on one homogeneous GPU
system.

Scientific scope
----------------
- Input: A05 primary snapshot code units.
- Deduplication: one preparation record per unique primary code-unit SHA-256.
- Windowing: identical 128 literal-space-token window policy used by A02,
  including the backward-shifted full final window.
- Perturbations: 50 deterministic DetectCodeGPT-compatible variants per window
  by default, using random-insert-space+newline.
- Output: deterministic gzip-compressed JSONL logical shards containing the
  original raw window plus the ordered perturbation variants and integrity
  digests.
- No model is loaded. No log-rank, NPR, threshold, AGC/HWC, SonarQube, or DiD
  result is computed here.

Two-server preparation
----------------------
A code unit is assigned to one of DATA_SHARDS logical shards by its SHA-256.
A preparation worker owns logical shard s when s % NUM_WORKERS == WORKER_INDEX.
With the default DATA_SHARDS=96, NUM_WORKERS=2, later 3-GPU scoring can also
split the same logical shards evenly by s % 3 without regenerating inputs.

Category membership
-------------------
Primary A05 code-unit types map to downstream groups as follows:
  function_body              -> FUN
  method_body                -> C_FUN
  module_block, class_block  -> BLOCK
A unique source SHA may appear in more than one group. It is prepared exactly
once and stores all group memberships so later category-specific scoring can
reuse the same deterministic input.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib
import importlib.metadata
import importlib.util
import io
import json
import math
import os
import platform
import random
import shutil
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Sequence

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import pandas as pd
import scipy
import scipy.stats


SCRIPT_VERSION = "run-x-a09-v2"
WINDOW_POLICY = "128_space_by_tokens_final_full_window_shifted_backward_with_overlap"
PERTURBATION_POLICY = "detectcodegpt_random_insert_space_plus_newline_reference_compatible_v1"
PRIMARY_ROLE = "primary"

GROUP_BY_TYPE = {
    "function_body": "FUN",
    "method_body": "C_FUN",
    "module_block": "BLOCK",
    "class_block": "BLOCK",
}
GROUP_ORDER = {"FUN": 0, "C_FUN": 1, "BLOCK": 2}

REQUIRED_MANIFEST_COLUMNS = {
    "code_unit_sha256",
    "code_unit_relative_path",
    "code_unit_type",
    "aggregation_role",
    "space_by_token_count",
}

CHECK_COLUMNS = ["check_name", "passed", "observed", "expected", "note"]


@dataclass(frozen=True)
class RawWindow:
    index: int
    start_token: int
    end_token: int
    token_count: int
    marginal_token_count: int
    char_start: int
    char_end: int
    text: str
    overlaps_previous_window: bool


@dataclass
class UniqueUnit:
    code_unit_sha256: str
    code_unit_relative_path: str
    space_by_token_count: int
    code_unit_types: set[str]
    unit_groups: set[str]
    occurrence_count: int
    logical_shard: int = -1
    expected_windows: int = 0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_json_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256_bytes(encoded)


def atomic_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    os.replace(tmp, path)


def atomic_csv(frame: pd.DataFrame, path: Path, columns: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = frame.copy()
    if columns is not None:
        for column in columns:
            if column not in output.columns:
                output[column] = pd.Series(dtype="object")
        output = output[list(columns)]
    tmp = path.with_suffix(path.suffix + ".tmp")
    output.to_csv(tmp, index=False, quoting=csv.QUOTE_MINIMAL)
    os.replace(tmp, path)


def parse_optional_int(text: str | None) -> int | None:
    if text is None or str(text).strip() == "":
        return None
    return int(text)


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def require_columns(columns: Iterable[str], required: set[str], label: str) -> None:
    missing = sorted(required - set(columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def derive_window_seed(global_seed: int, code_unit_sha: str, window_index: int) -> int:
    raw = f"{global_seed}|{code_unit_sha}|{window_index}".encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return int.from_bytes(digest[:4], "big", signed=False)


def literal_space_token_spans(text: str) -> tuple[list[int], list[int]]:
    """Return raw character start/end offsets for every text.split(' ') token."""
    spaces = [index for index, char in enumerate(text) if char == " "]
    starts = [0] + [index + 1 for index in spaces]
    ends = spaces + [len(text)]
    if len(starts) != len(text.split(" ")) or len(ends) != len(starts):
        raise AssertionError("Literal-space token span construction is inconsistent with text.split(' ').")
    return starts, ends


def build_raw_windows(text: str, window_size: int) -> list[RawWindow]:
    """Build A02-compatible windows while preserving exact raw source slices."""
    if window_size < 1:
        raise ValueError("window_size must be positive")
    starts, ends = literal_space_token_spans(text)
    total_tokens = len(starts)

    intervals: list[tuple[int, int]] = []
    if total_tokens <= window_size:
        intervals.append((0, total_tokens))
    else:
        start = 0
        while start < total_tokens:
            end = min(start + window_size, total_tokens)
            if end - start < window_size and intervals:
                start = end - window_size
            intervals.append((start, end))
            if end >= total_tokens:
                break
            start = end

    windows: list[RawWindow] = []
    frontier = 0
    for index, (start_token, end_token) in enumerate(intervals):
        char_start = starts[start_token]
        char_end = ends[end_token - 1]
        raw_text = text[char_start:char_end]
        observed_token_count = len(raw_text.split(" "))
        expected_token_count = end_token - start_token
        if observed_token_count != expected_token_count:
            raise AssertionError(
                f"Raw window token mismatch: observed={observed_token_count}, expected={expected_token_count}"
            )
        marginal_start = max(start_token, frontier)
        marginal_count = max(0, end_token - marginal_start)
        frontier = max(frontier, end_token)
        windows.append(
            RawWindow(
                index=index,
                start_token=start_token,
                end_token=end_token,
                token_count=expected_token_count,
                marginal_token_count=marginal_count,
                char_start=char_start,
                char_end=char_end,
                text=raw_text,
                overlaps_previous_window=marginal_count < expected_token_count,
            )
        )
    if windows and sum(window.marginal_token_count for window in windows) != total_tokens:
        raise AssertionError("Window marginal counts do not cover the code unit exactly once.")
    return windows


def expected_window_count(space_by_tokens: int, window_size: int) -> int:
    if space_by_tokens < 1:
        raise ValueError("space_by_tokens must be positive")
    return max(1, math.ceil(space_by_tokens / window_size))


def set_perturbation_seeds(seed: int) -> None:
    """Match the Python/NumPy seed state established by A02 before perturbation."""
    random.seed(seed)
    np.random.seed(seed)


def random_insert_newline(text: str, pct: float = 0.3, mean: int = 1) -> str:
    """Reference-compatible copy of main.py random_insert_newline()."""
    del mean
    lines = text.split("\n")
    n_lines = len(lines)
    n_inserted = int(n_lines * pct)
    inserted_idxs = np.random.choice(n_lines, n_inserted, replace=False)
    for idx in inserted_idxs:
        n_newlines = 1
        lines[idx] = lines[idx] + "\n" * n_newlines
    return "\n".join(lines)


def random_insert_space(text: str, pct: float = 0.3, mean: int = 1) -> str:
    """Reference-compatible copy of main.py random_insert_space()."""
    tokens = text.split(" ")
    n_tokens = len(tokens)
    n_inserted = int(n_tokens * pct)
    inserted_idxs = np.random.choice(n_tokens, n_inserted, replace=False)
    for idx in inserted_idxs:
        n_spaces = scipy.stats.poisson.rvs(mean) + 1
        tokens[idx] = tokens[idx] + " " * int(n_spaces)
    return " ".join(tokens)


def perturb_texts_reference_compatible(
    texts: list[str],
    pct_words_masked: float,
    span_length: int,
    perturbation_chunk_size: int,
    n_perturbation_rounds: int,
    perturbation_type: str,
) -> list[str]:
    """Reproduce main.py perturb_texts() for random-insert-space+newline exactly.

    The chunk_size behavior is intentionally retained. With 50 identical texts
    and chunk_size=10, each 10-text batch first consumes RNG for 10 space
    variants, then 10 newline variants, and returns 5 of each. Generating only
    25 space and 25 newline variants directly would therefore be a different
    RNG sequence and is not allowed here.
    """
    if perturbation_type != "random-insert-space+newline":
        raise ValueError(
            "A09 v1 only supports perturbation_type='random-insert-space+newline' "
            "because this is the validated A02 production configuration."
        )
    if perturbation_chunk_size < 1:
        raise ValueError("perturbation_chunk_size must be positive")
    if n_perturbation_rounds < 1:
        raise ValueError("n_perturbation_rounds must be positive")

    current = list(texts)
    for _ in range(n_perturbation_rounds):
        outputs: list[str] = []
        for start in range(0, len(current), perturbation_chunk_size):
            chunk = current[start : start + perturbation_chunk_size]
            space_variants = [
                random_insert_space(text, pct_words_masked, span_length) for text in chunk
            ]
            newline_variants = [
                random_insert_newline(text, pct_words_masked, span_length) for text in chunk
            ]
            total_num = len(space_variants)
            n1 = int(total_num / 2)
            n2 = total_num - n1
            outputs.extend(space_variants[:n1])
            outputs.extend(newline_variants[:n2])
        current = outputs
    return current


def ordered_text_digest(texts: Sequence[str]) -> str:
    """Hash an ordered text sequence with unambiguous length prefixes."""
    digest = hashlib.sha256()
    for text in texts:
        raw = text.encode("utf-8")
        digest.update(len(raw).to_bytes(8, "big", signed=False))
        digest.update(raw)
    return digest.hexdigest()


def perturbation_type_for_index(index: int, chunk_size: int) -> str:
    """Return the effective type for one output index under the validated policy."""
    within = index % chunk_size
    half = chunk_size // 2
    return "space" if within < half else "newline"


def stable_shard(code_unit_sha: str, data_shards: int) -> int:
    if len(code_unit_sha) != 64:
        raise ValueError(f"Invalid SHA-256 value: {code_unit_sha!r}")
    return int(code_unit_sha[:16], 16) % data_shards


def load_unique_units(
    manifest_path: Path,
    data_shards: int,
    window_size: int,
    chunksize: int,
) -> tuple[list[UniqueUnit], int]:
    """Stream the A05 manifest and build a globally deduplicated primary-unit table."""
    header = pd.read_csv(manifest_path, nrows=0)
    require_columns(header.columns, REQUIRED_MANIFEST_COLUMNS, "A05 code-unit manifest")

    units: dict[str, UniqueUnit] = {}
    primary_occurrences = 0
    usecols = sorted(REQUIRED_MANIFEST_COLUMNS)

    for chunk in pd.read_csv(manifest_path, usecols=usecols, chunksize=chunksize, low_memory=False):
        primary = chunk.loc[chunk["aggregation_role"].astype(str).eq(PRIMARY_ROLE)].copy()
        if primary.empty:
            continue
        primary_occurrences += len(primary)
        for row in primary.itertuples(index=False):
            code_type = str(getattr(row, "code_unit_type"))
            if code_type not in GROUP_BY_TYPE:
                raise ValueError(f"Unexpected primary code_unit_type: {code_type!r}")
            sha = str(getattr(row, "code_unit_sha256"))
            rel = str(getattr(row, "code_unit_relative_path"))
            tokens = int(getattr(row, "space_by_token_count"))
            if tokens < 1:
                raise ValueError(f"Primary unit has non-positive space_by_token_count: {sha}")
            group = GROUP_BY_TYPE[code_type]
            existing = units.get(sha)
            if existing is None:
                units[sha] = UniqueUnit(
                    code_unit_sha256=sha,
                    code_unit_relative_path=rel,
                    space_by_token_count=tokens,
                    code_unit_types={code_type},
                    unit_groups={group},
                    occurrence_count=1,
                )
            else:
                if existing.code_unit_relative_path != rel:
                    raise ValueError(
                        f"SHA {sha} maps to multiple artifact paths: "
                        f"{existing.code_unit_relative_path!r} vs {rel!r}"
                    )
                if existing.space_by_token_count != tokens:
                    raise ValueError(
                        f"SHA {sha} maps to inconsistent token counts: "
                        f"{existing.space_by_token_count} vs {tokens}"
                    )
                existing.code_unit_types.add(code_type)
                existing.unit_groups.add(group)
                existing.occurrence_count += 1

    result = list(units.values())
    for unit in result:
        unit.logical_shard = stable_shard(unit.code_unit_sha256, data_shards)
        unit.expected_windows = expected_window_count(unit.space_by_token_count, window_size)
    result.sort(key=lambda item: item.code_unit_sha256)
    return result, primary_occurrences


def unit_priority(unit: UniqueUnit) -> tuple[int, str]:
    first_group = min((GROUP_ORDER[group] for group in unit.unit_groups), default=99)
    return first_group, unit.code_unit_sha256


def plan_frames(
    units: list[UniqueUnit],
    data_shards: int,
    num_workers: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for unit in units:
        rows.append(
            {
                "code_unit_sha256": unit.code_unit_sha256,
                "code_unit_relative_path": unit.code_unit_relative_path,
                "space_by_token_count": unit.space_by_token_count,
                "expected_windows": unit.expected_windows,
                "occurrence_count": unit.occurrence_count,
                "code_unit_types": ",".join(sorted(unit.code_unit_types)),
                "unit_groups": ",".join(sorted(unit.unit_groups, key=lambda value: GROUP_ORDER[value])),
                "logical_shard": unit.logical_shard,
            }
        )
    unit_frame = pd.DataFrame(rows)

    shard_rows: list[dict[str, Any]] = []
    for shard_id in range(data_shards):
        subset = unit_frame.loc[unit_frame["logical_shard"].eq(shard_id)]
        groups = defaultdict(int)
        for value in subset["unit_groups"].astype(str):
            for group in value.split(","):
                if group:
                    groups[group] += 1
        shard_rows.append(
            {
                "logical_shard": shard_id,
                "unique_units": int(len(subset)),
                "expected_windows": int(subset["expected_windows"].sum()) if not subset.empty else 0,
                "space_by_tokens": int(subset["space_by_token_count"].sum()) if not subset.empty else 0,
                "fun_membership_units": int(groups["FUN"]),
                "c_fun_membership_units": int(groups["C_FUN"]),
                "block_membership_units": int(groups["BLOCK"]),
                "prep_worker_index": shard_id % num_workers,
                "future_gpu_index_mod3": shard_id % 3,
            }
        )
    return unit_frame, pd.DataFrame(shard_rows)


def build_config_payload(args: argparse.Namespace, manifest_sha: str, source_hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "script_version": SCRIPT_VERSION,
        "window_policy": WINDOW_POLICY,
        "window_size_space_by_tokens": args.window_size,
        "perturbation_policy": PERTURBATION_POLICY,
        "perturbations_per_window": args.perturbations_per_window,
        "perturbation_type": args.perturbation_type,
        "random_seed": args.random_seed,
        "pct_words_masked": args.pct_words_masked,
        "span_length": args.span_length,
        "perturbation_chunk_size": args.perturbation_chunk_size,
        "n_perturbation_rounds": args.n_perturbation_rounds,
        "data_shards": args.data_shards,
        "input_manifest_sha256": manifest_sha,
        "reference_source_hashes": source_hashes,
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "python_version": platform.python_version(),
        "intended_scoring_model": args.scoring_model,
        "intended_scoring_model_revision": args.scoring_model_revision,
        "classification_enabled": False,
        "npr_scoring_enabled": False,
    }


def read_code_unit_text(unit: UniqueUnit, artifact_base: Path) -> str:
    path = artifact_base / unit.code_unit_relative_path
    if not path.is_file():
        raise FileNotFoundError(f"Missing code-unit artifact: {path}")
    raw = path.read_bytes()
    observed = sha256_bytes(raw)
    if observed != unit.code_unit_sha256:
        raise ValueError(
            f"Code-unit artifact SHA mismatch for {path}: observed={observed}, expected={unit.code_unit_sha256}"
        )
    return raw.decode("utf-8")


def generate_window_record(
    unit: UniqueUnit,
    window: RawWindow,
    args: argparse.Namespace,
    config_fingerprint: str,
) -> dict[str, Any]:
    seed = derive_window_seed(args.random_seed, unit.code_unit_sha256, window.index)
    set_perturbation_seeds(seed)
    perturbations = perturb_texts_reference_compatible(
        [window.text for _ in range(args.perturbations_per_window)],
        pct_words_masked=args.pct_words_masked,
        span_length=args.span_length,
        perturbation_chunk_size=args.perturbation_chunk_size,
        n_perturbation_rounds=args.n_perturbation_rounds,
        perturbation_type=args.perturbation_type,
    )
    if len(perturbations) != args.perturbations_per_window:
        raise AssertionError(
            f"Perturbation count mismatch: observed={len(perturbations)}, "
            f"expected={args.perturbations_per_window}"
        )

    return {
        "code_unit_sha256": unit.code_unit_sha256,
        "code_unit_relative_path": unit.code_unit_relative_path,
        "code_unit_types": sorted(unit.code_unit_types),
        "unit_groups": sorted(unit.unit_groups, key=lambda value: GROUP_ORDER[value]),
        "space_by_tokens_total": unit.space_by_token_count,
        "window_index": window.index,
        "window_space_by_start": window.start_token,
        "window_space_by_end": window.end_token,
        "window_space_by_token_count": window.token_count,
        "window_marginal_space_by_token_count": window.marginal_token_count,
        "overlaps_previous_window": window.overlaps_previous_window,
        "raw_char_start": window.char_start,
        "raw_char_end": window.char_end,
        "window_text_sha256": sha256_bytes(window.text.encode("utf-8")),
        "window_seed": seed,
        "original_text": window.text,
        "perturbation_count": len(perturbations),
        "perturbations_ordered_sha256": ordered_text_digest(perturbations),
        "perturbations": perturbations,
        "config_fingerprint": config_fingerprint,
    }


def write_deterministic_gzip_jsonl(
    output_path: Path,
    records: Iterable[dict[str, Any]],
    gzip_level: int,
) -> tuple[int, int, str]:
    """Write canonical JSONL into deterministic gzip and return rows, raw bytes, content SHA."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    row_count = 0
    raw_bytes = 0
    content_digest = hashlib.sha256()

    with tmp.open("wb") as raw_stream:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_stream,
            compresslevel=gzip_level,
            mtime=0,
        ) as gz_stream:
            with io.TextIOWrapper(gz_stream, encoding="utf-8", newline="\n") as text_stream:
                for record in records:
                    line = json.dumps(
                        record,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                        allow_nan=False,
                    ) + "\n"
                    encoded = line.encode("utf-8")
                    content_digest.update(encoded)
                    raw_bytes += len(encoded)
                    row_count += 1
                    text_stream.write(line)
    os.replace(tmp, output_path)
    return row_count, raw_bytes, content_digest.hexdigest()


def shard_file_name(shard_id: int, data_shards: int) -> str:
    return f"shard-{shard_id:03d}-of-{data_shards:03d}.jsonl.gz"


def shard_summary_name(shard_id: int, data_shards: int) -> str:
    return f"shard-{shard_id:03d}-of-{data_shards:03d}.summary.json"


def validate_reusable_shard(
    shard_path: Path,
    summary_path: Path,
    config_fingerprint: str,
    manifest_sha: str,
) -> dict[str, Any] | None:
    if not shard_path.is_file() or not summary_path.is_file():
        return None
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if summary.get("config_fingerprint") != config_fingerprint:
        return None
    if summary.get("input_manifest_sha256") != manifest_sha:
        return None
    if summary.get("gzip_sha256") != sha256_file(shard_path):
        return None
    if summary.get("status") != "PASS":
        return None
    return summary


def process_one_shard(
    shard_id: int,
    units: list[UniqueUnit],
    args_dict: dict[str, Any],
    config_fingerprint: str,
    manifest_sha: str,
) -> dict[str, Any]:
    """Process one logical shard. This function is multiprocessing-safe."""
    args = SimpleNamespace(**args_dict)
    artifact_base = Path(args.artifact_base)
    shard_root = Path(args.output_root) / "shards"
    shard_path = shard_root / shard_file_name(shard_id, args.data_shards)
    summary_path = shard_root / shard_summary_name(shard_id, args.data_shards)

    if not args.overwrite:
        reusable = validate_reusable_shard(
            shard_path,
            summary_path,
            config_fingerprint,
            manifest_sha,
        )
        if reusable is not None:
            result = dict(reusable)
            result["reused"] = True
            return result
    elif shard_path.exists():
        shard_path.unlink()
    if args.overwrite and summary_path.exists():
        summary_path.unlink()

    selected = sorted(units, key=unit_priority)
    if args.max_units_per_shard is not None:
        selected = selected[: args.max_units_per_shard]

    started = time.perf_counter()
    unit_count = 0
    window_count = 0
    perturbation_count = 0
    artifact_bytes = 0

    def iter_records() -> Iterable[dict[str, Any]]:
        nonlocal unit_count, window_count, perturbation_count, artifact_bytes
        for unit in selected:
            text = read_code_unit_text(unit, artifact_base)
            artifact_bytes += len(text.encode("utf-8"))
            if len(text.split(" ")) != unit.space_by_token_count:
                raise ValueError(
                    f"space_by_token_count mismatch for {unit.code_unit_sha256}: "
                    f"artifact={len(text.split(' '))}, manifest={unit.space_by_token_count}"
                )
            windows = build_raw_windows(text, args.window_size)
            if len(windows) != unit.expected_windows:
                raise AssertionError(
                    f"Window-count mismatch for {unit.code_unit_sha256}: "
                    f"observed={len(windows)}, expected={unit.expected_windows}"
                )
            unit_count += 1
            for window in windows:
                record = generate_window_record(unit, window, args, config_fingerprint)
                window_count += 1
                perturbation_count += int(record["perturbation_count"])
                yield record

    row_count, raw_jsonl_bytes, content_sha = write_deterministic_gzip_jsonl(
        shard_path,
        iter_records(),
        args.gzip_level,
    )
    if row_count != window_count:
        raise AssertionError(f"JSONL row count {row_count} != window count {window_count}")

    elapsed = time.perf_counter() - started
    summary = {
        "status": "PASS",
        "script_version": SCRIPT_VERSION,
        "logical_shard": shard_id,
        "data_shards": args.data_shards,
        "prep_worker_index": shard_id % args.num_workers,
        "unique_units": unit_count,
        "windows": window_count,
        "perturbations": perturbation_count,
        "artifact_input_bytes": artifact_bytes,
        "canonical_jsonl_bytes": raw_jsonl_bytes,
        "gzip_bytes": shard_path.stat().st_size,
        "canonical_jsonl_sha256": content_sha,
        "gzip_sha256": sha256_file(shard_path),
        "input_manifest_sha256": manifest_sha,
        "config_fingerprint": config_fingerprint,
        "elapsed_seconds": elapsed,
        "windows_per_second": window_count / elapsed if elapsed > 0 else None,
        "reused": False,
        "completed_utc": utc_now(),
    }
    atomic_json(summary, summary_path)
    return summary


def compare_with_reference_main(args: argparse.Namespace, text: str, seed: int) -> dict[str, Any]:
    """Hard-check copied perturbation logic against the project's main.py implementation."""
    # Load exactly the reference file requested by --reference-main instead of
    # assuming that main.py lives at the repository root. In this project the
    # DetectCodeGPT reference implementation is stored under code-detection/.
    reference_path = args.reference_main.resolve()
    module_name = f"a09_reference_main_{sha256_file(reference_path)[:12]}"
    spec = importlib.util.spec_from_file_location(module_name, reference_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load reference main.py from {reference_path}")
    detector_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(detector_main)

    detector_args = SimpleNamespace(
        span_length=args.span_length,
        pct_words_masked=args.pct_words_masked,
        perturb_type=args.perturbation_type,
        chunk_size=args.perturbation_chunk_size,
        mask_filling_model_name="Salesforce/codet5p-770m",
        n_perturbation_rounds=args.n_perturbation_rounds,
    )

    set_perturbation_seeds(seed)
    ours = perturb_texts_reference_compatible(
        [text for _ in range(args.perturbations_per_window)],
        pct_words_masked=args.pct_words_masked,
        span_length=args.span_length,
        perturbation_chunk_size=args.perturbation_chunk_size,
        n_perturbation_rounds=args.n_perturbation_rounds,
        perturbation_type=args.perturbation_type,
    )
    set_perturbation_seeds(seed)
    theirs = detector_main.perturb_texts(
        [text for _ in range(args.perturbations_per_window)],
        detector_args,
        {},
    )
    return {
        "exact_match": ours == theirs,
        "ours_ordered_sha256": ordered_text_digest(ours),
        "reference_ordered_sha256": ordered_text_digest(theirs),
        "count": len(ours),
    }


def run_self_test() -> None:
    cases = [
        ("a b c", 2, [(0, 2, 2, 2), (1, 3, 2, 1)]),
        ("line1\nline2  z", 2, [(0, 2, 2, 2), (1, 3, 2, 1)]),
    ]
    for text, size, expected in cases:
        windows = build_raw_windows(text, size)
        observed = [
            (window.start_token, window.end_token, window.token_count, window.marginal_token_count)
            for window in windows
        ]
        if observed != expected:
            raise AssertionError(f"Window self-test failed: {observed} != {expected}")
        for window in windows:
            if window.text != text[window.char_start : window.char_end]:
                raise AssertionError("Raw window text is not a direct source slice.")

    sample = "def f():\n    x = 1\n    return x"
    set_perturbation_seeds(123456)
    first = perturb_texts_reference_compatible(
        [sample] * 50,
        pct_words_masked=0.5,
        span_length=2,
        perturbation_chunk_size=10,
        n_perturbation_rounds=1,
        perturbation_type="random-insert-space+newline",
    )
    set_perturbation_seeds(123456)
    second = perturb_texts_reference_compatible(
        [sample] * 50,
        pct_words_masked=0.5,
        span_length=2,
        perturbation_chunk_size=10,
        n_perturbation_rounds=1,
        perturbation_type="random-insert-space+newline",
    )
    if first != second or len(first) != 50:
        raise AssertionError("Deterministic perturbation self-test failed.")
    if sum(perturbation_type_for_index(i, 10) == "space" for i in range(50)) != 25:
        raise AssertionError("Expected 25 space perturbations under chunk_size=10.")
    if sum(perturbation_type_for_index(i, 10) == "newline" for i in range(50)) != 25:
        raise AssertionError("Expected 25 newline perturbations under chunk_size=10.")
    print("prepare_snapshot_npr_perturbations self-test: PASS")


def build_verification_sample(
    units: list[UniqueUnit],
    artifact_base: Path,
    args: argparse.Namespace,
    config_fingerprint: str,
) -> pd.DataFrame:
    """Generate a deterministic shared sample that must match across both servers."""
    rows: list[dict[str, Any]] = []
    for unit in sorted(units, key=lambda item: item.code_unit_sha256):
        text = read_code_unit_text(unit, artifact_base)
        windows = build_raw_windows(text, args.window_size)
        for window in windows:
            seed = derive_window_seed(args.random_seed, unit.code_unit_sha256, window.index)
            set_perturbation_seeds(seed)
            perturbations = perturb_texts_reference_compatible(
                [window.text for _ in range(args.perturbations_per_window)],
                pct_words_masked=args.pct_words_masked,
                span_length=args.span_length,
                perturbation_chunk_size=args.perturbation_chunk_size,
                n_perturbation_rounds=args.n_perturbation_rounds,
                perturbation_type=args.perturbation_type,
            )
            reference = compare_with_reference_main(args, window.text, seed)
            rows.append(
                {
                    "code_unit_sha256": unit.code_unit_sha256,
                    "window_index": window.index,
                    "window_text_sha256": sha256_bytes(window.text.encode("utf-8")),
                    "window_seed": seed,
                    "unit_groups": ",".join(sorted(unit.unit_groups, key=lambda value: GROUP_ORDER[value])),
                    "perturbation_count": len(perturbations),
                    "perturbations_ordered_sha256": ordered_text_digest(perturbations),
                    "first_perturbation_sha256": sha256_bytes(perturbations[0].encode("utf-8")),
                    "last_perturbation_sha256": sha256_bytes(perturbations[-1].encode("utf-8")),
                    "reference_main_exact_match": bool(reference["exact_match"]),
                    "config_fingerprint": config_fingerprint,
                }
            )
            if len(rows) >= args.verify_windows:
                return pd.DataFrame(rows)
    return pd.DataFrame(rows)


def build_checks(
    args: argparse.Namespace,
    manifest_sha: str,
    units: list[UniqueUnit],
    primary_occurrences: int,
    total_windows: int,
) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, observed: Any, expected: Any, note: str = "") -> None:
        checks.append(
            {
                "check_name": name,
                "passed": bool(passed),
                "observed": observed,
                "expected": expected,
                "note": note,
            }
        )

    if args.expected_input_sha256:
        add(
            "input_manifest_sha256",
            manifest_sha == args.expected_input_sha256,
            manifest_sha,
            args.expected_input_sha256,
        )
    if args.expected_primary_occurrences is not None:
        add(
            "primary_occurrences",
            primary_occurrences == args.expected_primary_occurrences,
            primary_occurrences,
            args.expected_primary_occurrences,
        )
    if args.expected_unique_units is not None:
        add(
            "unique_primary_units",
            len(units) == args.expected_unique_units,
            len(units),
            args.expected_unique_units,
        )
    if args.expected_windows is not None:
        add(
            "expected_unique_windows",
            total_windows == args.expected_windows,
            total_windows,
            args.expected_windows,
        )
    add(
        "all_primary_types_recognized",
        all(unit.code_unit_types <= set(GROUP_BY_TYPE) for unit in units),
        int(sum(not unit.code_unit_types <= set(GROUP_BY_TYPE) for unit in units)),
        0,
    )
    add(
        "all_units_have_group_membership",
        all(bool(unit.unit_groups) for unit in units),
        int(sum(not unit.unit_groups for unit in units)),
        0,
    )
    add(
        "logical_shard_range",
        all(0 <= unit.logical_shard < args.data_shards for unit in units),
        int(sum(not (0 <= unit.logical_shard < args.data_shards) for unit in units)),
        0,
    )
    add(
        "data_shards_divisible_by_two_and_three",
        args.data_shards % 2 == 0 and args.data_shards % 3 == 0,
        args.data_shards,
        "multiple of 6",
        "This supports even two-server preparation and three-GPU scoring assignment.",
    )
    return pd.DataFrame(checks, columns=CHECK_COLUMNS)


def prepare_plan_outputs(
    args: argparse.Namespace,
    unit_frame: pd.DataFrame,
    shard_frame: pd.DataFrame,
    checks: pd.DataFrame,
    manifest_sha: str,
    primary_occurrences: int,
    config_fingerprint: str,
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    plan_dir = args.output_root / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    atomic_csv(unit_frame, plan_dir / "unique_primary_units.csv")
    atomic_csv(shard_frame, plan_dir / "logical_shard_plan.csv")
    atomic_csv(checks, plan_dir / "checks.csv", CHECK_COLUMNS)

    failed = checks.loc[~checks["passed"].astype(bool)]
    group_membership_counts = {
        group: int(unit_frame["unit_groups"].astype(str).str.split(",").map(lambda values: group in values).sum())
        for group in ("FUN", "C_FUN", "BLOCK")
    }
    summary = {
        "status": "PASS" if failed.empty else "FAIL",
        "script_version": SCRIPT_VERSION,
        "input_manifest": str(args.input_manifest.resolve()),
        "input_manifest_sha256": manifest_sha,
        "artifact_base": str(args.artifact_base.resolve()),
        "primary_occurrences": int(primary_occurrences),
        "unique_primary_units": int(len(unit_frame)),
        "expected_unique_windows": int(unit_frame["expected_windows"].sum()),
        "expected_perturbations": int(unit_frame["expected_windows"].sum()) * args.perturbations_per_window,
        "group_membership_unique_units": group_membership_counts,
        "data_shards": args.data_shards,
        "num_prep_workers": args.num_workers,
        "config_fingerprint": config_fingerprint,
        "reference_source_hashes": source_hashes,
        "failed_checks": int(len(failed)),
        "created_utc": utc_now(),
    }
    atomic_json(summary, plan_dir / "summary.json")
    return summary


def run_prepare(
    args: argparse.Namespace,
    units: list[UniqueUnit],
    manifest_sha: str,
    config_fingerprint: str,
) -> dict[str, Any]:
    if args.worker_index < 0 or args.worker_index >= args.num_workers:
        raise ValueError(
            f"worker_index must be in [0, {args.num_workers - 1}], got {args.worker_index}"
        )

    owned_shards = [
        shard_id
        for shard_id in range(args.data_shards)
        if shard_id % args.num_workers == args.worker_index
    ]
    units_by_shard: dict[int, list[UniqueUnit]] = defaultdict(list)
    for unit in units:
        if unit.logical_shard in owned_shards:
            units_by_shard[unit.logical_shard].append(unit)

    args_dict = {
        "artifact_base": str(args.artifact_base),
        "output_root": str(args.output_root),
        "data_shards": args.data_shards,
        "num_workers": args.num_workers,
        "window_size": args.window_size,
        "perturbations_per_window": args.perturbations_per_window,
        "perturbation_type": args.perturbation_type,
        "random_seed": args.random_seed,
        "pct_words_masked": args.pct_words_masked,
        "span_length": args.span_length,
        "perturbation_chunk_size": args.perturbation_chunk_size,
        "n_perturbation_rounds": args.n_perturbation_rounds,
        "gzip_level": args.gzip_level,
        "overwrite": args.overwrite,
        "max_units_per_shard": args.max_units_per_shard,
    }

    started = time.perf_counter()
    results: list[dict[str, Any]] = []

    if args.processes == 1:
        for position, shard_id in enumerate(owned_shards, start=1):
            result = process_one_shard(
                shard_id,
                units_by_shard.get(shard_id, []),
                args_dict,
                config_fingerprint,
                manifest_sha,
            )
            results.append(result)
            print(
                f"A09 prepare progress: shard={position}/{len(owned_shards)} "
                f"logical_shard={shard_id:03d} units={result['unique_units']} "
                f"windows={result['windows']} reused={int(bool(result.get('reused')))}",
                flush=True,
            )
    else:
        from concurrent.futures import ProcessPoolExecutor, as_completed

        with ProcessPoolExecutor(max_workers=args.processes) as executor:
            futures = {
                executor.submit(
                    process_one_shard,
                    shard_id,
                    units_by_shard.get(shard_id, []),
                    args_dict,
                    config_fingerprint,
                    manifest_sha,
                ): shard_id
                for shard_id in owned_shards
            }
            completed = 0
            for future in as_completed(futures):
                shard_id = futures[future]
                result = future.result()
                results.append(result)
                completed += 1
                print(
                    f"A09 prepare progress: shard={completed}/{len(owned_shards)} "
                    f"logical_shard={shard_id:03d} units={result['unique_units']} "
                    f"windows={result['windows']} reused={int(bool(result.get('reused')))}",
                    flush=True,
                )

    results.sort(key=lambda row: int(row["logical_shard"]))
    elapsed = time.perf_counter() - started
    worker_dir = args.output_root / "workers" / args.worker_label
    worker_dir.mkdir(parents=True, exist_ok=True)
    result_frame = pd.DataFrame(results)
    atomic_csv(result_frame, worker_dir / "prepared_shards.csv")

    summary = {
        "status": "PASS",
        "script_version": SCRIPT_VERSION,
        "worker_label": args.worker_label,
        "worker_index": args.worker_index,
        "num_workers": args.num_workers,
        "owned_logical_shards": owned_shards,
        "completed_shards": int(len(results)),
        "reused_shards": int(sum(bool(row.get("reused")) for row in results)),
        "unique_units": int(sum(int(row["unique_units"]) for row in results)),
        "windows": int(sum(int(row["windows"]) for row in results)),
        "perturbations": int(sum(int(row["perturbations"]) for row in results)),
        "gzip_bytes": int(sum(int(row["gzip_bytes"]) for row in results)),
        "elapsed_seconds": elapsed,
        "windows_per_second": (
            sum(int(row["windows"]) for row in results) / elapsed if elapsed > 0 else None
        ),
        "input_manifest_sha256": manifest_sha,
        "config_fingerprint": config_fingerprint,
        "processes": args.processes,
        "max_units_per_shard": args.max_units_per_shard,
        "completed_utc": utc_now(),
    }
    atomic_json(summary, worker_dir / "worker_summary.json")
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "verify", "prepare"), default="verify")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--input-manifest",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a05/python_code_unit_manifest.csv"),
    )
    parser.add_argument(
        "--artifact-base",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a05"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a09"),
    )
    parser.add_argument("--worker-label", default=platform.node().split(".")[0])
    parser.add_argument("--worker-index", type=int, default=0)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--data-shards", type=int, default=96)
    parser.add_argument("--processes", type=int, default=8)
    parser.add_argument("--manifest-chunksize", type=int, default=100000)
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--perturbations-per-window", type=int, default=50)
    parser.add_argument("--perturbation-type", default="random-insert-space+newline")
    parser.add_argument("--random-seed", type=int, default=20260723)
    parser.add_argument("--pct-words-masked", type=float, default=0.5)
    parser.add_argument("--span-length", type=int, default=2)
    parser.add_argument("--perturbation-chunk-size", type=int, default=10)
    parser.add_argument("--n-perturbation-rounds", type=int, default=1)
    parser.add_argument("--gzip-level", type=int, default=3)
    parser.add_argument("--verify-windows", type=int, default=8)
    parser.add_argument("--max-units-per-shard", type=parse_optional_int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--expected-input-sha256",
        default="1acb3726f5c62e6154672f1aff592973c65a13e58dbfd37f8058560d1a474e6c",
    )
    parser.add_argument("--expected-primary-occurrences", type=int, default=3480000)
    parser.add_argument("--expected-unique-units", type=int, default=419220)
    parser.add_argument("--expected-windows", type=int, default=1113866)
    parser.add_argument(
        "--reference-main",
        type=Path,
        default=Path("code-detection/main.py"),
        help=(
            "Original DetectCodeGPT main.py used only by MODE=verify to hard-check "
            "the copied perturbation logic. MODE=plan/prepare do not require it."
        ),
    )
    parser.add_argument(
        "--reference-a02-script",
        type=Path,
        default=Path("code-detection/score_snapshot_npr.py"),
    )
    parser.add_argument("--scoring-model", default="bigcode/starcoder2-7b")
    parser.add_argument(
        "--scoring-model-revision",
        default="bb9afde76d7945da5745592525db122d4d729eb1",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0

    if args.data_shards < 1:
        parser.error("--data-shards must be positive")
    if args.num_workers < 1:
        parser.error("--num-workers must be positive")
    if args.processes < 1:
        parser.error("--processes must be positive")
    if not (0 <= args.gzip_level <= 9):
        parser.error("--gzip-level must be in [0, 9]")
    if args.perturbations_per_window != 50:
        parser.error("A09 v2 freezes --perturbations-per-window at 50")
    if args.perturbation_chunk_size != 10:
        parser.error("A09 v2 freezes --perturbation-chunk-size at 10")
    if args.n_perturbation_rounds != 1:
        parser.error("A09 v2 freezes --n-perturbation-rounds at 1")
    if args.window_size != 128:
        parser.error("A09 v2 freezes --window-size at 128")
    if args.data_shards % 6 != 0:
        parser.error("--data-shards must be divisible by 6 for 2-server prep and 3-GPU scoring")

    args.project_root = args.project_root.resolve()
    args.input_manifest = (args.project_root / args.input_manifest).resolve() if not args.input_manifest.is_absolute() else args.input_manifest.resolve()
    args.artifact_base = (args.project_root / args.artifact_base).resolve() if not args.artifact_base.is_absolute() else args.artifact_base.resolve()
    args.output_root = (args.project_root / args.output_root).resolve() if not args.output_root.is_absolute() else args.output_root.resolve()
    args.reference_main = (args.project_root / args.reference_main).resolve() if not args.reference_main.is_absolute() else args.reference_main.resolve()
    args.reference_a02_script = (args.project_root / args.reference_a02_script).resolve() if not args.reference_a02_script.is_absolute() else args.reference_a02_script.resolve()

    if not args.input_manifest.is_file():
        raise FileNotFoundError(f"Missing A05 manifest: {args.input_manifest}")
    if not args.artifact_base.is_dir():
        raise FileNotFoundError(f"Missing A05 artifact base: {args.artifact_base}")
    if args.mode == "verify" and not args.reference_main.is_file():
        raise FileNotFoundError(f"Verification requires project main.py: {args.reference_main}")

    manifest_sha = sha256_file(args.input_manifest)
    # The reference main.py is a verification oracle only. Excluding its local
    # presence from plan/prepare fingerprints keeps two-server production
    # fingerprints identical after compatibility has already been verified.
    source_hashes = {
        "main.py": (
            sha256_file(args.reference_main)
            if args.mode == "verify" and args.reference_main.is_file()
            else "verification-only"
        ),
        "score_snapshot_npr.py": (
            sha256_file(args.reference_a02_script) if args.reference_a02_script.is_file() else "missing"
        ),
    }
    config_payload = build_config_payload(args, manifest_sha, source_hashes)
    config_fingerprint = stable_json_hash(config_payload)

    print("=" * 80)
    print("run-x-a09-v2: deterministic two-server NPR perturbation preparation")
    print(f"Mode:                            {args.mode}")
    print(f"Project root:                    {args.project_root}")
    print(f"Input manifest:                  {args.input_manifest}")
    print(f"Input manifest SHA256:           {manifest_sha}")
    print(f"Artifact base:                   {args.artifact_base}")
    print(f"Output root:                     {args.output_root}")
    print(f"Worker label/index:              {args.worker_label}/{args.worker_index}")
    print(f"Preparation workers:             {args.num_workers}")
    print(f"Logical data shards:             {args.data_shards}")
    print(f"Processes:                       {args.processes}")
    print(f"Window size:                     {args.window_size}")
    print(f"Perturbations/window:            {args.perturbations_per_window}")
    print(f"Perturbation type:               {args.perturbation_type}")
    print(f"Random seed:                     {args.random_seed}")
    print(f"NumPy/SciPy:                     {np.__version__}/{scipy.__version__}")
    print(f"Intended scoring model revision: {args.scoring_model_revision}")
    print(f"Config fingerprint:              {config_fingerprint}")
    print("Model loading:                    disabled")
    print("NPR scoring:                      disabled")
    print("Classification:                   disabled")
    print("=" * 80)

    started = time.perf_counter()
    units, primary_occurrences = load_unique_units(
        args.input_manifest,
        data_shards=args.data_shards,
        window_size=args.window_size,
        chunksize=args.manifest_chunksize,
    )
    total_windows = sum(unit.expected_windows for unit in units)
    unit_frame, shard_frame = plan_frames(units, args.data_shards, args.num_workers)
    checks = build_checks(
        args,
        manifest_sha,
        units,
        primary_occurrences,
        total_windows,
    )
    plan_summary = prepare_plan_outputs(
        args,
        unit_frame,
        shard_frame,
        checks,
        manifest_sha,
        primary_occurrences,
        config_fingerprint,
        source_hashes,
    )

    if plan_summary["status"] != "PASS":
        failed = checks.loc[~checks["passed"].astype(bool)]
        print(failed.to_string(index=False))
        raise RuntimeError("A09 plan checks failed; refusing perturbation generation.")

    print(
        f"A09 plan PASS: primary_occurrences={primary_occurrences}; "
        f"unique_units={len(units)}; windows={total_windows}; "
        f"perturbations={total_windows * args.perturbations_per_window}",
        flush=True,
    )

    if args.mode == "plan":
        print(f"Plan completed in {time.perf_counter() - started:.3f}s")
        return 0

    if args.mode == "verify":
        verify_frame = build_verification_sample(
            units,
            args.artifact_base,
            args,
            config_fingerprint,
        )
        if len(verify_frame) != args.verify_windows:
            raise RuntimeError(
                f"Could build only {len(verify_frame)}/{args.verify_windows} verification windows."
            )
        if not verify_frame["reference_main_exact_match"].astype(bool).all():
            raise RuntimeError("Copied perturbation logic differs from project main.py on verification sample.")

        worker_dir = args.output_root / "workers" / args.worker_label
        worker_dir.mkdir(parents=True, exist_ok=True)
        verify_path = worker_dir / "verification_perturbation_digests.csv"
        atomic_csv(verify_frame, verify_path)
        overall_digest = stable_json_hash(
            verify_frame[
                [
                    "code_unit_sha256",
                    "window_index",
                    "window_text_sha256",
                    "window_seed",
                    "perturbations_ordered_sha256",
                ]
            ].to_dict(orient="records")
        )
        verify_summary = {
            "status": "PASS",
            "worker_label": args.worker_label,
            "verification_windows": len(verify_frame),
            "all_reference_main_exact": True,
            "verification_overall_sha256": overall_digest,
            "input_manifest_sha256": manifest_sha,
            "config_fingerprint": config_fingerprint,
            "elapsed_seconds": time.perf_counter() - started,
            "completed_utc": utc_now(),
        }
        atomic_json(verify_summary, worker_dir / "verification_summary.json")
        print("=" * 80)
        print("run-x-a09 verification")
        print("Status:                          PASS")
        print(f"Verification windows:            {len(verify_frame)}")
        print("Reference main.py exact match:   1")
        print(f"Verification overall SHA256:     {overall_digest}")
        print(f"Output:                          {verify_path}")
        print("=" * 80)
        return 0

    summary = run_prepare(args, units, manifest_sha, config_fingerprint)
    print("=" * 80)
    print("run-x-a09 perturbation preparation")
    print(f"Status:                          {summary['status']}")
    print(f"Worker:                          {summary['worker_label']} ({summary['worker_index']}/{summary['num_workers']})")
    print(f"Completed logical shards:        {summary['completed_shards']}")
    print(f"Reused logical shards:           {summary['reused_shards']}")
    print(f"Unique units prepared:           {summary['unique_units']}")
    print(f"Windows prepared:                {summary['windows']}")
    print(f"Perturbations prepared:          {summary['perturbations']}")
    print(f"Compressed bytes:                {summary['gzip_bytes']}")
    print(f"Elapsed seconds:                 {summary['elapsed_seconds']:.3f}")
    print(f"Windows/second:                  {summary['windows_per_second']:.6f}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
