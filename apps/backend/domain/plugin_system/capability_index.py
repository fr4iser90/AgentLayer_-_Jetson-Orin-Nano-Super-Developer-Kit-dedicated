"""
Capability index: maps declared ``TOOL_CAPABILITIES`` / per-tool overrides to registered function names.

Convention: use dot-separated ids, e.g. ``mail.read``, ``weather.get`` (domain.action).
The LLM and routers can reason about capabilities without knowing provider brands.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def effective_capabilities_for_tool(meta: dict[str, Any], tool_name: str) -> list[str]:
    """
    Per-function ``capabilities`` in ``per_tool[tool_name]`` override package-level ``capabilities``.
    """
    pt = meta.get("per_tool")
    if isinstance(pt, dict):
        row = pt.get(tool_name)
        if isinstance(row, dict):
            c = row.get("capabilities")
            if isinstance(c, (list, tuple, frozenset, set)):
                out = [str(x).strip() for x in c if str(x).strip()]
                if out:
                    return out
    caps = meta.get("capabilities")
    if isinstance(caps, (list, tuple, frozenset, set)):
        return [str(x).strip() for x in caps if str(x).strip()]
    return []


def build_capability_index(
    tools_meta: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Inverted index: capability (lowercase) -> list of {tool_name, package_id, domain}."""
    idx: dict[str, list[dict[str, Any]]] = {}
    for entry in tools_meta:
        pid = str(entry.get("id") or "").strip()
        domain = (entry.get("domain") or "").strip().lower() or None
        tlist = entry.get("tools")
        if not isinstance(tlist, list):
            continue
        for tn in tlist:
            if not isinstance(tn, str) or not tn.strip():
                continue
            name = tn.strip()
            for cap in effective_capabilities_for_tool(entry, name):
                key = cap.lower()
                idx.setdefault(key, []).append(
                    {
                        "tool_name": name,
                        "package_id": pid,
                        "domain": domain,
                    }
                )
    return idx


def list_tools_without_capabilities(tools_meta: list[dict[str, Any]]) -> list[str]:
    """Registered function names with no effective capability (for migration / admin)."""
    out: set[str] = set()
    for entry in tools_meta:
        tlist = entry.get("tools")
        if not isinstance(tlist, list):
            continue
        for tn in tlist:
            if not isinstance(tn, str) or not tn.strip():
                continue
            name = tn.strip()
            if not effective_capabilities_for_tool(entry, name):
                out.add(name)
    return sorted(out)


def filter_merged_tools_by_capabilities(
    tools: list[Any],
    hints: frozenset[str],
    *,
    tools_meta: list[dict[str, Any]],
) -> list[Any]:
    """
    Keep tools that implement **any** of the given capabilities (case-insensitive), plus introspection.

    If no tool matches, returns the input list unchanged and logs a warning (same pattern as domain filter).
    """
    from apps.backend.domain.plugin_system.tool_routing import TOOL_INTROSPECTION, _tool_name

    if not hints:
        return list(tools)
    hint_lc = {h.strip().lower() for h in hints if str(h).strip()}
    if not hint_lc:
        return list(tools)

    # Build tool_name -> set(caps) from meta (scan once)
    caps_by_tool: dict[str, set[str]] = {}
    for entry in tools_meta:
        tlist = entry.get("tools")
        if not isinstance(tlist, list):
            continue
        for tn in tlist:
            if not isinstance(tn, str) or not tn.strip():
                continue
            name = tn.strip()
            for c in effective_capabilities_for_tool(entry, name):
                caps_by_tool.setdefault(name, set()).add(c.lower())

    allow = set(TOOL_INTROSPECTION)
    for tname, cset in caps_by_tool.items():
        if cset & hint_lc:
            allow.add(tname)

    non_intro = sum(
        1 for tname in allow if tname not in TOOL_INTROSPECTION
    )
    if non_intro == 0:
        logger.warning(
            "agent_capability_hints %s matched no tools with declared capabilities; ignoring filter",
            sorted(hint_lc),
        )
        return list(tools)

    out: list[Any] = []
    for spec in tools:
        n = _tool_name(spec)
        if not n:
            out.append(spec)
            continue
        if n in allow:
            out.append(spec)
    return out
