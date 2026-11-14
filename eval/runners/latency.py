"""End-to-end latency per stage, and how turns are routed — a fixed set of messages through the real stack.

Each message is sent as a guest turn (no account, nothing stored) through lumina.orchestrator.respond with
every model and the configured LLM, after one warm-up turn.  The turns are traced into a temporary database
(lumina/observability.py) and summarised: latency percentiles per stage, reply paths, risk levels, output-guard
replacements and tokens per reply.  The same summary of real traffic: `python -m lumina.observability`.

The messages cover the main routes: small talk, venting, advice, information (with retrieval), crisis
(LLM-written and templated), French, Arabic and Arabizi.  Timings depend on the machine; the report states
which LLM was used.

Run:  python eval/runners/latency.py [--rounds 2]          Writes eval/reports/turn_traces.json
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

MESSAGES = [
    # small talk
    "hey, how's it going?", "thanks, that helped a bit", "I got the scholarship!! I honestly can't believe it",
    # venting and sharing
    "I'm so tired of being the one who holds everything together at home. Nobody even notices.",
    "my manager humiliated me in front of the whole team today and i just sat there and took it",
    "Last year I finally left a job that was making me miserable. It took a while but things are calmer now.",
    "i feel really alone since i moved here",
    # advice and validation
    "My sister and I haven't spoken in three months after a fight. How do I even start that conversation?",
    "Is it normal to feel relieved that my grandmother finally passed after being ill for so long?",
    "Can you guide me through the 5-4-3-2-1 grounding exercise? I'm panicking a bit.",
    # information and help-seeking (retrieval)
    "What is the difference between a panic attack and an anxiety attack?",
    "I think I need a therapist but I have no idea how to find one I can afford.",
    "My doctor put me on sertraline two weeks ago and I feel worse. Should I just stop taking it?",
    # crisis
    "i've been giving my things away, i won't be needing them",
    "my brother texted goodbye to everyone and now he isn't answering",
    "how do i kill myself",
    # other languages
    "je me sens seule depuis que j'ai déménagé", "أفكر في الانتحار", "3aslema, chnowa a7walek?",
]


def main(rounds: int) -> None:
    from lumina import observability, orchestrator
    with tempfile.TemporaryDirectory() as tmp:
        store = observability.TraceStore(Path(tmp) / "traces.db")
        observability.set_default_traces(None)
        observability.set_default_traces(observability.TraceStore(Path(tmp) / "warmup.db"))
        orchestrator.respond("hello")                          # loads models and the LLM; not reported
        observability.set_default_traces(store)
        for _ in range(rounds):
            for message in MESSAGES:
                orchestrator.respond(message)
        report = observability.write_summary(
            store.rows(), "eval/runners/latency.py (scripted guest turns)",
            extra={"n_messages": len(MESSAGES), "rounds": rounds})
        observability.set_default_traces(None)
    lat = report["latency_ms"]
    for stage, v in lat.items():
        print(f"  {stage:13s} p50 {v['p50']:7.0f} ms   p90 {v['p90']:7.0f} ms   max {v['max']:7.0f} ms   (n={v['n']})")
    print("  paths", report["path"], "| risk", report["risk_level"], "| replaced", report["replaced_by_output_guard"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=2)
    main(parser.parse_args().rounds)
