"""Resolve ``workspace_id`` for agent tools when the user omits it (single board of that ``kind``)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from src.workspace import db as workspace_db


def parse_workspace_uuid_arg(raw: str | None) -> uuid.UUID | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


def workspace_rows_for_kind(
    user_id: uuid.UUID, tenant_id: int, kind: str, *, limit: int = 200
) -> list[dict[str, Any]]:
    want = (kind or "").strip().lower()
    rows = workspace_db.workspace_list(user_id, tenant_id, limit=limit)
    return [r for r in rows if (r.get("kind") or "").strip().lower() == want]


def resolve_workspace_id_for_kind(
    user_id: uuid.UUID,
    tenant_id: int,
    *,
    kind: str,
    raw_workspace_id: Any,
) -> tuple[uuid.UUID | None, str | None]:
    """
    If ``raw_workspace_id`` is non-empty, it must be a valid UUID.
    If omitted or empty, pick the workspace when exactly one row matches ``kind``;
    otherwise return an error string (no board, or ambiguous list).
    """
    if raw_workspace_id is not None and str(raw_workspace_id).strip():
        wid = parse_workspace_uuid_arg(str(raw_workspace_id).strip())
        if wid is None:
            return None, "workspace_id must be a valid UUID when provided"
        return wid, None
    rows = workspace_rows_for_kind(user_id, tenant_id, kind)
    label = (kind or "").strip() or "workspace"
    if not rows:
        return None, f"No {label} workspace yet — create one in the app first."
    if len(rows) == 1:
        rid = rows[0].get("id")
        try:
            return (rid if isinstance(rid, uuid.UUID) else uuid.UUID(str(rid))), None
        except (ValueError, TypeError):
            return None, "internal error: invalid workspace id in list"
    opts = [
        {"id": str(r.get("id", "")), "title": (r.get("title") or "").strip()}
        for r in rows[:40]
    ]
    return None, (
        f"Multiple {label} workspaces — pass workspace_id (UUID). Boards: "
        + json.dumps(opts, ensure_ascii=False)
    )
