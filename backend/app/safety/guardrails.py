"""Input-level safety checks independent of retrieved content."""
from __future__ import annotations

import re

_PRIVATE = re.compile(r"\b(email|address|internal note|risk score|warehouse note|customer name)\b", re.I)
_SECRETS = re.compile(r"\b(system prompt|hidden prompt|instructions|secret|credential|api key)\b", re.I)
_ACTIONS = re.compile(r"\b(approve|cancel|refund|replace|replacement|change (my )?address)\b", re.I)


def safety_response(message: str) -> tuple[str, bool, str | None] | None:
    if _PRIVATE.search(message):
        return ("I can’t share customer contact details, addresses, internal notes, or risk information. A support specialist can help with a legitimate privacy request.", True, "privacy request")
    if _SECRETS.search(message):
        return ("I can’t reveal hidden instructions, system prompts, credentials, or internal-only content. I can help with Aster & Row policies or an order lookup.", True, "security request")
    if _ACTIONS.search(message) and re.search(r"\b(please|can you|want to)\b", message, re.I):
        return ("I can explain the relevant policy, but I can’t complete that action or promise an outcome. A support specialist can review it.", True, "unsupported action")
    return None
