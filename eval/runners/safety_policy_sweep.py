"""Compare crisis decision policies on (a) clinical recall and (b) flag rate on help-seeking
counselling posts (Amod), which resemble real Lumina traffic far more than everyday chat.

Uses the same dev/test split as safety_detection.py and the shared Llama Guard cache.
Run:  python eval/runners/safety_policy_sweep.py [--amod-n 150]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval" / "runners"))
import safety_detection as sd                                   # noqa: E402
from lumina.safety import floor                                # noqa: E402
from lumina.safety.guard import classify_user_risk             # noqa: E402
from lumina.safety.risk_model import risk_classifier           # noqa: E402

CACHE = ROOT / "data" / "eval" / "cache" / "guard_user_risk.json"


def probs(texts):
    out = []
    for i in range(0, len(texts), 32):
        for s in risk_classifier([t[:2500] for t in texts[i:i + 32]]):
            out.append({x["label"]: x["score"] for x in s}["suicide"])
    return np.array(out)


def guard(texts, cache):
    res = []
    for t in texts:
        k = hashlib.sha256(t.encode()).hexdigest()
        if k not in cache:
            r = classify_user_risk([{"role": "user", "content": t}])
            if r.available:
                cache[k] = {"unsafe": r.unsafe, "categories": list(r.categories)}
                CACHE.write_text(json.dumps(cache), encoding="utf-8")
        res.append(bool(cache.get(k, {}).get("unsafe")))
    return np.array(res)


POLICIES = {
    "current: floor|guard|p>=.45":       lambda f, g, p: f | g | (p >= .45),
    "floor|guard|p>=.90":                lambda f, g, p: f | g | (p >= .90),
    "floor|guard|p>=.98":                lambda f, g, p: f | g | (p >= .98),
    "floor|(guard&p>=.10)|p>=.98":       lambda f, g, p: f | (g & (p >= .10)) | (p >= .98),
    "floor|(guard&p>=.10)|p>=.90":       lambda f, g, p: f | (g & (p >= .10)) | (p >= .90),
}


def main(amod_n: int):
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    data = sd.pd.concat([sd.load_cssrs(), sd.load_everyday()], ignore_index=True)
    _, test = sd.split(data)
    keys = [hashlib.sha256(t.encode()).hexdigest() for t in test["text"]]
    sub = test[[k in cache for k in keys]]

    pool = [json.loads(l) for l in (ROOT / "data/eval/intent/pool.jsonl").open(encoding="utf-8")]
    gold_ids = {json.loads(l)["id"] for l in (ROOT / "data/eval/intent/gold.jsonl").open(encoding="utf-8")}
    amod = [r["text"] for r in pool if r["source"] == "amod" and r["id"] not in gold_ids]
    amod = random.Random(13).sample(amod, min(amod_n, len(amod)))

    f_s, g_s, p_s = (np.array([floor.check(t).triggered for t in sub["text"]]),
                     guard(sub["text"].tolist(), cache), probs(sub["text"].tolist()))
    f_a, g_a, p_a = (np.array([floor.check(t).triggered for t in amod]), guard(amod, cache), probs(amod))
    pos = sub["label"].to_numpy() == 1
    ev = (sub["source"] == "everyday").to_numpy()
    sev0 = ((sub["source"] == "cssrs") & (sub["label"] == 0)).to_numpy()

    rows = []
    for name, pol in POLICIES.items():
        c_s, c_a = pol(f_s, g_s, p_s), pol(f_a, g_a, p_a)
        elev_s = (p_s >= .10) & ~c_s
        rows.append({"policy": name, "clinical_recall_crisis": round(float(c_s[pos].mean()), 3),
                     "clinical_recall_crisis_or_elevated": round(float((c_s | elev_s)[pos].mean()), 3),
                     "flag_rate_counselling_posts": round(float(c_a.mean()), 3),
                     "flag_rate_everyday": round(float(c_s[ev].mean()), 3),
                     "flag_rate_hard_negatives": round(float(c_s[sev0].mean()), 3)})
    out = {"n_clinical_subsample": int(len(sub)), "n_counselling": len(amod),
           "guard_flag_rate_counselling": round(float(g_a.mean()), 3), "policies": rows}
    (ROOT / "eval/reports/safety_policy_sweep.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines = ["# Crisis policy sweep", "",
             f"Clinical subsample n={out['n_clinical_subsample']} (test split) · counselling posts n={out['n_counselling']} "
             f"(Amod, not in gold) · Llama Guard flag rate on counselling posts: {out['guard_flag_rate_counselling']}", "",
             "| Policy | Clinical recall (crisis) | Clinical recall (crisis or elevated) | Flag rate: counselling | Flag rate: everyday | Flag rate: hard negatives |",
             "|---|---|---|---|---|---|"]
    lines += [f"| {r['policy']} | {r['clinical_recall_crisis']} | {r['clinical_recall_crisis_or_elevated']} | "
              f"{r['flag_rate_counselling_posts']} | {r['flag_rate_everyday']} | {r['flag_rate_hard_negatives']} |" for r in rows]
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--amod-n", type=int, default=150)
    main(ap.parse_args().amod_n)
