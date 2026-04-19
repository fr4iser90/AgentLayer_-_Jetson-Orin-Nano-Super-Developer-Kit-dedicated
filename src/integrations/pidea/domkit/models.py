"""Shared dataclasses for the PIDEA DOM toolkit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VersionInfo:
    """Resolved IDE / browser identity."""

    cdp_browser: str | None = None
    cdp_protocol_version: str | None = None
    cdp_user_agent: str | None = None
    cdp_webkit_version: str | None = None
    document_title: str | None = None
    navigator_user_agent: str | None = None
    window_cursor_version: str | None = None
    inferred_cursor_semver: str | None = None
    raw_json_version: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Per-selector validation against a single Page."""

    selector: str
    key: str
    count: int = 0
    visible_count: int = 0
    clickable_count: int = 0
    first_text_sample: str | None = None
    error: str | None = None


@dataclass
class SelectorCandidate:
    """A generated CSS selector with metadata for ranking."""

    css: str
    source: str  # e.g. "data-attr", "aria-label", "role"
    stability_score: float = 0.0
    match_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)
