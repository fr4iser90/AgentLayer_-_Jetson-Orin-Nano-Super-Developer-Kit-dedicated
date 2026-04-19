"""Generate a new selector profile JSON from an existing profile + overrides."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from src.integrations.pidea.domkit.selector_loader import load_full_profile


def merge_chat_selectors(
    base: dict[str, Any],
    overrides: dict[str, str],
    *,
    ide: str,
    version: str,
) -> dict[str, Any]:
    """Deep-copy ``base`` and replace ``chatSelectors`` keys present in ``overrides``."""
    data = copy.deepcopy(base)
    if "chatSelectors" not in data or not isinstance(data["chatSelectors"], dict):
        data["chatSelectors"] = {}
    cs = data["chatSelectors"]
    for k, v in overrides.items():
        if isinstance(v, str) and v.strip():
            cs[k] = v.strip()
    data["_generated"] = {"ide": ide, "version": version, "tool": "pidea.domkit.profile_generator"}
    return data


def write_profile(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def generate_from_base(
    ide: str,
    base_version: str,
    new_version: str,
    overrides: dict[str, str],
    output_path: Path,
) -> dict[str, Any]:
    base = load_full_profile(ide, base_version)
    merged = merge_chat_selectors(base, overrides, ide=ide, version=new_version)
    write_profile(output_path, merged)
    return merged
