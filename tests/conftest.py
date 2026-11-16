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


@pytest.fixture(autouse=True)
def data_key(monkeypatch, tmp_path):
    """Every test encrypts with its own throwaway key (never creates data/user/data.key)."""
    from cryptography.fernet import Fernet

    from lumina.memory import crypto
    monkeypatch.setenv("LUMINA_DATA_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(crypto, "DATA_KEY_PATH", tmp_path / "data.key")
    crypto.reset_for_tests()
    yield
    crypto.reset_for_tests()


@pytest.fixture(autouse=True)
def trace_store(tmp_path):
    """Every test gets its own empty turn-trace database (never data/user/traces.db)."""
    from lumina.observability import TraceStore, set_default_traces
    store = TraceStore(tmp_path / "traces.db")
    set_default_traces(store)
    yield store
    set_default_traces(None)


@pytest.fixture(autouse=True)
def journal_assess(monkeypatch):
    """Journal saves are safety-checked with the real models in production; here a stub reads a marker word
    ("CRISISWORD" → crisis, "HEAVYWORD" → elevated) so tests can exercise each path without the models."""
    from lumina.agent import tools
    from lumina.safety.assessment import SafetyAssessment

    def fake(text):
        if "CRISISWORD" in text:
            return SafetyAssessment("crisis", "ideation", False, {})
        return SafetyAssessment("elevated" if "HEAVYWORD" in text else "none", "none", False, {})
    monkeypatch.setattr(tools, "ASSESS", fake)


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


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    """The API's rate limiters are process-wide: every test starts with empty counts."""
    yield
    import sys
    api = sys.modules.get("lumina.api")
    if api is not None:
        api.chat_limiter.reset()
        api.tts_limiter.reset()
