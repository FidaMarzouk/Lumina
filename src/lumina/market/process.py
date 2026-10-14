"""Build the normalised, traceable market datasets from raw collection runs + the frozen v0 data.

Inputs
  data/raw/market/app_store/<latest run>/   app_profiles.jsonl, featured_reviews.jsonl, manifest.json
  data/market/v0/ios_reviews_health_companions.csv   (original Phase 1 reviews; producing script missing)
  configs/market/competitors.yaml

Outputs (data/market/processed/)
  apps.csv                one row per app: US page if available, else first available storefront;
                          availability per storefront; provenance (run id, source url, collected_at)
  reviews.jsonl           one row per review: v0 iOS reviews + current featured reviews, de-duplicated,
                          language-tagged; author names replaced by salted hashes
  (printed)               quality summary: counts, coverage, duplicates, nulls, language; the
                          rendered view is the Market section of reports/lumina_report.html

Run:  python -m lumina.market.process [--run <run_id>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import pandas as pd

from ..config import DATA_DIR, PROJECT_ROOT
from .collect.app_store import load_competitors

RAW = DATA_DIR / "raw" / "market" / "app_store"
V0_REVIEWS = DATA_DIR / "market" / "v0" / "ios_reviews_health_companions.csv"
OUT = DATA_DIR / "market" / "processed"
_SALT = os.getenv("LUMINA_HASH_SALT", "lumina-market-v1")
V0_APP_KEYS = {"replika": "replika", "woebot": "woebot", "wysa": "wysa"}


def _hash(name: str) -> str:
    return hashlib.sha256(f"{_SALT}:{name}".encode()).hexdigest()[:16]


def latest_run(run_id: str | None = None) -> Path:
    runs = sorted(p for p in RAW.iterdir() if (p / "manifest.json").exists())
    if run_id:
        return RAW / run_id
    return runs[-1]


def _lang_detector():
    from lingua import Language, LanguageDetectorBuilder
    return LanguageDetectorBuilder.from_languages(
        Language.ENGLISH, Language.FRENCH, Language.SPANISH, Language.GERMAN, Language.ARABIC,
        Language.PORTUGUESE, Language.ITALIAN).build()


def build_apps(run: Path) -> pd.DataFrame:
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    profiles = [json.loads(l) for l in (run / "app_profiles.jsonl").open(encoding="utf-8")]
    by_id = {}
    for p in profiles:
        by_id.setdefault(p["app_id"], {})[p["country"]] = p
    avail = pd.DataFrame(manifest["availability"])
    rows = []
    for app in load_competitors():
        pages = by_id.get(str(app["app_store_id"]), {})
        p = pages.get("us") or next(iter(pages.values()), None)
        a = avail[avail["app"] == app["key"]]
        row = {"key": app["key"], "name": app["name"], "category": app["category"],
               "app_store_id": app["app_store_id"],
               "storefronts_available": ",".join(a[a["available"]]["country"]),
               "storefronts_missing": ",".join(a[~a["available"]]["country"]),
               "status_note": app.get("status_note", "")}
        if p:
            iap = p["in_app_purchases"]
            row.update({
                "page_country": p["country"], "store_name": p["name"], "developer": p["developer"],
                "seller": p["seller"], "price": p["price"],
                "iap_count": len(iap), "iap_items": " | ".join(f"{i['name']}: {i['price']}" for i in iap),
                "rating_average": p["rating_average"], "rating_count": p["rating_count"],
                "rating_histogram_5_to_1": json.dumps(p["rating_histogram_5_to_1"]),
                "age_rating": p["age_rating"], "languages": ",".join(p["languages"]),
                "current_version": p["current_version"], "current_version_date": p["current_version_date"],
                "privacy_labels": json.dumps([l["type"] + ":" + "/".join(l["categories"]) for l in p["privacy_labels"]]),
                "accessibility_statement": p["accessibility_statement"],
                "developer_website": p["developer_website"], "privacy_policy_url": p["privacy_policy_url"],
                "description": p["description"], "release_notes": p["release_notes"],
                "source_url": p["provenance"]["source_url"], "collected_at": p["provenance"]["collected_at"],
                "run_id": p["provenance"]["run_id"],
            })
        rows.append(row)
    df = pd.DataFrame(rows)
    df["rating_count"] = df["rating_count"].astype("Int64")
    return df


def build_reviews(run: Path) -> pd.DataFrame:
    rows = []
    v0 = pd.read_csv(V0_REVIEWS, encoding="utf-8-sig")
    v0.columns = [c.strip() for c in v0.columns]
    for r in v0.itertuples(index=False):
        rows.append({"review_id": f"v0:{r.review_id}", "app": V0_APP_KEYS.get(str(r.app).strip().lower(), str(r.app).strip().lower()),
                     "country": "us", "rating": int(r.rating), "title": str(r.title) if pd.notna(r.title) else "",
                     "text": str(r.review), "date": str(r.date), "author_hash": _hash(str(r.username)),
                     "sample": "v0_newest_ios", "source": "data/market/v0/ios_reviews_health_companions.csv",
                     "collected_at": "2026-05-03 (approx., from data; producing script missing)", "run_id": "v0"})
    key_by_id = {str(a["app_store_id"]): a["key"] for a in load_competitors()}
    for l in (run / "featured_reviews.jsonl").open(encoding="utf-8"):
        f = json.loads(l)
        rows.append({"review_id": f"as:{f['review_id']}", "app": key_by_id.get(f["app_id"], f["app_id"]),
                     "country": f["country"], "rating": f["rating"], "title": f["title"], "text": f["text"],
                     "date": f["date"], "author_hash": f["author_hash"], "sample": "apple_featured",
                     "source": f["provenance"]["source_url"], "collected_at": f["provenance"]["collected_at"],
                     "run_id": f["provenance"]["run_id"]})
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce", format="mixed")
    df["dup_of_previous"] = df.duplicated("review_id")                       # same review on several storefronts
    df["text_hash"] = (df["title"].fillna("") + " " + df["text"].fillna("")).str.lower().str.strip().map(
        lambda t: hashlib.sha256(t.encode()).hexdigest()[:16])
    det = _lang_detector()
    df["language"] = [(det.detect_language_of(t) or "unknown").__str__().split(".")[-1].lower()
                      if isinstance(t, str) and len(t) > 3 else "unknown"
                      for t in (df["title"].fillna("") + ". " + df["text"].fillna(""))]
    return df


def quality_report(apps: pd.DataFrame, reviews: pd.DataFrame, run: Path) -> str:
    r = reviews
    lines = ["# Market data — quality report", "",
             f"Collection run: `{run.name}` (robots-compliant App Store product pages) + frozen v0 reviews.", "",
             "## Apps", "", "| App | Category | Storefronts available | Missing | Ratings (page storefront) | Current version date |",
             "|---|---|---|---|---|---|"]
    for a in apps.itertuples():
        lines.append(f"| {a.name} | {a.category} | {a.storefronts_available or '—'} | {a.storefronts_missing or '—'} | "
                     f"{a.rating_average if pd.notna(a.rating_average) else '—'} (n={a.rating_count if pd.notna(a.rating_count) else '—'}) | {str(a.current_version_date)[:15] if pd.notna(a.current_version_date) else '—'} |")
    u = r[~r["dup_of_previous"]]
    lines += ["", "## Reviews", "",
              f"Rows: {len(r)} · unique review ids: {len(u)} · cross-storefront duplicates removed: {int(r['dup_of_previous'].sum())} · "
              f"duplicate texts among unique ids: {int(u.duplicated('text_hash').sum())}", "",
              "| App | Sample | n (unique) | Date range | Mean rating | Non-English |", "|---|---|---|---|---|---|"]
    for (app, sample), g in u.groupby(["app", "sample"]):
        lines.append(f"| {app} | {sample} | {len(g)} | {g['date'].min():%Y-%m} → {g['date'].max():%Y-%m} | "
                     f"{g['rating'].mean():.2f} | {(g['language'] != 'english').sum()} |")
    nulls = {c: int(u[c].isna().sum()) for c in ("title", "text", "date", "rating")}
    lines += ["", f"Null counts (unique rows): {nulls}", "",
              "## Known biases and limits",
              "- **Featured reviews are chosen by Apple** (about 8 per storefront page): neither random nor recent (dates span up to 8 years). Their mean rating is not representative (see table). Use them as qualitative evidence only, never to estimate shares.",
              "- **The v0 reviews are the ~480 newest iOS reviews for 3 apps**, covering very different time windows: Replika about 7 months, Woebot about 4 years. The script that produced them is missing.",
              "- **No robots-compliant way to collect reviews at scale was found.** Apple's robots.txt disallows the review RSS feed and the APIs. Most apps therefore have only featured-review evidence.",
              "- **Rating averages and counts are per storefront**, not global.",
              "- **Only English storefronts were collected** (us, gb, ca, au). Availability gaps are recorded, not imputed."]
    return "\n".join(lines) + "\n"


def main(run_id: str | None = None) -> None:
    run = latest_run(run_id)
    OUT.mkdir(parents=True, exist_ok=True)
    apps = build_apps(run)
    reviews = build_reviews(run)
    apps.to_csv(OUT / "apps.csv", index=False, lineterminator="\n")
    reviews.to_json(OUT / "reviews.jsonl", orient="records", lines=True, force_ascii=False, date_format="iso")
    print(quality_report(apps, reviews, run))
    print(f"{len(apps)} apps, {len(reviews)} review rows → {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    main(ap.parse_args().run)
