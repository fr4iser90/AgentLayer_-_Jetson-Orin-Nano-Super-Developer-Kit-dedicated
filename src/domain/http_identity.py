"""Resolve (user_id, tenant_id) only from trusted auth — never from spoofable identity headers."""

from __future__ import annotations

import os
import secrets
import uuid

from fastapi import HTTPException, Request
from starlette.websockets import WebSocket

from src.infrastructure.auth import get_user_by_id, get_user_for_bearer_token
from src.infrastructure.db import db
from src.infrastructure.operator_settings import stored_optional_connection_key


def _bearer_raw(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    return auth.removeprefix("Bearer ").strip()


def _optional_key_service_user_id() -> uuid.UUID | None:
    """
    When the operator ``optional_connection_key`` matches ``Authorization: Bearer``,
    map that to a fixed DB user (env). Never derive tenant/user from client-supplied
    identity headers.
    """
    raw = (os.environ.get("AGENT_OPTIONAL_KEY_USER_ID") or "").strip()
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def resolve_chat_identity(request: Request) -> tuple[uuid.UUID, int]:
    """
    Identity for chat, tools, RAG, user APIs: JWT/API-key user, or optional shared-secret
    mapped to ``AGENT_OPTIONAL_KEY_USER_ID``. Tenant always ``users.tenant_id`` for that user.
    """
    token = _bearer_raw(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authorization: Bearer required (JWT access token, user API key, or optional connection key)",
        )
    user = get_user_for_bearer_token(token)
    if user is not None:
        return user.id, db.user_tenant_id(user.id)
    expected = stored_optional_connection_key()
    if expected is not None:
        try:
            if secrets.compare_digest(token, expected):
                svc = _optional_key_service_user_id()
                if svc is not None and get_user_by_id(svc) is not None:
                    return svc, db.user_tenant_id(svc)
        except (TypeError, ValueError):
            pass
    raise HTTPException(status_code=401, detail="invalid or unknown bearer token")


def resolve_tools_list_identity(request: Request) -> tuple[uuid.UUID | None, int]:
    """
    ``GET /v1/tools``: use JWT/API key / optional-key service user when Bearer is present and valid;
    otherwise anonymous catalog (no user) with tenant ``1`` — only when middleware allowed the request.
    """
    token = _bearer_raw(request)
    if not token:
        return None, 1
    user = get_user_for_bearer_token(token)
    if user is not None:
        return user.id, db.user_tenant_id(user.id)
    expected = stored_optional_connection_key()
    if expected is not None:
        try:
            if secrets.compare_digest(token, expected):
                svc = _optional_key_service_user_id()
                if svc is not None and get_user_by_id(svc) is not None:
                    return svc, db.user_tenant_id(svc)
        except (TypeError, ValueError):
            pass
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
    expected = stored_optional_connection_key()
    if expected is not None:
        try:
            if secrets.compare_digest(token, expected):
                svc = _optional_key_service_user_id()
                if svc is not None and get_user_by_id(svc) is not None:
                    return svc, db.user_tenant_id(svc)
        except (TypeError, ValueError):
            pass
    raise HTTPException(status_code=401, detail="invalid or unknown websocket token")
