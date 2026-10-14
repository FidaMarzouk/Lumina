"""Login tokens: random, opaque, stored only as SHA-256 hashes, valid for AUTH_TOKEN_TTL_DAYS."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from ..config import AUTH_TOKEN_TTL_DAYS, LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_S
from ..memory.store import Store, parse_iso, utcnow


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue(store: Store, user_id: str, now: datetime | None = None) -> str:
    now = now or utcnow()
    token = secrets.token_urlsafe(32)
    store.add_token(_hash(token), user_id, now + timedelta(days=AUTH_TOKEN_TTL_DAYS), now=now)
    return token


def resolve(store: Store, token: str, now: datetime | None = None) -> dict | None:
    """The user the token belongs to, or None if it is unknown or expired."""
    if not token:
        return None
    row = store.get_token(_hash(token))
    if row is None:
        return None
    if parse_iso(row["expires_at"]) <= (now or utcnow()):
        store.delete_token(row["token_hash"])
        return None
    return store.get_user(row["user_id"])


def revoke(store: Store, token: str) -> None:
    store.delete_token(_hash(token))


class LoginLimiter:
    """At most LOGIN_MAX_ATTEMPTS failed logins per key (email + client address) in LOGIN_WINDOW_S."""

    def __init__(self, max_attempts: int = LOGIN_MAX_ATTEMPTS, window_s: float = LOGIN_WINDOW_S):
        self.max_attempts, self.window_s = max_attempts, window_s
        self._failures: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque:
        q = self._failures[key]
        while q and now - q[0] > self.window_s:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.max_attempts

    def failed(self, key: str) -> None:
        with self._lock:
            self._prune(key, time.monotonic()).append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
