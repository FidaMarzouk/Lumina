"""Benchmark scoring rules and evidence verification (offline)."""
import json

import pandas as pd
import pytest

from lumina.market import benchmark as bm


def test_wilson_interval():
    lo, hi = bm.wilson(10, 100)
    assert 0.05 < lo < 0.1 < hi < 0.18
    assert all(map(lambda x: x != x, bm.wilson(0, 0)))       # NaN when n = 0


def _app(**over):
    base = {"storefronts_available": "us,gb,ca,au", "privacy_labels": json.dumps(["DATA_NOT_COLLECTED:"]),
            "accessibility_statement": "The developer has not yet indicated which accessibility features this app supports.",
            "current_version_date": "Fri Oct 09 2026 06:24:57 GMT+0000", "collected_at": "2026-10-11T14:58:00+00:00",
            "current_version": "1.0"}
    base.update(over)
    return pd.Series(base)


def test_observed_rules():
    o = bm.observed(_app())
    assert o["availability"][0] == 2 and o["privacy_label"][0] == 2
    assert o["accessibility_declared"][0] == 0 and o["maintenance"][0] == 2
    o = bm.observed(_app(storefronts_available=float("nan"), privacy_labels=float("nan")))
    assert o["availability"][0] == 0 and o["privacy_label"][0] == "unknown"
    linked = bm.observed(_app(privacy_labels=json.dumps(["DATA_LINKED_TO_YOU:CONTACT_INFO", "DATA_NOT_LINKED_TO_YOU:X"])))
    assert linked["privacy_label"][0] == 0


class _FakeClient:
    def __init__(self, payload): self.payload = payload
    def post(self, url, json):
        outer = self
        class R:
            def raise_for_status(self): pass
            def json(self): return {"message": {"content": __import__("json").dumps(outer.payload)}}
        return R()


def test_vendor_claims_require_a_verbatim_quote():
    text = "Talk to our AI anytime. Built on CBT techniques backed by clinical research."
    crit = {"conversational_ai": {"definition": "", "rule": ""}, "evidence_based_approach": {"definition": "", "rule": ""},
            "voice": {"definition": "", "rule": ""}}
    fake = _FakeClient({"conversational_ai": {"score": 2, "quote": "Talk to our AI anytime."},
                        "evidence_based_approach": {"score": 2, "quote": "Proven by 50 trials."},   # invented
                        "voice": {"score": 0, "quote": ""}})
    out = bm.vendor_claims(fake, "m", text, crit)
    assert out["conversational_ai"][0] == 2
    assert out["evidence_based_approach"][0] == "unknown"          # quote not in source → not accepted
    assert out["voice"][0] == 0
