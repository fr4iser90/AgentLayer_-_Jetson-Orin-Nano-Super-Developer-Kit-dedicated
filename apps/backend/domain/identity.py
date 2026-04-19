"""Per-request tenant/user identity for DB-scoped tools (set from HTTP headers)."""

from __future__ import annotations

import contextvars
import uuid

_identity: contextvars.ContextVar[tuple[int, uuid.UUID | None] | None] = (
    contextvars.ContextVar("agent_identity", default=None)
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


def reset_identity(token: contextvars.Token) -> None:
    _identity.reset(token)
