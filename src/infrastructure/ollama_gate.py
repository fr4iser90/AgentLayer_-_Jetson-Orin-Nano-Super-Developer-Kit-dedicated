"""Serialize HTTP calls to Ollama (one in flight) for small GPUs / Jetson.

Async handlers must not hold threading.Lock across await — use
``await asyncio.to_thread(ollama_post_json, ...)`` (see ``domain.agent``).
"""

from __future__ import annotations

import threading
from typing import Any

import httpx

OLLAMA_HTTP_LOCK = threading.Lock()


def ollama_post_json(
    url: str,
    json_body: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 600.0,
) -> dict[str, Any]:
    h = headers or {"Content-Type": "application/json"}
    with OLLAMA_HTTP_LOCK:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=json_body, headers=h)
            resp.raise_for_status()
            return resp.json()


def ollama_get_json(
    url: str,
    *,
    timeout: float = 60.0,
) -> tuple[int, str, Any | None]:
    """GET; returns ``(status, text_on_error, json_or_none)``."""
    with OLLAMA_HTTP_LOCK:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(url)
            if r.status_code != 200:
                return r.status_code, r.text, None
            return 200, "", r.json()
