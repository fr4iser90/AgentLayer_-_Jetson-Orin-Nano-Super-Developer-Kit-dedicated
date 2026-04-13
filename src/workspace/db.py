"""CRUD for ``user_workspaces`` (generic kind + ui_layout + data) and sharing."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from psycopg.rows import dict_row
from psycopg.types.json import Json

from src.core.config import config
from src.infrastructure.db import db
from src.workspace import file_storage, files_db
from src.workspace.defaults import defaults_for_kind

AccessRole = Literal["owner", "editor", "viewer"]


def workspace_access(
    user_id: uuid.UUID, tenant_id: int, workspace_id: uuid.UUID
) -> AccessRole | None:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT w.owner_user_id, m.role
                FROM user_workspaces w
                LEFT JOIN workspace_members m
                  ON m.workspace_id = w.id AND m.user_id = %s
                WHERE w.id = %s AND w.tenant_id = %s
                  AND (w.owner_user_id = %s OR m.user_id IS NOT NULL)
                """,
                (user_id, workspace_id, tenant_id, user_id),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    owner_uid, member_role = row[0], row[1]
    if owner_uid == user_id:
        return "owner"
    if member_role == "editor":
        return "editor"
    if member_role == "viewer":
        return "viewer"
    return None


def workspace_create(
    user_id: uuid.UUID,
    tenant_id: int,
    *,
    kind: str,
    title: str,
    ui_layout: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    du, dd = defaults_for_kind(kind)
    if ui_layout is not None:
        du = ui_layout
    if data is not None:
        dd = data
    label = (title or "").strip() or "Workspace"
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO user_workspaces (
                  tenant_id, owner_user_id, kind, title, ui_layout, data
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, kind, title, ui_layout, data, created_at, updated_at
                """,
                (tenant_id, user_id, kind.strip() or "custom", label, Json(du), Json(dd)),
            )
            row = cur.fetchone()
        conn.commit()
    r = _row_dict(dict(row) if row else {})
    r["access_role"] = "owner"
    return r


def workspace_list(user_id: uuid.UUID, tenant_id: int, limit: int = 200) -> list[dict[str, Any]]:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT w.id, w.kind, w.title, w.updated_at, w.created_at,
                  CASE
                    WHEN w.owner_user_id = %s THEN 'owner'
                    ELSE m.role::text
                  END AS access_role
                FROM user_workspaces w
                LEFT JOIN workspace_members m
                  ON m.workspace_id = w.id AND m.user_id = %s
                WHERE w.tenant_id = %s
                  AND (w.owner_user_id = %s OR m.user_id IS NOT NULL)
                ORDER BY w.updated_at DESC
                LIMIT %s
                """,
                (user_id, user_id, tenant_id, user_id, limit),
            )
            rows = cur.fetchall()
        conn.commit()
    out: list[dict[str, Any]] = []
    for r in rows:
        wid = r[0]
        if not isinstance(wid, uuid.UUID):
            wid = uuid.UUID(str(wid))
        role = (r[5] or "owner").strip().lower()
        if role not in ("owner", "editor", "viewer"):
            role = "owner"
        out.append(
            {
                "id": str(wid),
                "kind": r[1],
                "title": r[2] or "",
                "updated_at": r[3].isoformat() if isinstance(r[3], datetime) else str(r[3]),
                "created_at": r[4].isoformat() if isinstance(r[4], datetime) else str(r[4]),
                "access_role": role,
            }
        )
    return out


def _row_dict(r: dict[str, Any]) -> dict[str, Any]:
    if not r:
        return {}
    wid = r.get("id")
    if not isinstance(wid, uuid.UUID):
        wid = uuid.UUID(str(wid))
    ul = r.get("ui_layout")
    dt = r.get("data")
    ca = r.get("created_at")
    ua = r.get("updated_at")
    return {
        "id": str(wid),
        "kind": r.get("kind") or "",
        "title": r.get("title") or "",
        "ui_layout": ul if isinstance(ul, dict) else {},
        "data": dt if isinstance(dt, dict) else {},
        "created_at": ca.isoformat() if isinstance(ca, datetime) else str(ca or ""),
        "updated_at": ua.isoformat() if isinstance(ua, datetime) else str(ua or ""),
    }


def workspace_get(user_id: uuid.UUID, tenant_id: int, workspace_id: uuid.UUID) -> dict[str, Any] | None:
    role = workspace_access(user_id, tenant_id, workspace_id)
    if role is None:
        return None
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, kind, title, ui_layout, data, created_at, updated_at
                FROM user_workspaces
                WHERE id = %s AND tenant_id = %s
                """,
                (workspace_id, tenant_id),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    out = _row_dict(dict(row))
    out["access_role"] = role
    return out


def workspace_update(
    user_id: uuid.UUID,
    tenant_id: int,
    workspace_id: uuid.UUID,
    *,
    title: str | None = None,
    ui_layout: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    role = workspace_access(user_id, tenant_id, workspace_id)
    if role is None or role == "viewer":
        return None
    sets: list[str] = []
    args: list[Any] = []
    if title is not None:
        sets.append("title = %s")
        args.append((title or "").strip() or "Workspace")
    if ui_layout is not None:
        sets.append("ui_layout = %s")
        args.append(Json(ui_layout))
    if data is not None:
        sets.append("data = %s")
        args.append(Json(data))
    if not sets:
        return workspace_get(user_id, tenant_id, workspace_id)
    sets.append("updated_at = now()")
    args.extend([workspace_id, tenant_id, user_id, user_id])
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # SET fragments are fixed literals; values are always %s-bound (not SQL keyword injection).
            cur.execute(  # nosec B608  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
                f"""
                UPDATE user_workspaces w
                SET {", ".join(sets)}
                WHERE w.id = %s AND w.tenant_id = %s
                  AND (
                    w.owner_user_id = %s
                    OR EXISTS (
                      SELECT 1 FROM workspace_members m
                      WHERE m.workspace_id = w.id AND m.user_id = %s AND m.role = 'editor'
                    )
                  )
                RETURNING w.id, w.kind, w.title, w.ui_layout, w.data, w.created_at, w.updated_at
                """,
                args,
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    out = _row_dict(dict(row))
    out["access_role"] = role
    return out


def workspace_delete(user_id: uuid.UUID, tenant_id: int, workspace_id: uuid.UUID) -> bool:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM user_workspaces
                WHERE id = %s AND tenant_id = %s AND owner_user_id = %s
                """,
                (workspace_id, tenant_id, user_id),
            )
            ok = cur.fetchone() is not None
        conn.commit()
    if not ok:
        return False

    rels = files_db.files_delete_all_for_workspace_owner(workspace_id, user_id, tenant_id)
    root = config.workspace_upload_dir()
    for rel in rels:
        file_storage.unlink_if_exists(root, rel)

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM workspace_members WHERE workspace_id = %s",
                (workspace_id,),
            )
            cur.execute(
                """
                DELETE FROM user_workspaces
                WHERE id = %s AND tenant_id = %s AND owner_user_id = %s
                """,
                (workspace_id, tenant_id, user_id),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0


def members_list(
    owner_user_id: uuid.UUID, tenant_id: int, workspace_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Only workspace owner may list members."""
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM user_workspaces
                WHERE id = %s AND tenant_id = %s AND owner_user_id = %s
                """,
                (workspace_id, tenant_id, owner_user_id),
            )
            if cur.fetchone() is None:
                conn.commit()
                return []
            cur.execute(
                """
                SELECT m.user_id, m.role, m.created_at, u.email
                FROM workspace_members m
                JOIN users u ON u.id = m.user_id
                WHERE m.workspace_id = %s
                ORDER BY m.created_at ASC
                """,
                (workspace_id,),
            )
            rows = cur.fetchall()
        conn.commit()
    out: list[dict[str, Any]] = []
    for r in rows:
        uid, role, created, email = r[0], r[1], r[2], r[3]
        out.append(
            {
                "user_id": str(uid),
                "email": (email or "").strip(),
                "role": role,
                "created_at": created.isoformat() if isinstance(created, datetime) else str(created),
            }
        )
    return out


def member_add(
    owner_user_id: uuid.UUID,
    tenant_id: int,
    workspace_id: uuid.UUID,
    member_user_id: uuid.UUID,
    role: str,
) -> bool:
    r = (role or "").strip().lower()
    if r not in ("viewer", "editor"):
        return False
    if member_user_id == owner_user_id:
        return False
    mtid = db.user_tenant_id(member_user_id)
    if mtid != tenant_id:
        return False
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM user_workspaces
                WHERE id = %s AND tenant_id = %s AND owner_user_id = %s
                """,
                (workspace_id, tenant_id, owner_user_id),
            )
            if cur.fetchone() is None:
                conn.commit()
                return False
            cur.execute(
                """
                INSERT INTO workspace_members (workspace_id, user_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = EXCLUDED.role
                """,
                (workspace_id, member_user_id, r),
            )
        conn.commit()
    return True


def member_remove(
    owner_user_id: uuid.UUID,
    tenant_id: int,
    workspace_id: uuid.UUID,
    member_user_id: uuid.UUID,
) -> bool:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM user_workspaces
                WHERE id = %s AND tenant_id = %s AND owner_user_id = %s
                """,
                (workspace_id, tenant_id, owner_user_id),
            )
            if cur.fetchone() is None:
                conn.commit()
                return False
            cur.execute(
                """
                DELETE FROM workspace_members
                WHERE workspace_id = %s AND user_id = %s
                """,
                (workspace_id, member_user_id),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0


_INSTALLED_TEMPLATE_KINDS_SQL = """
CREATE TABLE IF NOT EXISTS tenant_workspace_installed_template_kinds (
  tenant_id BIGINT PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
  kinds TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[]
);
"""


def ensure_tenant_installed_template_kinds_table() -> None:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_INSTALLED_TEMPLATE_KINDS_SQL)
        conn.commit()


def tenant_installed_template_kinds(tenant_id: int) -> list[str] | None:
    """Which disk templates this tenant has installed, or ``None`` if unset (legacy: show all)."""
    ensure_tenant_installed_template_kinds_table()
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT kinds FROM tenant_workspace_installed_template_kinds WHERE tenant_id = %s",
                (tenant_id,),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    if row[0] is None:
        return None
    return [str(x).strip().lower() for x in row[0]]


def tenant_merge_installed_template_kinds(tenant_id: int, kinds: list[str]) -> None:
    """Record additional installed template kinds (distinct). ``custom`` is ignored."""
    ensure_tenant_installed_template_kinds_table()
    add = sorted(
        {
            str(k).strip().lower()
            for k in kinds
            if str(k).strip() and str(k).strip().lower() != "custom"
        }
    )
    if not add:
        return
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT kinds FROM tenant_workspace_installed_template_kinds WHERE tenant_id = %s",
                (tenant_id,),
            )
            row = cur.fetchone()
            existing: list[str] = []
            if row and row[0]:
                existing = [str(x).strip().lower() for x in row[0]]
            merged = sorted(set(existing + add))
            cur.execute(
                """
                INSERT INTO tenant_workspace_installed_template_kinds (tenant_id, kinds)
                VALUES (%s, %s)
                ON CONFLICT (tenant_id) DO UPDATE SET kinds = EXCLUDED.kinds
                """,
                (tenant_id, merged),
            )
        conn.commit()
