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
def weekly_status(user: dict = Depends(current_user), store: Store = Depends(get_store)):
    """Read-only: this week's insight if written, else whether one is due.  Never calls the LLM."""
    return weekly.weekly_status(store, user)


@router.post("/insights/weekly")
def write_weekly_insight(user: dict = Depends(current_user), store: Store = Depends(get_store)):
    """Writes this week's insight when it is due (LLM + guards, a few seconds); otherwise returns the status."""
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


# ── saves the person confirms, and their own entries (A3) ────────────────────
@router.post("/actions/{action_id}/confirm")
def confirm_action(action_id: str, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    """Run a save Lumina proposed in the chat.  Only the owner can confirm it, once, within PENDING_ACTION_MINUTES."""
    from ..agent import tools
    from ..memory.store import utcnow
    pending = store.take_pending(action_id, user["id"])
    if pending is None or pending["tool"] not in tools.WRITE_TOOLS:
        raise HTTPException(status_code=404, detail="That is no longer waiting to be saved. Please ask again.")
    ctx = tools.ToolContext(store, user["id"], bool(user["memory_enabled"]), utcnow())
    item = tools.WRITE_TOOLS[pending["tool"]].run(ctx, pending["args"])
    return {"done": True, "tool": pending["tool"], "item": item}


@router.post("/actions/{action_id}/cancel", status_code=204)
def cancel_action(action_id: str, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    store.take_pending(action_id, user["id"])          # nothing is saved; unknown or expired is fine too


# Writing directly in the app (the journal page, the sleep line, the mood stamps) needs no confirm step: the
# person typed it and pressed Save themselves.  The same validation and the same writers as the chat's saves.
def _write(name: str, body: dict, user: dict, store: Store) -> dict:
    from ..agent import tools
    from ..memory.store import utcnow
    prepared = tools.propose(name, body, tools.ToolContext(store, user["id"], bool(user["memory_enabled"]), utcnow()))
    if prepared is None:
        raise HTTPException(status_code=422, detail="That could not be saved as written.")
    return tools.WRITE_TOOLS[name].run(tools.ToolContext(store, user["id"], bool(user["memory_enabled"]), utcnow()),
                                       prepared[0])


class JournalEntryIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class SleepIn(BaseModel):
    hours: float = Field(ge=0, le=16)
    quality: Literal["poor", "ok", "good"] | None = None
    night: Literal["last_night", "night_before"] = "last_night"


class MoodIn(BaseModel):
    weather: Literal["clear", "part", "fog", "rain", "storm"]
    note: str | None = Field(default=None, max_length=300)


@router.post("/journal/entries", status_code=201)
def add_journal_entry(body: JournalEntryIn, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    return _write("journal_save", body.model_dump(), user, store)


class ScratchIn(BaseModel):
    text: str = Field(max_length=2000)


@router.patch("/journal/entries/{item_id}")
def scratch_journal_entry(item_id: str, body: ScratchIn, user: dict = Depends(current_user),
                          store: Store = Depends(get_store)):
    """Words scratched out of an entry, by the person, on the page.  Scratching can only take words away: text
    that adds or reorders anything is refused.  An entry with nothing left is deleted ({"deleted": true})."""
    from ..memory.store import only_scratched
    entry = next((e for e in store.journal_entries(user["id"]) if e["id"] == item_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail="Not found.")
    if not only_scratched(entry["text"], body.text):
        raise HTTPException(status_code=422, detail="Only scratching words out is possible here.")
    kept = store.scratch_journal_entry(item_id, user["id"], body.text)
    return {"deleted": True, "id": item_id} if kept is None else kept


@router.post("/logs/sleep", status_code=201)
def add_sleep_log(body: SleepIn, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    return _write("sleep_log", body.model_dump(), user, store)


@router.post("/logs/mood", status_code=201)
def add_mood_log(body: MoodIn, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    return _write("mood_log", body.model_dump(exclude_none=True), user, store)



@router.get("/journal/entries")
def journal_entries(user: dict = Depends(current_user), store: Store = Depends(get_store)):
    return {"entries": store.journal_entries(user["id"])}


@router.get("/logs/sleep")
def sleep_logs(user: dict = Depends(current_user), store: Store = Depends(get_store)):
    return {"nights": store.sleep_logs(user["id"])}


@router.get("/logs/mood")
def mood_logs(user: dict = Depends(current_user), store: Store = Depends(get_store)):
    return {"days": store.mood_logs(user["id"])}


@router.delete("/journal/entries/{item_id}", status_code=204)
def delete_journal_entry(item_id: str, user: dict = Depends(current_user), store: Store = Depends(get_store)):
    if not store.delete_own("journal", item_id, user["id"]):
        raise HTTPException(status_code=404, detail="Not found.")


@router.delete("/logs/{kind}/{item_id}", status_code=204)
def delete_log(kind: Literal["sleep", "mood"], item_id: str, user: dict = Depends(current_user),
               store: Store = Depends(get_store)):
    if not store.delete_own(kind, item_id, user["id"]):
        raise HTTPException(status_code=404, detail="Not found.")
