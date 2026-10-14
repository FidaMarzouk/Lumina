# ── data/pain_points.py ───────────────────────────────────────────────────────
# HealthMind — Pain Point Taxonomy
#
# 15 mental health labels derived from dataset analysis.
# Maps to 6 macro groups ordered by priority.
# Consumed by: nlp_engine.py
# ──────────────────────────────────────────────────────────────────────────────

# Zero-shot classification candidate labels
PAIN_POINT_LABELS = [
    "anxiety and panic attacks",
    "depression and hopelessness",
    "loneliness and social isolation",
    "trauma and abuse",
    "relationship and family issues",
    "low self-worth and self-esteem",
    "suicidal thoughts and self-harm",
    "sleep problems and exhaustion",
    "work stress and burnout",
    "academic pressure and school stress",
    "anger and emotional dysregulation",
    "intrusive thoughts and paranoia",
    "mood disorders and emotional instability",
    "physical symptoms of stress",
    "seeking therapy and professional help",
]

# Maps each pain point label to its macro group
MACRO_MAP = {
    "anxiety and panic attacks"               : "anxiety & fear",
    "depression and hopelessness"             : "emotional distress",
    "loneliness and social isolation"         : "social & relationships",
    "trauma and abuse"                        : "trauma & crisis",
    "relationship and family issues"          : "social & relationships",
    "low self-worth and self-esteem"          : "emotional distress",
    "suicidal thoughts and self-harm"         : "trauma & crisis",
    "sleep problems and exhaustion"           : "life stressors",
    "work stress and burnout"                 : "life stressors",
    "academic pressure and school stress"     : "life stressors",
    "anger and emotional dysregulation"       : "social & relationships",
    "intrusive thoughts and paranoia"         : "anxiety & fear",
    "mood disorders and emotional instability": "emotional distress",
    "physical symptoms of stress"             : "anxiety & fear",
    "seeking therapy and professional help"   : "help seeking",
}

# When multiple macros match, the highest priority one wins
MACRO_PRIORITY = [
    "trauma & crisis",
    "anxiety & fear",
    "emotional distress",
    "social & relationships",
    "life stressors",
    "help seeking",
]

# Physical phrases that signal anxiety even when the model scores below threshold
SYMPTOM_BOOST = {
    "anxiety and panic attacks": [
        "heart races", "can't breathe", "chest tight",
        "heart pounding", "shortness of breath",
    ],
}
