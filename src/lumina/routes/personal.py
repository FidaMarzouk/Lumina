"""Signed-in features: sessions (open or guided), journeys, insights and the "things that helped" jar."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import current_user, get_store
from ..insights import weekly
from ..journey import catalog, planner
from ..memory import episodes
from ..memory import service as memory
from ..memory.schemas import JAR_CHARS
from ..memory.store import Store


def _one_line(v):
    """Typed text kept as one tidy line (None or blank means none)."""
    if v is None:
        return None
    v = " ".join(str(v).split())
    return v or None

router = APIRouter()


# ── sessions ─────────────────────────────────────────────────────────────────
class SessionRequest(BaseModel):
    mode: Literal["open", "guided"] = "open"
    journey_id: str | None = Field(default=None, max_length=64)


def _opening(name: str, first_visit: bool, mode: str, step: dict) -> str:
    hello = f"Hi {name}, I'm Lumina." if name else "Hi, I'm Lumina."
    back = f"Welcome back, {name}." if name else "Welcome back."
    if mode == "guided":
        return f"{back if not first_visit else hello} Today's step in “{step['journey_title']}”: " \
               f"{step['title']}. {step['text']}"
    if first_visit:
        return f"{hello} I'm here to listen, with no judgement and no rush. How are you feeling today?"
    if step["kind"] == "journey_step":
        return f"{back} You can bring your own agenda today, or pick up where we left off with " \
               f"“{step['title']}”. {step['text']}"
    if step["kind"] == "journey_suggestion":
        return f"{back} Bring whatever is on your mind, or, if you'd like some structure, we could try " \
               f"“{step['journey_title']}”. {step['text']}"
    return f"{back} How are you feeling today?"


@router.post("/sessions", status_code=201)
def start_session(body: SessionRequest, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    uid = user["id"]
    first_visit = not store.user_sessions(uid)
    if body.mode == "guided":
        if body.journey_id:
            step = planner.start(store, uid, body.journey_id)
            if step is None:
                raise HTTPException(status_code=404, detail="Unknown journey.")
        else:
            step = planner.active_step(store, uid)
            if step is None:
                journey = planner.recommend(store, uid) or next(iter(catalog.load_catalog().values()))
                step = planner.start(store, uid, journey.id)
        waiting = planner.waiting(store, uid)
        if waiting.get("journey_id") == step["journey_id"] and waiting.get("step_id") == step["step_id"]:
            step = {**step, "text": waiting["text"]}
        session = store.create_session(uid, "guided", step["journey_id"], step["step_id"])
    else:
        step = planner.waiting(store, uid)
        session = store.create_session(uid, "open")
    return {"session_id": session["id"], "mode": session["mode"], "next_step": step,
            "opening": _opening(user["display_name"], first_visit, session["mode"], step)}


@router.post("/sessions/{session_id}/end")
def end_session(session_id: str, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    session = store.get_session(session_id, user["id"])
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    memory.wait_for_session(session_id)
    return episodes.close_session(store, user, session)


# ── journeys ─────────────────────────────────────────────────────────────────
class StepDone(BaseModel):
    journey_id: str = Field(max_length=64)
    step_id: str = Field(max_length=64)


@router.get("/journeys")
def journeys(user: dict = Depends(current_user), store: Store = Depends(get_store)):
    return {"journeys": planner.overview(store, user["id"])}


@router.post("/journeys/{journey_id}/start")
def start_journey(journey_id: str, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    step = planner.start(store, user["id"], journey_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Unknown journey.")
    return step


@router.get("/journey/next")
def next_step(user: dict = Depends(current_user), store: Store = Depends(get_store)):
    return planner.waiting(store, user["id"])


@router.post("/journey/steps/complete")
def complete_step(body: StepDone, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    step = planner.complete_step(store, user["id"], body.journey_id, body.step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Unknown journey step.")
    store.set_next_step(user["id"], step)
    return step


# ── insights ─────────────────────────────────────────────────────────────────
class Feedback(BaseModel):
    value: Literal["fits", "not_quite"]


@router.get("/insights")
def insights(kind: Literal["session", "weekly"] | None = None, limit: int = Query(default=20, ge=1, le=100),
             user: dict = Depends(current_user), store: Store = Depends(get_store)):
    return {"insights": [episodes.public_insight(r) for r in store.list_insights(user["id"], kind, limit)]}


@router.get("/insights/weekly")
def weekly_insight(user: dict = Depends(current_user), store: Store = Depends(get_store)):
    return weekly.weekly_insight(store, user)


@router.post("/insights/{insight_id}/feedback", status_code=204)
def feedback(insight_id: str, body: Feedback, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    if not store.set_feedback(insight_id, user["id"], body.value):
        raise HTTPException(status_code=404, detail="Insight not found.")


# ── things that helped ───────────────────────────────────────────────────────
class JarItem(BaseModel):
    text: str = Field(min_length=1, max_length=JAR_CHARS)

    _tidy = field_validator("text", mode="before")(_one_line)


def _public_jar(item: dict) -> dict:
    return {k: item[k] for k in ("id", "text", "status", "created_at")}


@router.get("/jar")
def jar(user: dict = Depends(current_user), store: Store = Depends(get_store)):
    """Kept items, and what Lumina noticed helped (suggested) until the person keeps or dismisses it."""
    items = [_public_jar(i) for i in store.jar_items(user["id"])]
    return {"kept": [i for i in items if i["status"] == "kept"],
            "suggested": [i for i in items if i["status"] == "suggested"]}


@router.post("/jar", status_code=201)
def add_to_jar(body: JarItem, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    return _public_jar(store.add_jar_item(user["id"], body.text, "kept"))


@router.post("/jar/{item_id}/keep", status_code=204)
def keep_in_jar(item_id: str, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    if not store.keep_jar_item(item_id, user["id"]):
        raise HTTPException(status_code=404, detail="Not found.")


@router.delete("/jar/{item_id}", status_code=204)
def remove_from_jar(item_id: str, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    if not store.delete_jar_item(item_id, user["id"]):
        raise HTTPException(status_code=404, detail="Not found.")
