"""Automatic self-heal for chat selector profiles: detect broken selectors, pick candidates, validate, persist."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from src.integrations.pidea.domkit.models import SelectorCandidate, ValidationResult
from src.integrations.pidea.domkit.selector_finder import find_all_candidates
from src.integrations.pidea.domkit.selector_loader import load_bundle
from src.integrations.pidea.domkit.selector_validator import validate_bundle_on_page, validate_selector_on_page

logger = logging.getLogger(__name__)

CRITICAL_CHAT_KEYS = frozenset({"aiMessages", "userMessages", "input"})
INTERACTIVE_RE = re.compile(
    r"(send|button|input|click|submit|toolbar|action|codicon|execute|apply)",
    re.I,
)


def is_selector_unsafe(css: str) -> bool:
    """Reject overly generic selectors (bare tags, no anchor)."""
    s = (css or "").strip()
    if len(s) < 8:
        return True
    if re.match(r"^(div|span)(\s*,|\s*$)", s, re.I) and "[" not in s and "." not in s and "#" not in s:
        return True
    if not re.search(r"[\[\.#]", s) and len(s) < 24:
        return True
    return False


def is_interactive_key(key: str) -> bool:
    return bool(INTERACTIVE_RE.search(key))


def is_broken(vr: ValidationResult, key: str) -> bool:
    if vr.error:
        return True
    if vr.count == 0:
        return True
    if vr.visible_count == 0:
        return True
    if is_interactive_key(key) and vr.count > 0 and vr.clickable_count == 0:
        return True
    return False


def _too_broad(vr: ValidationResult, key: str) -> bool:
    if key in ("aiMessages", "userMessages"):
        return vr.count > 120
    if "message" in key.lower() or "container" in key.lower():
        return vr.count > 200
    return vr.count > 600


def _row_dict(vr: ValidationResult) -> dict[str, Any]:
    status = "ok"
    if vr.error:
        status = "error"
    elif vr.count == 0:
        status = "empty"
    elif is_broken(vr, vr.key):
        status = "broken"
    return {
        "key": vr.key,
        "selector": vr.selector,
        "count": vr.count,
        "visible": vr.visible_count,
        "clickable": vr.clickable_count,
        "sample": vr.first_text_sample,
        "status": status,
        "error": vr.error,
    }


def pick_working_selector(page: Any, key: str, candidates: list[SelectorCandidate]) -> tuple[str | None, str | None]:
    """Try ranked candidates until one validates as non-broken and not overly broad."""
    for c in candidates[:14]:
        if is_selector_unsafe(c.css):
            continue
        vr = validate_selector_on_page(page, key, c.css)
        if _too_broad(vr, key):
            continue
        if not is_broken(vr, key):
            return c.css, None
    return None, "no_candidate_passed_validation"


def self_heal_run(
    ide: str,
    base_version: str,
    *,
    keys_filter: list[str] | None = None,
    new_version: str | None = None,
    dry_run: bool = False,
    persist: bool = False,
) -> dict[str, Any]:
    """
    Load profile, connect CDP, validate, repair broken keys using finder + validation loop.

    If ``persist`` and not ``dry_run`` and critical chat keys validate after heal, writes
    ``{base_version}-heal-{UTC timestamp}`` (or ``new_version``) via :func:`apply_profile`.
    """
    from src.integrations.pidea.ide_agents_admin_service import (  # noqa: PLC0415 — avoid cycle at import time
        apply_profile,
        normalize_ide,
        resolve_version,
        _run_with_page,
    )

    ide = normalize_ide(ide)
    base_version = resolve_version(ide, base_version)
    bundle = load_bundle(ide, base_version)
    chat = dict(bundle.chat)

    conn, page, _ = _run_with_page(ide, base_version)
    try:
        ks = sorted(chat.keys()) if keys_filter is None else [k for k in keys_filter if k in chat]
        initial = validate_bundle_on_page(page, chat, keys=ks)
        validation_before = [_row_dict(vr) for vr in initial]

        broken_keys = [vr.key for vr in initial if is_broken(vr, vr.key)]
        if not broken_keys:
            return {
                "ok": True,
                "ide": ide,
                "base_version": base_version,
                "changed_keys": [],
                "failed_keys": [],
                "critical_keys_ok": True,
                "validation_before": validation_before,
                "validation_after": validation_before,
                "updated_selectors": {},
                "new_version": None,
                "path": None,
                "dry_run": dry_run,
                "message": "nothing_to_heal",
            }

        overrides: dict[str, str] = {}
        failures: list[dict[str, str]] = []

        for key in broken_keys:
            candidates = find_all_candidates(page, key)
            css, err = pick_working_selector(page, key, candidates)
            if css:
                overrides[key] = css
                chat[key] = css
            else:
                failures.append({"key": key, "reason": err or "failed"})

        after = validate_bundle_on_page(page, chat, keys=ks)
        validation_after = [_row_dict(vr) for vr in after]

        critical_failures: list[str] = []
        for ck in CRITICAL_CHAT_KEYS:
            if ck not in chat:
                continue
            vr_by_key = {v.key: v for v in after}
            if ck not in vr_by_key:
                critical_failures.append(ck)
                continue
            if is_broken(vr_by_key[ck], ck):
                critical_failures.append(ck)
        critical_ok = len(critical_failures) == 0

        nv: str | None = None
        if new_version and new_version.strip():
            nv = new_version.strip()
        elif overrides and not dry_run and persist and critical_ok:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            nv = f"{base_version}-heal-{ts}"

        path: str | None = None
        wrote = False
        if persist and not dry_run and overrides and critical_ok and nv:
            out = apply_profile(ide, base_version, nv, overrides, backup=True)
            path = str(out.get("path", ""))
            wrote = True
        elif persist and not dry_run and overrides and not critical_ok:
            logger.warning("self-heal: not persisting — critical keys still broken: %s", critical_failures)

        return {
            "ok": critical_ok,
            "ide": ide,
            "base_version": base_version,
            "changed_keys": sorted(overrides.keys()),
            "failed_keys": failures,
            "critical_keys_ok": critical_ok,
            "critical_failures": critical_failures,
            "validation_before": validation_before,
            "validation_after": validation_after,
            "updated_selectors": overrides,
            "new_version": nv if wrote else None,
            "path": path,
            "dry_run": dry_run,
            "persisted": wrote,
        }
    finally:
        conn.close()
