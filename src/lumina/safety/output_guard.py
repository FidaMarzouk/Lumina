"""Output guard — checks every LLM reply before it reaches the user.

Checks (structural + model; no phrase lists):
  1. anything shaped like a phone number — contact numbers come only from the frontend help sheet; LLMs
     invent hotlines.  Countdowns, year ranges, dates and clock times are not phone numbers (see
     has_phone_number): the old pattern replaced every reply that named the "5-4-3-2-1" exercise.
     On crisis turns, emergency short codes too ("988", "15"): the model names another country's line.
  2. medication dosages  (number + dose unit)
  3. Llama Guard on the reply: self-harm content (S11) or specialized medical advice (S6)
  4. while a save waits for the person's Save button: a reply saying it is already saved (claims_done)

A violation replaces the reply with a safe, risk-appropriate template.  The reasons are
returned for logging/evaluation (never the text itself).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from . import templates

# A run of digit groups joined by single spaces, dots or hyphens (optionally "+" and bracketed groups).
# Whether a run is shaped like a phone number is decided in has_phone_number().
_DIGIT_RUN = re.compile(r"(?<![\w.,:/])\+?(?:\(\d{1,4}\)|\d+)(?:[ .\-]?(?:\(\d{1,4}\)|\d+))*(?![\w:/])")
_PHONE_MIN_DIGITS, _PHONE_MAX_DIGITS = 6, 15       # 116 123 … the E.164 maximum


def _is_year(group: str) -> bool:
    return len(group) == 4 and 1900 <= int(group) <= 2099


def has_phone_number(text: str) -> bool:
    """True when `text` holds something shaped like a phone number.

    Shape only, no word lists.  A digit run counts unless it is one of the things supportive replies
    legitimately write: a countdown of single digits ("5-4-3-2-1"), a range of years ("2019-2021"), an ISO
    date, or a short hyphenated range ("150-300 minutes").  Clock times never form a run (":" breaks it).
    """
    for m in _DIGIT_RUN.finditer(text):
        run = m.group()
        groups = re.findall(r"\d+", run)
        digits = sum(len(g) for g in groups)
        if not _PHONE_MIN_DIGITS <= digits <= _PHONE_MAX_DIGITS:
            continue
        if max(len(g) for g in groups) < 3:                       # 5-4-3-2-1, 10 20 30
            continue
        if len(groups) == 2 and all(_is_year(g) for g in groups):  # 2019-2021
            continue
        if (len(groups) == 3 and _is_year(groups[0]) and len(groups[1]) == len(groups[2]) == 2
                and 1 <= int(groups[1]) <= 12 and 1 <= int(groups[2]) <= 31):   # 2026-11-13
            continue
        if len(groups) == 2 and "-" in run and digits < 7:          # 150-300; "116 123" (a space) still counts
            continue
        return True
    return False


# Emergency short codes ("988", "le 15", "112").  Checked on crisis turns only, where a reply has no reason to
# hold a 2-4 digit number and a wrong country's code is dangerous; "24/7", ranges, times, decimals and
# percentages are left alone.  On other turns short numbers are ordinary ("7 to 8 hours", "10 minutes").
_SHORT_CODE = re.compile(r"(?<![\w.,:/+\-])\d{2,4}(?![\w:/%\-]|[.,]\d)")

_DOSE =re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:mg|milligrams?|mcg|micrograms?|ml|millilit(?:er|re)s?|tablets?|pills?|capsules?)\b",
                   re.IGNORECASE)
_BLOCKING_GUARD = {"suicide_self_harm", "specialized_advice"}

# A first-person completion claim ("I've added", "has been saved", "Done"): checked only while a save is waiting
# for the person's Save button (A3), when nothing has been saved and saying otherwise is a false promise about
# their own data.  The verbs are the actions the write tools offer, not a list of topics or intents.
_DONE = re.compile(r"\b(?:i'?ve|i have|i just|i'?ve gone ahead and)\s+(?:\w+\s+)?(?:saved|logged|noted|added|"
                   r"recorded|tracked|marked|written|put|kept|stored)\b(?!\s+together)|\b(?:has|have|is|was) (?:been |now )?"
                   r"(?:saved|logged|added|recorded|tracked|stored)\b|^\s*done\b", re.IGNORECASE | re.MULTILINE)


def claims_done(text: str) -> bool:
    return bool(_DONE.search(text))


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
          response_guard: Callable[[list[dict]], object] | None = None,
          pending_save: str | None = None) -> GuardedReply:
    """`pending_save`: the summary of a save waiting for the person's Save button, if any."""
    reasons: list[str] = []
    if has_phone_number(reply):
        reasons.append("phone_number")
    elif crisis and _SHORT_CODE.search(reply):
        reasons.append("short_code")
    if _DOSE.search(reply):
        reasons.append("dosage")
    if response_guard is not None:
        g = response_guard([{"role": "user", "content": user_message}, {"role": "assistant", "content": reply}])
        if getattr(g, "available", False) and getattr(g, "unsafe", False):
            reasons += [f"guard:{c}" for c in sorted(_BLOCKING_GUARD & set(g.categories))]
    if reasons:
        return GuardedReply(_fallback(crisis_subtype, crisis), True, tuple(sorted(set(reasons))))
    if pending_save and claims_done(reply):
        return GuardedReply(templates.proposal_reply(pending_save), True, ("claimed_save",))
    return GuardedReply(reply, False, ())
