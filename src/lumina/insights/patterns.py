"""Pattern miner — deterministic statistics over a user's stored signals and episodes.

No LLM here: the weekly insight writer only puts into words what this module found.

    themes     pain points of the period, and which of them also came up in earlier weeks
    emotions   dominant emotions of the period vs the previous four weeks
    links      feeling → behaviour and thought → feeling pairs that recur across turns
    echo       the earlier episode most similar to one of this period's (embedding cosine
               ≥ MEMORY_MIN_SIMILARITY, at least PATTERN_MIN_GAP_DAYS old).  Episodes about a year
               old (PATTERN_LOOKBACK_DAYS ± PATTERN_YEAR_BAND_DAYS) are preferred; otherwise the most
               similar earlier one.

Crisis turns and episodes of sessions with a crisis are excluded from everything.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from ..config import (
    MEMORY_MIN_SIMILARITY,
    PATTERN_LOOKBACK_DAYS,
    PATTERN_MIN_GAP_DAYS,
    PATTERN_YEAR_BAND_DAYS,
    PATTERN_YEAR_MARGIN,
    WEEKLY_PERIOD_DAYS,
)
from ..memory.embeddings import cosine
from ..memory.store import Store, parse_iso, utcnow

_HISTORY_WEEKS = 4


@dataclass
class PatternReport:
    period_start: str
    period_end: str
    episodes: list[dict] = field(default_factory=list)          # this period: {date, summary, themes}
    themes: list[dict] = field(default_factory=list)            # {theme, count, earlier_weeks}
    emotions: dict = field(default_factory=dict)                # {"this_period": {...}, "before": {...}}
    links: list[dict] = field(default_factory=list)             # {kind, from, to, count}
    echo: dict | None = None                                    # {then, days_ago, summary_then, summary_now, similarity}

    def as_evidence(self) -> dict:
        return asdict(self)


def _share(counter: Counter) -> dict:
    total = sum(counter.values())
    return {k: round(v / total, 2) for k, v in counter.most_common(4)} if total else {}


def _links(turns: list[dict]) -> list[dict]:
    feel_do, think_feel = Counter(), Counter()
    for t in turns:
        e = t.get("elements") or {}
        for f in e.get("feelings", []):
            for b in e.get("behaviours", []):
                feel_do[(f, b)] += 1
            for th in e.get("thoughts", []):
                think_feel[(th, f)] += 1
    # A link is a pattern only when it repeats; one co-occurrence is just a moment.
    out = [{"kind": "feeling_then_behaviour", "from": f, "to": b, "count": n}
           for (f, b), n in feel_do.most_common(3) if n >= 2]
    out += [{"kind": "thought_then_feeling", "from": th, "to": f, "count": n}
            for (th, f), n in think_feel.most_common(3) if n >= 2]
    # Feelings recur more reliably than paraphrased behaviours: also report a feeling present on several
    # days with the behaviours that came with it.
    by_feeling: dict[str, set] = {}
    for t in turns:
        e = t.get("elements") or {}
        for f in e.get("feelings", []):
            by_feeling.setdefault(f, set()).add(t["ts"][:10])
    for f, days in sorted(by_feeling.items(), key=lambda kv: -len(kv[1])):
        if len(days) >= 2 and not any(link["from"] == f for link in out):
            behaviours = [b for t in turns for b in (t.get("elements") or {}).get("behaviours", [])
                          if f in (t.get("elements") or {}).get("feelings", [])]
            out.append({"kind": "recurring_feeling", "from": f, "to": behaviours[-1] if behaviours else None,
                        "count": len(days)})
            break
    return out


def find_echo(current: list[dict], earlier: list[dict], now: datetime,
              min_similarity: float = MEMORY_MIN_SIMILARITY) -> dict | None:
    """Today's story first: the newest episode of the period with any earlier match is the one linked."""
    for cur in sorted(current, key=lambda e: e["created_at"], reverse=True):
        echo = _echo_for(cur, earlier, now, min_similarity)
        if echo:
            return echo
    return None


def _echo_for(cur: dict, earlier: list[dict], now: datetime, min_similarity: float) -> dict | None:
    best_band, best_any = None, None
    if cur.get("embedding") is not None:
        for old in earlier:
            if old.get("embedding") is None:
                continue
            age = (now - parse_iso(old["created_at"])).days
            if age < PATTERN_MIN_GAP_DAYS:
                continue
            sim = cosine(cur["embedding"], old["embedding"])
            if sim < min_similarity:
                continue
            cand = (sim, age, cur, old)
            if abs(age - PATTERN_LOOKBACK_DAYS) <= PATTERN_YEAR_BAND_DAYS and (best_band is None or sim > best_band[0]):
                best_band = cand
            if best_any is None or sim > best_any[0]:
                best_any = cand
    # A year-old match wins only when it is nearly as close as the best match overall.
    best = best_band if best_band and best_band[0] >= best_any[0] - PATTERN_YEAR_MARGIN else best_any
    if best is None:
        return None
    sim, age, cur, old = best
    return {"then": parse_iso(old["created_at"]).strftime("%B %Y"), "days_ago": age,
            "summary_then": old["summary"], "summary_now": cur["summary"], "similarity": round(sim, 3),
            "year_ago": best is best_band}


def mine(store: Store, user_id: str, now: datetime | None = None,
         exclude_earlier: set[str] | frozenset = frozenset()) -> PatternReport:
    """`exclude_earlier`: summaries of earlier episodes never to link to (a link the person said did not fit)."""
    now = now or utcnow()
    start = now - timedelta(days=WEEKLY_PERIOD_DAYS)
    history_start = start - timedelta(weeks=_HISTORY_WEEKS)

    all_turns = [t for t in store.user_turns(user_id, until=now) if t["risk_level"] != "crisis"]
    turns = [t for t in all_turns if parse_iso(t["ts"]) >= start]
    before = [t for t in all_turns if history_start <= parse_iso(t["ts"]) < start]
    episodes = [e for e in store.user_episodes(user_id, until=now) if not e["had_crisis"]]
    current = [e for e in episodes if parse_iso(e["created_at"]) >= start]
    earlier = [e for e in episodes if parse_iso(e["created_at"]) < start and e["summary"] not in exclude_earlier]

    report = PatternReport(period_start=start.date().isoformat(), period_end=now.date().isoformat())
    report.episodes = [{"date": parse_iso(e["created_at"]).strftime("%A %d %B"), "summary": e["summary"],
                        "themes": e["themes"]} for e in current]

    counts = Counter(p for t in turns for p in t["pain_points"])
    for e in current:
        counts.update(e["themes"])
    weeks_seen: dict[str, set] = {}
    for t in all_turns:
        if parse_iso(t["ts"]) < start:
            for p in t["pain_points"]:
                weeks_seen.setdefault(p, set()).add(parse_iso(t["ts"]).isocalendar()[:2])
    report.themes = [{"theme": th, "count": n, "earlier_weeks": len(weeks_seen.get(th, ()))}
                     for th, n in counts.most_common(4)]

    emo = Counter(t["emotion"] for t in turns if t["emotion"] and t["emotion"] != "neutral")
    emo_before = Counter(t["emotion"] for t in before if t["emotion"] and t["emotion"] != "neutral")
    report.emotions = {"this_period": _share(emo), "before": _share(emo_before)}

    report.links = _links(turns)
    report.echo = find_echo(current, earlier, now)
    return report
