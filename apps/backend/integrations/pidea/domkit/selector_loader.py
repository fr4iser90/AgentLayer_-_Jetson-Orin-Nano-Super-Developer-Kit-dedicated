"""Load selector profiles from ``selectors/<ide>/<version>.json`` (wraps PIDEA loader)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.backend.integrations.pidea.selectors_loader import load_chat_selectors, load_raw, selector_json_path, selectors_root
from apps.backend.integrations.pidea.types import SelectorBundle


def profile_path(ide: str, version: str) -> Path:
    return selector_json_path(ide, version)


def load_bundle(ide: str, version: str) -> SelectorBundle:
    return load_chat_selectors(ide, version)


def load_full_profile(ide: str, version: str) -> dict[str, Any]:
    return load_raw(ide, version)


def selectors_base_dir() -> Path:
    return selectors_root()
