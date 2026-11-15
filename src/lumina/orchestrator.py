"""Turn orchestrator — the fixed, deterministic flow of one conversational turn, as explicit stages:

    1 safety    normalise history → SAFETY ASSESSMENT (text analysis runs alongside it)
    2 route     route(safety)           → "method_template"   explicit method request: fixed reply, no LLM
                                        → "language_template" unreadable script: fixed "please write in…", no LLM
                route(safety, intent)   → "crisis" | "injection"   fixed prompts
                                        → "act"    the person asks the app to do something (Q3; tools: A2)
                                        → "talk"   everything else
    3 context   [signed-in, risk "none", no injection: memory]  [weather check-in]
    3b tools    [AGENT_TOOLS on, "act" route, signed in, risk "none"] read tools chosen by the tool model
                (lumina/agent).  An action request flagged as injection is let through to the tools; if the tool
                model picks a read tool, the turn becomes "act" (the flag misfires on "read me back what I
                wrote"); otherwise it stays "injection".
    4 prompt    empathy_engine.build_prompt (its category always agrees with the route)
    5 generate  whole reply (respond)  |  sentence by sentence on ordinary turns (respond_stream)
    6 guard     OUTPUT GUARD: whole reply, or every sentence before it is sent
    7 finish    result; [signed-in: record labels, CBT extraction in the background]; trace

The safety layer runs first and its outcome cannot be overridden by later steps: the route is a function of
the assessment first and the intent second.  tests/test_dialogue_and_api.py pins each route's behaviour
(golden turns), so a change to any stage shows up there.

The safety layer runs first and its outcome cannot be overridden by later steps.  History
comes from the client, so it is treated as untrusted data: only user/assistant turns are kept
(never `system`), and it is capped in count and length.

Memory (lumina/memory) is used only on turns with no risk and no injection: crisis, elevated and
injection turns get no remembered context, no reflection and no journey step in the prompt.  A
memory failure never affects the reply.

Logs contain labels and scores only — never message text.  Each turn also leaves a trace (lumina/observability:
stage timings, safety outcome, reply path, guard reasons; no text, no user or session id).
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from typing import Literal

from . import observability
from .agent import loop as agent_loop
from .agent import tools as agent_tools
from .config import AGENT_TOOLS, HISTORY_WINDOW, MAX_HISTORY_CHARS, MAX_HISTORY_TURNS
from .dialogue import llm_client
from .dialogue.empathy_engine import analyze, build_prompt
from .memory import service as memory
from .memory.service import SessionContext
from .memory.store import default_store, utcnow
from .safety import output_guard, templates
from .safety.assessment import SafetyAssessment, assess

log = logging.getLogger(__name__)
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="turn")

Route = Literal["method_template", "language_template", "crisis", "injection", "act", "talk"]
TEMPLATE_ROUTES = ("method_template", "language_template")
_CATEGORY_ROUTE = {"crisis": "crisis", "injection": "injection", "action": "act"}   # other categories: "talk"


def route(safety: SafetyAssessment, intent: str | None = None) -> Route | None:
    """Stage 2.  Before the intent is known, returns a template route or None (keep going); with it, always
    returns a route.  Safety decides first: no intent can lead a crisis or an injection elsewhere."""
    if safety.crisis_subtype == "method":
        return "method_template"
    if not safety.understood and not safety.is_crisis:
        return "language_template"
    if intent is None:
        return None
    if safety.is_crisis:
        return "crisis"
    if safety.injection:
        return "injection"
    if intent == "action_request":
        return "act"
    return "talk"


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


def _settle(future) -> None:
    """Wait for background work whose result is not needed; its failure must not affect the reply."""
    try:
        future.result()
    except Exception as exc:
        log.warning("Background analysis failed: %s", type(exc).__name__)


def respond(message: str, history: list | None = None, persona: str = "listener",
            session: SessionContext | None = None, weather: str | None = None) -> TurnResult:
    sw, usage = observability.Stopwatch(), {}
    prepared = _prepare(message, history, persona, session, weather, sw)
    result = prepared if isinstance(prepared, TurnResult) else _finish(prepared, *_whole_reply(prepared, sw, usage))
    observability.record(_trace(result, session, usage), sw.finish())
    return result


def respond_stream(message: str, history: list | None = None, persona: str = "listener",
                   session: SessionContext | None = None, weather: str | None = None) -> Iterator[dict]:
    """The same turn as respond(), as events for a streaming response:

        {"type": "delta", "text": …}     a checked sentence to add to the reply
        {"type": "replace", "text": …}   replace everything shown so far (the output guard rejected a sentence,
                                         or the LLM failed mid-reply)
        {"type": "done", "result": TurnResult}   always last; result.reply is the full, final reply

    Only ordinary turns stream (risk "none", no injection).  Their reply gets exactly the checks respond() gives
    it, the structural output guard (Llama Guard checks replies on risky turns only), run on all the text so
    far before each sentence is sent.  Risky and templated turns are not streamed: their reply is checked
    whole, as before, and arrives in "done".
    """
    sw, usage = observability.Stopwatch(), {}
    result = None
    try:
        prepared = _prepare(message, history, persona, session, weather, sw)
        if isinstance(prepared, TurnResult):
            result = prepared
        elif not _streamable(prepared):
            result = _finish(prepared, *_whole_reply(prepared, sw, usage))
        else:
            outcome: dict = {}
            yield from _stream_reply(prepared, sw, usage, outcome)
            result = _finish(prepared, outcome["reply"], outcome["path"], outcome["reasons"], outcome["replaced"])
        yield {"type": "done", "result": result}
    finally:
        if result is not None:
            observability.record(_trace(result, session, usage), sw.finish())


def _trace(result: TurnResult, session: SessionContext | None, usage: dict) -> dict:
    """The trace of one turn: labels and numbers only."""
    signals, debug = result.debug.get("safety", {}), result.debug
    reasons = debug.get("guard_reasons", [])
    return {"signed_in": session is not None, "path": debug.get("path", "unknown"), "risk_level": result.risk_level,
            "crisis_subtype": result.crisis_subtype, "injection": result.injection_detected,
            "language": signals.get("language"), "reader": signals.get("reader"), "intent": result.intent,
            "intent_category": debug.get("intent_category"), "rag_hits": debug.get("rag_hits"),
            "replaced": debug.get("path") in ("llm", "llm_stream") and bool(reasons), "guard_reasons": reasons,
            "tools": debug.get("tools", []),
            "degraded": signals.get("degraded", []), "tokens_in": usage.get("in"), "tokens_out": usage.get("out")}


@dataclass
class _Prepared:
    """A turn ready for the LLM: everything decided except the reply itself."""
    message: str
    session: SessionContext | None
    safety: SafetyAssessment
    route: Route
    analysis: tuple
    prompt: dict
    messages: list[dict]
    context: dict | None
    connections: object


def _prepare(message: str, history: list | None, persona: str, session: SessionContext | None, weather: str | None,
             sw: observability.Stopwatch) -> TurnResult | _Prepared:
    """Safety first, then memory, analysis and the prompt.  Returns a finished TurnResult for templated turns."""
    turns = normalize_history(history)
    # Text analysis does not depend on the safety outcome: run it alongside the assessment.
    analysis_future = _POOL.submit(analyze, message)
    with sw.stage("safety"):
        safety: SafetyAssessment = assess(message, turns)
    log.info("Safety — risk=%s subtype=%s injection=%s degraded=%s",
             safety.risk_level, safety.crisis_subtype, safety.injection, safety.signals.get("degraded"))

    # Method requests never reach the LLM.  Templated turns still let the analysis finish (it is done long
    # before the assessment), so no work is left running after the reply.
    early = route(safety)
    if early == "method_template":
        with sw.stage("analysis"):
            _settle(analysis_future)
        if session is not None:
            _remember(session, message, safety, None, False)
        return TurnResult(templates.method_reply(), "crisis", "neutral", "neutral", True, "method",
                          "crisis", safety.injection, {"safety": safety.signals, "path": "template", "route": early})

    # Written in a way neither the safety models nor the LLM can read (Arabizi): say so, don't guess.
    if early == "language_template":
        with sw.stage("analysis"):
            _settle(analysis_future)
        if session is not None:
            _remember(session, message, safety, None, False)
        return TurnResult(templates.unsupported_language_reply(), "unsupported_language", "neutral", "neutral",
                          False, "none", safety.risk_level, safety.injection,
                          {"safety": safety.signals, "path": "template_language", "route": early})

    context, connections = None, None
    if session is not None and safety.risk_level == "none" and not safety.injection:
        try:
            with sw.stage("memory"):
                context, connections = memory.load_context(default_store(), session, message)
        except Exception as exc:
            log.warning("Memory context unavailable: %s", type(exc).__name__)
    # The inner-weather check-in (guests too) sets the tone on ordinary turns only, like memory.
    if weather and safety.risk_level == "none" and not safety.injection:
        context = {**(context or {}), "weather": weather}

    with sw.stage("analysis"):          # only the wait left after the assessment
        analysis = analysis_future.result()
    turn_route = route(safety, analysis[0]["intent"])
    prompt_safety, tool_names = safety, []
    offered = _tools_allowed(safety, session)
    if offered and (turn_route == "act" or (turn_route == "injection" and analysis[0]["intent"] == "action_request")):
        with sw.stage("tools"):
            run = agent_loop.run(message, agent_tools.ToolContext(default_store(), session.user_id,
                                                                  session.memory_enabled, utcnow(), embed=_embed),
                                 allowed=offered)
        if run.used:
            tool_names = [c["name"] for c in run.calls]
            context = {**(context or {}), "tool_results": agent_loop.prompt_block(run)}
            if turn_route == "injection":
                # Read tools only return the person's own notes, so a look-up the injection classifier misread
                # goes ahead.  The result still reports injection_detected, and the reply is never streamed.
                turn_route, prompt_safety = "act", replace(safety, injection=False)
    with sw.stage("prompt"):            # includes knowledge retrieval
        prompt = build_prompt(message, prompt_safety, analysis, persona=persona, memory=context)
    prompt["tools"] = tool_names
    # The prompt builder decides its category from the same inputs; a disagreement is a bug in one of them.
    # Logged, not raised: the prompt builder applies safety on its own, and a failed turn helps nobody.  The
    # golden-turn tests check that they agree.
    if _CATEGORY_ROUTE.get(prompt["intent_category"], "talk") != turn_route:
        log.error("Route %s disagrees with prompt category %s", turn_route, prompt["intent_category"])
    messages = [{"role": "system", "content": prompt["system_prompt"]}]
    messages += turns[-HISTORY_WINDOW:]
    messages.append({"role": "user", "content": prompt["user_message"]})
    return _Prepared(message, session, safety, turn_route, analysis, prompt, messages, context, connections)


def _tools_allowed(safety: SafetyAssessment, session: SessionContext | None) -> tuple[str, ...]:
    """The read tools this turn may use (empty: none).  Never for guests, in a crisis, or within the recent turns
    after one.  At "elevated" risk only the jar and journey progress (tools.ELEVATED_SAFE); all at risk "none"."""
    if not AGENT_TOOLS or session is None or safety.is_crisis or safety.signals.get("history_crisis"):
        return ()
    if safety.risk_level == "none":
        return tuple(agent_tools.READ_TOOLS)
    if safety.risk_level == "elevated":
        return agent_tools.ELEVATED_SAFE
    return ()


def _embed(text: str):
    from .memory.embeddings import embed
    return embed(text)


def _llm_unavailable_reply(safety: SafetyAssessment) -> str:
    if safety.crisis_subtype == "third_party":
        return templates.third_party_fallback()
    if safety.is_crisis:
        return templates.ideation_fallback()
    return templates.unavailable_reply(crisis=False)


def _whole_reply(p: _Prepared, sw: observability.Stopwatch, usage: dict) -> tuple[str, str, tuple, bool]:
    """The reply written in one go and checked whole: (reply, path, guard reasons, replaced)."""
    safety = p.safety
    try:
        with sw.stage("llm"):
            reply = llm_client.complete(p.messages, usage=usage)
        # Structural checks run on every reply; the Llama Guard reply check on risky turns only.
        model_check = _response_guard() if safety.risk_level != "none" else None
        with sw.stage("output_guard"):
            guarded = output_guard.check(reply, user_message=p.message, crisis=safety.is_crisis,
                                         crisis_subtype=safety.crisis_subtype, response_guard=model_check)
        if guarded.replaced:
            log.warning("Output guard replaced the reply — reasons=%s", ",".join(guarded.reasons))
        return guarded.text, "llm", guarded.reasons, guarded.replaced
    except llm_client.LLMUnavailable:
        return _llm_unavailable_reply(safety), "fallback", (), False


def _streamable(p: _Prepared) -> bool:
    """Only replies that get no model check of the reply may be sent before they are complete."""
    return p.safety.risk_level == "none" and not p.safety.injection


# A sentence ends at . ! ? or … (with any closing quote or bracket) followed by whitespace, or at a line break.
# "4.5" or "e.g.x" do not end one; an abbreviation followed by a space may, which only makes a piece shorter.
_SENTENCE_END = re.compile(r"(?<=[.!?…])[\"'”’)\]]*\s+|\n+")


def split_sentences(buffer: str) -> tuple[list[str], str]:
    """(complete sentences with their trailing whitespace, the unfinished rest)."""
    out, start = [], 0
    for m in _SENTENCE_END.finditer(buffer):
        if m.end() > start:
            out.append(buffer[start:m.end()])
            start = m.end()
    return out, buffer[start:]


def _stream_reply(p: _Prepared, sw: observability.Stopwatch, usage: dict, outcome: dict) -> Iterator[dict]:
    """Yield checked sentences as the LLM writes them; fill `outcome` with the final reply."""
    safety, shown, buffer, first = p.safety, "", "", True
    outcome.update(reply="", path="llm_stream", reasons=(), replaced=False)

    def check(text: str):
        return output_guard.check(text, user_message=p.message, crisis=False, crisis_subtype="none")

    try:
        with sw.stage("llm"):
            pieces = llm_client.stream(p.messages, usage=usage)
            for piece in pieces:
                buffer += piece
                sentences, buffer = split_sentences(buffer)
                for sentence in sentences:
                    guarded = check(shown + sentence)
                    if guarded.replaced:
                        log.warning("Output guard replaced a streamed reply — reasons=%s", ",".join(guarded.reasons))
                        outcome.update(reply=guarded.text, reasons=guarded.reasons, replaced=True)
                        yield {"type": "replace", "text": guarded.text}
                        pieces.close()
                        return
                    shown += sentence
                    if first:
                        sw.ms["first_text"] = (time.perf_counter() - sw.started) * 1000
                        first = False
                    yield {"type": "delta", "text": sentence}
        rest = buffer.strip()
        if rest:
            guarded = check(shown + rest)
            if guarded.replaced:
                outcome.update(reply=guarded.text, reasons=guarded.reasons, replaced=True)
                yield {"type": "replace", "text": guarded.text}
                return
            if first:
                sw.ms["first_text"] = (time.perf_counter() - sw.started) * 1000
            shown += rest
            yield {"type": "delta", "text": rest}
        if not shown.strip():
            raise llm_client.LLMUnavailable("empty completion")
        outcome["reply"] = shown.strip()
    except llm_client.LLMUnavailable:
        reply = _llm_unavailable_reply(safety)
        outcome.update(reply=reply, path="fallback", reasons=(), replaced=False)
        yield {"type": "replace", "text": reply}


def _finish(p: _Prepared, reply: str, path: str, reasons: tuple, replaced: bool) -> TurnResult:
    """The result of an LLM turn, and what it leaves in memory."""
    safety, prompt = p.safety, p.prompt
    # The reflection was asked for in the prompt only on an emotional turn; show its chain only if the LLM's
    # reply went out unchanged.
    insight = None
    if (p.connections is not None and p.connections.ready and prompt["intent_category"] == "emotional"
            and path in ("llm", "llm_stream") and not replaced):
        insight = p.connections.chain
    if p.session is not None:
        _remember(p.session, p.message, safety, p.analysis, insight is not None)

    feeling = prompt["debug"]["feeling"]
    return TurnResult(
        reply=reply,
        intent="crisis" if safety.is_crisis else prompt["intent"],
        emotion=feeling.get("emotion", "neutral"),
        sentiment=feeling.get("sentiment", "neutral"),
        crisis_flag=safety.is_crisis,
        crisis_subtype=safety.crisis_subtype,
        risk_level=safety.risk_level,
        injection_detected=safety.injection,
        debug={"safety": safety.signals, "path": path, "route": p.route, "tools": prompt.get("tools", []),
               "guard_reasons": list(reasons),
               "intent_category": prompt["intent_category"], "rag_hits": prompt["rag_hits"],
               "memory": sorted(p.context) if p.context else []},
        insight=insight,
    )
