"""
lumina/nlp/models.py   (new)

Lazy model handles.

In the original code every HuggingFace pipeline and the spaCy model were created at
*import time* of nlp_engine.py / feeling_engine.py, so even `import empathy_engine`
(or a unit test) downloaded and loaded ~1.5 GB of models.  The handles below load a
model the first time it is called, exactly once (thread-safe), and behave like the
loaded object (`handle(text, ...)`, `handle.attr`).  The API server still loads
everything up-front at startup through `warm_up()`, so request latency is unchanged.
"""
import threading
from typing import Callable, List

__all__ = ["LazyModel", "lazy_pipeline", "lazy_spacy", "warm_up", "registered_models"]

_REGISTRY: List["LazyModel"] = []


class LazyModel:
    def __init__(self, name: str, factory: Callable[[], object]):
        self._name = name
        self._factory = factory
        self._obj = None
        self._lock = threading.Lock()
        _REGISTRY.append(self)

    def get(self):
        if self._obj is None:
            with self._lock:
                if self._obj is None:
                    self._obj = self._factory()
        return self._obj

    @property
    def loaded(self) -> bool:
        return self._obj is not None

    def __call__(self, *args, **kwargs):
        return self.get()(*args, **kwargs)

    def __getattr__(self, item):
        if item.startswith("_"):            # never trigger a load for private/dunder lookups
            raise AttributeError(item)
        return getattr(self.get(), item)

    def __repr__(self):
        return f"<LazyModel {self._name} loaded={self.loaded}>"


def _device() -> int:
    """GPU index for HuggingFace pipelines, or -1 for CPU (config NLP_DEVICE: auto | cpu | cuda)."""
    from ..config import NLP_DEVICE
    if NLP_DEVICE == "cpu":
        return -1
    import torch
    return 0 if torch.cuda.is_available() else -1


def lazy_pipeline(task: str, **kwargs) -> LazyModel:
    """transformers.pipeline(task, device=<gpu if available>, **kwargs), created on first use."""
    def factory():
        from transformers import pipeline as hf_pipeline
        return hf_pipeline(task, device=_device(), **kwargs)
    return LazyModel(f"{task}:{kwargs.get('model')}", factory)


def lazy_spacy(model_name: str, ruler_patterns) -> LazyModel:
    """spaCy model with an EntityRuler (placed first in the pipeline) loaded with `ruler_patterns`."""
    def factory():
        import spacy
        nlp = spacy.load(model_name)
        ruler = nlp.add_pipe("entity_ruler", first=True)
        ruler.add_patterns(ruler_patterns)
        return nlp
    return LazyModel(f"spacy:{model_name}", factory)


def registered_models() -> List[LazyModel]:
    return list(_REGISTRY)


def warm_up() -> None:
    """Load every registered model now (called once at API start-up)."""
    for model in _REGISTRY:
        model.get()
