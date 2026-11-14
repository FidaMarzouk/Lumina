"""Crisis detection on French, Arabic and Tunisian Arabic messages — the full safety assessment, live.

Set: data/eval/safety_multilingual/gold.jsonl — 60 crisis and 40 ordinary messages in four writing systems
(French, Arabic, Tunisian Arabic in Arabic letters, Tunisian Arabic in Latin letters = "Arabizi"); see
eval/datasets/DATASHEETS.md.  It was written for this test, not collected, and is small: read the numbers
as a regression check, not as population recall.

Reported per writing system:
    crisis recall, crisis-or-elevated recall, crisis flag rate on ordinary messages,
    how many messages were scored as prompt injection, and how the language was routed.
`--baseline` repeats the run with the language handling switched off (the behaviour before it existed).

Needs the real models and a running LLM.   Run:  python eval/runners/safety_multilingual.py [--baseline]
Writes eval/reports/safety_multilingual.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "data" / "eval" / "safety_multilingual" / "gold.jsonl"
OUT = ROOT / "eval" / "reports" / "safety_multilingual.json"


def evaluate(rows: list[dict], detectors) -> dict:
    from lumina.safety.assessment import assess
    per: dict[str, dict] = {}
    for r in rows:
        a = assess(r["text"], [], detectors)
        s = per.setdefault(r["lang"], {"n_crisis": 0, "n_ordinary": 0, "crisis_detected": 0, "crisis_or_elevated": 0,
                                       "ordinary_flagged_crisis": 0, "ordinary_flagged_elevated": 0,
                                       "scored_as_injection": 0, "not_understood": 0, "routed": Counter()})
        s["routed"][a.language] += 1
        s["scored_as_injection"] += a.injection
        s["not_understood"] += not a.understood
        if r["label"] == "crisis":
            s["n_crisis"] += 1
            s["crisis_detected"] += a.is_crisis
            s["crisis_or_elevated"] += a.risk_level != "none"
        else:
            s["n_ordinary"] += 1
            s["ordinary_flagged_crisis"] += a.is_crisis
            s["ordinary_flagged_elevated"] += a.risk_level == "elevated"
    for s in per.values():
        s["routed"] = dict(s["routed"])
        s["crisis_recall"] = round(s["crisis_detected"] / s["n_crisis"], 3)
        s["crisis_or_elevated_recall"] = round(s["crisis_or_elevated"] / s["n_crisis"], 3)
        s["ordinary_crisis_rate"] = round(s["ordinary_flagged_crisis"] / s["n_ordinary"], 3)
    total_c = sum(s["n_crisis"] for s in per.values())
    return {"by_writing_system": per,
            "overall": {"crisis_recall": round(sum(s["crisis_detected"] for s in per.values()) / total_c, 3),
                        "crisis_or_elevated_recall": round(sum(s["crisis_or_elevated"] for s in per.values()) / total_c, 3),
                        "ordinary_crisis_rate": round(sum(s["ordinary_flagged_crisis"] for s in per.values())
                                                      / sum(s["n_ordinary"] for s in per.values()), 3),
                        "scored_as_injection": sum(s["scored_as_injection"] for s in per.values())}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true", help="also run with language handling off")
    args = parser.parse_args()

    from lumina.config import LLM_MODEL, LLM_PROVIDER
    from lumina.safety.assessment import Detectors
    rows = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = {"n": len(rows), "llm": f"{LLM_PROVIDER}:{LLM_MODEL}", "reviewed_by_native_speaker": all("reviewed by user" in r.get("labeller", "") for r in rows),
              "with_language_handling": evaluate(rows, Detectors.default())}
    if args.baseline:
        d = Detectors.default()
        d.language, d.translate = (lambda text: "en"), (lambda text: None)
        report["baseline_english_only"] = evaluate(rows, d)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for name in ("baseline_english_only", "with_language_handling"):
        if name not in report:
            continue
        print(name)
        for lang, s in report[name]["by_writing_system"].items():
            print(f"  {lang:8s} crisis {s['crisis_detected']}/{s['n_crisis']}  crisis-or-elevated "
                  f"{s['crisis_or_elevated']}/{s['n_crisis']}  ordinary→crisis {s['ordinary_flagged_crisis']}/"
                  f"{s['n_ordinary']}  as-injection {s['scored_as_injection']}  routed {s['routed']}")
        print("  overall", report[name]["overall"])


if __name__ == "__main__":
    main()
