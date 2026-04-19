"""Detect Cursor / Chromium version via CDP ``/json/version`` and DOM hints."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urljoin

from apps.backend.integrations.pidea.domkit.models import VersionInfo

logger = logging.getLogger(__name__)

_JS_WINDOW_VERSION = """
() => {
  const w = window;
  const keys = ['cursorVersion', 'cursor', 'vscode'];
  const out = {};
  try {
    for (const k of keys) {
      const v = w[k];
      if (v && typeof v === 'object' && typeof v.version === 'string') {
        out[k + '.version'] = v.version;
      }
    }
  } catch (e) {}
  try {
    if (typeof w.__CURSOR_VERSION__ === 'string') out.__CURSOR_VERSION__ = w.__CURSOR_VERSION__;
  } catch (e) {}
  return out;
}
"""

_JS_NAV_TITLE = """
() => ({
  title: document.title || '',
  userAgent: navigator.userAgent || '',
})
"""


def _normalize_cdp_base(cdp_http_url: str) -> str:
    u = cdp_http_url.strip().rstrip("/")
    if not u.startswith(("http://", "https://")):
        u = f"http://{u}"
    return u


def fetch_cdp_json_version(cdp_http_url: str, *, timeout_s: float = 5.0) -> dict[str, Any]:
    """GET ``/json/version`` from the CDP HTTP endpoint."""
    base = _normalize_cdp_base(cdp_http_url)
    url = urljoin(base + "/", "json/version")
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        logger.warning("CDP json/version HTTP error: %s", e)
        return {}
    except urllib.error.URLError as e:
        logger.warning("CDP json/version URL error: %s", e)
        return {}
    except json.JSONDecodeError as e:
        logger.warning("CDP json/version JSON error: %s", e)
        return {}


def _infer_semver_from_user_agent(ua: str) -> str | None:
    if not ua:
        return None
    # Cursor often embeds "Cursor/0.42.3" or similar
    m = re.search(r"Cursor[/\s]+(\d+\.\d+\.\d+)", ua, re.I)
    if m:
        return m.group(1)
    m = re.search(r"(\d+\.\d+\.\d+)", ua)
    return m.group(1) if m else None


def collect_dom_version_hints(page: Any) -> tuple[str | None, str | None, dict[str, str]]:
    """Return (window_cursor_version_guess, combined_hint_string, window_keys)."""
    try:
        win = page.evaluate(_JS_WINDOW_VERSION)
        nav = page.evaluate(_JS_NAV_TITLE)
    except Exception as e:
        logger.debug("DOM version hints failed: %s", e)
        return None, None, {}

    title = (nav or {}).get("title") or ""
    ua = (nav or {}).get("userAgent") or ""
    parts: list[str] = []
    wflat: dict[str, str] = {}
    if isinstance(win, dict):
        for k, v in win.items():
            if isinstance(v, str) and v.strip():
                wflat[str(k)] = v.strip()
                parts.append(f"{k}={v.strip()}")
    combined = "; ".join(parts) if parts else None
    guess = None
    for v in wflat.values():
        m = re.search(r"(\d+\.\d+\.\d+)", v)
        if m:
            guess = m.group(1)
            break
    if not guess:
        guess = _infer_semver_from_user_agent(ua)
    _ = title  # may use for logging
    return guess, combined, wflat


def detect_version(
    cdp_http_url: str,
    page: Any | None = None,
) -> VersionInfo:
    """Aggregate CDP ``/json/version`` and optional DOM inspection."""
    raw = fetch_cdp_json_version(cdp_http_url)
    ua = raw.get("User-Agent") or raw.get("userAgent")
    if isinstance(ua, str):
        inferred = _infer_semver_from_user_agent(ua)
    else:
        inferred = None

    vi = VersionInfo(
        cdp_browser=raw.get("Browser") if isinstance(raw.get("Browser"), str) else None,
        cdp_protocol_version=raw.get("Protocol-Version") if isinstance(raw.get("Protocol-Version"), str) else None,
        cdp_user_agent=ua if isinstance(ua, str) else None,
        cdp_webkit_version=raw.get("WebKit-Version") if isinstance(raw.get("WebKit-Version"), str) else None,
        inferred_cursor_semver=inferred,
        raw_json_version=dict(raw) if isinstance(raw, dict) else {},
    )

    if page is not None:
        try:
            nav = page.evaluate(_JS_NAV_TITLE)
            if isinstance(nav, dict):
                vi.document_title = nav.get("title")
                vi.navigator_user_agent = nav.get("userAgent")
        except Exception as e:
            logger.debug("nav/title evaluate: %s", e)
        guess, _, wflat = collect_dom_version_hints(page)
        if guess:
            vi.inferred_cursor_semver = vi.inferred_cursor_semver or guess
        if wflat:
            for k, v in wflat.items():
                if "cursor" in k.lower() and "version" in k.lower():
                    vi.window_cursor_version = v
                    break

    return vi
