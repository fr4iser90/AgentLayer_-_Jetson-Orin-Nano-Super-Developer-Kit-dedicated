"""Validate CSS selectors: counts, visibility, clickability, text samples."""

from __future__ import annotations

import logging
from typing import Any

from src.integrations.pidea.domkit.models import ValidationResult

logger = logging.getLogger(__name__)

_MAX_TEXT = 400


def _is_visible(loc: Any) -> bool:
    try:
        return bool(loc.first.is_visible())
    except Exception:
        return False


def _is_clickable(loc: Any) -> bool:
    try:
        el = loc.first
        if not el.is_visible():
            return False
        box = el.bounding_box()
        return box is not None and box.get("width", 0) > 0 and box.get("height", 0) > 0
    except Exception:
        return False


def _first_inner_text(loc: Any) -> str | None:
    try:
        t = loc.first.inner_text(timeout=2_000)
        t = (t or "").strip()
        if len(t) > _MAX_TEXT:
            t = t[:_MAX_TEXT] + "…"
        return t or None
    except Exception as e:
        logger.debug("inner_text: %s", e)
        return None


def validate_selector_on_page(page: Any, key: str, css: str) -> ValidationResult:
    """Evaluate one selector on ``page`` (Playwright sync Page)."""
    css = (css or "").strip()
    if not css:
        return ValidationResult(selector="", key=key, error="empty selector")
    try:
        loc = page.locator(css)
        n = loc.count()
    except Exception as e:
        return ValidationResult(selector=css, key=key, error=str(e))

    vis = clk = 0
    sample: str | None = None
    for i in range(min(n, 50)):
        try:
            nth = loc.nth(i)
            if nth.is_visible():
                vis += 1
            if _is_clickable(nth):
                clk += 1
        except Exception:
            continue
    if n > 0 and sample is None:
        sample = _first_inner_text(loc)

    return ValidationResult(
        selector=css,
        key=key,
        count=n,
        visible_count=vis,
        clickable_count=clk,
        first_text_sample=sample,
    )


def validate_bundle_on_page(page: Any, chat: dict[str, str], keys: list[str] | None = None) -> list[ValidationResult]:
    """Validate a subset of keys (default: all)."""
    ks = keys if keys is not None else sorted(chat.keys())
    out: list[ValidationResult] = []
    for k in ks:
        if k not in chat:
            continue
        out.append(validate_selector_on_page(page, k, chat[k]))
    return out
