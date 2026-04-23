"""User HTTP API for persisted `scheduler_jobs` (user-defined schedules)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.backend.infrastructure.auth import get_current_user
from apps.backend.infrastructure.db import db
from apps.backend.infrastructure import scheduler_jobs_store
from apps.backend.workspace.db import workspace_access_ex

router = APIRouter(prefix="/v1/user/scheduler-jobs", tags=["scheduler-jobs-user"])


class SchedulerJobCreateBody(BaseModel):
    execution_target: str = Field(..., max_length=32)
    interval_minutes: int = Field(default=60, ge=5, le=10080)
    enabled: bool = True
    title: str | None = Field(default=None, max_length=500)
    instructions: str = Field(..., min_length=1, max_length=32000)
    workspace_id: str | None = None
    ide_workflow: dict[str, Any] | None = None


class SchedulerJobSetEnabledBody(BaseModel):
    enabled: bool = Field(...)


class SchedulerJobPatchBody(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    instructions: str | None = Field(default=None, max_length=32000)
    interval_minutes: int | None = Field(default=None, ge=5, le=10080)


@router.get("")
async def scheduler_job_list(request: Request, workspace_id: str | None = None, limit: int = 50) -> dict:
    user = await get_current_user(request)
    tenant_id = db.user_tenant_id(user.id)
    ws_id: uuid.UUID | None = None
    if workspace_id is not None and str(workspace_id).strip():
        try:
            ws_id = uuid.UUID(str(workspace_id).strip())
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="invalid workspace_id") from None
    rows = scheduler_jobs_store.list_jobs_for_user(
        tenant_id=tenant_id,
        current_user_id=user.id,
        is_admin=(user.role == "admin"),
        workspace_id=ws_id,
        limit=limit,
    )
    return {"ok": True, "jobs": [scheduler_jobs_store.row_to_public(r) for r in rows]}


@router.post("")
async def scheduler_job_create(request: Request, body: SchedulerJobCreateBody) -> dict[str, Any]:
    user = await get_current_user(request)
    tenant_id = db.user_tenant_id(user.id)
    tgt = body.execution_target.strip().lower()
    if tgt not in ("server_periodic", "ide_agent"):
        raise HTTPException(status_code=400, detail="invalid execution_target")
    if tgt == "ide_agent" and user.role != "admin":
        raise HTTPException(status_code=403, detail="execution_target ide_agent requires admin")

    ws_id: uuid.UUID | None = None
    if body.workspace_id is not None and str(body.workspace_id).strip():
        try:
            ws_id = uuid.UUID(str(body.workspace_id).strip())
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="invalid workspace_id") from None
        d = workspace_access_ex(user.id, tenant_id, ws_id)
        if d.role is None:
            raise HTTPException(status_code=403, detail="workspace not accessible")
        if d.allowed_block_ids is None:
            if d.role not in ("owner", "co_owner", "editor"):
                raise HTTPException(status_code=403, detail="workspace is read-only for this user")
        else:
            if not d.granular_can_write:
                raise HTTPException(status_code=403, detail="workspace is read-only for this user")

    row = scheduler_jobs_store.insert_job(
        tenant_id=tenant_id,
        created_by_user_id=user.id,
        execution_user_id=user.id,
        workspace_id=ws_id,
        execution_target=tgt,
        title=(body.title or "").strip() or None,
        instructions=body.instructions.strip(),
        interval_minutes=int(body.interval_minutes),
        enabled=bool(body.enabled),
        ide_workflow=body.ide_workflow or {},
    )
    if not row:
        raise HTTPException(status_code=500, detail="failed to create job")
    return {"ok": True, "job": scheduler_jobs_store.row_to_public(row)}


@router.patch("/{job_id}")
async def scheduler_job_patch(request: Request, job_id: str, body: SchedulerJobPatchBody) -> dict[str, Any]:
    user = await get_current_user(request)
    tenant_id = db.user_tenant_id(user.id)
    try:
        jid = uuid.UUID(job_id.strip())
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="invalid job_id") from None
    row = scheduler_jobs_store.update_job(
        job_id=jid,
        tenant_id=tenant_id,
        actor_user_id=user.id,
        actor_is_admin=(user.role == "admin"),
        title=body.title.strip() if isinstance(body.title, str) else None,
        instructions=body.instructions.strip() if isinstance(body.instructions, str) else None,
        interval_minutes=body.interval_minutes,
        ide_workflow=None,
    )
    if not row:
        raise HTTPException(status_code=404, detail="job not found or not allowed")
    return {"ok": True, "job": scheduler_jobs_store.row_to_public(row)}


@router.delete("/{job_id}")
async def scheduler_job_hard_delete(request: Request, job_id: str) -> dict[str, Any]:
    user = await get_current_user(request)
    tenant_id = db.user_tenant_id(user.id)
    try:
        jid = uuid.UUID(job_id.strip())
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="invalid job_id") from None
    ok = scheduler_jobs_store.hard_delete_job(
        job_id=jid,
        tenant_id=tenant_id,
        actor_user_id=user.id,
        actor_is_admin=(user.role == "admin"),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="job not found or not allowed")
    return {"ok": True, "deleted": True, "job_id": str(jid)}

@router.patch("/{job_id}/enabled")
async def scheduler_job_set_enabled(
    request: Request, job_id: str, body: SchedulerJobSetEnabledBody
) -> dict[str, Any]:
    user = await get_current_user(request)
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
        actor_is_admin=(user.role == "admin"),
    )
    if not row:
        raise HTTPException(status_code=404, detail="job not found or not allowed")
    return {"ok": True, "job": scheduler_jobs_store.row_to_public(row)}

