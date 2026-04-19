"""Capture DOM or accessibility snapshots for debugging / diffing."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def snapshot_html(page: Any, path: Path) -> None:
    """Write ``page.content()`` to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    html = page.content()
    path.write_text(html, encoding="utf-8", errors="replace")


def snapshot_accessibility(page: Any, path: Path) -> None:
    """Write Playwright accessibility tree as JSON (if supported)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tree = page.accessibility.snapshot()
        path.write_text(json.dumps(tree, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as e:
        logger.warning("accessibility snapshot failed: %s", e)
        path.write_text(f'{{"error": "{e!s}"}}\n', encoding="utf-8")
