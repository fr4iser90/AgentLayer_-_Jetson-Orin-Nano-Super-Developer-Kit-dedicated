"""Selector-JSON laden (cursor / vscode / windsurf, versioniert)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from apps.backend.integrations.pidea.errors import SelectorNotFoundError
from apps.backend.integrations.pidea.types import SelectorBundle

_PACKAGE_DIR = Path(__file__).resolve().parent
_SELECTORS_ROOT = _PACKAGE_DIR / "selectors"

_IDE_RE = re.compile(r"^[a-z0-9_-]+$")
_VER_RE = re.compile(r"^[0-9][a-zA-Z0-9._-]*$")


def selectors_root() -> Path:
    return _SELECTORS_ROOT


def _validate_ide_version(ide: str, version: str) -> None:
    if not _IDE_RE.match(ide):
        raise ValueError(f"invalid ide: {ide!r}")
    if not _VER_RE.match(version):
        raise ValueError(f"invalid version: {version!r}")


def selector_json_path(ide: str, version: str) -> Path:
    _validate_ide_version(ide, version)
    return _SELECTORS_ROOT / ide / f"{version}.json"


def list_available_versions(ide: str) -> list[str]:
    """Dateinamen ohne ``.json``, sortiert lexikographisch."""
    if not _IDE_RE.match(ide):
        raise ValueError(f"invalid ide: {ide!r}")
    d = _SELECTORS_ROOT / ide
    if not d.is_dir():
        return []
    out: list[str] = []
    for p in d.glob("*.json"):
        out.append(p.stem)
    return sorted(out)


def load_raw(ide: str, version: str) -> dict[str, Any]:
    """Volle Selector-Datei (alle Keys wie ``chatSelectors``, ``commandPaletteSelectors``, …)."""
    path = selector_json_path(ide, version)
    if not path.is_file():
        raise FileNotFoundError(f"selector file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_chat_selectors(ide: str, version: str) -> SelectorBundle:
    """Nur ``chatSelectors`` als flaches ``name → css``-Mapping."""
    data = load_raw(ide, version)
    chat = data.get("chatSelectors")
    if not isinstance(chat, dict):
        raise SelectorNotFoundError(
            "chatSelectors",
            f"missing or invalid chatSelectors in {ide}/{version}.json",
        )
    flat: dict[str, str] = {}
    for k, v in chat.items():
        if isinstance(k, str) and isinstance(v, str) and v.strip():
            flat[k] = v.strip()
    return SelectorBundle(chat=flat, raw=data)


def chat_selector(bundle: SelectorBundle, key: str) -> str:
    """Einzelnen Chat-Selector lesen; :raises: ``SelectorNotFoundError``."""
    s = bundle.chat.get(key)
    if not s:
        raise SelectorNotFoundError(key)
    return s
