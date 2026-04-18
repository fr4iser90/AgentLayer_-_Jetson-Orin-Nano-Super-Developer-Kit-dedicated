"""CRUD for ``user_workspaces`` (generic kind + ui_layout + data) and sharing."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, NamedTuple

from psycopg.rows import dict_row
from psycopg.types.json import Json

from src.core.config import config
from src.infrastructure.db import db
from src.workspace import file_storage, files_db
from src.workspace.defaults import defaults_for_kind

AccessRole = Literal["owner", "co_owner", "editor", "viewer"]


class WorkspaceAccessDetail(NamedTuple):
    """``allowed_block_ids`` is ``None`` for full workspace (not granular)."""

    role: AccessRole | None
    allowed_block_ids: frozenset[str] | None
    granular_can_write: bool


def workspace_access_ex(
    user_id: uuid.UUID, tenant_id: int, workspace_id: uuid.UUID
) -> WorkspaceAccessDetail:
    """Effective role, optional block allowlist, and whether granular edit is allowed."""
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
            if row:
                owner_uid, member_role = row[0], row[1]
                if owner_uid == user_id:
                    return WorkspaceAccessDetail("owner", None, False)
                if member_role == "co_owner":
                    return WorkspaceAccessDetail("co_owner", None, False)
                if member_role == "editor":
                    return WorkspaceAccessDetail("editor", None, False)
                if member_role == "viewer":
                    return WorkspaceAccessDetail("viewer", None, False)
            cur.execute(
                """
                SELECT block_ids, COALESCE(permission, 'view') AS permission
                FROM workspace_block_share_grants
                WHERE workspace_id = %s AND viewer_user_id = %s AND tenant_id = %s
                """,
                (workspace_id, user_id, tenant_id),
            )
            grow = cur.fetchone()
        conn.commit()
    if grow and grow[0]:
        raw_ids = grow[0]
        perm_raw = str(grow[1] or "view").strip().lower() if len(grow) > 1 else "view"
        if isinstance(raw_ids, list):
            bf = frozenset(str(x).strip() for x in raw_ids if str(x).strip())
        else:
            bf = frozenset()
        if bf:
            can_write = perm_raw == "edit"
            eff: AccessRole = "editor" if can_write else "viewer"
            return WorkspaceAccessDetail(eff, bf, can_write)
    return WorkspaceAccessDetail(None, None, False)


def workspace_access(
    user_id: uuid.UUID, tenant_id: int, workspace_id: uuid.UUID
) -> AccessRole | None:
    return workspace_access_ex(user_id, tenant_id, workspace_id).role


def workspace_has_full_access(
    user_id: uuid.UUID, tenant_id: int, workspace_id: uuid.UUID
) -> bool:
    """True if the user is owner or a normal member — not block-only granular access."""
    d = workspace_access_ex(user_id, tenant_id, workspace_id)
    return d.role is not None and d.allowed_block_ids is None


def _filter_ui_layout(layout: dict[str, Any], allowed: frozenset[str]) -> dict[str, Any]:
    if not isinstance(layout, dict):
        return {}
    blocks = layout.get("blocks")
    if not isinstance(blocks, list):
        return dict(layout)
    nb = [
        b
        for b in blocks
        if isinstance(b, dict) and str(b.get("id") or "").strip() in allowed
    ]
    out = dict(layout)
    out["blocks"] = nb
    return out


def _data_paths_from_blocks(blocks: list[Any]) -> list[str]:
    paths: list[str] = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        props = b.get("props")
        if isinstance(props, dict):
            dp = str(props.get("dataPath") or "").strip()
            if dp:
                paths.append(dp)
    return paths


def _filter_data_for_visible_blocks(
    data: dict[str, Any], filtered_layout: dict[str, Any]
) -> dict[str, Any]:
    blocks = filtered_layout.get("blocks")
    if not isinstance(blocks, list) or not isinstance(data, dict):
        return {}
    paths = _data_paths_from_blocks(blocks)
    keys: set[str] = set()
    for p in paths:
        if not p:
            continue
        keys.add(p.split(".")[0])
    if not keys:
        return {}
    return {k: v for k, v in data.items() if k in keys}


def _allowed_data_keys_from_layout(full_layout: dict[str, Any], allowed: frozenset[str]) -> set[str]:
    blocks = [
        b
        for b in (full_layout.get("blocks") or [])
        if isinstance(b, dict) and str(b.get("id") or "").strip() in allowed
    ]
    paths = _data_paths_from_blocks(blocks)
    keys: set[str] = set()
    for p in paths:
        if not p:
            continue
        keys.add(p.split(".")[0])
    return keys


def _merge_granular_data(
    full_data: dict[str, Any],
    patch: dict[str, Any] | None,
    full_layout: dict[str, Any],
    allowed: frozenset[str],
) -> dict[str, Any]:
    keys = _allowed_data_keys_from_layout(full_layout, allowed)
    out = dict(full_data)
    if not patch:
        return out
    for k in keys:
        if k in patch:
            out[k] = patch[k]
    return out


def _merge_ui_layout_granular(
    full_ul: dict[str, Any], patch_ul: dict[str, Any] | None, allowed: frozenset[str]
) -> dict[str, Any]:
    if not patch_ul:
        return full_ul
    pblocks = patch_ul.get("blocks")
    if not isinstance(pblocks, list):
        return full_ul
    pb_by_id: dict[str, dict[str, Any]] = {}
    for b in pblocks:
        if not isinstance(b, dict):
            continue
        bid = str(b.get("id") or "").strip()
        if bid and bid in allowed:
            pb_by_id[bid] = b
    out_bl: list[Any] = []
    for b in full_ul.get("blocks") or []:
        if not isinstance(b, dict):
            continue
        bid = str(b.get("id") or "").strip()
        if bid in allowed and bid in pb_by_id:
            out_bl.append(pb_by_id[bid])
        else:
            out_bl.append(b)
    out = dict(full_ul)
    out["blocks"] = out_bl
    return out


def _workspace_update_granular(
    user_id: uuid.UUID,
    tenant_id: int,
    workspace_id: uuid.UUID,
    *,
    title: str | None,
    ui_layout: dict[str, Any] | None,
    data: dict[str, Any] | None,
    allowed: frozenset[str],
) -> dict[str, Any] | None:
    """Patch only allowed blocks / related data keys; ignore title changes."""
    _ = title
    sets: list[str] = []
    args: list[Any] = []
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT ui_layout, data FROM user_workspaces
                WHERE id = %s AND tenant_id = %s
                """,
                (workspace_id, tenant_id),
            )
            row = cur.fetchone()
            if not row:
                conn.commit()
                return None
            full_ul = row["ui_layout"] if isinstance(row["ui_layout"], dict) else {}
            full_dt = row["data"] if isinstance(row["data"], dict) else {}
            new_ul = full_ul
            new_dt = full_dt
            if data is not None:
                new_dt = _merge_granular_data(full_dt, data, full_ul, allowed)
            if ui_layout is not None:
                new_ul = _merge_ui_layout_granular(full_ul, ui_layout, allowed)
            if new_ul == full_ul and new_dt == full_dt:
                conn.commit()
                return workspace_get(user_id, tenant_id, workspace_id)
            sets.append("ui_layout = %s")
            args.append(Json(new_ul))
            sets.append("data = %s")
            args.append(Json(new_dt))
            sets.append("updated_at = now()")
            args.extend([workspace_id, tenant_id, user_id])
            cur.execute(
                f"""
                UPDATE user_workspaces w
                SET {", ".join(sets)}
                WHERE w.id = %s AND w.tenant_id = %s
                  AND EXISTS (
                    SELECT 1 FROM workspace_block_share_grants g
                    WHERE g.workspace_id = w.id
                      AND g.viewer_user_id = %s
                      AND g.tenant_id = w.tenant_id
                      AND g.permission = 'edit'
                  )
                RETURNING w.id, w.kind, w.title, w.ui_layout, w.data, w.created_at, w.updated_at
                """,
                args,
            )
            urow = cur.fetchone()
        conn.commit()
    if not urow:
        return None
    out = _row_dict(dict(urow))
    d = workspace_access_ex(user_id, tenant_id, workspace_id)
    out["access_role"] = d.role or "editor"
    if d.allowed_block_ids is not None:
        ul = out.get("ui_layout") if isinstance(out.get("ui_layout"), dict) else {}
        out["ui_layout"] = _filter_ui_layout(ul, d.allowed_block_ids)
        dt = out.get("data") if isinstance(out.get("data"), dict) else {}
        out["data"] = _filter_data_for_visible_blocks(dt, out["ui_layout"])
        out["access_scope"] = "granular"
        out["allowed_block_ids"] = sorted(d.allowed_block_ids)
        out["granular_can_write"] = d.granular_can_write
    else:
        out["access_scope"] = "full"
    return out


def workspace_can_manage_members(
    user_id: uuid.UUID, tenant_id: int, workspace_id: uuid.UUID
) -> bool:
    """Primary owner or co_owner may list/add/remove workspace members."""
    role = workspace_access(user_id, tenant_id, workspace_id)
    return role == "owner" or role == "co_owner"


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
                    WHEN m.role IS NOT NULL THEN m.role::text
                    WHEN g.viewer_user_id IS NOT NULL THEN
                      CASE
                        WHEN COALESCE(g.permission, 'view') = 'edit' THEN 'editor'
                        ELSE 'viewer'
                      END
                    ELSE 'owner'
                  END AS access_role
                FROM user_workspaces w
                LEFT JOIN workspace_members m
                  ON m.workspace_id = w.id AND m.user_id = %s
                LEFT JOIN workspace_block_share_grants g
                  ON g.workspace_id = w.id AND g.viewer_user_id = %s AND g.tenant_id = w.tenant_id
                WHERE w.tenant_id = %s
                  AND (
                    w.owner_user_id = %s
                    OR m.user_id IS NOT NULL
                    OR g.viewer_user_id IS NOT NULL
                  )
                ORDER BY w.updated_at DESC
                LIMIT %s
                """,
                (user_id, user_id, user_id, tenant_id, user_id, limit),
            )
            rows = cur.fetchall()
        conn.commit()
    out: list[dict[str, Any]] = []
    for r in rows:
        wid = r[0]
        if not isinstance(wid, uuid.UUID):
            wid = uuid.UUID(str(wid))
        role = (r[5] or "owner").strip().lower()
        if role not in ("owner", "co_owner", "editor", "viewer"):
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
    d = workspace_access_ex(user_id, tenant_id, workspace_id)
    if d.role is None:
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
    out["access_role"] = d.role
    if d.allowed_block_ids is not None:
        ul = out.get("ui_layout") if isinstance(out.get("ui_layout"), dict) else {}
        out["ui_layout"] = _filter_ui_layout(ul, d.allowed_block_ids)
        dt = out.get("data") if isinstance(out.get("data"), dict) else {}
        out["data"] = _filter_data_for_visible_blocks(dt, out["ui_layout"])
        out["access_scope"] = "granular"
        out["allowed_block_ids"] = sorted(d.allowed_block_ids)
        out["granular_can_write"] = d.granular_can_write
    else:
        out["access_scope"] = "full"
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
    d = workspace_access_ex(user_id, tenant_id, workspace_id)
    if d.role is None:
        return None
    if d.allowed_block_ids is not None:
        if not d.granular_can_write:
            return None
        return _workspace_update_granular(
            user_id,
            tenant_id,
            workspace_id,
            title=title,
            ui_layout=ui_layout,
            data=data,
            allowed=d.allowed_block_ids,
        )
    if d.role == "viewer":
        return None
    role = d.role
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
                      WHERE m.workspace_id = w.id AND m.user_id = %s
                        AND m.role IN ('editor', 'co_owner')
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
    actor_user_id: uuid.UUID, tenant_id: int, workspace_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Primary owner or co_owner may list members."""
    if not workspace_can_manage_members(actor_user_id, tenant_id, workspace_id):
        return []
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM user_workspaces
                WHERE id = %s AND tenant_id = %s
                """,
                (workspace_id, tenant_id),
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
    actor_user_id: uuid.UUID,
    tenant_id: int,
    workspace_id: uuid.UUID,
    member_user_id: uuid.UUID,
    role: str,
) -> bool:
    r = (role or "").strip().lower()
    if r not in ("viewer", "editor", "co_owner"):
        return False
    if not workspace_can_manage_members(actor_user_id, tenant_id, workspace_id):
        return False
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT owner_user_id FROM user_workspaces
                WHERE id = %s AND tenant_id = %s
                """,
                (workspace_id, tenant_id),
            )
            row = cur.fetchone()
            if row is None:
                conn.commit()
                return False
            primary_owner = row[0]
            if not isinstance(primary_owner, uuid.UUID):
                primary_owner = uuid.UUID(str(primary_owner))
            if member_user_id == primary_owner:
                return False
    mtid = db.user_tenant_id(member_user_id)
    if mtid != tenant_id:
        return False
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
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


def _layout_block_ids(ui_layout: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    blocks = ui_layout.get("blocks")
    if not isinstance(blocks, list):
        return out
    for b in blocks:
        if isinstance(b, dict):
            bid = str(b.get("id") or "").strip()
            if bid:
                out.add(bid)
    return out


def block_share_grants_list(
    actor_user_id: uuid.UUID, tenant_id: int, workspace_id: uuid.UUID
) -> list[dict[str, Any]]:
    if not workspace_can_manage_members(actor_user_id, tenant_id, workspace_id):
        return []
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT g.viewer_user_id, g.block_ids, g.created_at, u.email,
                  COALESCE(g.permission, 'view') AS permission
                FROM workspace_block_share_grants g
                JOIN users u ON u.id = g.viewer_user_id
                WHERE g.workspace_id = %s AND g.tenant_id = %s
                ORDER BY u.email ASC
                """,
                (workspace_id, tenant_id),
            )
            rows = cur.fetchall()
        conn.commit()
    result: list[dict[str, Any]] = []
    for r in rows:
        uid, bid, created, email, perm_raw = r[0], r[1], r[2], r[3], r[4]
        perm = str(perm_raw or "view").strip().lower()
        if perm not in ("view", "edit"):
            perm = "view"
        result.append(
            {
                "user_id": str(uid),
                "email": (email or "").strip(),
                "block_ids": list(bid) if isinstance(bid, list) else [],
                "permission": perm,
                "created_at": created.isoformat() if isinstance(created, datetime) else str(created),
            }
        )
    return result


def block_share_grant_upsert(
    actor_user_id: uuid.UUID,
    tenant_id: int,
    workspace_id: uuid.UUID,
    *,
    viewer_user_id: uuid.UUID,
    block_ids: list[str],
    permission: str = "view",
) -> bool:
    if not workspace_can_manage_members(actor_user_id, tenant_id, workspace_id):
        return False
    perm = str(permission or "view").strip().lower()
    if perm not in ("view", "edit"):
        return False
    if db.user_tenant_id(viewer_user_id) != tenant_id:
        return False
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT owner_user_id, ui_layout FROM user_workspaces
                WHERE id = %s AND tenant_id = %s
                """,
                (workspace_id, tenant_id),
            )
            row = cur.fetchone()
            if not row:
                conn.commit()
                return False
            owner_uid, ul = row[0], row[1]
            if not isinstance(owner_uid, uuid.UUID):
                owner_uid = uuid.UUID(str(owner_uid))
            if viewer_user_id == owner_uid:
                conn.commit()
                return False
            ui_layout = ul if isinstance(ul, dict) else {}
            valid = _layout_block_ids(ui_layout)
            cleaned = [str(x).strip() for x in block_ids if str(x).strip()]
            cleaned = [x for x in cleaned if x in valid]
            if not cleaned:
                conn.commit()
                return False
            cur.execute(
                """
                INSERT INTO workspace_block_share_grants (
                  workspace_id, viewer_user_id, tenant_id, block_ids, created_by, permission
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, viewer_user_id)
                DO UPDATE SET
                  block_ids = EXCLUDED.block_ids,
                  created_by = EXCLUDED.created_by,
                  permission = EXCLUDED.permission
                """,
                (
                    workspace_id,
                    viewer_user_id,
                    tenant_id,
                    cleaned,
                    actor_user_id,
                    perm,
                ),
            )
        conn.commit()
    return True


def block_share_grant_delete(
    actor_user_id: uuid.UUID,
    tenant_id: int,
    workspace_id: uuid.UUID,
    viewer_user_id: uuid.UUID,
) -> bool:
    if not workspace_can_manage_members(actor_user_id, tenant_id, workspace_id):
        return False
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM workspace_block_share_grants
                WHERE workspace_id = %s AND tenant_id = %s AND viewer_user_id = %s
                """,
                (workspace_id, tenant_id, viewer_user_id),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0


def member_remove(
    actor_user_id: uuid.UUID,
    tenant_id: int,
    workspace_id: uuid.UUID,
    member_user_id: uuid.UUID,
) -> bool:
    if not workspace_can_manage_members(actor_user_id, tenant_id, workspace_id):
        return False
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT owner_user_id FROM user_workspaces
                WHERE id = %s AND tenant_id = %s
                """,
                (workspace_id, tenant_id),
            )
            row = cur.fetchone()
            if row is None:
                conn.commit()
                return False
            primary_owner = row[0]
            if not isinstance(primary_owner, uuid.UUID):
                primary_owner = uuid.UUID(str(primary_owner))
            if member_user_id == primary_owner:
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
