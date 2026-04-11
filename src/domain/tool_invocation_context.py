"""Per-request chat messages visible to tool handlers (set only around :func:`run_tool` from the agent loop)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_tool_invocation_messages: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "tool_invocation_messages", default=None
)


def get_tool_invocation_messages() -> list[dict[str, Any]] | None:
    return _tool_invocation_messages.get()


def set_tool_invocation_messages(messages: list[dict[str, Any]]) -> Token[list[dict[str, Any]] | None]:
    """Shallow copy recommended; handlers must treat messages as read-only."""
    return _tool_invocation_messages.set(messages)


def reset_tool_invocation_messages(token: Token[list[dict[str, Any]] | None]) -> None:
    _tool_invocation_messages.reset(token)
