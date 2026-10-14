"""CBT extraction quality: does the LLM pull the right situation / thoughts / feelings / behaviours?

Data: data/eval/cbt_extraction/gold.jsonl (40 short first-person messages with hand-written labels;
see eval/datasets/DATASHEETS.md).  The live LLM (config.LLM_PROVIDER) runs lumina.memory.extraction.

Paraphrases are expected, so an item counts as matched when the MiniLM cosine between a predicted
and a gold item is >= MATCH (greedy one-to-one matching).  Per field:
  precision     matched predicted items / predicted items
  recall        matched gold items / gold items
  invented      share of messages whose gold field is empty but the prediction is not
Output: eval/reports/cbt_extraction.json
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "data" / "eval" / "cbt_extraction" / "gold.jsonl"
MATCH = 0.60
FIELDS = ("situation", "thoughts", "feelings", "behaviours")


def _items(record: dict, field: str) -> list[str]:
    v = record.get(field)
    return [v] if isinstance(v, str) and v else list(v or [])


def _match(pred: list[str], gold: list[str], embed) -> int:
    if not pred or not gold:
        return 0
    pv, gv = [embed(p) for p in pred], [embed(g) for g in gold]
    pairs = sorted(((float(a @ b), i, j) for i, a in enumerate(pv) for j, b in enumerate(gv)), reverse=True)
    used_p, used_g, n = set(), set(), 0
    for sim, i, j in pairs:
        if sim < MATCH:
            break
        if i not in used_p and j not in used_g:
            used_p.add(i); used_g.add(j); n += 1
    return n


def main() -> dict:
    from lumina.config import LLM_MODEL, LLM_PROVIDER
    from lumina.memory.embeddings import embed
    from lumina.memory.extraction import extract_elements

    gold = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]
    stats = {f: {"pred": 0, "gold": 0, "match_p": 0, "match_g": 0, "empty_gold": 0, "invented": 0} for f in FIELDS}
    failures = 0
    for rec in gold:
        pred = extract_elements(rec["text"]).model_dump()
        failures += all(not _items(pred, f) for f in FIELDS)
        for f in FIELDS:
            p, g = _items(pred, f), _items(rec, f)
            m = _match(p, g, embed)
            s = stats[f]
            s["pred"] += len(p); s["gold"] += len(g); s["match_p"] += m; s["match_g"] += m
            if not g:
                s["empty_gold"] += 1
                s["invented"] += bool(p)

    fields = {f: {"precision": round(s["match_p"] / s["pred"], 3) if s["pred"] else None,
                  "recall": round(s["match_g"] / s["gold"], 3) if s["gold"] else None,
                  "invented_when_absent": round(s["invented"] / s["empty_gold"], 3) if s["empty_gold"] else None,
                  "n_gold_items": s["gold"]} for f, s in stats.items()}
    out = {"n": len(gold), "llm": f"{LLM_PROVIDER}:{LLM_MODEL}", "match_threshold": MATCH,
           "empty_extractions": failures, "fields": fields}
    rep = ROOT / "eval" / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "cbt_extraction.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
