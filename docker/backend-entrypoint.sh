#!/bin/sh
# Builds the knowledge index on first start (it lives in a volume, not in the image), then starts the API.
set -e

INDEX_DIR="/app/data/index/${LUMINA_INDEX_VERSION:-v1}"
if [ ! -f "$INDEX_DIR/chroma.sqlite3" ]; then
    echo "Knowledge index not found in $INDEX_DIR: building it (first start only, a few minutes)..."
    python -m lumina.knowledge.build_knowledge_base --stages embed
fi

exec "$@"
