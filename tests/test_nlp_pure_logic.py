"""Rule-based parts of nlp_engine (no model needed). Importing the module does not load any model."""
import pytest

pytest.importorskip("spacy")

from lumina.nlp import nlp_engine as ne


def test_import_does_not_load_models():
    for h in (ne.nlp_spacy, ne.pain_classifier, ne.ner_model, ne._intent.intent_classifier, ne._intent.intent_embedder):
        assert not h.loaded


def test_clean_text():
    assert ne.clean_text("Hi **there** <b>x</b> see https://a.b/c  now") == "Hi there x see now"


def test_stopwords_include_spacy_defaults_and_domain_noise():
    assert {"the", "feel", "really"} <= ne._STOPWORDS


def test_nlp_engine_no_longer_decides_crisis_or_injection():
    for name in ("detect_crisis", "detect_crisis_subtype", "detect_injection"):
        assert not hasattr(ne, name)
