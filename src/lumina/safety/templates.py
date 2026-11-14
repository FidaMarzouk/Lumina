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


def unsupported_language_reply() -> str:
    """For messages written in a way Lumina cannot read reliably (Arabic in Latin letters with digits).

    Lumina does not guess at these: neither the safety models nor the chat model understand them.  The reply
    is given in the three languages it can read, so the person can choose one, and points to "Get help".
    """
    return (
        "I'm sorry, I can't reliably understand messages written this way yet, and I don't want to guess at "
        "something important. Could you write to me in English, French, or Arabic in Arabic letters? "
        "If you need help right now, tap \"Get help\" at the top of the screen.\n\n"
        "Pardon, je ne comprends pas encore bien les messages écrits de cette façon, et je ne veux pas deviner. "
        "Pouvez-vous m'écrire en français, en anglais ou en arabe (en lettres arabes) ? "
        "Si vous avez besoin d'aide tout de suite, touchez « Get help » en haut de l'écran.\n\n"
        "عذراً، لا أستطيع بعد أن أفهم جيداً الرسائل المكتوبة بهذه الطريقة، ولا أريد أن أخمّن. "
        "هل يمكنك أن تكتب لي بالعربية بالحروف العربية، أو بالفرنسية أو الإنجليزية؟ "
        "إذا كنت بحاجة إلى مساعدة الآن، اضغط على «Get help» في أعلى الشاشة."
    )
