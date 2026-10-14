"""Choose the retrieval relevance threshold (MIN_SIMILARITY) from data.

On-topic:  98 mental-health FAQ questions (bowang0911/Mental_Health_FAQ) — the knowledge base should answer them.
Off-topic: 300 everyday small-talk openers (DailyDialog) — nothing should be retrieved for them.
For each message, the top-1 cosine similarity against the v1 index is computed; the threshold that
maximises (on-topic kept − off-topic kept) is reported, along with the rates at candidate thresholds.

This sets a floor that blocks irrelevant context; it is not a retrieval-quality (Recall@k) evaluation.
Output: eval/reports/retrieval_threshold.{json,md}
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main() -> dict:
    from datasets import load_dataset
    from lumina.rag.retriever import MentalHealthRetriever

    on = [r["text"] for r in load_dataset("bowang0911/Mental_Health_FAQ", "queries", split="train")]
    dd = load_dataset("OpenRL/daily_dialog", split="train")
    off = [d["dialog"][0].strip() for d in dd]
    off = random.Random(13).sample(off, 300)

    ret = MentalHealthRetriever()
    def top1(texts):
        return np.array([ret.query(t, top_k=1, min_similarity=-1.0)[0]["score"] for t in texts])
    s_on, s_off = top1(on), top1(off)

    rows, best = [], None
    for t in np.round(np.arange(0.20, 0.71, 0.05), 2):
        kept_on, kept_off = float((s_on >= t).mean()), float((s_off >= t).mean())
        rows.append({"threshold": float(t), "on_topic_kept": round(kept_on, 3), "off_topic_kept": round(kept_off, 3)})
        if best is None or kept_on - kept_off > best[1]:
            best = (float(t), kept_on - kept_off)
    out = {"n_on_topic": len(on), "n_off_topic": len(off),
           "on_topic_top1_median": round(float(np.median(s_on)), 3),
           "off_topic_top1_median": round(float(np.median(s_off)), 3),
           "best_threshold": best[0], "sweep": rows}
    rep = ROOT / "eval" / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "retrieval_threshold.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines = ["# Retrieval relevance threshold", "",
             f"Top-1 cosine similarity against index v1. On-topic (mental-health FAQ, n={len(on)}): median "
             f"{out['on_topic_top1_median']}; off-topic (small talk, n={len(off)}): median {out['off_topic_top1_median']}. "
             f"Best separation at **{best[0]}**.", "",
             "| Threshold | On-topic kept | Off-topic kept |", "|---|---|---|"]
    lines += [f"| {r['threshold']} | {r['on_topic_kept']} | {r['off_topic_kept']} |" for r in rows]
    print("\n".join(lines))
    return out


if __name__ == "__main__":
    main()
