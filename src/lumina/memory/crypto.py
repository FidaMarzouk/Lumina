"""Field encryption for what people write themselves: journal entries and mood-log notes (A3).

Fernet (AES-128-CBC with an HMAC-SHA256 tag, from the `cryptography` package): a copy of the database alone does
not reveal anyone's words.  The key comes from LUMINA_DATA_KEY, or is generated once into a file next to the
database (config.DATA_KEY_PATH, not in git).  Anyone holding both the database and the key can read the entries,
so in a deployment the key belongs in the environment, not on the same disk.

Losing the key makes the stored entries unreadable: keep a copy of it with any backup of the database.
"""

from __future__ import annotations

import logging
import os
import threading

from ..config import DATA_KEY_PATH

log = logging.getLogger(__name__)

_FERNET = None
_LOCK = threading.Lock()


class DecryptError(ValueError):
    """The stored text could not be decrypted (another key, or the data was changed)."""


def _load_key() -> bytes:
    from cryptography.fernet import Fernet
    env = os.getenv("LUMINA_DATA_KEY", "").strip()
    if env:
        return env.encode()
    if DATA_KEY_PATH.exists():
        return DATA_KEY_PATH.read_bytes().strip()
    DATA_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    fd = os.open(DATA_KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    log.warning("Generated a new data key at %s: keep a copy with any backup of the database", DATA_KEY_PATH)
    return key


def _fernet():
    global _FERNET
    if _FERNET is None:
        with _LOCK:
            if _FERNET is None:
                from cryptography.fernet import Fernet
                _FERNET = Fernet(_load_key())
    return _FERNET


def encrypt(text: str) -> bytes:
    return _fernet().encrypt(text.encode("utf-8"))


def decrypt(token: bytes) -> str:
    from cryptography.fernet import InvalidToken
    try:
        return _fernet().decrypt(bytes(token)).decode("utf-8")
    except InvalidToken as exc:
        raise DecryptError("stored text could not be decrypted") from exc


def reset_for_tests() -> None:
    """Forget the cached key (tests point DATA_KEY_PATH or LUMINA_DATA_KEY elsewhere)."""
    global _FERNET
    _FERNET = None
