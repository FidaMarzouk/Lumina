"""Output guard — checks every LLM reply before it reaches the user.

Checks (structural + model; no phrase lists):
  1. any phone number  — contact numbers come only from the frontend banner; LLMs invent hotlines
  2. medication dosages  (number + dose unit)
  3. Llama Guard on the reply: self-harm content (S11) or specialized medical advice (S6)

A violation replaces the reply with a safe, risk-appropriate template.  The reasons are
returned for logging/evaluation (never the text itself).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from . import templates

_PHONE = re.compile(r"(?<![\w.])\+?\d[\d \-().]{4,16}\d(?![\w.])")
_DOSE = re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:mg|milligrams?|mcg|micrograms?|ml|millilit(?:er|re)s?|tablets?|pills?|capsules?)\b",
                   re.IGNORECASE)
_BLOCKING_GUARD = {"suicide_self_harm", "specialized_advice"}


@dataclass(frozen=True)
class GuardedReply:
    text: str
    replaced: bool
    reasons: tuple[str, ...]


def _fallback(crisis_subtype: str, crisis: bool) -> str:
    if crisis_subtype == "method":
        return templates.method_reply()
    if crisis_subtype == "third_party":
        return templates.third_party_fallback()
    if crisis:
        return templates.ideation_fallback()
    return templates.generic_fallback()


def check(reply: str, *, user_message: str, crisis: bool, crisis_subtype: str,
          response_guard: Callable[[list[dict]], object] | None = None) -> GuardedReply:
    reasons: list[str] = []
    if _PHONE.search(reply):
        reasons.append("phone_number")
    if _DOSE.search(reply):
        reasons.append("dosage")
    if response_guard is not None:
        g = response_guard([{"role": "user", "content": user_message}, {"role": "assistant", "content": reply}])
        if getattr(g, "available", False) and getattr(g, "unsafe", False):
            reasons += [f"guard:{c}" for c in sorted(_BLOCKING_GUARD & set(g.categories))]
    if reasons:
        return GuardedReply(_fallback(crisis_subtype, crisis), True, tuple(sorted(set(reasons))))
    return GuardedReply(reply, False, ())
