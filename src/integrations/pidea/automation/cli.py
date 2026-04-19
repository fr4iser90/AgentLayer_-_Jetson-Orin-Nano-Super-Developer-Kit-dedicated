"""CLI: ``pidea doctor|scan|repair|snapshot|open-file|ask|read-chat``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from src.integrations.pidea.automation.action_runner import ActionRunner
from src.integrations.pidea.automation.chat_reader import read_chat_flat
from src.integrations.pidea.automation.workspace_reader import read_workspace_hints
from src.integrations.pidea.domkit import version_detector
from src.integrations.pidea.domkit.dom_snapshot import snapshot_accessibility, snapshot_html
from src.integrations.pidea.domkit.profile_generator import generate_from_base
from src.integrations.pidea.domkit.selector_finder import export_candidates_json, find_replacement_candidates
from src.integrations.pidea.domkit.selector_loader import load_bundle
from src.integrations.pidea.domkit.selector_validator import validate_bundle_on_page
from src.integrations.pidea.connection import PideaConnection

logger = logging.getLogger("pidea.cli")


def _cdp_url(ns: argparse.Namespace) -> str:
    u = (getattr(ns, "cdp_url", None) or os.environ.get("PIDEA_CDP_HTTP_URL") or "").strip()
    if not u:
        raise SystemExit("Set --cdp-url or PIDEA_CDP_HTTP_URL (e.g. http://127.0.0.1:9222)")
    if not u.startswith(("http://", "https://")):
        u = f"http://{u}"
    return u


def _connect_page(cdp: str):
    os.environ["PIDEA_CDP_HTTP_URL"] = cdp
    conn = PideaConnection(None)
    page = conn.connect(force=True)
    return conn, page


def cmd_doctor(ns: argparse.Namespace) -> int:
    cdp = _cdp_url(ns)
    vi = version_detector.detect_version(cdp, page=None)
    print("=== CDP /json/version ===")
    print(f"Browser: {vi.cdp_browser}")
    print(f"Protocol: {vi.cdp_protocol_version}")
    print(f"UA: {vi.cdp_user_agent}")
    print(f"Inferred semver (heuristic): {vi.inferred_cursor_semver}")

    conn, page = _connect_page(cdp)
    try:
        vi2 = version_detector.detect_version(cdp, page=page)
        print("=== DOM ===")
        print(f"document.title: {vi2.document_title}")
        print(f"navigator.userAgent: {vi2.navigator_user_agent}")
        print(f"window cursor hint: {vi2.window_cursor_version}")
        bundle = load_bundle(ns.ide, ns.version)
        print(f"=== Validate selectors ({ns.ide}/{ns.version}) ===")
        for vr in validate_bundle_on_page(page, bundle.chat):
            err = f" err={vr.error}" if vr.error else ""
            print(
                f"  {vr.key}: count={vr.count} visible={vr.visible_count} "
                f"clickable={vr.clickable_count}{err}"
            )
        print("=== Workspace hints ===")
        print(read_workspace_hints(page))
    finally:
        conn.close()
    return 0


def cmd_scan(ns: argparse.Namespace) -> int:
    cdp = _cdp_url(ns)
    conn, page = _connect_page(cdp)
    try:
        bundle = load_bundle(ns.ide, ns.version)
        if ns.all_keys:
            results = validate_bundle_on_page(page, bundle.chat, keys=None)
        else:
            results = validate_bundle_on_page(
                page,
                bundle.chat,
                keys=[
                    "isInputReady",
                    "input",
                    "userMessages",
                    "aiMessages",
                    "newChatButton",
                    "codiconSend",
                ],
            )
        for vr in results:
            sample = (vr.first_text_sample or "")[:120].replace("\n", " ")
            print(f"{vr.key}\tcount={vr.count}\tvis={vr.visible_count}\t{sample}")
    finally:
        conn.close()
    return 0


def cmd_repair(ns: argparse.Namespace) -> int:
    cdp = _cdp_url(ns)
    if ns.write and not ns.out:
        raise SystemExit("--write requires --out")
    conn, page = _connect_page(cdp)
    try:
        overrides: dict[str, str] = {}
        for key in ns.keys:
            cands = find_replacement_candidates(page, key)
            print(f"=== Candidates for {key} ===")
            print(export_candidates_json(cands[:10]))
            if cands:
                overrides[key] = cands[0].css
        if overrides and ns.write and ns.out:
            out = Path(ns.out)
            generate_from_base(ns.ide, ns.version, ns.new_version, overrides, out)
            print(f"Wrote profile -> {out.resolve()} keys={list(overrides.keys())}")
    finally:
        conn.close()
    return 0


def cmd_snapshot(ns: argparse.Namespace) -> int:
    cdp = _cdp_url(ns)
    conn, page = _connect_page(cdp)
    try:
        out = Path(ns.output)
        if ns.mode == "html":
            snapshot_html(page, out)
        else:
            snapshot_accessibility(page, out)
        print(out.resolve())
    finally:
        conn.close()
    return 0


def cmd_open_file(ns: argparse.Namespace) -> int:
    cdp = _cdp_url(ns)
    conn, page = _connect_page(cdp)
    try:
        ActionRunner(page).open_file(ns.path)
    finally:
        conn.close()
    return 0


def cmd_ask(ns: argparse.Namespace) -> int:
    cdp = _cdp_url(ns)
    conn, page = _connect_page(cdp)
    try:
        bundle = load_bundle(ns.ide, ns.version)
        inp = bundle.chat.get("input")
        if not inp:
            raise SystemExit("No input selector in bundle")
        ar = ActionRunner(page)
        ar.type_text(inp, ns.message, clear=True)
        ar.press("Enter")
    finally:
        conn.close()
    return 0


def cmd_interactive(ns: argparse.Namespace) -> int:
    from src.integrations.pidea.automation.interactive_cli import run_interactive

    _ = ns
    return run_interactive([])


def cmd_read_chat(ns: argparse.Namespace) -> int:
    cdp = _cdp_url(ns)
    conn, page = _connect_page(cdp)
    try:
        bundle = load_bundle(ns.ide, ns.version)
        u, a = read_chat_flat(page, bundle)
        print("--- user ---")
        for i, t in enumerate(u):
            print(f"[{i}] {t[:2000]}")
        print("--- assistant ---")
        for i, t in enumerate(a):
            print(f"[{i}] {t[:2000]}")
        if ns.json:
            import json

            print(json.dumps({"user": u, "assistant": a}, ensure_ascii=False, indent=2))
    finally:
        conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pidea", description="PIDEA Cursor DOM automation toolkit")
    p.add_argument("--cdp-url", default=os.environ.get("PIDEA_CDP_HTTP_URL"), help="CDP HTTP URL")
    p.add_argument("--ide", default="cursor", help="Selector IDE folder name")
    p.add_argument("--version", default="1.7.17", help="Selector profile version")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("doctor", help="CDP version + DOM hints + validate selectors")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("scan", help="Validate selectors (shortcut keys or --all)")
    sp.add_argument("--all", dest="all_keys", action="store_true", help="All keys in chatSelectors")
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("repair", help="Suggest replacement selectors (heuristic)")
    sp.add_argument("keys", nargs="+", help="Logical keys e.g. aiMessages userMessages")
    sp.add_argument("--write", action="store_true", help="Write merged profile JSON")
    sp.add_argument("--out", help="Output JSON path")
    sp.add_argument("--new-version", dest="new_version", default="0.0.0-repaired")
    sp.set_defaults(func=cmd_repair)

    sp = sub.add_parser("snapshot", help="Save DOM or a11y snapshot")
    sp.add_argument("--output", "-o", required=True)
    sp.add_argument("--mode", choices=("html", "a11y"), default="html")
    sp.set_defaults(func=cmd_snapshot)

    sp = sub.add_parser("open-file", help="Quick-open a file path (Ctrl+P)")
    sp.add_argument("path", help="File path as typed in quick open")
    sp.set_defaults(func=cmd_open_file)

    sp = sub.add_parser("ask", help="Type message into composer input and press Enter")
    sp.add_argument("message", help="Text to send")
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("read-chat", help="Print user/assistant lines from DOM")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_read_chat)

    sp = sub.add_parser("interactive", help="Minimal REPL")
    sp.set_defaults(func=cmd_interactive)

    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        argv = ["--help"]
    parser = build_parser()
    ns = parser.parse_args(argv)

    func = getattr(ns, "func", None)
    if func is None:
        parser.print_help()
        return 2
    return int(func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
