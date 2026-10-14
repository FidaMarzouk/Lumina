"""Server-side reply templates for safety-critical turns.

Method requests never reach the LLM: the reply below is returned as-is.  Ideation and
third-party replies are LLM-written but fall back to these templates when the output
guard rejects the generation or the LLM is unavailable.

Contact numbers are NOT written here: the frontend crisis banner shows them whenever
`crisis_flag` is true, so the text points to it.
"""


def method_reply() -> str:
    return (
        "It sounds like you're carrying something really painful right now, and I'm glad you reached out. "
        "I can't help with ways to hurt yourself — I care about you being safe. "
        "If you might act on these thoughts, please contact one of the emergency or support lines shown on screen now, "
        "or go to the nearest emergency department. If you can, reach out to someone you trust and let them know how "
        "you're feeling. I'm here to keep talking with you."
    )


def ideation_fallback() -> str:
    return (
        "I'm really sorry you're feeling this way — thank you for telling me. "
        "You deserve support right now, and you don't have to go through this alone. "
        "If you're in danger or might act on these thoughts, please use one of the support lines shown on screen "
        "or go to the nearest emergency department. Would you like to tell me a bit more about what's been happening?"
    )


def third_party_fallback() -> str:
    return (
        "That sounds frightening, and it matters that you're looking out for them. "
        "If they are in immediate danger, contact emergency services using the numbers shown on screen and try not to "
        "leave them alone. If it isn't immediate, gently ask them directly how they're doing and encourage them to talk "
        "to a professional. Please look after yourself too — would you like to talk through how to approach them?"
    )


def unavailable_reply(crisis: bool) -> str:
    base = "I'm having trouble responding right now. Please try again in a moment."
    if crisis:
        base += " If you need help right away, please use one of the support lines shown on screen."
    return base


def generic_fallback() -> str:
    return ("I want to make sure I respond carefully here. Could you tell me a little more about what's on your mind? "
            "I'm here to listen.")
