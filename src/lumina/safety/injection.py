"""Prompt-injection detection with a dedicated open classifier (no phrase lists).

Model: protectai/deberta-v3-base-prompt-injection-v2 (Apache-2.0).  Threshold tuned on a
held-out set (deepset/prompt-injections, not in the model's training data) plus benign
mental-health messages, to keep false positives on ordinary distress messages low.

The flag only changes the *tone* of the reply (calm redirect).  It never suppresses crisis
handling, and structural defences (server-built prompts, no client system roles, output
guard) do not depend on it.
"""

from __future__ import annotations

from ..config import INJECTION_MODEL, INJECTION_THRESHOLD
from ..nlp.models import lazy_pipeline

injection_classifier = lazy_pipeline(
    "text-classification", model=INJECTION_MODEL, tokenizer=INJECTION_MODEL,
    truncation=True, max_length=512, top_k=None,
)


def injection_probability(text: str) -> float:
    scores = injection_classifier(text[:2500])[0]
    by_label = {s["label"].upper(): s["score"] for s in scores}
    return float(by_label.get("INJECTION", 0.0))


def is_injection(text: str, threshold: float = INJECTION_THRESHOLD) -> bool:
    return injection_probability(text) >= threshold
