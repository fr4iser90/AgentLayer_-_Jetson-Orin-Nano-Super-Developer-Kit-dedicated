"""Datentypen für PIDEA (Config, Nachrichten, Selector-Bündel)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConnectionConfig:
    """HTTP-CDP-Endpunkt (wie von ``playwright.chromium.connect_over_cdp`` erwartet)."""

    cdp_http_url: str
    selector_ide: str = "cursor"
    selector_version: str = "1.7.17"
    default_timeout_ms: int = 30_000


@dataclass
class ChatMessage:
    """Eine sichtbare Chat-Zeile aus dem DOM."""

    role: str  # "user" | "assistant"
    text: str


@dataclass
class SelectorBundle:
    """Nur ``chatSelectors`` aus einer IDE-JSON (flaches Mapping name → CSS)."""

    chat: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
