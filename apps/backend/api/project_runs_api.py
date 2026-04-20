"""HTTP API for one-shot project runs (enqueue + list).

This is the UI-facing endpoint that creates `project_runs` rows directly (no schedule).
"""

from __future__ import annotations

from typing import Any
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.backend.infrastructure.auth import require_admin
from apps.backend.infrastructure.db import db
from apps.backend.infrastructure import project_runs_store

router = APIRouter(prefix="/v1/project-runs", tags=["project-runs"])


class ProjectRunCreateBody(BaseModel):
    instructions: str = Field(..., min_length=1, max_length=32000)
    ide_workflow: dict[str, Any] | None = None
    workspace_id: str | None = None
    project_row_id: str | None = Field(default=None, max_length=200)
    project_title: str | None = Field(default=None, max_length=500)


@router.post("")
async def project_run_create(request: Request, body: ProjectRunCreateBody) -> dict:
    # For now: IDE runs require admin anyway (same policy as PIDEA / ide_agent scheduling).
    user = await require_admin(request)
    tenant_id = db.user_tenant_id(user.id)

    instr = body.instructions.strip()
    if not instr:
        raise HTTPException(status_code=400, detail="instructions is required")

    ws_id: uuid.UUID | None = None
    if body.workspace_id is not None and str(body.workspace_id).strip():
        try:
            ws_id = uuid.UUID(str(body.workspace_id).strip())
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="invalid workspace_id") from None

    row = project_runs_store.insert_run(
        tenant_id=tenant_id,
        created_by_user_id=user.id,
        execution_user_id=user.id,
        scheduler_job_id=None,
        workspace_id=ws_id,
        project_row_id=(body.project_row_id or "").strip() or None,
        project_title=(body.project_title or "").strip() or None,
        execution_target="ide_agent",
        instructions=instr,
        ide_workflow=body.ide_workflow or {},
    )
    if not row:
        raise HTTPException(status_code=500, detail="failed to create run")
    return {"ok": True, "run": project_runs_store.row_to_public(row)}


@router.get("")
async def project_run_list(
    request: Request,
    workspace_id: str | None = None,
    project_row_id: str | None = None,
    limit: int = 50,
) -> dict:
    user = await require_admin(request)
    tenant_id = db.user_tenant_id(user.id)
    ws_id: uuid.UUID | None = None
    if workspace_id is not None and str(workspace_id).strip():
        try:
            ws_id = uuid.UUID(str(workspace_id).strip())
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="invalid workspace_id") from None
    rows = project_runs_store.list_runs(
        tenant_id=tenant_id,
        workspace_id=ws_id,
        project_row_id=(project_row_id or "").strip() or None,
        limit=limit,
    )
    return {"ok": True, "runs": [project_runs_store.row_to_public(r) for r in rows]}

