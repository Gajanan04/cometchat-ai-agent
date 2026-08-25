"""Early extractive baseline used only for comparison in the evaluation suite."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.rag.chunker import Chunk, chunk_documents
from app.rag.loader import load_documents
from app.tools.order_tool import lookup_order


_ORDER = re.compile(r"\bORD[- ]?\d{4}\b", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"a", "an", "and", "are", "can", "do", "for", "how", "i", "is", "it", "my", "of", "or", "the", "to", "what", "when", "where", "with", "you"}


@dataclass(frozen=True)
class BaselineSource:
    filename: str
    heading: str


@dataclass(frozen=True)
class BaselineResult:
    answer: str
    sources: list[BaselineSource]
    handoff: dict[str, bool]
    tool_calls: list[dict]


class ExtractiveBaseline:
    """A pre-improvement comparison: one raw lexical match or one safe lookup.

    It deliberately has no authority filtering, conflict handling, bespoke policy
    responses, or session memory. It is not part of the customer-facing agent.
    """

    def __init__(self, repository_root: str | Path) -> None:
        root = Path(repository_root)
        self.chunks = chunk_documents(load_documents(root / "knowledge-base"))
        self.orders_path = root / "data" / "orders.json"

    def chat(self, session_id: str, message: str) -> BaselineResult:
        del session_id
        order_id = _ORDER.search(message)
        if order_id:
            lookup = lookup_order(order_id.group(0), self.orders_path)
            answer = lookup.order["customer_safe_message"] if lookup.found else (lookup.error or "Order lookup failed.")
            return BaselineResult(
                answer=answer,
                sources=[],
                handoff={"recommended": False},
                tool_calls=[{"name": "order_lookup", "arguments": {"order_id": order_id.group(0)}, "found": lookup.found}],
            )

        match = self._top_match(message)
        if match is None:
            return BaselineResult("No matching passage was found.", [], {"recommended": False}, [])
        return BaselineResult(match.text, [BaselineSource(match.filename, match.heading)], {"recommended": False}, [])

    def _top_match(self, query: str) -> Chunk | None:
        query_words = _terms(query)
        candidates = []
        for chunk in self.chunks:
            overlap = len(query_words & _terms(f"{chunk.heading} {chunk.text}"))
            if overlap:
                candidates.append((chunk, overlap))
        if not candidates:
            return None
        return min(candidates, key=lambda item: (-item[1], item[0].filename, item[0].heading))[0]


def _terms(text: str) -> set[str]:
    return {word for word in _WORD.findall(text.lower()) if word not in _STOP}
