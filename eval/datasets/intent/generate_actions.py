"""Generate TRAINING examples for the action_request intent (Q3), and near-misses that must not be one.

The real-message pool (pool.jsonl) has no requests for the app to do things, because the app could not do any.
So training examples are written by a local LLM, across six kinds of action and five writing styles, and the
near-misses cover the same topics (sleep, journals, mood, reminders, memory, deleting) written as venting,
advice, information, validation, sharing or small talk.

The test set is separate and hand-written: data/eval/intent/gold_actions.jsonl.  Any generated example within
cosine 0.85 of a test message is dropped, so the test measures generalisation, not recall of near-copies.

Run:  python eval/datasets/intent/generate_actions.py [--model qwen2.5:7b]
Writes data/eval/intent/actions_train.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "eval" / "intent" / "actions_train.jsonl"
TEST = ROOT / "data" / "eval" / "intent" / "gold_actions.jsonl"
MAX_SIMILARITY_TO_TEST = 0.85

ACTIONS = {
    "journal_save": "asks the app to save, note or add something to their private journal",
    "sleep_log": "asks the app to log or track how long or how well they slept",
    "mood_log": "asks the app to log or track their mood or how they feel today",
    "reminder": "asks the app to remind them to do something at a time or on a day",
    "look_up": "asks the app to show, read back or look up what they wrote, logged or tracked before",
    "forget": "asks the app to delete, remove or forget something it keeps about them",
}
STYLES = {
    "curt": "short and to the point, like a command typed on a phone",
    "polite": "polite full sentences",
    "casual_typos": "all lowercase, casual, with abbreviations and a typo or two",
    "with_feelings": "starting with a sentence about how they feel, then the request",
    "indirect": "phrased as a question or a wish rather than a command",
}
TOPICS = {
    "sleep": "sleep, nights, insomnia or tiredness",
    "journal": "journals, diaries or writing things down",
    "mood": "mood, feelings going up and down, or tracking feelings",
    "reminders": "reminders, remembering or forgetting things",
    "memories": "looking back at the past or old memories",
    "deleting": "deleting, removing or letting go of something",
}
NEAR_MISS_INTENTS = {
    "venting": "expresses frustration or pain about it and mainly wants to be heard",
    "sharing_experience": "calmly tells a past experience about it, asking for nothing",
    "seeking_advice": "asks how to cope with or handle something about it",
    "information": "asks a general factual question about it",
    "seeking_validation": "asks whether something about it is normal or okay",
    "casual": "makes small talk or shares good news about it",
}


def ask(client: httpx.Client, model: str, instruction: str, n: int) -> list[str]:
    r = client.post("http://localhost:11434/api/chat", json={
        "model": model, "stream": False, "format": "json", "keep_alive": "30m",
        "options": {"temperature": 0.9, "num_predict": 900},
        "messages": [{"role": "system", "content": (
            "You write realistic example messages that people might type to a mental-health support chat app. "
            "Vary wording, length, details and situations; never repeat a sentence pattern. "
            f'Return JSON only: {{"messages": [{n} strings]}}')},
            {"role": "user", "content": instruction}]})
    r.raise_for_status()
    out = json.loads(r.json()["message"]["content"]).get("messages", [])
    return [" ".join(str(m).split()) for m in out if isinstance(m, str) and 3 <= len(m) <= 300]


def main(model: str) -> None:
    rows = []
    with httpx.Client(timeout=300) as client:
        for kind, what in ACTIONS.items():
            for style, how in STYLES.items():
                for text in ask(client, model, f"Write 10 different messages where the person {what}. Style: {how}.", 10):
                    rows.append({"text": text, "label": "action_request", "kind": kind, "style": style})
            print(f"actions: {kind} done ({len(rows)})", flush=True)
        for topic, about in TOPICS.items():
            for intent, does in NEAR_MISS_INTENTS.items():
                # As many concrete details as a request has (hours slept, a journal, a reminder, a date), so the
                # classifier learns that the ask, not the topic, makes an action (v2's first draft read "I slept
                # badly again, maybe 4 hours" as one).
                instruction = (f"Write 10 different messages about {about}, where the person {does}. Include concrete "
                               "details such as numbers of hours, days, a journal, notes, a reminder or something they "
                               "deleted, but they must NOT ask the app to save, log, track, remind, look up or delete "
                               "anything.")
                for text in ask(client, model, instruction, 10):
                    rows.append({"text": text, "label": intent, "kind": f"near_miss:{topic}", "style": None})
            print(f"near-misses: {topic} done ({len(rows)})", flush=True)

    # drop duplicates and anything too close to the hand-written test set
    from sentence_transformers import SentenceTransformer
    emb = SentenceTransformer("BAAI/bge-small-en-v1.5")
    test = [json.loads(line)["text"] for line in TEST.open(encoding="utf-8")]
    seen, kept, dropped = set(), [], 0
    T = emb.encode(test, normalize_embeddings=True, show_progress_bar=False)
    G = emb.encode([r["text"] for r in rows], normalize_embeddings=True, show_progress_bar=False)
    for r, g in zip(rows, G):
        key = r["text"].lower()
        if key in seen or float((T @ g).max()) >= MAX_SIMILARITY_TO_TEST:
            dropped += 1
            continue
        seen.add(key)
        kept.append({"id": "gen-" + hashlib.sha256(r["text"].encode()).hexdigest()[:10], "source": f"generated:{model}",
                     **r})
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
    print(f"kept {len(kept)}, dropped {dropped} (duplicates or within {MAX_SIMILARITY_TO_TEST} of a test message)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:7b")
    main(ap.parse_args().model)
