"""
Tool manifest helpers (normalization only).

1. **execution_context** — *where* code is intended to run (policy/UI):
   ``host`` | ``container`` | ``remote`` | ``browser``
2. **domain** (``TOOL_DOMAIN`` on modules) — router / product category; see registry.

Default execution is **container** unless a module sets ``TOOL_EXECUTION_CONTEXT``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

EXECUTION_CONTEXTS = frozenset({"host", "container", "remote", "browser"})
DEFAULT_EXECUTION_CONTEXT = "container"

OS_SUPPORT_VALUES = frozenset({"linux", "windows", "macos", "nixos", "any"})


def normalize_execution_context(raw: str | None) -> str:
    s = (raw or "").strip().lower()
    if s in EXECUTION_CONTEXTS:
        return s
    if raw and raw.strip():
        logger.warning("unknown TOOL_EXECUTION_CONTEXT %r — using %s", raw, DEFAULT_EXECUTION_CONTEXT)
    return DEFAULT_EXECUTION_CONTEXT


def parse_os_support(mod: Any) -> list[str] | None:
    raw = getattr(mod, "TOOL_OS_SUPPORT", None)
    if raw is None:
        return None
    out: list[str] = []
    if isinstance(raw, str):
        parts = [x.strip().lower() for x in raw.replace(";", ",").split(",") if x.strip()]
    elif isinstance(raw, (list, tuple, frozenset, set)):
        parts = [str(x).strip().lower() for x in raw if str(x).strip()]
    else:
        return None
    for p in parts:
        if p in OS_SUPPORT_VALUES or p == "darwin":
            out.append("macos" if p == "darwin" else p)
        else:
            logger.warning("unknown TOOL_OS_SUPPORT value %r ignored", p)
    return out or None


def normalize_risk_level(raw: Any) -> str | None:
    """Return ``l0``…``l3`` or None if unset."""
    if raw is None:
        return None
    if isinstance(raw, int):
        if 0 <= raw <= 3:
            return f"l{raw}"
        return None
    s = str(raw).strip().lower()
    if s in ("l0", "l1", "l2", "l3"):
        return s
    if s.startswith("l") and len(s) == 2 and s[1].isdigit():
        n = int(s[1])
        if 0 <= n <= 3:
            return f"l{n}"
    return None
