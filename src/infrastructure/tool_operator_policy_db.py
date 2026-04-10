"""Persist operator tool policy (admin UI); manifest defaults live in tool modules."""

from __future__ import annotations

from typing import Any

from src.domain.plugin_system.tool_manifest_dimensions import normalize_execution_context
from src.infrastructure.db import db


def list_policies() -> list[dict[str, Any]]:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT package_id, tool_name, enabled, default_on, user_configurable,
                       execution_context, updated_at
                FROM operator_tool_policies
                ORDER BY package_id, tool_name
                """
            )
            rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        ex = r[5]
        if isinstance(ex, str) and ex.strip():
            ex = normalize_execution_context(ex.strip())
        else:
            ex = None
        out.append(
            {
                "package_id": r[0],
                "tool_name": r[1],
                "enabled": bool(r[2]),
                "default_on": r[3],
                "user_configurable": r[4],
                "execution_context": ex,
                "updated_at": r[6].isoformat() if r[6] else None,
            }
        )
    return out


def _policy_key(package_id: str, tool_name: str) -> tuple[str, str]:
    return (package_id.strip(), (tool_name or "*").strip() or "*")


def policies_map() -> dict[tuple[str, str], dict[str, Any]]:
    """(package_id, tool_name) -> row dict with enabled, default_on, user_configurable, execution_context."""
    m: dict[tuple[str, str], dict[str, Any]] = {}
    for row in list_policies():
        k = _policy_key(row["package_id"], row["tool_name"])
        m[k] = row
    return m


def upsert_policy(
    package_id: str,
    tool_name: str,
    *,
    enabled: bool,
    default_on: bool | None,
    user_configurable: bool | None,
    execution_context: str | None = None,
) -> None:
    pkg = package_id.strip()
    tn = (tool_name or "*").strip() or "*"
    ex = execution_context
    if isinstance(ex, str) and ex.strip():
        ex = normalize_execution_context(ex.strip())
    else:
        ex = None
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO operator_tool_policies
                    (package_id, tool_name, enabled, default_on, user_configurable,
                     execution_context, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (package_id, tool_name) DO UPDATE SET
                    enabled = EXCLUDED.enabled,
                    default_on = EXCLUDED.default_on,
                    user_configurable = EXCLUDED.user_configurable,
                    execution_context = EXCLUDED.execution_context,
                    updated_at = now()
                """,
                (pkg, tn, enabled, default_on, user_configurable, ex),
            )
        conn.commit()


def replace_all_policies(rows: list[dict[str, Any]]) -> None:
    """Replace table contents with validated rows (admin save-all)."""
    cleaned: list[tuple[str, str, bool, bool | None, bool | None, str | None]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        pid = str(r.get("package_id") or "").strip()
        if not pid:
            continue
        tn = str(r.get("tool_name") or "*").strip() or "*"
        en = r.get("enabled")
        if not isinstance(en, bool):
            en = True
        d_on = r.get("default_on")
        if d_on is not None and not isinstance(d_on, bool):
            d_on = None
        uc = r.get("user_configurable")
        if uc is not None and not isinstance(uc, bool):
            uc = None
        ex = r.get("execution_context")
        if isinstance(ex, str) and ex.strip():
            ex = normalize_execution_context(ex.strip())
        else:
            ex = None
        cleaned.append((pid, tn, en, d_on, uc, ex))
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM operator_tool_policies")
            for pid, tn, en, d_on, uc, ex in cleaned:
                cur.execute(
                    """
                    INSERT INTO operator_tool_policies
                        (package_id, tool_name, enabled, default_on, user_configurable,
                         execution_context, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, now())
                    """,
                    (pid, tn, en, d_on, uc, ex),
                )
        conn.commit()
