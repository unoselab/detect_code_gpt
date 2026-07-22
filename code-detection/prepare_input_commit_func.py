#!/usr/bin/env python3
"""Prepare original implementation-body inputs for commit-function NPR scoring.

This program consumes the approved commit-function event manifest produced by
run-py-5a-py312. It does not rediscover change events. Instead, it reconnects
each approved event to the original post-commit Git blob, locates the same
named function under Python 3.12 parser semantics, and extracts the original
implementation body without using ``ast.unparse()`` or source formatting.

The AST is used only for function identity, source boundaries, docstring
identification, and structural-hash validation. Detector inputs are exact raw
source slices decoded with the source file's declared Python encoding. Original
spaces, indentation, line breaks, comments inside the scored implementation,
and repeated literal spaces are preserved.

Primary outputs
---------------
- commit_function_detectcodegpt_input_events.csv
- commit_function_detectcodegpt_unique_bodies.csv
- commit_function_detectcodegpt_blob_audit.csv
- commit_function_detectcodegpt_repo_month_audit.csv
- function_bodies/<sha-prefix>/<sha256>.txt

QC outputs
----------
- commit_function_detectcodegpt_exclusions.csv
- commit_function_detectcodegpt_checks.csv
- commit_function_detectcodegpt_summary.json
- commit_function_detectcodegpt_metadata.json

The statistical unit remains one commit-function change event. Identical
implementation bodies are stored once and may later be scored once, but every
original event remains in the event-level output.
"""

from __future__ import annotations

import argparse
import ast
import copy
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Sequence

import pandas as pd


FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
EVENT_ID_RE = re.compile(r"^[0-9a-fA-F]{24,64}$")

REQUIRED_COLUMNS = [
    "function_event_id",
    "dataset_source",
    "repo_name",
    "time",
    "commit",
    "parent_commit",
    "commit_order",
    "relative_path",
    "qualified_function_name",
    "function_name",
    "function_kind",
    "occurrence_index",
    "change_type",
    "start_line",
    "end_line",
]

OPTIONAL_MANIFEST_COLUMNS = [
    "parent_relative_path",
    "diff_status",
    "parent_start_line",
    "parent_end_line",
    "structural_sha256",
    "parent_structural_sha256",
    "function_source_relative_path",
    "content_sha256",
    "source_bytes",
]

EVENT_OUTPUT_COLUMNS = [
    "function_event_id",
    "dataset_source",
    "repo_name",
    "time",
    "commit",
    "parent_commit",
    "commit_order",
    "relative_path",
    "change_type",
    "qualified_function_name",
    "function_name",
    "function_kind",
    "occurrence_index",
    "start_line",
    "end_line",
    "is_nested_function",
    "parent_qualified_function_name",
    "raw_file_blob_sha256",
    "raw_file_bytes",
    "source_encoding",
    "newline_style",
    "raw_function_source_sha256",
    "raw_function_start_line",
    "raw_function_end_line",
    "manifest_structural_sha256",
    "recomputed_structural_sha256",
    "structural_sha256_matches_manifest",
    "leading_docstring_removed",
    "function_body_sha256",
    "function_body_relative_path",
    "function_body_character_count",
    "function_body_utf8_byte_count",
    "function_body_line_count",
    "function_body_split_space_token_count",
    "function_body_nonempty_whitespace_token_count",
    "n_128_token_windows",
    "tail_window_token_count",
    "has_tail_window",
    "has_short_tail_window",
    "contains_nested_function",
    "input_preparation_complete",
    "body_extraction_status",
    "body_exclusion_reason",
]

EXCLUSION_COLUMNS = [
    "function_event_id",
    "dataset_source",
    "repo_name",
    "time",
    "commit",
    "relative_path",
    "qualified_function_name",
    "function_name",
    "function_kind",
    "occurrence_index",
    "start_line",
    "end_line",
    "stage",
    "error_type",
    "error_message",
    "observed_candidate_count",
]

BLOB_AUDIT_COLUMNS = [
    "dataset_source",
    "repo_name",
    "commit",
    "relative_path",
    "repo_dir",
    "event_rows",
    "raw_file_blob_sha256",
    "raw_file_bytes",
    "source_encoding",
    "newline_style",
    "indexed_functions",
    "prepared_events",
    "excluded_events",
    "blob_status",
    "error_stage",
    "error_message",
]

UNIQUE_BODY_COLUMNS = [
    "function_body_sha256",
    "function_body_relative_path",
    "function_body_character_count",
    "function_body_utf8_byte_count",
    "function_body_line_count",
    "function_body_split_space_token_count",
    "function_body_nonempty_whitespace_token_count",
    "n_128_token_windows",
    "tail_window_token_count",
    "has_tail_window",
    "has_short_tail_window",
    "referencing_function_event_count",
    "first_function_event_id",
    "dataset_sources",
    "repositories",
    "first_observed_month",
    "last_observed_month",
]

CHECK_COLUMNS = ["check_name", "passed", "observed", "expected", "note"]


@dataclass(frozen=True)
class FunctionIndexRecord:
    """One named function located in an original source file."""

    qualified_name: str
    function_name: str
    function_kind: str
    occurrence_index: int
    start_line: int
    end_line: int
    structural_sha256: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    parent_qualified_function_name: str
    is_nested_function: bool
    contains_nested_function: bool


@dataclass(frozen=True)
class ExtractedBody:
    """Original source slices and derived detector-input metadata."""

    raw_function_source: str
    body_text: str
    leading_docstring_removed: bool
    function_body_character_count: int
    function_body_utf8_byte_count: int
    function_body_line_count: int
    function_body_split_space_token_count: int
    function_body_nonempty_whitespace_token_count: int
    n_128_token_windows: int
    tail_window_token_count: int
    has_tail_window: bool
    has_short_tail_window: bool


class StageError(RuntimeError):
    """Attach an explicit pipeline stage to an extraction failure."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare original implementation-body inputs for all approved "
            "commit-function change events."
        )
    )
    parser.add_argument(
        "--input-manifest",
        type=Path,
        default=Path(
            "../ai_code_complexity_study_python/ai-code-complexity-study/"
            "repo_python/run-py-5a-py312/strict/"
            "commit_function_detection_manifest.csv"
        ),
    )
    parser.add_argument(
        "--treatment-clone-dir",
        type=Path,
        default=Path("../ai_code_complexity_study_python/treatment-repos"),
    )
    parser.add_argument(
        "--control-clone-dir",
        type=Path,
        default=Path("../ai_code_complexity_study_python/control-repos"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/commit_function/run-1a/strict"),
    )
    parser.add_argument(
        "--qc-dir",
        type=Path,
        default=None,
        help="Defaults to <output-dir>/qc.",
    )
    parser.add_argument("--expected-manifest-rows", type=int, default=450548)
    parser.add_argument("--progress-every-blobs", type=int, default=1000)
    parser.add_argument(
        "--event-id-file",
        type=Path,
        default=None,
        help="Optional newline/CSV file selecting function_event_id values.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=0,
        help="Optional deterministic first-N event limit after event-id filtering.",
    )
    parser.add_argument("--overwrite-output", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--allow-python-before-312",
        action="store_true",
        help="Testing-only override. Production extraction requires Python 3.12+.",
    )
    return parser.parse_args()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def repo_slug(repo_name: str) -> str:
    return repo_name.replace("/", "_")


def safe_relative_python_path(path_text: str) -> bool:
    path = PurePosixPath(path_text)
    return (
        bool(path_text)
        and not path.is_absolute()
        and path.suffix.lower() == ".py"
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


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


def run_git_bytes(repo_dir: Path, args: Iterable[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo_dir), *list(args)],
        capture_output=True,
        check=False,
    )


def read_git_blob(repo_dir: Path, commit: str, relative_path: str) -> bytes:
    result = run_git_bytes(repo_dir, ["show", f"{commit}:{relative_path}"])
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        if not message:
            message = result.stdout.decode("utf-8", errors="replace").strip()
        raise StageError(
            "git_blob_read",
            f"Cannot read {commit}:{relative_path} from {repo_dir}: {message}",
        )
    return result.stdout


def decode_python_source(payload: bytes) -> tuple[str, str]:
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(payload).readline)
        return payload.decode(encoding), encoding
    except Exception as exc:
        raise StageError("source_decode", f"{type(exc).__name__}: {exc}") from exc


def detect_newline_style(payload: bytes) -> str:
    crlf = payload.count(b"\r\n")
    remainder = payload.replace(b"\r\n", b"")
    lf = remainder.count(b"\n")
    cr = remainder.count(b"\r")
    kinds = sum(value > 0 for value in (crlf, lf, cr))
    if kinds == 0:
        return "none"
    if kinds > 1:
        return "mixed"
    if crlf:
        return "CRLF"
    if lf:
        return "LF"
    return "CR"


def resolve_repo_dir(root: Path, repo_name: str) -> Path:
    candidates = [root / repo_slug(repo_name), root / Path(repo_name)]
    existing = [path for path in candidates if path.is_dir()]
    if len(existing) == 1:
        return existing[0]
    if len(existing) > 1:
        resolved = {path.resolve() for path in existing}
        if len(resolved) == 1:
            return existing[0]
        raise StageError(
            "repo_resolution",
            f"Multiple repository directories match {repo_name}: {existing}",
        )
    raise StageError(
        "repo_resolution",
        f"Repository clone not found for {repo_name} under {root}",
    )


def source_start_line(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    decorator_lines = [
        int(decorator.lineno)
        for decorator in node.decorator_list
        if hasattr(decorator, "lineno")
    ]
    return min([int(node.lineno), *decorator_lines])


class NestedDefinitionStripper(ast.NodeTransformer):
    """Remove nested named definitions from an enclosing function fingerprint."""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        return None


def direct_function_fingerprint(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    clone = copy.deepcopy(node)
    stripper = NestedDefinitionStripper()
    clone.body = [
        transformed
        for statement in clone.body
        if (transformed := stripper.visit(statement)) is not None
    ]
    return ast.dump(clone, annotate_fields=True, include_attributes=False)


def function_kind(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    scope_kinds: Sequence[str],
) -> str:
    is_async = isinstance(node, ast.AsyncFunctionDef)
    if scope_kinds and scope_kinds[-1] == "class":
        return "async_method" if is_async else "method"
    if "function" in scope_kinds:
        return "nested_async_function" if is_async else "nested_function"
    return "module_async_function" if is_async else "module_function"


def statement_child_bodies(statement: ast.stmt) -> Iterator[Sequence[ast.stmt]]:
    for field_name in ("body", "orelse", "finalbody"):
        value = getattr(statement, field_name, None)
        if isinstance(value, list) and all(isinstance(item, ast.stmt) for item in value):
            if value:
                yield value
    handlers = getattr(statement, "handlers", None)
    if isinstance(handlers, list):
        for handler in handlers:
            if isinstance(handler, ast.ExceptHandler) and handler.body:
                yield handler.body
    cases = getattr(statement, "cases", None)
    if isinstance(cases, list):
        for case in cases:
            body = getattr(case, "body", None)
            if isinstance(body, list) and body:
                yield body


def contains_nested_named_definition(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return True
    return False


def index_functions(source: str, filename: str) -> list[FunctionIndexRecord]:
    try:
        tree = ast.parse(source, filename=filename, type_comments=True)
    except Exception as exc:
        raise StageError("raw_file_parse", f"{type(exc).__name__}: {exc}") from exc

    occurrence_counts: Counter[str] = Counter()
    records: list[FunctionIndexRecord] = []

    def walk_statements(
        statements: Sequence[ast.stmt],
        scope_names: list[str],
        scope_kinds: list[str],
    ) -> None:
        for statement in statements:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified_name = ".".join([*scope_names, statement.name])
                occurrence_counts[qualified_name] += 1
                occurrence_index = occurrence_counts[qualified_name]
                kind = function_kind(statement, scope_kinds)
                fingerprint = direct_function_fingerprint(statement)
                parent_name = ".".join(scope_names) if scope_names else ""
                records.append(
                    FunctionIndexRecord(
                        qualified_name=qualified_name,
                        function_name=statement.name,
                        function_kind=kind,
                        occurrence_index=occurrence_index,
                        start_line=source_start_line(statement),
                        end_line=int(getattr(statement, "end_lineno", statement.lineno)),
                        structural_sha256=sha256_text(fingerprint),
                        node=statement,
                        parent_qualified_function_name=parent_name,
                        is_nested_function="function" in scope_kinds,
                        contains_nested_function=contains_nested_named_definition(statement),
                    )
                )
                walk_statements(
                    statement.body,
                    [*scope_names, statement.name],
                    [*scope_kinds, "function"],
                )
            elif isinstance(statement, ast.ClassDef):
                walk_statements(
                    statement.body,
                    [*scope_names, statement.name],
                    [*scope_kinds, "class"],
                )
            else:
                for child_body in statement_child_bodies(statement):
                    walk_statements(child_body, scope_names, scope_kinds)

    walk_statements(tree.body, [], [])
    return records


def build_line_offsets(source: str) -> tuple[list[str], list[int], list[int]]:
    lines = source.splitlines(keepends=True)
    if not lines:
        lines = [""]
    starts: list[int] = []
    ends: list[int] = []
    cursor = 0
    for line in lines:
        starts.append(cursor)
        cursor += len(line)
        ends.append(cursor)
    return lines, starts, ends


def utf8_byte_col_to_char_col(line: str, byte_col: int) -> int:
    if byte_col < 0:
        raise ValueError(f"Negative AST column offset: {byte_col}")
    payload = line.encode("utf-8")
    if byte_col > len(payload):
        raise ValueError(
            f"AST byte column {byte_col} exceeds UTF-8 line length {len(payload)}"
        )
    try:
        return len(payload[:byte_col].decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"AST byte column splits a UTF-8 character: {byte_col}") from exc


def node_position_offset(
    source_lines: Sequence[str],
    line_starts: Sequence[int],
    lineno: int,
    utf8_byte_col: int,
) -> int:
    if lineno < 1 or lineno > len(source_lines):
        raise ValueError(f"Line number outside source: {lineno}")
    char_col = utf8_byte_col_to_char_col(source_lines[lineno - 1], utf8_byte_col)
    return line_starts[lineno - 1] + char_col


def is_docstring_statement(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(getattr(statement, "value", None), ast.Constant)
        and isinstance(statement.value.value, str)
    )


def locate_function_suite_start(
    source: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    source_lines: Sequence[str],
    line_starts: Sequence[int],
    line_ends: Sequence[int],
) -> tuple[int, bool]:
    """Return the raw suite-content start and whether the suite is block-form.

    For a block function, the returned offset is immediately after the header's
    physical newline, preserving comments and blank lines before the first AST
    statement. For a one-line function, it is the first statement's exact source
    position after the header colon.
    """

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except Exception as exc:
        raise StageError("function_boundary", f"Tokenization failed: {exc}") from exc

    node_line = int(node.lineno)
    node_char_col = utf8_byte_col_to_char_col(
        source_lines[node_line - 1],
        int(node.col_offset),
    )

    def_index = None
    for index, token in enumerate(tokens):
        if token.type == tokenize.NAME and token.string == "def":
            if token.start[0] == node_line and token.start[1] >= node_char_col:
                def_index = index
                break
    if def_index is None:
        raise StageError("function_boundary", "Could not locate function def token")

    bracket_depth = 0
    colon_index = None
    for index in range(def_index + 1, len(tokens)):
        token = tokens[index]
        if token.type == tokenize.OP:
            if token.string in "([{":
                bracket_depth += 1
            elif token.string in ")]}":
                bracket_depth -= 1
            elif token.string == ":" and bracket_depth == 0:
                colon_index = index
                break
    if colon_index is None:
        raise StageError("function_boundary", "Could not locate function header colon")

    for token in tokens[colon_index + 1 :]:
        if token.type in {tokenize.ENCODING, tokenize.NL, tokenize.COMMENT}:
            continue
        if token.type == tokenize.NEWLINE:
            header_line = token.end[0]
            if header_line < len(line_starts):
                return line_starts[header_line], True
            return line_ends[header_line - 1], True
        if token.type in {tokenize.INDENT, tokenize.DEDENT}:
            continue
        start = node_position_offset(
            source_lines,
            line_starts,
            token.start[0],
            len(source_lines[token.start[0] - 1][: token.start[1]].encode("utf-8")),
        )
        return start, False

    raise StageError("function_boundary", "Could not locate function suite content")


def count_physical_lines(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines()) or 1


def extract_original_implementation_body(
    source: str,
    record: FunctionIndexRecord,
) -> ExtractedBody:
    node = record.node
    if not node.body:
        raise StageError("implementation_body_extract", "Function has no AST body")

    leading_docstring_removed = is_docstring_statement(node.body[0])
    real_body = node.body[1:] if leading_docstring_removed else node.body
    if not real_body:
        raise StageError(
            "implementation_body_extract",
            "docstring_only_after_prompt_removal",
        )

    lines, line_starts, line_ends = build_line_offsets(source)
    first_statement = real_body[0]
    first_line = int(first_statement.lineno)
    suite_start, block_suite = locate_function_suite_start(
        source,
        node,
        lines,
        line_starts,
        line_ends,
    )

    if leading_docstring_removed:
        docstring_statement = node.body[0]
        docstring_end_line = int(
            getattr(docstring_statement, "end_lineno", docstring_statement.lineno)
        )
        if first_line == docstring_end_line:
            body_start = node_position_offset(
                lines,
                line_starts,
                first_line,
                int(first_statement.col_offset),
            )
        else:
            if docstring_end_line < 1 or docstring_end_line > len(line_ends):
                raise StageError(
                    "docstring_boundary",
                    f"Docstring end line outside source: {docstring_end_line}",
                )
            # Exclude the exact leading docstring/prompt while preserving all
            # original comments, blank lines, indentation, and line endings that
            # follow it before the first executable statement.
            body_start = line_ends[docstring_end_line - 1]
    else:
        body_start = suite_start
        if not block_suite:
            body_start = node_position_offset(
                lines,
                line_starts,
                first_line,
                int(first_statement.col_offset),
            )

    end_line = int(getattr(node, "end_lineno", node.lineno))
    if end_line < 1 or end_line > len(line_ends):
        raise StageError(
            "function_boundary",
            f"Function end line outside source: {end_line}",
        )
    # Use the complete physical last line so inline comments remain part of the
    # original implementation. Do not consume later outer-scope comment lines.
    function_end = line_ends[end_line - 1]

    function_start_line = source_start_line(node)
    if function_start_line < 1 or function_start_line > len(line_starts):
        raise StageError(
            "function_boundary",
            f"Function start line outside source: {function_start_line}",
        )
    function_start = line_starts[function_start_line - 1]

    if not (function_start <= body_start < function_end <= len(source)):
        raise StageError(
            "implementation_body_extract",
            (
                "Invalid source boundaries: "
                f"function_start={function_start}, body_start={body_start}, "
                f"function_end={function_end}, source_length={len(source)}"
            ),
        )

    raw_function_source = source[function_start:function_end]
    body_text = source[body_start:function_end]
    if not body_text or not body_text.strip():
        raise StageError("implementation_body_extract", "empty_body_after_extraction")

    split_space_tokens = len(body_text.split(" "))
    nonempty_tokens = len(body_text.split())
    n_windows = math.ceil(split_space_tokens / 128) if split_space_tokens else 0
    remainder = split_space_tokens % 128
    tail_tokens = remainder if remainder else (128 if split_space_tokens else 0)
    has_tail = split_space_tokens > 128 and remainder > 0

    return ExtractedBody(
        raw_function_source=raw_function_source,
        body_text=body_text,
        leading_docstring_removed=leading_docstring_removed,
        function_body_character_count=len(body_text),
        function_body_utf8_byte_count=len(body_text.encode("utf-8")),
        function_body_line_count=count_physical_lines(body_text),
        function_body_split_space_token_count=split_space_tokens,
        function_body_nonempty_whitespace_token_count=nonempty_tokens,
        n_128_token_windows=n_windows,
        tail_window_token_count=tail_tokens,
        has_tail_window=has_tail,
        has_short_tail_window=has_tail and tail_tokens < 128,
    )


def body_artifact_relative_path(body_sha256: str) -> Path:
    return Path("function_bodies", body_sha256[:2], f"{body_sha256}.txt")


def write_body_artifact(output_dir: Path, body_text: str) -> tuple[str, str]:
    body_sha256 = sha256_text(body_text)
    relative = body_artifact_relative_path(body_sha256)
    destination = output_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = body_text.encode("utf-8")

    if destination.exists():
        existing = destination.read_bytes()
        if existing != payload or sha256_bytes(existing) != body_sha256:
            raise StageError(
                "body_artifact_verify",
                f"Existing body artifact conflicts with SHA-256: {destination}",
            )
        return body_sha256, relative.as_posix()

    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, destination)
    if sha256_bytes(destination.read_bytes()) != body_sha256:
        raise StageError(
            "body_artifact_verify",
            f"Written body artifact failed SHA-256 verification: {destination}",
        )
    return body_sha256, relative.as_posix()


def load_event_ids(path: Path) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(f"Event ID file not found: {path}")
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, dtype=str, low_memory=False)
        if "function_event_id" in frame.columns:
            values = frame["function_event_id"]
        elif len(frame.columns) == 1:
            values = frame.iloc[:, 0]
        else:
            raise ValueError(
                "CSV event ID file must contain function_event_id or exactly one column"
            )
        return {str(value).strip() for value in values if str(value).strip()}
    return {
        line.strip().split(",", 1)[0]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def load_manifest(
    path: Path,
    expected_rows: int,
    event_id_file: Path | None,
    max_events: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not path.exists():
        raise FileNotFoundError(f"Input manifest not found: {path}")

    frame = pd.read_csv(path, dtype=str, low_memory=False)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Input manifest missing required columns: {missing}")

    for column in REQUIRED_COLUMNS + [
        value for value in OPTIONAL_MANIFEST_COLUMNS if value in frame.columns
    ]:
        frame[column] = frame[column].fillna("").astype(str).str.strip()

    full_rows = len(frame)
    if expected_rows > 0 and full_rows != expected_rows:
        raise ValueError(
            f"Input manifest row count mismatch: observed={full_rows}, expected={expected_rows}"
        )

    if frame["function_event_id"].duplicated().any():
        duplicates = int(frame["function_event_id"].duplicated().sum())
        raise ValueError(f"Duplicate function_event_id rows: {duplicates}")

    invalid_sources = sorted(set(frame["dataset_source"]) - {"treatment", "control"})
    if invalid_sources:
        raise ValueError(f"Unsupported dataset_source values: {invalid_sources}")

    invalid_paths = frame.loc[
        ~frame["relative_path"].map(safe_relative_python_path),
        ["function_event_id", "relative_path"],
    ]
    if not invalid_paths.empty:
        raise ValueError(
            f"Invalid relative Python paths: {len(invalid_paths)}; "
            f"example={invalid_paths.iloc[0].to_dict()}"
        )

    invalid_commits = ~frame["commit"].map(lambda value: bool(FULL_SHA_RE.fullmatch(value)))
    if invalid_commits.any():
        example = frame.loc[invalid_commits, ["function_event_id", "commit"]].iloc[0]
        raise ValueError(f"Invalid commit SHA; example={example.to_dict()}")

    numeric_columns = ["commit_order", "occurrence_index", "start_line", "end_line"]
    for column in numeric_columns:
        converted = pd.to_numeric(frame[column], errors="coerce")
        if converted.isna().any():
            raise ValueError(f"Manifest column must be numeric: {column}")
        frame[column] = converted.astype(int)

    full_frame = frame.copy()
    selected = frame
    if event_id_file is not None:
        requested = load_event_ids(event_id_file)
        missing_ids = sorted(requested - set(frame["function_event_id"]))
        if missing_ids:
            raise ValueError(
                f"Event ID file contains IDs absent from manifest: {missing_ids[:5]}"
            )
        selected = frame.loc[frame["function_event_id"].isin(requested)].copy()

    selected = selected.sort_values(
        ["dataset_source", "repo_name", "time", "commit_order", "function_event_id"]
    ).reset_index(drop=True)
    if max_events > 0:
        selected = selected.head(max_events).copy()
    if selected.empty:
        raise ValueError("Event selection produced zero rows")
    return full_frame, selected


def blank_event_output(row: pd.Series) -> dict[str, Any]:
    return {
        "function_event_id": row["function_event_id"],
        "dataset_source": row["dataset_source"],
        "repo_name": row["repo_name"],
        "time": row["time"],
        "commit": row["commit"],
        "parent_commit": row["parent_commit"],
        "commit_order": int(row["commit_order"]),
        "relative_path": row["relative_path"],
        "change_type": row["change_type"],
        "qualified_function_name": row["qualified_function_name"],
        "function_name": row["function_name"],
        "function_kind": row["function_kind"],
        "occurrence_index": int(row["occurrence_index"]),
        "start_line": int(row["start_line"]),
        "end_line": int(row["end_line"]),
        "is_nested_function": False,
        "parent_qualified_function_name": "",
        "raw_file_blob_sha256": "",
        "raw_file_bytes": "",
        "source_encoding": "",
        "newline_style": "",
        "raw_function_source_sha256": "",
        "raw_function_start_line": "",
        "raw_function_end_line": "",
        "manifest_structural_sha256": row.get("structural_sha256", ""),
        "recomputed_structural_sha256": "",
        "structural_sha256_matches_manifest": "",
        "leading_docstring_removed": "",
        "function_body_sha256": "",
        "function_body_relative_path": "",
        "function_body_character_count": "",
        "function_body_utf8_byte_count": "",
        "function_body_line_count": "",
        "function_body_split_space_token_count": "",
        "function_body_nonempty_whitespace_token_count": "",
        "n_128_token_windows": "",
        "tail_window_token_count": "",
        "has_tail_window": "",
        "has_short_tail_window": "",
        "contains_nested_function": "",
        "input_preparation_complete": False,
        "body_extraction_status": "excluded",
        "body_exclusion_reason": "",
    }


def exclusion_row(
    row: pd.Series,
    stage: str,
    error: BaseException,
    observed_candidate_count: int = 0,
) -> dict[str, Any]:
    return {
        "function_event_id": row["function_event_id"],
        "dataset_source": row["dataset_source"],
        "repo_name": row["repo_name"],
        "time": row["time"],
        "commit": row["commit"],
        "relative_path": row["relative_path"],
        "qualified_function_name": row["qualified_function_name"],
        "function_name": row["function_name"],
        "function_kind": row["function_kind"],
        "occurrence_index": int(row["occurrence_index"]),
        "start_line": int(row["start_line"]),
        "end_line": int(row["end_line"]),
        "stage": stage,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "observed_candidate_count": observed_candidate_count,
    }


def exact_candidates(
    records: Sequence[FunctionIndexRecord],
    row: pd.Series,
) -> list[FunctionIndexRecord]:
    return [
        record
        for record in records
        if record.qualified_name == row["qualified_function_name"]
        and record.function_name == row["function_name"]
        and record.function_kind == row["function_kind"]
        and record.occurrence_index == int(row["occurrence_index"])
        and record.start_line == int(row["start_line"])
        and record.end_line == int(row["end_line"])
    ]


def add_check(
    rows: list[dict[str, Any]],
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    note: str = "",
) -> None:
    rows.append(
        {
            "check_name": name,
            "passed": bool(passed),
            "observed": observed,
            "expected": expected,
            "note": note,
        }
    )


def prepare_output_directories(
    output_dir: Path,
    qc_dir: Path,
    overwrite: bool,
) -> None:
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Output directory is not empty; use --overwrite-output: {output_dir}"
        )
    if overwrite:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        if qc_dir.exists() and not str(qc_dir).startswith(str(output_dir)):
            shutil.rmtree(qc_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    qc_dir.mkdir(parents=True, exist_ok=True)


def create_unique_body_manifest(events: pd.DataFrame) -> pd.DataFrame:
    prepared = events.loc[events["input_preparation_complete"].eq(True)].copy()
    if prepared.empty:
        return pd.DataFrame(columns=UNIQUE_BODY_COLUMNS)

    rows: list[dict[str, Any]] = []
    for body_sha, group in prepared.groupby("function_body_sha256", sort=True):
        first = group.iloc[0]
        rows.append(
            {
                "function_body_sha256": body_sha,
                "function_body_relative_path": first["function_body_relative_path"],
                "function_body_character_count": first["function_body_character_count"],
                "function_body_utf8_byte_count": first["function_body_utf8_byte_count"],
                "function_body_line_count": first["function_body_line_count"],
                "function_body_split_space_token_count": first[
                    "function_body_split_space_token_count"
                ],
                "function_body_nonempty_whitespace_token_count": first[
                    "function_body_nonempty_whitespace_token_count"
                ],
                "n_128_token_windows": first["n_128_token_windows"],
                "tail_window_token_count": first["tail_window_token_count"],
                "has_tail_window": first["has_tail_window"],
                "has_short_tail_window": first["has_short_tail_window"],
                "referencing_function_event_count": len(group),
                "first_function_event_id": group["function_event_id"].min(),
                "dataset_sources": "|".join(sorted(set(group["dataset_source"]))),
                "repositories": "|".join(sorted(set(group["repo_name"]))),
                "first_observed_month": group["time"].min(),
                "last_observed_month": group["time"].max(),
            }
        )
    return pd.DataFrame(rows, columns=UNIQUE_BODY_COLUMNS)


def create_repo_month_audit(selected: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    input_counts = (
        selected.groupby(["dataset_source", "repo_name", "time"], dropna=False)
        .size()
        .rename("input_function_change_events")
        .reset_index()
    )
    prepared = (
        events.loc[events["input_preparation_complete"].eq(True)]
        .groupby(["dataset_source", "repo_name", "time"], dropna=False)
        .size()
        .rename("prepared_function_change_events")
        .reset_index()
    )
    excluded = (
        events.loc[~events["input_preparation_complete"].eq(True)]
        .groupby(["dataset_source", "repo_name", "time"], dropna=False)
        .size()
        .rename("excluded_function_change_events")
        .reset_index()
    )
    out = input_counts.merge(
        prepared,
        on=["dataset_source", "repo_name", "time"],
        how="left",
        validate="one_to_one",
    ).merge(
        excluded,
        on=["dataset_source", "repo_name", "time"],
        how="left",
        validate="one_to_one",
    )
    for column in ["prepared_function_change_events", "excluded_function_change_events"]:
        out[column] = out[column].fillna(0).astype(int)
    out["events_reconcile"] = (
        out["input_function_change_events"]
        == out["prepared_function_change_events"]
        + out["excluded_function_change_events"]
    )
    return out.sort_values(["dataset_source", "repo_name", "time"]).reset_index(
        drop=True
    )


def run_pipeline(args: argparse.Namespace) -> int:
    if sys.version_info < (3, 12) and not args.allow_python_before_312:
        raise SystemExit(
            "ERROR: Python 3.12+ is required for production extraction; "
            f"found {sys.version.split()[0]}."
        )

    qc_dir = args.qc_dir if args.qc_dir is not None else args.output_dir / "qc"
    prepare_output_directories(args.output_dir, qc_dir, args.overwrite_output)

    full_manifest, selected = load_manifest(
        args.input_manifest,
        args.expected_manifest_rows,
        args.event_id_file,
        args.max_events,
    )

    events_output: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    blob_audit: list[dict[str, Any]] = []

    selected = selected.copy()
    selected["blob_key"] = (
        selected["dataset_source"]
        + "\0"
        + selected["repo_name"]
        + "\0"
        + selected["commit"]
        + "\0"
        + selected["relative_path"]
    )
    grouped = selected.groupby("blob_key", sort=False)
    total_blobs = grouped.ngroups
    prepared_total = 0

    for blob_index, (_, group) in enumerate(grouped, start=1):
        first = group.iloc[0]
        source_name = first["dataset_source"]
        repo_name = first["repo_name"]
        commit = first["commit"]
        relative_path = first["relative_path"]
        repo_root = (
            args.treatment_clone_dir
            if source_name == "treatment"
            else args.control_clone_dir
        )

        audit_row = {
            "dataset_source": source_name,
            "repo_name": repo_name,
            "commit": commit,
            "relative_path": relative_path,
            "repo_dir": "",
            "event_rows": len(group),
            "raw_file_blob_sha256": "",
            "raw_file_bytes": "",
            "source_encoding": "",
            "newline_style": "",
            "indexed_functions": "",
            "prepared_events": 0,
            "excluded_events": 0,
            "blob_status": "",
            "error_stage": "",
            "error_message": "",
        }

        try:
            repo_dir = resolve_repo_dir(repo_root, repo_name)
            audit_row["repo_dir"] = str(repo_dir)
            payload = read_git_blob(repo_dir, commit, relative_path)
            source, encoding = decode_python_source(payload)
            newline_style = detect_newline_style(payload)
            records = index_functions(
                source,
                filename=f"{repo_name}@{commit}:{relative_path}",
            )
            blob_sha = sha256_bytes(payload)
            audit_row.update(
                {
                    "raw_file_blob_sha256": blob_sha,
                    "raw_file_bytes": len(payload),
                    "source_encoding": encoding,
                    "newline_style": newline_style,
                    "indexed_functions": len(records),
                }
            )
        except Exception as exc:
            stage = exc.stage if isinstance(exc, StageError) else "blob_preparation"
            audit_row.update(
                {
                    "prepared_events": 0,
                    "excluded_events": len(group),
                    "blob_status": "excluded",
                    "error_stage": stage,
                    "error_message": f"{type(exc).__name__}: {exc}",
                }
            )
            for _, row in group.iterrows():
                event = blank_event_output(row)
                event["body_exclusion_reason"] = str(exc)
                events_output.append(event)
                exclusions.append(exclusion_row(row, stage, exc))
            blob_audit.append(audit_row)
            continue

        prepared_in_blob = 0
        excluded_in_blob = 0
        for _, row in group.iterrows():
            event = blank_event_output(row)
            event.update(
                {
                    "raw_file_blob_sha256": blob_sha,
                    "raw_file_bytes": len(payload),
                    "source_encoding": encoding,
                    "newline_style": newline_style,
                }
            )
            candidates = exact_candidates(records, row)
            if len(candidates) != 1:
                message = (
                    "Expected exactly one function identity match; "
                    f"observed={len(candidates)}"
                )
                error = StageError("function_identity_match", message)
                event["body_exclusion_reason"] = message
                events_output.append(event)
                exclusions.append(
                    exclusion_row(
                        row,
                        "function_identity_match",
                        error,
                        observed_candidate_count=len(candidates),
                    )
                )
                excluded_in_blob += 1
                continue

            record = candidates[0]
            manifest_structural = str(row.get("structural_sha256", "")).strip()
            structural_matches: bool | str = ""
            if manifest_structural:
                structural_matches = manifest_structural == record.structural_sha256
                if not structural_matches:
                    message = (
                        "Structural SHA-256 mismatch between approved manifest "
                        "and original post-commit parse"
                    )
                    error = StageError("structural_hash_validation", message)
                    event.update(
                        {
                            "is_nested_function": record.is_nested_function,
                            "parent_qualified_function_name": record.parent_qualified_function_name,
                            "recomputed_structural_sha256": record.structural_sha256,
                            "structural_sha256_matches_manifest": False,
                            "contains_nested_function": record.contains_nested_function,
                            "body_exclusion_reason": message,
                        }
                    )
                    events_output.append(event)
                    exclusions.append(
                        exclusion_row(row, "structural_hash_validation", error, 1)
                    )
                    excluded_in_blob += 1
                    continue

            try:
                extracted = extract_original_implementation_body(source, record)
                body_sha, body_relative = write_body_artifact(
                    args.output_dir,
                    extracted.body_text,
                )
                event.update(
                    {
                        "is_nested_function": record.is_nested_function,
                        "parent_qualified_function_name": record.parent_qualified_function_name,
                        "raw_function_source_sha256": sha256_text(
                            extracted.raw_function_source
                        ),
                        "raw_function_start_line": record.start_line,
                        "raw_function_end_line": record.end_line,
                        "recomputed_structural_sha256": record.structural_sha256,
                        "structural_sha256_matches_manifest": structural_matches,
                        "leading_docstring_removed": extracted.leading_docstring_removed,
                        "function_body_sha256": body_sha,
                        "function_body_relative_path": body_relative,
                        "function_body_character_count": extracted.function_body_character_count,
                        "function_body_utf8_byte_count": extracted.function_body_utf8_byte_count,
                        "function_body_line_count": extracted.function_body_line_count,
                        "function_body_split_space_token_count": extracted.function_body_split_space_token_count,
                        "function_body_nonempty_whitespace_token_count": extracted.function_body_nonempty_whitespace_token_count,
                        "n_128_token_windows": extracted.n_128_token_windows,
                        "tail_window_token_count": extracted.tail_window_token_count,
                        "has_tail_window": extracted.has_tail_window,
                        "has_short_tail_window": extracted.has_short_tail_window,
                        "contains_nested_function": record.contains_nested_function,
                        "input_preparation_complete": True,
                        "body_extraction_status": "prepared",
                        "body_exclusion_reason": "",
                    }
                )
                events_output.append(event)
                prepared_in_blob += 1
            except Exception as exc:
                stage = (
                    exc.stage if isinstance(exc, StageError) else "implementation_body_extract"
                )
                event.update(
                    {
                        "is_nested_function": record.is_nested_function,
                        "parent_qualified_function_name": record.parent_qualified_function_name,
                        "recomputed_structural_sha256": record.structural_sha256,
                        "structural_sha256_matches_manifest": structural_matches,
                        "contains_nested_function": record.contains_nested_function,
                        "body_exclusion_reason": str(exc),
                    }
                )
                events_output.append(event)
                exclusions.append(exclusion_row(row, stage, exc, 1))
                excluded_in_blob += 1

        audit_row.update(
            {
                "prepared_events": prepared_in_blob,
                "excluded_events": excluded_in_blob,
                "blob_status": "prepared" if excluded_in_blob == 0 else "partial",
            }
        )
        blob_audit.append(audit_row)
        prepared_total += prepared_in_blob

        if args.progress_every_blobs > 0 and (
            blob_index % args.progress_every_blobs == 0 or blob_index == total_blobs
        ):
            print(
                f"[progress] blobs={blob_index}/{total_blobs} "
                f"events={len(events_output)}/{len(selected)} "
                f"prepared={prepared_total} "
                f"excluded={len(exclusions)}",
                flush=True,
            )

    events = pd.DataFrame(events_output, columns=EVENT_OUTPUT_COLUMNS)
    exclusions_frame = pd.DataFrame(exclusions, columns=EXCLUSION_COLUMNS)
    blob_frame = pd.DataFrame(blob_audit, columns=BLOB_AUDIT_COLUMNS)
    unique_bodies = create_unique_body_manifest(events)
    repo_month_audit = create_repo_month_audit(selected, events)

    event_path = args.output_dir / "commit_function_detectcodegpt_input_events.csv"
    unique_path = args.output_dir / "commit_function_detectcodegpt_unique_bodies.csv"
    blob_path = args.output_dir / "commit_function_detectcodegpt_blob_audit.csv"
    repo_month_path = (
        args.output_dir / "commit_function_detectcodegpt_repo_month_audit.csv"
    )
    exclusion_path = qc_dir / "commit_function_detectcodegpt_exclusions.csv"
    check_path = qc_dir / "commit_function_detectcodegpt_checks.csv"
    summary_path = qc_dir / "commit_function_detectcodegpt_summary.json"
    metadata_path = qc_dir / "commit_function_detectcodegpt_metadata.json"

    atomic_csv(events, event_path)
    atomic_csv(unique_bodies, unique_path)
    atomic_csv(blob_frame, blob_path)
    atomic_csv(repo_month_audit, repo_month_path)
    atomic_csv(exclusions_frame, exclusion_path)

    prepared_events = int(events["input_preparation_complete"].eq(True).sum())
    excluded_events = len(events) - prepared_events
    duplicate_event_ids = int(events["function_event_id"].duplicated().sum())
    unexpected_missing_artifacts = 0
    artifact_hash_mismatches = 0
    for _, row in unique_bodies.iterrows():
        path = args.output_dir / str(row["function_body_relative_path"])
        if not path.exists():
            unexpected_missing_artifacts += 1
            continue
        if sha256_bytes(path.read_bytes()) != row["function_body_sha256"]:
            artifact_hash_mismatches += 1

    check_rows: list[dict[str, Any]] = []
    add_check(
        check_rows,
        "full_manifest_rows",
        len(full_manifest) == args.expected_manifest_rows
        if args.expected_manifest_rows > 0
        else True,
        len(full_manifest),
        args.expected_manifest_rows if args.expected_manifest_rows > 0 else "not_enforced",
    )
    add_check(
        check_rows,
        "selected_event_rows_written",
        len(events) == len(selected),
        len(events),
        len(selected),
    )
    add_check(
        check_rows,
        "unique_event_ids",
        duplicate_event_ids == 0,
        duplicate_event_ids,
        0,
    )
    add_check(
        check_rows,
        "prepared_plus_excluded_reconciles",
        prepared_events + excluded_events == len(selected),
        prepared_events + excluded_events,
        len(selected),
    )
    add_check(
        check_rows,
        "repo_month_events_reconcile",
        bool(repo_month_audit["events_reconcile"].all()),
        int((~repo_month_audit["events_reconcile"]).sum()),
        0,
    )
    add_check(
        check_rows,
        "missing_body_artifacts",
        unexpected_missing_artifacts == 0,
        unexpected_missing_artifacts,
        0,
    )
    add_check(
        check_rows,
        "body_artifact_hash_mismatches",
        artifact_hash_mismatches == 0,
        artifact_hash_mismatches,
        0,
    )
    add_check(
        check_rows,
        "ast_unparse_not_used",
        True,
        False,
        False,
        "Detector inputs are raw source slices; ast.unparse is never called.",
    )
    add_check(
        check_rows,
        "structural_hash_mismatches",
        int((events["structural_sha256_matches_manifest"] == False).sum()) == 0,  # noqa: E712
        int((events["structural_sha256_matches_manifest"] == False).sum()),  # noqa: E712
        0,
    )
    expected_exclusion_mask = pd.Series(False, index=exclusions_frame.index)
    if not exclusions_frame.empty:
        expected_exclusion_mask = (
            exclusions_frame["stage"].eq("implementation_body_extract")
            & exclusions_frame["error_message"].str.contains(
                "docstring_only_after_prompt_removal|empty_body_after_extraction",
                regex=True,
                na=False,
            )
        )
    expected_exclusions = int(expected_exclusion_mask.sum())
    unexpected_exclusions = int(len(exclusions_frame) - expected_exclusions)
    add_check(
        check_rows,
        "unexpected_exclusions",
        unexpected_exclusions == 0,
        unexpected_exclusions,
        0,
        (
            "Docstring-only or empty-after-prompt-removal functions are explicit "
            "detector-ineligible exclusions; all other exclusions fail QC."
        ),
    )

    checks = pd.DataFrame(check_rows, columns=CHECK_COLUMNS)
    atomic_csv(checks, check_path)

    stage_counts = (
        exclusions_frame["stage"].value_counts().sort_index().to_dict()
        if not exclusions_frame.empty
        else {}
    )
    all_checks_pass = bool(checks["passed"].all())
    if not all_checks_pass:
        status = "FAIL"
    elif expected_exclusions > 0:
        status = "PASS_WITH_EXCLUSIONS"
    else:
        status = "PASS"

    summary = {
        "status": status,
        "python_version": sys.version.split()[0],
        "input_manifest": str(args.input_manifest),
        "full_manifest_rows": len(full_manifest),
        "selected_event_rows": len(selected),
        "unique_git_blobs": total_blobs,
        "prepared_events": prepared_events,
        "excluded_events": excluded_events,
        "expected_detector_ineligible_exclusions": expected_exclusions,
        "unexpected_exclusions": unexpected_exclusions,
        "unique_bodies": len(unique_bodies),
        "deduplicated_body_references": prepared_events - len(unique_bodies),
        "repository_months": len(repo_month_audit),
        "failed_checks": int((~checks["passed"]).sum()),
        "exclusions_by_stage": stage_counts,
        "event_output": str(event_path),
        "unique_body_output": str(unique_path),
        "blob_audit_output": str(blob_path),
        "repo_month_audit_output": str(repo_month_path),
        "exclusion_output": str(exclusion_path),
        "check_output": str(check_path),
        "body_artifact_root": str(args.output_dir / "function_bodies"),
    }
    atomic_json(summary, summary_path)

    metadata = {
        "experiment": "run-1a-prepare-input-commit-func",
        "analysis_unit": "commit-function change event",
        "computational_storage_unit": "unique original implementation body",
        "source_of_truth": "original post-commit Git blob",
        "parser_role": "function identity, boundaries, docstring detection, and QC only",
        "parser_minimum_version": "Python 3.12",
        "detector_input_representation": "original source implementation body",
        "source_renderer": "raw source slice",
        "ast_unparse_used": False,
        "signature_included": False,
        "leading_docstring_prompt_included": False,
        "whitespace_preserved": True,
        "newline_structure_preserved": True,
        "primary_tokenization": "split_space_v1: text.split(' ')",
        "window_length": 128,
        "size_filter_applied": False,
        "agc_scoring_performed": False,
        "input_manifest_sha256": sha256_bytes(args.input_manifest.read_bytes()),
        "treatment_clone_dir": str(args.treatment_clone_dir),
        "control_clone_dir": str(args.control_clone_dir),
        "output_dir": str(args.output_dir),
        "qc_dir": str(qc_dir),
        "selection_event_id_file": str(args.event_id_file) if args.event_id_file else "",
        "selection_max_events": args.max_events,
    }
    atomic_json(metadata, metadata_path)

    print("=" * 76)
    print("Prepare original commit-function implementation-body inputs")
    print(f"Status:                       {summary['status']}")
    print(f"Full manifest rows:           {summary['full_manifest_rows']}")
    print(f"Selected event rows:          {summary['selected_event_rows']}")
    print(f"Unique Git blobs:             {summary['unique_git_blobs']}")
    print(f"Prepared events:              {summary['prepared_events']}")
    print(f"Excluded events:              {summary['excluded_events']}")
    print(f"Unique implementation bodies: {summary['unique_bodies']}")
    print(f"Deduplicated references:      {summary['deduplicated_body_references']}")
    print(f"Repository-months:            {summary['repository_months']}")
    print(f"Failed checks:                {summary['failed_checks']}")
    print(f"Event output:                 {event_path}")
    print(f"Unique body output:           {unique_path}")
    print(f"QC checks:                    {check_path}")
    print(f"QC summary:                   {summary_path}")
    print("=" * 76)

    return 0 if summary["status"] in {"PASS", "PASS_WITH_EXCLUSIONS"} else 1


def run_self_test() -> None:
    source = (
        "@decorator(flag=True)\n"
        "def outer(\n"
        "    value,\n"
        "):\n"
        "    \"\"\"Prompt text.\"\"\"\n"
        "    # implementation comment\n"
        "    result  = value + 1\n"
        "    def nested(x):\n"
        "        return  x * 2\n"
        "    return nested(result)  # preserve inline comment\n"
        "\n"
        "class C:\n"
        "    async def method(self):\n"
        "        return  1\n"
        "\n"
        "def one_line(): return  7  # inline\n"
        "\n"
        "def doc_only():\n"
        "    \"\"\"Only prompt.\"\"\"\n"
    )
    records = index_functions(source, "<self-test>")
    by_name = {(record.qualified_name, record.occurrence_index): record for record in records}

    outer = by_name[("outer", 1)]
    extracted = extract_original_implementation_body(source, outer)
    assert "Prompt text" not in extracted.body_text
    assert "    # implementation comment\n" in extracted.body_text
    assert "result  = value + 1" in extracted.body_text
    assert "# preserve inline comment" in extracted.body_text
    assert extracted.leading_docstring_removed is True
    assert outer.contains_nested_function is True

    nested = by_name[("outer.nested", 1)]
    nested_body = extract_original_implementation_body(source, nested).body_text
    assert nested_body.startswith("        return  x * 2")
    assert nested.is_nested_function is True

    method = by_name[("C.method", 1)]
    method_body = extract_original_implementation_body(source, method).body_text
    assert method.function_kind == "async_method"
    assert "return  1" in method_body

    one_line = by_name[("one_line", 1)]
    one_line_body = extract_original_implementation_body(source, one_line).body_text
    assert one_line_body.startswith("return  7")
    assert "# inline" in one_line_body

    doc_only = by_name[("doc_only", 1)]
    try:
        extract_original_implementation_body(source, doc_only)
    except StageError as exc:
        assert "docstring_only" in str(exc)
    else:
        raise AssertionError("Docstring-only function must be excluded")

    crlf_source = "def f():\r\n    value  = 1\r\n    return value\r\n"
    crlf_record = index_functions(crlf_source, "<crlf>")[0]
    crlf_body = extract_original_implementation_body(crlf_source, crlf_record).body_text
    assert "\r\n" in crlf_body
    assert "value  = 1" in crlf_body

    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        sha1, relative1 = write_body_artifact(root, extracted.body_text)
        sha2, relative2 = write_body_artifact(root, extracted.body_text)
        assert sha1 == sha2
        assert relative1 == relative2
        assert sha256_bytes((root / relative1).read_bytes()) == sha1

    assert "ast.unparse" not in extract_original_implementation_body.__code__.co_names
    print("Self-test: PASS")


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0
    return run_pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())
