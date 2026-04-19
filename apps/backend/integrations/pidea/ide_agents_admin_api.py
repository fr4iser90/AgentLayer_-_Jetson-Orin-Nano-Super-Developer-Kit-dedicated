"""Admin API for multi-IDE DOM analyzer UI. Prefix: ``/v1/admin/ide-agents/{ide}/…``."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from apps.backend.infrastructure.auth import require_admin
from apps.backend.integrations.pidea.domkit.self_heal import self_heal_run
from apps.backend.integrations.pidea.ide_agents_admin_service import (
    ALLOWED_IDES,
    apply_profile,
    diff_payload,
    explore_payload,
    list_versions,
    normalize_ide,
    repair_payload,
    resolve_version,
    run_action,
    snapshot_payload,
    status_payload,
    ui_context_payload,
    validate_payload,
)
from apps.backend.integrations.pidea.playwright_env import playwright_import_ok

router = APIRouter(prefix="/v1/admin/ide-agents", tags=["ide-agents-admin"])


@router.get("/meta/supported-ides")
async def supported_ides(request: Request):
    """Must be registered before ``/{ide}/…`` so ``meta`` is not captured as ide."""
    await _admin_guard(request)
    return {"ides": sorted(ALLOWED_IDES)}


@router.get("/meta/ui-context")
async def ide_ui_context(request: Request):
    """Nav + runtime: visible IDEs (configured / operator / env), operator defaults, Playwright flag."""
    await _admin_guard(request)
    return await _thread(ui_context_payload)


def _dom_analyzer_enabled() -> bool:
    return os.environ.get("AGENT_DOM_ANALYZER_UI", "1").strip().lower() not in ("0", "false", "no")


async def _admin_guard(request: Request) -> None:
    await require_admin(request)
    if not _dom_analyzer_enabled():
        raise HTTPException(status_code=404, detail="DOM analyzer UI is disabled (AGENT_DOM_ANALYZER_UI)")


def _ide_or_400(ide: str) -> str:
    try:
        return normalize_ide(ide)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


async def _thread(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


@router.get("/{ide}/versions")
async def ide_versions(request: Request, ide: str):
    await _admin_guard(request)
    try:
        return await _thread(list_versions, _ide_or_400(ide))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{ide}/status")
async def ide_status(request: Request, ide: str, version: str | None = None):
    await _admin_guard(request)
    ide = _ide_or_400(ide)
    try:
        ver = resolve_version(ide, version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return await _thread(status_payload, ide, ver)


class ValidateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keys: list[str] | None = None


@router.post("/{ide}/validate")
async def ide_validate(request: Request, ide: str, body: ValidateBody, version: str | None = None):
    await _admin_guard(request)
    if not playwright_import_ok():
        raise HTTPException(status_code=503, detail="Playwright is not installed on the server")
    ide = _ide_or_400(ide)
    try:
        ver = resolve_version(ide, version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        return await _thread(validate_payload, ide, ver, body.keys)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class RepairBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keys: list[str] = Field(..., min_length=1)


@router.post("/{ide}/repair")
async def ide_repair(request: Request, ide: str, body: RepairBody, version: str | None = None):
    await _admin_guard(request)
    if not playwright_import_ok():
        raise HTTPException(status_code=503, detail="Playwright is not installed on the server")
    ide = _ide_or_400(ide)
    try:
        ver = resolve_version(ide, version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return await _thread(repair_payload, ide, ver, body.keys)


class ActionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    path: str | None = None
    message: str | None = None
    key: str | None = None
    selector: str | None = None
    confirm: bool = False


@router.post("/{ide}/action")
async def ide_action(request: Request, ide: str, body: ActionBody, version: str | None = None):
    await _admin_guard(request)
    if not playwright_import_ok():
        raise HTTPException(status_code=503, detail="Playwright is not installed on the server")
    ide = _ide_or_400(ide)
    try:
        ver = resolve_version(ide, version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    dangerous = body.action in (
        "open_file",
        "open_folder",
        "send_chat",
        "accept_changes",
        "click_selector",
        "press_key",
    )
    if dangerous and not body.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true for this action")

    payload: dict[str, Any] = {
        "path": body.path,
        "message": body.message,
        "key": body.key,
        "selector": body.selector,
    }
    try:
        return await _thread(run_action, ide, ver, body.action, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class SnapshotBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = Field(default="html", pattern="^(html|a11y)$")
    max_chars: int = Field(default=200_000, ge=1000, le=500_000)


@router.post("/{ide}/snapshot")
async def ide_snapshot(request: Request, ide: str, body: SnapshotBody, version: str | None = None):
    await _admin_guard(request)
    if not playwright_import_ok():
        raise HTTPException(status_code=503, detail="Playwright is not installed on the server")
    ide = _ide_or_400(ide)
    try:
        ver = resolve_version(ide, version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return await _thread(snapshot_payload, ide, ver, body.mode, body.max_chars)


class DiffBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    a: str = Field(..., description="First HTML/text snapshot")
    b: str = Field(..., description="Second HTML/text snapshot")


@router.post("/{ide}/diff")
async def ide_diff(request: Request, ide: str, body: DiffBody):
    await _admin_guard(request)
    _ = _ide_or_400(ide)
    return diff_payload(body.a, body.b)


@router.get("/{ide}/explore")
async def ide_explore(
    request: Request,
    ide: str,
    version: str | None = None,
    search: str = "",
    limit: int = 300,
):
    await _admin_guard(request)
    if not playwright_import_ok():
        raise HTTPException(status_code=503, detail="Playwright is not installed on the server")
    ide = _ide_or_400(ide)
    try:
        ver = resolve_version(ide, version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return await _thread(explore_payload, ide, ver, search, limit)


class ApplyProfileBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_version: str | None = None
    new_version: str
    overrides: dict[str, str] = Field(default_factory=dict)
    confirm: bool = False


class SelfHealBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_version: str | None = None
    new_version: str | None = None
    keys: list[str] | None = Field(default=None, description="Subset of chat keys; default all keys validated as broken")
    dry_run: bool = False
    confirm: bool = False


@router.post("/{ide}/self-heal")
async def ide_self_heal(request: Request, ide: str, body: SelfHealBody, version: str | None = None):
    """Auto-detect broken selectors, pick best candidates, re-validate, optionally persist new versioned JSON."""
    await _admin_guard(request)
    if not playwright_import_ok():
        raise HTTPException(status_code=503, detail="Playwright is not installed on the server")
    ide = _ide_or_400(ide)
    try:
        base_v = resolve_version(ide, body.base_version or version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    persist = body.confirm and not body.dry_run
    if body.dry_run and body.confirm:
        raise HTTPException(status_code=400, detail="Use dry_run without confirm, or omit dry_run to persist")
    try:
        return await _thread(
            self_heal_run,
            ide,
            base_v,
            keys_filter=body.keys,
            new_version=body.new_version,
            dry_run=body.dry_run,
            persist=persist,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{ide}/profile/apply")
async def ide_profile_apply(request: Request, ide: str, body: ApplyProfileBody):
    await _admin_guard(request)
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to write selector JSON")
    if not body.overrides:
        raise HTTPException(status_code=400, detail="overrides must be non-empty")
    ide = _ide_or_400(ide)
    try:
        base_v = resolve_version(ide, body.base_version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        return await _thread(
            apply_profile,
            ide,
            base_v,
            body.new_version.strip(),
            body.overrides,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

