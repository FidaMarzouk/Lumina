"""Intent taxonomy — WHY the user is writing (not how they feel, not whether they are at risk).

This replaces lexicons/intent_labels.py, whose phrase lists (crisis keywords, self-harm
method phrases, injection phrases, idiom exceptions) are gone:
  * crisis / self-harm risk  → lumina/safety (models + a minimal floor)
  * prompt injection          → lumina/safety/injection.py (classifier)
  * intent                    → a trained classifier over these definitions (lumina/nlp/intent.py);
                                the zero-shot model uses the same definitions until it ships.

The definitions are the single source for: the zero-shot labels, and the labelling guide used
to build the intent dataset (eval/datasets/intent/).
"""

INTENTS: dict[str, str] = {
    "venting": (
        "the user is expressing current emotional pain, stress or frustration about their own life "
        "and mainly wants to be heard and understood"
    ),
    "seeking_advice": (
        "the user asks what they should do or how to cope with or handle a specific personal situation, "
        "wanting practical guidance or next steps"
    ),
    "seeking_validation": (
        "the user asks whether their thoughts, feelings, reactions or experiences are normal, valid or "
        "acceptable, wanting reassurance"
    ),
    "help_seeking": (
        "the user wants to find, access, afford or prepare for professional mental health care such as a "
        "therapist, counselor, psychiatrist, doctor or support service"
    ),
    "information": (
        "the user asks a general factual question about mental health, a condition, symptoms, treatments "
        "or how something works, not about what they personally should do"
    ),
    "sharing_experience": (
        "the user calmly narrates a past experience or how things went, without asking for anything and "
        "without expressing current distress"
    ),
    "casual": (
        "the user is making small talk: a greeting, thanks, goodbye, a pleasantry, positive news, or a "
        "message unrelated to their wellbeing"
    ),
    # Q3: the router's first gate for the agent tools (A1-A3).  Asking for an exercise or technique is
    # seeking_advice, not an action; only requests to record, fetch, remind or forget are.
    "action_request": (
        "the user asks Lumina to do something in the app for them: save or note something in their journal, "
        "log their sleep or mood, set a reminder, show or look up what they wrote or tracked before, or forget "
        "or delete something it keeps"
    ),
}

INTENT_NAMES = tuple(INTENTS)

# Zero-shot form: hypothesis text → intent name.
INTENT_LABELS = [f"{d}." for d in INTENTS.values()]
INTENT_MAP = {f"{d}.": name for name, d in INTENTS.items()}
