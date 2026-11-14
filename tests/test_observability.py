"""Turn traces: stage timings and outcomes per turn, with no text and no way back to a person."""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from lumina import observability
from lumina.observability import Stopwatch, TraceStore, summarise


def _fields(**over):
    base = {"signed_in": False, "path": "llm", "risk_level": "none", "crisis_subtype": "none", "injection": False,
            "language": "en", "reader": "none", "intent": "venting", "intent_category": "emotional", "rag_hits": 0,
            "replaced": False, "guard_reasons": [], "degraded": [], "tokens_in": 300, "tokens_out": 60}
    return {**base, **over}


def test_stopwatch_adds_up_repeated_stages_and_a_total():
    sw = Stopwatch()
    with sw.stage("analysis"):
        pass
    with sw.stage("analysis"):
        pass
    ms = sw.finish()
    assert set(ms) == {"analysis", "total"} and ms["total"] >= ms["analysis"] >= 0


def test_traces_hold_no_text(trace_store):
    """The schema has no column for messages, replies, users or sessions."""
    cols = {r[1] for r in sqlite3.connect(trace_store.path).execute("PRAGMA table_info(turn_traces)")}
    assert not cols & {"message", "text", "reply", "content", "user_id", "session_id", "email"}
    trace_store.add(_fields(message="my secret sentence"), {"total": 1.0})       # unknown fields are dropped
    assert "secret" not in repr(trace_store.rows())


def test_purge_keeps_only_recent_rows(trace_store):
    now = datetime.now(timezone.utc)
    trace_store.add(_fields(), {"total": 1}, now=now - timedelta(days=40))
    trace_store.add(_fields(), {"total": 1}, now=now)
    assert trace_store.purge(30, now=now) == 1 and len(trace_store.rows()) == 1


def test_record_never_raises(monkeypatch):
    class Broken:
        def add(self, *a, **k):
            raise sqlite3.OperationalError("disk full")
    monkeypatch.setattr(observability, "default_traces", lambda: Broken())
    observability.record(_fields(), {"total": 1.0})


def test_summary_is_aggregates_only(trace_store):
    for i in range(10):
        trace_store.add(_fields(replaced=i == 0, guard_reasons=["phone_number"] if i == 0 else []),
                        {"safety": 2000 + i, "llm": 3000 + 10 * i, "total": 6000 + 10 * i})
    trace_store.add(_fields(path="template", risk_level="crisis", crisis_subtype="method", tokens_in=None,
                            tokens_out=None, degraded=["guard"]), {"safety": 2500, "total": 2600})
    s = summarise(trace_store.rows())
    assert s["n_turns"] == 11 and s["path"] == {"llm": 10, "template": 1}
    assert s["latency_ms"]["llm"]["n"] == 10 and s["latency_ms"]["llm"]["p50"] == pytest.approx(3050, abs=10)
    assert s["replaced_by_output_guard"] == 0.1 and s["guard_reasons"] == {"phone_number": 1}
    assert s["turns_with_a_degraded_layer"] == pytest.approx(1 / 11, abs=0.001)
    assert s["crisis_subtype"] == {"method": 1} and s["tokens_per_reply"] == {"in_p50": 300, "out_p50": 60}
    assert summarise([]) == {"n_turns": 0}


def test_tracing_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(observability, "TRACES_ENABLED", False)
    observability.set_default_traces(None)
    assert observability.default_traces() is None
    observability.record(_fields(), {"total": 1.0})      # a no-op, not an error
