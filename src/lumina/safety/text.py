"""Text normalisation shared by every safety check.

Safety rules are written against the *normalised* form, so they do not depend on
how a phone keyboard renders apostrophes, on casing, or on stray whitespace.
"""

import re
import unicodedata

_APOSTROPHES = "’‘ʼ`´'"
_DASHES = "‐‑‒–—―"


def normalize(text: str) -> str:
    """Lower-case, NFKC, drop apostrophes ("don’t" -> "dont"), unify dashes, collapse whitespace."""
    t = unicodedata.normalize("NFKC", text).lower()
    t = t.translate({ord(c): None for c in _APOSTROPHES})
    t = t.translate({ord(c): "-" for c in _DASHES})
    t = re.sub(r"\s+", " ", t)
    return t.strip()
