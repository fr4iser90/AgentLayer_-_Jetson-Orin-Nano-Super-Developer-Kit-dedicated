"""Rolling chat context for out-of-band gateways (Telegram, Discord, …) → ``chat_messages``.

The Web UI and HTTP ``/v1/chat/completions`` already send full ``messages[]`` from the client;
only bridges that used to pass a single user turn need this persistence.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from psycopg.types.json import Json

from src.infrastructure.conversations_db import conversation_delete, conversation_get
from src.infrastructure.db import db

BridgeProvider = Literal["telegram", "discord"]

BRIDGE_TELEGRAM: BridgeProvider = "telegram"
BRIDGE_DISCORD: BridgeProvider = "discord"

# Cap messages sent to the LLM (user + assistant turns); avoids huge prompts on long chats.
MAX_CONTEXT_MESSAGES = 48


def _thread_key(thread_id: int | None) -> int:
    return int(thread_id) if thread_id is not None else 0


def bridge_agent_conversation_ensure(
    user_id: uuid.UUID,
    tenant_id: int,
    *,
    provider: BridgeProvider,
    scope_chat_id: int,
    scope_thread_id: int | None,
    model: str,
) -> uuid.UUID:
    """Return ``conversation_id`` for this peer, creating an empty conversation if needed."""
    tk = _thread_key(scope_thread_id)
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT conversation_id FROM bridge_agent_sessions
                WHERE user_id = %s AND provider = %s AND scope_chat_id = %s AND scope_thread_id = %s
                """,
                (user_id, provider, scope_chat_id, tk),
            )
            row = cur.fetchone()
            if row:
                cid = row[0]
                return cid if isinstance(cid, uuid.UUID) else uuid.UUID(str(cid))
            conv_id = uuid.uuid4()
            title = f"{provider} {scope_chat_id}" + (f" · thread {tk}" if tk else "")
            cur.execute(
                """
                INSERT INTO chat_conversations (
                  id, user_id, tenant_id, workspace_id, title, mode, model, agent_log, shared
                )
                VALUES (%s, %s, %s, NULL, %s, 'agent', %s, %s::jsonb, false)
                """,
                (conv_id, user_id, tenant_id, title, model, Json([])),
            )
            cur.execute(
                """
                INSERT INTO bridge_agent_sessions (
                  user_id, provider, scope_chat_id, scope_thread_id, conversation_id
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, provider, scope_chat_id, tk, conv_id),
            )
        conn.commit()
    return conv_id


def bridge_agent_session_reset(
    user_id: uuid.UUID,
    *,
    provider: BridgeProvider,
    scope_chat_id: int,
    scope_thread_id: int | None,
) -> bool:
    """Delete stored messages for this bridge session."""
    tk = _thread_key(scope_thread_id)
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT conversation_id FROM bridge_agent_sessions
                WHERE user_id = %s AND provider = %s AND scope_chat_id = %s AND scope_thread_id = %s
                """,
                (user_id, provider, scope_chat_id, tk),
            )
            row = cur.fetchone()
    if not row:
        return False
    cid = row[0]
    conv_id = cid if isinstance(cid, uuid.UUID) else uuid.UUID(str(cid))
    return conversation_delete(user_id, conv_id)


def messages_for_bridge_completion(
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    new_user_text: str,
) -> list[dict[str, Any]]:
    """Load history (trimmed), append the new user turn; roles ``user`` / ``assistant`` only."""
    conv = conversation_get(user_id, conversation_id)
    if not conv:
        return [{"role": "user", "content": new_user_text}]
    raw = conv.get("messages") or []
    out: list[dict[str, Any]] = []
    for m in raw:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = m.get("content")
        if content is None:
            continue
        if not isinstance(content, str):
            continue
        if not content.strip():
            continue
        out.append({"role": role, "content": content})
    if len(out) > MAX_CONTEXT_MESSAGES:
        out = out[-MAX_CONTEXT_MESSAGES:]
    out.append({"role": "user", "content": new_user_text})
    return out
