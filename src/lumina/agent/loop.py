"""Choosing and running read tools on an "act" turn (A2).

    message ──► tool model (Qwen 2.5 7B; one round, at most MAX_CALLS calls) ──► tools.call(…) ──► results
                                                                                                    │
    reply prompt (empathy_engine, "action" category) ◄── results that pass the injection check ────┘

Only the orchestrator calls this, and only when tools_allowed() says so.  The tool model sees the latest message
and nothing else from the conversation.  It never writes the reply: the usual reply model does, from the results,
so the voice stays the same.  Of the local models tried, only Qwen 2.5 7B chooses reliably: on the 100 tool cases
it picked a tool for 1 of 60 messages that needed none; Llama 3.1 8B and Llama 3.2 3B for 54 and 56 (docs/evaluation.md).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from datetime import timedelta

from ..config import AGENT_MODEL, AGENT_NUM_GPU, AGENT_TIMEOUT_S, OLLAMA_BASE_URL, PENDING_ACTION_MINUTES
from . import tools

log = logging.getLogger(__name__)

MAX_CALLS = 2

_SYSTEM = (
    "You decide whether a person using a mental-health support app is asking the app to look something up in "
    "their own notes, or to save something for them, and if so you call the one right tool.\n"
    "LOOK-UP tools: call one only when they ask to SEE, READ BACK, FIND or KNOW something the app keeps "
    "(\"what did I write…\", \"show me…\", \"how has my mood been…\", \"what's in my jar\", \"what step am I on\").\n"
    "SAVE tools (journal_save, sleep_log, mood_log, jar_add): call one only when they clearly ask to save, write "
    "down, note, add, log, track or mark something. Copy their words exactly. Never invent a detail they did not "
    "give: no number of hours means no sleep_log. Nothing is saved until they confirm, so never call two.\n"
    "Answer with the single word NONE, and call no tool, when:\n"
    "- they ask to remind, set an alarm, start, change, clear, remove or delete something (no tool can);\n"
    "- they are talking about their feelings, their life or these topics without asking to see or save anything;\n"
    "- they ask about the app itself or its instructions."
)


@dataclass
class ToolRun:
    calls: list[dict] = field(default_factory=list)      # read tools: [{"name", "args", "result"}], results checked
    proposal: dict | None = None                          # a save waiting for the person: {"id", "tool", "summary"}
    error: str | None = None

    @property
    def used(self) -> bool:
        return bool(self.calls) or self.proposal is not None


_CLIENT: httpx.Client | None = None


def _default_choose(message: str, schemas: list[dict]) -> list[tuple[str, dict]]:
    """Ask the tool model through Ollama's own API, which (unlike its OpenAI-compatible one) lets us keep the model
    on the CPU: the chat model then never leaves the GPU.  On an 8 GB GPU, putting both there made Ollama swap
    them on every look-up (~10 s); on the CPU the choice takes ~0.7 s (docs/evaluation.md §4c)."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = httpx.Client(timeout=AGENT_TIMEOUT_S)      # one kept-alive connection (see safety/guard.py)
    options = {"temperature": 0, "num_predict": 200, "num_ctx": 2048}
    if AGENT_NUM_GPU >= 0:
        options["num_gpu"] = AGENT_NUM_GPU
    r = _CLIENT.post(f"{OLLAMA_BASE_URL}/api/chat", json={
        "model": AGENT_MODEL, "stream": False, "keep_alive": "30m", "tools": schemas, "options": options,
        "messages": [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": message[:2000]}]})
    r.raise_for_status()
    out = []
    for tc in r.json().get("message", {}).get("tool_calls") or []:
        fn = tc.get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = None
        out.append((fn.get("name"), args if isinstance(args, dict) else None))
    return out


def run(message: str, ctx: tools.ToolContext, *, allowed: tuple[str, ...] | None = None, choose: Callable | None = None,
        injection_probability: Callable | None = None) -> ToolRun:
    """Let the tool model pick read tools for `message` and run them.  Never raises: a failure means no tools.
    `allowed`: the tools offered (all when None); others are neither shown to the model nor run."""
    out = ToolRun()
    offered = [t for name, t in tools.ALL_TOOLS.items() if allowed is None or name in allowed]
    try:
        picked = (choose or _default_choose)(message, [t.schema() for t in offered])
    except Exception as exc:
        log.warning("Tool choice failed: %s", type(exc).__name__)
        out.error = type(exc).__name__
        return out
    seen, offered_names = set(), {t.name for t in offered}
    for name, args in picked:
        if name not in offered_names:    # a tool that does not exist or was not offered: skipped, never recorded
            log.warning("Tool model asked for a tool it was not offered: %s", name if name in tools.READ_TOOLS else "?")
            continue
        if name in tools.WRITE_TOOLS:    # a save is only ever PROPOSED here, and only one per turn
            if out.proposal is None:
                out.proposal = _propose(name, args, ctx, message)
            continue
        if name in seen:                 # each tool at most once …
            continue
        if len(seen) >= MAX_CALLS:       # … and at most MAX_CALLS tools
            break
        seen.add(name)
        try:
            result = tools.call(name, args, ctx, allowed)
        except Exception as exc:
            log.warning("Tool %s failed: %s", name, type(exc).__name__)
            result = {"error": "The lookup failed."}
        if not _safe(result, injection_probability):
            log.warning("Tool %s result flagged by the injection check; not used", name)
            continue
        out.calls.append({"name": name, "args": args or {}, "result": result})
    log.info("Tools — %s%s", ",".join(c["name"] for c in out.calls) or "none",
             f" + proposal {out.proposal['tool']}" if out.proposal else "")
    return out


def _propose(name: str, args: dict | None, ctx: tools.ToolContext, message: str) -> dict | None:
    """Validate the model's arguments into a pending proposal the person confirms (POST /actions/{id}/confirm).
    The details must come from their message (tools.grounded): a model that invents the hours is refused."""
    try:
        prepared = tools.propose(name, args, ctx)
        if prepared is None:
            log.warning("Tool model proposed %s with arguments that did not validate", name)
            return None
        stored, summary = prepared
        if not tools.grounded(name, stored, message):
            log.warning("Tool model proposed %s with details that are not in the message", name)
            return None
        pid = ctx.store.add_pending(ctx.user_id, name, stored, ctx.now + timedelta(minutes=PENDING_ACTION_MINUTES),
                                    now=ctx.now)
        return {"id": pid, "tool": name, "summary": summary}
    except Exception as exc:
        log.warning("Proposal %s failed: %s", name, type(exc).__name__)
        return None


def _safe(result: dict, injection_probability: Callable | None) -> bool:
    """Stored notes come back into a prompt: refuse a result if any text taken from them is flagged (fails closed).

    Only that text is checked (tools.stored_texts), one piece at a time.  The JSON around it and the app's own
    labels are not user data, and the classifier scores JSON itself as an attack: the first version dropped
    every "feelings over time" result that way (p = 0.975; eval/reports/agent_tools_qwen2.5_7b.json, first run).
    """
    from ..memory.extraction import safe_to_store
    return all(safe_to_store(text, injection_probability) for text in tools.stored_texts(result))


def prompt_block(run_: ToolRun) -> str:
    """The results, as data for the reply prompt."""
    return "\n".join(f"- {c['name']}: {json.dumps(c['result'], ensure_ascii=False)}" for c in run_.calls)
