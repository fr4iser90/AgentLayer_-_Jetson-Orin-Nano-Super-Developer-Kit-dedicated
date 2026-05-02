"""HTTP API for project workspaces (/v1/workspaces)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.backend.core.config import config
from apps.backend.infrastructure.auth import get_current_user
from apps.backend.infrastructure.db import db
from apps.backend.infrastructure.operator_settings import public_dict

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


def _get_workspace_base_path() -> Path:
    base = os.environ.get("AGENTLAYER_WORKSPACE_PATH", "/workspace")
    return Path(base)


def _is_self_editing_allowed() -> bool:
    try:
        settings = public_dict()
        return bool(settings.get("workspace_allow_self_editing", False))
    except Exception:
        return False


def _user_can_access_self_workspace(user) -> bool:
    if user.role == "admin":
        return True
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(workspace_self_allowed, false) FROM users WHERE id = %s",
                (user.id,),
            )
            row = cur.fetchone()
            return bool(row[0]) if row else False


def _get_self_workspace(user) -> dict[str, Any] | None:
    if not _is_self_editing_allowed():
        return None
    if not _user_can_access_self_workspace(user):
        return None
    return {
        "id": "__agentlayer_self__",
        "owner_user_id": "__system__",
        "name": "AgentLayer (self)",
        "path": "/app",
        "source": "builtin",
        "git_url": None,
        "git_branch": "main",
        "access_role": "editor",
        "created_at": None,
        "updated_at": None,
    }


class WorkspaceCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    source: str = Field(default="manual", max_length=32)
    git_url: str | None = None
    git_branch: str = Field(default="main", max_length=255)


class WorkspaceUpdateBody(BaseModel):
    name: str | None = None
    git_branch: str | None = None


def _row_to_workspace(row: tuple) -> dict[str, Any]:
    return {
        "id": str(row[0]),
        "owner_user_id": str(row[1]),
        "name": row[2],
        "path": row[3],
        "source": row[4],
        "git_url": row[5],
        "git_branch": row[6],
        "access_role": row[7],
        "created_at": row[8].isoformat() if row[8] else None,
        "updated_at": row[9].isoformat() if row[9] else None,
    }


@router.get("")
async def list_workspaces(request: Request):
    """List all workspaces for the current user, including built-in AgentLayer workspace if enabled."""
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, owner_user_id, name, path, source, git_url, git_branch, access_role, created_at, updated_at
                FROM project_workspaces
                WHERE owner_user_id = %s
                ORDER BY name ASC
                """,
                (user.id,),
            )
            rows = cur.fetchall()

    workspaces = [_row_to_workspace(r) for r in rows]

    self_ws = _get_self_workspace(user)
    if self_ws:
        workspaces.insert(0, self_ws)

    return {"workspaces": workspaces}


@router.post("")
async def create_workspace(request: Request, body: WorkspaceCreateBody):
    """Create a new workspace (manual folder or git clone)."""
    user = await get_current_user(request)
    tid = db.user_tenant_id(user.id)

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(workspace_quota, 10) FROM users WHERE id = %s",
                (user.id,),
            )
            row = cur.fetchone()
            quota = row[0] if row else 10

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM project_workspaces WHERE owner_user_id = %s",
                (user.id,),
            )
            row = cur.fetchone()
            existing_count = row[0] if row else 0

    if existing_count >= quota:
        raise HTTPException(
            status_code=403,
            detail=f"Workspace quota exceeded ({quota} max). Delete some workspaces first.",
        )

    base_path = _get_workspace_base_path()
    user_workspace_dir = base_path / str(user.id) / body.name

    if body.source == "git" and body.git_url:
        user_workspace_dir.mkdir(parents=True, exist_ok=True)
        import subprocess

        result = subprocess.run(
            ["git", "clone", "--branch", body.git_branch or "main", "--depth", "1", body.git_url, str(user_workspace_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=f"Git clone failed: {result.stderr}")
    else:
        user_workspace_dir.mkdir(parents=True, exist_ok=True)

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO project_workspaces (owner_user_id, name, path, source, git_url, git_branch, access_role)
                VALUES (%s, %s, %s, %s, %s, %s, 'owner')
                RETURNING id, owner_user_id, name, path, source, git_url, git_branch, access_role, created_at, updated_at
                """,
                (user.id, body.name, str(user_workspace_dir), body.source, body.git_url, body.git_branch or "main"),
            )
            row = cur.fetchone()
        conn.commit()

    if not row:
        raise HTTPException(status_code=500, detail="Failed to create workspace")

    return {"workspace": _row_to_workspace(row)}


@router.get("/{workspace_id}")
async def get_workspace(request: Request, workspace_id: str):
    """Get a specific workspace."""
    user = await get_current_user(request)

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, owner_user_id, name, path, source, git_url, git_branch, access_role, created_at, updated_at
                FROM project_workspaces
                WHERE id = %s AND owner_user_id = %s
                """,
                (workspace_id, user.id),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return {"workspace": _row_to_workspace(row)}


@router.patch("/{workspace_id}")
async def update_workspace(request: Request, workspace_id: str, body: WorkspaceUpdateBody):
    """Update workspace (rename, change branch)."""
    user = await get_current_user(request)

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, owner_user_id, name, path, source, git_url, git_branch, access_role, created_at, updated_at
                FROM project_workspaces
                WHERE id = %s AND owner_user_id = %s AND access_role IN ('owner', 'editor')
                """,
                (workspace_id, user.id),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found or no edit permission")

    updates = []
    params = []

    if body.name:
        updates.append("name = %s")
        params.append(body.name)
    if body.git_branch:
        updates.append("git_branch = %s")
        params.append(body.git_branch)

    if updates:
        params.append(workspace_id)
        with db.pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE project_workspaces SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s",
                    tuple(params),
                )
            conn.commit()

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, owner_user_id, name, path, source, git_url, git_branch, access_role, created_at, updated_at
                FROM project_workspaces WHERE id = %s
                """,
                (workspace_id,),
            )
            row = cur.fetchone()

    return {"workspace": _row_to_workspace(row)}


@router.delete("/{workspace_id}")
async def delete_workspace(request: Request, workspace_id: str):
    """Delete a workspace (owner only)."""
    user = await get_current_user(request)

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT path FROM project_workspaces WHERE id = %s AND owner_user_id = %s AND access_role = 'owner'",
                (workspace_id, user.id),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found or no delete permission")

    import shutil

    workspace_path = Path(row[0])
    if workspace_path.exists():
        shutil.rmtree(workspace_path)

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM project_workspaces WHERE id = %s", (workspace_id,))
        conn.commit()

    return {"ok": True}


@router.get("/{workspace_id}/validate-path")
async def validate_workspace_path(request: Request, workspace_id: str):
    """Check if workspace path exists and is accessible."""
    user = await get_current_user(request)

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT path FROM project_workspaces WHERE id = %s AND owner_user_id = %s",
                (workspace_id, user.id),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")

    workspace_path = Path(row[0])
    return {
        "exists": workspace_path.exists(),
        "path": str(workspace_path),
        "is_directory": workspace_path.is_dir() if workspace_path.exists() else False,
    }