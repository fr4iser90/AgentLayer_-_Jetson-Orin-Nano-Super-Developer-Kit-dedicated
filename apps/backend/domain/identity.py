"""Per-request tenant/user identity for DB-scoped tools (set from HTTP headers)."""

from __future__ import annotations

import contextvars
import uuid
from typing import Any

_identity: contextvars.ContextVar[tuple[int, uuid.UUID | None] | None] = (
    contextvars.ContextVar("agent_identity", default=None)
)
_workspace: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("agent_workspace", default=None)
)


def set_identity(tenant_id: int, user_id: uuid.UUID) -> contextvars.Token:
    return _identity.set((tenant_id, user_id))


def get_identity() -> tuple[int, uuid.UUID | None]:
    """
    Current (tenant_id, user_id). If no request context set, returns (1, None).
    Callers that need a user for FK rows must require a non-None user_id themselves.
    """
    v = _identity.get()
    if v is None:
        return (1, None)
    return v


def set_workspace(workspace: dict[str, Any] | None) -> contextvars.Token:
    return _workspace.set(workspace)


def get_workspace() -> dict[str, Any] | None:
    """Current workspace dict with id, name, path, etc."""
    return _workspace.get()


def reset_workspace(token: contextvars.Token) -> None:
    _workspace.reset(token)


def reset_identity(token: contextvars.Token) -> None:
    _identity.reset(token)
