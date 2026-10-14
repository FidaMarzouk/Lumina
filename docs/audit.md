# Lumina — Current-State Audit

**Audit date:** 2026-10-11

**Method:** a read-only inspection of the original code. The code was frozen in git commit `a98d283` ("Baseline") and the data in `data/snapshots/v0/` (sha256 manifest).

**Path convention:**
- Paths are relative to the original folders, `Lumina_Phase1/` and `Lumina_Phase2/`.
- Line numbers refer to the baseline commit.

**Evidence labels.** Each finding is labelled:
- **[R]** — read from the code or data.
- **[X]** — confirmed by execution.
- **[U]** — cannot be verified from the repository.

---

## 0. Environment at audit time
- **[X] Python:** the default interpreter is Anaconda **Python 3.14.6**.
- **[X] Packages:** the following are not installed: torch, transformers, sentence-transformers, chromadb, spacy, fastapi, openai, scrapy, google-play-scraper, app-store-scraper, praw, vaderSentiment, loguru, datasets.
- **[X] Consequence:** neither the chatbot nor any scraper can run in that interpreter.
- **[X] Hardware:**
  - NVIDIA RTX 5050 Laptop GPU (8 GB) and 16 GB RAM.
  - Ollama 0.40 is installed, with `llama3.1:latest` (8B) and `nomic-embed-text` already pulled.
- **[R] Phase 1 setup files:** there is no requirements file, config, README or test suite.
  - `Lumina_Phase2/MIGRATION_NOTES.md:25` says Phase 1 "has its own requirements.txt"; it does not.
- **[R] Pinned versions:** Phase 2 pins `fastapi==0.104.1`, `pydantic==2.5.0`, `openai==1.3.0` and `uvicorn==0.24.0`. These are old releases from 2023, and unlikely to install on Python ≥3.13.

## 1. Repository map: how the two phases relate
| Area | Location | What it is |
|---|---|---|
| Market collectors | `Lumina_Phase1/Phase_1_Marketing/collectors1/Scrapers/` | Reddit (JSON), Hugging Face datasets, Medium RSS, App Store/Play, and an App Store HTML parser |
| Market data | `…/Marketing_Data/` | iOS reviews (1,454), derived clean and NLP CSVs, Reddit Replika (459) and Woebot (13), app metadata (10 rows) |
| Benchmark | `…/Benchmark/{benchmark,nlp_process,benchmark_final}.py` | CSV cleaning → NLTK + VADER → keyword-topic benchmark (prints to console only) |
| Segmentation | `…/collectors1/Segmentation/*.ipynb` | Keyword, MiniLM-similarity and zero-shot NLI notebooks, plus age extraction and figures |
| Report | `Lumina_Phase1/Lumina_Market_Analysis.html` | Hand-written HTML; all chart numbers are hardcoded in inline JS |
| Chatbot backend | `Lumina_Phase2/chatbot/` | FastAPI → `llm_client` → `empathy_engine` → `nlp_engine` + `feeling_engine` → Chroma retriever → Moonshot LLM |
| Knowledge base | `Lumina_Phase2/data/{raw,processed,vectorstore}` and `pipelines/` | 5 clinical sources → cleaning → chunking → MiniLM embeddings in Chroma (3,024 chunks) |
| Frontend | `Lumina_Phase2/frontend/` | React 19 + Vite + three.js avatar, browser speech-to-text and text-to-speech |

**How the two phases interact.** There are no code-level links. The only shared elements are:
- **[R] A JSONL record envelope.** It covers `id, source, dataset, collected_at, language, raw_text, metadata, cleaned_text, labels`. Phase 1's Reddit collector and Phase 2's NIMH/Wikipedia raw files both use it.
- **[R] A 14-label pain-point taxonomy.** It appears in both the Phase 1 segmentation and Phase 2's `lexicons/pain_points.py`, in slightly different versions.
- **[R] Market findings in the chatbot.** Market findings, such as crisis escalation and avoiding paywall frustration, influenced the chatbot's design informally.

---

## 2. Clinical safety: critical findings (Phase 2)
| # | Finding | Evidence |
|---|---|---|
| S1 | **Injection detection masks crisis.** The injection check short-circuits *before* the crisis check and returns `crisis_flag=False`. "Pretend you're my friend, I want to kill myself" gets no crisis handling. Several injection phrases are ordinary speech ("you are now", "this is a test", "no restrictions", "for educational purposes", "pretend to be"). | [R] `chatbot/nlp/nlp_engine.py:531-546`, `chatbot/nlp/lexicons/intent_labels.py:224-284` |
| S2 | **False-positive suppression can cancel real crises.** Any false-positive phrase *anywhere* in the message cancels the flag. So does positive sentiment combined with a non-negative emotion. "I overdosed on pills" contains the false-positive phrase "overdosed on". Method requests are not exempt. | [R] `chatbot/dialogue/empathy_engine.py:235-261`, `intent_labels.py:329` |
| S3 | **A suppressed crisis can trigger retrieval of suicide-related chunks.** It also gets no crisis guidance in the prompt. | [R] `empathy_engine.py:149-218, 400-404` |
| S4 | **Crisis replies are free-form LLM generations.** They are constrained only by prompt text, with no check on the output. The resources live only in the frontend banner. | [R] `empathy_engine.py:546-605`; `frontend/src/components/ui/CrisisBanner.jsx` |
| S5 | **988 is labelled "International"; it is the US/Canada line.** Backend error replies also say "call or text 988". The Tunisian number "71 391 000" has not been verified. | [R] `CrisisBanner.jsx:19-23`, `chatbot/dialogue/llm_client.py:193,201,208`; [U] Tunisian number |
| S6 | **The client controls history.** `system` roles in client history are accepted. The LLM-written summary of older turns is inserted with the `system` role, so user-controlled text gets system-level trust. History is never safety-scanned, and there is no risk state across turns. | [R] `llm_client.py:119-178` |
| S7 | **Crisis matching is brittle.** It uses plain substring matching on text whose curly apostrophes are not normalised, so "don’t want to live" (typed on a phone) is missed. "od on" matches "go**od on**e"; "cut myself" matches cooking accidents. Slang such as "kms" and "unalive" is not covered. | [R] `nlp_engine.py:140-158`, `intent_labels.py:80+` |
| S8 | **Message content is logged.** The first 60 characters of *every* message are logged at INFO level, which contradicts the "never log the full message" comment. Malformed history turns are logged whole. | [R] `chatbot/api.py:63,78-83`, `llm_client.py:153,155` |
| S9 | **Third-party data flow without consent.** All conversation text goes to Moonshot AI (`kimi-k2.6`), with no consent screen or disclosure. The landing page says "Private & safe". | [R] `chatbot/config.py:74-75`, `frontend/src/components/landing/LandingPage.jsx:43` |
| S10 | **No input length limit.** Very long inputs go untruncated to bart-large-mnli and NER, which could cause errors or 500s. | [R] `api.py:42-44`, `nlp_engine.py:250,449`; [U] behaviour on real models |

## 3. Phase 2: correctness, NLP and RAG
### 3.1 Orchestration and NLP
- **[R] The retrieval "substance" guard never blocks.**
  - `classify_pain_points` always returns at least one label (`nlp_engine.py:288-289`), so `_has_retrieval_substance` is always true (`empathy_engine.py:144`).
  - RAG fires for *any* eligible intent, including "hi" when it is classified as venting.
  - The same cause means the "SITUATION" block (`empathy_engine.py:365`) is always injected. This is why the LLM invents context such as "academic stress", which was seen in `notebooks/intent_eval.ipynb`'s smoke output.
- **[R] Two intent vocabularies.** `empathy_engine` defines light, emotional and informational intent sets (`:69-101`) that `nlp_engine` never emits (it emits venting, seeking_advice, seeking_validation, help_seeking, sharing_experience, crisis and injection). The light and informational prompts are therefore dead code.
- **[R] Overlap and duplication.**
  - Crisis vocabulary is spread over 4 places: `CRISIS_KEYWORDS`, the `CRISIS_SIGNAL` entity patterns, the ideation phrases in `nlp_engine.py:195`, and a crisis label in the zero-shot model that can never be reached.
  - Emotion is detected twice: by `EMOTION_STATE` patterns and by the emotion model.
  - The medication keywords are hard-coded inside a prompt builder (`empathy_engine.py:411`).
  - The two medication rules contradict each other (`:432-436` and `:445`).
- **[R] Model load.** Each message runs 5 transformer models plus spaCy:
  - bart-large-mnli (intent)
  - NLI-MiniLM (pain points)
  - biomedical NER
  - RoBERTa sentiment
  - DistilRoBERTa emotion

  Latency has never been measured.
- **[R] "Empathy" is not a model.** It is an (intent, emotion) → (tone, avoid) lookup (`lexicons/strategy_map.py`) plus prompt templates. That is a reasonable design, but it has never been evaluated.

### 3.2 Knowledge base and retrieval
- **[R] Source URLs are lost for NIMH and Wikipedia.**
  - The stored URL is the record UUID, because `cleaning.py:295-299` prefers `url or id or metadata.url`.
  - Citations are impossible for 1,572 of 3,024 chunks.
  - URL dedup never fires for those sources.
- **[R] Chunks don't fit the embedder.**
  - Sizes are up to 500 words, with a maximum section length of 4,129 words. all-MiniLM-L6-v2 truncates at 256 word-pieces, so the tail of every chunk over roughly 200 words is invisible to retrieval.
  - Of 2,645 section chunks, 829 are over 200 words, 231 are over 500, 307 are under 30 words, and 126 are exact duplicate texts.
- **[R] `MIN_SIMILARITY=0.30` never filters anything.** Scores are computed as `1 - d/2`, so 0.30 corresponds to cosine ≥ −0.4, and the top 3 chunks are always injected (`chatbot/rag/retriever.py:250`).
- **[R] The retrieval query ignores what the user said.** It is built only from entity strings and pain-point labels (`empathy_engine.py:180-197`).
- **[R] chunk_type labels are often wrong.** They come from substring keywords: "rate" matches "moderate", "sign" matches "design", "right" matches "frightening". There are 4 `references` chunks, which the retriever's `VALID_CHUNK_TYPES` does not include.
- **[R] Cleaning leaves noise in.** The English filter is a no-op, because it counts substrings such as "in" and "to" (`cleaning.py:66-71`). NIMH navigation menus survive cleaning.
- **[R] No citations anywhere.** Only bare chunk text reaches the prompt. `retriever.format_context`, which labels each chunk with its source, is never called. The API returns no sources.
- **[R] Re-ingestion leaves stale chunks.** Re-running the embedding upserts but never deletes, and the index has no version.
- **[X] The previous migration verified the store.** Re-chunking reproduces the 3,024 chunk IDs in the shipped Chroma store (`MIGRATION_NOTES.md` §3).

### 3.3 Tests and evaluation
- **[X] `python -m pytest -q` (Python 3.14): 2 failed, 11 passed, 4 skipped.**
  - `test_cleaning_reproduces_the_shipped_processed_files` fails because `cleaning.py:366` writes CRLF on Windows.
  - `test_split_text_overlap` fails because the test does not skip when `chromadb` is missing.
  - The skips are for missing spacy and chromadb.
- **[R] No test touches the real models or the crisis false-positive logic.** The tests use `pain=[]`, which cannot occur in real use.
- **[R] The intent evaluation is weak.** The only metric is 0.848 accuracy, on 165 of 995 items. Those labels are *silver*, generated by keyword rules similar to the heuristics being tested. The eval file `data/eval/clinical_hf_amod_counseling.jsonl` is not shipped.
- **[R] No evaluation of retrieval, emotion, sentiment, empathy, faithfulness or safety exists.**

### 3.4 Other issues
- `logging.basicConfig` is called twice.
- The retriever uses `print`.
- `top_k` defaults are inconsistent: 4 in the retriever, 3 in config.
- `CORS_ORIGINS` is hard-coded.
- Naming is mixed between "HealthMind" and "Lumina".
- The Moonshot key-setup link points to `.cn` while the API is `.ai`.
- `.gitignore` covers only `agenticenv/`.

## 4. Phase 1: data collection
- **[R] No scraper can be imported.**
  - Every collector imports `config` from `collectors1/config.py`, **which does not exist**.
  - `__init__.py:13` imports a missing `kaggle_datasets`.
  - `appstore_scraper.py:287` annotates with `pd.DataFrame` without importing pandas, so it raises a NameError when the class is defined.
- **[R] `web_spider.py` is in fact only a Reddit JSON scraper.**
  - The docstring says PRAW and Scrapy; neither is used.
  - Unauthenticated `.json` access conflicts with Reddit's API terms, which require OAuth.
  - A `break` at L218-219 skips comments for the final page.
  - It only reads the `hot` listing.
- **[R] No collector checks robots.txt.**
- **[R] Retries are uneven.** `_retry_get` (Reddit) and the Medium retry use backoff and handle 429. The App Store and Play scrapers have none, and they duplicate data when re-run (the "skip if done" check counts lines).
- **[R] Medium and Play produce no output.** There is no Medium output or Google Play review output anywhere. `app_store_scraper` targets an Apple endpoint that no longer works [U].
- **[R] The code that produced most of the data is missing:**
  - `ios_reviews_health_companions.csv`
  - `app_metadata_snapshot.csv`
  - the notebook inputs: `reddit_{anxiety,depression,loneliness,mentalhealth,therapy}_cleaned.csv`, `hf_mh_counseling_amod_cleaned.csv`, `hf_emotion_dair_cleaned.csv`. These files are absent too.
  - **all** of Phase 2's clinical raw data (NIMH, Wikipedia, Mayo Clinic, NHS, HelpGuide)
- **[R] Provenance where it can be traced.** The Reddit Replika and Woebot files match `RedditScraper`'s schema, followed by a cleaner that is missing. NIMH and Wikipedia use the same envelope, but no script that produced them is present.

### 4.1 Data inventory (v0)
| File | Rows | Notes |
|---|---|---|
| `ios_reviews_health_companions.csv` | 1,454 | Replika 474 (2025-10 to 2026-05), Woebot 495 (**2022-07 to 2026-03**), Wysa 485 (2024-01 to 2026-05). BOM and padded headers. `developer_response` 100% null. 0 duplicates. |
| `reviews_clean.csv` / `reviews_nlp.csv` | 1,454 | Derived. 25 rows flagged non-English and 68 flagged low-confidence, but never excluded. |
| `reddit_replika_cleaned.*` | 459 | 349 posts and 110 comments. Row 1 is the subreddit FAQ. Not used by any analysis. |
| `reddit_Woebot_cleaned.*` | 13 | Too small to use. |
| `app_metadata_snapshot.csv` | 10 | **Perplexity appears twice**, along with off-topic apps (perplexity, bevel, function-health). |
| Phase 2 `data/raw/*` | nimh 238, wiki 1,036, helpguide 28, mayo 48, nhs 27 | Two different schemas. 23 of the 48 Mayo records are URL duplicates. |

## 5. Phase 1: methodology and report validity
- **[R] Sentiment.** VADER is the only sentiment model, and it labels **117 of 350 one-star reviews (33%) as positive**.
  - Negation handling is dead code (`nlp_process.py:87-100`), because "not" is a stopword and punctuation is stripped first.
  - The "% positive" claims are therefore weak.
- **[R] Benchmark.** The benchmark is a hand-written keyword taxonomy of 24 topics with very generic keywords: "tool", "data", "code", "support", "ai", "friend".
  - "nightmare" and "voice" each sit in two topics.
  - `benchmark_final.py:324` selects the *least* severe "threat" terms, because it takes `.head()` of a list sorted in descending order.
  - Its output only goes to the console.
- **[R] Sampling.** "Newest ~480 iOS reviews per app" covers very different time windows: Replika 7 months, Woebot 4 years. Only 3 apps are compared, and Woebot's consumer app status is [U] (it may have been discontinued in 2025).
- **[R] Segmentation.**
  - **85% of the 14,452-document corpus is dair-ai emotion tweets**, which are not a population of mental-health app users.
  - The "segments" are cosine similarity to 14 fixed label phrases, not clustering.
  - **61% of documents were silently dropped** below the threshold.
  - There is no validation set, no inter-rater check, and no comparison across methods.
- **[R] Age analysis is invalid.**
  - "child" or "kid" is read as the poster being age 9.
  - The NLI "validation" falls through to acceptance on every branch.
  - The keyword notebook buckets NaN ages as "50+" (86% of rows).
  - Coverage is 164 of 5,661 documents, and 29% of the age-identified posters are minors. The report never mentions this, although it matters for safety.
- **[R] Unsupported or contradicted claims in `Lumina_Market_Analysis.html`:**
  - "~210,000 Replika users seeking an alternative" has no derivation.
  - "Replika collapsed to 1.00★ by May 2026" rests on n=4. Monthly averages are 2.6 to 3.1.
  - "Woebot Q1 2026 positive 33.3%" rests on n=3.
  - "13.7% of age-identifiable users are 50+" contradicts the data, which shows about 4–5%.
  - "61%+ under 35" contradicts the data, which shows about 89%.
  - "Six segments via NLP clustering on 14,452 documents" is wrong on both counts: there was no clustering, and there are 8 segments on 5,661 documents.
  - "Global mental health market >$500B" has no citation.
  - The personas, including their location, income and interests, are not supported by any data.
- **[R] Claims that do check out:** the per-app star distributions and averages, VADER means per app, "3 of 474 Replika reviews mention therapy", and the corpus label frequencies.

## 6. Frontend
Paths are under `frontend/src/`.
- **[R] The personality selector is never sent to the backend** (`App.jsx:14`, `api/chat.js`).
- **[R] "New session" does not reset the chat** (`Navbar.jsx:19` together with `App.jsx:25`).
- **[R] The greeting timestamp shows 1970** (`useChat.js:7` → `MessageBubble.jsx:18`).
- **[R] Voice input can send while the crisis modal is open** (`InputBar.jsx:71`).
- **[R] The greeting is never spoken under StrictMode** (`AvatarRoom.jsx:131`).
- **[R] Unused code and dependencies:** `elevenlabs`, `framer-motion`, `EmotionTag.jsx`, `mockResponse.js` (unreachable).
- **[R] Production builds cannot reach the backend.** There is no `VITE_API_URL`; only the dev proxy works (`vite.config.js:12`).
- **[R] The avatar's `<Environment preset="city">` downloads an HDRI from an external CDN at runtime.** Fonts also come from Google, which is a privacy concern.
- **[R] Accessibility gaps:**
  - no `aria-live` region for chat
  - icon buttons have no `aria-label`
  - the crisis modal has no dialog role and no focus trap
  - `outline: none` on inputs
  - low-contrast hint text
  - no handling of `prefers-reduced-motion`
- **[R] No persistence, consent, memory controls or deletion.**

## 7. Worth preserving
- The lazy, thread-safe model handles with `warm_up` (`chatbot/nlp/models.py`) and the central config.
- The intent heuristics plus zero-shot overrides, which is the only component with any measurement.
- The split between crisis-method and crisis-ideation prompts.
- The medication guard intent.
- The injection prompt's "no accusation" design.
- History normalisation and windowing.
- Section-level chunking with stable IDs, and the rich chunk metadata (already enough for citations once the URLs are fixed).
- The test stubs and fakes.
- The JSONL record envelope.
- `RedditScraper._retry_get` and the Medium RSS approach.
- The 1,454 iOS reviews and 459 Replika Reddit items (v0).
- The 14-label pain-point taxonomy.
- The `benchmark_final.py` topic list as a starting codebook.
- React chat, the avatar, and browser speech-to-text and text-to-speech.
- `MIGRATION_NOTES.md`, which is accurate and candid.

## 8. Cannot be verified from the repository
- Where the data came from when its producing script is missing (§4).
- Real model behaviour; to be checked once the environment is installed.
- Licence and terms of reuse for the clinical sources. Mayo Clinic and HelpGuide are copyrighted; NHS content has syndication terms.
- The Tunisian crisis line numbers.
- Woebot's current consumer availability.
- Whether Groq's free-tier data terms are acceptable for mental-health conversations.
