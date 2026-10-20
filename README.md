# Lumina

A mental health **support** assistant with:
- emotional support and evidence-based information, by text or by voice;
- optional accounts that remember (as private notes, never the messages): patterns across weeks and months,
  guided journeys with a next step always waiting, and in-conversation insights linking thoughts, feelings and actions;
- a model-first safety layer;
- a market-intelligence pipeline that grounds product decisions in evidence.

**Results at a glance:** open `reports/lumina_report.html` in a browser. It is one page, generated from the
pipeline outputs, with every evaluation and market result as charts and tables. `docs/evaluation.md` explains
what the numbers mean and what they do not show.

## Repository layout
```
src/lumina/            the Python package
  safety/              crisis risk (floor + Llama Guard + risk classifier), injection, output guard, templates

  nlp/                 intent (trained classifier), entities, pain points, emotion, sentiment

  rag/                 knowledge-base retrieval (ChromaDB)

  dialogue/            empathy strategy + prompts, LLM client (Ollama / Groq)

  voice/               spoken replies (Kokoro-82M, local)

  auth/                accounts: scrypt password hashes, hashed login tokens, login rate limit

  memory/              personal store (SQLite), CBT-note extraction, session summaries, demo seeder

  insights/            in-session thought → feeling → behaviour links, pattern miner, weekly insights

  journey/             journey catalogue (configs/journeys/*.yaml) and next-step planner

  routes/              API routes for accounts, sessions, journeys and insights

  knowledge/           clinical knowledge ingestion: raw JSONL → cleaned chunks → vector index

  market/              competitor collection, benchmark, review themes, segmentation

  reporting/           builds reports/lumina_report.html from eval/reports/ and data/market/processed/

  orchestrator.py      the fixed turn flow (safety first)

  api.py               FastAPI app: /chat, /tts, plus the routes/ above

frontend/              React + Vite UI: chat, voice orb, voice input/output, crisis help, sign-up / account

configs/market/        competitors, benchmark rules, review codebook, findings (hand-written)

configs/journeys/      guided journeys (CBT thought record, behavioural activation, grounding, sleep, …)

models/                trained artefacts with model cards (models/intent/v1)

data/                  knowledge/, market/, eval/; index/ is built locally; user/ holds accounts

eval/                  runners/ (one script per evaluation), reports/ (their JSON output), datasets/

tests/                 unit + integration tests; tests/regression = real-model crisis suite

notebooks/             exploration: segmentation_v0_* (Phase 1, superseded by market/), dialogue_* (prompt walkthroughs)

reports/               lumina_report.html (generated)

docs/                  audit, evaluation, data collection plan, knowledge-source licensing
```


# Local models (default provider)
ollama pull llama3.1
ollama pull llama-guard3:1b
```

## Run
```bash
uvicorn lumina.api:app --port 8000          # backend
cd frontend && npm install && npm run dev   # UI on http://localhost:5173 (proxies the API to :8000)
python -m lumina.memory.seed_demo           # optional: demo@lumina.local / lumina-demo with 14 months of synthetic history
```

**Voice.** Replies are spoken by Kokoro-82M (Apache-2.0), with a female or male voice chosen in the
UI; nothing is sent to a speech service. It renders about 4× faster than real time on CPU, one sentence at a time.
Without the `voice` extra the UI falls back to the browser's built-in voices.

## Run with Docker

```bash

docker compose up -d --build                 # UI on http://localhost:8080
docker compose logs -f backend               # first start: pulls the models, builds the knowledge index
docker compose exec backend python -m lumina.memory.seed_demo   # optional demo account
docker compose down                          # stop (data is kept; `down -v` deletes it)
```

| Service | What it runs | Data (named volume) |
|---|---|---|
| `frontend` | nginx: the built UI, and the API routes proxied to `backend` | — |
| `backend` | `uvicorn lumina.api:app`, CPU torch | `user-data` (accounts SQLite), `index` (ChromaDB), `hf-cache` (HF models, Kokoro) |
| `ollama` | chat model + Llama Guard, on the GPU | `ollama` |
| `ollama-pull` | one-shot: pulls the models, then exits | — |


## Test, evaluate, report
```bash
pytest                                     # fast offline suite (no models)
pytest -m models tests/regression          # crisis regression suite with the real models (~1 min)
python eval/runners/safety_detection.py    # crisis/injection metrics → eval/reports/*.json
python eval/runners/safety_policy_sweep.py # crisis policy comparison
python eval/runners/intent_classifier.py   # retrain + evaluate intent → models/intent/v1, eval/reports/
python eval/runners/pattern_recall.py      # threshold for linking today's story to an earlier one (synthetic)
python eval/runners/cbt_extraction.py      # CBT-note extraction vs hand labels (live LLM)
python eval/runners/insight_quality.py     # weekly insights for synthetic users (live LLM + guards)
python -m lumina.reporting                 # re-render reports/lumina_report.html after any of the above
```
## Accounts, memory and insights

Guests chat exactly as before: nothing is stored. With an account, each conversation is a **session**.

| Feature | How it works |
|---|---|
| **Insights from day one** | After each turn, the LLM writes a short CBT note in the background, capturing the situation, thoughts, feelings and behaviours stated in the message. The note is validated and checked by the injection classifier. Once enough notes are available, Lumina offers **one** tentative reflection linking them, which is displayed in the UI. |
| **A journey** | Start an *open* session (your own agenda) or a *guided* one, which follows a step from a journey defined in `configs/journeys/`. When a session ends, the step is marked complete. The planner selects the next step from the current journey or recommends one based on recurring themes, and the LLM writes the invitation. It waits for the next visit. |
| **Patterns** | Each completed session becomes an *episode*: an LLM-generated summary of the notes, stored with an embedding. `GET /insights/weekly` analyses the week for recurring themes and feeling-to-behaviour links, then connects today's story to the most similar earlier episode, favouring one from approximately a year ago. The LLM generates the reflection using only this evidence. |
| **Inner weather** | An optional check-in (clear, partly cloudy, foggy, rainy or stormy) at the start of a conversation. It shapes Lumina's opening line and is passed to the reply prompt as context during ordinary turns. It is not stored. |
| **Things that helped** | Per-message extraction also identifies what the person says helped them. At the end of a session, these items are *offered* for their jar; nothing is saved until they choose to keep it. They can also add their own items. On rainy or stormy days, Talk displays what's in the jar. |
| **Privacy** | Memory is opt-in, through the consent box at sign-up or the switch in *Your account*. Lumina stores labels, short paraphrased notes and summaries, **never the messages themselves**, in `data/user/lumina.db`. Users can export their data (`GET /users/me/export`) or delete their account and all associated data (`DELETE /users/me`). Logs contain no text. |
| **Safety** | Safety assessment always runs first. Crisis, elevated-risk and injection turns receive no memory, reflection or journey step in the prompt. A session containing a crisis turn receives no summary or journey progression, only an open check-in. Every summary, next step and weekly insight passes through the output guard; weekly insights also pass through Llama Guard. If an output is rejected, nothing is shown. |
## Knowledge base
```bash
python -m lumina.knowledge.build_knowledge_base     # clean data/knowledge/raw → processed → data/index/v1 (+ manifest.json)
```

## Safety design, in short
1. **Every message is assessed before anything else.** Three independent layers run:
   - a minimal explicit floor;
   - Llama Guard 3 with a Lumina taxonomy;
   - a trained risk classifier.

   The highest risk wins, and no layer can cancel another.
2. **Crisis turns** get a dedicated prompt, and the frontend opens the crisis help sheet. Crisis lines are also one tap away ("Get help") at all times.
3. **Every reply passes an output guard.** It rejects phone numbers and dosages, and on risky turns Llama Guard checks the reply. A rejected reply is replaced with a safe template.
4. **Message text is never logged**, by the chat or the voice endpoint.
