"""CRUD for ``user_workspaces`` (generic kind + ui_layout + data)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Json

from src.infrastructure.db import db
from src.workspace.defaults import defaults_for_kind


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
    return _row_dict(dict(row) if row else {})


def workspace_list(user_id: uuid.UUID, tenant_id: int, limit: int = 200) -> list[dict[str, Any]]:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, kind, title, updated_at, created_at
                FROM user_workspaces
                WHERE tenant_id = %s AND owner_user_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (tenant_id, user_id, limit),
            )
            rows = cur.fetchall()
        conn.commit()
    out: list[dict[str, Any]] = []
    for r in rows:
        wid = r[0]
        if not isinstance(wid, uuid.UUID):
            wid = uuid.UUID(str(wid))
        out.append(
            {
                "id": str(wid),
                "kind": r[1],
                "title": r[2] or "",
                "updated_at": r[3].isoformat() if isinstance(r[3], datetime) else str(r[3]),
                "created_at": r[4].isoformat() if isinstance(r[4], datetime) else str(r[4]),
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
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, kind, title, ui_layout, data, created_at, updated_at
                FROM user_workspaces
                WHERE id = %s AND tenant_id = %s AND owner_user_id = %s
                """,
                (workspace_id, tenant_id, user_id),
            )
            row = cur.fetchone()
        conn.commit()
    return _row_dict(dict(row)) if row else None


def workspace_update(
    user_id: uuid.UUID,
    tenant_id: int,
    workspace_id: uuid.UUID,
    *,
    title: str | None = None,
    ui_layout: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
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
    args.extend([workspace_id, tenant_id, user_id])
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                UPDATE user_workspaces
                SET {", ".join(sets)}
                WHERE id = %s AND tenant_id = %s AND owner_user_id = %s
                RETURNING id, kind, title, ui_layout, data, created_at, updated_at
                """,
                args,
            )
            row = cur.fetchone()
        conn.commit()
    return _row_dict(dict(row)) if row else None


def workspace_delete(user_id: uuid.UUID, tenant_id: int, workspace_id: uuid.UUID) -> bool:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
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
