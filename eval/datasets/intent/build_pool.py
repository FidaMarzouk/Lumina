"""Build the unlabelled pool of real user-style messages for the intent classifier.

Sources (licences in eval/datasets/DATASHEETS.md):
  amod      Amod/mental_health_counseling_conversations — "Context" (help-seeking posts)  [RAIL-D]
  ed        Estwld/empathetic_dialogues_llm (train)      — first user utterance           [CC-BY-NC-4.0]
  dd        OpenRL/daily_dialog (train)                  — first utterance (small talk)   [CC-BY-NC-SA-4.0]
  faq       bowang0911/Mental_Health_FAQ                 — questions (information)        [MIT]

Exact duplicates (normalised text) are removed.  Long posts are kept whole up to 600 characters
(the first sentences carry the intent).  Deterministic (seed 13).

Run:  python eval/datasets/intent/build_pool.py   →  data/eval/intent/pool.jsonl
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "eval" / "intent" / "pool.jsonl"
SEED = 13
SIZES = {"amod": 1200, "ed": 1400, "dd": 700, "faq": 400}


def _norm(t: str) -> str:
    t = t.replace("�", "'")        # U+FFFD = a mis-decoded apostrophe in the Amod source
    return re.sub(r"\s+", " ", t).strip()


def _first_utterance_dd(row) -> str | None:
    for key in ("utterances", "dialog", "dialogue", "turns"):
        if key in row and row[key]:
            v = row[key][0]
            return v if isinstance(v, str) else v.get("text") if isinstance(v, dict) else None
    return None


def load_sources() -> dict[str, list[str]]:
    from datasets import load_dataset
    out: dict[str, list[str]] = {}

    amod = load_dataset("Amod/mental_health_counseling_conversations", split="train")
    out["amod"] = [r["Context"] for r in amod]

    ed = load_dataset("Estwld/empathetic_dialogues_llm", split="train")
    out["ed"] = [r["conversations"][0]["content"] for r in ed if r["conversations"]]

    dd = load_dataset("OpenRL/daily_dialog", split="train")
    out["dd"] = [_detokenize(u) for u in (_first_utterance_dd(r) for r in dd) if u]

    faq = load_dataset("bowang0911/Mental_Health_FAQ", "queries", split="train")
    out["faq"] = [r["text"] for r in faq]
    return out


def _detokenize(t: str) -> str:
    """DailyDialog is whitespace-tokenised ('Jim , how about it ?') — restore normal spacing."""
    t = re.sub(r"\s+([,.?!;:])", r"\1", t)
    t = re.sub(r"\s*'\s*(s|t|m|re|ve|ll|d)\b", r"'\1", t)
    t = re.sub(r"([.?!])(?=[A-Z])", r"\1 ", t)
    return _norm(t)


def build() -> list[dict]:
    rng = random.Random(SEED)
    seen, pool = set(), []
    for source, texts in load_sources().items():
        uniq = []
        for t in texts:
            t = _norm(str(t))
            key = t.lower()
            if 3 <= len(t) and key not in seen:
                seen.add(key)
                uniq.append(t[:600])
        rng.shuffle(uniq)
        for t in uniq[: SIZES[source]]:
            pool.append({"id": hashlib.sha1(t.encode()).hexdigest()[:12], "source": source, "text": t})
    rng.shuffle(pool)
    return pool


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pool = build()
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for r in pool:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print(len(pool), Counter(r["source"] for r in pool))
