"""Metadata rows for dashboard binary uploads (bytes on disk under ``dashboard_upload_dir()``)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row

from apps.backend.infrastructure.db import db


def _row(r: dict[str, Any]) -> dict[str, Any] | None:
    if not r:
        return None
    wid = r.get("id")
    if isinstance(wid, uuid.UUID):
        wid_s = str(wid)
    else:
        wid_s = str(wid or "")
    ca = r.get("created_at")
    return {
        "id": wid_s,
        "dashboard_id": str(r.get("dashboard_id") or ""),
        "storage_relpath": r.get("storage_relpath") or "",
        "content_type": r.get("content_type") or "",
        "size_bytes": int(r.get("size_bytes") or 0),
        "original_name": r.get("original_name") or "",
        "created_at": ca.isoformat() if isinstance(ca, datetime) else str(ca or ""),
    }


def file_insert(
    *,
    tenant_id: int,
    owner_user_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    storage_relpath: str,
    content_type: str,
    size_bytes: int,
    original_name: str,
) -> dict[str, Any]:
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO dashboard_files (
                  tenant_id, owner_user_id, dashboard_id, storage_relpath,
                  content_type, size_bytes, original_name
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, dashboard_id, storage_relpath, content_type, size_bytes, original_name, created_at
                """,
                (
                    tenant_id,
                    owner_user_id,
                    dashboard_id,
                    storage_relpath,
                    content_type,
                    size_bytes,
                    (original_name or "")[:500],
                ),
            )
            row = cur.fetchone()
        conn.commit()
    out = _row(dict(row)) if row else None
    if not out:
        raise RuntimeError("dashboard_files insert failed")
    return out


def file_get_with_access(
    file_id: uuid.UUID, user_id: uuid.UUID, tenant_id: int
) -> dict[str, Any] | None:
    """Uploader, dashboard owner, or any dashboard member (viewer/editor) may read."""
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT wf.id, wf.dashboard_id, wf.storage_relpath, wf.content_type,
                       wf.size_bytes, wf.original_name, wf.created_at
                FROM dashboard_files wf
                INNER JOIN user_dashboards w
                  ON w.id = wf.dashboard_id AND w.tenant_id = wf.tenant_id
                WHERE wf.id = %s AND wf.tenant_id = %s
                  AND (
                    wf.owner_user_id = %s
                    OR w.owner_user_id = %s
                    OR EXISTS (
                      SELECT 1 FROM dashboard_members m
                      WHERE m.dashboard_id = w.id AND m.user_id = %s
                    )
                    OR EXISTS (
                      SELECT 1 FROM dashboard_block_share_grants g
                      WHERE g.dashboard_id = w.id AND g.viewer_user_id = %s AND g.tenant_id = w.tenant_id
                    )
                  )
                """,
                (file_id, tenant_id, user_id, user_id, user_id, user_id),
            )
            row = cur.fetchone()
        conn.commit()
    return _row(dict(row)) if row else None


def file_delete_with_access(file_id: uuid.UUID, user_id: uuid.UUID, tenant_id: int) -> str | None:
    """Uploader or dashboard owner may delete (not shared editors on others' files)."""
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM dashboard_files wf
                USING user_dashboards w
                WHERE wf.id = %s AND wf.tenant_id = %s
                  AND wf.dashboard_id = w.id AND wf.tenant_id = w.tenant_id
                  AND (wf.owner_user_id = %s OR w.owner_user_id = %s)
                RETURNING wf.storage_relpath
                """,
                (file_id, tenant_id, user_id, user_id),
            )
            row = cur.fetchone()
        conn.commit()
    if not row or row[0] is None:
        return None
    return str(row[0])


def files_delete_all_for_dashboard_owner(
    dashboard_id: uuid.UUID, owner_user_id: uuid.UUID, tenant_id: int
) -> list[str]:
    """When the dashboard owner deletes the dashboard — all attachments."""
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM dashboard_files wf
                USING user_dashboards w
                WHERE wf.dashboard_id = w.id AND wf.tenant_id = w.tenant_id
                  AND wf.dashboard_id = %s AND wf.tenant_id = %s
                  AND w.owner_user_id = %s
                RETURNING wf.storage_relpath
                """,
                (dashboard_id, tenant_id, owner_user_id),
            )
            rows = cur.fetchall()
        conn.commit()
    return [str(r[0]) for r in rows if r and r[0] is not None]
