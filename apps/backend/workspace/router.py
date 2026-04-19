"""HTTP API for generic workspaces (``/v1/workspaces``)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from apps.backend.core.config import config
from apps.backend.infrastructure.auth import get_current_user, get_user_by_email
from apps.backend.infrastructure.db import db
from apps.backend.infrastructure.operator_settings import (
    effective_workspace_upload_max_bytes,
    effective_workspace_upload_mime,
)
from apps.backend.workspace import db as workspace_db
from apps.backend.workspace import file_storage, files_db
from apps.backend.workspace.bootstrap import ensure_workspace_schema, workspace_tables_exist
from apps.backend.workspace.upload_bytes import normalized_content_type, sniff_image_mime
from apps.backend.infrastructure.public_error import http_500_detail

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


class WorkspaceMemberAddBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    role: str = Field(default="viewer", max_length=16)


class WorkspaceBlockShareBody(BaseModel):
    """Share only specific layout block ids; ``view`` = read-only, ``edit`` = patch those blocks."""

    email: str = Field(..., min_length=3, max_length=254)
    block_ids: list[str] = Field(default_factory=list)
    permission: str = Field(default="view", max_length=8)


class WorkspaceInstallBody(BaseModel):
    """Which bundle kinds to apply ``schema_sql`` for (nothing runs until you pick)."""

    kinds: list[str] = Field(default_factory=list)


@router.get("/install-status")
async def workspace_install_status(request: Request):
    """Schema state plus ``kind_catalog`` from ``workspace/**/workspace.kind.json``."""
    from apps.backend.workspace.bundle import kind_catalog, kinds_with_schema_sql, kinds_with_templates

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
        raise HTTPException(status_code=500, detail=http_500_detail(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_500_detail(e)) from e
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
        raise HTTPException(status_code=500, detail=http_500_detail(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_500_detail(e)) from e
    tid = db.user_tenant_id(user.id)
    workspace_db.tenant_merge_installed_template_kinds(tid, kinds)
    merged = workspace_db.tenant_installed_template_kinds(tid)
    return {"ok": True, "installed_template_kinds": merged}


@router.get("/upload-limits")
async def workspace_upload_limits(request: Request):
    """Effective max size and MIME allowlist (env + operator DB overrides)."""
    _require_schema()
    await get_current_user(request)
    return {
        "ok": True,
        "max_file_bytes": effective_workspace_upload_max_bytes(),
        "allowed_mime": sorted(effective_workspace_upload_mime()),
    }


@router.get("/files/{file_id}/content")
async def workspace_file_content(request: Request, file_id: uuid.UUID):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    meta = files_db.file_get_with_access(file_id, user.id, tid)
    if not meta:
        raise HTTPException(status_code=404, detail="file not found")
    try:
        data = file_storage.read_bytes(config.workspace_upload_dir(), meta["storage_relpath"])
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="file not found") from None
    return Response(
        content=data,
        media_type=meta.get("content_type") or "application/octet-stream",
    )


@router.delete("/files/{file_id}")
async def workspace_file_delete(request: Request, file_id: uuid.UUID):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    rel = files_db.file_delete_with_access(file_id, user.id, tid)
    if rel is None:
        raise HTTPException(status_code=404, detail="file not found")
    file_storage.unlink_if_exists(config.workspace_upload_dir(), rel)
    return {"ok": True, "deleted": True}


@router.post("/{workspace_id}/files")
async def workspace_file_upload(
    request: Request, workspace_id: uuid.UUID, file: UploadFile = File(...)
):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    ws = workspace_db.workspace_get(user.id, tid, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")
    role = ws.get("access_role")
    if role not in ("owner", "co_owner", "editor"):
        raise HTTPException(status_code=403, detail="upload not allowed for this role")

    max_b = effective_workspace_upload_max_bytes()
    allowed = effective_workspace_upload_mime()
    chunks: list[bytes] = []
    total = 0
    while True:
        block = await file.read(1024 * 64)
        if not block:
            break
        total += len(block)
        if total > max_b:
            raise HTTPException(
                status_code=413,
                detail=f"file too large (max {max_b} bytes)",
            )
        chunks.append(block)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="empty file")

    sniff = sniff_image_mime(data[:64])
    declared = normalized_content_type(file.content_type)
    if sniff is None or sniff not in allowed:
        raise HTTPException(
            status_code=415,
            detail="unsupported or invalid image type",
        )
    if declared and declared not in allowed:
        raise HTTPException(status_code=415, detail="content type not allowed")
    if declared and declared != sniff:
        raise HTTPException(
            status_code=400,
            detail=f"content type mismatch (declared {declared}, actual {sniff})",
        )

    fid = uuid.uuid4()
    relpath = f"{tid}/{fid}"
    name = (file.filename or "").strip()[:500]
    try:
        file_storage.write_bytes(config.workspace_upload_dir(), relpath, data)
    except OSError as e:
        raise HTTPException(status_code=500, detail=http_500_detail(e)) from e

    try:
        row = files_db.file_insert(
            tenant_id=tid,
            owner_user_id=user.id,
            workspace_id=workspace_id,
            storage_relpath=relpath,
            content_type=sniff,
            size_bytes=len(data),
            original_name=name,
        )
    except Exception:
        file_storage.unlink_if_exists(config.workspace_upload_dir(), relpath)
        raise

    return {
        "ok": True,
        "file": {
            "id": row["id"],
            "workspace_id": row["workspace_id"],
            "content_type": row["content_type"],
            "size_bytes": row["size_bytes"],
            "gallery_ref": f"wsfile:{row['id']}",
        },
    }


@router.get("")
async def list_workspaces(request: Request):
    from apps.backend.workspace.bundle import kind_catalog, kinds_with_schema_sql, kinds_with_templates

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


@router.get("/{workspace_id}/members")
async def list_workspace_members(request: Request, workspace_id: uuid.UUID):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    acc = workspace_db.workspace_access(user.id, tid, workspace_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    if not workspace_db.workspace_can_manage_members(user.id, tid, workspace_id):
        raise HTTPException(status_code=403, detail="only owner or co-owner can list members")
    items = workspace_db.members_list(user.id, tid, workspace_id)
    return {"ok": True, "members": items}


@router.post("/{workspace_id}/members")
async def add_workspace_member(
    request: Request, workspace_id: uuid.UUID, body: WorkspaceMemberAddBody
):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    if not workspace_db.workspace_can_manage_members(user.id, tid, workspace_id):
        raise HTTPException(status_code=403, detail="only owner or co-owner can add members")
    target = get_user_by_email(body.email.strip().lower())
    if target is None:
        raise HTTPException(status_code=404, detail="user not found for this email")
    if db.user_tenant_id(target.id) != tid:
        raise HTTPException(status_code=400, detail="user must be in the same tenant")
    role = (body.role or "viewer").strip().lower()
    if role not in ("viewer", "editor", "co_owner"):
        raise HTTPException(status_code=400, detail="role must be viewer, editor, or co_owner")
    ok = workspace_db.member_add(user.id, tid, workspace_id, target.id, role)
    if not ok:
        raise HTTPException(status_code=400, detail="could not add member")
    return {"ok": True, "members": workspace_db.members_list(user.id, tid, workspace_id)}


@router.delete("/{workspace_id}/members/{member_user_id}")
async def remove_workspace_member(
    request: Request, workspace_id: uuid.UUID, member_user_id: uuid.UUID
):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    if not workspace_db.workspace_can_manage_members(user.id, tid, workspace_id):
        raise HTTPException(status_code=403, detail="only owner or co-owner can remove members")
    if not workspace_db.member_remove(user.id, tid, workspace_id, member_user_id):
        raise HTTPException(status_code=404, detail="member not found")
    return {"ok": True, "removed": True}


@router.get("/{workspace_id}/block-shares")
async def list_workspace_block_shares(request: Request, workspace_id: uuid.UUID):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    if not workspace_db.workspace_can_manage_members(user.id, tid, workspace_id):
        raise HTTPException(status_code=403, detail="only owner or co-owner can list block shares")
    items = workspace_db.block_share_grants_list(user.id, tid, workspace_id)
    return {"ok": True, "grants": items}


@router.post("/{workspace_id}/block-shares")
async def upsert_workspace_block_share(
    request: Request, workspace_id: uuid.UUID, body: WorkspaceBlockShareBody
):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    target = get_user_by_email(body.email.strip().lower())
    if target is None:
        raise HTTPException(status_code=404, detail="user not found for this email")
    perm = (body.permission or "view").strip().lower()
    if perm not in ("view", "edit"):
        raise HTTPException(status_code=400, detail="permission must be view or edit")
    ok = workspace_db.block_share_grant_upsert(
        user.id,
        tid,
        workspace_id,
        viewer_user_id=target.id,
        block_ids=body.block_ids,
        permission=perm,
    )
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="could not save (check block ids exist in layout, not owner email, same tenant)",
        )
    items = workspace_db.block_share_grants_list(user.id, tid, workspace_id)
    return {"ok": True, "grants": items}


@router.delete("/{workspace_id}/block-shares/{viewer_user_id}")
async def delete_workspace_block_share(
    request: Request, workspace_id: uuid.UUID, viewer_user_id: uuid.UUID
):
    _require_schema()
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)
    if not workspace_db.workspace_can_manage_members(user.id, tid, workspace_id):
        raise HTTPException(status_code=403, detail="only owner or co-owner can remove block shares")
    if not workspace_db.block_share_grant_delete(user.id, tid, workspace_id, viewer_user_id):
        raise HTTPException(status_code=404, detail="grant not found")
    return {"ok": True, "removed": True}


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
