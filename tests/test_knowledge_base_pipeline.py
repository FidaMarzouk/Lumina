"""Knowledge-base cleaning v1 and the v1 index, checked against the data that ships with the project."""
import json

import pytest

from lumina import config
from lumina.knowledge import cleaning as cl

RAW = sorted(config.RAW_DIR.glob("*.jsonl"))
pytestmark = pytest.mark.skipif(not RAW, reason="raw knowledge data not present")


def test_cleaning_is_deterministic_and_matches_committed_output(tmp_path):
    cl.run_pipeline(out_dir=tmp_path / "a")
    cl.run_pipeline(out_dir=tmp_path / "b")
    for f in sorted((tmp_path / "a").glob("*.jsonl")):
        assert f.read_bytes() == (tmp_path / "b" / f.name).read_bytes(), f.name
        committed = config.PROCESSED_DIR / f.name
        if committed.exists():
            assert f.read_bytes() == committed.read_bytes(), f"{f.name}: re-run python -m lumina.knowledge.cleaning"


def test_every_document_has_a_real_page_url_and_sized_chunks():
    for f in sorted(config.PROCESSED_DIR.glob("*.jsonl")):
        for line in f.open(encoding="utf-8"):
            doc = json.loads(line)
            assert doc["url"].startswith("http") and "#" not in doc["url"], doc["url"]
            for c in doc["chunks"]:
                assert 1 <= c["words"] <= cl.TARGET_WORDS + 2 * cl.MIN_SECTION_WORDS, (doc["url"], c["words"])


def test_no_duplicate_chunk_texts_or_ids():
    texts, ids = set(), set()
    for f in sorted(config.PROCESSED_DIR.glob("*.jsonl")):
        for line in f.open(encoding="utf-8"):
            for c in json.loads(line)["chunks"]:
                assert c["chunk_id"] not in ids and c["text"].lower() not in texts
                ids.add(c["chunk_id"]); texts.add(c["text"].lower())


def test_text_rules():
    assert cl.classify_chunk("Moderate exercise", "design of a study") == "general"     # v0: statistics / symptoms
    assert cl.classify_chunk("Signs and symptoms", "") == "symptoms"
    assert cl.is_english("The person is feeling anxious and you can help them with this")
    assert not cl.is_english("Le patient est anxieux et il faut l'aider")
    assert cl.is_navigation("Where can I learn more?\nWhy is NIMH studying this?\nHow is research addressing it?")
    assert not cl.is_navigation("Feeling anxious is a normal part of life and many people worry about health.\n"
                                "Anxiety disorders involve more than temporary worry or fear for most people.\nShort line.")


def test_pack_respects_target_and_overlap():
    text = " ".join(f"Sentence number {i} has exactly seven words." for i in range(100))
    parts = cl.pack(text, target=60, overlap=14)
    assert len(parts) > 5 and all(len(p.split()) <= 60 for p in parts)
    assert parts[0].split()[-14:] == parts[1].split()[:14]                              # whole sentences, <= overlap words


def test_index_matches_processed_chunks(fake_sentence_transformers):
    chromadb = pytest.importorskip("chromadb")
    from chromadb.config import Settings
    from lumina.knowledge import embed_and_store as es
    if not (config.VECTORSTORE_PATH / "manifest.json").exists():
        pytest.skip("index not built")
    ids = {c["id"] for f in sorted(es.PROCESSED_DIR.glob("*.jsonl")) for r in es.load_jsonl(f) for c in es.extract_chunks(r)}
    col = chromadb.PersistentClient(path=str(config.VECTORSTORE_PATH), settings=Settings(anonymized_telemetry=False)) \
                  .get_collection(config.COLLECTION_NAME)
    manifest = json.loads((config.VECTORSTORE_PATH / "manifest.json").read_text(encoding="utf-8"))
    assert set(col.get(include=[])["ids"]) == ids and col.count() == manifest["n_chunks"]


def test_retriever_against_the_index(fake_sentence_transformers):
    chromadb = pytest.importorskip("chromadb")
    from chromadb.config import Settings
    import numpy as np
    if not (config.VECTORSTORE_PATH / "manifest.json").exists():
        pytest.skip("index not built")
    col = chromadb.PersistentClient(path=str(config.VECTORSTORE_PATH), settings=Settings(anonymized_telemetry=False)) \
                  .get_collection(config.COLLECTION_NAME)
    sample = col.get(limit=1, include=["embeddings", "documents", "metadatas"])
    vec, doc, meta = np.array(sample["embeddings"][0]), sample["documents"][0], sample["metadatas"][0]

    class StubModel:
        def __init__(self, *a, **k): pass
        def encode(self, text, **k): return vec

    import lumina.rag.retriever as r
    r.SentenceTransformer = StubModel
    ret = r.MentalHealthRetriever()
    hits = ret.query("anything", top_k=3)
    assert hits[0]["text"] == doc and hits[0]["url"].startswith("http")
    assert hits == sorted(hits, key=lambda h: -h["score"])
    only = ret.query("anything", top_k=3, source=meta["source"])
    assert only and all(h["source"] == meta["source"] for h in only)
