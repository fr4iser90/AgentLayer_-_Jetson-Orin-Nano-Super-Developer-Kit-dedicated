"""Resolve agent user (and tenant) from the same headers as /v1/chat/completions."""

from __future__ import annotations

import uuid

from fastapi import Request
from starlette.websockets import WebSocket

from src.core.config import config
from src.infrastructure.db import db


def resolve_user_tenant(request: Request) -> tuple[uuid.UUID, int]:
    """Return ``(user_id, tenant_id)`` from WebUI / custom headers."""
    external_sub = config.DEFAULT_EXTERNAL_SUB
    for h in config.USER_SUB_HEADERS:
        v = request.headers.get(h)
        if v is not None and str(v).strip():
            external_sub = str(v).strip()
            break
    raw_tenant = request.headers.get(config.TENANT_ID_HEADER)
    try:
        tenant_hdr = (
            int(str(raw_tenant).strip())
            if raw_tenant and str(raw_tenant).strip()
            else 1
        )
    except (TypeError, ValueError):
        tenant_hdr = 1
    if tenant_hdr < 1:
        tenant_hdr = 1
    return db.ensure_user_external(external_sub, tenant_hdr)


def resolve_user_tenant_ws(websocket: WebSocket) -> tuple[uuid.UUID, int]:
    """Same as ``resolve_user_tenant`` using WebSocket handshake headers."""
    h = websocket.headers
    external_sub = config.DEFAULT_EXTERNAL_SUB
    for hn in config.USER_SUB_HEADERS:
        v = h.get(hn)
        if v is not None and str(v).strip():
            external_sub = str(v).strip()
            break
    raw_tenant = h.get(config.TENANT_ID_HEADER)
    try:
        tenant_hdr = (
            int(str(raw_tenant).strip())
            if raw_tenant and str(raw_tenant).strip()
            else 1
        )
    except (TypeError, ValueError):
        tenant_hdr = 1
    if tenant_hdr < 1:
        tenant_hdr = 1
    return db.ensure_user_external(external_sub, tenant_hdr)
