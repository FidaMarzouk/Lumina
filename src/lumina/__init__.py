"""Lumina — mental health support assistant.

Packages:
    lumina.safety      crisis-risk assessment, injection detection, output guard (runs first, cannot be overridden)
    lumina.nlp         intent, entities, pain points, emotion, sentiment
    lumina.rag         knowledge-base retrieval
    lumina.dialogue    prompts (empathy strategy) and the LLM client
    lumina.knowledge   clinical knowledge ingestion: raw JSONL -> cleaned chunks -> vector index
    lumina.market      market-intelligence collection and analysis (Stage 3-4)
    lumina.orchestrator / lumina.api   the turn flow and the HTTP API
"""
