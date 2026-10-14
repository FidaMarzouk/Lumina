# ── feeling_engine.py ─────────────────────────────────────────────────────────
# HealthMind — Emotional Understanding Engine
#
# Responsible for understanding HOW the user feels:
#   - Overall sentiment (positive / negative / neutral)
#   - Specific emotion (sadness, fear, anger, joy, etc.)
#   - Full score distributions for nuanced prompt building
#
# Public function:
#   analyze_feeling(text: str) -> dict
#
# Does NOT handle text structure or entities — see nlp_engine.py
# Does NOT build prompts — see empathy_engine.py
# Does NOT call the LLM — see llm_client.py
#
# Why sentiment and emotion are together:
#   Both answer "how does the user feel?"
#   They use similar model types and cross-validate each other.
#   If sentiment = negative but emotion = joy, something is ambiguous.
#   Keeping them together makes that visible and debuggable.
#
# Dependencies:
#   pip install transformers torch
# ──────────────────────────────────────────────────────────────────────────────

from ..config import (
    SENTIMENT_MODEL,
    EMOTION_MODEL,
    EMOTION_THRESHOLD,
)
from .models import lazy_pipeline


# ── Model handles ─────────────────────────────────────────────────────────────
# Created on first use (loaded at API start-up via models.warm_up()).
# top_k=None returns all label scores — needed for full distributions.

sentiment_model = lazy_pipeline(
    "text-classification",
    model=SENTIMENT_MODEL,
    tokenizer=SENTIMENT_MODEL,
    truncation=True,
    max_length=512,
    top_k=None,
)

emotion_model = lazy_pipeline(
    "text-classification",
    model=EMOTION_MODEL,
    tokenizer=EMOTION_MODEL,
    truncation=True,
    max_length=512,
    top_k=None,
)


# ── Emotion label mapping ─────────────────────────────────────────────────────
# j-hartmann model returns these 7 labels.
# Mapped to response strategies in empathy_engine.py.

EMOTION_LABELS = {
    "sadness",
    "fear",
    "anger",
    "joy",
    "surprise",
    "disgust",
    "neutral",
}

# Sentiment label normalization
# cardiffnlp model returns: "positive", "neutral", "negative"
# Already clean — no mapping needed


# ── Internal functions ────────────────────────────────────────────────────────

def analyze_sentiment(text: str) -> tuple[str, float, dict[str, float]]:
    """
    Run sentiment analysis on raw text.
    Uses cardiffnlp/twitter-roberta-base-sentiment-latest.
    Chosen because it handles informal language well — important for Reddit-style text.

    Returns:
        sentiment   — "positive" | "negative" | "neutral"
        score       — confidence for the top label (0.0–1.0)
        all_scores  — full distribution e.g. {"negative": 0.91, "neutral": 0.07, "positive": 0.02}
    """
    # Truncate to safe length before model call
    truncated = text[:1800]

    results    = sentiment_model(truncated)[0]  # top_k=None returns list
    all_scores = {r["label"].lower(): round(r["score"], 4) for r in results}
    top_label  = max(all_scores, key=all_scores.get)
    top_score  = all_scores[top_label]

    return top_label, top_score, all_scores


def detect_emotion(text: str) -> tuple[str, float, dict[str, float]]:
    """
    Run emotion detection on raw text.
    Uses j-hartmann/emotion-english-distilroberta-base.
    Returns 7-class emotion label with full score distribution.

    If top confidence < EMOTION_THRESHOLD (default 0.55):
        Returns "neutral" as a safe fallback — signal is too ambiguous
        to act on with confidence.

    Returns:
        emotion     — one of: sadness, fear, anger, joy, surprise, disgust, neutral
        score       — confidence for the top label (0.0–1.0)
        all_scores  — full distribution e.g. {"sadness": 0.88, "fear": 0.07, ...}
    """
    truncated = text[:1800]

    results    = emotion_model(truncated)[0]
    all_scores = {r["label"].lower(): round(r["score"], 4) for r in results}
    top_label  = max(all_scores, key=all_scores.get)
    top_score  = all_scores[top_label]

    # Low confidence — default to neutral rather than guessing
    if top_score < EMOTION_THRESHOLD:
        return "neutral", top_score, all_scores

    return top_label, top_score, all_scores


# ── Public function ───────────────────────────────────────────────────────────

def analyze_feeling(text: str) -> dict:
    """
    Full emotional analysis of a user message.
    This is the ONLY function other modules should call from this file.

    Runs sentiment and emotion analysis together.
    Returns combined output for use by empathy_engine.py.

    Parameters
    ----------
    text : str
        Raw user message exactly as typed.
        Does not need to be pre-cleaned — models handle raw text well.

    Returns
    -------
    dict with keys:

        sentiment           (str)
            Overall tone: "positive" | "negative" | "neutral"

        sentiment_score     (float)
            Confidence for the sentiment label (0.0–1.0).

        sentiment_scores    (dict[str, float])
            Full distribution across all sentiment labels.
            Example: {"negative": 0.91, "neutral": 0.07, "positive": 0.02}

        emotion             (str)
            Dominant emotion: one of sadness, fear, anger,
            joy, surprise, disgust, neutral.
            Returns "neutral" when confidence < EMOTION_THRESHOLD.

        emotion_score       (float)
            Confidence for the emotion label (0.0–1.0).

        emotion_scores      (dict[str, float])
            Full distribution across all 7 emotion labels.
            Example: {"sadness": 0.88, "fear": 0.07, "neutral": 0.03, ...}

        emotion_ambiguous   (bool)
            True when emotion confidence < EMOTION_THRESHOLD.
            Signals to empathy_engine.py that the emotional signal
            is weak and a conservative response strategy should be used.

    Example output:
        {
            "sentiment":         "negative",
            "sentiment_score":   0.91,
            "sentiment_scores":  {"negative": 0.91, "neutral": 0.07, "positive": 0.02},
            "emotion":           "sadness",
            "emotion_score":     0.88,
            "emotion_scores":    {"sadness": 0.88, "fear": 0.07, "anger": 0.03,
                                  "neutral": 0.01, "joy": 0.01},
            "emotion_ambiguous": False
        }
    """
    sentiment, sentiment_score, sentiment_scores = analyze_sentiment(text)
    emotion,   emotion_score,   emotion_scores   = detect_emotion(text)

    return {
        "sentiment"        : sentiment,
        "sentiment_score"  : sentiment_score,
        "sentiment_scores" : sentiment_scores,
        "emotion"          : emotion,
        "emotion_score"    : emotion_score,
        "emotion_scores"   : emotion_scores,
        "emotion_ambiguous": emotion_score < EMOTION_THRESHOLD,
    }
