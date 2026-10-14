"""Memory for one conversational turn — what the orchestrator reads before the reply and writes after it.

    before:  load_context()   → past episodes relevant to the message, the in-session
                                thought/feeling/behaviour chain, and the guided journey step
    after:   record_turn()    → labels for this turn (no text)
             extract_async()  → CBT elements for this turn, in the background

Crisis and injection turns are recorded as a risk level only: no labels, no extraction, and
the orchestrator does not load memory for them.  Nothing here runs when memory is off, except
the guided step (journeys work without memory).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from dataclasses import dataclass
from datetime import datetime

from ..config import MEMORY_EXTRACTION, MEMORY_MIN_SIMILARITY, MEMORY_TOP_K
from ..insights import in_session
from ..insights.in_session import Connections
from ..journey import catalog
from . import extraction
from .store import Store, parse_iso, utcnow

log = logging.getLogger(__name__)

# Intents whose messages describe the person's own situation; small talk and factual questions have no
# CBT triangle to extract, so they cost no LLM call.
_EXTRACT_INTENTS = {"venting", "seeking_advice", "seeking_validation", "help_seeking", "sharing_experience"}

_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="memory")
_PENDING: dict[str, list[Future]] = {}
_PENDING_LOCK = threading.Lock()


@dataclass(frozen=True)
class SessionContext:
    user_id: str
    session_id: str
    memory_enabled: bool
    mode: str = "open"
    journey_id: str | None = None
    step_id: str | None = None
    display_name: str = ""


def human_when(created_at: str, now: datetime | None = None) -> str:
    then = parse_iso(created_at)
    days = ((now or utcnow()) - then).days
    if days <= 0:
        return "earlier today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 14:
        return "last week"
    if days < 60:
        return f"{days // 7} weeks ago"
    return then.strftime("in %B %Y")


def guided_step(ctx: SessionContext) -> dict | None:
    if ctx.mode != "guided" or not ctx.journey_id:
        return None
    journey = catalog.get(ctx.journey_id)
    index = journey.step_index(ctx.step_id) if journey and ctx.step_id else None
    if index is None:
        return None
    step = journey.steps[index]
    return {"journey": journey.title, "approach": journey.approach, "title": step.title,
            "goal": step.goal, "guidance": step.guidance}


def recall(store: Store, ctx: SessionContext, message: str, embed: Callable | None = None,
           now: datetime | None = None) -> list[dict]:
    """Up to MEMORY_TOP_K earlier episodes similar to `message` (crisis sessions are never recalled)."""
    episodes = [e for e in store.user_episodes(ctx.user_id)
                if e["session_id"] != ctx.session_id and not e["had_crisis"] and e["embedding"] is not None]
    if not episodes:
        return []
    from .embeddings import cosine
    try:
        query = (embed or _embed)(message)
    except Exception as exc:
        log.warning("Memory recall unavailable: %s", type(exc).__name__)
        return []
    scored = sorted(((cosine(query, e["embedding"]), e) for e in episodes), key=lambda p: -p[0])
    return [{"when": human_when(e["created_at"], now), "summary": e["summary"]}
            for score, e in scored[:MEMORY_TOP_K] if score >= MEMORY_MIN_SIMILARITY]


def _embed(text: str):
    from .embeddings import embed
    return embed(text)


def load_context(store: Store, ctx: SessionContext, message: str,
                 embed: Callable | None = None) -> tuple[dict, Connections | None]:
    """(memory dict for empathy_engine.build_prompt, in-session connections or None)."""
    memory: dict = {"name": ctx.display_name}
    step = guided_step(ctx)
    if step:
        memory["guided_step"] = step
    conn = None
    if ctx.memory_enabled:
        conn = in_session.build(store.session_turns(ctx.session_id))
        if conn.turns_with_elements:
            memory["connections"] = conn.as_prompt_dict()
        memory["recalled"] = recall(store, ctx, message, embed)
    return memory, conn


def record_turn(store: Store, ctx: SessionContext, *, safety, nlp: dict | None, feeling: dict | None) -> int | None:
    """Store this turn's labels (never its text).  Returns the row id, or None when memory is off."""
    if not ctx.memory_enabled:
        return None
    if safety.is_crisis or safety.injection or nlp is None or feeling is None:
        return store.add_turn(ctx.session_id, ctx.user_id, intent=None, emotion=None, sentiment=None,
                              pain_points=[], macro=None, risk_level=safety.risk_level)
    return store.add_turn(ctx.session_id, ctx.user_id, intent=nlp.get("intent"), emotion=feeling.get("emotion"),
                          sentiment=feeling.get("sentiment"), pain_points=list(nlp.get("pain_points", [])),
                          macro=nlp.get("primary_macro"), risk_level=safety.risk_level)


def should_extract(safety, nlp: dict | None) -> bool:
    return (MEMORY_EXTRACTION and not safety.is_crisis and not safety.injection and nlp is not None
            and nlp.get("intent") in _EXTRACT_INTENTS)


def extract_and_store(store: Store, turn_id: int, message: str, complete: Callable | None = None,
                      injection_probability: Callable | None = None) -> None:
    elements = extraction.extract_elements(message, complete)
    if not elements.is_empty() and not extraction.safe_to_store(extraction.elements_text(elements),
                                                                 injection_probability):
        log.warning("Extracted notes flagged by the injection check; not stored")
        return
    store.set_turn_elements(turn_id, elements.model_dump())


def extract_async(store: Store, session_id: str, turn_id: int, message: str) -> None:
    def job():
        try:
            extract_and_store(store, turn_id, message)
        except Exception as exc:
            log.warning("Background extraction failed: %s", type(exc).__name__)
    future = _POOL.submit(job)
    with _PENDING_LOCK:
        _PENDING.setdefault(session_id, []).append(future)


def wait_for_session(session_id: str, timeout: float = 30.0) -> None:
    """Let in-flight extractions of a session finish before it is summarised."""
    with _PENDING_LOCK:
        futures = _PENDING.pop(session_id, [])
    if futures:
        wait_futures(futures, timeout=timeout)
