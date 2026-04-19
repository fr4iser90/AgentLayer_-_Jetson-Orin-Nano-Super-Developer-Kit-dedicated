"""Minimal interactive shell for quick CDP commands."""

from __future__ import annotations

import os
import shlex
import sys
from typing import Any

from src.integrations.pidea.automation.action_runner import ActionRunner
from src.integrations.pidea.automation.chat_reader import read_chat_flat
from src.integrations.pidea.domkit.selector_loader import load_bundle
from src.integrations.pidea.connection import PideaConnection


def _page_from_env() -> tuple[Any, Any]:
    cdp = (os.environ.get("PIDEA_CDP_HTTP_URL") or "").strip()
    if not cdp:
        print("Set PIDEA_CDP_HTTP_URL", file=sys.stderr)
        raise SystemExit(1)
    if not cdp.startswith(("http://", "https://")):
        cdp = f"http://{cdp}"
    os.environ["PIDEA_CDP_HTTP_URL"] = cdp
    conn = PideaConnection(None)
    return conn, conn.connect(force=True)


def run_interactive(argv: list[str]) -> int:
    _ = argv
    print("pidea interactive — commands: help | exit | read | type <css> <text> | key <name>")
    conn, page = _page_from_env()
    ide, ver = os.environ.get("PIDEA_SELECTOR_IDE", "cursor"), os.environ.get("PIDEA_SELECTOR_VERSION", "1.7.17")
    try:
        bundle = load_bundle(ide, ver)
        ar = ActionRunner(page)
        while True:
            try:
                line = input("pidea> ").strip()
            except EOFError:
                break
            if not line:
                continue
            parts = shlex.split(line)
            cmd = parts[0].lower()
            if cmd in ("exit", "quit"):
                break
            if cmd == "help":
                print("read | type <css> <text> | key Enter | open <path>")
                continue
            if cmd == "read":
                u, a = read_chat_flat(page, bundle)
                print("user:", len(u), "assistant:", len(a))
                continue
            if cmd == "type" and len(parts) >= 3:
                css = parts[1]
                text = " ".join(parts[2:])
                ar.type_text(css, text)
                continue
            if cmd == "key" and len(parts) >= 2:
                ar.press(parts[1])
                continue
            if cmd == "open" and len(parts) >= 2:
                ar.open_file(parts[1])
                continue
            print("unknown command", file=sys.stderr)
    finally:
        conn.close()
    return 0
