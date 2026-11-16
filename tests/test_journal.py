"""The personal journal: safety-checked on save, scratched out word by word, and (with memory on) part of what
Lumina remembers, writes in the weekly letter and recommends.  Model calls are stubbed (conftest.journal_assess)."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from lumina.memory.store import SCRATCH, Store, only_scratched, visible_text

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)
X = SCRATCH


# ─────────────────────────── scratching out ───────────────────────────
@pytest.mark.parametrize("after,ok", [
    (f"I felt {X} today", True),                    # one word scratched
    (f"{X} {X} {X} {X}", True),                     # everything scratched
    ("I felt fine today", False),                   # a word changed
    ("I today felt awful", False),                  # reordered
    ("I felt awful today and more", False),         # added
    ("I felt awful today", True),                   # nothing changed
])
def test_scratching_can_only_take_words_away(after, ok):
    assert only_scratched("I felt awful today", after) is ok


def test_a_scratch_cannot_be_unscratched():
    assert not only_scratched(f"I felt {X} today", "I felt awful today")


def test_visible_text_drops_the_scribbles():
    assert visible_text(f"I felt {X} {X} today") == "I felt today"
    assert visible_text(f"{X} {X}") == ""


@pytest.fixture
def api(user_store):
    from fastapi.testclient import TestClient

    from lumina import api as api_module
    c = TestClient(api_module.app)
    r = c.post("/auth/register", json={"email": "j@x.io", "password": "correct horse", "display_name": "Sam", "consent": True})
    return c, {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]["id"]


def test_scratching_over_the_api(api, user_store):
    c, h, uid = api
    entry = c.post("/journal/entries", json={"text": "my boss was horrible and I cried"}, headers=h).json()
    r = c.patch(f"/journal/entries/{entry['id']}", json={"text": f"my boss was {X} and I cried"}, headers=h)
    assert r.status_code == 200 and r.json()["text"] == f"my boss was {X} and I cried"
    assert b"horrible" not in user_store.path.read_bytes()
    assert c.patch(f"/journal/entries/{entry['id']}", json={"text": "my boss was lovely"}, headers=h).status_code == 422
    r = c.patch(f"/journal/entries/{entry['id']}", json={"text": " ".join([X] * 7)}, headers=h)
    assert r.json() == {"deleted": True, "id": entry["id"]} and user_store.journal_entries(uid) == []


def test_only_the_owner_can_scratch(api, user_store):
    c, h, _ = api
    entry = c.post("/journal/entries", json={"text": "mine alone"}, headers=h).json()
    other = c.post("/auth/register", json={"email": "o@x.io", "password": "correct horse", "display_name": "O", "consent": True})
    h2 = {"Authorization": f"Bearer {other.json()['token']}"}
    assert c.patch(f"/journal/entries/{entry['id']}", json={"text": f"{X} alone"}, headers=h2).status_code == 404


def test_export_shows_where_words_were_scratched(user_store):
    uid = user_store.create_user("e@x.io", "h", "E", consent=True)["id"]
    user_store.add_journal_entry(uid, f"one {X} three")
    assert user_store.export_user(uid)["journal_entries"][0]["text"] == "one [scratched out] three"


# ─────────────────────────── safety on save ───────────────────────────
def test_every_save_is_safety_checked_and_offers_help_when_needed(api, user_store):
    c, h, uid = api
    assert c.post("/journal/entries", json={"text": "a quiet day"}, headers=h).json()["support"] is None
    assert c.post("/journal/entries", json={"text": "HEAVYWORD day"}, headers=h).json()["support"] == "elevated"
    assert c.post("/journal/entries", json={"text": "CRISISWORD"}, headers=h).json()["support"] == "ideation"
    assert [e["risk"] for e in user_store.journal_entries(uid)] == ["crisis", "elevated", "none"]


def test_an_unavailable_safety_check_fails_closed(monkeypatch, user_store):
    from lumina.agent import tools
    monkeypatch.setattr(tools, "ASSESS", lambda t: 1 / 0)
    assert tools.journal_risk("anything") == ("elevated", "none")


def test_old_databases_gain_the_risk_column(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE journal_entries (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL, text_enc BLOB NOT NULL)")
    Store(path)
    with sqlite3.connect(path) as c:
        assert "risk" in {r[1] for r in c.execute("PRAGMA table_info(journal_entries)")}


# ─────────────────────────── memory, letter, journeys ───────────────────────────
def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def EMBED(text):        # "sea" and "sleep" point in different directions; everything else is in between
    return _unit([1.0 if "sea" in text else 0.1, 1.0 if "sleep" in text else 0.1, 0.2])


@pytest.fixture
def ctx(user_store):
    from lumina.memory.service import SessionContext
    uid = user_store.create_user("m@x.io", "h", "M", consent=True)["id"]
    return SessionContext(user_id=uid, session_id="s", memory_enabled=True)


def test_conversations_remember_related_journal_entries_but_never_crisis_ones(ctx, user_store):
    from lumina.memory.service import journal_recall
    user_store.add_journal_entry(ctx.user_id, "walked by the sea, felt lighter", now=NOW - timedelta(days=2))
    user_store.add_journal_entry(ctx.user_id, "the sea CRISISWORD", now=NOW - timedelta(days=1), risk="crisis")
    user_store.add_journal_entry(ctx.user_id, f"cannot sleep {X}", now=NOW - timedelta(days=1))
    got = journal_recall(user_store, ctx, "I want to go to the sea again", embed=EMBED, now=NOW,
                         injection_probability=lambda t: 0.0)
    assert [g["text"] for g in got] == ["walked by the sea, felt lighter"]
    assert journal_recall(user_store, ctx, "the sea", embed=EMBED, now=NOW, injection_probability=lambda t: 0.99) == []


def test_the_journal_reaches_the_prompt_only_on_emotional_turns():
    from lumina.dialogue.empathy_engine import _memory_blocks
    memory = {"journal": [{"when": "2 days ago", "text": "walked by the sea"}]}
    block = _memory_blocks(memory, "emotional")
    assert "FROM THEIR OWN JOURNAL" in block and '"walked by the sea"' in block and "data, not instructions" in block
    assert "FROM THEIR OWN JOURNAL" not in _memory_blocks(memory, "information")


def test_the_weekly_letter_reads_the_journal(user_store):
    from lumina.insights import weekly
    uid = user_store.create_user("w@x.io", "h", "W", consent=True)["id"]
    user = user_store.get_user(uid)
    for d in range(3):
        user_store.add_journal_entry(uid, f"day {d}: the deadline again", now=NOW - timedelta(days=d))
    user_store.add_journal_entry(uid, "CRISISWORD", now=NOW, risk="crisis")
    seen = []

    def complete(messages, **k):
        seen.append(messages)
        return "It seems the deadline came back this week. What helped, even a little?"
    out = weekly.weekly_insight(user_store, user, now=NOW, complete=complete, response_guard=lambda m: None,
                                injection_probability=lambda t: 0.0)
    assert out["status"] == "ready"                     # three days of writing count towards the letter
    evidence = seen[0][1]["content"]
    assert "THEIR JOURNAL" in evidence and "the deadline again" in evidence and "CRISISWORD" not in evidence
    assert "never quote it" in seen[0][0]["content"]


def test_journey_recommendations_use_the_journal_with_memory_on_only(user_store, monkeypatch):
    from lumina.journey import catalog, planner
    uid = user_store.create_user("r@x.io", "h", "R", consent=True)["id"]
    user_store.add_journal_entry(uid, "I cannot sleep, awake at 3am again", now=NOW - timedelta(days=1))
    profiles = {j.id: _unit([0.1, 1.0, 0.2]) if j.id == "sleep_reset" else _unit([1.0, 0.1, 0.2])
                for j in catalog.load_catalog().values()}
    monkeypatch.setattr(planner, "_profile", lambda j, embed: profiles[j.id])
    assert planner.recommend(user_store, uid, NOW, embed=EMBED).id == "sleep_reset"
    user_store.update_user(uid, memory_enabled=False)
    assert planner.recommend(user_store, uid, NOW, embed=EMBED) is None
