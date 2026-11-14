"""Q1: why the pain-point labels were retired, and how journeys are recommended instead.

Part 1 — the retired zero-shot pain-point classifier (cross-encoder/nli-MiniLM2-L6-H768 over the 15 labels in
lumina/nlp/lexicons/pain_points.py), on the 300 user-reviewed gold intent messages: how often small talk and
personal messages get a label at each threshold, and each label's median score.  It ran on every message
until Q1 and fed the reply prompt, the stored turn signals, weekly themes and the journey recommender.

Part 2 — journey recommendation on the synthetic histories (lumina/memory/synthetic.py), 3 session summaries
per scenario:
    old  pain points of the summaries → dominant macro → first journey listing that macro as a theme
    new  lumina.journey.planner: the journey whose description (one of three profile texts) is closest in
         meaning to the summaries
FITS says which journeys suit each scenario; it is a judgement written for this test (pending the user's
review), with 7 scenarios only.  Read the result as a sanity check, not an accuracy estimate.

Run:  python eval/runners/journey_recommendation.py          Writes eval/reports/journey_recommendation.json
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import median

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "eval" / "reports" / "journey_recommendation.json"
PAIN_MODEL = "cross-encoder/nli-MiniLM2-L6-H768"
OLD_THRESHOLD = 0.12

FITS = {
    "work_deadline": ["thought_record", "self_compassion", "grounding_anxiety"],
    "sleep": ["sleep_reset"],
    "friend_conflict": ["thought_record", "reconnecting", "self_compassion"],
    "loneliness": ["reconnecting", "behavioural_activation"],
    "family_visit": ["self_compassion", "thought_record"],
    "good_week": [],                                   # nothing needed; any suggestion is acceptable
    "exam_pressure": ["thought_record", "grounding_anxiety", "behavioural_activation"],
}


def pain_scores(texts: list[str]) -> list[dict]:
    from transformers import pipeline

    from lumina.nlp.lexicons import PAIN_POINT_LABELS
    clf = pipeline("zero-shot-classification", model=PAIN_MODEL, device=-1)
    out = []
    for t in texts:
        r = clf(t[:512], candidate_labels=PAIN_POINT_LABELS, multi_label=True)
        out.append(dict(zip(r["labels"], r["scores"])))
    return out


def part1() -> dict:
    from lumina.nlp.lexicons import PAIN_POINT_LABELS
    gold = [json.loads(line) for line in (ROOT / "data/eval/intent/gold.jsonl").open(encoding="utf-8")]
    scores = pain_scores([g["text"] for g in gold])
    casual = [s for s, g in zip(scores, gold) if g["gold"] == "casual"]
    personal = [s for s, g in zip(scores, gold) if g["gold"] != "casual"]
    sweep = []
    for thr in (0.12, 0.3, 0.5, 0.7, 0.9):
        sweep.append({"threshold": thr,
                      "small_talk_labelled": round(float(np.mean([max(s.values()) >= thr for s in casual])), 3),
                      "personal_labelled": round(float(np.mean([max(s.values()) >= thr for s in personal])), 3)})
    return {"n_gold": len(gold), "n_small_talk": len(casual), "deployed_threshold": OLD_THRESHOLD, "sweep": sweep,
            "median_score_per_label": {label: round(median(s[label] for s in scores), 3) for label in PAIN_POINT_LABELS}}


def part2() -> dict:
    from lumina.journey import planner
    from lumina.journey.catalog import load_catalog
    from lumina.memory.embeddings import embed
    from lumina.memory.synthetic import SCENARIOS
    from lumina.nlp.lexicons import MACRO_MAP, MACRO_PRIORITY

    journeys = list(load_catalog().values())
    profiles = {
        "title + summary": lambda j: f"{j.title}. {j.summary}",
        "title + summary + step goals (deployed)": planner.profile_text,
        "title + summary + step goals + openers": lambda j: f"{j.title}. {j.summary} "
                                                         + " ".join(s.goal + " " + s.opener for s in j.steps),
    }
    episodes = {name: np.stack([embed(t) for t in sc["summaries"]]) for name, sc in SCENARIOS.items()}

    def judge(name: str, picked: str | None) -> str:
        return "no fit defined" if not FITS[name] else ("fits" if picked in FITS[name] else "does not fit")

    results = {}
    for label, text in profiles.items():
        P = np.stack([embed(text(j)) for j in journeys])
        rows = []
        for name, E in episodes.items():
            fit = (E @ P.T).mean(axis=0)
            order = np.argsort(-fit)
            picked = journeys[order[0]].id
            rows.append({"scenario": name, "picked": picked, "similarity": round(float(fit[order[0]]), 3),
                         "runner_up": journeys[order[1]].id, "verdict": judge(name, picked)})
        results[label] = {"fits": sum(r["verdict"] == "fits" for r in rows), "rows": rows}

    scores = pain_scores([t for sc in SCENARIOS.values() for t in sc["summaries"]])
    rows, i = [], 0
    for name, sc in SCENARIOS.items():
        macros = Counter()
        for s in scores[i:i + len(sc["summaries"])]:
            picked_labels = [lab for lab, v in sorted(s.items(), key=lambda kv: -kv[1]) if v >= OLD_THRESHOLD][:3]
            found = {MACRO_MAP.get(lab) for lab in picked_labels}
            macros[next((m for m in MACRO_PRIORITY if m in found), "none")] += 1
        i += len(sc["summaries"])
        macro = next((m for m, _ in macros.most_common() if m not in ("none", "trauma & crisis")), None)
        picked = next((j.id for j in journeys if macro in j.themes), None)
        rows.append({"scenario": name, "macro": macro, "picked": picked, "verdict": judge(name, picked)})
    results["old: pain-point macro"] = {"fits": sum(r["verdict"] == "fits" for r in rows), "rows": rows}
    return {"n_scenarios": len(SCENARIOS), "n_with_a_fit": sum(bool(v) for v in FITS.values()),
            "fits_judged_by": "Claude, 2026-11-14; pending user review", "fits": FITS, "methods": results}


def main() -> None:
    report = {"pain_points_retired": part1(), "journey_recommendation": part2()}
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    p1 = report["pain_points_retired"]
    for row in p1["sweep"]:
        print(f"  threshold {row['threshold']:.2f}: small talk labelled {row['small_talk_labelled']:.0%}, "
              f"personal {row['personal_labelled']:.0%}")
    p2 = report["journey_recommendation"]
    for name, r in p2["methods"].items():
        print(f"  {name}: {r['fits']}/{p2['n_with_a_fit']} fit — " + ", ".join(f"{x['scenario']}→{x['picked']}" for x in r["rows"]))


if __name__ == "__main__":
    main()
