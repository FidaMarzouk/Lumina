# ── nlp_engine.py ─────────────────────────────────────────────────────────────
# Lumina — Text Understanding Engine
#
# Describes WHAT the user wrote:
#   - mental health entities mentioned (spaCy EntityRuler + biomedical NER fallback)
#   - pain points (zero-shot NLI over the pain-point taxonomy)
#   - intent — WHY they are writing (trained classifier, see nlp/intent.py)
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
    PAIN_MODEL,
    NER_MODEL,
    NER_CONFIDENCE,
    PAIN_THRESHOLD,
    PAIN_TOP_K,
)

from .lexicons import (
    MH_PATTERNS,
    PAIN_POINT_LABELS, MACRO_MAP, MACRO_PRIORITY, SYMPTOM_BOOST,
    NER_FALSE_POSITIVES,
)
from . import intent as _intent
from .models import lazy_pipeline, lazy_spacy


# ── Model handles ─────────────────────────────────────────────────────────────
# Same models / arguments as before, but created on first use (see models.py);
# the API server loads them at start-up through models.warm_up().

nlp_spacy         = lazy_spacy("en_core_web_sm", MH_PATTERNS)      # + EntityRuler(MH_PATTERNS)

pain_classifier   = lazy_pipeline("zero-shot-classification", model=PAIN_MODEL)

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


# ── Pain point classification ─────────────────────────────────────────────────

def classify_pain_points(text: str) -> tuple[list[str], str]:
    """
    Zero-shot classification into 15 mental health pain point labels.
    Returns (pain_points, primary_macro).
    """
    classification = pain_classifier(
        text[:512],
        candidate_labels=PAIN_POINT_LABELS,
        multi_label=True,
    )

    pairs  = list(zip(classification["labels"], classification["scores"]))
    picked = [
        label for label, score in pairs
        if score >= PAIN_THRESHOLD
    ][:PAIN_TOP_K]

    # An empty result is a valid answer: forcing the top label onto every message (as before)
    # made "hi" look like it had a pain point, so the RAG gate and the SITUATION block always fired.
    text_lower = text.lower()
    for label, phrases in SYMPTOM_BOOST.items():
        if label not in picked and any(p in text_lower for p in phrases):
            picked.insert(0, label)
            picked = picked[:PAIN_TOP_K]

    if not picked:
        return [], "none"
    macros  = list(set(MACRO_MAP.get(pp, "help seeking") for pp in picked))
    primary = next((m for m in MACRO_PRIORITY if m in macros), macros[0])

    return picked, primary


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
        pain_points        (list[str])
        primary_macro      (str)
        intent             (str)
            One of lumina/nlp/intent_taxonomy.INTENT_NAMES.
        intent_confidence  (float)
        intent_ambiguous   (list[dict] | None)

    Crisis risk and prompt injection are NOT assessed here — see lumina/safety.
    """
    cleaned = clean_text(text)

    entities             = extract_entities(cleaned)
    pain_points, primary = classify_pain_points(cleaned)
    intent, conf, top2   = classify_intent(cleaned)
    tokens               = tokenize(cleaned)

    return {
        "cleaned_text"     : cleaned,
        "tokens"           : tokens,
        "entities"         : entities,
        "pain_points"      : pain_points,
        "primary_macro"    : primary,
        "intent"           : intent,
        "intent_confidence": conf,
        "intent_ambiguous" : top2,
    }