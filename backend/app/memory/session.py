"""Bounded in-memory session context."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Turn:
    role: str
    content: str


class SessionStore:
    def __init__(self, max_turns: int = 8) -> None:
        self.max_turns = max_turns
        self._sessions: dict[str, list[Turn]] = defaultdict(list)

    def history(self, session_id: str) -> list[Turn]:
        return list(self._sessions[session_id])

    def append(self, session_id: str, role: str, content: str) -> None:
        self._sessions[session_id].append(Turn(role, content))
        self._sessions[session_id] = self._sessions[session_id][-self.max_turns:]

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
