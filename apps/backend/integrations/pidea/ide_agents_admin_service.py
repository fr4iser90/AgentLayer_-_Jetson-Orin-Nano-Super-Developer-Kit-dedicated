"""Sync helpers for IDE DOM analyzer admin API (Playwright CDP)."""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apps.backend.infrastructure import operator_settings
from apps.backend.integrations.pidea.automation.action_runner import ActionRunner
from apps.backend.integrations.pidea.automation.chat_reader import read_chat_flat
from apps.backend.integrations.pidea.automation.workspace_reader import read_workspace_hints
from apps.backend.integrations.pidea.connection import PideaConnection
from apps.backend.integrations.pidea.domkit.dom_snapshot import snapshot_accessibility
from apps.backend.integrations.pidea.domkit.profile_generator import generate_from_base
from apps.backend.integrations.pidea.domkit.selector_finder import find_replacement_candidates
from apps.backend.integrations.pidea.domkit.selector_loader import load_bundle
from apps.backend.integrations.pidea.domkit.selector_validator import validate_bundle_on_page
from apps.backend.integrations.pidea.domkit.version_detector import detect_version
from apps.backend.integrations.pidea.playwright_env import playwright_import_ok
from apps.backend.integrations.pidea.selectors_loader import list_available_versions, selector_json_path
from apps.backend.integrations.pidea.types import ConnectionConfig

logger = logging.getLogger(__name__)

ALLOWED_IDES = frozenset({"cursor", "vscode", "windsurf"})

_EXPLORE_JS = """
([limit, search]) => {
  const q = (search || "").toLowerCase();
  const out = [];
  const sel = "button, input, textarea, [role], [aria-label], [data-message-role], [data-message-kind], a[href]";
  document.querySelectorAll(sel).forEach((el, i) => {
    if (out.length >= limit) return;
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute("role");
    const aria = el.getAttribute("aria-label");
    const ph = el.getAttribute("placeholder");
    const data = {};
    for (const a of el.attributes) {
      if (a.name.startsWith("data-")) data[a.name] = a.value.slice(0, 120);
    }
    const text = (el.innerText || "").replace(/\\s+/g, " ").trim().slice(0, 160);
    const blob = [tag, role || "", aria || "", ph || "", text, JSON.stringify(data)].join(" ").toLowerCase();
    if (q && !blob.includes(q)) return;
    let suggest = tag;
    if (el.id) suggest = "#" + el.id;
    else if (aria) suggest = tag + '[aria-label="' + aria.replace(/"/g, '\\\\"').slice(0, 48) + '"]';
    else if (Object.keys(data).length) {
      const k = Object.keys(data)[0];
      suggest = "[" + k + '="' + String(data[k]).replace(/"/g, '\\\\"').slice(0, 40) + '"]';
    }
    out.push({
      tag, role, ariaLabel: aria, placeholder: ph, dataAttrs: data,
      textPreview: text,
      suggestSelector: suggest,
    });
  });
  return out;
}
"""


def normalize_ide(ide: str) -> str:
    i = ide.strip().lower()
    if i not in ALLOWED_IDES:
        raise ValueError(f"unsupported ide: {ide!r}; allowed: {sorted(ALLOWED_IDES)}")
    return i


def resolve_version(ide: str, version: str | None) -> str:
    """Pick selector version: explicit param, operator match, or latest available file."""
    if version and version.strip():
        v = version.strip()
        # validate file exists
        p = selector_json_path(ide, v)
        if not p.is_file():
            raise FileNotFoundError(str(p))
        return v
    r = operator_settings._cached_row() or {}
    op_ide = str(r.get("pidea_selector_ide") or "").strip().lower()
    op_ver = str(r.get("pidea_selector_version") or "").strip()
    if op_ide == ide and op_ver:
        p = selector_json_path(ide, op_ver)
        if p.is_file():
            return op_ver
    vers = list_available_versions(ide)
    if not vers:
        raise FileNotFoundError(f"no selector JSON under selectors/{ide}/")
    return vers[-1]


def _make_config(ide: str, version: str) -> ConnectionConfig:
    base = operator_settings.resolved_pidea_connection_config()
    return ConnectionConfig(
        cdp_http_url=base.cdp_http_url,
        selector_ide=ide,
        selector_version=version,
        default_timeout_ms=base.default_timeout_ms,
    )


def _run_with_page(ide: str, version: str):
    if not playwright_import_ok():
        raise RuntimeError("Playwright is not installed on the server")
    cfg = _make_config(ide, version)
    conn = PideaConnection(cfg)
    page = conn.connect(force=True)
    return conn, page, cfg


def status_payload(ide: str, version: str) -> dict[str, Any]:
    ide, version = normalize_ide(ide), resolve_version(ide, version)
    cfg = _make_config(ide, version)
    cdp = cfg.cdp_http_url
    vi = detect_version(cdp, page=None)
    out: dict[str, Any] = {
        "ide": ide,
        "selector_version": version,
        "cdp_http_url": cdp,
        "connected": False,
        "cdp_json_version": vi.raw_json_version,
        "inferred_semver": vi.inferred_cursor_semver,
        "document_title": None,
        "active_page_url": None,
        "navigator_user_agent": None,
        "workspace_hints": None,
        "last_refresh": datetime.now(timezone.utc).isoformat(),
    }
    try:
        conn, page, _ = _run_with_page(ide, version)
        try:
            out["connected"] = True
            vi2 = detect_version(cdp, page=page)
            out["document_title"] = vi2.document_title
            out["navigator_user_agent"] = vi2.navigator_user_agent
            try:
                out["active_page_url"] = page.url
            except Exception:
                pass
            out["workspace_hints"] = read_workspace_hints(page)
        finally:
            conn.close()
    except Exception as e:
        out["error"] = str(e)
        logger.info("dom analyzer status connect failed: %s", e)
    return out


def validate_payload(ide: str, version: str, keys: list[str] | None) -> dict[str, Any]:
    ide, version = normalize_ide(ide), resolve_version(ide, version)
    bundle = load_bundle(ide, version)
    conn, page, _ = _run_with_page(ide, version)
    try:
        ks = sorted(bundle.chat.keys()) if keys is None else [k for k in keys if k in bundle.chat]
        rows = []
        for vr in validate_bundle_on_page(page, bundle.chat, keys=ks):
            status = "ok"
            if vr.error:
                status = "error"
            elif vr.count == 0:
                status = "empty"
            rows.append(
                {
                    "key": vr.key,
                    "selector": vr.selector,
                    "count": vr.count,
                    "visible": vr.visible_count,
                    "clickable": vr.clickable_count,
                    "sample": vr.first_text_sample,
                    "status": status,
                    "error": vr.error,
                }
            )
        return {"ide": ide, "selector_version": version, "rows": rows}
    finally:
        conn.close()


def repair_payload(ide: str, version: str, keys: list[str]) -> dict[str, Any]:
    ide, version = normalize_ide(ide), resolve_version(ide, version)
    conn, page, _ = _run_with_page(ide, version)
    try:
        out: dict[str, Any] = {"ide": ide, "selector_version": version, "candidates": {}}
        for key in keys:
            cands = find_replacement_candidates(page, key)
            out["candidates"][key] = [
                {
                    "css": c.css,
                    "source": c.source,
                    "rank": round(c.stability_score, 3),
                    "matches": c.match_count,
                }
                for c in cands[:15]
            ]
        return out
    finally:
        conn.close()


def explore_payload(ide: str, version: str, search: str, limit: int) -> dict[str, Any]:
    ide, version = normalize_ide(ide), resolve_version(ide, version)
    conn, page, _ = _run_with_page(ide, version)
    try:
        lim = max(1, min(limit, 500))
        raw = page.evaluate(_EXPLORE_JS, [lim, search or ""])
        items = raw if isinstance(raw, list) else []
        return {"ide": ide, "items": items, "count": len(items)}
    finally:
        conn.close()


def snapshot_payload(ide: str, version: str, mode: str, max_chars: int) -> dict[str, Any]:
    ide, version = normalize_ide(ide), resolve_version(ide, version)
    conn, page, _ = _run_with_page(ide, version)
    try:
        mc = max(1000, min(max_chars, 500_000))
        if mode == "a11y":
            import os
            import tempfile
            from pathlib import Path

            fd, p = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            tmp = Path(p)
            snapshot_accessibility(page, tmp)
            text = tmp.read_text(encoding="utf-8")
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            truncated = len(text) > mc
            text = text[:mc] + ("…" if truncated else "")
            return {"mode": "a11y", "truncated": truncated, "content": text, "length": len(text)}
        html = page.content()
        truncated = len(html) > mc
        html = html[:mc] + ("…" if truncated else "")
        return {"mode": "html", "truncated": truncated, "content": html, "length": len(html)}
    finally:
        conn.close()


def diff_payload(html_a: str, html_b: str) -> dict[str, Any]:
    a = html_a.splitlines(keepends=True)
    b = html_b.splitlines(keepends=True)
    diff = "".join(difflib.unified_diff(a, b, fromfile="a", tofile="b"))
    return {"unified_diff": diff, "diff_length": len(diff)}


def run_action(
    ide: str,
    version: str,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    ide, version = normalize_ide(ide), resolve_version(ide, version)
    bundle = load_bundle(ide, version)
    conn, page, _ = _run_with_page(ide, version)
    try:
        ar = ActionRunner(page)
        chat = bundle.chat
        if action == "open_file":
            path = str(payload.get("path") or "").strip()
            if not path:
                raise ValueError("path required")
            ar.open_file(path)
            return {"ok": True, "action": action}
        if action == "open_folder":
            path = str(payload.get("path") or "").strip()
            if not path:
                raise ValueError("path required")
            ar.open_folder(path)
            return {"ok": True, "action": action}
        if action == "send_chat":
            msg = str(payload.get("message") or "").strip()
            if not msg:
                raise ValueError("message required")
            inp = chat.get("input")
            if not inp:
                raise ValueError("no input selector in profile")
            ar.send_chat(inp, msg)
            return {"ok": True, "action": action}
        if action == "read_chat":
            u, a = read_chat_flat(page, bundle)
            return {"ok": True, "action": action, "user": u, "assistant": a}
        if action == "accept_changes":
            sel = str(payload.get("selector") or chat.get("codeBlockApplyButton") or ".anysphere-text-button")
            ar.accept_changes(sel)
            return {"ok": True, "action": action}
        if action == "press_key":
            key = str(payload.get("key") or "").strip()
            if not key:
                raise ValueError("key required")
            ar.press(key)
            return {"ok": True, "action": action}
        if action == "click_selector":
            sel = str(payload.get("selector") or "").strip()
            if not sel:
                raise ValueError("selector required")
            ar.click(sel)
            return {"ok": True, "action": action}
        raise ValueError(f"unknown action: {action}")
    finally:
        conn.close()


def apply_profile(
    ide: str,
    base_version: str,
    new_version: str,
    overrides: dict[str, str],
    *,
    backup: bool = True,
) -> dict[str, Any]:
    ide = normalize_ide(ide)
    base_version = resolve_version(ide, base_version)
    if not re.match(r"^[0-9][a-zA-Z0-9._-]*$", new_version.strip()):
        raise ValueError("invalid new_version")
    nv = new_version.strip()
    out_path = selector_json_path(ide, nv)
    base_path = selector_json_path(ide, base_version)
    if backup and base_path.is_file():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bak = base_path.with_suffix(base_path.suffix + f".bak.{ts}")
        shutil.copy2(base_path, bak)
    generate_from_base(ide, base_version, nv, overrides, out_path)
    return {"ok": True, "path": str(out_path), "ide": ide, "version": nv}


def list_versions(ide: str) -> dict[str, Any]:
    ide = normalize_ide(ide)
    return {"ide": ide, "versions": list_available_versions(ide)}


def ui_context_payload() -> dict[str, Any]:
    """Admin UI: which IDE rows to show (profiles / operator default / env allowlist)."""
    row = operator_settings._cached_row() or {}
    op_ide = str(row.get("pidea_selector_ide") or "").strip().lower()
    if op_ide and op_ide not in ALLOWED_IDES:
        op_ide = ""
    op_ver = str(row.get("pidea_selector_version") or "").strip() or None

    env_allow = os.environ.get("AGENT_IDE_AGENTS_VISIBLE_IDES", "").strip()
    visible: list[str] = []
    if env_allow:
        seen: set[str] = set()
        for raw in env_allow.split(","):
            x = raw.strip().lower()
            if x in ALLOWED_IDES and x not in seen:
                seen.add(x)
                visible.append(x)
    else:
        for ide in sorted(ALLOWED_IDES):
            has_prof = bool(list_available_versions(ide))
            if has_prof or op_ide == ide:
                visible.append(ide)
    if not visible and op_ide in ALLOWED_IDES:
        visible = [op_ide]

    return {
        "visible_ides": visible,
        "operator_selector_ide": op_ide or None,
        "operator_selector_version": op_ver,
        "playwright_import_ok": playwright_import_ok(),
    }
