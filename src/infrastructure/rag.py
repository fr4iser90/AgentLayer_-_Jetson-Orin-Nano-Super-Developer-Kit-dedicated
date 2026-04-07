"""RAG helpers for tools; implementation lives in ``src.api.rag``."""

from __future__ import annotations

import types

from src.api.rag import (
    chunk_text,
    ingest_for_user,
    ollama_embed_one,
    search_for_identity,
)

rag = types.SimpleNamespace(
    chunk_text=chunk_text,
    ingest_for_user=ingest_for_user,
    ollama_embed_one=ollama_embed_one,
    search_for_identity=search_for_identity,
)
