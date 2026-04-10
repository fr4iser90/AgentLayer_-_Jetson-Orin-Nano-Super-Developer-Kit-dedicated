"""Central JSON registry for admin UI buckets/tags (not derived from filesystem layout)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ALLOWED_ADMIN_BUCKETS = frozenset(
    {
        "files",
        "network",
        "knowledge",
        "secrets",
        "comms",
        "verticals",
        "meta",
        "media",
        "unsorted",
    }
)

_cache: tuple[float, dict[str, Any]] | None = None


def _repo_root() -> Path:
    # src/domain/plugin_system/tool_admin_registry.py → repo root
    return Path(__file__).resolve().parents[3]


def registry_json_path() -> Path:
    raw = (os.environ.get("AGENT_TOOL_ADMIN_REGISTRY") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _repo_root() / "config" / "tool_admin_registry.json"


def invalidate_cache() -> None:
    global _cache
    _cache = None


def _load_document() -> dict[str, Any]:
    global _cache
    path = registry_json_path()
    if not path.is_file():
        return {"packages": {}}
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {"packages": {}}
    if _cache is not None and _cache[0] == mtime:
        return _cache[1]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("tool admin registry unreadable %s: %s", path, e)
        raw = {"packages": {}}
    if not isinstance(raw, dict):
        raw = {"packages": {}}
    pkgs = raw.get("packages")
    if not isinstance(pkgs, dict):
        raw["packages"] = {}
    _cache = (mtime, raw)
    return raw


def apply_admin_metadata(entry: dict[str, Any]) -> None:
    """Set ``admin_bucket`` and optional ``admin_tags`` from ``config/tool_admin_registry.json``."""
    pid = str(entry.get("id") or "").strip()
    doc = _load_document()
    packages = doc.get("packages")
    if not isinstance(packages, dict):
        packages = {}
    row = packages.get(pid) if isinstance(packages.get(pid), dict) else {}
    bucket = str(row.get("bucket") or "unsorted").strip().lower() or "unsorted"
    if bucket not in ALLOWED_ADMIN_BUCKETS:
        logger.warning("unknown admin_bucket %r for package %s — using unsorted", bucket, pid)
        bucket = "unsorted"
    entry["admin_bucket"] = bucket
    tags = row.get("tags")
    if isinstance(tags, (list, tuple)):
        at = [str(x).strip() for x in tags if str(x).strip()]
        if at:
            entry["admin_tags"] = at
