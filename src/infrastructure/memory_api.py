"""HTTP API for user memory (facts + semantic notes).

This is a user-facing wrapper around the same storage used by the `memory_*` agent tool.
All operations are scoped to the authenticated chat identity (tenant_id + user_id).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.domain.http_identity import resolve_chat_identity
from src.api import memory as memory_service

router = APIRouter(prefix="/v1/user/memory", tags=["user-memory"])


def _parse_uuid(raw: str | None) -> uuid.UUID | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return uuid.UUID(s)
    except ValueError:
        raise HTTPException(status_code=400, detail="workspace_id must be UUID") from None


class FactUpsertBody(BaseModel):
    workspace_id: str | None = None
    key: str = Field(min_length=1, max_length=256)
    value_json: Any
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str | None = Field(default=None, max_length=256)
    expires_at: str | None = None


@router.post("/facts/upsert")
def upsert_fact(request: Request, body: FactUpsertBody) -> dict:
    resolve_chat_identity(request)  # auth guard; memory_service uses identity internally
    wid = _parse_uuid(body.workspace_id)
    exp: datetime | None = None
    if body.expires_at and body.expires_at.strip():
        try:
            exp = datetime.fromisoformat(body.expires_at.strip())
        except ValueError as e:
            raise HTTPException(status_code=400, detail="expires_at must be ISO timestamp") from e
    try:
        fact = memory_service.fact_upsert_for_identity(
            key=body.key,
            value_json=body.value_json,
            workspace_id=wid,
            confidence=body.confidence,
            source=body.source,
            expires_at=exp,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"ok": True, "fact": fact}


@router.get("/facts")
def list_facts(request: Request, workspace_id: str | None = None, prefix: str | None = None, limit: int = 50) -> dict:
    resolve_chat_identity(request)
    wid = _parse_uuid(workspace_id)
    try:
        facts = memory_service.fact_list_for_identity(workspace_id=wid, prefix=prefix, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"ok": True, "facts": facts, "count": len(facts)}


@router.delete("/facts/{key}")
def delete_fact(request: Request, key: str, workspace_id: str | None = None) -> dict:
    resolve_chat_identity(request)
    wid = _parse_uuid(workspace_id)
    try:
        ok = memory_service.fact_delete_for_identity(key=key, workspace_id=wid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "deleted": bool(ok)}


class NoteAddBody(BaseModel):
    workspace_id: str | None = None
    text: str = Field(min_length=1, max_length=20_000)
    tags: list[str] | None = None
    source: str | None = Field(default=None, max_length=256)


@router.post("/notes")
def add_note(request: Request, body: NoteAddBody) -> dict:
    resolve_chat_identity(request)
    wid = _parse_uuid(body.workspace_id)
    try:
        out = memory_service.note_add_for_identity(
            text=body.text,
            workspace_id=wid,
            tags=body.tags,
            source=body.source,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"ok": True, **out}


@router.get("/notes/search")
def search_notes(
    request: Request,
    query: str,
    workspace_id: str | None = None,
    limit: int = 10,
) -> dict:
    resolve_chat_identity(request)
    wid = _parse_uuid(workspace_id)
    try:
        hits = memory_service.note_search_for_identity(query=query, workspace_id=wid, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"ok": True, "hits": hits, "count": len(hits)}


@router.delete("/notes/{note_id}")
def delete_note(request: Request, note_id: int) -> dict:
    resolve_chat_identity(request)
    try:
        ok = memory_service.note_delete_for_identity(note_id=note_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "deleted": bool(ok)}

