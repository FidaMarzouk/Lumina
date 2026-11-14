# ── nlp_engine.py ─────────────────────────────────────────────────────────────
# Lumina — Text Understanding Engine
#
# Describes WHAT the user wrote:
#   - mental health entities mentioned (spaCy EntityRuler + biomedical NER fallback)
#   - intent — WHY they are writing (trained classifier, see nlp/intent.py)
#
# Pain points are no longer classified here (Q1, docs/evaluation.md): the zero-shot NLI labels were noise —
# 91% of small talk got one, and "physical symptoms of stress" scored a median 0.45 on every message.  The
# themes of a conversation now come from the LLM-written session summary (lumina/memory/episodes.py).
#   - clean tokens for downstream use
#
# Public function:
#   analyze_message(text: str) -> dict
#
# Crisis risk and prompt injection are NOT assessed here: lumina/safety does that,
# model-first, before this engine runs.  The phrase lists that used to live here
# (crisis keywords, method phrases, injection phrases, intent heuristics) were removed.
# ──────────────────────────────────────────────────────────────────────────────

import re
import string

from spacy.lang.en.stop_words import STOP_WORDS as _SPACY_STOP_WORDS

from ..config import (
    NER_MODEL,
    NER_CONFIDENCE,
)

from .lexicons import (
    MH_PATTERNS,
    NER_FALSE_POSITIVES,
)
from . import intent as _intent
from .models import lazy_pipeline, lazy_spacy


# ── Model handles ─────────────────────────────────────────────────────────────
# Same models / arguments as before, but created on first use (see models.py);
# the API server loads them at start-up through models.warm_up().

nlp_spacy         = lazy_spacy("en_core_web_sm", MH_PATTERNS)      # + EntityRuler(MH_PATTERNS)

ner_model         = lazy_pipeline("ner", model=NER_MODEL, aggregation_strategy="first")


# ── Mental health stopwords ───────────────────────────────────────────────────

_MH_NOISE = {
    "feel", "feeling", "felt", "like", "know", "think", "really",
    "want", "need", "make", "say", "said", "go", "get", "got",
    "people", "thing", "time", "day", "way", "year", "life", "lot",
    "little", "good", "bad", "right", "just", "much", "even",
    "still", "also", "well", "never", "always", "every",
}
_STOPWORDS = _SPACY_STOP_WORDS | _MH_NOISE      # == nlp_spacy.Defaults.stop_words | _MH_NOISE, without loading the model


# ── Text cleaning ─────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"[*_~`>#|\\]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    lowered = lowered.replace("\u2019", "").replace("\u2018", "").replace("'", "")
    lowered = lowered.translate(str.maketrans("", "", string.punctuation))
    doc = nlp_spacy(lowered)
    return [
        token.lemma_
        for token in doc
        if token.text not in _STOPWORDS
        and token.lemma_ not in _STOPWORDS
        and not token.is_space
        and token.is_alpha
        and len(token.text) > 2
    ]


# ── NER ───────────────────────────────────────────────────────────────────────

def extract_entities(text: str) -> dict[str, list[str]]:
    """
    Two-stage NER:
      Stage 1 — Rule-based (spaCy EntityRuler with MH_PATTERNS).
                Exact match on curated mental health vocabulary.
                Zero false positives on known terms.

      Stage 2 — ML fallback (d4data/biomedical-ner-all).
                Only runs when rule-based finds nothing.
                Catches terms not in the pattern list.
    """
    result: dict[str, list[str]] = {
        "SYMPTOM":          [],
        "DISORDER":         [],
        "MEDICATION":       [],
        "THERAPY":          [],
        "CRISIS_SIGNAL":    [],
        "EMOTION_STATE":    [],
        "COPING_STRATEGY":  [],
        "SUPPORT_RESOURCE": [],
    }

    doc  = nlp_spacy(text.lower()[:512])
    seen: set[str] = set()

    for ent in doc.ents:
        word  = ent.text.strip()
        label = ent.label_
        if label in result and len(word) >= 3 and word not in seen:
            result[label].append(word)
            seen.add(word)

    if not any(result.values()):
        ml_label_map = {
            "Sign_symptom":     "SYMPTOM",
            "Disease_disorder": "DISORDER",
            "Medication":       "MEDICATION",
            "Duration":         "SYMPTOM",
        }
        ml_results = ner_model(str(text))
        for r in ml_results:
            word     = r["word"].lower().strip()
            ml_label = r["entity_group"]
            score    = r["score"]
            mapped   = ml_label_map.get(ml_label)
            if (
                score >= NER_CONFIDENCE
                and mapped
                and len(word) >= 3
                and word not in NER_FALSE_POSITIVES
                and word not in seen
            ):
                result[mapped].append(word)
                seen.add(word)

    return result


# ── Intent classification ─────────────────────────────────────────────────────

def classify_intent(text: str) -> tuple[str, float, list | None]:
    """(intent, confidence, top2_if_ambiguous) from the trained classifier (nlp/intent.py)."""
    return _intent.classify(text)


# ── Public function ───────────────────────────────────────────────────────────

def analyze_message(text: str) -> dict:
    """
    Full text understanding pipeline for mental health conversations.
    This is the ONLY function other modules should call from this file.

    Parameters
    ----------
    text : str
        Raw user message exactly as typed.

    Returns
    -------
    dict with keys:
        cleaned_text       (str)
        tokens             (list[str])
        entities           (dict[str, list[str]])
        intent             (str)
            One of lumina/nlp/intent_taxonomy.INTENT_NAMES.
        intent_confidence  (float)
        intent_ambiguous   (list[dict] | None)

    Crisis risk and prompt injection are NOT assessed here — see lumina/safety.
    """
    cleaned = clean_text(text)

    entities           = extract_entities(cleaned)
    intent, conf, top2 = classify_intent(cleaned)
    tokens             = tokenize(cleaned)

    return {
        "cleaned_text"     : cleaned,
        "tokens"           : tokens,
        "entities"         : entities,
        "intent"           : intent,
        "intent_confidence": conf,
        "intent_ambiguous" : top2,
    }