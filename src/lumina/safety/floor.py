"""Deterministic safety floor — a deliberately SMALL backstop under the model-based detectors.

Why it exists: the primary crisis detectors are models (safety.guard = Llama Guard 3,
safety.risk_model = a trained suicide-risk classifier).  Models can be unavailable,
time out, or miss.  The floor catches only *unambiguous, explicit* statements so that
the system never silently drops the most obvious crisis messages.

What it is NOT: a coverage mechanism.  It does not try to enumerate wording — novel
phrasing is the models' job and is measured in eval/ (see docs/evaluation.md).
Keep this list short; every pattern must be explicit first-person self-harm/suicide
language or an explicit request for a self-harm method.

The floor can only RAISE risk.  No layer (including sentiment) can cancel another.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .text import normalize

_SELF = r"(?:kill|hurt|harm|cut|hang|poison|unalive)"

# Explicit requests for a method. Never cancelled.
_METHOD = re.compile(
    rf"\bhow (?:can|do|would|should|to) (?:i )?(?:{_SELF} myself|commit suicide|end my life|self[- ]?harm)\b"
    rf"|\b(?:ways?|best way|easiest way|painless way) to (?:{_SELF} myself|die|commit suicide|end my life)\b"
    r"|\b(?:lethal|fatal) dose\b"
)

# Explicit first-person statements.
_EXPLICIT = re.compile(
    r"\b(?:kill|killing) myself\b|\bkms\b|\b(?:want|wanna|going) to die\b"
    r"|\b(?:end|take) my (?:own )?life\b|\bi(?: am|m)? (?:feeling )?suicidal\b"
    r"|\b(?:dont|do not) want to (?:live|be alive)\b|\bbetter off dead\b"
)
# "cut/hurt myself" is deliberately absent: it is ambiguous ("cut myself while cooking") and the
# risk model covers self-harm language (eval/reports/safety_detection.json).

# The only idioms that cancel an explicit match — and only when they cover the matched span.
_IDIOM = re.compile(
    r"\bkill(?:ing)? myself laughing\b|\b(?:want|going) to die (?:of|from) (?:laughter|embarrassment)\b"
)


@dataclass(frozen=True)
class FloorResult:
    method: bool
    explicit: bool

    @property
    def triggered(self) -> bool:
        return self.method or self.explicit


def check(text: str) -> FloorResult:
    t = normalize(text)
    if _METHOD.search(t):
        return FloorResult(method=True, explicit=True)
    idioms = [(m.start(), m.end()) for m in _IDIOM.finditer(t)]
    for m in _EXPLICIT.finditer(t):
        if not any(s <= m.start() and m.end() <= e for s, e in idioms):
            return FloorResult(method=False, explicit=True)
    return FloorResult(method=False, explicit=False)
