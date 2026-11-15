"""Read tools (A2): what a signed-in person can ask Lumina to look up in their own stored notes.

Every tool:
  * takes validated arguments (a Pydantic model; anything else is refused) and NEVER a user id: the user comes
    from the signed-in session (ToolContext), so a tool can only ever read the person's own data;
  * returns data only — dates, titles, labels and short excerpts (EXCERPT_CHARS) — which the reply prompt treats
    as data, not instructions;
  * reads only.  Writing (journal entries, sleep and mood logs, reminders, deleting) is roadmap item A3.

What exists to read: session summaries (the journal pages, with themes and the feelings detected in the
conversation), the jar of things that helped, and journey progress.  There is no self-reported mood or sleep
log yet, so `feelings_over_time` says plainly that its feelings were detected, not reported.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..journey import planner
from ..memory.store import Store, parse_iso

EXCERPT_CHARS = 200
MAX_RESULTS = 5
MIN_PAGE_SIMILARITY = 0.15


@dataclass(frozen=True)
class ToolContext:
    store: Store
    user_id: str
    memory_enabled: bool
    now: datetime
    embed: Callable | None = None          # text → unit vector (tests pass a stub)


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JournalSearchArgs(_Args):
    query: str | None = Field(default=None, max_length=200,
                              description="What to look for, in a few words (a person, a topic, a feeling). "
                                          "Leave out to get the most recent pages.")
    days_back: int = Field(default=30, ge=1, le=400, description="How many days back to look.")


class FeelingsArgs(_Args):
    days: int = Field(default=14, ge=7, le=120, description="How many days back to summarise.")


class NoArgs(_Args):
    pass


def _excerpt(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= EXCERPT_CHARS else text[:EXCERPT_CHARS - 1].rsplit(" ", 1)[0] + "…"


def _day(ts: str) -> str:
    return parse_iso(ts).strftime("%A %d %B %Y")


def _memory_off() -> dict:
    return {"unavailable": "Memory is switched off, so Lumina keeps no notes to look back on."}


def journal_search(ctx: ToolContext, args: JournalSearchArgs) -> dict:
    if not ctx.memory_enabled:
        return _memory_off()
    every = sorted((e for e in ctx.store.user_episodes(ctx.user_id) if not e["had_crisis"]),
                   key=lambda e: e["created_at"], reverse=True)
    titles = {i["session_id"]: (i.get("evidence") or {}).get("title")
              for i in ctx.store.list_insights(ctx.user_id, kind="session", limit=1000)}
    since = ctx.now - timedelta(days=args.days_back)
    episodes = [e for e in every if parse_iso(e["created_at"]) >= since]
    if not episodes:
        # "What did I write yesterday?" is asked as days_back=1 while the last page is 30 hours old: say what the
        # most recent page is rather than only "nothing in the last 1 days".
        return {"pages": [], "note": "No journal page in that period.",
                "most_recent_page": _page(every[0], titles) if every else None}
    if args.query and ctx.embed is not None:
        import numpy as np
        q = ctx.embed(args.query)
        scored = [(float(np.dot(q, e["embedding"])) if e["embedding"] is not None else -1.0, e) for e in episodes]
        # A short query ("friend") scores 0.18-0.29 against a page about it and 0.08-0.15 against unrelated pages
        # (all-MiniLM-L6-v2), so the floor sits between them and the rest is ranking.
        episodes = [e for score, e in sorted(scored, key=lambda p: -p[0]) if score >= MIN_PAGE_SIMILARITY]
        if not episodes:
            return {"pages": [], "note": "No journal page in that period is about that."}
    return {"pages": [_page(e, titles) for e in episodes[:MAX_RESULTS]]}


def _page(e: dict, titles: dict) -> dict:
    return {"date": _day(e["created_at"]), "title": titles.get(e["session_id"]), "summary": _excerpt(e["summary"]),
            "themes": e["themes"][:4]}


def feelings_over_time(ctx: ToolContext, args: FeelingsArgs) -> dict:
    if not ctx.memory_enabled:
        return _memory_off()
    turns = [t for t in ctx.store.user_turns(ctx.user_id, since=ctx.now - timedelta(days=args.days))
             if t["risk_level"] != "crisis" and t["emotion"] and t["emotion"] != "neutral"]
    weeks: dict[str, Counter] = {}
    for t in turns:
        start = parse_iso(t["ts"]) - timedelta(days=parse_iso(t["ts"]).weekday())
        weeks.setdefault(start.strftime("week of %d %B"), Counter())[t["emotion"]] += 1
    return {"source": "feelings detected automatically in what they wrote, not ones they reported; may be wrong",
            "weeks": [{"week": w, "feelings": [f"{e} (in {n} message{'s' if n > 1 else ''})" for e, n in c.most_common(3)]}
                      for w, c in weeks.items()],
            "note": None if weeks else "No conversations with a clear feeling in that period."}


def jar_list(ctx: ToolContext, args: NoArgs) -> dict:
    kept = [i for i in ctx.store.jar_items(ctx.user_id) if i["status"] == "kept"]
    return {"things_that_helped": [_excerpt(i["text"]) for i in kept[-20:]],
            "note": None if kept else "The jar is empty so far."}


def journey_status(ctx: ToolContext, args: NoArgs) -> dict:
    progress = ctx.store.journey_progress(ctx.user_id)
    active = planner.active_step(ctx.store, ctx.user_id)
    from ..journey import catalog
    done = [catalog.get(j).title for j, row in progress.items() if row["status"] == "completed" and catalog.get(j)]
    if active:
        return {"current": {"journey": active["journey_title"], "step": active["title"],
                            "step_number": active["step_index"] + 1, "steps": active["step_count"]},
                "completed_journeys": done}
    return {"current": None, "completed_journeys": done, "note": "No journey in progress."}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[_Args]
    run: Callable[[ToolContext, _Args], dict]

    def schema(self) -> dict:
        params = self.args.model_json_schema()
        params.pop("title", None)
        for p in params.get("properties", {}).values():
            p.pop("title", None)
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                                                 "parameters": params}}


READ_TOOLS: dict[str, Tool] = {t.name: t for t in (
    Tool("journal_search", "Look up the person's own journal pages (summaries of their past conversations with "
         "Lumina), by topic or by recency. Use when they ask what they wrote, said or talked about before.",
         JournalSearchArgs, journal_search),
    Tool("feelings_over_time", "Summarise which feelings came up in their conversations, week by week. Use when "
         "they ask how their mood or feelings have been lately.", FeelingsArgs, feelings_over_time),
    Tool("jar_list", "List the things they kept in their jar of things that helped. Use when they ask what helped "
         "them before or what is in their jar.", NoArgs, jar_list),
    Tool("journey_status", "Say which guided journey and step they are on, and which they finished. Use when they "
         "ask where they are in their journey or what comes next.", NoArgs, journey_status),
)}


# At "elevated" risk (not after a crisis: then no tools at all) only these are offered: the person's own list of
# what helped and where they are in a journey.  Journal pages and feelings over time can bring back hard material.
ELEVATED_SAFE = ("jar_list", "journey_status")


def stored_texts(result: dict) -> list[str]:
    """The text in a tool result that comes from what was stored about the person (summaries, titles, themes,
    jar items).  Everything else in a result is the app's own wording or fixed labels (emotion names, journey
    titles from configs/journeys)."""
    texts = list(result.get("things_that_helped") or [])
    for page in [*(result.get("pages") or []), *([result["most_recent_page"]] if result.get("most_recent_page") else [])]:
        texts += [page.get("summary") or "", page.get("title") or "", *(page.get("themes") or [])]
    return [t for t in texts if t]


def call(name: str, raw_args: dict | None, ctx: ToolContext, allowed: tuple[str, ...] | None = None) -> dict:
    """Run one tool by name with untrusted arguments.  Unknown or not-offered tools and invalid arguments are refused."""
    tool = READ_TOOLS.get(name)
    if tool is None or (allowed is not None and name not in allowed):
        return {"error": f"There is no tool called {name}."}
    try:
        args = tool.args.model_validate(raw_args or {})
    except ValidationError:
        return {"error": "The tool was asked for something it cannot do."}
    return tool.run(ctx, args)
