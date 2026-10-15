# Lumina backend (FastAPI).  Built and run by docker-compose.yml; see "Run with Docker" in README.md.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/cache/hf

# espeak-ng: Kokoro's fallback phonemiser for words outside its dictionary
RUN apt-get update && apt-get install -y --no-install-recommends espeak-ng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU torch: the GPU is left to Ollama (chat model), as on the host setup
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# Dependencies first, so code changes do not reinstall them
COPY pyproject.toml README.md ./
RUN mkdir -p src/lumina && touch src/lumina/__init__.py \
    && pip install -e ".[nlp,rag,llm,api,voice]" \
    && python -m spacy download en_core_web_sm

COPY src ./src
COPY configs ./configs
COPY models ./models
COPY data/knowledge/processed ./data/knowledge/processed
COPY docker/backend-entrypoint.sh /usr/local/bin/lumina-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/lumina-entrypoint && chmod +x /usr/local/bin/lumina-entrypoint

EXPOSE 8000
ENTRYPOINT ["lumina-entrypoint"]
# --proxy-headers: the login rate limit keys on the client address, which nginx passes in X-Forwarded-For
CMD ["uvicorn", "lumina.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
