"""robots.txt matching per RFC 9309 (the standard library is not enough).

`urllib.robotparser` does plain prefix matching and ignores `*` / `$` wildcards, so a rule such as
Apple's `Disallow: /*/rss/*` would NOT block `/us/rss/...` (verified).  This matcher implements:
  * group selection: the group whose user-agent token is a case-insensitive substring of our
    product token wins (longest token first); otherwise the `*` group
  * rule matching with `*` (any sequence) and `$` (end of URL)
  * the most specific (longest) matching rule wins; on a tie, Allow wins
  * no matching rule → allowed
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass
class _Group:
    agents: list[str] = field(default_factory=list)
    rules: list[tuple[bool, str]] = field(default_factory=list)   # (allow, pattern)


def _compile(pattern: str) -> re.Pattern:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    rx = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.compile(rx + ("$" if anchored else ""))


class Robots:
    def __init__(self, text: str):
        self.groups: list[_Group] = []
        current: _Group | None = None
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (s.strip() for s in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if current is None or not last_was_agent:
                    current = _Group()
                    self.groups.append(current)
                current.agents.append(value.lower())
                last_was_agent = True
            elif key in ("allow", "disallow") and current is not None:
                if value:                                   # empty Disallow = allow everything
                    current.rules.append((key == "allow", value))
                last_was_agent = False
            else:
                last_was_agent = False

    def _group_for(self, user_agent: str) -> _Group | None:
        token = user_agent.split("/")[0].lower()
        best, best_len = None, -1
        for g in self.groups:
            for a in g.agents:
                if a != "*" and a in token and len(a) > best_len:
                    best, best_len = g, len(a)
        if best is not None:
            return best
        return next((g for g in self.groups if "*" in g.agents), None)

    def can_fetch(self, user_agent: str, url: str) -> bool:
        group = self._group_for(user_agent)
        if group is None:
            return True
        parts = urlsplit(url)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        best_len, allowed = -1, True
        for allow, pattern in group.rules:
            if _compile(pattern).match(path):
                length = len(pattern)
                if length > best_len or (length == best_len and allow):
                    best_len, allowed = length, allow
        return allowed
