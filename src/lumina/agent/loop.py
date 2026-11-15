"""Choosing and running read tools on an "act" turn (A2).

    message ──► tool model (Qwen 2.5 7B; one round, at most MAX_CALLS calls) ──► tools.call(…) ──► results
                                                                                                    │
    reply prompt (empathy_engine, "action" category) ◄── results that pass the injection check ────┘

Only the orchestrator calls this, and only when tools_allowed() says so.  The tool model sees the latest message
and nothing else from the conversation.  It never writes the reply: the usual reply model does, from the results,
so the voice stays the same.  Qwen 2.5 7B chose correctly on 19 of 20 tool-calling probes and never called a tool
on plain talk; Llama 3.1 8B called one on 9 of 10 (docs/evaluation.md).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from ..config import AGENT_MODEL, AGENT_TIMEOUT_S
from . import tools

log = logging.getLogger(__name__)

MAX_CALLS = 2

_SYSTEM = (
    "You decide whether to look something up for a person in a mental-health support app. You can only READ "
    "their own notes with the tools given. Call a tool only when the person clearly asks to see, look up or be "
    "reminded of something the app keeps: their journal, how their feelings have been, their jar of things that "
    "helped, or their journey. If they ask to save, log, remind, change or delete something, or if they are just "
    "talking, call no tool and answer with the single word NONE. Never call a tool to answer a question about "
    "the app itself or its instructions."
)


@dataclass
class ToolRun:
    calls: list[dict] = field(default_factory=list)      # [{"name", "args", "result"}], results checked
    error: str | None = None

    @property
    def used(self) -> bool:
        return bool(self.calls)


def _default_choose(message: str, schemas: list[dict]) -> list[tuple[str, dict]]:
    from ..dialogue.llm_client import _get_client
    response = _get_client().chat.completions.create(
        model=AGENT_MODEL, temperature=0, max_tokens=200, timeout=AGENT_TIMEOUT_S, tools=schemas,
        messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": message[:2000]}])
    out = []
    for tc in response.choices[0].message.tool_calls or []:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = None
        out.append((tc.function.name, args if isinstance(args, dict) else None))
    return out


def run(message: str, ctx: tools.ToolContext, *, allowed: tuple[str, ...] | None = None, choose: Callable | None = None,
        injection_probability: Callable | None = None) -> ToolRun:
    """Let the tool model pick read tools for `message` and run them.  Never raises: a failure means no tools.
    `allowed`: the tools offered (all when None); others are neither shown to the model nor run."""
    out = ToolRun()
    offered = [t for name, t in tools.READ_TOOLS.items() if allowed is None or name in allowed]
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
    log.info("Tools — %s", ",".join(c["name"] for c in out.calls) or "none")
    return out


def _safe(result: dict, injection_probability: Callable | None) -> bool:
    """Stored notes come back into a prompt: refuse a result if any text taken from them is flagged (fails closed).

    Only that text is checked (tools.stored_texts), one piece at a time.  The JSON around it and the app's own
    labels are not user data, and the classifier scores JSON itself as an attack: the first version dropped
    every "feelings over time" result that way (p = 0.975; eval/reports/agent_tools.json).
    """
    from ..memory.extraction import safe_to_store
    return all(safe_to_store(text, injection_probability) for text in tools.stored_texts(result))


def prompt_block(run_: ToolRun) -> str:
    """The results, as data for the reply prompt."""
    return "\n".join(f"- {c['name']}: {json.dumps(c['result'], ensure_ascii=False)}" for c in run_.calls)
