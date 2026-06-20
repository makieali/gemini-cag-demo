"""In-memory, per-session store for knowledge bases and their stats.

This is deliberately simple for a demo: state lives in process memory keyed by a
session id. For multi-process or production use, swap this for Redis or a
database -- the rest of the app only depends on the small surface below.
"""
from __future__ import annotations

import threading
from typing import Optional

from .analytics import SessionStats
from .models import KnowledgeBase


class SessionStore:
    """Thread-safe map of session id -> (KnowledgeBase, SessionStats)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._kb: dict[str, KnowledgeBase] = {}
        self._stats: dict[str, SessionStats] = {}

    def set_kb(self, session_id: str, kb: KnowledgeBase) -> None:
        with self._lock:
            self._kb[session_id] = kb
            self._stats[session_id] = SessionStats()

    def get_kb(self, session_id: str) -> Optional[KnowledgeBase]:
        with self._lock:
            return self._kb.get(session_id)

    def record_query(self, session_id: str, result) -> SessionStats:
        with self._lock:
            stats = self._stats.get(session_id, SessionStats()).add(result)
            self._stats[session_id] = stats
            return stats

    def get_stats(self, session_id: str) -> SessionStats:
        with self._lock:
            return self._stats.get(session_id, SessionStats())

    def clear(self, session_id: str) -> Optional[KnowledgeBase]:
        with self._lock:
            kb = self._kb.pop(session_id, None)
            self._stats.pop(session_id, None)
            return kb
