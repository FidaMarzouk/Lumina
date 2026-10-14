"""Intent classification with a trained classifier (sentence embeddings + logistic regression).

Replaces the phrase heuristics + bart-large-mnli zero-shot.  The model is trained and
evaluated by eval/runners/intent_classifier.py; its metrics and training data are recorded
in models/intent/<version>/model_card.json and eval/reports/intent_classifier.json.

Low-confidence predictions are reported as ambiguous (top-2) so the prompt can stay open
instead of committing to a guess.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np

from ..config import INTENT_AMBIGUOUS_BELOW, INTENT_MODEL_DIR
from .models import LazyModel


@lru_cache(maxsize=1)
def model_card() -> dict:
    return json.loads((INTENT_MODEL_DIR / "model_card.json").read_text(encoding="utf-8"))


def _load_classifier():
    import joblib
    return joblib.load(INTENT_MODEL_DIR / "classifier.joblib")


def _load_embedder():
    from sentence_transformers import SentenceTransformer
    from .models import _device
    return SentenceTransformer(model_card()["embedder"], device="cuda" if _device() == 0 else "cpu")


intent_classifier = LazyModel("intent:classifier", _load_classifier)
intent_embedder = LazyModel("intent:embedder", _load_embedder)


def classify(text: str) -> tuple[str, float, list[dict] | None]:
    """Return (intent, confidence, top2_if_ambiguous)."""
    vec = intent_embedder.encode([text[:1000]], normalize_embeddings=True, show_progress_bar=False)
    probs = intent_classifier.predict_proba(vec)[0]
    classes = intent_classifier.classes_
    order = np.argsort(probs)[::-1]
    top, second = order[0], order[1]
    conf = float(probs[top])
    ambiguous = None
    if conf < INTENT_AMBIGUOUS_BELOW:
        ambiguous = [{"intent": str(classes[i]), "confidence": round(float(probs[i]), 3)} for i in (top, second)]
    return str(classes[top]), round(conf, 3), ambiguous
