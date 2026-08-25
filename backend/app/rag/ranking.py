"""Document precedence and conflict helpers; no documents are removed at load time."""
from __future__ import annotations

from .chunker import Chunk


def authority_score(chunk: Chunk) -> int:
    metadata = chunk.metadata
    score = 0
    if metadata.get("status") == "active":
        score += 40
    if metadata.get("policy_authority") == "official":
        score += 30
    if metadata.get("audience") == "customer":
        score += 20
    if metadata.get("customer_answering") is False:
        score -= 100
    if metadata.get("status") in {"superseded", "draft"}:
        score -= 40
    return score


def customer_authoritative(chunks: list[Chunk]) -> list[Chunk]:
    """Return ranked candidates suitable for customer-facing grounding."""
    return sorted(
        [chunk for chunk in chunks if authority_score(chunk) > 0],
        key=lambda chunk: (-authority_score(chunk), chunk.filename, chunk.heading),
    )


def detect_conflict(chunks: list[Chunk]) -> bool:
    """Identify explicit opposing care guidance among current authoritative chunks."""
    texts = " ".join(chunk.text.lower() for chunk in customer_authoritative(chunks))
    return "hand-wash" in texts and "dishwasher safe" in texts
