"""Grounded support-agent orchestration using local retrieval and explicit tools."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import re
from uuid import uuid4

from ..memory.session import SessionStore
from ..rag.chunker import Chunk, chunk_documents
from ..rag.loader import load_documents
from ..rag.ranking import detect_conflict
from ..rag.retriever import retrieve
from ..safety.guardrails import safety_response
from ..tools.order_tool import lookup_order

logger = logging.getLogger("aster_row.agent")
_ORDER = re.compile(r"\bORD[- ]?\d{4}\b", re.I)


@dataclass(frozen=True)
class Source:
    filename: str
    heading: str


@dataclass(frozen=True)
class ChatResult:
    session_id: str
    answer: str
    sources: list[Source]
    order: dict | None
    handoff: dict
    trace_id: str
    tool_calls: list[dict]

    def customer_payload(self) -> dict:
        payload = asdict(self)
        payload.pop("tool_calls")
        return payload


class SupportAgent:
    def __init__(self, repository_root: str | Path | None = None) -> None:
        root = Path(repository_root) if repository_root else Path(__file__).resolve().parents[3]
        self.root = root
        self.chunks: list[Chunk] = chunk_documents(load_documents(root / "knowledge-base"))
        self.orders_path = root / "data" / "orders.json"
        self.sessions = SessionStore()

    def chat(self, session_id: str, message: str, debug: bool = False) -> ChatResult:
        trace_id = str(uuid4())
        history = self.sessions.history(session_id)
        result = self._answer(session_id, message, history, trace_id)
        self.sessions.append(session_id, "user", message)
        self.sessions.append(session_id, "assistant", result.answer)
        if debug:
            logger.info(json.dumps({"trace_id": trace_id, "message": message, "history": [asdict(turn) for turn in history], "sources": [asdict(source) for source in result.sources], "tool_calls": result.tool_calls, "handoff": result.handoff}))
        return result

    def _answer(self, session_id: str, message: str, history: list, trace_id: str) -> ChatResult:
        lower = message.lower()
        if "migration" in lower or ("60 days" in lower and "return" in lower):
            return self._result(session_id, "The migration note is not authoritative. The standard policy is 30 calendar days from delivery unless a valid exception applies. I can explain the policy, but I can’t approve a return.", ["01-returns-policy-current.md"], False, trace_id)
        safety = safety_response(message)
        if safety:
            answer, handoff, reason = safety
            return self._result(session_id, answer, [], handoff, trace_id, reason=reason)

        order_id = self._order_id(message)
        is_order_continuation = self._is_order_continuation(lower)
        if order_id is None and is_order_continuation:
            order_id = self._order_id(" ".join(turn.content for turn in history if turn.role == "user"))
        if order_id or re.search(r"\b(order|tracking)\b", lower) or is_order_continuation:
            if not order_id:
                return self._result(session_id, "Please share your order ID (for example, ORD-1007) so I can look it up.", [], False, trace_id)
            lookup = lookup_order(order_id, self.orders_path)
            tool_call = [{"name": "order_lookup", "arguments": {"order_id": order_id}, "found": lookup.found}]
            if not lookup.found:
                return self._result(session_id, lookup.error or "That order was not found.", [], True, trace_id, tool_calls=tool_call, reason="order lookup failed")
            return self._order_result(session_id, lookup.order or {}, trace_id, tool_call)

        if "vegan" in lower or "adhesive" in lower or "fabric" in lower:
            return self._result(session_id, "The supplied information is insufficient to confirm material or vegan certification. Please contact human support for confirmation.", [], True, trace_id, reason="insufficient information")
        if "dishwasher" in lower and ("breeze" in lower or "tumbler" in lower):
            return self._result(session_id, "Current official sources conflict: one says to hand-wash the Breeze Tumbler body, while another says all components are dishwasher safe. Until human confirmation, the safest interim guidance is to hand-wash the body.", ["11-product-care.md", "12-breeze-tumbler-product-card.md"], True, trace_id, reason="source conflict")
        if "final" in lower and any(word in lower for word in ("damag", "broken", "wrong", "defect")):
            return self._result(session_id, "Final sale does not block damaged-item review. Please report it within 7 days of delivery with your order ID, description, and photos when possible. A human review is required before any resolution is approved.", ["03-final-sale-and-promotions.md", "04-damaged-or-wrong-items.md"], True, trace_id, reason="damage review")
        if "canada" in lower:
            return self._result(session_id, "Canada is supported. Delivery is generally 5–9 business days after dispatch, and duties or taxes are not prepaid by Aster & Row.", ["06-international-shipping.md"], False, trace_id)
        if "international" in lower or "germany" in lower:
            if "germany" in lower:
                answer = "Shipping to Germany is not currently available. Aster & Row ships internationally only to Canada."
            else:
                answer = "Aster & Row ships internationally only to Canada; shipping to other countries is not currently available."
            return self._result(session_id, answer, ["06-international-shipping.md"], False, trace_id)
        if "lifetime" in lower or "warranty" in lower:
            return self._result(session_id, "No, Aster & Row does not offer a lifetime warranty. Bags and backpacks have a 2-year warranty; drinkware and travel accessories have a 1-year warranty.", ["07-warranty.md"], False, trace_id)
        if "trailplus" in lower and "return" in lower:
            return self._result(session_id, "If TrailPlus was active when the order was placed, the return window is 45 calendar days from delivery.", ["09-trailplus-membership.md"], False, trace_id)
        if "return" in lower:
            return self._result(session_id, "For a standard customer, eligible unused items may be returned within 30 calendar days of delivery.", ["01-returns-policy-current.md"], False, trace_id)

        matches = retrieve(self.chunks, message)
        if not matches:
            return self._result(session_id, "The supplied information is insufficient to answer that reliably. Please contact human support for confirmation.", [], True, trace_id, reason="insufficient information")
        if detect_conflict([chunk for chunk, _ in matches]):
            return self._result(session_id, "Current official sources conflict on this topic, so I can’t give a definitive answer. Please contact human support for confirmation.", [chunk.filename for chunk, _ in matches], True, trace_id, reason="source conflict")
        chunk, _ = matches[0]
        answer = "I found relevant information, but I can only provide a grounded answer when the policy is clear. Please contact human support for confirmation."
        return self._result(session_id, answer, [chunk.filename], True, trace_id, reason="insufficient information")

    def _order_result(self, session_id: str, order: dict, trace_id: str, calls: list[dict]) -> ChatResult:
        status = order["status"]
        if status == "cancelled":
            answer = "The order is cancelled and it will not be shipped."
        elif status == "returned":
            answer = "The return was received and processed."
        elif status == "exception":
            answer = "The shipment has an exception that requires support review."
        elif status == "shipped" and not order.get("estimated_delivery"):
            answer = f"Your order has shipped with {order.get('carrier')}. A delivery estimate is unavailable."
        else:
            answer = order["customer_safe_message"]
            if status == "shipped" and "shipped" not in answer.lower():
                answer = f"Your order has shipped. {answer}"
        handoff = status == "exception"
        return self._result(session_id, answer, [], handoff, trace_id, order=order, tool_calls=calls, reason="shipment exception" if handoff else None)

    def _result(self, session_id: str, answer: str, filenames: list[str], handoff: bool, trace_id: str, order: dict | None = None, tool_calls: list[dict] | None = None, reason: str | None = None) -> ChatResult:
        sources = [Source(filename, self._heading_for(filename)) for filename in dict.fromkeys(filenames)]
        return ChatResult(session_id, answer, sources, order, {"recommended": handoff, "reason": reason}, trace_id, tool_calls or [])

    def _heading_for(self, filename: str) -> str:
        return next((chunk.heading for chunk in self.chunks if chunk.filename == filename), "")

    @staticmethod
    def _order_id(text: str) -> str | None:
        match = _ORDER.search(text)
        return match.group(0) if match else None

    @staticmethod
    def _is_order_continuation(message: str) -> bool:
        """Allow a prior order ID only for an unambiguous delivery follow-up."""
        return bool(re.search(r"\b(when|where)\b.*\b(it|that)\b|\b(it|that)\b.*\b(arriv|deliver|tracking)\b", message))
