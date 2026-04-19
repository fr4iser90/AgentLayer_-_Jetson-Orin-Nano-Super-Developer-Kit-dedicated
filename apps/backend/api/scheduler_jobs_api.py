"""HTTP API for IDE clients: fetch due ``ide_agent`` jobs and ack after local execution."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request

from apps.backend.infrastructure.auth import require_admin
from apps.backend.infrastructure.db import db
from apps.backend.infrastructure.scheduler_jobs_store import (
    ack_job_run_for_user,
    fetch_due_jobs_ide_for_user,
    row_to_public,
)

router = APIRouter(prefix="/v1/scheduler", tags=["scheduler"])


@router.get("/jobs/due")
async def list_due_ide_jobs(
    request: Request,
    execution_target: str = "ide_agent",
    limit: int = 20,
) -> dict:
    """
    Return due scheduler jobs for the **current user** as ``execution_user_id`` (IDE integration).
    Only ``execution_target=ide_agent`` is supported here. **Admin only** (same policy as PIDEA).
    """
    if execution_target.strip().lower() != "ide_agent":
        raise HTTPException(
            status_code=400,
            detail="only execution_target=ide_agent is supported for this endpoint",
        )
    user = await require_admin(request)
    tenant_id = db.user_tenant_id(user.id)
    lim = max(1, min(100, limit))
    rows = fetch_due_jobs_ide_for_user(
        tenant_id=tenant_id,
        execution_user_id=user.id,
        limit=lim,
    )
    return {"ok": True, "jobs": [row_to_public(r) for r in rows]}


@router.post("/jobs/{job_id}/ack-run")
async def ack_ide_job_run(request: Request, job_id: str) -> dict:
    """
    Mark ``last_run_at`` after the IDE has executed the job locally (advances the interval).
    **Admin only**; must match job tenant (``execution_user_id`` must be the admin for typical jobs).
    """
    user = await require_admin(request)
    try:
        jid = uuid.UUID(job_id.strip())
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="invalid job_id") from None
    tenant_id = db.user_tenant_id(user.id)
    is_admin = user.role == "admin"
    row = ack_job_run_for_user(
        job_id=jid,
        tenant_id=tenant_id,
        actor_user_id=user.id,
        actor_is_admin=is_admin,
    )
    if not row:
        raise HTTPException(status_code=404, detail="job not found or not allowed")
    return {"ok": True, "job": row_to_public(row)}
