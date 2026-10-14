"""
lumina/config.py — central configuration: paths, model names, thresholds, LLM provider.
No model name, threshold or path should be hard-coded elsewhere: import it from here.
Secrets and machine-specific values come from the environment / `.env` at the repo root.

    from lumina.config import NER_MODEL, EMOTION_THRESHOLD

Repository data layout (repo root = the folder that contains `src/`):
    data/knowledge/raw/        clinical knowledge documents as collected (*.jsonl)
    data/knowledge/processed/  cleaned + chunked documents (*_clean.jsonl)
    data/index/<version>/      ChromaDB persistent store (rebuildable, not in git)
    data/market/               market-intelligence datasets (v0 = original Phase 1 data)
    data/eval/                 evaluation datasets (see eval/datasets/DATASHEETS.md)
    data/snapshots/v0/         frozen, checksummed copy of the original data (never overwritten)
    models/                    trained artefacts with model cards
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Project paths ─────────────────────────────────────────────────────────────
PROJECT_ROOT     = Path(__file__).resolve().parents[2]
DATA_DIR         = PROJECT_ROOT / "data"
RAW_DIR          = DATA_DIR / "knowledge" / "raw"
PROCESSED_DIR    = DATA_DIR / "knowledge" / "processed"        # cleaned + chunked documents (cleaning v1)
INDEX_VERSION    = os.getenv("LUMINA_INDEX_VERSION", "v1")
VECTORSTORE_PATH = DATA_DIR / "index" / INDEX_VERSION
MARKET_DIR       = DATA_DIR / "market"
MODELS_DIR       = PROJECT_ROOT / "models"

# Only the repo-root .env is read (no upward search from an arbitrary working directory).
load_dotenv(PROJECT_ROOT / ".env")

# ── NLP models ────────────────────────────────────────────────────────────────

# Device for the small HuggingFace classifiers.  Default "cpu": on an 8 GB GPU they otherwise
# compete with the two Ollama models (LLM + Llama Guard), which then evict each other every turn
# (measured: ~17 s/turn with swapping vs ~1.2 s LLM latency when resident).  "auto" = GPU if available.
NLP_DEVICE = os.getenv("NLP_DEVICE", "cpu").lower()

# Pain point zero-shot classifier
# Proven on the Reddit mental health dataset during testing
PAIN_MODEL      = "cross-encoder/nli-MiniLM2-L6-H768"
PAIN_THRESHOLD  = 0.12   # minimum score to include a pain point label
PAIN_TOP_K      = 3      # maximum number of pain points returned per message

# Intent classifier — trained (embeddings + logistic regression); see eval/runners/intent_classifier.py
INTENT_MODEL_DIR      = MODELS_DIR / "intent" / "v1"
INTENT_AMBIGUOUS_BELOW = 0.45   # top-class probability below this → reported as ambiguous (top-2)
INTENT_MODEL    = "facebook/bart-large-mnli"   # legacy zero-shot; used only until the trained model ships

# Sentiment analysis
# cardiffnlp model is trained on Twitter data — handles informal language well
SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"

# Biomedical NER
# d4data/biomedical-ner-all — 8 entity types, best for mental health UGC text
NER_MODEL       = "d4data/biomedical-ner-all"
NER_CONFIDENCE  = 0.65   # entities below this confidence are discarded

# ── Emotion model ─────────────────────────────────────────────────────────────

# 7-class emotion classifier trained on multiple datasets
# Labels: anger, disgust, fear, joy, neutral, sadness, surprise
EMOTION_MODEL     = "j-hartmann/emotion-english-distilroberta-base"
EMOTION_THRESHOLD = 0.70  # below this → default to "neutral" (ambiguous signal)

# ── RAG settings ──────────────────────────────────────────────────────────────

# Sentence embedding model for semantic search
# all-MiniLM-L6-v2 — fast, free, runs locally, good quality
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "mental_health_kb"   # ChromaDB collection (used by ingestion AND retrieval)
TOP_K_RESULTS   = 3     # number of passages retrieved per query
MIN_SIMILARITY  = 0.40  # cosine floor for injecting chunks (eval/reports/retrieval_threshold.json: keeps 95% of
                        # mental-health questions, 7% of small talk; casual intents are also gated out upstream)

# Ingestion (lumina/knowledge/embed_and_store.py). These are the values the shipped vector
# store was built with.  They replaced CHUNK_SIZE=300 / CHUNK_OVERLAP=50, which were
# declared here but never read — ingestion used its own 500 / 50 constants.
MAX_CHUNK_TOKENS      = 500    # chunks longer than this (in words) get split
CHUNK_OVERLAP_TOKENS  = 50     # overlap between split sub-chunks
EMBED_BATCH_SIZE      = 64     # embeddings are generated in batches

# ── Safety layer (lumina/safety) ─────────────────────────────────────────────
# Crisis risk = max(deterministic floor, Llama Guard 3, trained risk classifier).
# No layer can cancel another; sentiment/emotion never influence risk.
OLLAMA_BASE_URL        = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
SAFETY_GUARD_MODEL     = os.getenv("SAFETY_GUARD_MODEL", "llama-guard3:1b")   # Ollama tag
SAFETY_GUARD_TIMEOUT_S = float(os.getenv("SAFETY_GUARD_TIMEOUT_S", "8"))
# 0 = run Llama Guard on CPU (~2.2 s, measured) so the chat LLM stays resident on an 8 GB GPU;
# with both on the GPU Ollama evicted one of them every turn.  Set -1 to let Ollama decide.
SAFETY_GUARD_NUM_GPU   = int(os.getenv("SAFETY_GUARD_NUM_GPU", "0"))
RISK_MODEL             = "vibhorag101/roberta-base-suicide-prediction-phr"   # MIT; binary suicide-risk classifier
RISK_THRESHOLD         = 0.90   # P(suicidal) at or above → crisis (with floor | guard).  Chosen by the user from
                                # eval/reports/safety_policy_sweep.json: clinical crisis recall 0.92, 0.97 crisis-or-elevated,
                                # banner on ~11% of counselling-style posts (vs 21% at 0.45)
RISK_ELEVATED_THRESHOLD = 0.10  # P(suicidal) at or above → elevated (gentler tone only; no banner)
INJECTION_MODEL        = "protectai/deberta-v3-base-prompt-injection-v2"     # Apache-2.0
INJECTION_THRESHOLD    = 0.90   # P(INJECTION) at or above → flagged.  0.28% FPR on mental-health text (eval/reports)
RECENT_RISK_TURNS      = 6      # previous user turns considered for conversation-level risk
# Crisis contact details live only in the frontend banner (frontend/src/components/ui/CrisisBanner.jsx).

# ── Request limits ────────────────────────────────────────────────────────────
MAX_MESSAGE_CHARS   = 2000
MAX_HISTORY_TURNS   = 40
MAX_HISTORY_CHARS   = 4000      # per turn

# ── LLM settings (free tier: local Ollama or Groq) ────────────────────────────
# Both expose an OpenAI-compatible API, so one client serves both.
#   LLM_PROVIDER=ollama  → local, private, no key (default; `ollama pull llama3.1`)
#   LLM_PROVIDER=groq    → hosted, needs GROQ_API_KEY; conversation text leaves the machine
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
_LLM_DEFAULTS = {
    "ollama": {"base_url": f"{OLLAMA_BASE_URL}/v1", "model": "llama3.1"},
    "groq":   {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
}
if LLM_PROVIDER not in _LLM_DEFAULTS:
    raise ValueError(f"LLM_PROVIDER must be one of {sorted(_LLM_DEFAULTS)}, got '{LLM_PROVIDER}'")
LLM_BASE_URL    = os.getenv("LLM_BASE_URL", _LLM_DEFAULTS[LLM_PROVIDER]["base_url"])
LLM_MODEL       = os.getenv("LLM_MODEL", _LLM_DEFAULTS[LLM_PROVIDER]["model"])
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.6"))
LLM_MAX_TOKENS  = int(os.getenv("LLM_MAX_TOKENS", "350"))
LLM_TIMEOUT_S   = float(os.getenv("LLM_TIMEOUT_S", "60"))
HISTORY_WINDOW  = 6        # previous turns sent verbatim to the LLM

# ── API keys (loaded from .env — never hardcode) ──────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_API_KEY  = GROQ_API_KEY if LLM_PROVIDER == "groq" else "ollama"   # Ollama ignores the key

# ── Voice (text-to-speech) ────────────────────────────────────────────────────
# Kokoro-82M (Apache-2.0) runs locally, so spoken replies never leave the machine.  On CPU it renders
# about 4x faster than real time; the frontend requests one sentence at a time so speech starts quickly.
TTS_ENABLED   = os.getenv("TTS_ENABLED", "1") != "0"
TTS_REPO      = "hexgrad/Kokoro-82M"
TTS_DEVICE    = os.getenv("TTS_DEVICE", "cpu")      # cpu keeps the GPU free for the chat model
TTS_VOICES    = {"female": os.getenv("TTS_VOICE_FEMALE", "af_heart"),
                 "male":   os.getenv("TTS_VOICE_MALE", "am_michael")}
TTS_SPEED     = float(os.getenv("TTS_SPEED", "0.95"))  # slightly unhurried
TTS_MAX_CHARS = 600                                    # per request
TTS_SAMPLE_RATE = 24000

# ── Accounts (lumina/auth) ────────────────────────────────────────────────────
USER_DB_PATH        = Path(os.getenv("LUMINA_USER_DB", str(DATA_DIR / "user" / "lumina.db")))   # not in git
AUTH_TOKEN_TTL_DAYS = 30
PASSWORD_MIN_CHARS  = 8
LOGIN_MAX_ATTEMPTS  = 5        # per email + client address …
LOGIN_WINDOW_S      = 60       # … within this many seconds

# ── Personal memory, insights, journeys (lumina/memory, lumina/insights, lumina/journey) ──
# Only derived data is stored: labels, short paraphrased CBT elements and LLM-written summaries —
# never the messages themselves.  Memory is off until the user consents at sign-up or in settings.
MEMORY_EXTRACTION       = os.getenv("MEMORY_EXTRACTION", "1") != "0"   # per-turn CBT extraction (background LLM call)
EXTRACTION_MAX_TOKENS   = 300
SUMMARY_MAX_TOKENS      = 350
WEEKLY_MAX_TOKENS       = 400
MEMORY_TOP_K            = 2      # past episodes recalled into the prompt
MEMORY_MIN_SIMILARITY   = 0.50   # cosine floor for recalling / linking an episode.  eval/reports/pattern_recall.json:
                                 # best trade-off of the sweep (0.45 linked 30% of histories with no real pattern)
INSIGHT_MIN_TURNS       = 3      # user turns with extracted elements before an in-session reflection is offered
INSIGHT_COOLDOWN_TURNS  = 4      # at most one reflection per this many turns
WEEKLY_PERIOD_DAYS      = 7
WEEKLY_MIN_EPISODES     = 2      # sessions with a summary in the period before a weekly insight is written
PATTERN_LOOKBACK_DAYS   = 365    # "a pattern from last year": preferred age of a linked episode …
PATTERN_YEAR_BAND_DAYS  = 75     # … ± this many days, when its similarity is within
PATTERN_YEAR_MARGIN     = 0.10   # … this margin of the closest earlier episode
PATTERN_MIN_GAP_DAYS    = 21     # an episode must be at least this old to count as "from before"
JOURNEY_STEP_MIN_TURNS  = 3      # user turns in a guided session before its step counts as done
JOURNEYS_DIR            = PROJECT_ROOT / "configs" / "journeys"

# ── HTTP API ──────────────────────────────────────────────────────────────────
CORS_ORIGINS = ["http://localhost:5173"]   # the Vite dev server
