"""Password hashing with scrypt (stdlib hashlib — no extra dependency).

Stored form:  scrypt$<n>$<r>$<p>$<salt b64>$<hash b64>   (salt: 16 random bytes per password)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

_N, _R, _P, _DKLEN = 2 ** 14, 8, 1, 32


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return "$".join(["scrypt", str(_N), str(_R), str(_P),
                     base64.b64encode(salt).decode(), base64.b64encode(digest).decode()])


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest_b64)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt_b64),
                                n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


# Verified against when the email is unknown, so a login takes the same time either way.
DUMMY_HASH = hash_password(os.urandom(16).hex())
