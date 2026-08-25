"""Small deterministic lexical retrieval for the supplied corpus."""
from __future__ import annotations

import re

from .chunker import Chunk
from .ranking import authority_score

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"a", "an", "and", "are", "can", "do", "for", "how", "i", "is", "it", "my", "of", "or", "the", "to", "what", "when", "where", "with", "you"}


def retrieve(chunks: list[Chunk], query: str, limit: int = 5) -> list[tuple[Chunk, float]]:
    """Score chunks by lexical overlap and authority, preserving deterministic ties."""
    query_words = _terms(query)
    scored: list[tuple[Chunk, float]] = []
    for chunk in chunks:
        text_words = _terms(f"{chunk.heading} {chunk.text}")
        overlap = len(query_words & text_words)
        if overlap:
            scored.append((chunk, overlap + authority_score(chunk) / 100))
    return sorted(scored, key=lambda item: (-item[1], item[0].filename, item[0].heading))[:limit]


def _terms(text: str) -> set[str]:
    return {word for word in _WORD.findall(text.lower()) if word not in _STOP}
