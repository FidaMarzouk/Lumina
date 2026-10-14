from lumina.nlp import lexicons as lx
from lumina.nlp.intent_taxonomy import INTENT_NAMES, INTENT_MAP, INTENT_LABELS


def test_pain_point_taxonomy_is_closed():
    assert set(lx.MACRO_MAP) == set(lx.PAIN_POINT_LABELS) and len(lx.PAIN_POINT_LABELS) == 15
    assert set(lx.MACRO_MAP.values()) == set(lx.MACRO_PRIORITY) and len(lx.MACRO_PRIORITY) == 6
    assert set(lx.SYMPTOM_BOOST) <= set(lx.PAIN_POINT_LABELS)


def test_strategy_map_only_uses_known_intents():
    intents = {i for i, _ in lx.STRATEGY_MAP}
    assert intents <= set(INTENT_NAMES) | {"crisis"}
    assert all(len(v) == 2 for v in lx.STRATEGY_MAP.values()) and len(lx.DEFAULT_STRATEGY) == 2


def test_intent_taxonomy_is_consistent_and_has_no_crisis_label():
    assert set(INTENT_MAP.values()) == set(INTENT_NAMES) and len(INTENT_LABELS) == len(INTENT_NAMES)
    assert "crisis" not in INTENT_NAMES and "injection" not in INTENT_NAMES


def test_phrase_based_safety_lists_are_gone():
    for name in ("CRISIS_KEYWORDS", "SELF_HARM_METHOD_KEYWORDS", "PROMPT_INJECTION_PATTERNS",
                 "CRISIS_FALSE_POSITIVE_PHRASES"):
        assert not hasattr(lx, name)
    assert all(isinstance(p, dict) and p for p in lx.MH_PATTERNS)
