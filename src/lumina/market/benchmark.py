"""Evidence-backed competitive benchmark (criteria: configs/market/benchmark_criteria.yaml).

Output: data/market/processed/benchmark_long.csv  (one row per app × criterion, with evidence)
        data/market/processed/benchmark_matrix.csv (apps × criteria scores, "unknown" kept)
Run:    python -m lumina.market.benchmark [--model llama3.1]

`human_verified` is False for every row until someone checks it; the report shows that status.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone

import httpx
import pandas as pd
import yaml

from ..config import DATA_DIR, OLLAMA_BASE_URL, PROJECT_ROOT

CRITERIA = PROJECT_ROOT / "configs" / "market" / "benchmark_criteria.yaml"
PROC = DATA_DIR / "market" / "processed"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[‘’“”]", "'", t or "")).strip().lower()


# ── observed ────────────────────────────────────────────────────────────────────
def observed(app: pd.Series) -> dict[str, tuple]:
    out = {}
    raw = app.get("storefronts_available")
    avail = [c for c in str(raw).split(",") if c] if isinstance(raw, str) else []
    out["availability"] = (2 if len(avail) == 4 else 1 if avail else 0, f"available in: {','.join(avail) or 'none'}")
    if pd.isna(app.get("privacy_labels")):
        return out | {k: ("unknown", "no store page") for k in ("privacy_label", "accessibility_declared", "maintenance")}
    labels = json.loads(app["privacy_labels"])
    types = {l.split(":")[0] for l in labels}
    if types & {"DATA_LINKED_TO_YOU", "DATA_USED_TO_TRACK_YOU"}:
        s = 0
    elif types == {"DATA_NOT_COLLECTED"}:
        s = 2
    elif types <= {"DATA_NOT_LINKED_TO_YOU"} and types:
        s = 1
    else:
        s = "unknown"
    out["privacy_label"] = (s, "; ".join(labels) or "none declared")
    acc = str(app.get("accessibility_statement") or "")
    out["accessibility_declared"] = (0 if "not yet indicated" in acc.lower() else 2 if acc else "unknown", acc[:160])
    try:
        d = datetime.strptime(str(app["current_version_date"])[:15], "%a %b %d %Y").replace(tzinfo=timezone.utc)
        c = datetime.fromisoformat(str(app["collected_at"]))
        days = (c - d).days
        out["maintenance"] = (2 if days <= 90 else 1 if days <= 365 else 0, f"v{app['current_version']}, {days} days before collection")
    except Exception:
        out["maintenance"] = ("unknown", "version date unparseable")
    return out


# ── vendor-claimed (LLM + verified quote) ───────────────────────────────────────
def vendor_claims(client: httpx.Client, model: str, source_text: str, criteria: dict) -> dict[str, tuple]:
    spec = "\n".join(f"- {k}: {v['definition']} Scoring: {v['rule']}" for k, v in criteria.items())
    prompt = ("Score an app ONLY from the vendor text below. For each criterion return the score (0, 1 or 2) and the "
              "exact sentence from the text that supports it, copied verbatim. If the text does not mention it, "
              "score 0 with an empty quote. Never use outside knowledge.\n\nCriteria:\n" + spec +
              '\n\nAnswer JSON only: {"<criterion>": {"score": 0|1|2, "quote": "<verbatim sentence or empty>"}}'
              "\n\nVENDOR TEXT:\n" + source_text[:6000])
    r = client.post(f"{OLLAMA_BASE_URL}/api/chat", json={
        "model": model, "stream": False, "format": "json", "keep_alive": "30m",
        "options": {"temperature": 0, "num_predict": 900}, "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    raw = json.loads(r.json()["message"]["content"])
    src = _norm(source_text)
    out = {}
    for k in criteria:
        item = raw.get(k) if isinstance(raw.get(k), dict) else {}
        score, quote = item.get("score"), str(item.get("quote") or "").strip()
        if score not in (0, 1, 2):
            out[k] = ("unknown", "model returned no valid score")
        elif score == 0 and not quote:
            out[k] = (0, "not mentioned in vendor text")
        elif quote and _norm(quote) in src:
            out[k] = (score, quote[:300])
        else:
            out[k] = ("unknown", f"quote not found verbatim in source (model proposed {score})")
    return out


# ── review-inferred ─────────────────────────────────────────────────────────────
def review_inferred(cfg: dict) -> dict[str, dict[str, tuple]]:
    rev = pd.read_json(PROC / "reviews.jsonl", lines=True)
    th = pd.read_json(PROC / "review_themes.jsonl", lines=True)
    df = rev[~rev["dup_of_previous"] & (rev["sample"] == "v0_newest_ios")].merge(th, on="review_id")
    df = df[df["themes"].notna()]
    out: dict[str, dict] = {}
    for app, g in df.groupby("app"):
        n = len(g)
        out[app] = {}
        for crit, c in cfg["review_inferred"].items():
            if n < cfg["min_reviews_for_inference"]:
                out[app][crit] = ("unknown", f"only {n} non-curated reviews")
                continue
            k = sum(any(t["theme"] == c["theme"] and t["polarity"] == c["polarity"] for t in ts) for ts in g["themes"])
            lo, hi = wilson(k, n)
            out[app][crit] = (round(k / n, 3), f"{k}/{n} newest iOS reviews (v0), 95% CI {lo:.2f}–{hi:.2f}")
    return out


def main(model: str) -> None:
    cfg = yaml.safe_load(CRITERIA.read_text(encoding="utf-8"))
    apps = pd.read_csv(PROC / "apps.csv")
    inferred = review_inferred(cfg)
    rows = []
    with httpx.Client(timeout=300) as client:
        for _, a in apps.iterrows():
            for crit, (score, ev) in observed(a).items():
                rows.append((a["key"], crit, "observed", score, ev, a.get("source_url")))
            if pd.notna(a.get("description")):
                text = f"{a['description']}\n\nRelease notes: {a.get('release_notes') or ''}"
                claims = vendor_claims(client, model, text, cfg["vendor_claimed"])
            else:
                claims = {k: ("unknown", "no store page in collected storefronts") for k in cfg["vendor_claimed"]}
            for crit, (score, ev) in claims.items():
                rows.append((a["key"], crit, "vendor_claimed", score, ev, a.get("source_url")))
            for crit in cfg["review_inferred"]:
                score, ev = inferred.get(a["key"], {}).get(crit, ("unknown", "no non-curated review sample"))
                rows.append((a["key"], crit, "review_inferred", score, ev, "data/market/processed/reviews.jsonl"))
    long = pd.DataFrame(rows, columns=["app", "criterion", "evidence_type", "score", "evidence", "source"])
    long["human_verified"] = False
    long.to_csv(PROC / "benchmark_long.csv", index=False, lineterminator="\n")
    long.pivot(index="app", columns="criterion", values="score").to_csv(PROC / "benchmark_matrix.csv", lineterminator="\n")
    print(long.pivot(index="app", columns="criterion", values="score").to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.1")
    main(ap.parse_args().model)
