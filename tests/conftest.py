import sys
import types

import pytest


@pytest.fixture(autouse=True)
def user_store(tmp_path):
    """Every test gets its own empty personal-data database (never data/user/lumina.db)."""
    from lumina.memory.store import Store, set_default_store
    store = Store(tmp_path / "lumina.db")
    set_default_store(store)
    yield store
    set_default_store(None)


@pytest.fixture
def fake_sentence_transformers(monkeypatch):
    """ingestion / retriever import sentence_transformers at module level; tests never need the real model."""
    mod = types.ModuleType("sentence_transformers")

    class SentenceTransformer:                       # replaced per-test where an embedding is needed
        def __init__(self, *a, **k): pass

    mod.SentenceTransformer = SentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", mod)
    for name in [m for m in sys.modules if m.startswith(("lumina.rag", "lumina.knowledge.embed_and_store"))]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    return mod
