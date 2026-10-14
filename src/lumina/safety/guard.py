"""Llama Guard 3 (local, via Ollama) — model-based safety classification.

Two uses:
  * classify_user_risk(): the LAST user turn is judged against a Lumina-specific
    taxonomy (method seeking / ideation-intent / concern for someone else).  Llama Guard 3
    is trained to follow custom category definitions given in its prompt, which lets the
    model — not a phrase list — distinguish a method request from an expression of pain.
  * classify_response(): an assistant reply is judged against the default MLCommons
    taxonomy (S6 specialized advice, S11 self-harm, …) as part of the output guard.

Recent turns are included so follow-ups ("how many would it take?") are judged in context.
Failure policy: any error / timeout → available=False; the other layers still run.
Quality is measured in eval/ (docs/evaluation.md) — do not assume it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from ..config import OLLAMA_BASE_URL, SAFETY_GUARD_MODEL, SAFETY_GUARD_NUM_GPU, SAFETY_GUARD_TIMEOUT_S

log = logging.getLogger(__name__)

# Lumina user-risk taxonomy (S-codes are local to this prompt).
USER_RISK_CATEGORIES = {
    "S1": ("method",
           "Self-Harm Method Seeking. The user asks for or about ways, means, doses, places, timing or "
           "instructions to hurt or kill themselves, or how to hide self-harm or make it look like an accident."),
    "S2": ("ideation",
           "Suicidal Ideation or Self-Harm Intent. The user expresses a wish to die, thoughts of suicide, "
           "a plan or intent to end their life or hurt themselves, or current or recent self-harm."),
    "S3": ("third_party",
           "Concern For Someone At Risk. The user says another person may be suicidal, self-harming, or "
           "in danger of ending their life."),
}

# Default Llama Guard 3 taxonomy (used for assistant replies).
DEFAULT_CATEGORIES = {
    "S1": "violent_crimes", "S2": "non_violent_crimes", "S3": "sex_related_crimes",
    "S4": "child_sexual_exploitation", "S5": "defamation", "S6": "specialized_advice",
    "S7": "privacy", "S8": "intellectual_property", "S9": "indiscriminate_weapons",
    "S10": "hate", "S11": "suicide_self_harm", "S12": "sexual_content", "S13": "elections",
    "S14": "code_interpreter_abuse",
}


@dataclass(frozen=True)
class GuardResult:
    available: bool
    unsafe: bool = False
    categories: tuple[str, ...] = field(default_factory=tuple)   # names, e.g. ("method",) or ("suicide_self_harm",)


def parse(output: str) -> tuple[bool, tuple[str, ...]]:
    lines = [ln.strip() for ln in output.strip().splitlines() if ln.strip()]
    if not lines or lines[0].lower() != "unsafe":
        return False, ()
    codes = tuple(c.strip().upper() for ln in lines[1:] for c in ln.split(",") if c.strip())
    return True, codes


def build_user_risk_prompt(conversation: list[dict]) -> str:
    """Official Llama Guard 3 prompt format with the Lumina taxonomy."""
    cats = "\n".join(f"{code}: {desc}" for code, (_, desc) in USER_RISK_CATEGORIES.items())
    convo = "\n\n".join(
        f"{'User' if t['role'] == 'user' else 'Agent'}: {t['content']}" for t in conversation)
    return (
        "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
        "Task: Check if there is unsafe content in 'User' messages in conversations according our safety "
        "policy with the below categories.\n\n"
        f"<BEGIN UNSAFE CONTENT CATEGORIES>\n{cats}\n<END UNSAFE CONTENT CATEGORIES>\n\n"
        f"<BEGIN CONVERSATION>\n\n{convo}\n\n<END CONVERSATION>\n\n"
        "Provide your safety assessment for ONLY THE LAST User message in the above conversation:\n"
        " - First line must read 'safe' or 'unsafe'.\n"
        " - If unsafe, a second line must include a comma-separated list of violated categories."
        "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )


def classify_user_risk(conversation: list[dict], *, client: httpx.Client | None = None) -> GuardResult:
    """`conversation` = [{"role": "user"|"assistant", "content": str}, ...]; the last turn must be the user's."""
    payload = {"model": SAFETY_GUARD_MODEL, "prompt": build_user_risk_prompt(conversation),
               "raw": True, "stream": False, "keep_alive": "30m",
               "options": _options()}
    out = _call("/api/generate", payload, client, lambda j: j["response"])
    if out is None:
        return GuardResult(False)
    unsafe, codes = parse(out)
    names = tuple(USER_RISK_CATEGORIES[c][0] for c in codes if c in USER_RISK_CATEGORIES)
    return GuardResult(True, unsafe and bool(names), names)


def classify_response(conversation: list[dict], *, client: httpx.Client | None = None) -> GuardResult:
    """Judge the last (assistant) turn with Ollama's built-in Llama Guard template."""
    payload = {"model": SAFETY_GUARD_MODEL, "messages": conversation, "stream": False, "keep_alive": "30m",
               "options": _options()}
    out = _call("/api/chat", payload, client, lambda j: j["message"]["content"])
    if out is None:
        return GuardResult(False)
    unsafe, codes = parse(out)
    return GuardResult(True, unsafe, tuple(DEFAULT_CATEGORIES.get(c, c) for c in codes))


def _options() -> dict:
    opts = {"temperature": 0, "num_predict": 16}
    if SAFETY_GUARD_NUM_GPU >= 0:
        opts["num_gpu"] = SAFETY_GUARD_NUM_GPU
    return opts


def _call(path: str, payload: dict, client: httpx.Client | None, extract) -> str | None:
    try:
        if client is None:
            with httpx.Client(timeout=SAFETY_GUARD_TIMEOUT_S) as c:
                r = c.post(f"{OLLAMA_BASE_URL}{path}", json=payload)
        else:
            r = client.post(f"{OLLAMA_BASE_URL}{path}", json=payload)
        r.raise_for_status()
        return extract(r.json())
    except Exception as exc:                      # an unavailable guard must never break a turn
        log.warning("Safety guard unavailable (%s)", type(exc).__name__)
        return None
