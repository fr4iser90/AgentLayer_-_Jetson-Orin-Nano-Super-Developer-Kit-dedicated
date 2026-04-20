"""Admin HTTP API for persisted `scheduler_jobs` (user-defined schedules)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.backend.infrastructure.auth import require_admin
from apps.backend.infrastructure.db import db
from apps.backend.infrastructure import scheduler_jobs_store

router = APIRouter(prefix="/v1/admin/scheduler-jobs", tags=["scheduler-jobs-admin"])


class SchedulerJobSetEnabledBody(BaseModel):
    enabled: bool = Field(...)


@router.get("")
async def scheduler_job_list(
    request: Request,
    workspace_id: str | None = None,
    include_global: bool = False,
    execution_target: str | None = None,
    enabled: bool | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    user = await require_admin(request)
    tenant_id = db.user_tenant_id(user.id)
    ws_id: uuid.UUID | None = None
    if workspace_id is not None and str(workspace_id).strip():
        try:
            ws_id = uuid.UUID(str(workspace_id).strip())
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="invalid workspace_id") from None
    tgt = (execution_target or "").strip().lower() or None
    if tgt is not None and tgt not in ("server_periodic", "ide_agent"):
        raise HTTPException(status_code=400, detail="invalid execution_target")
    rows = scheduler_jobs_store.list_jobs_for_tenant(
        tenant_id=tenant_id,
        workspace_id=ws_id,
        include_global=bool(include_global),
        execution_target=tgt,
        enabled=enabled,
        limit=limit,
    )
    return {"ok": True, "jobs": [scheduler_jobs_store.row_to_public(r) for r in rows]}


@router.patch("/{job_id}/enabled")
async def scheduler_job_set_enabled(request: Request, job_id: str, body: SchedulerJobSetEnabledBody) -> dict:
    user = await require_admin(request)
    tenant_id = db.user_tenant_id(user.id)
    try:
        jid = uuid.UUID(job_id.strip())
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="invalid job_id") from None
    row = scheduler_jobs_store.set_enabled(
        job_id=jid,
        tenant_id=tenant_id,
        enabled=bool(body.enabled),
        actor_user_id=user.id,
        actor_is_admin=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    return {"ok": True, "job": scheduler_jobs_store.row_to_public(row)}

