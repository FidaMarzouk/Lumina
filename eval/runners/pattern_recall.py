"""Does the pattern miner link today's story to the right earlier moment — and only when there is one?

Synthetic histories (lumina/memory/synthetic.py; invented, not user data).  Each user has one episode
this week (scenario C, paraphrase i) and 15 earlier distractor episodes from other scenarios.
  positive users: one earlier episode of C in a *different* paraphrase is planted at a random age
  negative users: no earlier episode of C
For each similarity threshold, patterns.find_echo is run with real MiniLM embeddings:
  recall         = positives linked to the planted episode
  wrong_link     = positives linked to a different episode
  false_pattern  = negatives linked to anything
  year_band_preferred = per scenario, a history holding the same pattern ~4 months and ~1 year ago:
                        how often the year-old one is linked (the "pattern from last year" preference)
The deployed threshold is config.MEMORY_MIN_SIMILARITY; the sweep shows whether it should move.
Output: eval/reports/pattern_recall.json
"""

from __future__ import annotations

import json
import random
from datetime import timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
N_USERS = 200
N_DISTRACTORS = 15


def _histories(rng: random.Random):
    from lumina.memory.synthetic import SCENARIOS
    keys = list(SCENARIOS)
    for u in range(N_USERS):
        current_key = rng.choice(keys)
        i = rng.randrange(3)
        positive = u % 2 == 0
        others = [k for k in keys if k != current_key]
        earlier = [{"key": k, "text": SCENARIOS[k]["summaries"][rng.randrange(3)], "age": rng.randint(21, 430),
                    "planted": False} for k in (rng.choice(others) for _ in range(N_DISTRACTORS))]
        if positive:
            j = rng.choice([x for x in range(3) if x != i])
            earlier.append({"key": current_key, "text": SCENARIOS[current_key]["summaries"][j],
                            "age": rng.randint(21, 430), "planted": True})
        yield {"positive": positive, "current": SCENARIOS[current_key]["summaries"][i], "earlier": earlier}


def main() -> dict:
    from lumina.config import MEMORY_MIN_SIMILARITY, PATTERN_LOOKBACK_DAYS, PATTERN_YEAR_BAND_DAYS
    from lumina.insights.patterns import find_echo
    from lumina.memory.embeddings import embed
    from lumina.memory.store import iso, utcnow
    from lumina.memory.synthetic import SCENARIOS

    texts = [s for sc in SCENARIOS.values() for s in sc["summaries"]]
    vec = {t: embed(t) for t in texts}
    now = utcnow()
    users = list(_histories(random.Random(13)))

    def episodes(user):
        cur = [{"summary": user["current"], "embedding": vec[user["current"]], "created_at": iso(now - timedelta(days=1))}]
        old = [{"summary": e["text"], "embedding": vec[e["text"]], "created_at": iso(now - timedelta(days=e["age"])),
                "planted": e["planted"]} for e in user["earlier"]]
        return cur, old

    # Similarity of same-scenario paraphrase pairs vs different-scenario pairs (how separable the task is).
    same = [float(vec[a] @ vec[b]) for sc in SCENARIOS.values() for a in sc["summaries"] for b in sc["summaries"] if a < b]
    keys = list(SCENARIOS)
    diff = [float(vec[a] @ vec[b]) for x in range(len(keys)) for y in range(x + 1, len(keys))
            for a in SCENARIOS[keys[x]]["summaries"] for b in SCENARIOS[keys[y]]["summaries"]]

    rows = []
    for t in np.round(np.arange(0.30, 0.76, 0.05), 2):
        rec = wrong = false = 0
        for user in users:
            cur, old = episodes(user)
            echo = find_echo(cur, old, now, min_similarity=float(t))
            if user["positive"]:
                planted = next(e for e in old if e["planted"])
                if echo and echo["summary_then"] == planted["summary"]:
                    rec += 1
                elif echo:
                    wrong += 1
            elif echo:
                false += 1
        npos = sum(u["positive"] for u in users)
        rows.append({"threshold": float(t), "recall": round(rec / npos, 3), "wrong_link": round(wrong / npos, 3),
                     "false_pattern": round(false / (len(users) - npos), 3)})
    best = max(rows, key=lambda r: r["recall"] - r["wrong_link"] - r["false_pattern"])
    deployed = min(rows, key=lambda r: abs(r["threshold"] - MEMORY_MIN_SIMILARITY))

    # Year-band preference: a history with the same scenario both ~4 months and ~1 year ago.
    band_hits, band_n = 0, 0
    for sc in SCENARIOS.values():
        cur = [{"summary": sc["summaries"][0], "embedding": vec[sc["summaries"][0]], "created_at": iso(now)}]
        old = [{"summary": sc["summaries"][1], "embedding": vec[sc["summaries"][1]], "created_at": iso(now - timedelta(days=120))},
               {"summary": sc["summaries"][2], "embedding": vec[sc["summaries"][2]],
                "created_at": iso(now - timedelta(days=PATTERN_LOOKBACK_DAYS))}]
        echo = find_echo(cur, old, now)
        band_n += 1
        band_hits += bool(echo and echo["summary_then"] == sc["summaries"][2])

    out = {"n_users": len(users), "n_distractors": N_DISTRACTORS, "deployed_threshold": MEMORY_MIN_SIMILARITY,
           "deployed": deployed, "best_threshold": best["threshold"], "best": best, "sweep": rows,
           "paraphrase_similarity_median": round(float(np.median(same)), 3),
           "cross_scenario_similarity_median": round(float(np.median(diff)), 3),
           "cross_scenario_similarity_p95": round(float(np.percentile(diff, 95)), 3),
           "year_band_preferred": f"{band_hits}/{band_n}", "year_band_days": PATTERN_YEAR_BAND_DAYS}
    rep = ROOT / "eval" / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "pattern_recall.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "sweep"}, indent=2))
    return out


if __name__ == "__main__":
    main()
