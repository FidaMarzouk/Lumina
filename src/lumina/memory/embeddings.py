"""Sentence embeddings for episode memory — the same model as the knowledge base (config.EMBEDDING_MODEL)."""

from __future__ import annotations

import numpy as np

from ..config import EMBEDDING_MODEL
from ..nlp.models import LazyModel, _device


def _load():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL, device="cuda" if _device() == 0 else "cpu")


embedder = LazyModel(f"embedder:{EMBEDDING_MODEL}", _load)


def embed(text: str) -> np.ndarray:
    """Unit-length float32 vector, so a dot product is the cosine similarity."""
    return np.asarray(embedder.encode(text, normalize_embeddings=True), dtype=np.float32)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    return float(np.dot(a, b) / (na * nb)) if na and nb else 0.0
