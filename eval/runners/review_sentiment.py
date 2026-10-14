"""Sentiment model validity on app reviews: transformer (the model Lumina uses) vs VADER (the v0 method).

Weak labels from star ratings: 1–2★ → negative, 3★ → neutral, 4–5★ → positive.  Stars are a proxy,
not ground truth (people write mixed reviews), so the report shows agreement, the specific failure
the v0 analysis suffered (1★ reviews labelled positive), and macro-F1.
Output: eval/reports/review_sentiment.{json,md}
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from lumina.config import SENTIMENT_MODEL
from lumina.nlp.models import lazy_pipeline

ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / "data" / "market" / "processed" / "reviews.jsonl"
REPORT = ROOT / "eval" / "reports"


def star_label(r: int) -> str:
    return "negative" if r <= 2 else "neutral" if r == 3 else "positive"


def main() -> dict:
    from sklearn.metrics import f1_score
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    df = pd.read_json(REVIEWS, lines=True)
    df = df[~df["dup_of_previous"] & (df["language"] == "english")].copy()
    text = (df["title"].fillna("") + ". " + df["text"].fillna("")).tolist()
    df["stars"] = df["rating"].map(star_label)

    vader = SentimentIntensityAnalyzer()
    comp = np.array([vader.polarity_scores(t)["compound"] for t in text])
    df["vader"] = np.where(comp >= 0.05, "positive", np.where(comp <= -0.05, "negative", "neutral"))

    pipe = lazy_pipeline("text-classification", model=SENTIMENT_MODEL, tokenizer=SENTIMENT_MODEL,
                         truncation=True, max_length=512, top_k=None)
    preds = []
    for i in range(0, len(text), 32):
        for scores in pipe(text[i:i + 32]):
            preds.append(max(scores, key=lambda s: s["score"])["label"].lower())
    df["transformer"] = preds

    out = {"n": int(len(df)), "label_counts_stars": df["stars"].value_counts().to_dict(), "methods": {}}
    for m in ("vader", "transformer"):
        one_star = df[df["rating"] == 1]
        out["methods"][m] = {
            "agreement_with_stars": round(float((df[m] == df["stars"]).mean()), 3),
            "macro_f1_vs_stars": round(f1_score(df["stars"], df[m], average="macro"), 3),
            "one_star_labelled_positive": round(float((one_star[m] == "positive").mean()), 3),
            "five_star_labelled_negative": round(float((df[df["rating"] == 5][m] == "negative").mean()), 3),
        }
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "review_sentiment.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines = ["# Review sentiment — VADER (v0 method) vs transformer", "",
             f"English unique reviews: n={out['n']}. Weak labels from stars (1–2 neg, 3 neutral, 4–5 pos).", "",
             "| Method | Agreement with stars | Macro-F1 vs stars | 1★ labelled positive | 5★ labelled negative |",
             "|---|---|---|---|---|"]
    for m, v in out["methods"].items():
        lines.append(f"| {m} | {v['agreement_with_stars']} | {v['macro_f1_vs_stars']} | "
                     f"{v['one_star_labelled_positive']} | {v['five_star_labelled_negative']} |")
    print("\n".join(lines))
    return out


if __name__ == "__main__":
    main()
