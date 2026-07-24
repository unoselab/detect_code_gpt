#!/usr/bin/env python3
"""Shared overlap-window NPR logic for mixed-code and repository experiments."""
from __future__ import annotations

import hashlib
import math
import random
from typing import Any

import numpy as np

ALGORITHM_VERSION = "overlap_final_full_window_valid_frontier_weighting-v1"
PARTIAL_BODY_POLICY = "any_valid_window_partial_success_full_windows-v2"


def stable_sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_window_seed(global_seed: int, body_sha: str, chunk_index: int) -> int:
    digest = hashlib.sha256(f"{global_seed}|{body_sha}|{chunk_index}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big", signed=False)


def set_all_seeds(seed: int, torch_module: Any | None = None) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch_module is not None:
        torch_module.manual_seed(seed)
        if torch_module.cuda.is_available():
            torch_module.cuda.manual_seed_all(seed)


def chunk_literal_space(text: str, window_size: int) -> list[tuple[str, int, int, int]]:
    """Return full-size final-overlap windows using literal-space tokenization."""
    tokens = text.split(" ")
    total_tokens = len(tokens)
    if total_tokens <= window_size:
        return [(text, total_tokens, 0, total_tokens)]

    chunks: list[tuple[str, int, int, int]] = []
    start = 0
    while start < total_tokens:
        end = min(start + window_size, total_tokens)
        if end - start < window_size and chunks:
            start = end - window_size
        selected = tokens[start:end]
        chunks.append((" ".join(selected), len(selected), start, end))
        if end >= total_tokens:
            break
        start = end
    return chunks


def compute_marginal_token_counts(
    chunks: list[tuple[str, int, int, int]],
) -> list[int]:
    counts: list[int] = []
    frontier = 0
    for _, _, start, end in chunks:
        counts.append(max(0, end - max(start, frontier)))
        frontier = max(frontier, end)
    return counts


def classify_window_validity(scored: dict[str, Any]) -> tuple[bool, str | None]:
    npr = float(scored.get("npr", float("nan")))
    if math.isfinite(npr):
        return True, None
    valid_perturbations = int(scored.get("valid_perturbation_scores", 0))
    mean_perturbed = float(scored.get("mean_p_logrank", float("nan")))
    original = float(scored.get("orig_logrank", float("nan")))
    if valid_perturbations == 0:
        return False, "no_valid_perturbation_scores"
    if not math.isfinite(mean_perturbed):
        return False, "nonfinite_mean_perturbed_log_rank"
    if not math.isfinite(original):
        return False, "nonfinite_original_log_rank"
    if original == 0.0:
        return False, "zero_original_log_rank"
    return False, "unknown_invalid_window"


def compute_aggregation_weights(chunks: list[dict[str, Any]]) -> list[int]:
    weights: list[int] = []
    frontier = 0
    for chunk in chunks:
        if not bool(chunk["window_npr_valid"]):
            weights.append(0)
            continue
        start = int(chunk["start_token_body"])
        end = int(chunk["end_token_body"])
        weights.append(max(0, end - max(start, frontier)))
        frontier = max(frontier, end)
    return weights


def aggregate_valid_frontier_weighted(chunks: list[dict[str, Any]]) -> float:
    valid = [
        chunk
        for chunk in chunks
        if math.isfinite(float(chunk["npr"]))
        and int(chunk["aggregation_weight_token_count"]) > 0
    ]
    if not valid:
        return float("nan")
    numerator = sum(
        float(chunk["npr"]) * int(chunk["aggregation_weight_token_count"])
        for chunk in valid
    )
    denominator = sum(int(chunk["aggregation_weight_token_count"]) for chunk in valid)
    return float(numerator / denominator) if denominator else float("nan")


def sanitize_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def sanitize_window_for_json(chunk: dict[str, Any]) -> dict[str, Any]:
    out = dict(chunk)
    for key in ("npr", "orig_logrank", "mean_p_logrank"):
        if key in out:
            out[key] = sanitize_float(out[key])
    return out


def validate_window_accounting(chunks: list[dict[str, Any]], body_tokens: int) -> None:
    marginal = sum(int(chunk["marginal_token_count"]) for chunk in chunks)
    valid_tokens = sum(int(chunk["aggregation_weight_token_count"]) for chunk in chunks)
    if marginal != body_tokens:
        raise RuntimeError(
            f"Marginal token accounting mismatch: observed={marginal}, expected={body_tokens}"
        )
    if not 0 <= valid_tokens <= body_tokens:
        raise RuntimeError(
            f"Aggregation token accounting out of range: {valid_tokens}/{body_tokens}"
        )
    for chunk in chunks:
        if not chunk["window_npr_valid"] and int(chunk["aggregation_weight_token_count"]) != 0:
            raise RuntimeError("Invalid window has nonzero aggregation weight.")
