"""
retriever.py
------------
Query-time retrieval for the mental health RAG system.
Embeds an incoming user question and returns the top-k most
similar chunks from ChromaDB, ready to be injected into an LLM prompt.
"""

import logging
from typing import Optional

from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

from ..config import COLLECTION_NAME, EMBEDDING_MODEL, VECTORSTORE_PATH, MIN_SIMILARITY


# ─────────────────────────────────────────────
# CONFIG  (shared with lumina/knowledge/embed_and_store.py through lumina/config.py)
# ─────────────────────────────────────────────

log = logging.getLogger(__name__)

VECTORSTORE_DIR = VECTORSTORE_PATH
EMBED_MODEL     = EMBEDDING_MODEL

# Chunk types present in your data — used for optional filtering
VALID_CHUNK_TYPES = {
    "overview", "symptoms", "causes", "treatment",
    "advice", "general", "statistics", "rights_legal",
}   # must match lumina/knowledge/cleaning.py CHUNK_TYPE_RULES (+ "general")


# ─────────────────────────────────────────────
# RETRIEVER CLASS
# ─────────────────────────────────────────────

class MentalHealthRetriever:
    """
    Loads the embedding model and ChromaDB collection once,
    then answers repeated queries efficiently.

    Usage
    -----
        retriever = MentalHealthRetriever()

        results = retriever.query("What are the symptoms of anxiety?", top_k=4)
        context = retriever.format_context(results)
    """

    def __init__(self):
        from ..nlp.models import _device
        self.model = SentenceTransformer(EMBED_MODEL, device="cuda" if _device() == 0 else "cpu")
        if not VECTORSTORE_DIR.exists():
            raise FileNotFoundError(
                f"Vector store not found at '{VECTORSTORE_DIR}'. "
                "Run `python -m lumina.knowledge.build_knowledge_base` first."
            )
        client = chromadb.PersistentClient(
            path=str(VECTORSTORE_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = client.get_collection(COLLECTION_NAME)
        log.info("Retriever ready: %d chunks in %s", self.collection.count(), VECTORSTORE_DIR)

    # ── Core query ──────────────────────────────

    def query(
        self,
        user_question: str,
        top_k: int = 4,
        chunk_type: Optional[str] = None,
        source: Optional[str] = None,
        min_similarity: Optional[float] = None,
    ) -> list[dict]:
        """
        Embed the user question and retrieve the top-k most similar chunks.

        Parameters
        ----------
        user_question : str
            The raw question from the user.
        top_k : int
            Number of chunks to return (3–5 recommended).
        chunk_type : str, optional
            Filter by chunk type before similarity search.
            Options: 'overview', 'symptoms', 'causes', 'treatment',
                     'advice', 'general', 'statistics', 'rights_legal'
        source : str, optional
            Filter by source before similarity search.
            Options: 'nimh', 'wikipedia', 'helpguide', 'mayo_clinic', 'nhs'
        min_similarity : float, optional
            Cosine-similarity floor; defaults to config.MIN_SIMILARITY.

        Returns
        -------
        list[dict]
            Each dict contains: text, score, title, heading,
            source, url, chunk_type, doc_id
        """
        if not user_question.strip():
            raise ValueError("user_question cannot be empty.")

        # Build optional metadata filter for Chroma
        where_filter = self._build_filter(chunk_type, source)

        # Embed the query
        query_vector = self.model.encode(user_question, normalize_embeddings=True).tolist()

        # Run similarity search
        kwargs = dict(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        if where_filter:
            kwargs["where"] = where_filter

        results = self.collection.query(**kwargs)

        # Parse raw results
        parsed = self._parse_results(results)

        floor = MIN_SIMILARITY if min_similarity is None else min_similarity
        filtered = [r for r in parsed if r.get("score", 0) >= floor]

        # Return up to top_k of the filtered, already-sorted list
        return filtered[:top_k]

    # ── Context formatting for LLM prompt ───────

    def format_context(self, results: list[dict]) -> str:
        """
        Format retrieved chunks into a clean context block
        ready to be inserted into an LLM system/user prompt.

        Example output
        --------------
        [Source: Mayo Clinic — Anxiety disorders | Section: Symptoms]
        Common anxiety signs and symptoms include feeling nervous ...

        [Source: NHS — Returning to work after mental health issues | Section: Introduction]
        If you've had a mental health problem and been off work ...
        """
        if not results:
            return "No relevant information found in the knowledge base."

        parts = []
        for i, r in enumerate(results, 1):
            header = (
                f"[{i}] Source: {r['source'].upper()} — {r['title']} "
                f"| Section: {r['heading']} "
                f"| Type: {r['chunk_type']} "
                f"| Relevance: {r['score']:.2f}"
            )
            parts.append(f"{header}\n{r['text']}")

        return "\n\n".join(parts)

    def build_prompt_messages(
        self,
        user_question: str,
        results: list[dict],
        system_intro: str = (
            "You are a compassionate and knowledgeable mental health assistant. "
            "Answer the user's question using ONLY the provided context. "
            "If the context does not contain enough information, say so honestly. "
            "Never fabricate medical advice."
        ),
    ) -> list[dict]:
        """
        Build a messages list (OpenAI / Anthropic format) with the
        retrieved context injected, ready to pass to any LLM.

        Returns
        -------
        list[dict]  e.g. [{"role": "system", ...}, {"role": "user", ...}]
        """
        context = self.format_context(results)
        user_content = (
            f"Use the following knowledge base excerpts to answer the question.\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"QUESTION: {user_question}"
        )
        return [
            {"role": "system", "content": system_intro},
            {"role": "user",   "content": user_content},
        ]

    # ── Diagnostics ──────────────────────────────

    def peek(self, n: int = 5) -> list[dict]:
        """Return n random chunks from the store — useful for sanity checking."""
        result = self.collection.get(limit=n, include=["documents", "metadatas"])
        return [
            {"text": doc, **meta}
            for doc, meta in zip(result["documents"], result["metadatas"])
        ]

    def collection_stats(self) -> dict:
        """Return high-level stats about what's stored."""
        total = self.collection.count()
        sample = self.collection.get(limit=total, include=["metadatas"])
        sources = {}
        types   = {}
        for meta in sample["metadatas"]:
            s = meta.get("source", "unknown")
            t = meta.get("chunk_type", "unknown")
            sources[s] = sources.get(s, 0) + 1
            types[t]   = types.get(t, 0) + 1
        return {"total_chunks": total, "by_source": sources, "by_chunk_type": types}

    # ── Private helpers ───────────────────────────

    def _build_filter(
        self,
        chunk_type: Optional[str],
        source: Optional[str],
    ) -> Optional[dict]:
        """Build a Chroma $and / single-field where filter."""
        conditions = []
        if chunk_type:
            if chunk_type not in VALID_CHUNK_TYPES:
                raise ValueError(
                    f"Invalid chunk_type '{chunk_type}'. "
                    f"Choose from: {sorted(VALID_CHUNK_TYPES)}"
                )
            conditions.append({"chunk_type": {"$eq": chunk_type}})
        if source:
            conditions.append({"source": {"$eq": source}})

        if len(conditions) == 0:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _parse_results(self, raw: dict) -> list[dict]:
        """Convert Chroma's raw query output into clean dicts."""
        parsed = []
        docs      = raw["documents"][0]
        metadatas = raw["metadatas"][0]
        distances = raw["distances"][0]

        for doc, meta, dist in zip(docs, metadatas, distances):
            # Chroma cosine distance d = 1 - cos.  Score = cosine similarity (was 1 - d/2, which squeezed
            # every result into ~0.85–0.90 and made MIN_SIMILARITY filter nothing).
            score = 1 - dist
            parsed.append({
                "text":       doc,
                "score":      round(score, 4),
                "doc_id":     meta.get("doc_id", ""),
                "title":      meta.get("title", ""),
                "source":     meta.get("source", ""),
                "url":        meta.get("url", ""),
                "heading":    meta.get("heading", ""),
                "chunk_type": meta.get("chunk_type", ""),
                "split_index":  meta.get("split_index", 0),
                "total_splits": meta.get("total_splits", 1),
            })

        # Sort by score descending (Chroma usually does this, but enforce it)
        parsed.sort(key=lambda x: x["score"], reverse=True)
        return parsed


# ─────────────────────────────────────────────
# QUICK TEST  (run this file directly)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    retriever = MentalHealthRetriever()

    # Stats
    stats = retriever.collection_stats()
    print("\n── Collection Stats ──────────────────────────")
    print(f"  Total chunks : {stats['total_chunks']}")
    print(f"  By source    : {stats['by_source']}")
    print(f"  By type      : {stats['by_chunk_type']}")

    # Sample query
    question = "What are the symptoms of anxiety and how is it treated?"
    print(f"\n── Sample Query ──────────────────────────────")
    print(f"  Q: {question}\n")

    results = retriever.query(question, top_k=3)
    for r in results:
        print(f"  [{r['score']:.2f}] {r['source'].upper()} — {r['heading']}")
        print(f"         {r['text'][:120]} …\n")

    print("── Formatted Context Block ───────────────────")
    print(retriever.format_context(results))