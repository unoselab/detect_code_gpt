#!/usr/bin/env python3
"""Prepare raw Python snapshot code units for later NPR scoring.

This A01 stage operates on materialized historical repository snapshots. It
reads Python files directly from the snapshot tree, preserves raw decoded source
text, uses the Python AST only to identify scopes and source boundaries, and
writes content-addressed raw-source code-unit artifacts.

Primary code units:
- function_body: direct module-level function implementation body
- method_body: direct class method implementation body
- module_block: contiguous module-level source outside function/class definitions
- class_block: contiguous class-level source outside method/nested-class definitions

Nested definitions that overlap a larger primary unit are retained only as
``diagnostic_overlap`` records. They are never intended to contribute primary
aggregation weight.

This stage does not load an LLM, generate perturbations, split 128-token scoring
windows, calculate NPR, or classify AI-generated/human-written code.
"""

from __future__ import annotations

import argparse
import ast
import bisect
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import tokenize
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Sequence


IMPLEMENTATION_VERSION = "v2"
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
DEFINITION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

SNAPSHOT_COLUMNS = [
    "snapshot_order",
    "snapshot_id",
    "dataset_source",
    "repo_name",
    "repo_key",
    "snapshot_time",
    "snapshot_commit",
    "repo_month_rows",
    "first_panel_month",
    "last_panel_month",
    "snapshot_path",
    "snapshot_dir_name",
    "metadata_source",
    "metadata_complete",
    "python_files_discovered",
    "python_files_prepared",
    "python_files_excluded",
    "primary_code_units",
    "diagnostic_overlap_units",
    "function_bodies",
    "method_bodies",
    "module_blocks",
    "class_blocks",
    "code_unit_characters_primary",
    "code_unit_utf8_bytes_primary",
    "space_by_tokens_primary",
]

FILE_COLUMNS = [
    "snapshot_order",
    "snapshot_id",
    "dataset_source",
    "repo_name",
    "repo_key",
    "snapshot_time",
    "snapshot_commit",
    "relative_path",
    "absolute_path",
    "file_sha256",
    "file_bytes",
    "source_encoding",
    "newline_style",
    "physical_line_count",
    "parse_status",
    "parse_error_type",
    "parse_error_message",
    "module_docstring_removed",
    "module_docstring_removed_lines",
    "module_docstring_removed_utf8_bytes",
    "function_records",
    "method_records",
    "nested_function_records",
    "module_blocks",
    "class_blocks",
    "primary_code_units",
    "diagnostic_overlap_units",
]

CODE_UNIT_COLUMNS = [
    "snapshot_order",
    "snapshot_id",
    "dataset_source",
    "repo_name",
    "repo_key",
    "snapshot_time",
    "snapshot_commit",
    "relative_path",
    "file_sha256",
    "code_unit_id",
    "code_unit_type",
    "aggregation_role",
    "qualified_name",
    "function_kind",
    "occurrence_index",
    "scope_kind",
    "scope_qualified_name",
    "direct_statement_count",
    "leading_docstring_removed",
    "contains_nested_definition",
    "start_line",
    "end_line",
    "start_char_offset",
    "end_char_offset",
    "code_unit_sha256",
    "code_unit_relative_path",
    "character_count",
    "utf8_byte_count",
    "physical_line_count",
    "space_by_token_count",
    "nonempty_whitespace_token_count",
]

EXCLUSION_COLUMNS = [
    "snapshot_id",
    "dataset_source",
    "repo_name",
    "snapshot_commit",
    "relative_path",
    "qualified_name",
    "stage",
    "error_type",
    "error_message",
]

CHECK_COLUMNS = [
    "check_name",
    "severity",
    "passed",
    "observed",
    "expected",
    "note",
]


@dataclass(frozen=True)
class SnapshotTarget:
    order: int
    path: Path
    snapshot_id: str
    dataset_source: str
    repo_name: str
    repo_key: str
    snapshot_time: str
    snapshot_commit: str
    repo_month_rows: str
    first_panel_month: str
    last_panel_month: str
    metadata_source: str

    @property
    def metadata_complete(self) -> bool:
        return bool(
            self.dataset_source in {"treatment", "control"}
            and self.repo_name
            and FULL_SHA_RE.fullmatch(self.snapshot_commit or "")
        )


@dataclass(frozen=True)
class FunctionRecord:
    qualified_name: str
    function_name: str
    function_kind: str
    occurrence_index: int
    aggregation_role: str
    contains_nested_definition: bool
    node: ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class ScopeRecord:
    scope_kind: str
    qualified_name: str
    aggregation_role: str
    statements: Sequence[ast.stmt]
    node: ast.ClassDef | None


@dataclass(frozen=True)
class ExtractedUnit:
    code_unit_type: str
    aggregation_role: str
    qualified_name: str
    function_kind: str
    occurrence_index: int | str
    scope_kind: str
    scope_qualified_name: str
    direct_statement_count: int | str
    leading_docstring_removed: bool
    contains_nested_definition: bool
    start_offset: int
    end_offset: int
    text: str


class StageError(RuntimeError):
    """Pipeline error carrying a stable stage name."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare raw Python code units from materialized snapshots."
    )
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        default=Path("/mnt/samsung850ev/project-workspace/tmp/python-snapshot-samples"),
    )
    parser.add_argument(
        "--snapshot-manifest",
        type=Path,
        default=None,
        help=(
            "Optional source snapshot manifest. Rows are matched to materialized "
            "snapshot directories by explicit path, snapshot ID, or commit SHA."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/snapshot_npr/run-x-a01"),
    )
    parser.add_argument(
        "--qc-dir",
        type=Path,
        default=None,
        help="Defaults to <output-dir>/qc.",
    )
    parser.add_argument("--expected-snapshots", type=int, default=2)
    parser.add_argument("--progress-every-files", type=int, default=100)
    parser.add_argument("--overwrite-output", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--require-complete-metadata",
        action="store_true",
        help=(
            "Fail QC when a snapshot lacks dataset_source/repo_name/full commit "
            "metadata needed for downstream stable joins."
        ),
    )
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


def count_physical_lines(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines()) or 1


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


def decode_python_source(payload: bytes) -> tuple[str, str]:
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(payload).readline)
        return payload.decode(encoding), encoding
    except Exception as exc:
        raise StageError("source_decode", f"{type(exc).__name__}: {exc}") from exc


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


def ast_position_offset(
    source_lines: Sequence[str],
    line_starts: Sequence[int],
    lineno: int,
    utf8_byte_col: int,
) -> int:
    if lineno < 1 or lineno > len(source_lines):
        raise ValueError(f"Line number outside source: {lineno}")
    char_col = utf8_byte_col_to_char_col(source_lines[lineno - 1], utf8_byte_col)
    return line_starts[lineno - 1] + char_col


def offset_to_line(line_starts: Sequence[int], offset: int, source_length: int) -> int:
    if not line_starts:
        return 1
    if offset >= source_length and source_length > 0:
        return len(line_starts)
    index = bisect.bisect_right(line_starts, max(0, offset)) - 1
    return max(1, min(len(line_starts), index + 1))


def source_start_line(node: ast.AST) -> int:
    base = int(getattr(node, "lineno", 1))
    decorators = getattr(node, "decorator_list", [])
    decorator_lines = [
        int(decorator.lineno) for decorator in decorators if hasattr(decorator, "lineno")
    ]
    return min([base, *decorator_lines]) if decorator_lines else base


def definition_start_offset(
    node: ast.AST,
    line_starts: Sequence[int],
) -> int:
    line = source_start_line(node)
    if line < 1 or line > len(line_starts):
        raise StageError("definition_boundary", f"Definition start line outside source: {line}")
    return line_starts[line - 1]


def definition_end_offset(node: ast.AST, line_ends: Sequence[int]) -> int:
    line = int(getattr(node, "end_lineno", getattr(node, "lineno", 1)))
    if line < 1 or line > len(line_ends):
        raise StageError("definition_boundary", f"Definition end line outside source: {line}")
    return line_ends[line - 1]


def is_docstring_statement(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(getattr(statement, "value", None), ast.Constant)
        and isinstance(statement.value.value, str)
    )


def statement_child_bodies(statement: ast.stmt) -> Iterator[Sequence[ast.stmt]]:
    for field_name in ("body", "orelse", "finalbody"):
        value = getattr(statement, field_name, None)
        if isinstance(value, list) and value and all(isinstance(item, ast.stmt) for item in value):
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


def contains_nested_named_definition(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, DEFINITION_TYPES):
            return True
    return False


def locate_suite_start(
    source: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    keyword: str,
    source_lines: Sequence[str],
    line_starts: Sequence[int],
    line_ends: Sequence[int],
) -> tuple[int, bool]:
    """Return suite content start and whether the suite is block-form."""

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except Exception as exc:
        raise StageError("suite_boundary", f"Tokenization failed: {exc}") from exc

    node_line = int(node.lineno)
    node_char_col = utf8_byte_col_to_char_col(
        source_lines[node_line - 1], int(node.col_offset)
    )

    keyword_index = None
    for index, token in enumerate(tokens):
        if token.type == tokenize.NAME and token.string == keyword:
            if token.start[0] == node_line and token.start[1] >= node_char_col:
                keyword_index = index
                break
    if keyword_index is None:
        raise StageError("suite_boundary", f"Could not locate {keyword!r} token")

    bracket_depth = 0
    colon_index = None
    for index in range(keyword_index + 1, len(tokens)):
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
        raise StageError("suite_boundary", "Could not locate definition header colon")

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
        # tokenize columns are character offsets, not UTF-8 byte offsets.
        return line_starts[token.start[0] - 1] + token.start[1], False

    raise StageError("suite_boundary", "Could not locate suite content")


def function_kind(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    scope_kinds: Sequence[str],
) -> str:
    is_async = isinstance(node, ast.AsyncFunctionDef)
    if "function" in scope_kinds:
        return "nested_async_function" if is_async else "nested_function"
    if scope_kinds and scope_kinds[-1] == "class":
        return "async_method" if is_async else "method"
    return "module_async_function" if is_async else "module_function"


def index_source(
    source: str,
    filename: str,
) -> tuple[ast.Module, list[FunctionRecord], list[ScopeRecord]]:
    try:
        tree = ast.parse(source, filename=filename, type_comments=True)
    except Exception as exc:
        raise StageError("raw_file_parse", f"{type(exc).__name__}: {exc}") from exc

    function_records: list[FunctionRecord] = []
    scope_records: list[ScopeRecord] = [
        ScopeRecord(
            scope_kind="module",
            qualified_name="<module>",
            aggregation_role="primary",
            statements=tree.body,
            node=None,
        )
    ]
    occurrence_counts: Counter[str] = Counter()

    def walk(
        statements: Sequence[ast.stmt],
        scope_names: list[str],
        scope_kinds: list[str],
        inside_compound: bool,
    ) -> None:
        for statement in statements:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = ".".join([*scope_names, statement.name])
                occurrence_counts[qualified] += 1
                role = (
                    "primary"
                    if "function" not in scope_kinds and not inside_compound
                    else "diagnostic_overlap"
                )
                function_records.append(
                    FunctionRecord(
                        qualified_name=qualified,
                        function_name=statement.name,
                        function_kind=function_kind(statement, scope_kinds),
                        occurrence_index=occurrence_counts[qualified],
                        aggregation_role=role,
                        contains_nested_definition=contains_nested_named_definition(statement),
                        node=statement,
                    )
                )
                walk(
                    statement.body,
                    [*scope_names, statement.name],
                    [*scope_kinds, "function"],
                    inside_compound=False,
                )
            elif isinstance(statement, ast.ClassDef):
                qualified = ".".join([*scope_names, statement.name])
                class_role = (
                    "primary"
                    if "function" not in scope_kinds and not inside_compound
                    else "diagnostic_overlap"
                )
                scope_records.append(
                    ScopeRecord(
                        scope_kind="class",
                        qualified_name=qualified,
                        aggregation_role=class_role,
                        statements=statement.body,
                        node=statement,
                    )
                )
                # Preserve diagnostic ancestry for classes nested inside compound
                # statements. A class inside an outer primary module/class block is
                # diagnostic_overlap, and its methods must not become primary again.
                walk(
                    statement.body,
                    [*scope_names, statement.name],
                    [*scope_kinds, "class"],
                    inside_compound=inside_compound,
                )
            else:
                for child_body in statement_child_bodies(statement):
                    walk(
                        child_body,
                        scope_names,
                        scope_kinds,
                        inside_compound=True,
                    )

    walk(tree.body, [], [], inside_compound=False)
    return tree, function_records, scope_records


def extract_function_body(
    source: str,
    record: FunctionRecord,
    source_lines: Sequence[str],
    line_starts: Sequence[int],
    line_ends: Sequence[int],
) -> ExtractedUnit:
    node = record.node
    if not node.body:
        raise StageError("implementation_body_extract", "Function has no AST body")

    leading_docstring_removed = is_docstring_statement(node.body[0])
    real_body = node.body[1:] if leading_docstring_removed else node.body
    if not real_body:
        raise StageError(
            "implementation_body_extract", "docstring_only_after_prompt_removal"
        )

    suite_start, block_suite = locate_suite_start(
        source,
        node,
        "def",
        source_lines,
        line_starts,
        line_ends,
    )
    first_statement = real_body[0]
    first_line = int(first_statement.lineno)

    if leading_docstring_removed:
        docstring_statement = node.body[0]
        doc_end_line = int(
            getattr(docstring_statement, "end_lineno", docstring_statement.lineno)
        )
        if first_line == doc_end_line:
            body_start = ast_position_offset(
                source_lines,
                line_starts,
                first_line,
                int(first_statement.col_offset),
            )
        else:
            if doc_end_line < 1 or doc_end_line > len(line_ends):
                raise StageError(
                    "docstring_boundary", f"Docstring end line outside source: {doc_end_line}"
                )
            body_start = line_ends[doc_end_line - 1]
    else:
        body_start = suite_start
        if not block_suite:
            body_start = ast_position_offset(
                source_lines,
                line_starts,
                first_line,
                int(first_statement.col_offset),
            )

    body_end = definition_end_offset(node, line_ends)
    if not (0 <= body_start < body_end <= len(source)):
        raise StageError(
            "implementation_body_extract",
            f"Invalid body boundaries: start={body_start}, end={body_end}, source={len(source)}",
        )

    text = source[body_start:body_end]
    if not text or not text.strip():
        raise StageError("implementation_body_extract", "empty_body_after_extraction")

    kind = "method_body" if "method" in record.function_kind else "function_body"
    return ExtractedUnit(
        code_unit_type=kind,
        aggregation_role=record.aggregation_role,
        qualified_name=record.qualified_name,
        function_kind=record.function_kind,
        occurrence_index=record.occurrence_index,
        scope_kind="function",
        scope_qualified_name=record.qualified_name,
        direct_statement_count=len(real_body),
        leading_docstring_removed=leading_docstring_removed,
        contains_nested_definition=record.contains_nested_definition,
        start_offset=body_start,
        end_offset=body_end,
        text=text,
    )


def scope_suite_bounds(
    source: str,
    scope: ScopeRecord,
    source_lines: Sequence[str],
    line_starts: Sequence[int],
    line_ends: Sequence[int],
) -> tuple[int, int]:
    if scope.scope_kind == "module":
        return 0, len(source)
    assert scope.node is not None
    start, _ = locate_suite_start(
        source,
        scope.node,
        "class",
        source_lines,
        line_starts,
        line_ends,
    )
    end = definition_end_offset(scope.node, line_ends)
    return start, end


def extract_scope_blocks(
    source: str,
    scope: ScopeRecord,
    source_lines: Sequence[str],
    line_starts: Sequence[int],
    line_ends: Sequence[int],
) -> tuple[list[ExtractedUnit], bool, int, int]:
    """Extract contiguous direct-statement blocks outside named definitions."""

    statements = list(scope.statements)
    scope_start, scope_end = scope_suite_bounds(
        source, scope, source_lines, line_starts, line_ends
    )

    docstring_removed = bool(statements and is_docstring_statement(statements[0]))
    removed_lines = 0
    removed_bytes = 0
    cursor = scope_start
    effective = statements

    if docstring_removed:
        doc = statements[0]
        doc_end_line = int(getattr(doc, "end_lineno", doc.lineno))
        doc_start = ast_position_offset(
            source_lines, line_starts, int(doc.lineno), int(doc.col_offset)
        )
        doc_end_exact = ast_position_offset(
            source_lines,
            line_starts,
            int(getattr(doc, "end_lineno", doc.lineno)),
            int(getattr(doc, "end_col_offset", doc.col_offset)),
        )
        removed_lines = int(getattr(doc, "end_lineno", doc.lineno)) - int(doc.lineno) + 1
        removed_bytes = len(source[doc_start:doc_end_exact].encode("utf-8"))
        effective = statements[1:]
        if effective:
            first = effective[0]
            if int(first.lineno) == doc_end_line:
                cursor = ast_position_offset(
                    source_lines,
                    line_starts,
                    int(first.lineno),
                    int(first.col_offset),
                )
            else:
                cursor = line_ends[doc_end_line - 1]
        else:
            cursor = scope_end

    units: list[ExtractedUnit] = []
    run: list[ast.stmt] = []
    block_ordinal = 0

    def emit_run(end_offset: int) -> None:
        nonlocal cursor, run, block_ordinal
        if not run:
            return
        start_offset = cursor
        if not (0 <= start_offset < end_offset <= len(source)):
            raise StageError(
                "scope_block_extract",
                f"Invalid block boundaries: start={start_offset}, end={end_offset}",
            )
        text = source[start_offset:end_offset]
        if text and text.strip():
            block_ordinal += 1
            unit_type = "module_block" if scope.scope_kind == "module" else "class_block"
            units.append(
                ExtractedUnit(
                    code_unit_type=unit_type,
                    aggregation_role=scope.aggregation_role,
                    qualified_name=f"{scope.qualified_name}::<block:{block_ordinal}>",
                    function_kind="",
                    occurrence_index=block_ordinal,
                    scope_kind=scope.scope_kind,
                    scope_qualified_name=scope.qualified_name,
                    direct_statement_count=len(run),
                    leading_docstring_removed=docstring_removed and block_ordinal == 1,
                    contains_nested_definition=any(
                        contains_nested_named_definition(statement) for statement in run
                    ),
                    start_offset=start_offset,
                    end_offset=end_offset,
                    text=text,
                )
            )
        run = []

    for statement in effective:
        if isinstance(statement, DEFINITION_TYPES):
            boundary = definition_start_offset(statement, line_starts)
            emit_run(boundary)
            cursor = definition_end_offset(statement, line_ends)
        else:
            run.append(statement)

    emit_run(scope_end)
    return units, docstring_removed, removed_lines, removed_bytes


def analyze_source(source: str, filename: str) -> tuple[
    list[ExtractedUnit], dict[str, Any]
]:
    tree, functions, scopes = index_source(source, filename)
    del tree
    source_lines, line_starts, line_ends = build_line_offsets(source)

    units: list[ExtractedUnit] = []
    unit_exclusions: list[dict[str, str]] = []
    module_docstring_removed = False
    module_docstring_removed_lines = 0
    module_docstring_removed_bytes = 0

    for scope in scopes:
        try:
            block_units, removed, removed_lines, removed_bytes = extract_scope_blocks(
                source, scope, source_lines, line_starts, line_ends
            )
            units.extend(block_units)
            if scope.scope_kind == "module":
                module_docstring_removed = removed
                module_docstring_removed_lines = removed_lines
                module_docstring_removed_bytes = removed_bytes
        except Exception as exc:
            unit_exclusions.append(
                {
                    "qualified_name": scope.qualified_name,
                    "stage": exc.stage if isinstance(exc, StageError) else "scope_block_extract",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )

    for record in functions:
        try:
            units.append(
                extract_function_body(
                    source,
                    record,
                    source_lines,
                    line_starts,
                    line_ends,
                )
            )
        except Exception as exc:
            unit_exclusions.append(
                {
                    "qualified_name": record.qualified_name,
                    "stage": exc.stage if isinstance(exc, StageError) else "function_body_extract",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )

    units.sort(
        key=lambda unit: (
            unit.start_offset,
            unit.end_offset,
            unit.aggregation_role != "primary",
            unit.code_unit_type,
            unit.qualified_name,
        )
    )

    stats = {
        "module_docstring_removed": module_docstring_removed,
        "module_docstring_removed_lines": module_docstring_removed_lines,
        "module_docstring_removed_utf8_bytes": module_docstring_removed_bytes,
        "function_records": sum(
            1 for record in functions if "method" not in record.function_kind
        ),
        "method_records": sum(1 for record in functions if "method" in record.function_kind),
        "nested_function_records": sum(
            1 for record in functions if record.aggregation_role == "diagnostic_overlap"
        ),
        "unit_exclusions": unit_exclusions,
    }
    return units, stats


def safe_relative_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise StageError("path_validation", f"Unsafe relative path: {relative}")
    return relative


def write_csv(rows: Sequence[dict[str, Any]], columns: Sequence[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    os.replace(temporary, path)


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def code_unit_artifact_relative_path(code_sha256: str) -> Path:
    return Path("code_units", code_sha256[:2], f"{code_sha256}.txt")


def write_code_unit_artifact(output_dir: Path, text: str) -> tuple[str, str]:
    code_sha = sha256_text(text)
    relative = code_unit_artifact_relative_path(code_sha)
    destination = output_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = text.encode("utf-8")

    if destination.exists():
        existing = destination.read_bytes()
        if existing != payload or sha256_bytes(existing) != code_sha:
            raise StageError(
                "artifact_verify",
                f"Existing artifact conflicts with SHA-256: {destination}",
            )
        return code_sha, relative.as_posix()

    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, destination)
    if sha256_bytes(destination.read_bytes()) != code_sha:
        raise StageError(
            "artifact_verify", f"Written artifact failed SHA-256: {destination}"
        )
    return code_sha, relative.as_posix()


def make_code_unit_id(
    snapshot_id: str,
    relative_path: str,
    unit: ExtractedUnit,
    code_sha256: str,
) -> str:
    material = "\0".join(
        [
            snapshot_id,
            relative_path,
            unit.code_unit_type,
            unit.aggregation_role,
            unit.qualified_name,
            str(unit.occurrence_index),
            str(unit.start_offset),
            str(unit.end_offset),
            code_sha256,
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def discover_python_files(snapshot_path: Path) -> list[Path]:
    files: list[Path] = []
    for path in snapshot_path.rglob("*.py"):
        try:
            relative_parts = path.relative_to(snapshot_path).parts
        except ValueError:
            continue
        if ".git" in relative_parts:
            continue
        if path.is_file() or path.is_symlink():
            files.append(path)
    return sorted(files, key=lambda value: value.relative_to(snapshot_path).as_posix())


def discover_snapshot_dirs(snapshot_root: Path) -> list[Path]:
    if not snapshot_root.is_dir():
        raise FileNotFoundError(f"Snapshot root not found: {snapshot_root}")

    direct_dirs = sorted(
        [path for path in snapshot_root.iterdir() if path.is_dir() and path.name != ".git"],
        key=lambda path: path.name,
    )
    candidates = [path for path in direct_dirs if discover_python_files(path)]
    if candidates:
        return candidates
    if discover_python_files(snapshot_root):
        return [snapshot_root]
    return []


def clean_manifest_value(row: dict[str, str], names: Iterable[str]) -> str:
    for name in names:
        value = str(row.get(name, "") or "").strip()
        if value:
            return value
    return ""


def read_manifest_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    if not path.is_file():
        raise FileNotFoundError(f"Snapshot manifest not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [
            {key: str(value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(stream)
        ]


def read_local_snapshot_metadata(snapshot_dir: Path) -> tuple[dict[str, str], str]:
    for name in (
        ".snapshot_metadata.json",
        "_snapshot_metadata.json",
        "snapshot_metadata.json",
    ):
        path = snapshot_dir / name
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise StageError(
                    "snapshot_metadata", f"Cannot parse {path}: {type(exc).__name__}: {exc}"
                ) from exc
            if not isinstance(raw, dict):
                raise StageError("snapshot_metadata", f"Metadata must be an object: {path}")
            return {str(key): str(value or "").strip() for key, value in raw.items()}, name
    return {}, ""


def manifest_row_commit(row: dict[str, str]) -> str:
    return clean_manifest_value(
        row, ("snapshot_commit", "latest_commit_effective", "commit_sha", "commit")
    )


def manifest_row_snapshot_id(row: dict[str, str]) -> str:
    return clean_manifest_value(
        row, ("snapshot_id", "repo_snapshot_key", "snapshot_key", "model_c_snapshot_key")
    )


def manifest_row_path(row: dict[str, str], manifest_path: Path | None) -> Path | None:
    value = clean_manifest_value(
        row,
        (
            "materialized_path",
            "snapshot_path",
            "snapshot_dir",
            "snapshot_directory",
            "local_snapshot_path",
        ),
    )
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute() and manifest_path is not None:
        path = manifest_path.parent / path
    return path.resolve(strict=False)


def match_manifest_row(
    snapshot_dir: Path,
    rows: Sequence[dict[str, str]],
    manifest_path: Path | None,
) -> tuple[dict[str, str], str]:
    if not rows:
        return {}, ""

    resolved_dir = snapshot_dir.resolve(strict=False)
    path_matches = [
        row for row in rows if manifest_row_path(row, manifest_path) == resolved_dir
    ]
    if len(path_matches) == 1:
        return path_matches[0], "manifest_explicit_path"

    name_lower = snapshot_dir.name.lower()
    id_matches = [
        row
        for row in rows
        if manifest_row_snapshot_id(row)
        and manifest_row_snapshot_id(row).lower() == name_lower
    ]
    if len(id_matches) == 1:
        return id_matches[0], "manifest_snapshot_id"

    commit_matches = []
    for row in rows:
        commit = manifest_row_commit(row).lower()
        if not commit:
            continue
        if commit in name_lower or commit[:12] in name_lower:
            commit_matches.append(row)
    if len(commit_matches) == 1:
        return commit_matches[0], "manifest_commit_in_directory_name"

    repo_commit_matches = []
    for row in rows:
        commit = manifest_row_commit(row).lower()
        repo_name = clean_manifest_value(row, ("repo_name",))
        repo_slug = repo_name.replace("/", "_").lower()
        if commit and repo_slug and repo_slug in name_lower and commit[:12] in name_lower:
            repo_commit_matches.append(row)
    if len(repo_commit_matches) == 1:
        return repo_commit_matches[0], "manifest_repo_commit_in_directory_name"

    return {}, ""


def normalize_snapshot_target(
    order: int,
    snapshot_dir: Path,
    local: dict[str, str],
    manifest: dict[str, str],
    metadata_source: str,
) -> SnapshotTarget:
    merged = dict(manifest)
    merged.update({key: value for key, value in local.items() if value})

    dataset_source = clean_manifest_value(merged, ("dataset_source", "source"))
    repo_name = clean_manifest_value(merged, ("repo_name", "repository"))
    repo_key = clean_manifest_value(merged, ("repo_key",)) or repo_name.lower()
    commit = manifest_row_commit(merged)
    snapshot_time = clean_manifest_value(
        merged,
        ("snapshot_time", "time", "first_panel_month", "month"),
    )
    first_panel_month = clean_manifest_value(merged, ("first_panel_month",))
    last_panel_month = clean_manifest_value(merged, ("last_panel_month",))
    repo_month_rows = clean_manifest_value(merged, ("repo_month_rows",))
    snapshot_id = manifest_row_snapshot_id(merged)

    if not snapshot_id:
        if dataset_source and repo_name and commit:
            digest = hashlib.sha256(
                f"{dataset_source}\0{repo_name}\0{commit}".encode("utf-8")
            ).hexdigest()[:16]
            snapshot_id = (
                f"{dataset_source}__{repo_name.replace('/', '_')}__{commit[:12]}__{digest}"
            )
        else:
            snapshot_id = snapshot_dir.name

    return SnapshotTarget(
        order=order,
        path=snapshot_dir.resolve(),
        snapshot_id=snapshot_id,
        dataset_source=dataset_source,
        repo_name=repo_name,
        repo_key=repo_key,
        snapshot_time=snapshot_time,
        snapshot_commit=commit,
        repo_month_rows=repo_month_rows,
        first_panel_month=first_panel_month,
        last_panel_month=last_panel_month,
        metadata_source=metadata_source or "directory_name_only",
    )


def build_snapshot_targets(
    snapshot_root: Path,
    snapshot_manifest: Path | None,
) -> list[SnapshotTarget]:
    dirs = discover_snapshot_dirs(snapshot_root)
    manifest_rows = read_manifest_rows(snapshot_manifest)
    targets: list[SnapshotTarget] = []

    for order, snapshot_dir in enumerate(dirs, start=1):
        local, local_source = read_local_snapshot_metadata(snapshot_dir)
        manifest, manifest_source = match_manifest_row(
            snapshot_dir, manifest_rows, snapshot_manifest
        )
        sources = [value for value in (manifest_source, local_source) if value]
        targets.append(
            normalize_snapshot_target(
                order,
                snapshot_dir,
                local,
                manifest,
                "+".join(sources),
            )
        )
    return targets


def prepare_output_directories(output_dir: Path, qc_dir: Path, overwrite: bool) -> None:
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Output directory is not empty; use --overwrite-output: {output_dir}"
        )
    if overwrite:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        if qc_dir.exists() and not str(qc_dir.resolve()).startswith(str(output_dir.resolve())):
            shutil.rmtree(qc_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    qc_dir.mkdir(parents=True, exist_ok=True)


def add_check(
    rows: list[dict[str, Any]],
    name: str,
    severity: str,
    passed: bool,
    observed: Any,
    expected: Any,
    note: str = "",
) -> None:
    rows.append(
        {
            "check_name": name,
            "severity": severity,
            "passed": bool(passed),
            "observed": observed,
            "expected": expected,
            "note": note,
        }
    )


def primary_overlap_count(code_units: Sequence[dict[str, Any]]) -> int:
    by_file: dict[tuple[str, str], list[tuple[int, int, str]]] = {}
    for row in code_units:
        if row["aggregation_role"] != "primary":
            continue
        key = (str(row["snapshot_id"]), str(row["relative_path"]))
        by_file.setdefault(key, []).append(
            (
                int(row["start_char_offset"]),
                int(row["end_char_offset"]),
                str(row["code_unit_id"]),
            )
        )

    overlaps = 0
    for spans in by_file.values():
        spans.sort()
        previous_end = -1
        for start, end, _ in spans:
            if start < previous_end:
                overlaps += 1
            previous_end = max(previous_end, end)
    return overlaps


def process_file(
    target: SnapshotTarget,
    path: Path,
    output_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    relative_path = safe_relative_path(path, target.path)
    base_file = {
        "snapshot_order": target.order,
        "snapshot_id": target.snapshot_id,
        "dataset_source": target.dataset_source,
        "repo_name": target.repo_name,
        "repo_key": target.repo_key,
        "snapshot_time": target.snapshot_time,
        "snapshot_commit": target.snapshot_commit,
        "relative_path": relative_path,
        "absolute_path": str(path.resolve(strict=False)),
        "file_sha256": "",
        "file_bytes": "",
        "source_encoding": "",
        "newline_style": "",
        "physical_line_count": "",
        "parse_status": "excluded",
        "parse_error_type": "",
        "parse_error_message": "",
        "module_docstring_removed": "",
        "module_docstring_removed_lines": "",
        "module_docstring_removed_utf8_bytes": "",
        "function_records": "",
        "method_records": "",
        "nested_function_records": "",
        "module_blocks": 0,
        "class_blocks": 0,
        "primary_code_units": 0,
        "diagnostic_overlap_units": 0,
    }
    exclusions: list[dict[str, Any]] = []

    if path.is_symlink():
        error = StageError("file_read", "Python path is a symbolic link; target is not followed")
        base_file["parse_error_type"] = type(error).__name__
        base_file["parse_error_message"] = str(error)
        exclusions.append(
            {
                "snapshot_id": target.snapshot_id,
                "dataset_source": target.dataset_source,
                "repo_name": target.repo_name,
                "snapshot_commit": target.snapshot_commit,
                "relative_path": relative_path,
                "qualified_name": "",
                "stage": error.stage,
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        )
        return base_file, [], exclusions

    try:
        payload = path.read_bytes()
        source, encoding = decode_python_source(payload)
        file_sha = sha256_bytes(payload)
        base_file.update(
            {
                "file_sha256": file_sha,
                "file_bytes": len(payload),
                "source_encoding": encoding,
                "newline_style": detect_newline_style(payload),
                "physical_line_count": count_physical_lines(source),
            }
        )
        units, stats = analyze_source(source, f"{target.snapshot_id}:{relative_path}")
    except Exception as exc:
        stage = exc.stage if isinstance(exc, StageError) else "file_preparation"
        base_file["parse_error_type"] = type(exc).__name__
        base_file["parse_error_message"] = str(exc)
        exclusions.append(
            {
                "snapshot_id": target.snapshot_id,
                "dataset_source": target.dataset_source,
                "repo_name": target.repo_name,
                "snapshot_commit": target.snapshot_commit,
                "relative_path": relative_path,
                "qualified_name": "",
                "stage": stage,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        )
        return base_file, [], exclusions

    base_file.update(
        {
            "parse_status": "prepared",
            "module_docstring_removed": stats["module_docstring_removed"],
            "module_docstring_removed_lines": stats["module_docstring_removed_lines"],
            "module_docstring_removed_utf8_bytes": stats[
                "module_docstring_removed_utf8_bytes"
            ],
            "function_records": stats["function_records"],
            "method_records": stats["method_records"],
            "nested_function_records": stats["nested_function_records"],
        }
    )

    for item in stats["unit_exclusions"]:
        exclusions.append(
            {
                "snapshot_id": target.snapshot_id,
                "dataset_source": target.dataset_source,
                "repo_name": target.repo_name,
                "snapshot_commit": target.snapshot_commit,
                "relative_path": relative_path,
                "qualified_name": item["qualified_name"],
                "stage": item["stage"],
                "error_type": item["error_type"],
                "error_message": item["error_message"],
            }
        )

    _, line_starts, _ = build_line_offsets(source)
    code_rows: list[dict[str, Any]] = []
    for unit in units:
        try:
            code_sha, artifact_relative = write_code_unit_artifact(output_dir, unit.text)
            code_unit_id = make_code_unit_id(
                target.snapshot_id, relative_path, unit, code_sha
            )
            start_line = offset_to_line(line_starts, unit.start_offset, len(source))
            end_line = offset_to_line(
                line_starts, max(unit.start_offset, unit.end_offset - 1), len(source)
            )
            code_rows.append(
                {
                    "snapshot_order": target.order,
                    "snapshot_id": target.snapshot_id,
                    "dataset_source": target.dataset_source,
                    "repo_name": target.repo_name,
                    "repo_key": target.repo_key,
                    "snapshot_time": target.snapshot_time,
                    "snapshot_commit": target.snapshot_commit,
                    "relative_path": relative_path,
                    "file_sha256": file_sha,
                    "code_unit_id": code_unit_id,
                    "code_unit_type": unit.code_unit_type,
                    "aggregation_role": unit.aggregation_role,
                    "qualified_name": unit.qualified_name,
                    "function_kind": unit.function_kind,
                    "occurrence_index": unit.occurrence_index,
                    "scope_kind": unit.scope_kind,
                    "scope_qualified_name": unit.scope_qualified_name,
                    "direct_statement_count": unit.direct_statement_count,
                    "leading_docstring_removed": unit.leading_docstring_removed,
                    "contains_nested_definition": unit.contains_nested_definition,
                    "start_line": start_line,
                    "end_line": end_line,
                    "start_char_offset": unit.start_offset,
                    "end_char_offset": unit.end_offset,
                    "code_unit_sha256": code_sha,
                    "code_unit_relative_path": artifact_relative,
                    "character_count": len(unit.text),
                    "utf8_byte_count": len(unit.text.encode("utf-8")),
                    "physical_line_count": count_physical_lines(unit.text),
                    "space_by_token_count": len(unit.text.split(" ")),
                    "nonempty_whitespace_token_count": len(unit.text.split()),
                }
            )
        except Exception as exc:
            stage = exc.stage if isinstance(exc, StageError) else "artifact_write"
            exclusions.append(
                {
                    "snapshot_id": target.snapshot_id,
                    "dataset_source": target.dataset_source,
                    "repo_name": target.repo_name,
                    "snapshot_commit": target.snapshot_commit,
                    "relative_path": relative_path,
                    "qualified_name": unit.qualified_name,
                    "stage": stage,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )

    base_file["module_blocks"] = sum(
        1 for row in code_rows if row["code_unit_type"] == "module_block"
    )
    base_file["class_blocks"] = sum(
        1 for row in code_rows if row["code_unit_type"] == "class_block"
    )
    base_file["primary_code_units"] = sum(
        1 for row in code_rows if row["aggregation_role"] == "primary"
    )
    base_file["diagnostic_overlap_units"] = sum(
        1 for row in code_rows if row["aggregation_role"] == "diagnostic_overlap"
    )
    return base_file, code_rows, exclusions


def run_self_test() -> None:
    source = (
        '"""module docs"""\n'
        "# keep this module comment\n"
        "CONFIG = 1\n"
        "\n"
        "def f():\n"
        '    """function docs"""\n'
        "\n"
        "    # implementation comment\n"
        "    x = 'é'\n"
        "    def nested():\n"
        "        return x\n"
        "    return nested()\n"
        "\n"
        "class C:\n"
        '    """class docs"""\n'
        "    value = 2\n"
        "\n"
        "    def m(self): return self.value  # inline\n"
        "\n"
        "if CONFIG:\n"
        "    def conditional():\n"
        "        return 3\n"
        "    RESULT = conditional()\n"
    )
    units, stats = analyze_source(source, "self_test.py")
    primary = [unit for unit in units if unit.aggregation_role == "primary"]
    diagnostic = [unit for unit in units if unit.aggregation_role == "diagnostic_overlap"]

    assert stats["module_docstring_removed"] is True
    assert any(unit.code_unit_type == "module_block" for unit in primary)
    assert any(unit.qualified_name == "f" and unit.code_unit_type == "function_body" for unit in primary)
    assert any(unit.code_unit_type == "class_block" and unit.scope_qualified_name == "C" for unit in primary)
    method = next(unit for unit in primary if unit.qualified_name == "C.m")
    assert method.code_unit_type == "method_body"
    assert "return self.value  # inline" in method.text
    function = next(unit for unit in primary if unit.qualified_name == "f")
    assert '"""function docs"""' not in function.text
    assert "# implementation comment" in function.text
    assert "    x = 'é'" in function.text
    assert any(unit.qualified_name == "f.nested" for unit in diagnostic)
    assert any(unit.qualified_name == "conditional" for unit in diagnostic)

    # Regression test for the production overlap bug found in A05 v1.
    # The outer if statement is represented by a primary module_block. The class
    # inside that compound statement and every descendant method must therefore
    # remain diagnostic_overlap so their source is not weighted twice.
    compound_class_source = (
        "FLAG = True\n"
        "if FLAG:\n"
        "    class ConditionalClass:\n"
        "        value = 1\n"
        "        def method(self):\n"
        "            return self.value\n"
    )
    compound_units, _ = analyze_source(compound_class_source, "compound_class.py")
    compound_primary = [
        unit for unit in compound_units if unit.aggregation_role == "primary"
    ]
    compound_diagnostic = [
        unit for unit in compound_units if unit.aggregation_role == "diagnostic_overlap"
    ]
    assert any(unit.code_unit_type == "module_block" for unit in compound_primary)
    assert any(
        unit.scope_qualified_name == "ConditionalClass"
        and unit.code_unit_type == "class_block"
        for unit in compound_diagnostic
    )
    assert any(
        unit.qualified_name == "ConditionalClass.method"
        and unit.code_unit_type == "method_body"
        for unit in compound_diagnostic
    )
    assert not any(
        unit.qualified_name == "ConditionalClass.method"
        for unit in compound_primary
    )
    compound_primary_spans = sorted(
        (unit.start_offset, unit.end_offset) for unit in compound_primary
    )
    compound_previous_end = -1
    for start, end in compound_primary_spans:
        assert start >= compound_previous_end, (start, end, compound_previous_end)
        compound_previous_end = end

    primary_spans = sorted((unit.start_offset, unit.end_offset) for unit in primary)
    previous_end = -1
    for start, end in primary_spans:
        assert start >= previous_end, (start, end, previous_end)
        previous_end = end

    one_line_source = "def one(): return 1  # keep\n"
    one_units, _ = analyze_source(one_line_source, "one.py")
    one = next(unit for unit in one_units if unit.qualified_name == "one")
    assert one.text == "return 1  # keep\n"

    crlf_payload = b"# coding: utf-8\r\ndef g():\r\n    return 1\r\n"
    decoded, encoding = decode_python_source(crlf_payload)
    assert encoding.lower().replace("_", "-") in {"utf-8", "utf-8-sig"}
    assert detect_newline_style(crlf_payload) == "CRLF"
    assert "\r\n" in decoded

    print("Self-test: PASS")


def run_pipeline(args: argparse.Namespace) -> int:
    if sys.version_info < (3, 12) and not args.allow_python_before_312:
        raise SystemExit(
            "ERROR: Python 3.12+ is required for production extraction; "
            f"found {sys.version.split()[0]}."
        )
    if args.expected_snapshots < 0:
        raise ValueError("--expected-snapshots must be non-negative")
    if args.progress_every_files < 0:
        raise ValueError("--progress-every-files must be non-negative")

    qc_dir = args.qc_dir if args.qc_dir is not None else args.output_dir / "qc"
    prepare_output_directories(args.output_dir, qc_dir, args.overwrite_output)

    targets = build_snapshot_targets(args.snapshot_root, args.snapshot_manifest)
    snapshot_rows: list[dict[str, Any]] = []
    file_rows: list[dict[str, Any]] = []
    code_rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    total_discovered_files = sum(len(discover_python_files(target.path)) for target in targets)
    processed_files = 0

    for target in targets:
        snapshot_files = discover_python_files(target.path)
        snapshot_file_rows: list[dict[str, Any]] = []
        snapshot_code_rows: list[dict[str, Any]] = []

        for path in snapshot_files:
            file_row, file_code_rows, file_exclusions = process_file(
                target, path, args.output_dir
            )
            snapshot_file_rows.append(file_row)
            snapshot_code_rows.extend(file_code_rows)
            exclusions.extend(file_exclusions)
            processed_files += 1
            if args.progress_every_files and processed_files % args.progress_every_files == 0:
                print(
                    f"Progress: files={processed_files}/{total_discovered_files}; "
                    f"snapshots_targeted={len(targets)}",
                    flush=True,
                )

        file_rows.extend(snapshot_file_rows)
        code_rows.extend(snapshot_code_rows)
        primary = [row for row in snapshot_code_rows if row["aggregation_role"] == "primary"]
        diagnostic = [
            row for row in snapshot_code_rows if row["aggregation_role"] == "diagnostic_overlap"
        ]
        snapshot_rows.append(
            {
                "snapshot_order": target.order,
                "snapshot_id": target.snapshot_id,
                "dataset_source": target.dataset_source,
                "repo_name": target.repo_name,
                "repo_key": target.repo_key,
                "snapshot_time": target.snapshot_time,
                "snapshot_commit": target.snapshot_commit,
                "repo_month_rows": target.repo_month_rows,
                "first_panel_month": target.first_panel_month,
                "last_panel_month": target.last_panel_month,
                "snapshot_path": str(target.path),
                "snapshot_dir_name": target.path.name,
                "metadata_source": target.metadata_source,
                "metadata_complete": target.metadata_complete,
                "python_files_discovered": len(snapshot_files),
                "python_files_prepared": sum(
                    row["parse_status"] == "prepared" for row in snapshot_file_rows
                ),
                "python_files_excluded": sum(
                    row["parse_status"] != "prepared" for row in snapshot_file_rows
                ),
                "primary_code_units": len(primary),
                "diagnostic_overlap_units": len(diagnostic),
                "function_bodies": sum(
                    row["code_unit_type"] == "function_body" for row in snapshot_code_rows
                ),
                "method_bodies": sum(
                    row["code_unit_type"] == "method_body" for row in snapshot_code_rows
                ),
                "module_blocks": sum(
                    row["code_unit_type"] == "module_block" for row in snapshot_code_rows
                ),
                "class_blocks": sum(
                    row["code_unit_type"] == "class_block" for row in snapshot_code_rows
                ),
                "code_unit_characters_primary": sum(
                    int(row["character_count"]) for row in primary
                ),
                "code_unit_utf8_bytes_primary": sum(
                    int(row["utf8_byte_count"]) for row in primary
                ),
                "space_by_tokens_primary": sum(
                    int(row["space_by_token_count"]) for row in primary
                ),
            }
        )

    prepared_files = sum(row["parse_status"] == "prepared" for row in file_rows)
    excluded_files = len(file_rows) - prepared_files
    primary_units = sum(row["aggregation_role"] == "primary" for row in code_rows)
    diagnostic_units = len(code_rows) - primary_units
    incomplete_metadata = sum(not bool(row["metadata_complete"]) for row in snapshot_rows)
    overlaps = primary_overlap_count(code_rows)
    duplicate_snapshot_ids = len(snapshot_rows) - len({row["snapshot_id"] for row in snapshot_rows})
    duplicate_file_keys = len(file_rows) - len(
        {(row["snapshot_id"], row["relative_path"]) for row in file_rows}
    )
    duplicate_unit_ids = len(code_rows) - len({row["code_unit_id"] for row in code_rows})

    artifact_failures = 0
    for row in code_rows:
        artifact = args.output_dir / str(row["code_unit_relative_path"])
        if not artifact.is_file() or sha256_bytes(artifact.read_bytes()) != row["code_unit_sha256"]:
            artifact_failures += 1

    expected_snapshots_ok = (
        args.expected_snapshots == 0 or len(snapshot_rows) == args.expected_snapshots
    )
    add_check(
        checks,
        "expected_snapshot_count",
        "hard",
        expected_snapshots_ok,
        len(snapshot_rows),
        args.expected_snapshots if args.expected_snapshots else "not_enforced",
    )
    add_check(
        checks,
        "snapshot_ids_unique",
        "hard",
        duplicate_snapshot_ids == 0,
        duplicate_snapshot_ids,
        0,
    )
    add_check(
        checks,
        "python_file_keys_unique",
        "hard",
        duplicate_file_keys == 0,
        duplicate_file_keys,
        0,
    )
    add_check(
        checks,
        "code_unit_ids_unique",
        "hard",
        duplicate_unit_ids == 0,
        duplicate_unit_ids,
        0,
    )
    add_check(
        checks,
        "python_file_reconciliation",
        "hard",
        len(file_rows) == prepared_files + excluded_files,
        len(file_rows),
        prepared_files + excluded_files,
    )
    add_check(
        checks,
        "primary_source_overlap_count",
        "hard",
        overlaps == 0,
        overlaps,
        0,
        "Primary code-unit character spans must not overlap within a file.",
    )
    add_check(
        checks,
        "artifact_sha256_integrity",
        "hard",
        artifact_failures == 0,
        artifact_failures,
        0,
    )
    add_check(
        checks,
        "snapshot_metadata_complete",
        "hard" if args.require_complete_metadata else "warning",
        incomplete_metadata == 0,
        incomplete_metadata,
        0,
        "Stable downstream joins require dataset_source, repo_name, and full commit SHA.",
    )

    snapshot_output = args.output_dir / "python_snapshot_manifest.csv"
    file_output = args.output_dir / "python_file_manifest.csv"
    code_output = args.output_dir / "python_code_unit_manifest.csv"
    exclusion_output = qc_dir / "python_snapshot_input_exclusions.csv"
    check_output = qc_dir / "python_snapshot_input_checks.csv"
    summary_output = qc_dir / "python_snapshot_input_summary.json"
    metadata_output = qc_dir / "python_snapshot_input_metadata.json"

    write_csv(snapshot_rows, SNAPSHOT_COLUMNS, snapshot_output)
    write_csv(file_rows, FILE_COLUMNS, file_output)
    write_csv(code_rows, CODE_UNIT_COLUMNS, code_output)
    write_csv(exclusions, EXCLUSION_COLUMNS, exclusion_output)
    write_csv(checks, CHECK_COLUMNS, check_output)

    hard_failures = sum(
        row["severity"] == "hard" and not row["passed"] for row in checks
    )
    warning_failures = sum(
        row["severity"] == "warning" and not row["passed"] for row in checks
    )
    if hard_failures:
        status = "FAIL"
    elif exclusions:
        status = "PASS_WITH_EXCLUSIONS"
    else:
        status = "PASS"

    summary = {
        "implementation_version": IMPLEMENTATION_VERSION,
        "status": status,
        "snapshots_discovered": len(snapshot_rows),
        "snapshots_with_complete_metadata": len(snapshot_rows) - incomplete_metadata,
        "snapshots_with_incomplete_metadata": incomplete_metadata,
        "python_files_discovered": len(file_rows),
        "python_files_prepared": prepared_files,
        "python_files_excluded": excluded_files,
        "primary_code_units": primary_units,
        "diagnostic_overlap_units": diagnostic_units,
        "function_bodies": sum(row["code_unit_type"] == "function_body" for row in code_rows),
        "method_bodies": sum(row["code_unit_type"] == "method_body" for row in code_rows),
        "module_blocks": sum(row["code_unit_type"] == "module_block" for row in code_rows),
        "class_blocks": sum(row["code_unit_type"] == "class_block" for row in code_rows),
        "exclusion_records": len(exclusions),
        "failed_checks": hard_failures,
        "warning_checks": warning_failures,
        "primary_source_overlap_count": overlaps,
        "artifact_integrity_failures": artifact_failures,
    }
    write_json(summary, summary_output)

    metadata = {
        "implementation_version": IMPLEMENTATION_VERSION,
        "python_version": sys.version,
        "python_executable": sys.executable,
        "snapshot_root": str(args.snapshot_root.resolve()),
        "snapshot_manifest": (
            str(args.snapshot_manifest.resolve()) if args.snapshot_manifest else ""
        ),
        "output_dir": str(args.output_dir.resolve()),
        "qc_dir": str(qc_dir.resolve()),
        "expected_snapshots": args.expected_snapshots,
        "require_complete_metadata": args.require_complete_metadata,
        "source_policy": {
            "input": "materialized_snapshot_files",
            "python_file_suffix": ".py",
            "ast_role": "scope_and_boundary_locator_only",
            "ast_unparse_used": False,
            "raw_source_slicing": True,
            "leading_module_class_function_docstrings_removed": True,
            "comments_blank_lines_repeated_spaces_preserved_within_slices": True,
            "primary_function_policy": "direct module/class functions only",
            "nested_overlap_policy": "diagnostic_overlap",
            "diagnostic_ancestor_policy": (
                "descendants of a class nested inside a compound statement remain "
                "diagnostic_overlap and cannot become primary again"
            ),
            "module_class_block_policy": "contiguous direct statements outside named definitions",
            "space_by_token_definition": "text.split(' ')",
            "scoring_windows_created": False,
            "npr_computed": False,
            "agc_hwc_classification": False,
        },
    }
    write_json(metadata, metadata_output)

    print(
        "Completed A01: "
        f"status={status}; snapshots={len(snapshot_rows)}; files={len(file_rows)}; "
        f"prepared_files={prepared_files}; excluded_files={excluded_files}; "
        f"primary_units={primary_units}; diagnostic_units={diagnostic_units}; "
        f"failed_checks={hard_failures}",
        flush=True,
    )
    return 0 if hard_failures == 0 else 1


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0
    return run_pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())
