"""Heading-aware chunks for small Markdown knowledge bases."""
from __future__ import annotations

from dataclasses import dataclass

from .loader import KnowledgeDocument


@dataclass(frozen=True)
class Chunk:
    filename: str
    heading: str
    text: str
    metadata: dict


def chunk_documents(documents: list[KnowledgeDocument]) -> list[Chunk]:
    """Split documents on headings, retaining document metadata on every chunk."""
    chunks: list[Chunk] = []
    for document in documents:
        current_heading = document.headings[0].text if document.headings else document.filename
        lines: list[str] = []
        for line in document.body.splitlines():
            if line.startswith("#") and line.lstrip("#").startswith(" "):
                if lines:
                    chunks.append(_chunk(document, current_heading, "\n".join(lines)))
                current_heading = line.lstrip("#").strip()
                lines = [line]
            else:
                lines.append(line)
        if lines:
            chunks.append(_chunk(document, current_heading, "\n".join(lines)))
    return [chunk for chunk in chunks if chunk.text.strip()]


def _chunk(document: KnowledgeDocument, heading: str, text: str) -> Chunk:
    return Chunk(document.filename, heading, text.strip(), dict(document.metadata))
