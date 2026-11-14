"""Next-step planner — there is always a thoughtful next step waiting.

    1. a journey in progress            → its current step
    2. otherwise a journey that fits    → the journey whose description is closest in meaning to the
                                          user's recent session summaries (episodes of the last 30 days,
                                          crisis sessions excluded), skipping finished journeys
    3. otherwise                        → an open check-in ("bring your own agenda")

Each step is a dict the API returns as is:
    {kind: journey_step | journey_suggestion | check_in, title, text, journey_id?, journey_title?,
     step_id?, step_index?, step_count?}
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

import numpy as np

from ..memory.store import Store, utcnow
from . import catalog
from .catalog import Journey

log = logging.getLogger(__name__)

_RECENT_DAYS = 30
_PROFILES: dict[str, np.ndarray] = {}      # journey id → embedding of its description (computed once)


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


def profile_text(journey: Journey) -> str:
    """What a journey is about, for matching: title, summary and each step's goal.
    (eval/runners/journey_recommendation.py compared three profiles; this one fitted best.)"""
    return f"{journey.title}. {journey.summary} " + " ".join(step.goal for step in journey.steps)


def _profile(journey: Journey, embed: Callable) -> np.ndarray:
    if embed is not _default_embed:
        return embed(profile_text(journey))
    if journey.id not in _PROFILES:
        _PROFILES[journey.id] = embed(profile_text(journey))
    return _PROFILES[journey.id]


def _default_embed(text: str) -> np.ndarray:
    from ..memory.embeddings import embed
    return embed(text)


def recommend(store: Store, user_id: str, now: datetime | None = None,
              embed: Callable | None = None) -> Journey | None:
    """The unfinished journey closest in meaning to the person's recent conversations, or None.

    Uses the embeddings already stored with each session summary.  Needs memory on (no summaries otherwise),
    so without it the planner offers the open check-in, as before.
    """
    now = now or utcnow()
    episodes = [e for e in store.user_episodes(user_id, since=now - timedelta(days=_RECENT_DAYS))
                if not e["had_crisis"] and e["embedding"] is not None]
    if not episodes:
        return None
    finished = {jid for jid, row in store.journey_progress(user_id).items() if row["status"] == "completed"}
    candidates = [j for j in catalog.load_catalog().values() if j.id not in finished]
    if not candidates:
        return None
    embed = embed or _default_embed
    try:
        recent = np.stack([np.asarray(e["embedding"], dtype=np.float32) for e in episodes])
        recent /= np.linalg.norm(recent, axis=1, keepdims=True) + 1e-9
        profiles = np.stack([_profile(j, embed) for j in candidates])
        profiles /= np.linalg.norm(profiles, axis=1, keepdims=True) + 1e-9
        fit = (recent @ profiles.T).mean(axis=0)
    except Exception as exc:     # no embedder, or summaries embedded by another model: suggest nothing
        log.warning("Journey recommendation unavailable: %s", type(exc).__name__)
        return None
    return candidates[int(np.argmax(fit))]


def next_step(store: Store, user_id: str, now: datetime | None = None, embed: Callable | None = None) -> dict:
    step = active_step(store, user_id)
    if step:
        return step
    journey = recommend(store, user_id, now, embed=embed)
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
