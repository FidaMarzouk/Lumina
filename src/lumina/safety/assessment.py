"""Safety assessment of one user turn — combines the independent layers.

    risk = max(floor, guard, risk classifier)          (no layer can cancel another)

    crisis    if  floor triggered
              or  guard flags method / ideation / third_party
              or  P(risk | message) >= RISK_THRESHOLD
    elevated  if  P(risk | message) >= RISK_ELEVATED_THRESHOLD
              or  P(risk | recent user turns + message) >= RISK_THRESHOLD   (risk spread over turns)
              or  a recent turn was a crisis
    none      otherwise

    subtype:  method       — explicit method request caught by the floor (fully templated, no LLM).
                             Llama Guard's "method" label is NOT used for this: it misfired on e.g. a
                             medication question; guard-flagged turns get the crisis prompt + output guard.
              ideation     — any other first-person signal
              third_party  — guard says the risk concerns someone else and nothing else fired

    Context only raises risk to "elevated" so one false alarm cannot cascade through a conversation.

Injection is assessed independently and NEVER changes the risk outcome.
Sentiment and emotion are deliberately not inputs.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Literal

from ..config import RECENT_RISK_TURNS, RISK_ELEVATED_THRESHOLD, RISK_THRESHOLD
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

    @property
    def is_crisis(self) -> bool:
        return self.risk_level == "crisis"


@dataclass
class Detectors:
    """Injectable detector functions (real models by default; stubs in tests)."""
    guard: Callable[[list[dict]], "object"]
    risk_probability: Callable[[str], float]
    injection_probability: Callable[[str], float]
    injection_threshold: float

    @classmethod
    def default(cls) -> "Detectors":
        from ..config import INJECTION_THRESHOLD
        from .guard import classify_user_risk
        from .injection import injection_probability
        from .risk_model import risk_probability
        return cls(classify_user_risk, risk_probability, injection_probability, INJECTION_THRESHOLD)


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


def assess(message: str, history: list[dict] | None = None, detectors: Detectors | None = None) -> SafetyAssessment:
    """`history` = normalised previous turns [{"role": "user"|"assistant", "content": str}, ...]."""
    d = detectors or _detectors()
    history = history or []
    recent = history[-2 * RECENT_RISK_TURNS:]
    prev_user = [t["content"] for t in recent if t["role"] == "user"][-RECENT_RISK_TURNS:]

    # The guard is an HTTP call to Ollama (~2 s): start it first and compute the local layers meanwhile.
    guard_future = _POOL.submit(_safe, d.guard, recent + [{"role": "user", "content": message}], default=None)

    fl = floor.check(message)
    p_msg = _safe(d.risk_probability, message, default=None)
    p_ctx = _safe(d.risk_probability, "\n".join(prev_user + [message]), default=None) if prev_user else p_msg
    history_crisis = any(floor.check(t).triggered for t in prev_user) or (
        bool(prev_user) and (_safe(d.risk_probability, "\n".join(prev_user), default=0.0) or 0.0) >= RISK_THRESHOLD)

    p_inj = _safe(d.injection_probability, message, default=None)
    injection = p_inj is not None and p_inj >= d.injection_threshold

    guard = guard_future.result()
    guard_ok = bool(guard and guard.available)
    guard_cats = set(guard.categories) if guard_ok and guard.unsafe else set()

    msg_high = p_msg is not None and p_msg >= RISK_THRESHOLD
    msg_mid = p_msg is not None and p_msg >= RISK_ELEVATED_THRESHOLD
    ctx_high = p_ctx is not None and p_ctx >= RISK_THRESHOLD

    first_person = fl.triggered or bool(guard_cats & {"method", "ideation"}) or msg_high
    if fl.method:
        level, subtype = "crisis", "method"
    elif first_person:
        level, subtype = "crisis", "ideation"
    elif "third_party" in guard_cats:
        level, subtype = "crisis", "third_party"
    elif msg_mid or ctx_high or history_crisis:
        level, subtype = "elevated", "none"
    else:
        level, subtype = "none", "none"

    signals = {
        "floor": {"method": fl.method, "explicit": fl.explicit},
        "guard": {"available": guard_ok, "categories": sorted(guard_cats)},
        "risk_p": None if p_msg is None else round(p_msg, 4),
        "risk_p_context": None if p_ctx is None else round(p_ctx, 4),
        "history_crisis": history_crisis,
        "injection_p": None if p_inj is None else round(p_inj, 4),
        "degraded": [n for n, ok in (("guard", guard_ok), ("risk_model", p_msg is not None),
                                     ("injection_model", p_inj is not None)) if not ok],
    }
    return SafetyAssessment(level, subtype, injection, signals)
