"""Turn orchestrator — the fixed, deterministic flow of one conversational turn.

    normalise history → SAFETY ASSESSMENT → (method request? → template, no LLM)
                      → [signed-in session: memory context] → analysis + prompt (empathy_engine)
                      → LLM → OUTPUT GUARD → reply
                      → [signed-in session: record labels; CBT extraction in the background]

The safety layer runs first and its outcome cannot be overridden by later steps.  History
comes from the client, so it is treated as untrusted data: only user/assistant turns are kept
(never `system`), and it is capped in count and length.

Memory (lumina/memory) is used only on turns with no risk and no injection: crisis, elevated and
injection turns get no remembered context, no reflection and no journey step in the prompt.  A
memory failure never affects the reply.

Logs contain labels and scores only — never message text.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field

from .config import HISTORY_WINDOW, MAX_HISTORY_CHARS, MAX_HISTORY_TURNS
from .dialogue import llm_client
from .dialogue.empathy_engine import analyze, build_prompt
from .memory import service as memory
from .memory.service import SessionContext
from .memory.store import default_store
from .safety import output_guard, templates
from .safety.assessment import SafetyAssessment, assess

log = logging.getLogger(__name__)
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="turn")


@dataclass
class TurnResult:
    reply: str
    intent: str
    emotion: str
    sentiment: str
    crisis_flag: bool
    crisis_subtype: str
    risk_level: str
    injection_detected: bool
    pain_points: list = field(default_factory=list)
    debug: dict = field(default_factory=dict)        # never sent to the client
    insight: dict | None = None                      # in-session thought → feeling → behaviour link, when offered

    def as_dict(self) -> dict:
        return asdict(self)


def normalize_history(history: list | None) -> list[dict]:
    """Keep only well-formed user/assistant turns ('ai' → 'assistant', 'text' → 'content')."""
    out = []
    for turn in (history or [])[-MAX_HISTORY_TURNS:]:
        if not isinstance(turn, dict):
            continue
        role = {"ai": "assistant"}.get(turn.get("role"), turn.get("role"))
        content = turn.get("content", turn.get("text"))
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content.strip()[:MAX_HISTORY_CHARS]})
    return out


def _response_guard():
    from .safety.guard import classify_response
    return classify_response


def _remember(session: SessionContext, message: str, safety: SafetyAssessment, analysis: tuple | None,
              insight_offered: bool) -> None:
    """Record the turn's labels and queue extraction.  Never raises: memory must not break a reply."""
    try:
        store = default_store()
        nlp, feeling = analysis if analysis is not None else (None, None)
        turn_id = memory.record_turn(store, session, safety=safety, nlp=nlp, feeling=feeling)
        if turn_id is None:
            return
        if insight_offered:
            store.mark_insight_offered(turn_id)
        if memory.should_extract(safety, nlp):
            memory.extract_async(store, session.session_id, turn_id, message)
    except Exception as exc:
        log.warning("Recording the turn failed: %s", type(exc).__name__)


def respond(message: str, history: list | None = None, persona: str = "listener",
            session: SessionContext | None = None, weather: str | None = None) -> TurnResult:
    turns = normalize_history(history)
    # Text analysis does not depend on the safety outcome: run it alongside the assessment.
    analysis_future = _POOL.submit(analyze, message)
    safety: SafetyAssessment = assess(message, turns)
    log.info("Safety — risk=%s subtype=%s injection=%s degraded=%s",
             safety.risk_level, safety.crisis_subtype, safety.injection, safety.signals.get("degraded"))

    # Method requests never reach the LLM.
    if safety.crisis_subtype == "method":
        if session is not None:
            _remember(session, message, safety, None, False)
        return TurnResult(templates.method_reply(), "crisis", "neutral", "neutral", True, "method",
                          "crisis", safety.injection, [], {"safety": safety.signals, "path": "template"})

    context, connections = None, None
    if session is not None and safety.risk_level == "none" and not safety.injection:
        try:
            context, connections = memory.load_context(default_store(), session, message)
        except Exception as exc:
            log.warning("Memory context unavailable: %s", type(exc).__name__)
    # The inner-weather check-in (guests too) sets the tone on ordinary turns only, like memory.
    if weather and safety.risk_level == "none" and not safety.injection:
        context = {**(context or {}), "weather": weather}

    analysis = analysis_future.result()
    prompt = build_prompt(message, safety, analysis, persona=persona, memory=context)
    messages = [{"role": "system", "content": prompt["system_prompt"]}]
    messages += turns[-HISTORY_WINDOW:]
    messages.append({"role": "user", "content": prompt["user_message"]})

    replaced = False
    try:
        reply = llm_client.complete(messages)
        # Structural checks run on every reply; the Llama Guard reply check (~2 s) on risky turns only.
        model_check = _response_guard() if safety.risk_level != "none" else None
        guarded = output_guard.check(reply, user_message=message, crisis=safety.is_crisis,
                                     crisis_subtype=safety.crisis_subtype, response_guard=model_check)
        if guarded.replaced:
            log.warning("Output guard replaced the reply — reasons=%s", ",".join(guarded.reasons))
        reply, path, reasons, replaced = guarded.text, "llm", guarded.reasons, guarded.replaced
    except llm_client.LLMUnavailable:
        if safety.crisis_subtype == "third_party":
            reply = templates.third_party_fallback()
        elif safety.is_crisis:
            reply = templates.ideation_fallback()
        else:
            reply = templates.unavailable_reply(crisis=False)
        path, reasons = "fallback", ()

    # The reflection was asked for in the prompt only on an emotional turn; show its chain only if the LLM's
    # reply went out unchanged.
    insight = None
    if (connections is not None and connections.ready and prompt["intent_category"] == "emotional"
            and path == "llm" and not replaced):
        insight = connections.chain
    if session is not None:
        _remember(session, message, safety, analysis, insight is not None)

    nlp, feeling = prompt["debug"]["nlp"], prompt["debug"]["feeling"]
    return TurnResult(
        reply=reply,
        intent="crisis" if safety.is_crisis else prompt["intent"],
        emotion=feeling.get("emotion", "neutral"),
        sentiment=feeling.get("sentiment", "neutral"),
        crisis_flag=safety.is_crisis,
        crisis_subtype=safety.crisis_subtype,
        risk_level=safety.risk_level,
        injection_detected=safety.injection,
        pain_points=nlp.get("pain_points", []),
        debug={"safety": safety.signals, "path": path, "guard_reasons": list(reasons),
               "intent_category": prompt["intent_category"], "rag_hits": prompt["rag_hits"],
               "memory": sorted(context) if context else []},
        insight=insight,
    )
