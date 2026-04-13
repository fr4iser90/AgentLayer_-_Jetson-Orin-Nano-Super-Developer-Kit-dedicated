"""Resolve (user_id, tenant_id) only from trusted auth — never from spoofable identity headers."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, Request
from starlette.websockets import WebSocket

from src.infrastructure.auth import get_user_for_bearer_token
from src.infrastructure.db import db


def _bearer_raw(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    return auth.removeprefix("Bearer ").strip()


def resolve_chat_identity(request: Request) -> tuple[uuid.UUID, int]:
    """
    Identity for chat, tools, RAG, user APIs: JWT or user API key only.
    Tenant is ``users.tenant_id`` for that user.
    """
    token = _bearer_raw(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authorization: Bearer required (JWT access token or user API key)",
        )
    user = get_user_for_bearer_token(token)
    if user is not None:
        return user.id, db.user_tenant_id(user.id)
    raise HTTPException(status_code=401, detail="invalid or unknown bearer token")


def resolve_tools_list_identity(request: Request) -> tuple[uuid.UUID | None, int]:
    """
    ``GET /v1/tools``: use JWT/API key when Bearer is present and valid;
    otherwise anonymous catalog (no user) with tenant ``1`` — only when middleware allowed the request.
    """
    token = _bearer_raw(request)
    if not token:
        return None, 1
    user = get_user_for_bearer_token(token)
    if user is not None:
        return user.id, db.user_tenant_id(user.id)
    raise HTTPException(status_code=401, detail="invalid bearer token")


def _bearer_raw_ws(websocket: WebSocket) -> str:
    q = (websocket.query_params.get("token") or "").strip()
    auth = (websocket.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        auth = auth[7:].strip()
    return q or auth


def resolve_chat_identity_ws(websocket: WebSocket) -> tuple[uuid.UUID, int]:
    """WebSocket: same rules as ``resolve_chat_identity`` (query ``token=`` or ``Authorization: Bearer``)."""
    token = _bearer_raw_ws(websocket)
    if not token:
        raise HTTPException(status_code=401, detail="missing token (query ?token= or Authorization: Bearer)")
    user = get_user_for_bearer_token(token)
    if user is not None:
        return user.id, db.user_tenant_id(user.id)
    raise HTTPException(status_code=401, detail="invalid or unknown websocket token")
