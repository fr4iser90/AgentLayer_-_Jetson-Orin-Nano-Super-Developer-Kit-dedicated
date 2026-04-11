"""
User-facing tool package presentation (UX layer over registry ids).

Modules may set ``TOOL_UI`` (see module docstring in previous revisions). Category taxonomy
and icons are split across :mod:`tool_ui_constants`, :mod:`tool_ui_defaults`, :mod:`tool_ui_icons`.
"""

from __future__ import annotations

import re
from typing import Any

from src.domain.plugin_system.tool_ui_constants import (
    DOMAIN_CATEGORY_FALLBACK,
    UI_CATEGORY_LABEL,
    UI_CATEGORY_ORDER,
    VALID_UI_CATEGORIES,
    prettify_package_id,
)
from src.domain.plugin_system.tool_ui_defaults import PACKAGE_UI_DEFAULTS
from src.domain.plugin_system.tool_ui_icons import ICON_MAP


def _coerce_order(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    return max(0, min(9999, n))


def _normalize_ui_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    cat = raw.get("category")
    if isinstance(cat, str) and cat.strip():
        c = cat.strip().lower()
        if c in VALID_UI_CATEGORIES:
            out["category"] = c
    disp = raw.get("display_name")
    if isinstance(disp, str) and disp.strip():
        out["display_name"] = disp.strip()
    ic = raw.get("icon")
    if isinstance(ic, str) and ic.strip():
        cleaned = re.sub(r"[^a-z0-9_-]", "", ic.strip().lower())[:64]
        if cleaned:
            out["icon"] = cleaned
    tag = raw.get("tagline")
    if isinstance(tag, str) and tag.strip():
        out["tagline"] = tag.strip()[:400]
    ordv = _coerce_order(raw.get("order"))
    if ordv is not None:
        out["order"] = ordv
    return out


def apply_tool_ui_metadata(mod: Any, entry: dict[str, Any]) -> None:
    """
    Set ``entry["ui"]`` for API / Settings UI. Mutates ``entry``.
    """
    pid = str(entry.get("id") or "").strip() or "unknown"
    domain = str(entry.get("domain") or "").strip().lower()

    merged: dict[str, Any] = dict(PACKAGE_UI_DEFAULTS.get(pid, {}))

    ico = ICON_MAP.get(pid)
    if ico:
        merged.setdefault("icon", ico)

    if not merged.get("category"):
        dc = DOMAIN_CATEGORY_FALLBACK.get(pid) or DOMAIN_CATEGORY_FALLBACK.get(domain)
        if dc and dc in VALID_UI_CATEGORIES:
            merged["category"] = dc
        else:
            merged["category"] = "system"

    if not merged.get("display_name"):
        lab = getattr(mod, "TOOL_LABEL", None)
        if isinstance(lab, str) and lab.strip():
            merged["display_name"] = lab.strip()
        else:
            merged["display_name"] = prettify_package_id(pid)

    if merged.get("order") is None:
        merged["order"] = 500

    tool_ui = getattr(mod, "TOOL_UI", None)
    if isinstance(tool_ui, dict) and tool_ui:
        merged.update(_normalize_ui_overrides(tool_ui))

    cat = merged.get("category", "system")
    if cat not in VALID_UI_CATEGORIES:
        cat = "system"
    merged["category"] = cat

    ui: dict[str, Any] = {
        "category": cat,
        "display_name": str(merged.get("display_name") or prettify_package_id(pid)),
        "order": int(merged.get("order") if merged.get("order") is not None else 500),
    }
    if merged.get("icon"):
        ui["icon"] = merged["icon"]
    if merged.get("tagline"):
        ui["tagline"] = merged["tagline"]

    if not ui.get("tagline"):
        desc = getattr(mod, "TOOL_DESCRIPTION", None)
        if isinstance(desc, str) and desc.strip():
            ui["tagline"] = desc.strip()[:240]

    entry["ui"] = ui
