"""HTTP-Endpunkte für PIDEA / IDE Agent — gesamte Oberfläche bleibt unter ``integrations/pidea/``."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from apps.backend.infrastructure.auth import get_current_user, ide_agent_access_for_user, require_admin
from apps.backend.integrations.pidea.errors import (
    IDEUnreachableError,
    PideaDisabledError,
    PideaError,
    PideaTimeoutError,
    PlaywrightNotInstalledError,
    SelectorNotFoundError,
)
from apps.backend.integrations.pidea.ide_agent_message import run_ide_agent_message_sync, run_ide_agent_snapshot_sync
from apps.backend.integrations.pidea.ide_agents_admin_api import router as ide_agents_admin_router
from apps.backend.infrastructure.public_error import http_500_detail
from apps.backend.integrations.pidea.playwright_env import (
    install_playwright_on_server_sync,
    playwright_import_ok,
    reload_playwright_import_state,
)

router = APIRouter(tags=["pidea"])
router.include_router(ide_agents_admin_router)


@router.get("/v1/experimental/status")
async def experimental_status(request: Request):
    """PIDEA / IDE Agent: global flag, per-user access (admin oder ``ide_agent_allowed``), Playwright."""
    user = await get_current_user(request)

    from apps.backend.infrastructure import operator_settings

    global_on = operator_settings.pidea_effective_enabled()
    return {
        "pidea_globally_enabled": global_on,
        "pidea_effective_enabled": global_on,
        "ide_agent_access": ide_agent_access_for_user(user),
        "pidea_playwright_installed": playwright_import_ok(),
    }


async def _run_ide_agent_with_mapping(run) -> Any:
    try:
        return await asyncio.to_thread(run)
    except PideaDisabledError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except PlaywrightNotInstalledError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except IDEUnreachableError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except PideaTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e)) from e
    except SelectorNotFoundError as e:
        raise HTTPException(status_code=500, detail=http_500_detail(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Selector bundle not found: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PideaError as e:
        raise HTTPException(status_code=500, detail=http_500_detail(e)) from e


@router.get("/v1/ide-agent/snapshot")
async def ide_agent_snapshot(request: Request):
    """Liest den aktuellen IDE-Composer-Stand (User-/AI-Zeilen) ohne zu senden."""
    user = await get_current_user(request)
    if not ide_agent_access_for_user(user):
        raise HTTPException(status_code=403, detail="IDE Agent access denied")
    if not playwright_import_ok():
        raise HTTPException(status_code=503, detail="Playwright is not installed on the server")

    def _run() -> dict[str, Any]:
        return run_ide_agent_snapshot_sync()

    return await _run_ide_agent_with_mapping(_run)


class IdeAgentMessageBody(BaseModel):
    """Text in den IDE-Composer (Cursor, …) via Playwright + CDP; Antwort aus dem DOM."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=32000)
    new_chat: bool = False
    reply_timeout_seconds: float = Field(default=120.0, ge=5.0, le=600.0)


@router.post("/v1/ide-agent/message")
async def ide_agent_message(request: Request, body: IdeAgentMessageBody):
    """Steuert das IDE-KI-Panel: braucht ``ide_agent_access`` und Playwright auf dem API-Host."""
    user = await get_current_user(request)
    if not ide_agent_access_for_user(user):
        raise HTTPException(status_code=403, detail="IDE Agent access denied")
    if not playwright_import_ok():
        raise HTTPException(status_code=503, detail="Playwright is not installed on the server")
    text = body.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="message is empty")

    def _run() -> dict[str, Any]:
        return run_ide_agent_message_sync(
            text,
            new_chat=body.new_chat,
            reply_timeout_s=body.reply_timeout_seconds,
        )

    return await _run_ide_agent_with_mapping(_run)


@router.post("/v1/admin/experimental/install-playwright")
async def admin_install_playwright(request: Request):
    """Admin: Playwright + Chromium in der laufenden API-Umgebung installieren (Subprozess)."""
    await require_admin(request)
    ok, log_text = await asyncio.to_thread(install_playwright_on_server_sync)
    if ok:
        reload_playwright_import_state()
    return {
        "ok": ok,
        "detail": log_text,
        "pidea_playwright_installed": playwright_import_ok(),
    }
