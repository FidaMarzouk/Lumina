"""App Store product-page parser (offline, recorded fixture) and the polite HTTP client."""
from pathlib import Path

import pytest

from lumina.common.http import PoliteClient, RobotsDisallowed
from lumina.market.collect.app_store import parse_page
from lumina.market.schemas import Provenance

FIXTURE = Path(__file__).parent / "fixtures" / "app_store_page_wysa_us.html"
PROV = Provenance(source="test", source_url="https://apps.apple.com/us/app/id1166585565",
                  collected_at="2026-10-11T00:00:00+00:00", run_id="test")


def test_parse_recorded_page():
    p, reviews = parse_page(FIXTURE.read_text(encoding="utf-8"), "1166585565", "us", PROV)
    assert p.name.startswith("Wysa") and p.developer == "Touchkin" and p.category == "Health & Fitness"
    assert p.rating_count and len(p.rating_histogram_5_to_1) == 5 and sum(p.rating_histogram_5_to_1) == p.rating_count
    assert p.in_app_purchases and all(i.price.startswith("$") for i in p.in_app_purchases)
    assert p.privacy_labels and p.privacy_labels[0].categories
    assert p.similar_apps and p.current_version and p.description
    assert len(reviews) == p.featured_review_count > 0
    assert all(1 <= r.rating <= 5 and len(r.author_hash) == 16 for r in reviews)


def test_reviewer_names_are_never_stored():
    _, reviews = parse_page(FIXTURE.read_text(encoding="utf-8"), "1166585565", "us", PROV)
    dumped = "".join(r.model_dump_json() for r in reviews)
    assert "reviewerName" not in dumped and "beanie31031" not in dumped


def test_robots_disallowed_url_is_never_fetched(monkeypatch):
    c = PoliteClient()
    monkeypatch.setattr(c, "allowed", lambda url: False)
    monkeypatch.setattr(c, "_fetch", lambda url: (_ for _ in ()).throw(AssertionError("fetched!")))
    with pytest.raises(RobotsDisallowed):
        c.get("https://itunes.apple.com/us/rss/customerreviews/id=1/json")
    assert c.log[-1]["robots"] == "disallowed"


APPLE_ITUNES_ROBOTS = """User-agent: *
Disallow: /WebObjects/*
Allow: /WebObjects/MZStore.woa/wa/viewMultiRoom?*
Disallow: /search*
Disallow: /*/rss/*
Disallow: /*/lookup?

User-agent: Googlebot
Disallow: /*/album/*/*?i=*
"""


@pytest.mark.parametrize("url,allowed", [
    ("https://itunes.apple.com/us/rss/customerreviews/page=1/id=1/sortby=mostrecent/json", False),  # stdlib says True
    ("https://itunes.apple.com/us/lookup?id=1", False),
    ("https://itunes.apple.com/search?term=wysa", False),
    ("https://itunes.apple.com/WebObjects/MZStore.woa/wa/viewMultiRoom?id=1", True),   # longer Allow wins
    ("https://itunes.apple.com/WebObjects/other", False),
    ("https://itunes.apple.com/us/app/id1", True),
])
def test_robots_wildcards_follow_rfc9309(url, allowed):
    from lumina.common.robots import Robots
    assert Robots(APPLE_ITUNES_ROBOTS).can_fetch("LuminaResearch/0.2", url) is allowed


def test_robots_end_anchor_and_specific_agent_group():
    from lumina.common.robots import Robots
    r = Robots("User-agent: luminaresearch\nDisallow: /private$\n\nUser-agent: *\nDisallow: /")
    assert not r.can_fetch("LuminaResearch/0.2", "https://x.org/private")
    assert r.can_fetch("LuminaResearch/0.2", "https://x.org/private/page")     # $ anchors
    assert not r.can_fetch("OtherBot/1.0", "https://x.org/anything")
