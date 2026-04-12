"""HTTP API for generic workspaces (``/v1/workspaces``)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.infrastructure.auth import get_current_user
from src.infrastructure.db import db
from src.workspace import db as workspace_db
from src.workspace.bootstrap import ensure_workspace_schema, workspace_tables_exist

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


def _require_schema() -> None:
    if not workspace_tables_exist():
        raise HTTPException(
            status_code=400,
            detail="workspace schema not installed; use POST /v1/workspaces/install from the UI first",
        )


class WorkspaceCreateBody(BaseModel):
    kind: str = Field(default="custom", max_length=64)
    title: str = Field(default="", max_length=500)
    ui_layout: dict[str, Any] | None = None
    data: dict[str, Any] | None = None


class WorkspacePatchBody(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    ui_layout: dict[str, Any] | None = None
    data: dict[str, Any] | None = None


class WorkspaceInstallBody(BaseModel):
    """Which bundle kinds to apply ``schema_sql`` for (nothing runs until you pick)."""

    kinds: list[str] = Field(default_factory=list)


@router.get("/install-status")
async def workspace_install_status(request: Request):
    """Schema state plus ``kind_catalog`` from ``workspace/**/workspace.kind.json``."""
    from src.workspace.bundle import kind_catalog, kinds_with_schema_sql, kinds_with_templates

    user = await get_current_user(request)
    installed = workspace_tables_exist()
    cat = kind_catalog()
    template_kinds = kinds_with_templates()
    installed_kinds: list[str] | None = None
    if installed:
        tid = db.user_tenant_id(user.id)
        installed_kinds = workspace_db.tenant_installed_template_kinds(tid)
    return {
        "ok": True,
        "schema_installed": installed,
        "kind_catalog": cat,
        "schema_install_offers": kinds_with_schema_sql() if not installed else [],
        "template_kinds": template_kinds,
        "installed_template_kinds": installed_kinds,
    }


@router.post("/install")
async def workspace_install(request: Request, body: WorkspaceInstallBody):
    """Apply ``schema_sql`` only for ``body.kinds`` — does not create workspace rows."""
    user = await get_current_user(request)
    if workspace_tables_exist():
        return {"ok": True, "already": True}
    kinds = [str(k).strip().lower() for k in body.kinds if str(k).strip()]
    if not kinds:
        raise HTTPException(
            status_code=400,
            detail="select at least one kind (body.kinds) to install schema for; nothing is installed by default",
        )
    try:
        ensure_workspace_schema(kinds)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"install failed: {e!s}") from e
    tid = db.user_tenant_id(user.id)
    workspace_db.tenant_merge_installed_template_kinds(tid, kinds)
    return {"ok": True, "already": False}


@router.post("/install-templates")
async def workspace_install_templates(request: Request, body: WorkspaceInstallBody):
    """Install more template kinds for this tenant (idempotent DDL + merge). Requires base schema."""
    _require_schema()
    user = await get_current_user(request)
    kinds = [str(k).strip().lower() for k in body.kinds if str(k).strip()]
    if not kinds:
        raise HTTPException(
            status_code=400,
            detail="send at least one kind in body.kinds",
        )
    try:
        ensure_workspace_schema(kinds)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"install-templates failed: {e!s}") from e
    tid = db.user_tenant_id(user.id)
    workspace_db.tenant_merge_installed_template_kinds(tid, kinds)
    merged = workspace_db.tenant_installed_template_kinds(tid)
    return {"ok": True, "installed_template_kinds": merged}


@router.get("")
async def list_workspaces(request: Request):
    from src.workspace.bundle import kind_catalog, kinds_with_schema_sql, kinds_with_templates

    user = await get_current_user(request)
    cat = kind_catalog()
    template_kinds = kinds_with_templates()
    if not workspace_tables_exist():
        return {
            "ok": True,
            "workspaces": [],
            "schema_installed": False,
            "kind_catalog": cat,
            "schema_install_offers": kinds_with_schema_sql(),
            "template_kinds": template_kinds,
            "installed_template_kinds": [],
        }
    tid = db.user_tenant_id(user.id)
    items = workspace_db.workspace_list(user.id, tid)
    installed_kinds = workspace_db.tenant_installed_template_kinds(tid)
    return {
        "ok": True,
        "workspaces": items,
        "schema_installed": True,
        "kind_catalog": cat,
        "schema_install_offers": [],
        "template_kinds": template_kinds,
        "installed_template_kinds": installed_kinds,
    }


@router.post("")
async def create_workspace(request: Request, body: WorkspaceCreateBody):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    row = workspace_db.workspace_create(
        user.id,
        tid,
        kind=body.kind,
        title=body.title,
        ui_layout=body.ui_layout,
        data=body.data,
    )
    return {"ok": True, "workspace": row}


@router.get("/{workspace_id}")
async def get_workspace(request: Request, workspace_id: uuid.UUID):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    row = workspace_db.workspace_get(user.id, tid, workspace_id)
    if not row:
        raise HTTPException(status_code=404, detail="workspace not found")
    return {"ok": True, "workspace": row}


@router.patch("/{workspace_id}")
async def patch_workspace(
    request: Request, workspace_id: uuid.UUID, body: WorkspacePatchBody
):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    row = workspace_db.workspace_update(
        user.id,
        tid,
        workspace_id,
        title=body.title,
        ui_layout=body.ui_layout,
        data=body.data,
    )
    if not row:
        raise HTTPException(status_code=404, detail="workspace not found")
    return {"ok": True, "workspace": row}


@router.delete("/{workspace_id}")
async def delete_workspace(request: Request, workspace_id: uuid.UUID):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    if not workspace_db.workspace_delete(user.id, tid, workspace_id):
        raise HTTPException(status_code=404, detail="workspace not found")
    return {"ok": True, "deleted": True}
