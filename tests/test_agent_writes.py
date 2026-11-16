"""Write tools (A3): nothing saved without the person's yes, their words encrypted at rest, every entry deletable."""
from datetime import datetime, timedelta, timezone

import pytest

from lumina.agent import loop, tools
from lumina.memory import crypto

NOW = datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)
SECRET = "I cried in the car after work and nobody knows"


@pytest.fixture
def ctx(user_store):
    uid = user_store.create_user("w@x.io", "h", "Sam", consent=True)["id"]
    return tools.ToolContext(user_store, uid, True, NOW)


# ─────────────────────────── storage ───────────────────────────
def test_their_words_are_encrypted_at_rest(ctx, user_store):
    user_store.add_journal_entry(ctx.user_id, SECRET, now=NOW)
    user_store.add_mood_log(ctx.user_id, "2026-11-15", "rain", "the meeting went badly", now=NOW)
    raw = user_store.path.read_bytes()
    assert SECRET.encode() not in raw and b"the meeting went badly" not in raw
    assert user_store.journal_entries(ctx.user_id)[0]["text"] == SECRET
    assert user_store.mood_logs(ctx.user_id)[0]["note"] == "the meeting went badly"


def test_another_key_cannot_read_them(ctx, user_store, monkeypatch):
    from cryptography.fernet import Fernet
    user_store.add_journal_entry(ctx.user_id, SECRET, now=NOW)
    monkeypatch.setenv("LUMINA_DATA_KEY", Fernet.generate_key().decode())
    crypto.reset_for_tests()
    with pytest.raises(crypto.DecryptError):
        user_store.journal_entries(ctx.user_id)


def test_each_entry_can_be_deleted_only_by_its_owner(ctx, user_store):
    other = user_store.create_user("o@x.io", "h", "Bo", consent=True)["id"]
    entry = user_store.add_journal_entry(ctx.user_id, "mine", now=NOW)
    night = user_store.add_sleep_log(ctx.user_id, "2026-11-14", 6, "ok", now=NOW)
    assert not user_store.delete_own("journal", entry["id"], other)                  # not theirs
    assert user_store.delete_own("journal", entry["id"], ctx.user_id)
    assert user_store.delete_own("sleep", night["id"], ctx.user_id)
    assert user_store.journal_entries(ctx.user_id) == [] and user_store.sleep_logs(ctx.user_id) == []


def test_export_includes_their_words_and_account_deletion_removes_everything(ctx, user_store):
    user_store.add_journal_entry(ctx.user_id, SECRET, now=NOW)
    user_store.add_sleep_log(ctx.user_id, "2026-11-14", 5, "poor", now=NOW)
    user_store.add_mood_log(ctx.user_id, "2026-11-15", "fog", None, now=NOW)
    out = user_store.export_user(ctx.user_id)
    assert out["journal_entries"][0]["text"] == SECRET and out["sleep_logs"][0]["hours"] == 5
    assert out["mood_logs"][0]["weather"] == "fog"
    user_store.delete_user(ctx.user_id)
    import sqlite3
    with sqlite3.connect(user_store.path) as c:
        for table in ("journal_entries", "sleep_logs", "mood_logs", "pending_actions"):
            assert c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table


# ─────────────────────────── proposals ───────────────────────────
def test_a_save_is_proposed_never_run(ctx, user_store):
    run = loop.run("save this to my journal: I called my mum", ctx,
                   choose=lambda m, s: [("journal_save", {"text": "I called my mum"}), ("sleep_log", {"hours": 6})])
    assert run.proposal["tool"] == "journal_save" and run.proposal["summary"] == 'Save to your journal: "I called my mum"'
    assert user_store.journal_entries(ctx.user_id) == [] and user_store.sleep_logs(ctx.user_id) == []   # one, unsaved


@pytest.mark.parametrize("name,args", [("sleep_log", {}), ("sleep_log", {"hours": 30}), ("mood_log", {"weather": "sunny"}),
                                       ("journal_save", {"text": ""}), ("jar_add", {"text": "x" * 200}),
                                       ("journal_save", {"text": "x", "user_id": "someone-else"})])
def test_invented_or_invalid_details_are_refused(ctx, name, args):
    assert loop.run("x", ctx, choose=lambda m, s: [(name, args)]).proposal is None


@pytest.mark.parametrize("message,name,args,ok", [
    ("log my sleep, about 5 hours", "sleep_log", {"hours": 5}, True),
    ("slept five and a half hours", "sleep_log", {"hours": 5.5}, True),
    ("log that I woke up three times", "sleep_log", {"hours": 7}, False),          # hours invented
    ("record my mood, 6/10", "sleep_log", {"hours": 6}, True),                    # a number they wrote (mood eval)
    ("put this in my journal: work was hard", "journal_save", {"text": "work was hard"}, True),
    ("write down that I'm proud", "journal_save", {"text": "Today I achieved something great"}, False),
    ("add 'breathing exercise' to my jar", "jar_add", {"text": "breathing exercise"}, True),
])
def test_proposals_only_carry_details_from_the_message(ctx, message, name, args, ok):
    assert (loop.run(message, ctx, choose=lambda m, s: [(name, args)]).proposal is not None) is ok


def test_summaries_say_exactly_what_will_be_saved(ctx):
    stored, summary = tools.propose("sleep_log", {"hours": 5, "quality": "poor"}, ctx)
    assert stored["night"] == "2026-11-14" and summary == "Log 5 hours of sleep for the night of Saturday 14 November, poor"
    assert tools.propose("mood_log", {"weather": "part", "note": "a bit better"}, ctx)[1] == \
        'Log today\'s mood as partly cloudy: "a bit better"'


def test_reading_back_what_they_saved(ctx, user_store):
    user_store.add_journal_entry(ctx.user_id, "proud of today", now=NOW - timedelta(days=1))
    user_store.add_sleep_log(ctx.user_id, "2026-11-13", 5, "poor", now=NOW)
    user_store.add_sleep_log(ctx.user_id, "2026-11-14", 7, "good", now=NOW)
    user_store.add_mood_log(ctx.user_id, "2026-11-15", "clear", None, now=NOW)
    assert tools.call("journal_search", {"days_back": 7}, ctx)["saved_entries"][0]["text"] == "proud of today"
    assert tools.call("sleep_history", {"days": 7}, ctx)["average_hours"] == 6.0
    assert tools.call("feelings_over_time", {"days": 7}, ctx)["logged_moods"]["days"][0]["mood"] == "clear"
    # Their own saves come back even with memory (Lumina's notes) switched off.
    off = tools.ToolContext(user_store, ctx.user_id, False, NOW)
    assert "unavailable" in (found := tools.call("journal_search", {}, off)) and found["saved_entries"]
    assert tools.call("feelings_over_time", {"days": 7}, off)["logged_moods"]["days"]
    assert "error" in tools.call("journal_save", {"text": "x"}, ctx)        # a write tool never runs as a read


# ─────────────────────────── confirming over the API ───────────────────────────
@pytest.fixture
def api(user_store):
    from fastapi.testclient import TestClient

    from lumina import api as api_module
    c = TestClient(api_module.app)
    def register(email):
        r = c.post("/auth/register", json={"email": email, "password": "correct horse", "display_name": "Sam",
                                           "consent": True})
        return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]["id"]
    return c, register


def test_confirm_saves_once_and_only_for_the_owner(api, user_store):
    c, register = api
    (alice, alice_id), (bob, _) = register("a@x.io"), register("b@x.io")
    pid = user_store.add_pending(alice_id, "journal_save", {"text": SECRET}, datetime.now(timezone.utc) + timedelta(minutes=30))
    assert c.post(f"/actions/{pid}/confirm", headers=bob).status_code == 404          # not Bob's
    r = c.post(f"/actions/{pid}/confirm", headers=alice)
    assert r.status_code == 200 and r.json()["item"]["text"] == SECRET
    assert c.post(f"/actions/{pid}/confirm", headers=alice).status_code == 404         # only once
    assert [e["text"] for e in c.get("/journal/entries", headers=alice).json()["entries"]] == [SECRET]
    assert c.get("/journal/entries", headers=bob).json()["entries"] == []


def test_expired_or_cancelled_proposals_save_nothing(api, user_store):
    c, register = api
    headers, uid = register("a@x.io")
    old = user_store.add_pending(uid, "sleep_log", {"night": "2026-11-14", "hours": 6, "quality": None},
                                 datetime.now(timezone.utc) - timedelta(minutes=1))
    assert c.post(f"/actions/{old}/confirm", headers=headers).status_code == 404
    pid = user_store.add_pending(uid, "mood_log", {"day": "2026-11-15", "weather": "rain", "note": None},
                                 datetime.now(timezone.utc) + timedelta(minutes=30))
    assert c.post(f"/actions/{pid}/cancel", headers=headers).status_code == 204
    assert c.post(f"/actions/{pid}/confirm", headers=headers).status_code == 404
    assert user_store.sleep_logs(uid) == [] and user_store.mood_logs(uid) == []


def test_entries_are_deleted_one_by_one_over_the_api(api, user_store):
    c, register = api
    headers, uid = register("a@x.io")
    night = user_store.add_sleep_log(uid, "2026-11-14", 6, None)
    assert c.delete(f"/logs/sleep/{night['id']}", headers=headers).status_code == 204
    assert c.delete(f"/logs/sleep/{night['id']}", headers=headers).status_code == 404
    assert c.delete("/logs/passwords/x", headers=headers).status_code == 422             # only sleep and mood


# ─────────────────────────── in the turn ───────────────────────────
from lumina import orchestrator as orch  # noqa: E402
from lumina.memory.service import SessionContext  # noqa: E402
from lumina.safety.assessment import SafetyAssessment  # noqa: E402


@pytest.fixture
def turn(monkeypatch, user_store):
    from lumina.dialogue import empathy_engine as ee
    uid = user_store.create_user("t@x.io", "h", "Sam", consent=True)["id"]
    monkeypatch.setattr(orch, "AGENT_TOOLS", True)
    monkeypatch.setattr(orch, "_response_guard", lambda: None)
    monkeypatch.setattr(orch.memory, "load_context", lambda *a, **k: ({}, None))
    monkeypatch.setattr(orch, "_remember", lambda *a, **k: None)

    def run(safety, picks, session=True, reply="Ready."):
        nlp = {"cleaned_text": "msg", "tokens": [], "entities": {}, "intent": "action_request", "intent_confidence": 0.9,
               "intent_ambiguous": None}
        feeling = {"emotion": "neutral", "emotion_score": 0.9, "sentiment": "neutral", "sentiment_score": 0.9,
                   "emotion_scores": {}, "sentiment_scores": {}, "emotion_ambiguous": False}
        monkeypatch.setattr(ee, "analyze_message", lambda t: nlp)
        monkeypatch.setattr(ee, "analyze_feeling", lambda t: feeling)
        monkeypatch.setattr(orch, "assess", lambda m, h: safety)
        offered, prompts = [], []
        monkeypatch.setattr(loop, "_default_choose", lambda m, schemas: offered.extend(s["function"]["name"] for s in schemas) or picks)
        monkeypatch.setattr(orch.llm_client, "complete", lambda msgs, **k: prompts.append(msgs[0]["content"]) or reply)
        ctx = SessionContext(user_id=uid, session_id="s", memory_enabled=True) if session else None
        return orch.respond("log 5 hours of sleep", [], session=ctx), offered, prompts
    return run, uid


def test_a_proposed_save_reaches_the_reply_and_the_response_but_not_the_database(turn, user_store):
    run, uid = turn
    result, _, prompts = run(SafetyAssessment("none", "none", False, {}), [("sleep_log", {"hours": 5})])
    assert result.proposal["tool"] == "sleep_log" and "Log 5 hours" in result.proposal["summary"]
    assert "YOU HAVE PREPARED THIS FOR THEM" in prompts[0] and "Never say or imply it is already saved" in prompts[0]
    assert user_store.sleep_logs(uid) == []


def test_saving_is_offered_at_elevated_risk_but_never_in_a_crisis_or_to_guests(turn):
    run, _ = turn
    _, offered, _ = run(SafetyAssessment("elevated", "none", False, {}), [])
    assert {"journal_save", "sleep_log", "mood_log", "jar_add"} <= set(offered) and "journal_search" not in offered
    _, offered, _ = run(SafetyAssessment("crisis", "ideation", False, {}), [])
    assert offered == []
    _, offered, _ = run(SafetyAssessment("none", "none", False, {}), [], session=False)
    assert offered == []


# ─────────────────────────── never "already saved" ───────────────────────────
from lumina.safety import output_guard  # noqa: E402

SUMMARY = 'Add to your jar of things that helped: "breathing exercise"'


@pytest.mark.parametrize("reply,claims", [
    # the reply from the A3 eval that the prompt alone did not prevent
    ("I've prepared something for you: I've added \"breathing exercise\" to your jar of things that helped. "
     "You can save this when you press the Save button below.", True),
    ("Your sleep has been logged.", True),
    ("Done! It's in your journal.", True),
    ("I've just saved that for you.", True),
    ("I've put together a note to save. Press Save below to keep it.", False),
    ("Once you press Save, it will be added to your jar.", False),
    ("You've logged a lot of short nights lately; that sounds exhausting.", False),
])
def test_a_reply_never_says_a_waiting_save_is_done(reply, claims):
    out = output_guard.check(reply, user_message="add breathing exercise to my jar", crisis=False,
                             crisis_subtype="none", pending_save=SUMMARY)
    assert out.replaced is claims
    if claims:
        assert out.reasons == ("claimed_save",) and SUMMARY in out.text and "press Save" in out.text
        assert not output_guard.claims_done(out.text)
    # Without a waiting save the same words are left alone (e.g. talking about something they did themselves).
    assert not output_guard.check(reply, user_message="x", crisis=False, crisis_subtype="none").replaced


def test_the_turn_replaces_a_claim_while_a_save_waits(turn, user_store):
    run, uid = turn
    result, _, _ = run(SafetyAssessment("none", "none", False, {}), [("sleep_log", {"hours": 5})],
                       reply="I've logged 5 hours of sleep for you.")
    assert result.proposal and "press Save" in result.reply and "I've logged" not in result.reply
    assert user_store.sleep_logs(uid) == []


# ─────────────────────────── writing directly in the app ───────────────────────────
def test_writing_in_the_app_needs_no_confirm_step_but_the_same_rules(api, user_store):
    c, register = api
    headers, uid = register("a@x.io")
    r = c.post("/journal/entries", json={"text": "  proud of   today "}, headers=headers)
    assert r.status_code == 201 and r.json()["text"] == "proud of today"
    r = c.post("/logs/sleep", json={"hours": 5.5, "quality": "poor"}, headers=headers)
    assert r.status_code == 201 and r.json()["hours"] == 5.5
    r = c.post("/logs/mood", json={"weather": "rain"}, headers=headers)
    assert r.status_code == 201 and r.json()["weather"] == "rain" and r.json()["note"] is None
    assert c.post("/logs/sleep", json={"hours": 30}, headers=headers).status_code == 422
    assert c.post("/logs/mood", json={"weather": "sunny"}, headers=headers).status_code == 422
    assert c.post("/journal/entries", json={"text": ""}, headers=headers).status_code == 422
    assert c.post("/journal/entries", json={"text": "x"}).status_code == 401                 # signed in only
    assert user_store.path.read_bytes().find(b"proud of today") == -1                        # still encrypted
