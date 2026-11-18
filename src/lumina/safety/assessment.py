"""Safety assessment of one user turn — combines the independent layers.

With the LLM reader's reading (English messages, reader on and working):

    crisis    if  floor triggered                                          (always on its own)
              or  the reader says "other" or "method"
              or  the reader says "self" and (P(risk | message) >= SAFETY_READER_SELF_MIN_P
                                              or guard flags or P(risk | message) >= RISK_THRESHOLD)
    elevated  if  guard flags or P(risk | message) >= RISK_THRESHOLD but the reader says "none"
              or  the reader says "self" without the confirmation above
              or  P(risk | message) >= RISK_ELEVATED_THRESHOLD
              or  P(risk | recent user turns + message) >= RISK_THRESHOLD   (risk spread over turns)
              or  a recent turn was a crisis
    none      otherwise

Without a reading (reader off or failed; French and Arabic, read by the translator instead; Arabizi), every
layer stands alone, as before S3:

    crisis    if  floor triggered or guard flags or P(risk | message) >= RISK_THRESHOLD
              or  the translator's reading says "self" / "method" / "other"
    elevated, none   as above

    Why (eval/runners/safety_policy_sweep.py): Llama Guard 1B and the classifier key on
    topic words, and alone they opened the crisis sheet on "I need a therapist I can afford" or a sertraline
    question.  The LLM reader (lumina/safety/reader.py) reads intent: requiring it to agree halves the false
    alarms on counselling posts at the same clinical recall, and it alone catches indirect risk such as "my
    brother texted goodbye to everyone and now he isn't answering".  A demoted turn is "elevated" (gentler
    tone), never "none".  The floor is never demoted.

    subtype:  method       — explicit method request caught by the floor (fully templated, no LLM).
                             Llama Guard's "method" label is NOT used for this: it misfired on e.g. a
                             medication question; guard-flagged turns get the crisis prompt + output guard.
              ideation     — any other first-person signal
              third_party  — the reader (or, without a reading, the guard or translator) says the risk
                             concerns someone else and nothing first-person fired

    Context only raises risk to "elevated" so one false alarm cannot cascade through a conversation.

Injection is assessed independently and NEVER changes the risk outcome.
Sentiment and emotion are deliberately not inputs.

Language (lumina/safety/language.py).  The detectors are English models, so:
    French / Arabic   the message is translated by the chat LLM; floor and risk classifier also run on the
                      English, the translator's own risk reading is one more layer ("self"/"method" →
                      ideation, "other" → third_party), and injection is scored on the English (the
                      injection model scores Arabic script as an attack).  No translation → "elevated".
    Arabizi           cannot be read reliably: `understood` is False and risk is at least "elevated"; the
                      orchestrator answers with a fixed reply instead of guessing.
Everything above still runs on the original text, and translation can only RAISE risk to crisis.  One
exception, for the "elevated" band only: once a translation exists, the risk classifier's mid-range score is
read from the English, because its scores on non-English text are noise.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Literal

from ..config import RECENT_RISK_TURNS, RISK_ELEVATED_THRESHOLD, RISK_THRESHOLD, SAFETY_READER_SELF_MIN_P
from . import floor

log = logging.getLogger(__name__)

RiskLevel = Literal["none", "elevated", "crisis"]
CrisisSubtype = Literal["none", "ideation", "method", "third_party"]


@dataclass(frozen=True)
class SafetyAssessment:
    risk_level: RiskLevel
    crisis_subtype: CrisisSubtype
    injection: bool
    signals: dict = field(default_factory=dict)   # layer outputs (no user text) — for logs and evaluation
    language: str = "en"                          # "en" | "fr" | "ar" | "arabizi"
    understood: bool = True                       # False: written in a way the safety layer cannot read

    @property
    def is_crisis(self) -> bool:
        return self.risk_level == "crisis"


class SeenCrisis:
    """Which recent messages were assessed as crisis, by hash only (no text, memory only, bounded).

    History comes from the client as plain text and is re-read by the English detectors each turn, which
    cannot see a crisis that was only visible in translation.  Remembering the outcome keeps a follow-up
    ("how many would it take?") elevated whatever language the earlier message was in.
    """

    def __init__(self, size: int = 4096):
        self._size, self._keys, self._lock = size, OrderedDict(), threading.Lock()

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    def add(self, text: str) -> None:
        key = self._key(text)
        with self._lock:
            self._keys[key] = True
            self._keys.move_to_end(key)
            while len(self._keys) > self._size:
                self._keys.popitem(last=False)

    def __contains__(self, text: str) -> bool:
        with self._lock:
            return self._key(text) in self._keys


@dataclass
class Detectors:
    """Injectable detector functions (real models by default; stubs in tests)."""
    guard: Callable[[list[dict]], "object"]
    risk_probability: Callable[[str], float]
    injection_probability: Callable[[str], float]
    injection_threshold: float
    language: Callable[[str], str] = lambda text: "en"
    translate: Callable[[str], "object"] = lambda text: None      # → language.Translation | None
    read_risk: Callable[[str], "str | None"] | None = None       # → reader.RISKS | None; None = no reader
    seen: SeenCrisis = field(default_factory=SeenCrisis)

    @classmethod
    def default(cls) -> "Detectors":
        from ..config import INJECTION_THRESHOLD, SAFETY_READER
        from . import language, reader
        from .guard import classify_user_risk
        from .injection import injection_probability
        from .risk_model import risk_probability
        return cls(classify_user_risk, risk_probability, injection_probability, INJECTION_THRESHOLD,
                   language.detect, language.translate, reader.read_risk if SAFETY_READER else None)


_DEFAULT: Detectors | None = None
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="safety")


def _detectors() -> Detectors:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Detectors.default()
    return _DEFAULT


def _safe(fn, *args, default):
    try:
        return fn(*args)
    except Exception as exc:          # a failing model layer degrades to the remaining layers
        log.warning("Safety layer %s failed (%s)", getattr(fn, "__name__", fn), type(exc).__name__)
        return default


_TRANSLATED = ("fr", "ar")


def _max(*values):
    known = [v for v in values if v is not None]
    return max(known) if known else None


def assess(message: str, history: list[dict] | None = None, detectors: Detectors | None = None) -> SafetyAssessment:
    """`history` = normalised previous turns [{"role": "user"|"assistant", "content": str}, ...]."""
    d = detectors or _detectors()
    history = history or []
    recent = history[-2 * RECENT_RISK_TURNS:]
    prev_user = [t["content"] for t in recent if t["role"] == "user"][-RECENT_RISK_TURNS:]
    lang = _safe(d.language, message, default="en")

    # The guard is an HTTP call to Ollama (~2 s), the translation or the risk reader an LLM call (~0.4 s):
    # start them first and compute the local layers meanwhile.  French and Arabic get the translator, whose
    # own risk reading replaces the reader's; Arabizi gets neither (nothing can read it).
    guard_future = _POOL.submit(_safe, d.guard, recent + [{"role": "user", "content": message}], default=None)
    translation_future = _POOL.submit(_safe, d.translate, message, default=None) if lang in _TRANSLATED else None
    use_reader = lang == "en" and d.read_risk is not None
    reader_future = _POOL.submit(_safe, d.read_risk, message, default=None) if use_reader else None

    fl = floor.check(message)
    p_msg = _safe(d.risk_probability, message, default=None)
    p_ctx = _safe(d.risk_probability, "\n".join(prev_user + [message]), default=None) if prev_user else p_msg
    history_crisis = any(floor.check(t).triggered or t in d.seen for t in prev_user) or (
        bool(prev_user) and (_safe(d.risk_probability, "\n".join(prev_user), default=0.0) or 0.0) >= RISK_THRESHOLD)

    translation = translation_future.result() if translation_future is not None else None
    english = getattr(translation, "english", None)
    llm_risk = getattr(translation, "risk", "none") if translation is not None else "none"
    reader_risk = reader_future.result() if reader_future is not None else None
    p_mid = p_msg                                 # the score read for the "elevated" band
    if english:                                   # the same layers on the English; they can only raise risk
        fl_en = floor.check(english)
        fl = floor.FloorResult(method=fl.method or fl_en.method, explicit=fl.explicit or fl_en.explicit)
        p_en = _safe(d.risk_probability, english, default=None)
        # The classifier's mid-range scores on text it was not trained on are noise (an Arabic "hello, how
        # are you?" scored 0.42): the elevated band reads the English score, the crisis threshold the higher.
        p_mid = p_en if p_en is not None else p_msg
        p_msg = _max(p_msg, p_en)
        p_ctx = _max(p_ctx, _safe(d.risk_probability, "\n".join(prev_user + [english]), default=None)
                     if prev_user else p_msg)

    # Injection: on the English when the message is not English.  Without a translation, French is still
    # scored as written (a hijacked translator returns none); Arabic script and Arabizi are not, because
    # the injection model scores them as attacks whatever they say.
    inj_text = english or (message if lang in ("en", "fr") else None)
    p_inj = _safe(d.injection_probability, inj_text, default=None) if inj_text else None
    injection = p_inj is not None and p_inj >= d.injection_threshold

    guard = guard_future.result()
    guard_ok = bool(guard and guard.available)
    guard_cats = set(guard.categories) if guard_ok and guard.unsafe else set()

    msg_high = p_msg is not None and p_msg >= RISK_THRESHOLD
    msg_mid = p_mid is not None and p_mid >= RISK_ELEVATED_THRESHOLD
    ctx_high = p_ctx is not None and p_ctx >= RISK_THRESHOLD
    understood = lang != "arabizi"
    unread = not understood or (lang in _TRANSLATED and not english)     # nothing could read this message

    model_flag = bool(guard_cats) or msg_high      # Llama Guard or the classifier would raise a crisis
    if reader_risk is not None:
        # Confirmation (S3): the reader read this message, so Llama Guard or the classifier alone no longer
        # opens the crisis sheet.  When the reader sees no risk, their flag lowers to "elevated"; when it sees
        # risk, its reading also decides whose risk it is.
        p_self = p_msg is not None and p_msg >= SAFETY_READER_SELF_MIN_P
        first_person = (fl.triggered or reader_risk == "method"
                        or (reader_risk == "self" and (p_self or model_flag)))
        third_party = reader_risk == "other"
        demoted = model_flag and reader_risk == "none"
    else:
        # No reading (reader off or failed, or a translated or unreadable message): every layer stands alone.
        first_person = (fl.triggered or bool(guard_cats & {"method", "ideation"}) or msg_high
                        or llm_risk in ("self", "method"))
        third_party = "third_party" in guard_cats or llm_risk == "other"
        demoted = False
    if fl.method:
        level, subtype = "crisis", "method"
    elif first_person:
        level, subtype = "crisis", "ideation"
    elif third_party:
        level, subtype = "crisis", "third_party"
    elif msg_mid or ctx_high or history_crisis or unread or reader_risk == "self" or demoted:
        level, subtype = "elevated", "none"
    else:
        level, subtype = "none", "none"
    if level == "crisis":
        d.seen.add(message)

    signals = {
        "floor": {"method": fl.method, "explicit": fl.explicit},
        "guard": {"available": guard_ok, "categories": sorted(guard_cats)},
        "risk_p": None if p_msg is None else round(p_msg, 4),
        "risk_p_context": None if p_ctx is None else round(p_ctx, 4),
        "history_crisis": history_crisis,
        "injection_p": None if p_inj is None else round(p_inj, 4),
        "language": lang,
        "translated": bool(english),
        "llm_risk": llm_risk,
        "reader": reader_risk,
        "degraded": [n for n, ok in (("guard", guard_ok), ("risk_model", p_msg is not None),
                                     ("injection_model", p_inj is not None or inj_text is None),
                                     ("translator", lang not in _TRANSLATED or bool(english)),
                                     ("reader", not use_reader or reader_risk is not None)) if not ok],
    }
    return SafetyAssessment(level, subtype, injection, signals, language=lang, understood=understood)
