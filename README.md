# Lumina

A mental health **support** assistant with:
- emotional support and evidence-based information, by text or by voice;
- optional accounts that remember (as private notes, never the messages): patterns across weeks and months,
  guided journeys with a next step always waiting, and in-conversation insights linking thoughts, feelings and actions;
- a model-first safety layer;
- a market-intelligence pipeline that grounds product decisions in evidence.

Lumina is not a clinician. It does not diagnose or prescribe, and it does not replace professional care.

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
data/                  knowledge/, market/, eval/; index/ is built locally; user/ holds accounts (never in git)
eval/                  runners/ (one script per evaluation), reports/ (their JSON output), datasets/
tests/                 unit + integration tests; tests/regression = real-model crisis suite
notebooks/             exploration: segmentation_v0_* (Phase 1, superseded by market/), dialogue_* (prompt walkthroughs)
reports/               lumina_report.html (generated)
docs/                  audit, evaluation, data collection plan, knowledge-source licensing
```

## Setup
```bash
conda create -n lumina python=3.12 && conda activate lumina
pip install torch --index-url https://download.pytorch.org/whl/cu128    # or the CPU wheel
pip install -e ".[all]"
python -m spacy download en_core_web_sm
cp .env.example .env                       # choose the LLM provider and voices

# Local models (default provider)
ollama pull llama3.1
ollama pull llama-guard3:1b
```

The HuggingFace models, including the Kokoro voice (~330 MB), download on first use.

**Ollama tips.** Set `OLLAMA_KEEP_ALIVE=30m` on the Ollama server so the chat model is not unloaded between messages. On an 8 GB GPU, Llama Guard runs on the CPU by default (`SAFETY_GUARD_NUM_GPU=0`) so that the chat model stays on the GPU.

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
Needs Docker Desktop only (on Windows: WSL 2 backend, and an NVIDIA driver for the GPU). No Python, Node or Ollama on the host.
```bash
cp .env.example .env                         # optional; the defaults work (OLLAMA_BASE_URL is set by compose)
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

The first start downloads ~5 GB of Ollama models and ~2 GB of HuggingFace models, and builds the knowledge
index from `data/knowledge/processed`; later starts take seconds. Accounts live in the `user-data` volume, not in
`data/user/`. After a code change, run `docker compose up -d --build` again. Without an NVIDIA GPU, delete the
`deploy:` block of the `ollama` service (it then runs on CPU, slowly) or set `LLM_PROVIDER=groq` in `.env`.

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
Guests chat exactly as before: nothing is stored. With an account, each conversation is a **session**:

| Feature | How it works |
|---|---|
| **Insights from day one** | After each turn, the LLM writes a short CBT note in the background: the situation, thoughts, feelings and behaviours stated in the message, validated and checked by the injection classifier. Once a conversation has enough of these, Lumina offers **one** tentative reflection linking them, and the UI shows the link. |
| **A journey** | Start an *open* session (your own agenda) or a *guided* one, which works through a step of a journey in `configs/journeys/`. When a session ends, the step counts as done, the planner picks the next step (the current journey, or one recommended from recurring themes), and the LLM words the invitation. It is waiting at the next visit. |
| **Patterns** | Each finished session becomes an *episode*: an LLM summary of the notes, with an embedding. `GET /insights/weekly` mines the week (recurring themes, feeling → behaviour links) and links today's story to the most similar earlier episode, preferring one from about a year ago. The LLM writes it up from that evidence only. |
| **Inner weather** | An optional check-in (clear, partly cloudy, foggy, rainy, stormy) at the start of a conversation. It tunes Lumina's opening line and is passed to the reply prompt as context on ordinary turns. It is not stored. |
| **Things that helped** | The per-message extraction also notes what the person says helped them. At the end of a session these are *offered* for their jar; nothing is kept until they choose to, and they can add their own. On a rainy or stormy day, Talk shows what is in the jar. |

**Privacy.** Memory is opt-in (the consent box at sign-up, or the switch in *Your account*). Lumina stores labels,
short paraphrased notes and summaries, **never the messages themselves**, in `data/user/lumina.db`.
People can download everything (`GET /users/me/export`) or delete their account and all of its data
(`DELETE /users/me`). Logs still contain no text.

**Safety.** The safety assessment still runs first. Crisis, elevated-risk and injection turns get no memory, no
reflection and no journey step in the prompt. A session that contained a crisis turn gets no summary and no
journey push, only an open check-in. Every summary, next step and weekly insight goes through the output guard;
weekly insights also go through Llama Guard. If one is rejected, nothing is shown.

API (all except `/chat` need `Authorization: Bearer <token>`): `POST /auth/register|login|logout`, `GET /auth/me`,
`PATCH|DELETE /users/me`, `GET /users/me/export`, `POST /sessions`, `POST /sessions/{id}/end`, `POST /chat`
(with `session_id`), `GET /journeys`, `POST /journeys/{id}/start`, `GET /journey/next`, `POST /journey/steps/complete`,
`GET /insights`, `GET /insights/weekly`, `POST /insights/{id}/feedback`, `GET|POST /jar`, `POST /jar/{id}/keep`,
`DELETE /jar/{id}`.

## Knowledge base
```bash
python -m lumina.knowledge.build_knowledge_base     # clean data/knowledge/raw → processed → data/index/v1 (+ manifest.json)
```

## Safety design, in short
1. **Every message is assessed before anything else.** Three independent layers run:
   - a minimal explicit floor;
   - Llama Guard 3 with a Lumina taxonomy;
   - a trained suicide-risk classifier.

   The highest risk wins, and no layer can cancel another.
2. **Explicit method requests never reach the LLM.** They get a server-side template.
3. **Crisis turns** get a dedicated prompt, and the frontend opens the crisis help sheet. Crisis lines are also one tap away ("Get help") at all times.
4. **Every reply passes an output guard.** It rejects phone numbers and dosages, and on risky turns Llama Guard checks the reply. A rejected reply is replaced with a safe template.
5. **Message text is never logged**, by the chat or the voice endpoint.

## Roadmap
**Done:** audit; safety layer and orchestrator; trained intent classifier; unified repository; robots-compliant
market collection, benchmark and segmentation; knowledge base cleaning; calibrated retrieval; local natural voice;
frontend redesign; accounts with opt-in memory, in-session insights, journeys and weekly pattern insights.

**Next:** emotion, sentiment, retrieval-ranking and generation evaluation (see *Not yet evaluated* in the report);
UI screens for the journey catalogue and the insights history (the API is ready); a larger, reviewed CBT-extraction set.

**Design only:** agent tools; dashboard.
