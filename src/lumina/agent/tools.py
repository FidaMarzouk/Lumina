"""Tools: what a signed-in person can ask Lumina to look up (A2) or save (A3) in their own data.

Write tools never run when the model picks them.  The model's arguments are validated and turned into a
proposal (`prepare`: the exact words, the date, a one-line summary), stored as pending, and shown to the person
with a Save button; only POST /actions/{id}/confirm runs it (`run`).  The model gets no delete tool: deleting
is done by the person in the app, one entry at a time.

Every tool:
  * takes validated arguments (a Pydantic model; anything else is refused) and NEVER a user id: the user comes
    from the signed-in session (ToolContext), so a tool can only ever read the person's own data;
  * returns data only — dates, titles, labels and short excerpts (EXCERPT_CHARS) — which the reply prompt treats
    as data, not instructions;
  * read tools: what Lumina noted (session summaries = journal pages, detected feelings), the jar, journey
    progress, and what the person saved themselves (journal entries, sleep and mood logs).

To the person there is one journal and one mood, so one look-up each: `journal_search` searches the pages
Lumina wrote and the entries they saved; `feelings_over_time` gives the feelings detected in conversations (and
says they were detected) and the moods they logged.  Their own saves are returned even with memory switched off.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..journey import planner
from ..memory.store import Store, parse_iso, visible_text

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


Weather = Literal["clear", "part", "fog", "rain", "storm"]
_WEATHER_WORDS = {"clear": "clear", "part": "partly cloudy", "fog": "foggy", "rain": "rainy", "storm": "stormy"}


class DaysArgs(_Args):
    days: int = Field(default=14, ge=1, le=400, description="How many days back to look.")


class JournalSaveArgs(_Args):
    text: str = Field(min_length=1, max_length=2000,
                      description="Exactly what they want saved, in their own words, copied from their message.")


class SleepLogArgs(_Args):
    hours: float = Field(ge=0, le=16, description="Hours slept.")
    quality: Literal["poor", "ok", "good"] | None = Field(default=None, description="How it felt, if they said.")
    night: Literal["last_night", "night_before"] = Field(default="last_night", description="Which night.")


class MoodLogArgs(_Args):
    weather: Weather = Field(description="Their mood as inner weather: clear, part (partly cloudy), fog, rain, storm.")
    note: str | None = Field(default=None, max_length=300, description="A few words they added, if any.")


class JarAddArgs(_Args):
    text: str = Field(min_length=1, max_length=80, description="The thing that helped, in a few words.")


def _excerpt(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= EXCERPT_CHARS else text[:EXCERPT_CHARS - 1].rsplit(" ", 1)[0] + "…"


def _day(ts: str) -> str:
    return parse_iso(ts).strftime("%A %d %B %Y")


def _memory_off() -> dict:
    return {"unavailable": "Memory is switched off, so Lumina keeps no notes to look back on."}


def journal_search(ctx: ToolContext, args: JournalSearchArgs) -> dict:
    out = _journal_pages(ctx, args) if ctx.memory_enabled else _memory_off()
    out["saved_entries"], note = _saved_entries(ctx, args)
    if note:
        out["saved_entries_note"] = note
    return out


def _saved_entries(ctx: ToolContext, args: JournalSearchArgs) -> tuple[list[dict], str | None]:
    """The entries they saved themselves in the window, best match first when there is a query."""
    # Scratched-out words are gone; entries saved at crisis risk are not read back (as crisis conversations).
    entries = [{**e, "text": visible_text(e["text"])}
               for e in ctx.store.journal_entries(ctx.user_id, since=ctx.now - timedelta(days=args.days_back))
               if e["risk"] != "crisis" and visible_text(e["text"])]
    if not entries:
        return [], "No entries saved in that period."
    if args.query and ctx.embed is not None:
        import numpy as np
        q = ctx.embed(args.query)
        scored = sorted(((float(np.dot(q, ctx.embed(e["text"]))), e) for e in entries[:50]), key=lambda p: -p[0])
        entries = [e for score, e in scored if score >= MIN_PAGE_SIMILARITY]
        if not entries:
            return [], "No saved entry in that period is about that."
    return [{"date": _day(e["created_at"]), "text": _excerpt(e["text"])} for e in entries[:MAX_RESULTS]], None


def _journal_pages(ctx: ToolContext, args: JournalSearchArgs) -> dict:
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
    out = _detected_feelings(ctx, args) if ctx.memory_enabled else _memory_off()
    days = ctx.store.mood_logs(ctx.user_id, since_day=(ctx.now - timedelta(days=args.days)).date().isoformat())
    out["logged_moods"] = {"source": "moods they logged themselves, as inner weather",
                           "days": [{"day": d["day"], "mood": _WEATHER_WORDS[d["weather"]],
                                     "note": _excerpt(d["note"]) if d["note"] else None} for d in days[:14]],
                           "note": None if days else "No moods logged in that period."}
    return out


def _detected_feelings(ctx: ToolContext, args: FeelingsArgs) -> dict:
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


# ── reading the sleep they logged (A3) ──────────────────────────────────────
def sleep_history(ctx: ToolContext, args: DaysArgs) -> dict:
    nights = ctx.store.sleep_logs(ctx.user_id, since_night=(ctx.now - timedelta(days=args.days)).date().isoformat())
    hours = [n["hours"] for n in nights]
    return {"nights": [{"night of": n["night"], "hours": n["hours"], "quality": n["quality"]} for n in nights[:14]],
            "average_hours": round(sum(hours) / len(hours), 1) if hours else None,
            "note": None if nights else "No sleep logged in that period."}


# ── writing: prepare a proposal, run on confirmation (A3) ─────────────────────
def _night(ctx: ToolContext, which: str) -> str:
    return (ctx.now - timedelta(days=1 if which == "last_night" else 2)).date().isoformat()


def prepare_journal(ctx: ToolContext, args: JournalSaveArgs) -> tuple[dict, str]:
    text = " ".join(args.text.split()) if "\n" not in args.text else args.text.strip()
    return {"text": text}, f'Save to your journal: "{_excerpt(text)}"'


def journal_risk(text: str) -> tuple[str, str]:
    """(risk level, crisis subtype) of words about to be saved to the journal: the same safety assessment as a
    chat message.  Tests replace ASSESS; a failure fails closed to "elevated" (help shown, not fed back unchecked)."""
    try:
        a = (ASSESS or _assess)(text)
        return a.risk_level, a.crisis_subtype
    except Exception:
        return "elevated", "none"


def _assess(text: str):
    from ..safety.assessment import assess
    return assess(text, [])


ASSESS: Callable | None = None


def run_journal(ctx: ToolContext, stored: dict) -> dict:
    risk, subtype = journal_risk(stored["text"])
    entry = ctx.store.add_journal_entry(ctx.user_id, stored["text"], now=ctx.now, risk=risk)
    return {**entry, "support": subtype if risk == "crisis" else ("elevated" if risk == "elevated" else None)}


def prepare_sleep(ctx: ToolContext, args: SleepLogArgs) -> tuple[dict, str]:
    night = _night(ctx, args.night)
    label = parse_iso(night + "T00:00:00+00:00").strftime("%A %d %B")
    hours = int(args.hours) if args.hours == int(args.hours) else args.hours
    quality = f", {args.quality}" if args.quality else ""
    return ({"night": night, "hours": args.hours, "quality": args.quality},
            f"Log {hours} hour{'s' if args.hours != 1 else ''} of sleep for the night of {label}{quality}")


def run_sleep(ctx: ToolContext, stored: dict) -> dict:
    return ctx.store.add_sleep_log(ctx.user_id, stored["night"], stored["hours"], stored["quality"], now=ctx.now)


def prepare_mood(ctx: ToolContext, args: MoodLogArgs) -> tuple[dict, str]:
    note = f': "{_excerpt(args.note)}"' if args.note else ""
    return ({"day": ctx.now.date().isoformat(), "weather": args.weather, "note": args.note},
            f"Log today's mood as {_WEATHER_WORDS[args.weather]}{note}")


def run_mood(ctx: ToolContext, stored: dict) -> dict:
    return ctx.store.add_mood_log(ctx.user_id, stored["day"], stored["weather"], stored["note"], now=ctx.now)


def prepare_jar(ctx: ToolContext, args: JarAddArgs) -> tuple[dict, str]:
    text = " ".join(args.text.split())
    return {"text": text}, f'Add to your jar of things that helped: "{text}"'


def run_jar(ctx: ToolContext, stored: dict) -> dict:
    item = ctx.store.add_jar_item(ctx.user_id, stored["text"], "kept", now=ctx.now)
    return {"id": item["id"], "text": item["text"]}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[_Args]
    run: Callable[[ToolContext, _Args], dict]
    prepare: Callable[[ToolContext, _Args], tuple[dict, str]] | None = None   # write tools only

    @property
    def writes(self) -> bool:
        return self.prepare is not None

    def schema(self) -> dict:
        params = self.args.model_json_schema()
        params.pop("title", None)
        for p in params.get("properties", {}).values():
            p.pop("title", None)
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                                                 "parameters": params}}


READ_TOOLS: dict[str, Tool] = {t.name: t for t in (
    Tool("journal_search", "Look up the person's own journal: the pages from their past conversations with Lumina "
         "and the entries they saved, by topic or by recency. Use when they ask what they wrote, saved, said or "
         "talked about before.",
         JournalSearchArgs, journal_search),
    Tool("feelings_over_time", "Summarise their mood: the feelings that came up in their conversations, week by "
         "week, and the moods they logged. Use when they ask how their mood or feelings have been lately.",
         FeelingsArgs, feelings_over_time),
    Tool("jar_list", "List the things they kept in their jar of things that helped. Use when they ask what helped "
         "them before or what is in their jar.", NoArgs, jar_list),
    Tool("journey_status", "Say which guided journey and step they are on, and which they finished. Use when they "
         "ask where they are in their journey or what comes next.", NoArgs, journey_status),
    Tool("sleep_history", "Read back the sleep they logged, night by night, with the average. Use when they ask "
         "how they have been sleeping or what they logged.", DaysArgs, sleep_history),
)}

WRITE_TOOLS: dict[str, Tool] = {t.name: t for t in (
    Tool("journal_save", "Save words to their own journal. Use only when they clearly ask to save, note or write "
         "something down; copy their words exactly.", JournalSaveArgs, run_journal, prepare_journal),
    Tool("sleep_log", "Log how long (and how well) they slept. Use only when they ask to log or track their sleep.",
         SleepLogArgs, run_sleep, prepare_sleep),
    Tool("mood_log", "Log today's mood as inner weather. Use only when they ask to log, track or mark their mood.",
         MoodLogArgs, run_mood, prepare_mood),
    Tool("jar_add", "Add something that helped them to their jar. Use only when they ask to add or keep it.",
         JarAddArgs, run_jar, prepare_jar),
)}
ALL_TOOLS: dict[str, Tool] = {**READ_TOOLS, **WRITE_TOOLS}


# At "elevated" risk (not after a crisis: then no tools at all) only these are offered: the person's own list of
# what helped and where they are in a journey.  Journal pages and feelings over time can bring back hard material.
# Saving their own words or a log is not withheld at "elevated" risk either.
ELEVATED_SAFE = ("jar_list", "journey_status", "journal_save", "sleep_log", "mood_log", "jar_add")


def stored_texts(result: dict) -> list[str]:
    """The text in a tool result that comes from what was stored about the person (summaries, titles, themes,
    jar items).  Everything else in a result is the app's own wording or fixed labels (emotion names, journey
    titles from configs/journeys)."""
    texts = list(result.get("things_that_helped") or [])
    texts += [e.get("text") or "" for e in result.get("saved_entries") or []]
    texts += [d.get("note") or "" for d in (result.get("logged_moods") or {}).get("days") or []]
    for page in [*(result.get("pages") or []), *([result["most_recent_page"]] if result.get("most_recent_page") else [])]:
        texts += [page.get("summary") or "", page.get("title") or "", *(page.get("themes") or [])]
    return [t for t in texts if t]


_NUMBER_WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve "
                                              "thirteen fourteen fifteen sixteen".split())}
GROUNDED_SHARE = 0.8


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def grounded(name: str, stored: dict, message: str) -> bool:
    """Whether a proposal's details come from the person's message rather than the model: the hours they slept
    are a number they wrote, and saved words are (at least GROUNDED_SHARE of them) their own words.  The mood's
    weather is a choice of five and is not checked; the summary on the Save slip shows it before anything is kept."""
    said = _words(message)
    if name == "sleep_log":
        numbers = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", message)}
        numbers |= {float(_NUMBER_WORDS[w]) for w in said if w in _NUMBER_WORDS}
        whole = float(int(stored["hours"]))
        return stored["hours"] in numbers or whole in numbers          # "5 and a half" → 5.5 keeps the 5
    text = stored.get("text") if name in ("journal_save", "jar_add") else stored.get("note")
    if not text:
        return True
    words, pool = _words(text), set(said)
    return not words or sum(w in pool for w in words) / len(words) >= GROUNDED_SHARE


def propose(name: str, raw_args: dict | None, ctx: ToolContext) -> tuple[dict, str] | None:
    """Validate a write tool's untrusted arguments into (what will be stored, the summary the person confirms)."""
    tool = WRITE_TOOLS.get(name)
    if tool is None:
        return None
    try:
        args = tool.args.model_validate(raw_args or {})
    except ValidationError:
        return None
    return tool.prepare(ctx, args)


def call(name: str, raw_args: dict | None, ctx: ToolContext, allowed: tuple[str, ...] | None = None) -> dict:
    """Run one READ tool by name with untrusted arguments.  Unknown or not-offered tools and invalid arguments are
    refused; write tools never run here (see propose / POST /actions/{id}/confirm)."""
    tool = READ_TOOLS.get(name)
    if tool is None or (allowed is not None and name not in allowed):
        return {"error": f"There is no tool called {name}."}
    try:
        args = tool.args.model_validate(raw_args or {})
    except ValidationError:
        return {"error": "The tool was asked for something it cannot do."}
    return tool.run(ctx, args)
