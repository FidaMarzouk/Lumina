"""Silver-label the intent pool with a local LLM (Llama 3.1 8B via Ollama), using the taxonomy
definitions in lumina/nlp/intent_taxonomy.py.

These labels are TRAINING labels only ("silver": machine-generated, unreviewed).  The classifier
is evaluated on a separate gold set labelled independently (eval/datasets/intent/gold.jsonl);
agreement between the silver labeller and the gold labels is reported as a label-quality check.

Resumable: already-labelled ids in the output file are skipped.

Run:  python eval/datasets/intent/silver_label.py [--model llama3.1]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
from lumina.nlp.intent_taxonomy import INTENTS  # noqa: E402

POOL = ROOT / "data" / "eval" / "intent" / "pool.jsonl"
OUT = ROOT / "data" / "eval" / "intent" / "silver.jsonl"

SYSTEM = (
    "You label messages that a person might send to a mental health support chatbot. "
    "Choose the ONE intent that best describes why the person is writing.\n\nIntents:\n"
    + "\n".join(f"- {k}: {v}" for k, v in INTENTS.items())
    + "\n\nRules: judge the main purpose of the message; a question about the person's own situation is "
      "seeking_advice or seeking_validation, a general factual question is information; positive news or "
      "everyday chit-chat is casual.\n"
      'Answer with JSON only: {"intent": "<one of the intent names>", "confidence": <0 to 1>}'
)


def label(client: httpx.Client, model: str, text: str) -> dict:
    r = client.post("http://localhost:11434/api/chat", json={
        "model": model, "stream": False, "format": "json", "keep_alive": "30m",
        "options": {"temperature": 0, "num_predict": 40},
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Message: {text}"}],
    })
    r.raise_for_status()
    out = json.loads(r.json()["message"]["content"])
    intent = str(out.get("intent", "")).strip().lower()
    return {"silver": intent if intent in INTENTS else None, "silver_conf": out.get("confidence")}


def main(model: str) -> None:
    done = set()
    if OUT.exists():
        done = {json.loads(l)["id"] for l in OUT.open(encoding="utf-8")}
    pool = [json.loads(l) for l in POOL.open(encoding="utf-8")]
    todo = [r for r in pool if r["id"] not in done]
    print(f"{len(done)} done, {len(todo)} to label")
    t0 = time.time()
    with httpx.Client(timeout=120) as client, OUT.open("a", encoding="utf-8", newline="\n") as f:
        for i, r in enumerate(todo, 1):
            try:
                res = label(client, model, r["text"])
            except Exception as exc:
                res = {"silver": None, "silver_conf": None, "error": type(exc).__name__}
            f.write(json.dumps({**r, **res, "labeller": model}, ensure_ascii=False) + "\n")
            f.flush()
            if i % 100 == 0:
                print(f"{i}/{len(todo)}  {(time.time() - t0) / i:.2f}s/item", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.1")
    main(ap.parse_args().model)
