"""
lumina/knowledge/cleaning.py — knowledge-base cleaning + chunking (v1)

    data/knowledge/raw/*.jsonl  →  data/knowledge/processed/<source>_clean.jsonl

One output record per source PAGE:
    {doc_id, source, url, title, language, chunks: [{chunk_id, heading, text, chunk_type, words}]}

Fixes over v0 (docs/audit.md §3.2; the previous code and outputs are in git history and data/snapshots/v0):
  * real page URLs: metadata.url is used before the record UUID (provenance of every chunk; not shown to users)
  * NIMH / Wikipedia section records are grouped into one document per page (fragment stripped)
  * English check uses whole words (v0 counted substrings, e.g. "in" inside any word → never filtered)
  * chunk_type keywords match on word boundaries (v0: "rate" matched "moderate", "sign" matched "design")
  * navigation / link-list fragments are dropped by structure (many short lines, almost no sentences)
  * chunks are ~160 words, split on sentence boundaries with a short overlap, so they fit the
    embedder's 256-token window (v0: up to 4,129 words → most of each long chunk was never embedded)
  * sections under 30 words are merged into the next chunk of the same page; exact duplicate
    chunk texts are dropped across the whole knowledge base

Run:  python -m lumina.knowledge.cleaning
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path

from lumina.config import PROCESSED_DIR as PROC_DIR, RAW_DIR

CHUNKER_VERSION = "v1"
TARGET_WORDS = 160          # all-MiniLM-L6-v2 reads 256 word-pieces; at 200 words 17% of chunks overflowed (technical vocab)
OVERLAP_WORDS = 30
MIN_SECTION_WORDS = 30

CHUNK_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("symptoms",     ["symptoms?", "signs?", "warning signs?", "when to see", "diagnos\\w*"]),
    ("causes",       ["causes?", "risk factors?", "etiology"]),
    ("treatment",    ["treatments?", "therap(?:y|ies)", "medicines?", "medications?", "psychotherapy",
                      "cbt", "dbt", "ssris?", "prescriptions?"]),
    ("advice",       ["how to", "tips?", "coping", "cope", "self-care", "self-help", "lifestyle",
                      "what you can do", "support", "help"]),
    ("rights_legal", ["laws?", "legal", "rights", "discrimination", "disability", "employers?", "benefits?"]),
    ("overview",     ["overview", "introduction", "what is", "about", "definition"]),
    ("statistics",   ["statistics", "prevalence", "epidemiology"]),
]
_TYPE_RX = [(t, re.compile(r"\b(?:" + "|".join(kws) + r")\b", re.I)) for t, kws in CHUNK_TYPE_RULES]

SKIP_HEADINGS = re.compile(
    r"\b(more information|references|bibliography|further reading|external links|see also|notes|"
    r"clinical trials|additional federal resources|share outreach|find help and support|"
    r"women's health topics|free health information|thank you for subscribing)\b", re.I)

_ENGLISH = {"the", "and", "of", "to", "in", "is", "are", "you", "for", "with", "that", "it", "this"}


# ── text utilities ────────────────────────────────────────────────────────────
def remove_citations(text: str) -> str:
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\[citation needed\]", "", text, flags=re.I)
    return re.sub(r"\[[\w\s]{1,30}\]", "", text)


_REF_LINE = re.compile(r"(doi\s*:|10\.\d{4}|PMID\s*\d|PMC\d|ISBN\s|ISSN\s|Retrieved\s+\w+\s+\d|Archived from|"
                       r"\^[\s\w]|Cite error:)", re.I)
_BOILERPLATE = [
    r"Copy Link\s+Link copied.*", r"Share\s+Print\s+Download PDF.*", r"Subscribe.*?inbox\.",
    r"Email Address.*?email\.", r"Click here.*?\.", r"Learn more about Mayo Clinic.*",
    r"Mayo Clinic in Rochester.*", r"Women's health topics.*?inbox", r"Get the latest information.*?below\.",
    r"On this page\n.*?\n\n", r"Explore clinical trials.*", r"Share outreach materials.*",
    r"Additional federal resources.*", r"Find help and support.*",
]


def clean_text(raw: str) -> str:
    text = remove_citations(raw or "")
    text = "\n".join(l.strip() for l in text.splitlines() if not _REF_LINE.search(l.strip()))
    for pat in _BOILERPLATE:
        text = re.sub(pat, "", text, flags=re.DOTALL | re.I)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def is_english(text: str) -> bool:
    words = set(re.findall(r"[a-z]+", text[:1500].lower()))
    return len(words & _ENGLISH) >= 4


def is_navigation(text: str) -> bool:
    """Link lists / menus / "on this page" question lists: several lines, all short, little prose."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) < 3:
        return False
    lengths = sorted(len(l.split()) for l in lines)
    median, longest = lengths[len(lengths) // 2], lengths[-1]
    prose = sum(1 for l in lines if len(l.split()) >= 12 and l.endswith((".", "!")))
    return median <= 10 and longest <= 20 and prose / len(lines) < 0.3


def classify_chunk(heading: str, text: str) -> str:
    for target in (heading, text[:200]):
        for t, rx in _TYPE_RX:
            if rx.search(target):
                return t
    return "general"


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def pack(text: str, target: int = TARGET_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    """Pack sentences into ~target-word chunks; carry ≤ overlap words of trailing sentences forward."""
    sents = []
    for s in split_sentences(text):
        w = s.split()
        while len(w) > target:                     # very long "sentence" (lists, tables): hard split
            sents.append(" ".join(w[:target]))
            w = w[target - overlap:]
        sents.append(" ".join(w))
    chunks, cur = [], []
    for s in sents:
        if cur and sum(len(x.split()) for x in cur) + len(s.split()) > target:
            chunks.append(" ".join(cur))
            carry, n = [], 0
            for x in reversed(cur):
                if n + len(x.split()) > overlap:
                    break
                carry.insert(0, x)
                n += len(x.split())
            cur = carry
        cur.append(s)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


# ── record → page grouping ────────────────────────────────────────────────────
SOURCES = {"nimh": "nimh", "wiki": "wikipedia", "nhs": "nhs", "helpguide": "helpguide", "mayo": "mayo_clinic"}


def source_of(filename: str) -> str:
    return next((v for k, v in SOURCES.items() if k in filename.lower()), "unknown")


def page_url(record: dict) -> str:
    meta = record.get("metadata") or {}
    url = record.get("url") or meta.get("url") or ""
    return url.split("#")[0]


def page_title(record: dict) -> str:
    meta = record.get("metadata") or {}
    return (record.get("title") or meta.get("article_title") or meta.get("page_title") or "Untitled").strip()


def sections_of(record: dict) -> list[tuple[str, str]]:
    if record.get("sections"):                                  # nhs / helpguide / mayo
        return [(h.strip(), b) for h, b in record["sections"].items()]
    meta = record.get("metadata") or {}                         # nimh / wikipedia: one section per record
    return [((meta.get("section_title") or "General").strip(), record.get("raw_text") or "")]


def build_pages(raw_file: Path) -> list[dict]:
    source = source_of(raw_file.name)
    pages: "OrderedDict[str, dict]" = OrderedDict()
    for line in raw_file.open(encoding="utf-8"):
        if not line.strip():
            continue
        rec = json.loads(line)
        url = page_url(rec)
        if not url:
            continue
        title = page_title(rec)
        if source == "helpguide":       # the scraper glued title and subtitle: "BurnoutSymptoms, Treatment…"
            title = re.sub(r"(?<=[a-z’'])(?=[A-Z])", ": ", title, count=1)
        page = pages.setdefault(url, {"title": title, "sections": OrderedDict()})
        for heading, body in sections_of(rec):
            page["sections"].setdefault(heading, body)       # duplicate records / sections: first wins
    out = []
    for url, page in pages.items():
        sample = " ".join(page["sections"].values())
        if not is_english(sample):
            continue
        chunks, pending = [], ""
        for heading, body in page["sections"].items():
            if SKIP_HEADINGS.search(heading):
                continue
            text = clean_text(body)
            if not text or is_navigation(text):
                continue
            if len(text.split()) < MIN_SECTION_WORDS:       # tiny section: carry into the next chunk
                pending = f"{pending} {heading}: {text}".strip()
                continue
            if pending:
                text, pending = f"{pending}\n{text}", ""
            for piece in pack(text):
                chunks.append({"heading": heading, "text": piece, "chunk_type": classify_chunk(heading, piece)})
        if pending and chunks:
            chunks[-1]["text"] += " " + pending
        if chunks:
            out.append({"doc_id": hashlib.md5(url.encode()).hexdigest()[:16], "source": source, "url": url,
                        "title": page["title"], "language": "en", "chunks": chunks})
    return out


def run_pipeline(raw_dir: Path = RAW_DIR, out_dir: Path = PROC_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    seen_texts: set[str] = set()
    stats = {}
    for raw in sorted(raw_dir.glob("*.jsonl")):
        pages = build_pages(raw)
        n_chunks = n_dupes = 0
        for p in pages:
            kept = []
            for i, c in enumerate(p["chunks"]):
                h = hashlib.sha256(re.sub(r"\s+", " ", c["text"].lower()).encode()).hexdigest()
                if h in seen_texts:
                    n_dupes += 1
                    continue
                seen_texts.add(h)
                c["chunk_id"] = hashlib.md5(f"{p['url']}::{i}::{h[:12]}".encode()).hexdigest()
                c["words"] = len(c["text"].split())
                kept.append(c)
            p["chunks"] = kept
            n_chunks += len(kept)
        pages = [p for p in pages if p["chunks"]]
        with open(out_dir / f"{raw.stem}_clean.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for p in pages:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        stats[raw.stem] = {"pages": len(pages), "chunks": n_chunks, "duplicate_chunks_dropped": n_dupes}
        print(f"{raw.stem:32s} pages={len(pages):4d} chunks={n_chunks:5d} duplicates_dropped={n_dupes}")
    return stats


if __name__ == "__main__":
    run_pipeline()
