"""User memory: structured facts + semantic notes (pgvector).

Facts are authoritative key/value JSON (opt-in writes).
Notes are free-form and retrieved semantically via Ollama embeddings.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from src.api.rag import ollama_embed_one
from src.core.config import config
from src.domain.identity import get_identity
from src.infrastructure.db import db

_SECRET_RE = re.compile(
    r"(?:\bapi[\s_-]*key\b|\btoken\b|\bpassword\b|\bsecret\b|-----BEGIN|sk-[A-Za-z0-9]{10,})",
    re.IGNORECASE,
)


def _enabled() -> bool:
    return bool(getattr(config, "AGENT_MEMORY_ENABLED", True))


def _require_identity() -> tuple[int, uuid.UUID]:
    tid, uid = get_identity()
    if uid is None:
        raise ValueError("No user identity")
    return tid, uid


def _reject_secrets(text: str) -> None:
    if _SECRET_RE.search(text or ""):
        raise ValueError("refusing to store secrets (token/password/key-like content detected)")


def fact_upsert_for_identity(
    *,
    key: str,
    value_json: Any,
    workspace_id: uuid.UUID | None = None,
    confidence: float | None = None,
    source: str | None = None,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    if not _enabled():
        raise ValueError("memory is disabled on this server")
    _require_identity()
    if isinstance(value_json, str):
        _reject_secrets(value_json)
    return db.memory_fact_upsert(
        key=key,
        value_json=value_json,
        workspace_id=workspace_id,
        confidence=confidence,
        source=source,
        expires_at=expires_at,
    )


def fact_list_for_identity(
    *,
    workspace_id: uuid.UUID | None = None,
    prefix: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if not _enabled():
        return []
    _require_identity()
    return db.memory_fact_list(workspace_id=workspace_id, prefix=prefix, limit=limit)


def fact_delete_for_identity(*, key: str, workspace_id: uuid.UUID | None = None) -> bool:
    if not _enabled():
        raise ValueError("memory is disabled on this server")
    _require_identity()
    return db.memory_fact_delete(key=key, workspace_id=workspace_id)


def note_add_for_identity(
    *,
    text: str,
    workspace_id: uuid.UUID | None = None,
    tags: list[str] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    if not _enabled():
        raise ValueError("memory is disabled on this server")
    _require_identity()
    t = (text or "").strip()
    _reject_secrets(t)
    emb = ollama_embed_one(t)
    nid = db.memory_note_insert(text=t, embedding=emb, tags=tags, source=source, workspace_id=workspace_id)
    return {"ok": True, "id": nid}


def note_search_for_identity(
    *,
    query: str,
    workspace_id: uuid.UUID | None = None,
    tags: list[str] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if not _enabled():
        return []
    _require_identity()
    q = (query or "").strip()
    if not q:
        return []
    emb = ollama_embed_one(q)
    return db.memory_note_vector_search(query_embedding=emb, workspace_id=workspace_id, tags=tags, limit=limit)


def note_delete_for_identity(*, note_id: int) -> bool:
    if not _enabled():
        raise ValueError("memory is disabled on this server")
    _require_identity()
    return db.memory_note_soft_delete(int(note_id))


def render_memory_context(
    *,
    workspace_id: uuid.UUID | None,
    user_query: str,
    facts_limit: int = 40,
    notes_limit: int = 6,
) -> str:
    """Build a compact system snippet. Caller decides where to inject it."""
    if not _enabled():
        return ""
    facts_global = fact_list_for_identity(workspace_id=None, limit=facts_limit)
    facts_ws = fact_list_for_identity(workspace_id=workspace_id, limit=facts_limit) if workspace_id else []
    merged: dict[str, dict[str, Any]] = {str(f["key"]): f for f in facts_global}
    for f in facts_ws:
        merged[str(f["key"])] = f
    notes = note_search_for_identity(query=user_query, workspace_id=workspace_id, limit=notes_limit)

    if not merged and not notes:
        return ""

    lines: list[str] = []
    lines.append("[User memory — facts]")
    if merged:
        for k in sorted(merged.keys()):
            v = merged[k].get("value_json")
            lines.append(f"- {k}: {v!r}")
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("[User memory — notes]")
    if notes:
        for i, n in enumerate(notes[:notes_limit], 1):
            txt = str(n.get("text") or "").strip().replace("\n", " ")
            if len(txt) > 280:
                txt = txt[:280] + "…"
            tag_s = n.get("tags") or []
            tag_str = ", ".join(tag_s) if isinstance(tag_s, list) and tag_s else ""
            lines.append(f"{i}) {txt}" + (f" (tags: {tag_str})" if tag_str else ""))
    else:
        lines.append("(none)")
    return "\n".join(lines).strip()

