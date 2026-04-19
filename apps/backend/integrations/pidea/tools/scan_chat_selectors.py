#!/usr/bin/env python3
"""Zählt Treffer für chatSelectors (userMessages, aiMessages, …) per CDP — gleiche Playwright-Pipeline wie der IDE-Agent.

Voraussetzung: ``pip install -r requirements-pidea.txt`` und ``playwright install chromium``.

Beispiel (Repo-Root, ``PYTHONPATH=src``)::

    export PIDEA_CDP_HTTP_URL=http://127.0.0.1:9222
    python -m apps.integrations.pidea.tools.scan_chat_selectors
    python -m apps.integrations.pidea.tools.scan_chat_selectors path/to/selectors.json
    python -m apps.integrations.pidea.tools.scan_chat_selectors --all path/to/selectors.json

Das Skript **erzeugt keine Selektoren** — es zählt nur Treffer für die bereits in der JSON stehenden CSS-Strings.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
_DEFAULT_JSON = _TOOLS_DIR.parent / "selectors" / "cursor" / "1.7.17.json"

_QUICK_KEYS = (
    "isInputReady",
    "input",
    "userMessages",
    "aiMessages",
    "newChatButton",
    "codiconSend",
)


def _normalize_cdp_http_url(url: str) -> str:
    u = url.strip()
    if not u:
        return u
    if not u.startswith(("http://", "https://")):
        return f"http://{u}"
    return u


def _load_chat_selectors(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    chat = data.get("chatSelectors") or data.get("chat_selectors")
    if not isinstance(chat, dict):
        raise SystemExit(f"No chatSelectors in {path}")
    out: dict[str, str] = {}
    for k, v in chat.items():
        if isinstance(k, str) and isinstance(v, str) and v.strip():
            out[k] = v.strip()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Count selector matches via CDP (Playwright).")
    parser.add_argument(
        "json_path",
        nargs="?",
        default=None,
        help=f"Path to selector JSON (default: {_DEFAULT_JSON})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Alle Keys aus chatSelectors der JSON zählen (sonst nur die wichtigsten: input, user/ai, send, …).",
    )
    args = parser.parse_args()

    cdp = _normalize_cdp_http_url(os.environ.get("PIDEA_CDP_HTTP_URL", "").strip())
    if not cdp:
        print("Set PIDEA_CDP_HTTP_URL (e.g. http://127.0.0.1:9222)", file=sys.stderr)
        raise SystemExit(1)

    json_path = Path(args.json_path).resolve() if args.json_path else _DEFAULT_JSON
    if not json_path.is_file():
        print(f"Selector file not found: {json_path}", file=sys.stderr)
        raise SystemExit(1)

    chat = _load_chat_selectors(json_path)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit(
            "Playwright fehlt: pip install -r requirements-pidea.txt && playwright install chromium"
        ) from e

    print("CDP:", cdp)
    print("JSON:", json_path)
    print("---")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp)
        try:
            page_index = 0
            for context in browser.contexts:
                for page in context.pages:
                    page_index += 1
                    try:
                        url = page.url
                    except Exception:
                        url = "(url error)"
                    print(f"Page #{page_index} {url}")

                    keys_to_scan = sorted(chat.keys()) if args.all else [k for k in _QUICK_KEYS if k in chat]
                    for key in keys_to_scan:
                        if key not in chat:
                            continue
                        sel = chat[key]
                        try:
                            n = page.locator(sel).count()
                            err = None
                        except Exception as ex:
                            n = 0
                            err = str(ex)
                        line = f"  {key}: count={n}"
                        print(f"{line} ({err})" if err else line)

                    try:
                        u_n = page.locator(chat["userMessages"]).count() if "userMessages" in chat else 0
                        a_n = page.locator(chat["aiMessages"]).count() if "aiMessages" in chat else 0
                    except Exception:
                        u_n = a_n = 0
                    print(f"  summary: userMessages={u_n} aiMessages={a_n}")
                    print("---")

            if page_index == 0:
                print("No pages in CDP contexts — open the IDE/Composer and retry.")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
