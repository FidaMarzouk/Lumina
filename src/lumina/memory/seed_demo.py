"""Create a demo account with ~14 months of synthetic history, so patterns across time can be shown.

    python -m lumina.memory.seed_demo                       # demo@lumina.local / lumina-demo
    python -m lumina.memory.seed_demo --email me@x.io --password "…" --name Sam

The history is invented (lumina/memory/synthetic.py).  It includes a planted pattern: a work
deadline → "I'm not good enough" → anxiety → working late, about a year ago and again this week,
so POST /insights/weekly can connect today's story to last year.  It also fills what a person keeps by
hand: 8 saved journal entries, two weeks of sleep and mood logs, a jar of five things, one finished journey and
one in progress.  An existing account with the same email is deleted first.
"""

from __future__ import annotations

import argparse
import random
from datetime import timedelta

from ..auth.passwords import hash_password
from ..config import USER_DB_PATH
from .store import Store, utcnow
from .synthetic import SCENARIOS

# (days ago, scenario, paraphrase index) — this week, a year ago, and a spread of other moments
_PLANTED = [(1, "work_deadline", 0), (3, "sleep", 1), (5, "friend_conflict", 2), (366, "work_deadline", 1)]


def _timeline(rng: random.Random) -> list[tuple[int, str, int]]:
    others = [k for k in SCENARIOS if k != "work_deadline"]
    days = list(range(12, 430, 9))
    timeline = [(d + rng.randint(0, 4), rng.choice(others), rng.randint(0, 2)) for d in days]
    timeline = [t for t in timeline if not 350 <= t[0] <= 385]       # keep the year-ago moment clean
    return sorted(_PLANTED + timeline, key=lambda t: -t[0])


def seed(store: Store, email: str, password: str, name: str, embed=None, seed_value: int = 7) -> dict:
    existing = store.get_user_by_email(email)
    if existing:
        store.delete_user(existing["id"])
    now = utcnow()
    first = now - timedelta(days=440)
    user = store.create_user(email, hash_password(password), name, consent=True, now=first)
    if embed is None:
        try:
            from .embeddings import embed
        except ImportError:
            embed = None

    rng = random.Random(seed_value)
    for days_ago, key, variant in _timeline(rng):
        sc = SCENARIOS[key]
        when = now - timedelta(days=days_ago, hours=rng.randint(0, 10))
        session = store.create_session(user["id"], "open", now=when)
        for i in range(rng.randint(3, 5)):
            tid = store.add_turn(session["id"], user["id"], intent="venting" if sc["pain"] else "sharing_experience",
                                 emotion=sc["emotion"], sentiment="positive" if key == "good_week" else "negative",
                                 pain_points=[], macro=None, risk_level="none",
                                 now=when + timedelta(minutes=3 * i))
            store.set_turn_elements(tid, sc["elements"])
        store.end_session(session["id"], now=when + timedelta(minutes=20))
        summary = sc["summaries"][variant]
        store.save_episode(session["id"], user["id"], summary=summary, themes=[p.split(" and ")[0] for p in sc["pain"]],
                           elements={k: v if isinstance(v, list) else [v] for k, v in sc["elements"].items()},
                           emotions=[sc["emotion"]], had_crisis=False,
                           embedding=embed(summary) if embed else None, now=when + timedelta(minutes=20))
        store.add_insight(user["id"], "session", summary, {"themes": sc["pain"], "synthetic": True},
                          session_id=session["id"], now=when + timedelta(minutes=20))
    _seed_personal(store, user["id"], now, rng)
    return user


# What a person keeps by hand (A3 saves, the jar, journeys), so every page of the app has something on it.
# Invented, in the same voice as the planted pattern: a hard work week, short nights, small things that helped.
_ENTRIES = [
    (19, "Went to the sea after work. Didn't fix anything but I could breathe again."),
    (16, "Called my sister. We laughed about the kitchen disaster from last summer."),
    (13, "Bad night. Kept replaying the meeting. Wrote the thought down and it looked smaller on paper."),
    (10, "Said no to the extra project. My hands were shaking but I said it."),
    (7, "Proud of today: I left my laptop closed after 8."),
    (4, "The deadline is back and so is the old voice saying I'm not good enough. Noticing it this time."),
    (2, "Walked the long way home. The jacaranda on the corner is flowering."),
    (1, "Tired, but I asked for help at work instead of staying late."),
]
_JAR = ["a walk by the sea", "calling my sister", "the 4-7-8 breathing", "laptop closed after 8",
        "writing the thought down"]
_WEATHER = ["part", "rain", "fog", "part", "clear", "rain", "storm", "fog", "part", "clear", "part", "rain",
            "part", "clear"]
_NOTES = {1: "asked for help", 4: "the deadline again", 7: "laptop closed early", 9: "rough meeting"}


def _seed_personal(store: Store, uid: str, now, rng: random.Random) -> None:
    for days_ago, text in _ENTRIES:
        store.add_journal_entry(uid, text, now=now - timedelta(days=days_ago, hours=rng.randint(1, 6)))
    for i, text in enumerate(_JAR):
        store.add_jar_item(uid, text, "kept", now=now - timedelta(days=30 - 5 * i))
    for days_ago in range(14, 0, -1):
        night = (now - timedelta(days=days_ago)).date().isoformat()
        hours = round(rng.uniform(4.5, 7.5) * 2) / 2 if days_ago > 5 else round(rng.uniform(4.0, 6.0) * 2) / 2
        store.add_sleep_log(uid, night, hours, "poor" if hours < 5.5 else "ok" if hours < 7 else "good",
                            now=now - timedelta(days=days_ago - 1))
    for days_ago, weather in zip(range(13, -1, -1), _WEATHER):
        day = (now - timedelta(days=days_ago)).date().isoformat()
        store.add_mood_log(uid, day, weather, _NOTES.get(days_ago), now=now - timedelta(days=days_ago))
    store.set_progress(uid, "grounding_anxiety", 4, "completed", now=now - timedelta(days=60))
    store.set_progress(uid, "sleep_reset", 1, "active", now=now - timedelta(days=6))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", default="demo@lumina.local")
    ap.add_argument("--password", default="lumina-demo")
    ap.add_argument("--name", default="Alex")
    args = ap.parse_args()
    store = Store(USER_DB_PATH)
    user = seed(store, args.email.lower(), args.password, args.name)
    n = len(store.user_episodes(user["id"]))
    print(f"Demo account ready: {args.email} / {args.password}  ({n} synthetic sessions in {USER_DB_PATH})")


if __name__ == "__main__":
    main()
