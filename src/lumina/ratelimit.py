"""Request rate limits for the expensive endpoints (/chat, /tts), per person.

A chat turn costs several seconds of the local models, so one client sending in a
loop would make Lumina unusable for everyone else.  The limits are far above how fast a person types or
listens; they only stop automated floods.

Keyed by account when signed in, otherwise by client address (the API runs behind nginx with proxy
headers, so this is the real address).  In memory, per process: a restart forgets the counts, which is
acceptable for abuse protection.  Nothing about the request is kept beyond the key and timestamps.
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict, deque

_MAX_KEYS = 10_000          # oldest keys are forgotten beyond this, so memory stays bounded


class RateLimiter:
    """Sliding windows: e.g. [(12, 60), (200, 3600)] = at most 12 per minute and 200 per hour."""

    def __init__(self, limits: list[tuple[int, float]], clock=time.monotonic):
        self.limits = sorted(limits, key=lambda limit: limit[1])
        self._longest = self.limits[-1][1]
        self._hits: OrderedDict[str, deque] = OrderedDict()
        self._lock = threading.Lock()
        self._clock = clock

    def hit(self, key: str) -> float | None:
        """Count one request for `key`.  Returns None if allowed, else seconds until one is allowed again.
        A refused request is not counted."""
        now = self._clock()
        with self._lock:
            q = self._hits.pop(key, deque())
            while q and now - q[0] >= self._longest:
                q.popleft()
            wait = 0.0
            for count, window in self.limits:
                recent = [t for t in q if now - t < window]
                if len(recent) >= count:
                    wait = max(wait, window - (now - recent[-count]))
            if wait <= 0:
                q.append(now)
            self._hits[key] = q                       # most recently used last
            while len(self._hits) > _MAX_KEYS:
                self._hits.popitem(last=False)
        return None if wait <= 0 else wait

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_key(request, user: dict | None) -> str:
    if user is not None:
        return f"user:{user['id']}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def retry_after(seconds: float) -> str:
    return str(max(1, math.ceil(seconds)))
