"""PostgreSQL pool and persistence helpers. Schema changes: Alembic (see entrypoint)."""

from __future__ import annotations

import hashlib
import logging
import secrets
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


def ensure_user_external(external_sub: str, tenant_id: int) -> tuple[int, int]:
    """
    Resolve or create ``users`` row. ``external_sub`` is a stable id from the client
    (e.g. OIDC sub or WebUI user id string). Returns ``(user_id, tenant_id)``.
    """
    sub = (external_sub or "").strip() or "default"
    tid = int(tenant_id) if tenant_id else 1
    if tid < 1:
        tid = 1
    with pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM tenants WHERE id = %s", (tid,))
            if cur.fetchone() is None:
                tid = 1
            cur.execute(
                "SELECT id FROM users WHERE tenant_id = %s AND external_sub = %s",
                (tid, sub),
            )
            row = cur.fetchone()
            if row:
                uid = int(row[0])
            else:
                cur.execute(
                    """
                    INSERT INTO users (tenant_id, external_sub)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (tid, sub),
                )
                uid = int(cur.fetchone()[0])
        conn.commit()
    return uid, tid


def user_external_sub(user_id: int) -> str | None:
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


def todo_create(title: str) -> int:
    tenant_id, user_id = get_identity()
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
    tenant_id, user_id = get_identity()
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
    tenant_id, user_id = get_identity()
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


def user_secret_upsert(user_id: int, service_key: str, plaintext: str) -> None:
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


def user_secret_get_plaintext(user_id: int, service_key: str) -> str | None:
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


def user_secret_delete(user_id: int, service_key: str) -> bool:
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


def user_secret_list_service_keys(user_id: int) -> list[str]:
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


def secret_upload_otp_create(user_id: int, ttl_seconds: int = 600) -> str:
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
            uid = int(row[0])
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
    tenant_id, user_id = get_identity()
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
    tenant_id, user_id = get_identity()
    q = (query or "").strip()
    if not q:
        return []
    limit = max(1, min(int(limit or 20), 50))
    pat = _ilike_contains(q)
    sql_full = """
                SELECT id, title, left(body, 500) AS body_excerpt, created_at
                FROM user_kb_notes
                WHERE tenant_id = %s AND user_id = %s
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
                WHERE tenant_id = %s AND user_id = %s
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
                    (tenant_id, user_id, pat, pat, q, limit),
                )
            except psycopg.Error:
                logger.debug(
                    "kb_note_search fts fallback for query %r", q[:80], exc_info=True
                )
                conn.rollback()
                cur.execute(
                    sql_ilike,
                    (tenant_id, user_id, pat, pat, limit),
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
    tenant_id, user_id = get_identity()
    max_body_chars = max(500, min(int(max_body_chars or 12000), 100_000))
    with pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, title, body, created_at, updated_at
                FROM user_kb_notes
                WHERE id = %s AND tenant_id = %s AND user_id = %s
                """,
                (note_id, tenant_id, user_id),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    body = str(row["body"] or "")
    if len(body) > max_body_chars:
        body = body[:max_body_chars] + "\n… (truncated)"
    return {
        "id": row["id"],
        "title": row["title"],
        "body": body,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


def rag_document_and_chunks_insert(
    tenant_id: int,
    user_id: int,
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
    user_id: int,
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