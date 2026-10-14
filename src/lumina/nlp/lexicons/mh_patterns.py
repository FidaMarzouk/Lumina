# ── data/mh_patterns.py ───────────────────────────────────────────────────────
# HealthMind — Mental Health Entity Patterns
#
# Rule-based exact-match patterns for spaCy EntityRuler.
# Consumed by: nlp_engine.py
#
# Each pattern is a dict with "label" and "pattern" keys.
# Multi-word terms are matched as full phrases.
# Single ambiguous words are avoided — only unambiguous terms are listed.
# ──────────────────────────────────────────────────────────────────────────────

MH_PATTERNS = [

    # ── SYMPTOM ───────────────────────────────────────────────────────────────
    *[{"label": "SYMPTOM", "pattern": p} for p in [
        "anxiety", "panic attack", "panic attacks", "depression", "insomnia",
        "fatigue", "burnout", "burn out", "hopelessness", "worthlessness",
        "dissociation", "dissociating", "flashback", "flashbacks",
        "intrusive thoughts", "intrusive thought", "hypervigilance",
        "emotional numbness", "numbness", "brain fog", "mood swings",
        "mood swing", "irritability", "social withdrawal", "overthinking",
        "rumination", "catastrophizing", "racing thoughts", "chest tightness",
        "shortness of breath", "trembling", "shaking", "derealization",
        "depersonalization", "sleep problems", "nightmares", "night sweats",
        "loss of appetite", "overeating", "emotional eating", "crying spells",
        "loss of interest", "anhedonia", "concentration issues", "forgetfulness",
        "can't sleep", "cannot sleep", "trouble sleeping",
        "trouble falling asleep", "can't fall asleep",
        "difficulty sleeping", "difficulty falling asleep",
    ]],

    # ── DISORDER ──────────────────────────────────────────────────────────────
    # Multi-word phrases only — no ambiguous single words
    *[{"label": "DISORDER", "pattern": p} for p in [
        "post-traumatic stress disorder", "post traumatic stress disorder",
        "obsessive compulsive disorder", "obsessive-compulsive disorder",
        "attention deficit hyperactivity disorder",
        "bipolar disorder", "borderline personality disorder",
        "generalized anxiety disorder", "social anxiety disorder",
        "social anxiety", "panic disorder", "major depressive disorder",
        "eating disorder", "binge eating disorder",
        "alcohol use disorder", "substance use disorder",
        "autism spectrum disorder", "seasonal affective disorder",
        "dissociative identity disorder",
        # Safe abbreviations — long enough to be unambiguous
        "ptsd", "ocd", "adhd", "bpd", "mdd", "gad", "asd",
        "schizophrenia", "psychosis", "agoraphobia",
        "anorexia", "bulimia", "dysthymia", "cyclothymia",
    ]],

    # ── THERAPY ───────────────────────────────────────────────────────────────
    *[{"label": "THERAPY", "pattern": p} for p in [
        "cognitive behavioral therapy", "cognitive-behavioral therapy",
        "dialectical behavior therapy", "dialectical behaviour therapy",
        "eye movement desensitization and reprocessing",
        "acceptance and commitment therapy",
        "mindfulness-based cognitive therapy",
        "mindfulness-based stress reduction",
        "psychodynamic therapy", "humanistic therapy",
        "narrative therapy", "compassion focused therapy",
        "schema therapy", "interpersonal therapy",
        "solution-focused therapy",
        "psychotherapy", "talk therapy", "group therapy",
        "family therapy", "exposure therapy", "trauma therapy",
        "somatic therapy", "art therapy", "music therapy",
        # Safe abbreviations
        "cbt", "dbt", "emdr", "mbct", "mbsr",
    ]],

    # ── MEDICATION ────────────────────────────────────────────────────────────
    *[{"label": "MEDICATION", "pattern": p} for p in [
        "antidepressant", "antidepressants", "ssri", "ssris", "snri", "snris",
        "sertraline", "zoloft", "fluoxetine", "prozac",
        "escitalopram", "lexapro", "citalopram", "celexa",
        "paroxetine", "paxil", "venlafaxine", "effexor",
        "duloxetine", "cymbalta", "bupropion", "wellbutrin",
        "mirtazapine", "remeron", "trazodone",
        "benzodiazepine", "benzodiazepines",
        "lorazepam", "ativan", "alprazolam", "xanax",
        "clonazepam", "klonopin", "diazepam", "valium",
        "quetiapine", "seroquel", "aripiprazole", "abilify",
        "lithium", "lamotrigine", "lamictal", "valproate", "depakote",
        "buspirone", "buspar", "hydroxyzine", "vistaril",
        "melatonin", "zolpidem", "ambien",
        "methylphenidate", "ritalin", "adderall",
        "antipsychotic", "antipsychotics",
        "mood stabilizer", "mood stabilizers",
        "sleep aid", "sleep aids",
    ]],

    # ── CRISIS_SIGNAL ─────────────────────────────────────────────────────────
    # Exact phrases only — never single words
    *[{"label": "CRISIS_SIGNAL", "pattern": p} for p in [
        "suicidal thoughts", "suicidal ideation", "want to die",
        "wanting to die", "wish i was dead", "wish i were dead",
        "end my life", "ending my life", "no reason to live",
        "no will to live", "don't want to be here",
        "dont want to be here", "not want to live",
        "hurt myself", "hurting myself", "kill myself",
        "self-harm", "self harm", "cutting myself",
        "suicide attempt", "mental health crisis",
        "nervous breakdown", "psychiatric ward",
        "inpatient treatment", "killing myself",
        "ending my life", "wanting to die",
        "thought about suicide", "thinking about suicide",
        "thinking about killing",
    ]],

    # ── EMOTION_STATE ─────────────────────────────────────────────────────────
    *[{"label": "EMOTION_STATE", "pattern": p} for p in [
        "overwhelmed", "stressed out", "burned out",
        "anxious", "nervous", "terrified", "fearful",
        "panicking", "panicked", "worried",
        "hopeless", "lonely", "isolated", "empty",
        "numb", "disconnected", "depressed",
        "frustrated", "ashamed", "guilty",
        "embarrassed", "worthless", "useless",
        "exhausted", "drained", "hopeful",
        "grateful", "relieved", "motivated",
        "calm", "peaceful", "content",
    ]],

    # ── COPING_STRATEGY ───────────────────────────────────────────────────────
    *[{"label": "COPING_STRATEGY", "pattern": p} for p in [
        "meditation", "mindfulness", "deep breathing",
        "breathing exercises", "journaling", "gratitude journal",
        "grounding", "grounding techniques", "box breathing",
        "progressive muscle relaxation", "yoga", "self-care",
        "positive affirmations", "sleep hygiene",
        "daily routine", "digital detox", "nature walk",
        "cold shower", "distraction",
    ]],

    # ── SUPPORT_RESOURCE ──────────────────────────────────────────────────────
    *[{"label": "SUPPORT_RESOURCE", "pattern": p} for p in [
        "therapist", "psychologist", "psychiatrist",
        "counselor", "counsellor", "social worker",
        "mental health professional", "crisis line",
        "crisis hotline", "suicide hotline",
        "crisis text line", "samaritans", "nami",
        "betterhelp", "talkspace", "support group",
        "peer support", "online therapy", "telehealth",
        "emergency room", "psychiatric ward",
        "inpatient", "outpatient", "rehab", "988",
    ]],
]


# ── NER false positives ───────────────────────────────────────────────────────
# Generic words the biomedical NER model tags as entities but that carry no specific
# clinical meaning; dropped from its output.  (Moved here from the deleted intent_labels.py.)
NER_FALSE_POSITIVES = {
    "health", "disease", "symptom", "symptoms", "pain",
    "doctor", "disorder", "disorders", "condition", "conditions",
    "problem", "problems", "issue", "issues", "feeling", "feelings",
    "thing", "things", "mental", "emotional", "stress", "stressed",
    "mood", "mind", "brain", "thought", "thoughts", "therapy",
    "therapist", "help", "better", "worse", "normal", "bad", "good",
    "scared", "afraid", "worried", "nervous", "upset", "angry",
    "sad", "happy", "confused", "lost",
}
