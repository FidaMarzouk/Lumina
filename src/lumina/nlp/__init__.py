"""
Text understanding (Phase 2).

    from lumina.nlp import analyze_message, analyze_feeling

Exports are lazy (PEP 562): importing `lumina.nlp` — or `lumina.nlp.lexicons` — does
not import spaCy / transformers / torch.
"""
import importlib

_EXPORTS = {
    "analyze_message": ".nlp_engine",
    "analyze_feeling": ".feeling_engine",
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name in _EXPORTS:
        return getattr(importlib.import_module(_EXPORTS[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
