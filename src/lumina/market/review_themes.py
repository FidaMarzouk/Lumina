"""Multi-label review theme annotation with a local LLM, following configs/market/review_codebook.yaml.

The model is an annotator, not ground truth: its labels are validated against an independently
labelled gold sample (data/market/eval/review_themes_gold.jsonl) before any prevalence is reported.

Run:  python -m lumina.market.review_themes annotate      # all unique reviews → data/market/processed/review_themes.jsonl
"""

from __future__ import annotations

import argparse
import re
import json
from pathlib import Path

import httpx
import yaml

from ..config import DATA_DIR, OLLAMA_BASE_URL, PROJECT_ROOT

CODEBOOK = PROJECT_ROOT / "configs" / "market" / "review_codebook.yaml"
REVIEWS = DATA_DIR / "market" / "processed" / "reviews.jsonl"
OUT = DATA_DIR / "market" / "processed" / "review_themes.jsonl"
POLARITIES = ("praise", "complaint", "neutral")


def codebook() -> dict[str, str]:
    return {k: v["definition"] for k, v in yaml.safe_load(CODEBOOK.read_text(encoding="utf-8"))["themes"].items()}


# v2 (after the v1 validation: precision 0.44 / recall 0.77): every theme must be backed by a short
# verbatim quote from the review; themes whose quote is not found in the text are dropped.
PROMPT_VERSION = 2


def system_prompt(cb: dict[str, str]) -> str:
    return (
        "You annotate app-store reviews of mental health apps. List only the themes from the codebook that the "
        "reviewer EXPLICITLY talks about, each with its polarity (praise, complaint or neutral) and a short quote "
        "(a few words copied exactly from the review) that shows it. Most reviews have 0 to 3 themes. Generic praise "
        "like 'great app' or 'it helped' is not a theme unless it says HOW. Use an empty list if none apply.\n\nCodebook:\n"
        + "\n".join(f"- {k}: {v}" for k, v in cb.items())
        + '\n\nAnswer with JSON only: {"themes": [{"theme": "<name>", "polarity": "praise|complaint|neutral", '
          '"quote": "<exact words from the review>"}]}'
    )


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[‘’`]", "'", re.sub(r"[“”]", '"', t or ""))).strip().lower()


def annotate_one(client: httpx.Client, model: str, sysmsg: str, cb: dict, title: str, text: str) -> list[dict]:
    """Themes for one review.  One retry on malformed JSON (e.g. output cut off); raises if both fail."""
    last_exc: Exception | None = None
    for _ in range(2):
        r = client.post(f"{OLLAMA_BASE_URL}/api/chat", json={
            "model": model, "stream": False, "format": "json", "keep_alive": "30m",
            "options": {"temperature": 0, "num_predict": 600},
            "messages": [{"role": "system", "content": sysmsg},
                         {"role": "user", "content": f"Title: {title}\nReview: {text[:2500]}"}]})
        r.raise_for_status()
        try:
            out = json.loads(r.json()["message"]["content"]).get("themes", [])
            break
        except json.JSONDecodeError as exc:
            last_exc = exc
    else:
        raise last_exc
    source = _norm(f"{title} {text[:2500]}")
    seen, clean = set(), []
    for t in out if isinstance(out, list) else []:
        if not isinstance(t, dict):
            continue
        name = str(t.get("theme", "")).strip().lower()
        pol = str(t.get("polarity", "neutral")).strip().lower()
        quote = _norm(str(t.get("quote", "")))
        if name in cb and name not in seen and len(quote) >= 3 and quote in source:
            seen.add(name)
            clean.append({"theme": name, "polarity": pol if pol in POLARITIES else "neutral"})
    return clean


def annotate(model: str = "llama3.1", ids: set[str] | None = None, out: Path = OUT) -> None:
    cb = codebook()
    sysmsg = system_prompt(cb)
    done = set()
    if out.exists():                                   # keep successful rows, redo failed ones
        kept = [l for l in out.open(encoding="utf-8") if not json.loads(l)["error"]]
        out.write_text("".join(kept), encoding="utf-8", newline="\n")
        done = {json.loads(l)["review_id"] for l in kept}
    rows = [json.loads(l) for l in REVIEWS.open(encoding="utf-8")]
    rows = [r for r in rows if not r["dup_of_previous"] and r["review_id"] not in done
            and (ids is None or r["review_id"] in ids)]
    with httpx.Client(timeout=120) as client, out.open("a", encoding="utf-8", newline="\n") as f:
        for i, r in enumerate(rows, 1):
            try:
                themes, err = annotate_one(client, model, sysmsg, cb, r["title"], r["text"]), None
            except Exception as exc:
                themes, err = None, type(exc).__name__
            f.write(json.dumps({"review_id": r["review_id"], "themes": themes, "annotator": model, "error": err}) + "\n")
            f.flush()
            if i % 100 == 0:
                print(f"{i}/{len(rows)}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["annotate"])
    ap.add_argument("--model", default="llama3.1")
    a = ap.parse_args()
    annotate(a.model)
