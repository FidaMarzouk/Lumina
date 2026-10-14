"""Text-to-speech with Kokoro-82M, run locally.

The model loads lazily (first call or `warm_up`) and is shared; synthesis is serialised because the
pipeline is not thread-safe.  Privacy: the text is never logged.
"""

from __future__ import annotations

import importlib.util
import io
import logging
import threading
import wave

import numpy as np

from ..config import TTS_DEVICE, TTS_ENABLED, TTS_REPO, TTS_SAMPLE_RATE, TTS_SPEED, TTS_VOICES

log = logging.getLogger(__name__)

_lock = threading.RLock()
_pipeline = None


class TTSUnavailable(RuntimeError):
    """Voice output is switched off or its package is not installed."""


def available() -> bool:
    return TTS_ENABLED and importlib.util.find_spec("kokoro") is not None


def _get_pipeline():
    global _pipeline
    if not available():
        raise TTSUnavailable("voice output needs: pip install -e \".[voice]\" (and TTS_ENABLED=1)")
    with _lock:
        if _pipeline is None:
            from kokoro import KPipeline
            _pipeline = KPipeline(lang_code="a", repo_id=TTS_REPO, device=TTS_DEVICE)
    return _pipeline


def to_wav(audio: np.ndarray, rate: int = TTS_SAMPLE_RATE) -> bytes:
    """Float samples in [-1, 1] → 16-bit mono WAV bytes."""
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def synthesize(text: str, voice: str = "female") -> bytes:
    """Speak `text` with the female or male voice; returns WAV bytes."""
    pipe = _get_pipeline()
    with _lock:
        parts = [np.asarray(a, dtype=np.float32) for _, _, a in pipe(text, voice=TTS_VOICES[voice], speed=TTS_SPEED)
                 if a is not None]
    return to_wav(np.concatenate(parts) if parts else np.zeros(1, dtype=np.float32))


def warm_up() -> None:
    """Load the model and both voices so the first spoken reply is not slow."""
    try:
        for v in TTS_VOICES:
            synthesize("Hi.", v)
        log.info("Voice output ready (%s on %s)", TTS_REPO, TTS_DEVICE)
    except TTSUnavailable as e:
        log.info("Voice output off: %s", e)
    except Exception as e:   # never block the API on voice
        log.warning("Voice output failed to load: %s", type(e).__name__)
