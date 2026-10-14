"""Polite HTTP client shared by every collector.

Guarantees, for every request:
  * robots.txt is checked (cached per host) — a disallowed URL raises RobotsDisallowed, it is never fetched
  * per-host minimum interval + jitter (rate limit)
  * retries with exponential backoff; HTTP 429/503 honour Retry-After
  * an honest User-Agent (no browser impersonation, no rotating agents)
  * optional on-disk response cache, so re-runs and parser changes do not re-hit the site

Every call is recorded in `self.log` (url, status, from_cache, robots decision) for the run manifest.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .robots import Robots

log = logging.getLogger(__name__)

USER_AGENT = "LuminaResearch/0.2 (non-commercial research; respects robots.txt)"
_DISALLOW_ALL = "User-agent: *\nDisallow: /"


class RobotsDisallowed(RuntimeError):
    pass


class FetchFailed(RuntimeError):
    pass


@dataclass
class Response:
    url: str
    final_url: str
    status: int
    text: str
    fetched_at: str
    from_cache: bool


@dataclass
class PoliteClient:
    min_interval_s: float = 6.0
    jitter_s: float = 1.0
    max_retries: int = 4
    timeout_s: float = 30.0
    cache_dir: Path | None = None
    user_agent: str = USER_AGENT
    log: list[dict] = field(default_factory=list)
    _robots: dict[str, Robots] = field(default_factory=dict)
    _last: dict[str, float] = field(default_factory=dict)
    _client: httpx.Client | None = None

    # ── public ────────────────────────────────────────────────────────────────
    def get(self, url: str) -> Response:
        if not self.allowed(url):
            self.log.append({"url": url, "robots": "disallowed"})
            raise RobotsDisallowed(url)
        cached = self._cache_get(url)
        if cached:
            self.log.append({"url": url, "robots": "allowed", "status": cached.status, "from_cache": True})
            return cached
        resp = self._fetch(url)
        self._cache_put(resp)
        self.log.append({"url": url, "robots": "allowed", "status": resp.status, "from_cache": False})
        return resp

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            try:
                r = self._http().get(f"{host}/robots.txt")
                # RFC 9309: 4xx → no restrictions; 5xx / unreachable → assume complete disallow
                if r.status_code < 400:
                    text = r.text
                elif r.status_code < 500:
                    text = ""
                else:
                    text = _DISALLOW_ALL
            except httpx.HTTPError:
                log.warning("robots.txt unreachable for %s — treating as disallowed", host)
                text = _DISALLOW_ALL
            self._robots[host] = Robots(text)
        return self._robots[host].can_fetch(self.user_agent, url)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # ── internals ─────────────────────────────────────────────────────────────
    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout_s, follow_redirects=True,
                                        headers={"User-Agent": self.user_agent})
        return self._client

    def _wait(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            delay = self.min_interval_s + random.uniform(0, self.jitter_s) - (time.monotonic() - last)
            if delay > 0:
                time.sleep(delay)
        self._last[host] = time.monotonic()

    def _fetch(self, url: str) -> Response:
        host = urlsplit(url).netloc
        for attempt in range(1, self.max_retries + 1):
            self._wait(host)
            try:
                r = self._http().get(url)
            except httpx.HTTPError as exc:
                wait = 2 ** attempt
                log.warning("GET failed (%s), retry %d/%d in %ds", type(exc).__name__, attempt, self.max_retries, wait)
                time.sleep(wait)
                continue
            if r.status_code in (429, 503):
                retry_after = r.headers.get("Retry-After", "")
                wait = int(retry_after) if retry_after.isdigit() else 2 ** (attempt + 2)
                log.warning("HTTP %d from %s, waiting %ds", r.status_code, host, wait)
                time.sleep(wait)
                continue
            return Response(url, str(r.url), r.status_code, r.text,
                            datetime.now(timezone.utc).isoformat(timespec="seconds"), False)
        raise FetchFailed(url)

    def _cache_path(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.json"

    def _cache_get(self, url: str) -> Response | None:
        p = self._cache_path(url)
        if p is None or not p.exists():
            return None
        d = json.loads(p.read_text(encoding="utf-8"))
        return Response(d["url"], d["final_url"], d["status"], d["text"], d["fetched_at"], True)

    def _cache_put(self, resp: Response) -> None:
        p = self._cache_path(resp.url)
        if p is None or resp.status >= 400:
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(resp.__dict__ | {"from_cache": False}), encoding="utf-8")
