"""Rate limits on the expensive endpoints: generous for people, a wall for floods, and help in the refusal."""
from types import SimpleNamespace

import pytest

from lumina import orchestrator as orch
from lumina.ratelimit import RateLimiter, client_key, retry_after


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_sliding_windows_allow_then_refuse_then_recover():
    clock = Clock()
    rl = RateLimiter([(3, 60), (5, 3600)], clock=clock)
    assert [rl.hit("a") for _ in range(3)] == [None, None, None]
    wait = rl.hit("a")
    assert wait == pytest.approx(60)                       # the minute window is full
    clock.t += 61
    assert rl.hit("a") is None and rl.hit("a") is None     # 5 in the hour now
    clock.t += 61
    assert rl.hit("a") == pytest.approx(3600 - 122, abs=1)  # the hour window is full


def test_refused_requests_do_not_count_and_keys_are_separate():
    clock = Clock()
    rl = RateLimiter([(2, 60)], clock=clock)
    rl.hit("a"), rl.hit("a")
    for _ in range(10):
        assert rl.hit("a") is not None                     # hammering does not extend the wait
    assert rl.hit("b") is None
    clock.t += 60
    assert rl.hit("a") is None


def test_memory_stays_bounded(monkeypatch):
    import lumina.ratelimit as mod
    monkeypatch.setattr(mod, "_MAX_KEYS", 3)
    rl = RateLimiter([(1, 60)], clock=Clock())
    for k in "abcde":
        rl.hit(k)
    assert list(rl._hits) == ["c", "d", "e"]


def test_key_is_the_account_when_signed_in_else_the_address():
    req = SimpleNamespace(client=SimpleNamespace(host="10.0.0.7"))
    assert client_key(req, {"id": "u1"}) == "user:u1"
    assert client_key(req, None) == "ip:10.0.0.7"
    assert retry_after(0.2) == "1" and retry_after(59.1) == "60"


@pytest.fixture
def api_client(monkeypatch):
    from fastapi.testclient import TestClient

    from lumina import api
    result = orch.TurnResult("hi", "casual", "neutral", "neutral", False, "none", "none", False, [], {"safety": {}})
    monkeypatch.setattr(api, "respond", lambda *a, **k: result)
    monkeypatch.setattr(api, "chat_limiter", RateLimiter([(3, 60)]))
    monkeypatch.setattr(api, "tts_limiter", RateLimiter([(2, 60)]))
    monkeypatch.setattr(api.tts, "synthesize", lambda text, voice: b"RIFF")
    return TestClient(api.app)


def test_chat_flood_gets_429_with_retry_after_and_a_way_to_help(api_client):
    codes = [api_client.post("/chat", json={"message": "hi"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    r = api_client.post("/chat", json={"message": "hi"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert "Get help" in r.json()["detail"]


def test_tts_is_limited_separately_from_chat(api_client):
    assert [api_client.post("/tts", json={"text": "Hello."}).status_code for _ in range(3)] == [200, 200, 429]
    assert api_client.post("/chat", json={"message": "hi"}).status_code == 200
