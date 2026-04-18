"""Persistence for server-side chat conversations (first-party UI)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from psycopg.types.json import Json

from src.infrastructure.db import db
from src.workspace import db as workspace_db


def _serialize_message_content(content: Any) -> str:
    """Store plain string or JSON-encode multimodal / structured content."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def _deserialize_message_content(raw: str | None) -> Any:
    """Restore OpenAI-style multimodal arrays saved as JSON text."""
    s = raw or ""
    st = s.strip()
    if not st:
        return ""
    if st.startswith("["):
        try:
            out = json.loads(s)
            if isinstance(out, list):
                return out
        except json.JSONDecodeError:
            pass
    return s


def _user_tenant_id(user_id: uuid.UUID) -> int:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tenant_id FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError("user not found")
            return int(row[0])


def _shared_chat_can_write(user_id: uuid.UUID, tenant_id: int, workspace_id: uuid.UUID) -> bool:
    role = workspace_db.workspace_access(user_id, tenant_id, workspace_id)
    return role is not None and role != "viewer"


def _row_to_list_item(
    r: tuple[Any, ...],
) -> dict[str, Any]:
    cid = r[0]
    if not isinstance(cid, uuid.UUID):
        cid = uuid.UUID(str(cid))
    wid = r[6]
    ws_out: str | None = None
    if wid is not None:
        ws_out = str(wid) if isinstance(wid, uuid.UUID) else str(uuid.UUID(str(wid)))
    shared = bool(r[7])
    return {
        "id": str(cid),
        "title": r[1] or "",
        "mode": r[2],
        "model": r[3] or "",
        "updated_at": r[4].isoformat() if isinstance(r[4], datetime) else str(r[4]),
        "message_count": int(r[5] or 0),
        "workspace_id": ws_out,
        "shared": shared,
    }


def conversations_list(
    user_id: uuid.UUID, *, workspace_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    tenant_id = _user_tenant_id(user_id)
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            if workspace_id is not None:
                cur.execute(
                    """
                    SELECT c.id, c.title, c.mode, c.model, c.updated_at,
                      (SELECT COUNT(*)::int FROM chat_messages m WHERE m.conversation_id = c.id),
                      c.workspace_id, c.shared
                    FROM chat_conversations c
                    WHERE c.workspace_id = %s
                      AND (
                        (c.shared = true AND EXISTS (
                          SELECT 1 FROM user_workspaces w
                          LEFT JOIN workspace_members m
                            ON m.workspace_id = w.id AND m.user_id = %s
                          WHERE w.id = c.workspace_id AND w.tenant_id = c.tenant_id
                            AND (w.owner_user_id = %s OR m.user_id IS NOT NULL)
                        ))
                        OR (c.shared = false AND c.user_id = %s)
                      )
                    ORDER BY c.shared DESC, c.updated_at DESC
                    """,
                    (workspace_id, user_id, user_id, user_id),
                )
            else:
                cur.execute(
                    """
                    SELECT c.id, c.title, c.mode, c.model, c.updated_at,
                      (SELECT COUNT(*)::int FROM chat_messages m WHERE m.conversation_id = c.id),
                      c.workspace_id, c.shared
                    FROM chat_conversations c
                    WHERE c.tenant_id = %s
                      AND (
                        (c.user_id = %s AND c.shared = false)
                        OR (
                          c.shared = true
                          AND c.workspace_id IS NOT NULL
                          AND (
                            EXISTS (
                              SELECT 1 FROM user_workspaces w
                              WHERE w.id = c.workspace_id
                                AND w.tenant_id = c.tenant_id
                                AND w.owner_user_id = %s
                            )
                            OR EXISTS (
                              SELECT 1 FROM workspace_members m
                              WHERE m.workspace_id = c.workspace_id AND m.user_id = %s
                            )
                          )
                        )
                      )
                    ORDER BY c.updated_at DESC
                    """,
                    (tenant_id, user_id, user_id, user_id),
                )
            rows = cur.fetchall()
    return [_row_to_list_item(r) for r in rows]


def _fetch_messages(cur: Any, conversation_id: uuid.UUID) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT role, content FROM chat_messages
        WHERE conversation_id = %s
        ORDER BY position ASC
        """,
        (conversation_id,),
    )
    mrows = cur.fetchall()
    return [
        {"role": mr[0], "content": _deserialize_message_content(mr[1])} for mr in mrows
    ]


def conversation_get(user_id: uuid.UUID, conversation_id: uuid.UUID) -> dict[str, Any] | None:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, mode, model, agent_log, updated_at, created_at, workspace_id,
                       user_id, tenant_id, shared
                FROM chat_conversations
                WHERE id = %s
                """,
                (conversation_id,),
            )
            crow = cur.fetchone()
            if not crow:
                return None
            cid_raw = crow[0]
            wid = crow[7]
            row_user = crow[8]
            tenant_id = int(crow[9])
            shared = bool(crow[10])
            if shared and wid is not None:
                if not workspace_db.workspace_has_full_access(user_id, tenant_id, wid):
                    return None
            elif row_user != user_id:
                return None
            messages = _fetch_messages(cur, conversation_id)
    agent_log = crow[4]
    if isinstance(agent_log, str):
        try:
            agent_log = json.loads(agent_log)
        except Exception:
            agent_log = []
    if not isinstance(agent_log, list):
        agent_log = []
    cid = cid_raw
    ws_out: str | None = None
    if wid is not None:
        ws_out = str(wid) if isinstance(wid, uuid.UUID) else str(uuid.UUID(str(wid)))
    return {
        "id": str(cid if isinstance(cid, uuid.UUID) else uuid.UUID(str(cid))),
        "title": crow[1] or "",
        "mode": crow[2],
        "model": crow[3] or "",
        "agent_log": agent_log,
        "messages": messages,
        "updated_at": crow[5].isoformat() if isinstance(crow[5], datetime) else str(crow[5]),
        "created_at": crow[6].isoformat() if isinstance(crow[6], datetime) else str(crow[6]),
        "workspace_id": ws_out,
        "shared": shared,
    }


def conversation_create(
    user_id: uuid.UUID,
    *,
    title: str,
    mode: str,
    model: str,
    messages: list[dict[str, Any]],
    agent_log: list[Any],
    workspace_id: uuid.UUID | None = None,
    shared: bool = False,
) -> dict[str, Any]:
    tenant_id = _user_tenant_id(user_id)
    if shared:
        if workspace_id is None:
            raise ValueError("shared conversation requires workspace_id")
        if not _shared_chat_can_write(user_id, tenant_id, workspace_id):
            raise PermissionError("cannot create shared workspace chat for this user")
        with db.pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM chat_conversations
                    WHERE workspace_id = %s AND shared = true
                    LIMIT 1
                    """,
                    (workspace_id,),
                )
                existing = cur.fetchone()
                if existing is not None:
                    eid = existing[0]
                    if not isinstance(eid, uuid.UUID):
                        eid = uuid.UUID(str(eid))
                    conn.commit()
                    got = conversation_get(user_id, eid)
                    if got:
                        return got
                    raise RuntimeError("conversation_create: existing shared row invisible")
                cur.execute(
                    """
                    SELECT owner_user_id, tenant_id FROM user_workspaces
                    WHERE id = %s AND tenant_id = %s
                    """,
                    (workspace_id, tenant_id),
                )
                ws_row = cur.fetchone()
                if ws_row is None:
                    conn.commit()
                    raise ValueError("workspace not found")
                owner_uid = ws_row[0]
                if not isinstance(owner_uid, uuid.UUID):
                    owner_uid = uuid.UUID(str(owner_uid))
                conv_id = uuid.uuid4()
                cur.execute(
                    """
                    INSERT INTO chat_conversations (
                      id, user_id, tenant_id, workspace_id, title, mode, model, agent_log, shared
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, true)
                    """,
                    (
                        conv_id,
                        owner_uid,
                        tenant_id,
                        workspace_id,
                        title,
                        mode,
                        model,
                        Json(agent_log),
                    ),
                )
                for i, m in enumerate(messages):
                    role = m.get("role") or "user"
                    content = _serialize_message_content(m.get("content"))
                    if role not in ("user", "assistant", "system"):
                        role = "user"
                    cur.execute(
                        """
                        INSERT INTO chat_messages (conversation_id, position, role, content)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (conv_id, i, role, content),
                    )
            conn.commit()
        got = conversation_get(user_id, conv_id)
        if not got:
            raise RuntimeError("conversation_create: row missing after insert")
        return got

    conv_id = uuid.uuid4()
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_conversations (
                  id, user_id, tenant_id, workspace_id, title, mode, model, agent_log, shared
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, false)
                """,
                (conv_id, user_id, tenant_id, workspace_id, title, mode, model, Json(agent_log)),
            )
            for i, m in enumerate(messages):
                role = m.get("role") or "user"
                content = _serialize_message_content(m.get("content"))
                if role not in ("user", "assistant", "system"):
                    role = "user"
                cur.execute(
                    """
                    INSERT INTO chat_messages (conversation_id, position, role, content)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (conv_id, i, role, content),
                )
        conn.commit()
    got = conversation_get(user_id, conv_id)
    if not got:
        raise RuntimeError("conversation_create: row missing after insert")
    return got


def conversation_replace(
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    title: str | None,
    mode: str | None,
    model: str | None,
    messages: list[dict[str, Any]] | None,
    agent_log: list[Any] | None,
) -> dict[str, Any] | None:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, tenant_id, workspace_id, shared
                FROM chat_conversations WHERE id = %s
                """,
                (conversation_id,),
            )
            meta = cur.fetchone()
            if meta is None:
                return None
            row_user, tenant_id, ws_id, shared = (
                meta[0],
                int(meta[1]),
                meta[2],
                bool(meta[3]),
            )
            if shared and ws_id is not None:
                if not _shared_chat_can_write(user_id, tenant_id, ws_id):
                    return None
            elif row_user != user_id:
                return None
            parts: list[str] = []
            args: list[Any] = []
            if title is not None:
                parts.append("title = %s")
                args.append(title)
            if mode is not None:
                parts.append("mode = %s")
                args.append(mode if mode in ("chat", "agent") else "chat")
            if model is not None:
                parts.append("model = %s")
                args.append(model)
            if agent_log is not None:
                parts.append("agent_log = %s::jsonb")
                args.append(Json(agent_log))
            parts.append("updated_at = now()")
            if shared:
                args.append(conversation_id)
                cur.execute(  # nosec B608
                    f"""
                    UPDATE chat_conversations SET {", ".join(parts)}
                    WHERE id = %s
                    """,
                    args,
                )
            else:
                args.extend([conversation_id, user_id])
                cur.execute(  # nosec B608
                    f"""
                    UPDATE chat_conversations SET {", ".join(parts)}
                    WHERE id = %s AND user_id = %s
                    """,
                    args,
                )
            if messages is not None:
                cur.execute(
                    "DELETE FROM chat_messages WHERE conversation_id = %s",
                    (conversation_id,),
                )
                for i, m in enumerate(messages):
                    role = m.get("role") or "user"
                    content = _serialize_message_content(m.get("content"))
                    if role not in ("user", "assistant", "system"):
                        role = "user"
                    cur.execute(
                        """
                        INSERT INTO chat_messages (conversation_id, position, role, content)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (conversation_id, i, role, content),
                    )
        conn.commit()
    return conversation_get(user_id, conversation_id)


def conversation_delete(user_id: uuid.UUID, conversation_id: uuid.UUID) -> bool:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, tenant_id, workspace_id, shared
                FROM chat_conversations WHERE id = %s
                """,
                (conversation_id,),
            )
            meta = cur.fetchone()
            if meta is None:
                return False
            row_user, tenant_id, ws_id, shared = (
                meta[0],
                int(meta[1]),
                meta[2],
                bool(meta[3]),
            )
            if shared and ws_id is not None:
                if not _shared_chat_can_write(user_id, tenant_id, ws_id):
                    return False
                cur.execute(
                    "DELETE FROM chat_conversations WHERE id = %s RETURNING id",
                    (conversation_id,),
                )
            elif row_user != user_id:
                return False
            else:
                cur.execute(
                    "DELETE FROM chat_conversations WHERE id = %s AND user_id = %s RETURNING id",
                    (conversation_id, user_id),
                )
            row = cur.fetchone()
        conn.commit()
    return row is not None


def conversation_append_message(
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    role: str,
    content: Any,
) -> bool:
    """Append one message to a conversation (next ``position``). Personal chats only (same checks as delete)."""
    if role not in ("user", "assistant", "system"):
        return False
    serialized = _serialize_message_content(content)
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, workspace_id, shared FROM chat_conversations WHERE id = %s
                """,
                (conversation_id,),
            )
            meta = cur.fetchone()
            if meta is None:
                return False
            row_user, _ws_id, shared = meta[0], meta[1], bool(meta[2])
            if shared:
                return False
            if row_user != user_id:
                return False
            cur.execute(
                """
                SELECT COALESCE(MAX(position), -1) + 1 FROM chat_messages
                WHERE conversation_id = %s
                """,
                (conversation_id,),
            )
            pos_row = cur.fetchone()
            pos = int(pos_row[0]) if pos_row else 0
            cur.execute(
                """
                INSERT INTO chat_messages (conversation_id, position, role, content)
                VALUES (%s, %s, %s, %s)
                """,
                (conversation_id, pos, role, serialized),
            )
            cur.execute(
                "UPDATE chat_conversations SET updated_at = now() WHERE id = %s",
                (conversation_id,),
            )
        conn.commit()
    return True
