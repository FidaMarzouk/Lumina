"""Read tools (A2): only the person's own data, validated arguments, never on risky turns, never invented."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from lumina.agent import loop, tools
from lumina.safety.assessment import SafetyAssessment

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def person(user_store):
    """Two people; the first has journal pages, feelings, a jar and a journey."""
    a = user_store.create_user("a@x.io", "h", "Sam", consent=True)
    b = user_store.create_user("b@x.io", "h", "Bo", consent=True)
    for days, summary, vec, emotion in ((2, "You talked about your sister and the argument.", [1, 0, 0], "anger"),
                                        (9, "You described lying awake before the exam.", [0, 1, 0], "fear"),
                                        (40, "An old page from last month about work.", [0, 0, 1], "sadness")):
        s = user_store.create_session(a["id"], "open", now=NOW - timedelta(days=days))
        user_store.add_turn(s["id"], a["id"], intent="venting", emotion=emotion, sentiment="negative", pain_points=[],
                            macro=None, risk_level="none", now=NOW - timedelta(days=days))
        user_store.save_episode(s["id"], a["id"], summary=summary, themes=["family"], elements={}, emotions=[emotion],
                                had_crisis=False, embedding=np.asarray(vec, dtype=np.float32), now=NOW - timedelta(days=days))
    crisis = user_store.create_session(a["id"], "open", now=NOW - timedelta(days=1))
    user_store.save_episode(crisis["id"], a["id"], summary="A crisis conversation.", themes=[], elements={}, emotions=[],
                            had_crisis=True, embedding=np.asarray([1, 0, 0], dtype=np.float32), now=NOW - timedelta(days=1))
    user_store.add_jar_item(a["id"], "a walk by the sea", "kept")
    user_store.add_jar_item(a["id"], "suggested only", "suggested")
    user_store.add_jar_item(b["id"], "Bo's secret", "kept")
    user_store.set_progress(a["id"], "sleep_reset", 1, "active", NOW)
    embed = lambda text: np.asarray([1, 0, 0] if "sister" in text else [0, 1, 0], dtype=np.float32)  # noqa: E731
    return tools.ToolContext(user_store, a["id"], True, NOW, embed=embed)


def test_journal_search_by_topic_and_recency_skips_crisis_pages(person):
    by_topic = tools.call("journal_search", {"query": "my sister"}, person)
    assert [p["summary"] for p in by_topic["pages"]][0].startswith("You talked about your sister")
    recent = tools.call("journal_search", {"days_back": 30}, person)
    assert [p["summary"][:12] for p in recent["pages"]] == ["You talked a", "You describe"]   # newest first, ≤ 30 days
    assert all("crisis" not in p["summary"] for p in recent["pages"])
    assert tools.call("journal_search", {"days_back": 400}, person)["pages"][-1]["summary"].startswith("An old page")


def test_tools_only_ever_read_the_signed_in_persons_data(person):
    assert tools.call("jar_list", {}, person)["things_that_helped"] == ["a walk by the sea"]   # kept only, own only
    # a user id smuggled into the arguments is refused, not used
    assert "error" in tools.call("jar_list", {"user_id": "someone-else"}, person)


def test_arguments_are_validated_and_unknown_tools_refused(person):
    assert "error" in tools.call("journal_search", {"days_back": 99999}, person)
    assert "error" in tools.call("journal_search", {"query": "x" * 500}, person)
    assert "error" in tools.call("delete_everything", {}, person)


def test_feelings_are_labelled_as_detected_not_reported(person):
    out = tools.call("feelings_over_time", {"days": 14}, person)
    assert "not ones they reported" in out["source"]
    assert {f.split(" ")[0] for w in out["weeks"] for f in w["feelings"]} == {"anger", "fear"}
    assert all("message" in f for w in out["weeks"] for f in w["feelings"])          # words, not bare scores


def test_an_empty_window_still_names_the_most_recent_page(person):
    out = tools.call("journal_search", {"days_back": 1}, person)
    assert out["pages"] == [] and out["most_recent_page"]["summary"].startswith("You talked about your sister")


def test_memory_off_means_no_notes_to_read(person):
    off = tools.ToolContext(person.store, person.user_id, False, NOW)
    assert "unavailable" in tools.call("journal_search", {}, off)
    assert "unavailable" in tools.call("feelings_over_time", {}, off)


def test_journey_status(person):
    out = tools.call("journey_status", {}, person)
    assert out["current"]["step_number"] == 2 and out["current"]["steps"] >= 2


def test_loop_runs_chosen_tools_caps_calls_and_drops_flagged_results(person):
    choose = lambda msg, schemas: [("jar_list", {}), ("jar_list", {}), ("journey_status", {}), ("journal_search", {})]  # noqa: E731
    run = loop.run("what helped me?", person, choose=choose, injection_probability=lambda t: 0.0)
    assert [c["name"] for c in run.calls] == ["jar_list", "journey_status"]        # duplicates dropped, max 2
    flagged = loop.run("x", person, choose=lambda m, s: [("jar_list", {})], injection_probability=lambda t: 0.99)
    assert not flagged.used                                                         # never reaches the prompt


def test_only_text_from_stored_notes_is_injection_checked(person):
    """The classifier scores JSON as an attack; the app's own labels and wrappers are not user data."""
    def flags_everything(text):
        return 0.99
    feelings = loop.run("x", person, choose=lambda m, s: [("feelings_over_time", {})],
                        injection_probability=flags_everything)
    assert feelings.used                                                            # no stored text to check
    assert tools.stored_texts({"pages": [{"summary": "s", "title": "t", "themes": ["a"]}],
                               "things_that_helped": ["walk"]}) == ["walk", "s", "t", "a"]
    seen = []
    loop.run("x", person, choose=lambda m, s: [("jar_list", {})], injection_probability=lambda t: seen.append(t) or 0.0)
    assert seen == ["a walk by the sea"]                                            # each item on its own, no JSON


def test_loop_never_raises(person):
    def broken(message, schemas):
        raise TimeoutError
    assert not loop.run("x", person, choose=broken).used
    assert loop.run("x", person, choose=lambda m, s: []).calls == []


def test_schemas_are_plain_json_schema():
    for tool in tools.READ_TOOLS.values():
        schema = tool.schema()["function"]
        assert schema["parameters"]["type"] == "object" and "user_id" not in str(schema)


# ─────────────────────────── in the turn ───────────────────────────
from lumina import orchestrator as orch  # noqa: E402
from lumina.memory.service import SessionContext  # noqa: E402


@pytest.fixture
def turn(monkeypatch, user_store):
    """Run a turn with tools on; safety, intent, tool choice and LLM stubbed.  Returns (result, choose-calls, prompt)."""
    from lumina.dialogue import empathy_engine as ee
    uid = user_store.create_user("t@x.io", "h", "Sam", consent=True)["id"]
    user_store.add_jar_item(uid, "calling my sister", "kept")
    monkeypatch.setattr(orch, "AGENT_TOOLS", True)
    monkeypatch.setattr(orch, "_response_guard", lambda: None)
    monkeypatch.setattr(orch.memory, "load_context", lambda *a, **k: ({}, None))
    monkeypatch.setattr(orch, "_remember", lambda *a, **k: None)
    monkeypatch.setattr("lumina.agent.loop._safe", lambda result, p: True)

    def run(safety, intent, picks, session=True):
        nlp = {"cleaned_text": "msg", "tokens": [], "entities": {}, "intent": intent, "intent_confidence": 0.9,
               "intent_ambiguous": None}
        feeling = {"emotion": "neutral", "emotion_score": 0.9, "sentiment": "neutral", "sentiment_score": 0.9,
                   "emotion_scores": {}, "sentiment_scores": {}, "emotion_ambiguous": False}
        monkeypatch.setattr(ee, "analyze_message", lambda t: nlp)
        monkeypatch.setattr(ee, "analyze_feeling", lambda t: feeling)
        monkeypatch.setattr(orch, "assess", lambda m, h: safety)
        chosen, prompts = [], []
        monkeypatch.setattr(loop, "_default_choose", lambda m, s: chosen.append(m) or picks)
        monkeypatch.setattr(orch.llm_client, "complete", lambda msgs, **k: prompts.append(msgs[0]["content"]) or "Here it is.")
        ctx = SessionContext(user_id=uid, session_id="s", memory_enabled=True) if session else None
        return orch.respond("what's in my jar?", [], session=ctx), chosen, prompts
    return run


SAFE = SafetyAssessment("none", "none", False, {})


def test_an_act_turn_answers_from_the_tool_results(turn):
    result, chosen, prompts = turn(SAFE, "action_request", [("jar_list", {})])
    assert chosen and result.debug["tools"] == ["jar_list"] and result.debug["route"] == "act"
    assert "calling my sister" in prompts[0] and "Never add" in prompts[0]


@pytest.mark.parametrize("safety", [SafetyAssessment("crisis", "ideation", False, {}),
                                    SafetyAssessment("elevated", "none", False, {"history_crisis": True}),
                                    SafetyAssessment("none", "none", False, {"history_crisis": True})])
def test_no_tools_in_a_crisis_or_after_one(turn, safety):
    result, chosen, _ = turn(safety, "action_request", [("jar_list", {})])
    assert chosen == [] and result.debug["tools"] == []


def test_elevated_turns_may_only_read_the_jar_and_journey(turn):
    elevated = SafetyAssessment("elevated", "none", False, {})
    result, _, _ = turn(elevated, "action_request", [("journal_search", {}), ("jar_list", {})])
    assert result.debug["tools"] == ["jar_list"]                      # journal pages are not offered, nor run


def test_no_tools_for_guests_or_plain_talk(turn):
    assert turn(SAFE, "action_request", [("jar_list", {})], session=False)[1] == []
    assert turn(SAFE, "venting", [("jar_list", {})])[1] == []


def test_a_misread_look_up_goes_ahead_only_if_a_read_tool_is_chosen(turn):
    injection = SafetyAssessment("none", "none", True, {})
    looked_up, _, prompts = turn(injection, "action_request", [("journal_search", {})])
    assert looked_up.debug["route"] == "act" and looked_up.injection_detected            # flag still reported
    real_injection, _, prompts = turn(injection, "action_request", [])
    assert real_injection.debug["route"] == "injection" and "override or reveal" in prompts[0]


def test_tools_off_by_default(turn, monkeypatch):
    monkeypatch.setattr(orch, "AGENT_TOOLS", False)
    assert turn(SAFE, "action_request", [("jar_list", {})])[1] == []
