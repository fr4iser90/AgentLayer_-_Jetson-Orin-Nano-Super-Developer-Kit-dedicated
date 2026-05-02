"""Shared helpers for coding tools: path validation, workspace scoping, blocklist enforcement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apps.backend.core import config

try:
    from plugins.tools.agent.core.coding.coding_index_lib import (
        _HAS_TS,
        _SUPPORTED_LANGUAGES,
    )
except ImportError:
    _HAS_TS = False
    _SUPPORTED_LANGUAGES = {}


def _get_workspace_root() -> Path | None:
    """Coding root: /code in Docker, or local workspace for dev."""
    if not config.CODING_ENABLED:
        return None
    
    root = Path("/code")
    if root.exists() and root.is_dir():
        return root
    
    workspace_root = Path("/workspace/AgentLayer")
    if workspace_root.exists() and workspace_root.is_dir():
        return workspace_root
    
    return None


def _disabled_error() -> str:
    return json.dumps(
        {"ok": False, "error": "coding tools are disabled in Admin settings"},
        ensure_ascii=False,
    )


def _no_root_error() -> str:
    return json.dumps(
        {"ok": False, "error": "coding root /code not found - check Docker volume mount"},
        ensure_ascii=False,
    )


def validate_coding_path(rel: str) -> tuple[Path | None, str | None]:
    """
    Resolve *rel* under ``CODING_ROOT`` and enforce the blocklist.

    Returns ``(resolved_path, None)`` on success or ``(None, error_message)``.
    """
    if not config.CODING_ENABLED:
        return None, _disabled_error()
    root = _get_workspace_root()
    if root is None:
        return None, _no_root_error()
    s = (rel or "").strip()
    if not s:
        return None, "path is empty"
    if "\x00" in s:
        return None, "path contains null byte"
    try:
        p = Path(s)
        if p.is_absolute():
            resolved = p.resolve()
        else:
            resolved = (root / p).resolve()
    except (OSError, ValueError) as e:
        return None, f"invalid path: {e}"
    root_r = root.resolve()
    try:
        resolved.relative_to(root_r)
    except ValueError:
        return None, "path escapes the coding root"
    resolved_lower = str(resolved).lower()
    for blocked in config.CODING_PATH_BLOCKLIST:
        if resolved_lower.startswith(blocked):
            return None, f"path is blocked (matches blocklist entry {blocked!r})"
    return resolved, None


def coding_root() -> Path | None:
    """Get the current coding root path."""
    if not config.CODING_ENABLED:
        return None
    return _get_workspace_root()


def is_probably_text(data: bytes) -> bool:
    if not data:
        return True
    return b"\x00" not in data[:8192]


def coalesce_content(arguments: dict[str, Any]) -> tuple[str, str | None]:
    """Extract *content* from arguments, trying ``content``, ``text``, ``source`` keys."""
    for key in ("content", "text", "source"):
        v = arguments.get(key)
        if v is not None:
            s = str(v)
            return s, None
    return "", "content is required (use 'content', 'text', or 'source' key)"
