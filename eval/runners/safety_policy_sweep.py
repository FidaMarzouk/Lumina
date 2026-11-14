"""Compare crisis decision policies on (a) clinical recall, (b) flag rate on help-seeking counselling posts
(Amod), which resemble real Lumina traffic far more than everyday chat, and (c) indirect wording
(data/eval/safety_indirect/gold.jsonl: 15 indirect or third-party crisis messages, each paired with a
harmless near-miss).

Layers: f = floor, g = Llama Guard, p = risk classifier, r = LLM risk reader (lumina/safety/reader.py:
"none" | "self" | "method" | "other").  Uses the same dev/test split as safety_detection.py; Llama Guard and
reader outputs are cached in data/eval/cache/ (the reader cache is keyed by its prompt, so editing the prompt
re-reads everything).
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
from lumina.safety import reader as risk_reader                # noqa: E402
from lumina.safety.risk_model import risk_classifier           # noqa: E402

CACHE = ROOT / "data" / "eval" / "cache" / "guard_user_risk.json"
READER_CACHE = ROOT / "data" / "eval" / "cache" / "reader_risk.json"
INDIRECT = ROOT / "data" / "eval" / "safety_indirect" / "gold.jsonl"


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


def reader(texts):
    """The LLM risk reader's label per text, cached per prompt version."""
    version = hashlib.sha256((risk_reader._SYSTEM + json.dumps(risk_reader._EXAMPLES)).encode()).hexdigest()[:12]
    cache = json.loads(READER_CACHE.read_text(encoding="utf-8")) if READER_CACHE.exists() else {}
    if cache.get("_version") != version:
        cache = {"_version": version}
    out = []
    for i, t in enumerate(texts):
        k = hashlib.sha256(t.encode()).hexdigest()
        if k not in cache:
            r = risk_reader.read_risk(t)
            if r is not None:
                cache[k] = r
            if i % 25 == 0:
                READER_CACHE.write_text(json.dumps(cache), encoding="utf-8")
        out.append(cache.get(k, "none"))
    READER_CACHE.parent.mkdir(parents=True, exist_ok=True)
    READER_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return np.array(out)


DEPLOYED = "floor|guard|p>=.90|r:other|r:method|(r:self&p>=.45)"
POLICIES = {
    "floor|guard|p>=.45 (first policy)":   lambda f, g, p, r: f | g | (p >= .45),
    "floor|guard|p>=.90 (before S4)":      lambda f, g, p, r: f | g | (p >= .90),
    "floor|guard|p>=.98":                  lambda f, g, p, r: f | g | (p >= .98),
    "floor|(guard&p>=.10)|p>=.90":         lambda f, g, p, r: f | (g & (p >= .10)) | (p >= .90),
    "floor|guard|p>=.90|r:other":          lambda f, g, p, r: f | g | (p >= .90) | (r == "other"),
    "floor|guard|p>=.90|r:any":            lambda f, g, p, r: f | g | (p >= .90) | (r != "none"),
    "floor|guard|p>=.90|r:other|r:method|(r:self&p>=.10)":
        lambda f, g, p, r: f | g | (p >= .90) | np.isin(r, ["other", "method"]) | ((r == "self") & (p >= .10)),
    DEPLOYED:
        lambda f, g, p, r: f | g | (p >= .90) | np.isin(r, ["other", "method"]) | ((r == "self") & (p >= .45)),
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

    ind = [json.loads(l) for l in INDIRECT.open(encoding="utf-8") if l.strip()]
    ind_text = [r["text"] for r in ind]
    ind_pos = np.array([r["label"] == "crisis" for r in ind])

    def layers(texts):
        return (np.array([floor.check(t).triggered for t in texts]), guard(texts, cache), probs(texts), reader(texts))
    L_s, L_a, L_i = layers(sub["text"].tolist()), layers(amod), layers(ind_text)
    p_s, r_s = L_s[2], L_s[3]
    pos = sub["label"].to_numpy() == 1
    ev = (sub["source"] == "everyday").to_numpy()
    sev0 = ((sub["source"] == "cssrs") & (sub["label"] == 0)).to_numpy()

    rows = []
    for name, pol in POLICIES.items():
        c_s, c_a, c_i = pol(*L_s), pol(*L_a), pol(*L_i)
        elev_s = ((p_s >= .10) | (r_s != "none")) & ~c_s
        rows.append({"policy": name, "deployed": name == DEPLOYED,
                     "clinical_recall_crisis": round(float(c_s[pos].mean()), 3),
                     "clinical_recall_crisis_or_elevated": round(float((c_s | elev_s)[pos].mean()), 3),
                     "flag_rate_counselling_posts": round(float(c_a.mean()), 3),
                     "flag_rate_everyday": round(float(c_s[ev].mean()), 3),
                     "flag_rate_hard_negatives": round(float(c_s[sev0].mean()), 3),
                     "indirect_crisis_detected": f"{int(c_i[ind_pos].sum())}/{int(ind_pos.sum())}",
                     "indirect_near_miss_flagged": f"{int(c_i[~ind_pos].sum())}/{int((~ind_pos).sum())}"})
    out = {"n_clinical_subsample": int(len(sub)), "n_counselling": len(amod), "n_indirect": len(ind),
           "guard_flag_rate_counselling": round(float(L_a[1].mean()), 3),
           "reader_flag_rate_counselling": round(float((L_a[3] != "none").mean()), 3),
           "reader_alone": {"clinical_recall": round(float((r_s[pos] != "none").mean()), 3),
                            "flag_rate_hard_negatives": round(float((r_s[sev0] != "none").mean()), 3),
                            "flag_rate_everyday": round(float((r_s[ev] != "none").mean()), 3)},
           "policies": rows}
    (ROOT / "eval/reports/safety_policy_sweep.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines = ["# Crisis policy sweep", "",
             f"Clinical subsample n={out['n_clinical_subsample']} (test split) · counselling posts n={out['n_counselling']} "
             f"(Amod, not in gold) · Llama Guard flag rate on counselling posts: {out['guard_flag_rate_counselling']}", "",
             "| Policy | Clinical recall (crisis) | Clinical recall (crisis or elevated) | Flag rate: counselling | Flag rate: everyday | Flag rate: hard negatives | Indirect crisis | Near-miss flagged |",
             "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {'**' + r['policy'] + '** (deployed)' if r['deployed'] else r['policy']} | {r['clinical_recall_crisis']} | "
              f"{r['clinical_recall_crisis_or_elevated']} | {r['flag_rate_counselling_posts']} | {r['flag_rate_everyday']} | "
              f"{r['flag_rate_hard_negatives']} | {r['indirect_crisis_detected']} | {r['indirect_near_miss_flagged']} |"
              for r in rows]
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--amod-n", type=int, default=150)
    main(ap.parse_args().amod_n)
