"""
lumina/knowledge/embed_and_store.py — build a versioned vector index from the cleaned chunks.

    data/knowledge/processed/*.jsonl  →  data/index/<INDEX_VERSION>/  (ChromaDB + manifest.json)

Chunks are already sized by the cleaning step (~160 words), so nothing is split here.  Every build
recreates the collection, so no stale chunks survive a rebuild (an earlier version only upserted).  The manifest
records what went in: model, chunker version, counts per source, input file hashes, and how many
chunks exceed the embedder's token window.

Run:  python -m lumina.knowledge.embed_and_store
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from lumina import config as _cfg

PROCESSED_DIR = _cfg.PROCESSED_DIR
VECTORSTORE_DIR = _cfg.VECTORSTORE_PATH
COLLECTION_NAME = _cfg.COLLECTION_NAME
EMBED_MODEL = _cfg.EMBEDDING_MODEL
BATCH_SIZE = _cfg.EMBED_BATCH_SIZE


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def extract_chunks(record: dict) -> list[dict]:
    """Flatten one page record into chunk dicts (id, text, metadata) for the index."""
    return [{
        "id": c["chunk_id"], "text": c["text"],
        "doc_id": record["doc_id"], "title": record["title"], "source": record["source"],
        "url": record["url"], "language": record.get("language", "en"),
        "heading": c["heading"], "chunk_type": c["chunk_type"], "split_index": i,
        "total_splits": len(record["chunks"]),
    } for i, c in enumerate(record["chunks"])]


def build_vector_store() -> dict:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer

    files = sorted(PROCESSED_DIR.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"No cleaned files in {PROCESSED_DIR}; run python -m lumina.knowledge.cleaning")
    chunks = [c for f in files for rec in load_jsonl(f) for c in extract_chunks(rec)]

    model = SentenceTransformer(EMBED_MODEL, device="cpu")
    max_tokens = model.max_seq_length
    over = sum(len(model.tokenizer(c["text"])["input_ids"]) > max_tokens for c in chunks)
    embeddings = model.encode([c["text"] for c in chunks], batch_size=BATCH_SIZE, show_progress_bar=True,
                              normalize_embeddings=True).tolist()

    VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR), settings=Settings(anonymized_telemetry=False))
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION_NAME)
    col = client.create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    for s in range(0, len(chunks), BATCH_SIZE):
        b = chunks[s:s + BATCH_SIZE]
        col.add(ids=[c["id"] for c in b], embeddings=embeddings[s:s + BATCH_SIZE],
                documents=[c["text"] for c in b],
                metadatas=[{k: v for k, v in c.items() if k not in ("id", "text")} for c in b])

    from lumina.knowledge.cleaning import CHUNKER_VERSION
    manifest = {
        "index_version": _cfg.INDEX_VERSION, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "embedding_model": EMBED_MODEL, "max_seq_length": max_tokens, "chunker_version": CHUNKER_VERSION,
        "collection": COLLECTION_NAME, "distance": "cosine", "n_chunks": col.count(),
        "chunks_over_token_window": over,
        "chunks_by_source": dict(Counter(c["source"] for c in chunks)),
        "inputs": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
    }
    (VECTORSTORE_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    build_vector_store()
