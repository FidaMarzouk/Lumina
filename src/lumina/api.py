import json
import logging
import threading
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .auth.deps import get_store, optional_user
from .config import (
    CHAT_RATE_LIMITS,
    CORS_ORIGINS,
    MAX_HISTORY_CHARS,
    MAX_HISTORY_TURNS,
    MAX_MESSAGE_CHARS,
    SESSION_SWEEP_MINUTES,
    TTS_MAX_CHARS,
    TTS_RATE_LIMITS,
    TTS_VOICES,
)
from .dialogue.llm_client import check_llm_configured
from .memory.schemas import Weather
from .memory.service import SessionContext
from .memory.store import Store
from .nlp.models import warm_up
from .observability import default_traces
from .orchestrator import respond, respond_stream
from .ratelimit import RateLimiter, client_key, retry_after
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
    traces = default_traces()
    if traces is not None:
        traces.purge()            # turn traces older than TRACE_RETENTION_DAYS
    warm_up()                 # load spaCy + HuggingFace models once, before the first request
    if tts.available():         # voice loads in the background; chat works while it does
        threading.Thread(target=tts.warm_up, name="tts-warm-up", daemon=True).start()
    # The knowledge base opens in the background too (a question arriving meanwhile waits for it, as before).
    from .dialogue.empathy_engine import warm_up_retrieval
    threading.Thread(target=warm_up_retrieval, name="rag-warm-up", daemon=True).start()
    stop = threading.Event()
    threading.Thread(target=_sweep_idle_sessions, args=(stop,), name="session-sweep", daemon=True).start()
    yield
    stop.set()


def _sweep_idle_sessions(stop: threading.Event) -> None:
    """Every SESSION_SWEEP_MINUTES (and once at start), close sessions idle for SESSION_IDLE_HOURS."""
    from .memory import episodes
    while True:
        try:
            episodes.sweep_idle(get_store())
        except Exception as exc:             # a failed sweep is retried next time; it never stops the API
            log.warning("Idle-session sweep failed: %s", type(exc).__name__)
        if stop.wait(SESSION_SWEEP_MINUTES * 60):
            return


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


chat_limiter = RateLimiter(CHAT_RATE_LIMITS)
tts_limiter = RateLimiter(TTS_RATE_LIMITS)


def chat_rate_limit(request: Request, user: dict | None = Depends(optional_user)) -> None:
    """Refuses floods of messages.  The refusal still points to help: someone may be writing in distress."""
    wait = chat_limiter.hit(client_key(request, user))
    if wait is not None:
        log.warning("Chat rate limit hit")
        raise HTTPException(status_code=429, headers={"Retry-After": retry_after(wait)},
                            detail=f"You're sending messages faster than Lumina can answer. Please wait "
                                   f"{retry_after(wait)} seconds and send it again. If you need help right now, "
                                   f"tap \"Get help\" at the top of the screen.")


def tts_rate_limit(request: Request, user: dict | None = Depends(optional_user)) -> None:
    wait = tts_limiter.hit(client_key(request, user))
    if wait is not None:
        raise HTTPException(status_code=429, headers={"Retry-After": retry_after(wait)},
                            detail="Too many voice requests. Please wait a moment.")


@app.post("/chat", response_model=ChatResponse, response_model_exclude_none=True,
          dependencies=[Depends(chat_rate_limit)])
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


@app.post("/chat/stream", dependencies=[Depends(chat_rate_limit)],
          responses={200: {"content": {"application/x-ndjson": {}}}})
def chat_stream(request: ChatRequest, user: dict | None = Depends(optional_user), store: Store = Depends(get_store)):
    """The same turn as /chat, one JSON event per line, so the reply appears sentence by sentence:

        {"type": "delta", "text": …}      add this checked sentence to the reply
        {"type": "replace", "text": …}    replace the reply shown so far with this text
        {"type": "done", "response": …}   the full /chat response (its reply is final); always last
        {"type": "error", "detail": …}    something failed after the stream began

    Only ordinary turns stream; risky and templated replies arrive whole in "done" (lumina/orchestrator).
    Problems found before the first event (empty message, ended session) are normal HTTP errors.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    session = _session_context(request.session_id, user, store) if request.session_id else None
    history = [t.model_dump() for t in request.history]
    extra = {"weather": request.weather} if request.weather else {}
    if session is not None:
        extra["session"] = session

    def events():
        try:
            for event in respond_stream(request.message, history, request.persona, **extra):
                if event["type"] == "done":
                    fields = {k: v for k, v in event["result"].as_dict().items() if k != "debug"}
                    event = {"type": "done",
                             "response": ChatResponse(**fields).model_dump(mode="json", exclude_none=True)}
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as e:
            log.error("Error processing a streamed message: %s", type(e).__name__)
            yield json.dumps({"type": "error", "detail": "Something went wrong. Please try again."}) + "\n"

    # X-Accel-Buffering: nginx would otherwise hold the sentences back until the reply is complete.
    return StreamingResponse(events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


class SpeechRequest(BaseModel):
    text : str = Field(min_length=1, max_length=TTS_MAX_CHARS)
    voice: Literal["female", "male"] = "female"


@app.get("/tts/status")
def tts_status():
    return {"available": tts.available(), "voices": list(TTS_VOICES)}


@app.post("/tts", response_class=Response, responses={200: {"content": {"audio/wav": {}}}},
          dependencies=[Depends(tts_rate_limit)])
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
