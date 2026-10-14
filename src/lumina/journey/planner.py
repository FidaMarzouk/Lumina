"""Next-step planner — there is always a thoughtful next step waiting.

    1. a journey in progress            → its current step
    2. otherwise a journey that fits    → recommended from the dominant pain-point macro of the
                                          user's recent turns (crisis turns excluded), skipping
                                          finished journeys
    3. otherwise                        → an open check-in ("bring your own agenda")

Each step is a dict the API returns as is:
    {kind: journey_step | journey_suggestion | check_in, title, text, journey_id?, journey_title?,
     step_id?, step_index?, step_count?}
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from ..memory.store import Store, utcnow
from . import catalog
from .catalog import Journey

_RECENT_DAYS = 30
_NOT_A_THEME = {None, "", "none", "trauma & crisis"}


def step_payload(journey: Journey, index: int, kind: str = "journey_step") -> dict:
    step = journey.steps[index]
    return {"kind": kind, "journey_id": journey.id, "journey_title": journey.title, "step_id": step.id,
            "step_index": index, "step_count": len(journey.steps), "title": step.title, "text": step.opener}


def check_in() -> dict:
    return {"kind": "check_in", "title": "Your own agenda",
            "text": "Come with whatever is on your mind today, or ask me to suggest something to work on together."}


def active_step(store: Store, user_id: str) -> dict | None:
    for journey_id, row in store.journey_progress(user_id).items():
        journey = catalog.get(journey_id)
        if row["status"] == "active" and journey and row["step_index"] < len(journey.steps):
            return step_payload(journey, row["step_index"])
    return None


def recommend(store: Store, user_id: str, now: datetime | None = None) -> Journey | None:
    now = now or utcnow()
    turns = store.user_turns(user_id, since=now - timedelta(days=_RECENT_DAYS))
    macros = Counter(t["macro"] for t in turns if t["risk_level"] == "none" and t["macro"] not in _NOT_A_THEME)
    finished = {jid for jid, row in store.journey_progress(user_id).items() if row["status"] == "completed"}
    candidates = [j for j in catalog.load_catalog().values() if j.id not in finished]
    for macro, _ in macros.most_common():
        for journey in candidates:
            if macro in journey.themes:
                return journey
    return None


def next_step(store: Store, user_id: str, now: datetime | None = None) -> dict:
    step = active_step(store, user_id)
    if step:
        return step
    journey = recommend(store, user_id, now)
    if journey:
        payload = step_payload(journey, 0, kind="journey_suggestion")
        payload["text"] = f"{journey.summary} {journey.steps[0].opener}"
        return payload
    return check_in()


def waiting(store: Store, user_id: str, now: datetime | None = None) -> dict:
    """The step waiting for this visit: the one stored at the last session end (its wording may be
    personalised) while it is still current, otherwise a freshly planned one."""
    fresh = next_step(store, user_id, now)
    stored = store.get_next_step(user_id)
    if stored and all(stored.get(k) == fresh.get(k) for k in ("kind", "journey_id", "step_id")):
        return stored
    return fresh


def start(store: Store, user_id: str, journey_id: str, now: datetime | None = None) -> dict | None:
    """Make `journey_id` the active journey (pausing any other); returns its current step."""
    journey = catalog.get(journey_id)
    if journey is None:
        return None
    progress = store.journey_progress(user_id)
    for other_id, row in progress.items():
        if other_id != journey_id and row["status"] == "active":
            store.set_progress(user_id, other_id, row["step_index"], "paused", now)
    row = progress.get(journey_id)
    index = row["step_index"] if row and row["status"] != "completed" else 0
    store.set_progress(user_id, journey_id, index, "active", now)
    return step_payload(journey, index)


def complete_step(store: Store, user_id: str, journey_id: str, step_id: str,
                  now: datetime | None = None) -> dict | None:
    """Mark `step_id` done and move on; returns the next step, a check-in when the journey is finished,
    or None if the journey/step is unknown.  Completing a step that is not the current one is a no-op."""
    journey = catalog.get(journey_id)
    index = journey.step_index(step_id) if journey else None
    if index is None:
        return None
    row = store.journey_progress(user_id).get(journey_id)
    current = row["step_index"] if row else 0
    if index != current or (row and row["status"] == "completed"):
        return next_step(store, user_id, now)
    if index + 1 >= len(journey.steps):
        store.set_progress(user_id, journey_id, len(journey.steps), "completed", now)
        return {**check_in(), "completed_journey": journey.title}
    store.set_progress(user_id, journey_id, index + 1, "active", now)
    return step_payload(journey, index + 1)


def overview(store: Store, user_id: str) -> list[dict]:
    progress = store.journey_progress(user_id)
    out = []
    for journey in catalog.load_catalog().values():
        row = progress.get(journey.id)
        out.append({**journey.public(), "status": row["status"] if row else "not_started",
                    "step_index": row["step_index"] if row else 0})
    return out
