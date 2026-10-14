"""Trained suicide-risk classifier — the high-recall model layer for first-person distress.

Model: vibhorag101/roberta-base-suicide-prediction-phr (MIT), fine-tuned on Reddit posts
(r/SuicideWatch vs. other subreddits).  Its labels come from subreddit membership, i.e.
they are noisy; it is therefore evaluated on an independent, clinically labelled set
(C-SSRS-annotated posts) and its thresholds are tuned on a dev split — see eval/.

Applied to the current message AND to the recent user turns joined together, so risk
expressed across several short messages is still visible.
"""

from __future__ import annotations

from ..config import RISK_MODEL
from ..nlp.models import lazy_pipeline

risk_classifier = lazy_pipeline(
    "text-classification", model=RISK_MODEL, tokenizer=RISK_MODEL,
    truncation=True, max_length=512, top_k=None,
)

_POSITIVE = {"suicidal", "suicide", "label_1", "1", "positive", "risk"}


def risk_probability(text: str) -> float:
    """P(suicide risk) in [0, 1]."""
    scores = risk_classifier(text[:2500])[0]
    by_label = {s["label"].lower(): s["score"] for s in scores}
    positive = [v for k, v in by_label.items() if k in _POSITIVE]
    if positive:
        return float(max(positive))
    negative = [v for k, v in by_label.items() if k.startswith("non") or k in {"label_0", "0", "negative"}]
    return float(1.0 - max(negative)) if negative else 0.0
