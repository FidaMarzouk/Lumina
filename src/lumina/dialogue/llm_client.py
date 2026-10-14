# ── llm_client.py ─────────────────────────────────────────────────────────────
# Lumina — LLM client
#
# Responsible for ONE thing only: send a list of messages to the configured LLM and
# return the text.  Prompt building lives in empathy_engine.py; safety decisions and the
# turn flow live in lumina/orchestrator.py.
#
# Providers (lumina/config.py, LLM_PROVIDER): local Ollama (default) or Groq — both
# OpenAI-compatible, so one client serves both.
# ──────────────────────────────────────────────────────────────────────────────

import logging

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from ..config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MAX_TOKENS, LLM_MODEL, LLM_PROVIDER, LLM_TEMPERATURE, LLM_TIMEOUT_S,
)

log = logging.getLogger(__name__)

_client = None


class LLMUnavailable(RuntimeError):
    """The LLM could not produce a reply (connection, rate limit, provider error)."""


def check_llm_configured() -> None:
    if LLM_PROVIDER == "groq" and not LLM_API_KEY:
        raise EnvironmentError("LLM_PROVIDER=groq but GROQ_API_KEY is not set (add it to .env).")


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        check_llm_configured()
        _client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=LLM_TIMEOUT_S, max_retries=1)
    return _client


def complete(messages: list[dict], *, json_mode: bool = False, max_tokens: int | None = None,
             temperature: float | None = None) -> str:
    """Return the assistant text for `messages`, or raise LLMUnavailable.

    json_mode asks the provider for a single JSON object (Ollama and Groq both support it); it is used
    for memory extraction and summaries, never for replies.
    """
    extra = {"response_format": {"type": "json_object"}} if json_mode else {}
    try:
        response = _get_client().chat.completions.create(
            model=LLM_MODEL, messages=messages,
            temperature=LLM_TEMPERATURE if temperature is None else temperature,
            max_tokens=max_tokens or LLM_MAX_TOKENS, **extra,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise LLMUnavailable("empty completion")
        return text
    except RateLimitError as exc:
        log.error("LLM rate limit hit (%s)", LLM_PROVIDER)
        raise LLMUnavailable("rate limit") from exc
    except (APIConnectionError, APITimeoutError) as exc:
        log.error("Could not reach the LLM (%s at %s)", LLM_PROVIDER, LLM_BASE_URL)
        raise LLMUnavailable("connection") from exc
    except APIStatusError as exc:
        log.error("LLM provider error: %s", exc.status_code)
        raise LLMUnavailable(f"status {exc.status_code}") from exc
