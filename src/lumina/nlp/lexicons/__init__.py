# ── lexicons/__init__.py ──────────────────────────────────────────────────────
# Lookup tables used by nlp_engine (entity patterns, pain-point labels) and
# empathy_engine (response strategy map).
#
# Intent definitions live in lumina/nlp/intent_taxonomy.py.  Crisis and injection
# detection live in lumina/safety (model-based) — there are no phrase lists for them.
# ──────────────────────────────────────────────────────────────────────────────

from .mh_patterns import MH_PATTERNS, NER_FALSE_POSITIVES
from .pain_points import PAIN_POINT_LABELS, MACRO_MAP, MACRO_PRIORITY, SYMPTOM_BOOST
from .strategy_map import STRATEGY_MAP, DEFAULT_STRATEGY
from ..intent_taxonomy import INTENT_LABELS, INTENT_MAP


__all__ = [
    "MH_PATTERNS", "NER_FALSE_POSITIVES",
    "PAIN_POINT_LABELS", "MACRO_MAP", "MACRO_PRIORITY", "SYMPTOM_BOOST",
    "INTENT_LABELS", "INTENT_MAP",
    "STRATEGY_MAP", "DEFAULT_STRATEGY",
]
