from lumina.nlp import models


def test_lazy_model_loads_once_and_proxies():
    calls = []

    def factory():
        calls.append(1)
        return type("M", (), {"attr": 7, "__call__": lambda self, x: x * 2})()

    m = models.LazyModel("t", factory)
    assert not m.loaded and calls == []
    assert m(3) == 6 and m.attr == 7 and m(4) == 8
    assert calls == [1] and m.loaded


def test_private_attribute_lookup_does_not_trigger_load():
    m = models.LazyModel("t", lambda: (_ for _ in ()).throw(RuntimeError("should not load")))
    assert not hasattr(m, "_nope")


def test_warm_up_loads_every_registered_model(monkeypatch):
    monkeypatch.setattr(models, "_REGISTRY", [])          # isolate from the real engine handles
    a, b = models.LazyModel("a", lambda: object()), models.LazyModel("b", lambda: object())
    assert [m.loaded for m in models.registered_models()] == [False, False]
    models.warm_up()
    assert a.loaded and b.loaded
