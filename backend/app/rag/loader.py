"""Deterministic loading of Markdown knowledge-base documents.

This module only reads and represents source documents. It does not filter
documents, determine authority, or make retrieval decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


_FRONT_MATTER_DELIMITER = "---"
_KEY_VALUE_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")
_HEADING_PATTERN = re.compile(r"^(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")


class FrontMatterError(ValueError):
    """Raised when a document begins with malformed YAML front matter."""


@dataclass(frozen=True)
class MarkdownHeading:
    """An ATX Markdown heading preserved from a document."""

    level: int
    text: str
    line_number: int


@dataclass(frozen=True)
class KnowledgeDocument:
    """A source document and its parsed, non-interpreted metadata."""

    filename: str
    text: str
    body: str
    metadata: dict[str, Any]
    headings: tuple[MarkdownHeading, ...]
    has_front_matter: bool


def load_documents(knowledge_base_dir: str | Path) -> list[KnowledgeDocument]:
    """Load every top-level Markdown document in deterministic filename order."""

    directory = Path(knowledge_base_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"Knowledge-base directory does not exist: {directory}")
    paths = sorted(directory.glob("*.md"), key=lambda path: path.name.casefold())
    return [load_document(path) for path in paths]


def load_document(path: str | Path) -> KnowledgeDocument:
    """Read one Markdown document without changing its source text."""

    document_path = Path(path)
    text = document_path.read_text(encoding="utf-8")
    metadata, body, body_start_line, has_front_matter = _split_front_matter(text, document_path)
    return KnowledgeDocument(
        filename=document_path.name,
        text=text,
        body=body,
        metadata=metadata,
        headings=_extract_headings(body, body_start_line),
        has_front_matter=has_front_matter,
    )


def _split_front_matter(text: str, path: Path) -> tuple[dict[str, Any], str, int, bool]:
    """Split leading YAML front matter from content, retaining missing-FM state."""

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != _FRONT_MATTER_DELIMITER:
        return {}, text, 1, False
    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == _FRONT_MATTER_DELIMITER),
        None,
    )
    if closing_index is None:
        raise FrontMatterError(f"{path}: opening front matter delimiter has no closing delimiter")
    metadata = _parse_yaml_mapping("".join(lines[1:closing_index]), path)
    body = "".join(lines[closing_index + 1:])
    return metadata, body, closing_index + 2, True


def _parse_yaml_mapping(text: str, path: Path) -> dict[str, Any]:
    """Parse the flat YAML mapping used by the supplied document front matter.

    Nested mappings and sequences fail explicitly rather than being partially
    parsed and silently corrupted. Dates remain strings to preserve source
    values exactly.
    """

    metadata: dict[str, Any] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=2):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line[0].isspace() or raw_line.lstrip().startswith("-"):
            raise FrontMatterError(f"{path}:{line_number}: nested YAML values are not supported")
        match = _KEY_VALUE_PATTERN.match(raw_line)
        if match is None:
            raise FrontMatterError(f"{path}:{line_number}: expected 'key: value'")
        key, value = match.groups()
        if key in metadata:
            raise FrontMatterError(f"{path}:{line_number}: duplicate metadata key '{key}'")
        metadata[key] = _parse_yaml_scalar(value, path, line_number)
    return metadata


def _parse_yaml_scalar(value: str, path: Path, line_number: int) -> Any:
    """Parse common scalar YAML values while preserving dates as strings."""

    value = _strip_unquoted_comment(value).strip()
    if value == "":
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value.startswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError as error:
            raise FrontMatterError(f"{path}:{line_number}: invalid double-quoted YAML string") from error
    if value.startswith("'"):
        if not value.endswith("'") or len(value) == 1:
            raise FrontMatterError(f"{path}:{line_number}: unterminated single-quoted string")
        return value[1:-1].replace("''", "'")
    if value[0] in "[{":
        raise FrontMatterError(f"{path}:{line_number}: collection metadata values are not supported")
    return value


def _strip_unquoted_comment(value: str) -> str:
    """Remove a YAML comment only when its hash is outside quoted text."""

    quote: str | None = None
    for index, character in enumerate(value):
        if character in {"'", '"'}:
            quote = None if quote == character else character if quote is None else quote
        elif character == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index]
    return value


def _extract_headings(text: str, start_line: int) -> tuple[MarkdownHeading, ...]:
    """Return all ATX headings in source order with original line numbers."""

    headings: list[MarkdownHeading] = []
    for offset, line in enumerate(text.splitlines(), start=start_line):
        match = _HEADING_PATTERN.match(line)
        if match is not None:
            hashes, heading_text = match.groups()
            headings.append(MarkdownHeading(len(hashes), heading_text.strip(), offset))
    return tuple(headings)
