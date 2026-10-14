# ── data/strategy_map.py ─────────────────────────────────────────────────────
# HealthMind — Response Strategy Map
#
# Maps (intent, emotion) → (tone instruction, what to avoid).
# Consumed by: empathy_engine.py
#
# Intent set (v2):
#   venting, seeking_advice, seeking_validation,
#   help_seeking, sharing_experience, crisis
# ──────────────────────────────────────────────────────────────────────────────

STRATEGY_MAP = {
    # ── Venting ───────────────────────────────────────────────────────────────
    ("venting", "sadness") : ("warm and validating",          "do not give advice or suggest solutions"),
    ("venting", "anger")   : ("calm and acknowledging",       "do not challenge, correct, or take sides"),
    ("venting", "fear")    : ("reassuring and grounding",     "do not minimize or rush to fix"),
    ("venting", "disgust") : ("non-judgmental and validating","do not question their reaction"),
    ("venting", "surprise"): ("gentle and curious",           "do not assume how they feel"),
    ("venting", "neutral") : ("gentle and open",              "follow their lead, do not push"),
    ("venting", "joy")     : ("warm and affirming",           "match their energy, do not over-analyze"),

    # ── Seeking advice ────────────────────────────────────────────────────────
    ("seeking_advice", "sadness") : ("practical and gentle",      "lead with empathy before advice"),
    ("seeking_advice", "fear")    : ("calm and structured",       "give clear steps, avoid overwhelming detail"),
    ("seeking_advice", "anger")   : ("steady and practical",      "acknowledge frustration before advising"),
    ("seeking_advice", "disgust") : ("measured and validating",   "acknowledge their reaction before advising"),
    ("seeking_advice", "surprise"): ("grounding and informative", "normalize before advising"),
    ("seeking_advice", "neutral") : ("clear and supportive",      "be direct but warm"),
    ("seeking_advice", "joy")     : ("encouraging and practical", "build on their motivation"),

    # ── Seeking validation ────────────────────────────────────────────────────
    ("seeking_validation", "fear")    : ("reassuring and normalizing", "do not give advice or diagnose"),
    ("seeking_validation", "sadness") : ("warm and affirming",         "do not minimize or reframe"),
    ("seeking_validation", "neutral") : ("calm and normalizing",       "do not over-reassure or dismiss"),
    ("seeking_validation", "disgust") : ("non-judgmental and steady",  "do not question why they feel that way"),
    ("seeking_validation", "anger")   : ("validating and grounding",   "do not challenge or explain away their anger"),
    ("seeking_validation", "surprise"): ("gentle and normalizing",     "normalize their reaction without over-explaining"),
    ("seeking_validation", "joy")     : ("affirming and warm",         "validate without deflating their mood"),

    # ── Help seeking ──────────────────────────────────────────────────────────
    ("help_seeking", "neutral") : ("informative and warm",       "give useful information without lecturing"),
    ("help_seeking", "fear")    : ("reassuring and informative", "normalize help-seeking before informing"),
    ("help_seeking", "sadness") : ("warm and informative",       "validate before informing"),
    ("help_seeking", "anger")   : ("steady and informative",     "acknowledge frustration before directing them"),
    ("help_seeking", "disgust") : ("calm and practical",         "do not lecture, just point to resources"),
    ("help_seeking", "surprise"): ("grounding and informative",  "normalize that needing help is okay"),
    ("help_seeking", "joy")     : ("encouraging and informative","affirm their initiative in seeking help"),

    # ── Sharing experience ────────────────────────────────────────────────────
    # Kept but only reached when confidence >= 0.70 on a calm past narrative
    ("sharing_experience", "sadness") : ("reflective and normalizing", "reflect back, do not reframe or fix"),
    ("sharing_experience", "neutral") : ("engaged and curious",        "show genuine interest"),
    ("sharing_experience", "fear")    : ("validating and steady",      "normalize their experience"),
    ("sharing_experience", "anger")   : ("calm and reflective",        "acknowledge without re-inflaming"),
    ("sharing_experience", "surprise"): ("curious and engaged",        "let them lead, do not over-interpret"),
    ("sharing_experience", "joy")     : ("warm and celebratory",       "affirm their growth or reflection"),

    # ── Crisis ────────────────────────────────────────────────────────────────
    # Always uses this entry regardless of emotion
    ("crisis", "any") : ("calm, direct, and safety-focused", "do not leave them without a next step"),
}

# Fallback when (intent, emotion) combo is not in STRATEGY_MAP
DEFAULT_STRATEGY = ("warm and supportive", "do not make assumptions about how they feel")


# ── Intents added with the trained classifier (same tone for every emotion) ─────
for _emotion in ("sadness", "anger", "fear", "disgust", "surprise", "neutral", "joy"):
    STRATEGY_MAP[("casual", _emotion)] = ("friendly, light and brief", "do not bring up mental health unprompted")
    STRATEGY_MAP[("information", _emotion)] = ("clear, warm and factual", "do not diagnose or give personal medical advice")
