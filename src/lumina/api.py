import logging
import threading
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .auth.deps import get_store, optional_user
from .config import (
    CORS_ORIGINS,
    MAX_HISTORY_CHARS,
    MAX_HISTORY_TURNS,
    MAX_MESSAGE_CHARS,
    TTS_MAX_CHARS,
    TTS_VOICES,
)
from .dialogue.llm_client import check_llm_configured
from .memory.schemas import Weather
from .memory.service import SessionContext
from .memory.store import Store
from .nlp.models import warm_up
from .orchestrator import respond
from .routes import account, personal
from .voice import tts

# ── Logging ───────────────────────────────────────────────────────────────────
# Privacy: nothing in this service logs message text — only labels, scores and ids.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Start-up ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    check_llm_configured()      # fail fast if the configured provider needs a key that is missing
    from .safety import injection, risk_model  # noqa: F401  (registers the safety models for warm-up)
    try:
        from .memory import embeddings  # noqa: F401  (episode memory embedder, if sentence-transformers is installed)
    except ImportError:
        pass
    get_store().purge_expired_tokens()
    warm_up()                 # load spaCy + HuggingFace models once, before the first request
    if tts.available():         # voice loads in the background; chat works while it does
        threading.Thread(target=tts.warm_up, name="tts-warm-up", daemon=True).start()
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Lumina API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(account.router)
app.include_router(personal.router)


# ── Request / Response models ─────────────────────────────────────────────────
class HistoryTurn(BaseModel):
    role: str = Field(max_length=16)               # "user" | "assistant" | "ai"; anything else is dropped
    content: str | None = Field(default=None, max_length=MAX_HISTORY_CHARS)
    text: str | None = Field(default=None, max_length=MAX_HISTORY_CHARS)   # frontend field name

    model_config = {"extra": "ignore"}


class ChatRequest(BaseModel):
    message: str = Field(max_length=MAX_MESSAGE_CHARS)
    persona: Literal["listener", "friend", "coach", "sage", "calm"] = "listener"   # UI conversation style
    history: list[HistoryTurn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)
    session_id: str | None = Field(default=None, max_length=64)   # signed-in conversations only (POST /sessions)
    weather: Weather | None = None    # the inner-weather check-in, if the person picked one


class Insight(BaseModel):
    """The thought → feeling → behaviour link Lumina reflected on in this reply."""
    situation: str | None = None
    thought  : str | None = None
    feeling  : str | None = None
    behaviour: str | None = None


class ChatResponse(BaseModel):
    reply              : str
    intent             : str
    emotion            : str
    sentiment          : str
    crisis_flag        : bool
    crisis_subtype     : Literal["none", "ideation", "method", "third_party"]
    risk_level         : Literal["none", "elevated", "crisis"]
    injection_detected : bool
    pain_points        : list[str]
    insight            : Insight | None = None     # omitted when there is none (and always for guests)


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "Lumina API is running"}


def _session_context(session_id: str, user: dict | None, store: Store) -> SessionContext:
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in again.")
    session = store.get_session(session_id, user["id"])
    if session is None or session["ended_at"]:
        raise HTTPException(status_code=404, detail="This conversation has ended. Please start a new one.")
    return SessionContext(user_id=user["id"], session_id=session["id"], memory_enabled=bool(user["memory_enabled"]),
                          mode=session["mode"], journey_id=session["journey_id"], step_id=session["step_id"],
                          display_name=user["display_name"])


@app.post("/chat", response_model=ChatResponse, response_model_exclude_none=True)
def chat(request: ChatRequest, user: dict | None = Depends(optional_user), store: Store = Depends(get_store)):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    session = _session_context(request.session_id, user, store) if request.session_id else None

    try:
        history = [t.model_dump() for t in request.history]
        extra = {"weather": request.weather} if request.weather else {}
        if session is None:
            result = respond(request.message, history, request.persona, **extra)
        else:
            result = respond(request.message, history, request.persona, session=session, **extra)
    except Exception as e:
        log.error("Error processing message: %s", type(e).__name__)
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")

    return ChatResponse(**{k: v for k, v in result.as_dict().items() if k != "debug"})


class SpeechRequest(BaseModel):
    text : str = Field(min_length=1, max_length=TTS_MAX_CHARS)
    voice: Literal["female", "male"] = "female"


@app.get("/tts/status")
def tts_status():
    return {"available": tts.available(), "voices": list(TTS_VOICES)}


@app.post("/tts", response_class=Response, responses={200: {"content": {"audio/wav": {}}}})
def speak(request: SpeechRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    try:
        audio = tts.synthesize(request.text, request.voice)
    except tts.TTSUnavailable:
        raise HTTPException(status_code=503, detail="Voice is not available on this server.")
    except Exception as e:
        log.error("Error synthesising speech: %s", type(e).__name__)
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
