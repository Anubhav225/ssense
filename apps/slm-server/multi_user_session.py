#!/usr/bin/env python3
"""
multi_user_session.py — In-Memory Multi-User Multi-Turn Conversation Manager

Maintains per-(user_id, domain) conversation context for up to 10k+ concurrent users.
Features:
  - Keyed by (user_id, domain) to isolate users and sites.
  - Rolling window: keeps last 5 turns (10 messages: user + assistant).
  - 30-minute inactivity TTL per session.
  - Automatic lazy pruning and capacity bounds to protect RAM integrity.
"""

import asyncio
import time
from typing import Dict, List, Optional, Tuple


MAX_TURNS_PER_SESSION = 5
SESSION_TTL_SECONDS = 30 * 60  # 30 minutes


class UserDomainSession:
    def __init__(self, user_id: str, domain: str):
        self.user_id = user_id
        self.domain = domain
        self.turns: List[Tuple[str, str]] = []  # List of (user_prompt, assistant_response)
        self.last_active = time.time()

    def touch(self) -> None:
        self.last_active = time.time()

    def is_expired(self, now: Optional[float] = None) -> bool:
        current = now if now is not None else time.time()
        return (current - self.last_active) > SESSION_TTL_SECONDS

    def add_turn(self, user_prompt: str, assistant_response: str) -> None:
        self.touch()
        self.turns.append((user_prompt, assistant_response))
        if len(self.turns) > MAX_TURNS_PER_SESSION:
            self.turns = self.turns[-MAX_TURNS_PER_SESSION:]

    def get_turns(self) -> List[Tuple[str, str]]:
        self.touch()
        return list(self.turns)

    def format_history_for_prompt(self) -> str:
        """
        Formats previous turns into ChatML format suitable for injection
        into the prompt prior to the current question.
        """
        if not self.turns:
            return ""
        formatted = []
        for u, a in self.turns:
            formatted.append(f"<|im_start|>user\n{u}<|im_end|>\n<|im_start|>assistant\n{a}<|im_end|>")
        return "\n".join(formatted)


class MultiUserSessionManager:
    def __init__(self, max_sessions: int = 20_000):
        self._sessions: Dict[str, UserDomainSession] = {}
        self._lock = asyncio.Lock()
        self._max_sessions = max_sessions

    @staticmethod
    def _make_key(user_id: str, domain: str) -> str:
        d = domain.strip().lower()
        for pfx in ("www.", "en.", "m.", "app."):
            if d.startswith(pfx):
                d = d[len(pfx):]
        return f"{user_id.strip()}::{d}"

    async def get_history(self, user_id: str, domain: str) -> List[Tuple[str, str]]:
        key = self._make_key(user_id, domain)
        async with self._lock:
            session = self._sessions.get(key)
            if not session:
                return []
            if session.is_expired():
                del self._sessions[key]
                return []
            return session.get_turns()

    async def get_history_prompt(self, user_id: str, domain: str) -> str:
        key = self._make_key(user_id, domain)
        async with self._lock:
            session = self._sessions.get(key)
            if not session:
                return ""
            if session.is_expired():
                del self._sessions[key]
                return ""
            return session.format_history_for_prompt()

    async def record_turn(self, user_id: str, domain: str, user_prompt: str, assistant_response: str) -> None:
        key = self._make_key(user_id, domain)
        now = time.time()
        async with self._lock:
            # Check capacity and lazy prune if near ceiling
            if len(self._sessions) >= self._max_sessions:
                expired = [k for k, s in self._sessions.items() if s.is_expired(now)]
                for k in expired:
                    del self._sessions[k]
                # If still over max, evict oldest 10%
                if len(self._sessions) >= self._max_sessions:
                    sorted_sessions = sorted(self._sessions.items(), key=lambda item: item[1].last_active)
                    for k, _ in sorted_sessions[: self._max_sessions // 10]:
                        del self._sessions[k]

            session = self._sessions.get(key)
            if not session or session.is_expired(now):
                session = UserDomainSession(user_id, domain)
                self._sessions[key] = session
            session.add_turn(user_prompt, assistant_response)

    async def clear_session(self, user_id: str, domain: str) -> None:
        key = self._make_key(user_id, domain)
        async with self._lock:
            self._sessions.pop(key, None)

    async def cleanup_expired(self) -> int:
        now = time.time()
        async with self._lock:
            expired = [k for k, s in self._sessions.items() if s.is_expired(now)]
            for k in expired:
                del self._sessions[k]
            return len(expired)

    @property
    def active_session_count(self) -> int:
        return len(self._sessions)


multi_user_session_manager = MultiUserSessionManager()
