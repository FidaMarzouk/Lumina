"""A2: read tools, end to end — the right look-up on requests, nothing on everything else, no invented actions.

100 hand-written messages (data/eval/agent_tools/cases.jsonl; pending the user's review), each sent through the
full real pipeline (safety, intent, route, tool model, reply model, output guard) as a signed-in person with memory
on, against a temporary account seeded with 14 months of synthetic history (lumina.memory.seed_demo) plus a jar
and an active journey:
    40 look-ups      expected tool: journal_search, feelings_over_time, jar_list or journey_status
    20 write requests  no read tool should run, and the reply must not claim it saved, logged, set or deleted
                       anything (writing is A3)
    40 plain talk    about the same things (sleep, journals, memories…): no tool should run

Run:  python eval/runners/agent_tools.py [--model qwen2.5:3b]      Writes eval/reports/agent_tools_<model>.json
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "data" / "eval" / "agent_tools" / "cases.jsonl"

# Replies to write requests that claim the action was done (checked on Lumina's output, not on user text).
_CLAIM = re.compile(r"\b(i'?ve|i have|i'll|i will|i just|i've gone ahead and)\s+(saved|logged|noted|added|set|created|"
                    r"deleted|removed|cleared|recorded|tracked|marked|started|written|put)\b|\b(has|have) been (saved|"
                    r"logged|noted|added|set|deleted|removed|cleared|recorded|tracked|marked)\b|^\s*done\b",
                    re.IGNORECASE | re.MULTILINE)


def main(model: str) -> dict:
    from lumina import observability, orchestrator
    from lumina.agent import loop
    from lumina.memory import seed_demo
    from lumina.memory.service import SessionContext
    from lumina.memory.store import Store, set_default_store

    cases = [json.loads(line) for line in CASES.open(encoding="utf-8")]
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "eval.db")
        set_default_store(store)
        traces = observability.TraceStore(Path(tmp) / "traces.db")
        observability.set_default_traces(traces)
        user = seed_demo.seed(store, "eval@lumina.local", "eval-password", "Alex")
        for item in ("a walk by the sea", "calling my sister", "the 4-7-8 breathing"):
            store.add_jar_item(user["id"], item, "kept")
        store.set_progress(user["id"], "sleep_reset", 1, "active")
        session = store.create_session(user["id"], "open")
        ctx = SessionContext(user_id=user["id"], session_id=session["id"], memory_enabled=True, display_name="Alex")

        orchestrator.AGENT_TOOLS = True
        loop.AGENT_MODEL = model
        orchestrator.respond("hello", [], session=ctx)                     # warm-up, not counted
        rows = []
        for case in cases:
            n_before = len(traces.rows())
            result = orchestrator.respond(case["text"], [], session=ctx)
            trace = traces.rows()[n_before]
            rows.append({**case, "route": result.debug.get("route"), "risk": result.risk_level,
                         "tools": result.debug.get("tools", []), "reply": result.reply,
                         "claims_done": bool(_CLAIM.search(result.reply)),
                         "ms_tools": trace["ms"].get("tools"), "ms_total": trace["ms"]["total"]})
            print(f"  {case['kind']:5s} {str(case['expected_tool']):18s} -> {','.join(rows[-1]['tools']) or '-':28s} "
                  f"route={rows[-1]['route']} | {case['text'][:60]}", flush=True)
        set_default_store(None)
        observability.set_default_traces(None)

    read = [r for r in rows if r["kind"] == "read"]
    write = [r for r in rows if r["kind"] == "write"]
    talk = [r for r in rows if r["kind"] == "talk"]
    tool_turns = [r for r in rows if r["ms_tools"] is not None]
    report = {
        "tool_model": model, "n": len(rows),
        "read": {"n": len(read),
                 "right_tool": sum(r["expected_tool"] in r["tools"] for r in read),
                 "no_tool": sum(not r["tools"] for r in read),
                 "wrong_tool_only": sum(bool(r["tools"]) and r["expected_tool"] not in r["tools"] for r in read),
                 "routes": dict(Counter(r["route"] for r in read)),
                 "by_tool": {t: f"{sum(t in r['tools'] for r in read if r['expected_tool'] == t)}/"
                                f"{sum(r['expected_tool'] == t for r in read)}"
                             for t in sorted({r['expected_tool'] for r in read})}},
        "write": {"n": len(write), "tool_called": sum(bool(r["tools"]) for r in write),
                  "reply_claims_done": sum(r["claims_done"] for r in write),
                  "routes": dict(Counter(r["route"] for r in write))},
        "talk": {"n": len(talk), "tool_called": sum(bool(r["tools"]) for r in talk),
                 "routes": dict(Counter(r["route"] for r in talk))},
        "latency_ms": {"tool_step_median": round(statistics.median(r["ms_tools"] for r in tool_turns)) if tool_turns else None,
                       "turn_median_with_tool_step": round(statistics.median(r["ms_total"] for r in tool_turns)) if tool_turns else None,
                       "turn_median_without": round(statistics.median(r["ms_total"] for r in rows if r["ms_tools"] is None))},
        "rows": rows,
    }
    out = ROOT / "eval" / "reports" / f"agent_tools_{model.replace(':', '_')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("tool_model", "read", "write", "talk", "latency_ms")}, indent=1))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    from lumina.config import AGENT_MODEL
    ap.add_argument("--model", default=AGENT_MODEL)
    main(ap.parse_args().model)
