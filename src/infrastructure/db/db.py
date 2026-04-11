"""PostgreSQL pool and persistence helpers. Schema changes: Alembic (see entrypoint)."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import ConnectionPool

from src.core.config import config
from src.domain.identity import get_identity

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("database pool not initialized")
    return _pool


def init_pool() -> None:
    global _pool
    if not config.DATABASE_URL:
        raise RuntimeError(
            "PostgreSQL connection missing: DATABASE_URL is empty and could not be built from "
            "POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB (and PGHOST defaulting to postgres). "
            "Fix: set DATABASE_URL in docker/.env (see .env.example), or pass the same POSTGRES_* "
            "variables into the agent-layer container as for the postgres service, then restart."
        )
    if _pool is not None:
        return
    _pool = ConnectionPool(
        conninfo=config.DATABASE_URL,
        min_size=1,
        max_size=10,
        kwargs={"autocommit": False},
    )
    logger.info("PostgreSQL pool ready")


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def tenants_list() -> list[dict[str, Any]]:
    """All rows from ``tenants`` (for admin UI: ids used in tool allowlists and ``users.tenant_id``)."""
    with pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, name, created_at
                FROM tenants
                ORDER BY id ASC
                """
            )
            rows = cur.fetchall()
        conn.commit()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        ca = d.get("created_at")
        if ca is not None and hasattr(ca, "isoformat"):
            d["created_at"] = ca.isoformat()
        out.append(d)
    return out


def tenant_exists(tenant_id: int) -> bool:
    if tenant_id < 1:
        return False
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM tenants WHERE id = %s", (tenant_id,))
            ok = cur.fetchone() is not None
        conn.commit()
    return ok


def tenant_insert(name: str) -> dict[str, Any]:
    """Insert a tenant row; ``name`` trim, fallback label if empty."""
    label = (name or "").strip() or "tenant"
    with pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "INSERT INTO tenants (name) VALUES (%s) RETURNING id, name, created_at",
                (label,),
            )
            row = cur.fetchone()
        conn.commit()
    d = dict(row)
    ca = d.get("created_at")
    if ca is not None and hasattr(ca, "isoformat"):
        d["created_at"] = ca.isoformat()
    return d


def user_external_sub(user_id: uuid.UUID) -> str | None:
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT external_sub FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    return str(row[0]) if row[0] is not None else None


def user_tenant_id(user_id: uuid.UUID) -> int:
    """``users.tenant_id`` for FK-scoped data and tool policy (defaults to ``1``)."""
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tenant_id FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
        conn.commit()
    if not row or row[0] is None:
        return 1
    try:
        t = int(row[0])
    except (TypeError, ValueError):
        return 1
    return t if t >= 1 else 1


def user_role(user_id: uuid.UUID | None) -> str:
    """Return ``users.role`` (``user`` or ``admin``) for tool access checks."""
    if user_id is None:
        return "user"
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
        conn.commit()
    if not row or row[0] is None:
        return "user"
    r = str(row[0]).strip().lower()
    return r if r in ("user", "admin") else "user"


def _require_user_uuid() -> tuple[int, uuid.UUID]:
    tenant_id, user_id = get_identity()
    if user_id is None:
        raise ValueError(
            "no user identity in this context (chat/tool requests need user/tenant headers)"
        )
    return tenant_id, user_id


def todo_create(title: str) -> int:
    tenant_id, user_id = _require_user_uuid()
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO todos (title, tenant_id, user_id)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (title, tenant_id, user_id),
            )
            row = cur.fetchone()
            tid = int(row[0])
        conn.commit()
        return tid


def todo_list(limit: int = 100) -> list[dict[str, Any]]:
    tenant_id, user_id = _require_user_uuid()
    with pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, status, created_at, updated_at
                FROM todos
                WHERE tenant_id = %s AND user_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (tenant_id, user_id, limit),
            )
            rows = cur.fetchall()
        conn.commit()
    return [dict(r) for r in rows]


def todo_set_status(todo_id: int, status: str) -> bool:
    tenant_id, user_id = _require_user_uuid()
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE todos
                SET status = %s, updated_at = now()
                WHERE id = %s AND tenant_id = %s AND user_id = %s
                """,
                (status, todo_id, tenant_id, user_id),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0


def log_tool_invocation(
    tool_name: str,
    args: dict[str, Any],
    result_text: str,
    ok: bool,
) -> None:
    excerpt = (result_text or "")[:4000]
    tenant_id, user_id = get_identity()
    if user_id is None:
        return
    args_for_db: Any = args
    if isinstance(args, dict):
        redact = config.tool_log_redact_keys()
        if redact:
            args_for_db = {}
            for k, v in args.items():
                if k in redact and isinstance(v, str) and len(v) > 200:
                    args_for_db[k] = f"<omitted {len(v)} chars>"
                else:
                    args_for_db[k] = v
    try:
        with pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tool_invocations
                      (tool_name, args_json, result_excerpt, ok, tenant_id, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (tool_name, Json(args_for_db), excerpt, ok, tenant_id, user_id),
                )
            conn.commit()
    except psycopg.Error:
        logger.exception("failed to log tool_invocation for %s", tool_name)


def recent_tool_invocations(limit: int = 50) -> list[dict[str, Any]]:
    tenant_id, user_id = get_identity()
    if user_id is None:
        return []
    with pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, tool_name, args_json, result_excerpt, ok, created_at,
                       tenant_id, user_id
                FROM tool_invocations
                WHERE tenant_id = %s AND user_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (tenant_id, user_id, limit),
            )
            rows = cur.fetchall()
        conn.commit()
    return [dict(r) for r in rows]


def user_secret_upsert(user_id: uuid.UUID, service_key: str, plaintext: str) -> None:
    from src.infrastructure.crypto_secrets import crypto_secrets

    ct = crypto_secrets.encrypt_secret(plaintext)
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_secrets (user_id, service_key, ciphertext)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, service_key) DO UPDATE SET
                  ciphertext = EXCLUDED.ciphertext,
                  updated_at = now()
                """,
                (user_id, service_key, ct),
            )
        conn.commit()


def user_secret_get_plaintext(user_id: uuid.UUID, service_key: str) -> str | None:
    """Server-side only — never return this to LLM tool JSON."""
    from src.infrastructure.crypto_secrets import crypto_secrets

    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ciphertext FROM user_secrets
                WHERE user_id = %s AND service_key = %s
                """,
                (user_id, service_key),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    return crypto_secrets.decrypt_secret(bytes(row[0]))


def user_secret_delete(user_id: uuid.UUID, service_key: str) -> bool:
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM user_secrets
                WHERE user_id = %s AND service_key = %s
                """,
                (user_id, service_key),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0


def user_secret_list_service_keys(user_id: uuid.UUID) -> list[str]:
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT service_key FROM user_secrets
                WHERE user_id = %s
                ORDER BY service_key
                """,
                (user_id,),
            )
            rows = cur.fetchall()
        conn.commit()
    return [str(r[0]) for r in rows]


def secret_upload_otp_create(user_id: uuid.UUID, ttl_seconds: int = 600) -> str:
    """Insert a one-time registration token; return plaintext OTP (show once)."""
    raw = secrets.token_urlsafe(18)
    otp_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    expires = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO secret_upload_otps (user_id, otp_hash, expires_at)
                VALUES (%s, %s, %s)
                """,
                (user_id, otp_hash, expires),
            )
        conn.commit()
    return raw


def user_secret_register_with_otp(
    otp_raw: str, service_key: str, plaintext: str
) -> None:
    """Validate OTP (single-use), then upsert encrypted secret for bound user."""
    from src.infrastructure.crypto_secrets import crypto_secrets

    otp_raw = (otp_raw or "").strip()
    if not otp_raw:
        raise ValueError("otp is required")
    otp_hash = hashlib.sha256(otp_raw.encode("utf-8")).hexdigest()
    ct = crypto_secrets.encrypt_secret(plaintext)
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, used_at, expires_at
                FROM secret_upload_otps
                WHERE otp_hash = %s
                FOR UPDATE
                """,
                (otp_hash,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(
                    "unknown otp — check copy/paste (no spaces/line breaks), or mint a new one with register_secrets"
                )
            uid = row[0]
            if not isinstance(uid, uuid.UUID):
                uid = uuid.UUID(str(uid))
            used_at = row[1]
            expires_at = row[2]
            if used_at is not None:
                raise ValueError(
                    "otp already used (single-use) — call register_secrets again for a new curl_bash"
                )
            now_utc = datetime.now(UTC)
            if expires_at is not None:
                exp = expires_at
                if getattr(exp, "tzinfo", None) is None:
                    exp = exp.replace(tzinfo=UTC)
                if exp <= now_utc:
                    raise ValueError(
                        "otp expired — default validity 10 min; call register_secrets again"
                    )
            cur.execute(
                """
                UPDATE secret_upload_otps SET used_at = now()
                WHERE otp_hash = %s AND used_at IS NULL
                """,
                (otp_hash,),
            )
            cur.execute(
                """
                INSERT INTO user_secrets (user_id, service_key, ciphertext)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, service_key) DO UPDATE SET
                  ciphertext = EXCLUDED.ciphertext,
                  updated_at = now()
                """,
                (uid, service_key, ct),
            )
        conn.commit()


def kb_note_append(title: str, body: str) -> int:
    tenant_id, user_id = _require_user_uuid()
    title = (title or "").strip()
    body = (body or "").strip()
    if not body:
        raise ValueError("body is required")
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_kb_notes (title, body, tenant_id, user_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (title, body, tenant_id, user_id),
            )
            row = cur.fetchone()
            nid = int(row[0])
        conn.commit()
    return nid


def _ilike_contains(s: str) -> str:
    esc = s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


def kb_note_search(query: str, limit: int = 20) -> list[dict[str, Any]]:
    tenant_id, user_id = _require_user_uuid()
    q = (query or "").strip()
    if not q:
        return []
    limit = max(1, min(int(limit or 20), 50))
    pat = _ilike_contains(q)
    sql_full = """
                SELECT id, title, left(body, 500) AS body_excerpt, created_at
                FROM user_kb_notes
                WHERE tenant_id = %s
                  AND (
                    user_id = %s
                    OR id IN (
                      SELECT note_id FROM user_kb_note_shares
                      WHERE grantee_user_id = %s
                    )
                  )
                  AND (
                    title ILIKE %s ESCAPE '\\'
                    OR body ILIKE %s ESCAPE '\\'
                    OR search_tsv @@ websearch_to_tsquery('simple', %s)
                  )
                ORDER BY created_at DESC
                LIMIT %s
                """
    sql_ilike = """
                SELECT id, title, left(body, 500) AS body_excerpt, created_at
                FROM user_kb_notes
                WHERE tenant_id = %s
                  AND (
                    user_id = %s
                    OR id IN (
                      SELECT note_id FROM user_kb_note_shares
                      WHERE grantee_user_id = %s
                    )
                  )
                  AND (
                    title ILIKE %s ESCAPE '\\'
                    OR body ILIKE %s ESCAPE '\\'
                  )
                ORDER BY created_at DESC
                LIMIT %s
                """
    with pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            try:
                cur.execute(
                    sql_full,
                    (tenant_id, user_id, user_id, pat, pat, q, limit),
                )
            except psycopg.Error:
                logger.debug(
                    "kb_note_search fts fallback for query %r", q[:80], exc_info=True
                )
                conn.rollback()
                cur.execute(
                    sql_ilike,
                    (tenant_id, user_id, user_id, pat, pat, limit),
                )
            rows = cur.fetchall()
        conn.commit()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "title": r["title"],
                "body_excerpt": r["body_excerpt"],
                "created_at": (
                    r["created_at"].isoformat() if r.get("created_at") else None
                ),
            }
        )
    return out


def kb_note_get(note_id: int, max_body_chars: int = 12000) -> dict[str, Any] | None:
    tenant_id, user_id = _require_user_uuid()
    max_body_chars = max(500, min(int(max_body_chars or 12000), 100_000))
    with pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, body, created_at, updated_at, user_id AS owner_user_id
                FROM user_kb_notes
                WHERE id = %s AND tenant_id = %s
                  AND (
                    user_id = %s
                    OR id IN (
                      SELECT note_id FROM user_kb_note_shares
                      WHERE grantee_user_id = %s
                    )
                  )
                """,
                (note_id, tenant_id, user_id, user_id),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    body = str(row["body"] or "")
    if len(body) > max_body_chars:
        body = body[:max_body_chars] + "\n… (truncated)"
    owner_uid = row.get("owner_user_id")
    return {
        "id": row["id"],
        "title": row["title"],
        "body": body,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
        "is_owner": owner_uid == user_id,
        "owner_user_id": str(owner_uid) if owner_uid is not None else None,
    }


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


def rag_document_and_chunks_insert(
    tenant_id: int,
    user_id: uuid.UUID,
    domain: str,
    title: str,
    source_uri: str | None,
    content_sha256: str,
    chunks: list[tuple[int, str, list[float]]],
) -> tuple[int, int]:
    """
    Insert one ``rag_documents`` row and its chunks (each with embedding).
    Returns ``(document_id, chunk_count)``. Caller must validate embedding dims.
    """
    if not chunks:
        raise ValueError("chunks must be non-empty")
    domain = (domain or "").strip()
    title = (title or "").strip()
    uri = (source_uri or "").strip() or None
    sha = (content_sha256 or "").strip() or None
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_documents
                  (tenant_id, user_id, domain, title, source_uri, content_sha256)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (tenant_id, user_id, domain, title, uri, sha),
            )
            doc_id = int(cur.fetchone()[0])
            for idx, content, emb in chunks:
                cur.execute(
                    """
                    INSERT INTO rag_chunks (document_id, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    """,
                    (doc_id, int(idx), content, _vector_literal(emb)),
                )
        conn.commit()
    return doc_id, len(chunks)


def rag_vector_search(
    tenant_id: int,
    user_id: uuid.UUID,
    query_embedding: list[float],
    domain: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Cosine distance (pgvector ``<=>``); lower is more similar."""
    limit = max(1, min(int(limit), 50))
    dom = (domain or "").strip()
    qv = _vector_literal(query_embedding)
    with pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                  c.id AS chunk_id,
                  c.chunk_index,
                  left(c.content, 8000) AS content,
                  d.id AS document_id,
                  d.title,
                  d.domain,
                  (c.embedding <=> %s::vector) AS distance
                FROM rag_chunks c
                JOIN rag_documents d ON d.id = c.document_id
                WHERE d.tenant_id = %s
                  AND d.user_id = %s
                  AND (%s = '' OR d.domain = %s)
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
                """,
                (qv, tenant_id, user_id, dom, dom, qv, limit),
            )
            rows = cur.fetchall()
        conn.commit()
    out: list[dict[str, Any]] = []
    for r in rows:
        dist = r.get("distance")
        out.append(
            {
                "chunk_id": r["chunk_id"],
                "chunk_index": r["chunk_index"],
                "content": r["content"],
                "document_id": r["document_id"],
                "title": r["title"],
                "domain": r["domain"],
                "distance": float(dist) if dist is not None else None,
            }
        )
    return out


def user_persona_get(user_id: uuid.UUID) -> dict[str, Any] | None:
    with pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT instructions, inject_into_agent, updated_at
                FROM user_agent_persona
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    return {
        "instructions": row["instructions"] or "",
        "inject_into_agent": bool(row["inject_into_agent"]),
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def user_persona_upsert(
    tenant_id: int,
    user_id: uuid.UUID,
    *,
    instructions: str,
    inject_into_agent: bool,
) -> None:
    text = (instructions or "").strip()
    if len(text) > 100_000:
        raise ValueError("instructions too long (max 100000 characters)")
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_agent_persona (user_id, tenant_id, instructions, inject_into_agent)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                  instructions = EXCLUDED.instructions,
                  inject_into_agent = EXCLUDED.inject_into_agent,
                  updated_at = now()
                """,
                (user_id, tenant_id, text, inject_into_agent),
            )
        conn.commit()


DEFAULT_AGENT_PROFILE: dict[str, Any] = {
    "display_name": "",
    "preferred_output_language": "",
    "locale": "",
    "timezone": "",
    "home_location": "",
    "work_location": "",
    "travel_mode": "",
    "travel_preferences": {},
    "tone": "",
    "verbosity": "",
    "language_level": "",
    "interests": [],
    "hobbies": [],
    "job_title": "",
    "organization": "",
    "industry": "",
    "experience_level": "",
    "primary_tools": [],
    "proactive_mode": False,
    "interaction_style": "",
    "inject_structured_profile": True,
    "inject_dynamic_traits": False,
    "dynamic_traits": {},
    "profile_version": 0,
    "profile_hash": "",
    "injection_preferences": {},
    "usage_patterns": {},
}

# Fields that define profile content for profile_hash (cache / diff).
_PROFILE_HASH_FIELDS: tuple[str, ...] = (
    "display_name",
    "preferred_output_language",
    "locale",
    "timezone",
    "home_location",
    "work_location",
    "travel_mode",
    "travel_preferences",
    "tone",
    "verbosity",
    "language_level",
    "interests",
    "hobbies",
    "job_title",
    "organization",
    "industry",
    "experience_level",
    "primary_tools",
    "proactive_mode",
    "interaction_style",
    "inject_structured_profile",
    "inject_dynamic_traits",
    "dynamic_traits",
    "injection_preferences",
    "usage_patterns",
)


def _compute_profile_hash(d: dict[str, Any]) -> str:
    payload = {k: d[k] for k in _PROFILE_HASH_FIELDS}
    blob = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _norm_json_array(val: Any) -> list[Any]:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val.strip():
        try:
            p = json.loads(val)
            return p if isinstance(p, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _norm_json_object(val: Any) -> dict[str, Any]:
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val.strip():
        try:
            p = json.loads(val)
            return p if isinstance(p, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _norm_weighted_tags(val: Any) -> list[dict[str, Any]]:
    """Interests/hobbies: strings or ``[{ \"name\": \"…\", \"weight\": 0.0–1.0 }]``."""
    out: list[dict[str, Any]] = []
    items: list[Any]
    if isinstance(val, list):
        items = val
    else:
        items = _norm_json_array(val)
    for item in items:
        if isinstance(item, str) and item.strip():
            out.append({"name": item.strip(), "weight": 1.0})
        elif isinstance(item, dict):
            n = str(item.get("name") or "").strip()
            if not n:
                continue
            try:
                w = float(item.get("weight", 1.0))
            except (TypeError, ValueError):
                w = 1.0
            w = max(0.0, min(1.0, w))
            out.append({"name": n, "weight": w})
    return out[:200]


def _row_to_agent_profile(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "display_name": row.get("display_name") or "",
        "preferred_output_language": row.get("preferred_output_language") or "",
        "locale": row.get("locale") or "",
        "timezone": row.get("timezone") or "",
        "home_location": row.get("home_location") or "",
        "work_location": row.get("work_location") or "",
        "travel_mode": row.get("travel_mode") or "",
        "travel_preferences": _norm_json_object(row.get("travel_preferences")),
        "tone": row.get("tone") or "",
        "verbosity": row.get("verbosity") or "",
        "language_level": row.get("language_level") or "",
        "interests": _norm_weighted_tags(row.get("interests")),
        "hobbies": _norm_weighted_tags(row.get("hobbies")),
        "job_title": row.get("job_title") or "",
        "organization": row.get("organization") or "",
        "industry": row.get("industry") or "",
        "experience_level": row.get("experience_level") or "",
        "primary_tools": _norm_json_array(row.get("primary_tools")),
        "proactive_mode": bool(row.get("proactive_mode")),
        "interaction_style": row.get("interaction_style") or "",
        "inject_structured_profile": bool(row.get("inject_structured_profile", True)),
        "inject_dynamic_traits": bool(row.get("inject_dynamic_traits")),
        "dynamic_traits": _norm_json_object(row.get("dynamic_traits")),
        "profile_version": int(row.get("profile_version") or 0),
        "profile_hash": str(row.get("profile_hash") or ""),
        "injection_preferences": _norm_json_object(row.get("injection_preferences")),
        "usage_patterns": _norm_json_object(row.get("usage_patterns")),
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def user_agent_profile_get(user_id: uuid.UUID) -> dict[str, Any] | None:
    with pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                  display_name, preferred_output_language, locale, timezone,
                  home_location, work_location, travel_mode, travel_preferences,
                  tone, verbosity, language_level,
                  interests, hobbies,
                  job_title, organization, industry, experience_level, primary_tools,
                  proactive_mode, interaction_style,
                  inject_structured_profile, inject_dynamic_traits, dynamic_traits,
                  profile_version, profile_hash, injection_preferences, usage_patterns,
                  updated_at
                FROM user_agent_profile
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    return _row_to_agent_profile(row)


def user_agent_profile_upsert(
    tenant_id: int,
    user_id: uuid.UUID,
    data: dict[str, Any],
) -> None:
    """Replace structured profile for user (complete row). Bumps profile_version; sets profile_hash."""
    d = {**DEFAULT_AGENT_PROFILE, **data}
    d.pop("profile_version", None)
    d.pop("profile_hash", None)
    d["travel_preferences"] = _norm_json_object(d.get("travel_preferences"))
    d["interests"] = _norm_weighted_tags(d.get("interests"))
    d["hobbies"] = _norm_weighted_tags(d.get("hobbies"))
    d["primary_tools"] = _norm_json_array(d.get("primary_tools"))
    d["dynamic_traits"] = _norm_json_object(d.get("dynamic_traits"))
    d["injection_preferences"] = _norm_json_object(d.get("injection_preferences"))
    d["usage_patterns"] = _norm_json_object(d.get("usage_patterns"))
    d["proactive_mode"] = bool(d.get("proactive_mode"))
    d["inject_structured_profile"] = bool(d.get("inject_structured_profile", True))
    d["inject_dynamic_traits"] = bool(d.get("inject_dynamic_traits"))
    for arr_name in ("interests", "hobbies", "primary_tools"):
        if len(d[arr_name]) > 200:
            raise ValueError(f"{arr_name}: at most 200 entries")
    if len(json.dumps(d["travel_preferences"])) > 16_000:
        raise ValueError("travel_preferences JSON too large")
    if len(json.dumps(d["dynamic_traits"])) > 16_000:
        raise ValueError("dynamic_traits JSON too large")
    if len(json.dumps(d["injection_preferences"])) > 16_000:
        raise ValueError("injection_preferences JSON too large")
    if len(json.dumps(d["usage_patterns"])) > 16_000:
        raise ValueError("usage_patterns JSON too large")
    for k in (
        "display_name",
        "preferred_output_language",
        "locale",
        "timezone",
        "home_location",
        "work_location",
        "travel_mode",
        "tone",
        "verbosity",
        "language_level",
        "job_title",
        "organization",
        "industry",
        "experience_level",
        "interaction_style",
    ):
        s = str(d.get(k) or "")
        if len(s) > 10_000:
            raise ValueError(f"{k} too long (max 10000 characters)")
    phash = _compute_profile_hash(d)
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT profile_version FROM user_agent_profile WHERE user_id = %s",
                (user_id,),
            )
            prev = cur.fetchone()
            old_v = int(prev[0]) if prev else 0
            new_v = old_v + 1
            cur.execute(
                """
                INSERT INTO user_agent_profile (
                  user_id, tenant_id,
                  display_name, preferred_output_language, locale, timezone,
                  home_location, work_location, travel_mode, travel_preferences,
                  tone, verbosity, language_level,
                  interests, hobbies,
                  job_title, organization, industry, experience_level, primary_tools,
                  proactive_mode, interaction_style,
                  inject_structured_profile, inject_dynamic_traits, dynamic_traits,
                  profile_version, profile_hash, injection_preferences, usage_patterns
                )
                VALUES (
                  %s, %s,
                  %s, %s, %s, %s,
                  %s, %s, %s, %s,
                  %s, %s, %s,
                  %s, %s,
                  %s, %s, %s, %s, %s,
                  %s, %s,
                  %s, %s, %s,
                  %s, %s, %s, %s
                )
                ON CONFLICT (user_id) DO UPDATE SET
                  tenant_id = EXCLUDED.tenant_id,
                  display_name = EXCLUDED.display_name,
                  preferred_output_language = EXCLUDED.preferred_output_language,
                  locale = EXCLUDED.locale,
                  timezone = EXCLUDED.timezone,
                  home_location = EXCLUDED.home_location,
                  work_location = EXCLUDED.work_location,
                  travel_mode = EXCLUDED.travel_mode,
                  travel_preferences = EXCLUDED.travel_preferences,
                  tone = EXCLUDED.tone,
                  verbosity = EXCLUDED.verbosity,
                  language_level = EXCLUDED.language_level,
                  interests = EXCLUDED.interests,
                  hobbies = EXCLUDED.hobbies,
                  job_title = EXCLUDED.job_title,
                  organization = EXCLUDED.organization,
                  industry = EXCLUDED.industry,
                  experience_level = EXCLUDED.experience_level,
                  primary_tools = EXCLUDED.primary_tools,
                  proactive_mode = EXCLUDED.proactive_mode,
                  interaction_style = EXCLUDED.interaction_style,
                  inject_structured_profile = EXCLUDED.inject_structured_profile,
                  inject_dynamic_traits = EXCLUDED.inject_dynamic_traits,
                  dynamic_traits = EXCLUDED.dynamic_traits,
                  profile_version = EXCLUDED.profile_version,
                  profile_hash = EXCLUDED.profile_hash,
                  injection_preferences = EXCLUDED.injection_preferences,
                  usage_patterns = EXCLUDED.usage_patterns,
                  updated_at = now()
                """,
                (
                    user_id,
                    tenant_id,
                    d["display_name"],
                    d["preferred_output_language"],
                    d["locale"],
                    d["timezone"],
                    d["home_location"],
                    d["work_location"],
                    d["travel_mode"],
                    Json(d["travel_preferences"]),
                    d["tone"],
                    d["verbosity"],
                    d["language_level"],
                    Json(d["interests"]),
                    Json(d["hobbies"]),
                    d["job_title"],
                    d["organization"],
                    d["industry"],
                    d["experience_level"],
                    Json(d["primary_tools"]),
                    d["proactive_mode"],
                    d["interaction_style"],
                    d["inject_structured_profile"],
                    d["inject_dynamic_traits"],
                    Json(d["dynamic_traits"]),
                    new_v,
                    phash,
                    Json(d["injection_preferences"]),
                    Json(d["usage_patterns"]),
                ),
            )
        conn.commit()


def user_resolve_in_tenant(
    tenant_id: int,
    *,
    email: str | None = None,
    external_sub: str | None = None,
) -> uuid.UUID | None:
    em = (email or "").strip()
    sub = (external_sub or "").strip()
    if not em and not sub:
        return None
    with pool().connection() as conn:
        with conn.cursor() as cur:
            if em:
                cur.execute(
                    """
                    SELECT id FROM users
                    WHERE tenant_id = %s AND email IS NOT NULL
                      AND lower(trim(email)) = lower(trim(%s))
                    """,
                    (tenant_id, em),
                )
            else:
                cur.execute(
                    "SELECT id FROM users WHERE tenant_id = %s AND external_sub = %s",
                    (tenant_id, sub),
                )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    uid = row[0]
    return uid if isinstance(uid, uuid.UUID) else uuid.UUID(str(uid))


def kb_note_is_owner(note_id: int, user_id: uuid.UUID, tenant_id: int) -> bool:
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM user_kb_notes
                WHERE id = %s AND user_id = %s AND tenant_id = %s
                """,
                (note_id, user_id, tenant_id),
            )
            row = cur.fetchone()
        conn.commit()
    return row is not None


def kb_note_share_create(
    note_id: int,
    owner_user_id: uuid.UUID,
    tenant_id: int,
    grantee_user_id: uuid.UUID,
) -> int:
    if grantee_user_id == owner_user_id:
        raise ValueError("cannot share a note with yourself")
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, tenant_id FROM user_kb_notes WHERE id = %s",
                (note_id,),
            )
            nrow = cur.fetchone()
            if not nrow:
                raise ValueError("note not found")
            nu, nt = nrow[0], int(nrow[1])
            ou = nu if isinstance(nu, uuid.UUID) else uuid.UUID(str(nu))
            if ou != owner_user_id or nt != tenant_id:
                raise ValueError("not the owner of this note")
            cur.execute(
                "SELECT tenant_id FROM users WHERE id = %s",
                (grantee_user_id,),
            )
            grow = cur.fetchone()
            if not grow or int(grow[0]) != tenant_id:
                raise ValueError("grantee not in the same tenant")
            cur.execute(
                """
                INSERT INTO user_kb_note_shares (note_id, grantee_user_id)
                VALUES (%s, %s)
                ON CONFLICT (note_id, grantee_user_id) DO NOTHING
                RETURNING id
                """,
                (note_id, grantee_user_id),
            )
            ins = cur.fetchone()
            if not ins:
                raise ValueError("this user already has access")
            sid = int(ins[0])
        conn.commit()
    return sid


def kb_note_share_list(
    note_id: int, owner_user_id: uuid.UUID, tenant_id: int
) -> list[dict[str, Any]]:
    with pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT s.id, s.grantee_user_id, s.created_at, u.email, u.external_sub
                FROM user_kb_note_shares s
                JOIN user_kb_notes n ON n.id = s.note_id
                JOIN users u ON u.id = s.grantee_user_id
                WHERE s.note_id = %s AND n.user_id = %s AND n.tenant_id = %s
                ORDER BY s.created_at DESC
                """,
                (note_id, owner_user_id, tenant_id),
            )
            rows = cur.fetchall()
        conn.commit()
    out: list[dict[str, Any]] = []
    for r in rows:
        gid = r["grantee_user_id"]
        out.append(
            {
                "share_id": int(r["id"]),
                "grantee_user_id": str(gid),
                "grantee_email": r.get("email"),
                "grantee_external_sub": r.get("external_sub"),
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            }
        )
    return out


def kb_note_share_delete(share_id: int, owner_user_id: uuid.UUID, tenant_id: int) -> bool:
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM user_kb_note_shares s
                USING user_kb_notes n
                WHERE s.id = %s AND s.note_id = n.id
                  AND n.user_id = %s AND n.tenant_id = %s
                RETURNING s.id
                """,
                (share_id, owner_user_id, tenant_id),
            )
            row = cur.fetchone()
        conn.commit()
    return row is not None