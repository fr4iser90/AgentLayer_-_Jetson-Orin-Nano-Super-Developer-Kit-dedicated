"""Serialize HTTP calls to Ollama (one in flight) for small GPUs / Jetson.

Async handlers must not hold threading.Lock across await — use
``await asyncio.to_thread(ollama_post_json, ...)`` (see ``domain.agent``).
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import httpx

logger = logging.getLogger(__name__)

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


def ollama_post_chat_completions(
    url: str,
    json_body: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 600.0,
) -> tuple[dict[str, Any], bool]:
    """
    POST to ``/v1/chat/completions``. Some vision models reject ``tools`` (Ollama 400:
    ``does not support tools``). In that case retry once without ``tools``.

    Returns ``(response_json, tools_omitted)``.
    """
    h = headers or {"Content-Type": "application/json"}
    tools_omitted = False
    with OLLAMA_HTTP_LOCK:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=json_body, headers=h)
            if (
                resp.status_code == 400
                and "tools" in json_body
                and "support tools" in (resp.text or "").lower()
            ):
                logger.warning(
                    "Ollama: model rejected tools; retrying without tools[] (preview=%r)",
                    (resp.text or "")[:300],
                )
                retry_body = {k: v for k, v in json_body.items() if k != "tools"}
                resp = client.post(url, json=retry_body, headers=h)
                tools_omitted = True
            resp.raise_for_status()
            return resp.json(), tools_omitted


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
