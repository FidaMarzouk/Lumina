"""App Store product-page collector (robots-compliant).

Apple's robots.txt disallows the review RSS feed and the Search/Lookup APIs on itunes.apple.com,
and `/api/*` on apps.apple.com.  Product pages (`apps.apple.com/<cc>/app/id<ID>`) are allowed and
carry structured data (JSON-LD + server data): metadata, rating histogram, in-app purchase prices,
privacy labels, accessibility statement, current version notes, ~8 featured reviews, and Apple's
"You Might Also Like" list (used for market-map discovery).

Usage:
    python -m lumina.market.collect.app_store collect   --countries us gb ca au
    python -m lumina.market.collect.app_store discover  --seeds 1166585565 1305375832 --depth 1

Outputs (one immutable run directory per invocation):
    data/raw/market/app_store/<run_id>/manifest.json
    data/raw/market/app_store/<run_id>/pages/<country>_<app_id>.html   (raw evidence)
    data/raw/market/app_store/<run_id>/app_profiles.jsonl
    data/raw/market/app_store/<run_id>/featured_reviews.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ...common.http import FetchFailed, PoliteClient, RobotsDisallowed
from ...common.runs import git_sha, new_run_dir, write_manifest
from ...config import DATA_DIR, PROJECT_ROOT
from ..schemas import AppProfile, FeaturedReview, InAppPurchase, PrivacyLabel, Provenance, SimilarApp

log = logging.getLogger(__name__)

SOURCE = "app_store_product_page"
RAW_BASE = DATA_DIR / "raw" / "market"
CACHE_DIR = DATA_DIR / "cache" / "http"
COMPETITORS = PROJECT_ROOT / "configs" / "market" / "competitors.yaml"
_SALT = os.getenv("LUMINA_HASH_SALT", "lumina-market-v1")


def page_url(app_id: str, country: str) -> str:
    return f"https://apps.apple.com/{country}/app/id{app_id}"


# ── parsing ─────────────────────────────────────────────────────────────────────
def _json_block(html: str, pattern: str) -> dict | None:
    m = re.search(pattern, html, re.S)
    return json.loads(m.group(1)) if m else None


def _items(shelves: dict, name: str) -> list:
    sh = shelves.get(name) or {}
    return sh.get("items") or []


def _link(shelves: dict, text: str) -> str | None:
    for it in _items(shelves, "notPurchasedLinks"):
        if it.get("text") == text:
            for d in it.get("clickAction", {}).get("actionMetrics", {}).get("data", []):
                url = d.get("fields", {}).get("actionUrl")
                if url:
                    return url
    return None


def _annotation_text(item: dict) -> str:
    parts = []
    for sub in item.get("items", []):
        if sub.get("$kind") == "linkableText":
            parts.append(sub["linkableText"]["styledText"]["rawText"].replace("**", ""))
    return "\n".join(parts) or item.get("summary") or ""


def parse_page(html: str, app_id: str, country: str, prov: Provenance) -> tuple[AppProfile, list[FeaturedReview]]:
    ld = _json_block(html, r'<script id=software-application type="application/ld\+json">(.*?)</script>') or {}
    server = _json_block(html, r'<script type="application/json" id="serialized-server-data">(.*?)</script>')
    if not server:
        raise ValueError("serialized-server-data block not found (page layout changed?)")
    data = server["data"][0]["data"]
    shelves = data.get("shelfMapping", {})

    info = {a["title"]: a for a in _items(shelves, "information")}
    iap = [InAppPurchase(name=p["leadingText"], price=p["trailingText"])
           for p in info.get("In-App Purchases", {}).get("items", []) if p.get("$kind") == "textPair"]
    privacy = [PrivacyLabel(type=p.get("identifier", ""),
                            categories=[c.get("identifier", c.get("title", "")) for c in p.get("categories", [])])
               for p in _items(shelves, "privacyTypes")]
    ratings = (_items(shelves, "productRatings") or [{}])[0]
    version = (_items(shelves, "mostRecentVersion") or [{}])[0]
    acc = (_items(shelves, "accessibilityHeader") or [{}])[0]
    desc_items = _items(shelves, "description")
    description = desc_items[0]["paragraph"]["text"] if desc_items else ld.get("description", "")
    languages = info.get("Languages", {}).get("summary") or ""
    offers = ld.get("offers") or {}

    reviews = []
    for it in _items(shelves, "allProductReviews"):
        r = it.get("review") or {}
        if not r.get("id") or not r.get("rating"):
            continue
        reviews.append(FeaturedReview(
            review_id=str(r["id"]), app_id=app_id, country=country, rating=int(r["rating"]),
            title=r.get("title") or "", text=r.get("contents") or "", date=r.get("date"),
            author_hash=hashlib.sha256(f"{_SALT}:{r.get('reviewerName', '')}".encode()).hexdigest()[:16],
            provenance=prov))

    profile = AppProfile(
        app_id=app_id, country=country,
        name=data.get("title") or ld.get("name", ""),
        developer=(ld.get("author") or {}).get("name"),
        seller=info.get("Seller", {}).get("summary"),
        category=info.get("Category", {}).get("summary"),
        genres=ld.get("genre") or [],
        description=description,
        price=offers.get("price"), currency=offers.get("priceCurrency"),
        in_app_purchases=iap,
        rating_average=ratings.get("ratingAverage"),
        rating_count=ratings.get("totalNumberOfRatings"),
        # Apple sends these as floats derived from percentages (e.g. 228.00000000000003)
        rating_histogram_5_to_1=[round(c) for c in ratings["ratingCounts"]] if ratings.get("ratingCounts") else None,
        age_rating=info.get("Age Rating", {}).get("summary"),
        languages=[l.strip() for l in languages.split(",") if l.strip()],
        size=info.get("Size", {}).get("summary"),
        compatibility=_annotation_text(info["Compatibility"]) if "Compatibility" in info else None,
        current_version=(version.get("primarySubtitle") or "").replace("Version ", "") or None,
        current_version_date=version.get("secondarySubtitle"),
        release_notes=version.get("text"),
        privacy_labels=privacy,
        accessibility_statement=((acc.get("text") or {}).get("styledText") or {}).get("rawText"),
        developer_website=_link(shelves, "Developer Website"),
        privacy_policy_url=_link(shelves, "Privacy Policy"),
        similar_apps=[SimilarApp(app_id=str(s["adamId"]), title=s.get("title", ""))
                      for s in _items(shelves, "similarItems") if s.get("adamId")],
        featured_review_count=len(reviews),
        provenance=prov,
    )
    return profile, reviews


# ── collection ──────────────────────────────────────────────────────────────────
def load_competitors(path: Path = COMPETITORS) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["apps"]


class NotInStorefront(RuntimeError):
    """HTTP 404 for a valid app id: the app is not sold in that country's App Store."""


def _fetch(client: PoliteClient, app_id: str, country: str, run_id: str, run_dir: Path):
    url = page_url(app_id, country)
    resp = client.get(url)
    if resp.status == 404:
        raise NotInStorefront(url)
    if resp.status != 200:
        raise FetchFailed(f"{url} -> HTTP {resp.status}")
    (run_dir / "pages").mkdir(exist_ok=True)
    (run_dir / "pages" / f"{country}_{app_id}.html").write_text(resp.text, encoding="utf-8")
    prov = Provenance(source=SOURCE, source_url=resp.final_url, collected_at=resp.fetched_at, run_id=run_id)
    return parse_page(resp.text, app_id, country, prov)


def collect(countries: list[str], app_ids: list[str] | None = None) -> Path:
    apps = load_competitors()
    if app_ids:
        apps = [a for a in apps if str(a["app_store_id"]) in app_ids]
    run_id, run_dir = new_run_dir(RAW_BASE, "app_store")
    client = PoliteClient(cache_dir=CACHE_DIR)
    profiles, reviews, errors, availability = [], [], [], []
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for app in apps:
        for cc in countries:
            app_id = str(app["app_store_id"])
            try:
                p, rs = _fetch(client, app_id, cc, run_id, run_dir)
                if app.get("name_must_contain") and app["name_must_contain"].lower() not in p.name.lower():
                    errors.append({"app": app["key"], "country": cc, "error": f"name mismatch: page is '{p.name}'"})
                profiles.append(p)
                reviews.extend(rs)
                availability.append({"app": app["key"], "country": cc, "available": True})
            except NotInStorefront:
                availability.append({"app": app["key"], "country": cc, "available": False})
            except (RobotsDisallowed, FetchFailed, ValueError, KeyError) as exc:
                errors.append({"app": app["key"], "country": cc, "error": f"{type(exc).__name__}: {exc}"})
                log.warning("%s/%s failed: %s", app["key"], cc, exc)
    with open(run_dir / "app_profiles.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for p in profiles:
            f.write(p.model_dump_json() + "\n")
    with open(run_dir / "featured_reviews.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in reviews:
            f.write(r.model_dump_json() + "\n")
    write_manifest(run_dir, {
        "source": SOURCE, "run_id": run_id, "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_version": git_sha(PROJECT_ROOT), "countries": countries,
        "apps": [a["key"] for a in apps], "user_agent": client.user_agent,
        "rate_limit": {"min_interval_s": client.min_interval_s, "jitter_s": client.jitter_s},
        "counts": {"profiles": len(profiles), "featured_reviews": len(reviews), "errors": len(errors),
                   "not_in_storefront": sum(not a["available"] for a in availability)},
        "availability": availability, "errors": errors, "requests": client.log,
        "notes": "Robots-compliant product pages only. Featured reviews are Apple-selected (not random, not recent).",
    })
    client.close()
    return run_dir


def discover(seeds: list[str], depth: int, country: str = "us") -> Path:
    """Breadth-first walk of Apple's 'You Might Also Like' graph to find candidate competitors."""
    run_id, run_dir = new_run_dir(RAW_BASE, "app_store_discovery")
    client = PoliteClient(cache_dir=CACHE_DIR)
    seen, frontier, nodes, edges, errors = set(seeds), list(seeds), {}, [], []
    for level in range(depth + 1):
        nxt = []
        for app_id in frontier:
            try:
                p, _ = _fetch(client, app_id, country, run_id, run_dir)
            except (NotInStorefront, RobotsDisallowed, FetchFailed, ValueError, KeyError) as exc:
                errors.append({"app_id": app_id, "error": f"{type(exc).__name__}: {exc}"})
                continue
            nodes[app_id] = {"name": p.name, "developer": p.developer, "category": p.category,
                             "genres": p.genres, "rating_count": p.rating_count, "level": level}
            for s in p.similar_apps:
                edges.append({"from": app_id, "to": s.app_id, "title": s.title})
                if s.app_id not in seen and level < depth:
                    seen.add(s.app_id)
                    nxt.append(s.app_id)
        frontier = nxt
    candidates = {}
    for e in edges:
        candidates.setdefault(e["to"], {"title": e["title"], "in_degree": 0})["in_degree"] += 1
    (run_dir / "discovery.json").write_text(json.dumps(
        {"nodes": nodes, "edges": edges, "candidates": candidates}, indent=2, ensure_ascii=False), encoding="utf-8")
    write_manifest(run_dir, {"source": SOURCE + ":similar_apps", "run_id": run_id, "seeds": seeds, "depth": depth,
                             "country": country, "code_version": git_sha(PROJECT_ROOT),
                             "counts": {"pages": len(nodes), "candidates": len(candidates), "errors": len(errors)},
                             "errors": errors, "requests": client.log})
    client.close()
    return run_dir


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--countries", nargs="+", default=["us", "gb", "ca", "au"])
    c.add_argument("--apps", nargs="*", help="limit to these App Store ids")
    d = sub.add_parser("discover")
    d.add_argument("--seeds", nargs="+", required=True)
    d.add_argument("--depth", type=int, default=1)
    a = ap.parse_args()
    out = collect(a.countries, a.apps) if a.cmd == "collect" else discover(a.seeds, a.depth)
    print(out)
