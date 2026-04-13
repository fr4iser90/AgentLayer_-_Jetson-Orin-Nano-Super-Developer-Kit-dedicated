"""Persistence for server-side chat conversations (first-party UI)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from psycopg.types.json import Json

from src.infrastructure.db import db


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


def conversations_list(user_id: uuid.UUID) -> list[dict[str, Any]]:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.title, c.mode, c.model, c.updated_at,
                  (SELECT COUNT(*)::int FROM chat_messages m WHERE m.conversation_id = c.id)
                FROM chat_conversations c
                WHERE c.user_id = %s
                ORDER BY c.updated_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        cid = r[0]
        if not isinstance(cid, uuid.UUID):
            cid = uuid.UUID(str(cid))
        out.append(
            {
                "id": str(cid),
                "title": r[1] or "",
                "mode": r[2],
                "model": r[3] or "",
                "updated_at": r[4].isoformat() if isinstance(r[4], datetime) else str(r[4]),
                "message_count": int(r[5] or 0),
            }
        )
    return out


def conversation_get(user_id: uuid.UUID, conversation_id: uuid.UUID) -> dict[str, Any] | None:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, mode, model, agent_log, updated_at, created_at
                FROM chat_conversations
                WHERE id = %s AND user_id = %s
                """,
                (conversation_id, user_id),
            )
            crow = cur.fetchone()
            if not crow:
                return None
            cur.execute(
                """
                SELECT role, content FROM chat_messages
                WHERE conversation_id = %s
                ORDER BY position ASC
                """,
                (conversation_id,),
            )
            mrows = cur.fetchall()
    agent_log = crow[4]
    if isinstance(agent_log, str):
        import json

        try:
            agent_log = json.loads(agent_log)
        except Exception:
            agent_log = []
    if not isinstance(agent_log, list):
        agent_log = []
    messages = [
        {"role": mr[0], "content": _deserialize_message_content(mr[1])} for mr in mrows
    ]
    cid = crow[0]
    return {
        "id": str(cid if isinstance(cid, uuid.UUID) else uuid.UUID(str(cid))),
        "title": crow[1] or "",
        "mode": crow[2],
        "model": crow[3] or "",
        "agent_log": agent_log,
        "messages": messages,
        "updated_at": crow[5].isoformat() if isinstance(crow[5], datetime) else str(crow[5]),
        "created_at": crow[6].isoformat() if isinstance(crow[6], datetime) else str(crow[6]),
    }


def conversation_create(
    user_id: uuid.UUID,
    *,
    title: str,
    mode: str,
    model: str,
    messages: list[dict[str, Any]],
    agent_log: list[Any],
) -> dict[str, Any]:
    tenant_id = _user_tenant_id(user_id)
    conv_id = uuid.uuid4()
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_conversations (id, user_id, tenant_id, title, mode, model, agent_log)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (conv_id, user_id, tenant_id, title, mode, model, Json(agent_log)),
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
                "SELECT 1 FROM chat_conversations WHERE id = %s AND user_id = %s",
                (conversation_id, user_id),
            )
            if cur.fetchone() is None:
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
            args.extend([conversation_id, user_id])
            # SET fragments are fixed literals; values are always %s-bound (not SQL keyword injection).
            cur.execute(  # nosec B608  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
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
                "DELETE FROM chat_conversations WHERE id = %s AND user_id = %s RETURNING id",
                (conversation_id, user_id),
            )
            row = cur.fetchone()
        conn.commit()
    return row is not None
