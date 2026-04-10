"""Merge manifest defaults with operator DB policy for tool exposure."""

from __future__ import annotations

from typing import Any

from src.domain.plugin_system.tool_manifest_dimensions import normalize_execution_context
from src.domain.plugin_system.registry import ToolRegistry


def manifest_execution_context(meta_entry: dict[str, Any], tool_fn_name: str) -> str:
    """Package manifest, overridden by ``AGENT_TOOL_META_BY_NAME`` for this function when set."""
    base = meta_entry.get("execution_context")
    per = meta_entry.get("per_tool")
    if isinstance(per, dict):
        pt = per.get(tool_fn_name)
        if isinstance(pt, dict) and isinstance(pt.get("execution_context"), str):
            base = pt["execution_context"]
    return normalize_execution_context(base if isinstance(base, str) else None)


def _pick_execution_context_policy(
    pmap: dict[tuple[str, str], dict[str, Any]],
    package_id: str,
    tool_fn_name: str,
) -> str | None:
    """Non-None when operator row sets an override."""
    rx = pmap.get((package_id, tool_fn_name))
    rs = pmap.get((package_id, "*"))
    if rx is not None:
        v = rx.get("execution_context")
        if isinstance(v, str) and v.strip():
            return normalize_execution_context(v.strip())
    if rs is not None:
        v = rs.get("execution_context")
        if isinstance(v, str) and v.strip():
            return normalize_execution_context(v.strip())
    return None


def effective_execution_context(
    meta_entry: dict[str, Any],
    tool_fn_name: str,
    pmap: dict[tuple[str, str], dict[str, Any]],
) -> str:
    pid = str(meta_entry.get("id") or "").strip()
    ov = _pick_execution_context_policy(pmap, pid, tool_fn_name) if pid else None
    if ov is not None:
        ctx = ov
    else:
        ctx = manifest_execution_context(meta_entry, tool_fn_name)
    try:
        from src.infrastructure.operator_settings import resolved_agent_mode

        if resolved_agent_mode() == "sandbox":
            return "container"
    except Exception:
        pass
    return ctx


def effective_flags(
    meta_entry: dict[str, Any],
    tool_fn_name: str,
    pmap: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Resolved enabled / default_on / user_configurable / execution_context for one tool name."""
    pid = str(meta_entry.get("id") or "").strip()
    m_def = bool(meta_entry.get("default_on", True))
    m_uc = bool(meta_entry.get("user_configurable", True))
    per = meta_entry.get("per_tool")
    if isinstance(per, dict):
        pt = per.get(tool_fn_name)
        if isinstance(pt, dict):
            if "default_on" in pt:
                m_def = bool(pt["default_on"])
            if "user_configurable" in pt:
                m_uc = bool(pt["user_configurable"])
    rs = pmap.get((pid, "*"))
    rx = pmap.get((pid, tool_fn_name))
    enabled = True
    if rx is not None:
        enabled = bool(rx.get("enabled", True))
    elif rs is not None:
        enabled = bool(rs.get("enabled", True))

    def pick_ov(key: str, manifest_val: bool) -> bool:
        if rx is not None and rx.get(key) is not None:
            return bool(rx[key])
        if rs is not None and rs.get(key) is not None:
            return bool(rs[key])
        return manifest_val

    return {
        "enabled": enabled,
        "default_on": pick_ov("default_on", m_def),
        "user_configurable": pick_ov("user_configurable", m_uc),
        "execution_context": effective_execution_context(meta_entry, tool_fn_name, pmap),
    }


def filter_chat_tool_specs(
    specs: list[dict[str, Any]],
    reg: ToolRegistry,
    pmap: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spec in specs:
        fn = spec.get("function") if isinstance(spec, dict) else None
        n = fn.get("name") if isinstance(fn, dict) else None
        if not n:
            out.append(spec)
            continue
        name = str(n)
        meta = reg.meta_entry_for_tool_name(name)
        if not meta:
            out.append(spec)
            continue
        if effective_flags(meta, name, pmap)["enabled"]:
            out.append(spec)
    return out


def filter_tools_meta(
    entries: list[dict[str, Any]],
    pmap: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Drop packages whose every tool is disabled by policy."""
    out: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        names = entry.get("tools")
        if not isinstance(names, list):
            continue
        for tn in names:
            if not isinstance(tn, str):
                continue
            if effective_flags(entry, tn, pmap)["enabled"]:
                out.append(entry)
                break
    return out


def attach_execution_context_by_tool(
    entries: list[dict[str, Any]],
    pmap: dict[tuple[str, str], dict[str, Any]],
) -> None:
    """Mutate copies or entries: add ``execution_context_by_tool`` for API consumers."""
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        names = entry.get("tools")
        if not isinstance(names, list):
            continue
        m: dict[str, str] = {}
        for tn in names:
            if isinstance(tn, str):
                m[tn] = effective_flags(entry, tn, pmap)["execution_context"]
        if m:
            entry["execution_context_by_tool"] = m


def enrich_meta_for_admin(
    entries: list[dict[str, Any]],
    pmap: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach effective{} and tool_effective map for admin UI."""
    rich: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        row = dict(entry)
        names = row.get("tools")
        te: dict[str, Any] = {}
        if isinstance(names, list):
            for tn in names:
                if not isinstance(tn, str):
                    continue
                te[tn] = effective_flags(row, tn, pmap)
        row["tool_effective"] = te
        rs = pmap.get((str(row.get("id") or "").strip(), "*"))
        if rs:
            row["policy_row"] = {
                "enabled": rs.get("enabled"),
                "default_on": rs.get("default_on"),
                "user_configurable": rs.get("user_configurable"),
                "execution_context": rs.get("execution_context"),
            }
        rich.append(row)
    return rich
