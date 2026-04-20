"""CRUD for ``scheduler_jobs`` (tenant-scoped; policy in tool/API handlers)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Json

from apps.backend.infrastructure.db import db


def _uuid(v: Any) -> uuid.UUID | None:
    if v is None:
        return None
    if isinstance(v, uuid.UUID):
        return v
    try:
        return uuid.UUID(str(v).strip())
    except (ValueError, TypeError):
        return None


def user_belongs_to_tenant(user_id: uuid.UUID, tenant_id: int) -> bool:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM users WHERE id = %s AND tenant_id = %s",
                (user_id, tenant_id),
            )
            row = cur.fetchone()
        conn.commit()
    return row is not None


def insert_job(
    *,
    tenant_id: int,
    created_by_user_id: uuid.UUID,
    execution_user_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
    execution_target: str,
    title: str | None,
    instructions: str,
    interval_minutes: int,
    enabled: bool = True,
    ide_workflow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    wf = ide_workflow if ide_workflow is not None else {}
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO scheduler_jobs (
                  tenant_id, created_by_user_id, execution_user_id, workspace_id,
                  execution_target, title, instructions, interval_minutes, enabled,
                  ide_workflow, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                RETURNING id, tenant_id, created_by_user_id, execution_user_id, workspace_id,
                          execution_target, title, instructions, interval_minutes, enabled,
                          ide_workflow, last_run_at, created_at, updated_at
                """,
                (
                    tenant_id,
                    created_by_user_id,
                    execution_user_id,
                    workspace_id,
                    execution_target,
                    title,
                    instructions,
                    interval_minutes,
                    enabled,
                    Json(wf),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else {}


def list_jobs_for_user(
    *,
    tenant_id: int,
    current_user_id: uuid.UUID,
    is_admin: bool,
    workspace_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    lim = max(1, min(200, limit))
    params: list[Any] = [tenant_id]
    ws_filter = ""
    if workspace_id is not None:
        ws_filter = " AND j.workspace_id = %s"
        params.append(workspace_id)
    role_filter = ""
    if not is_admin:
        role_filter = " AND (j.created_by_user_id = %s OR j.execution_user_id = %s)"
        params.extend([current_user_id, current_user_id])
    params.append(lim)
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT j.id, j.tenant_id, j.created_by_user_id, j.execution_user_id, j.workspace_id,
                       j.execution_target, j.title, j.instructions, j.interval_minutes, j.enabled,
                       j.ide_workflow, j.last_run_at, j.created_at, j.updated_at
                FROM scheduler_jobs j
                WHERE j.tenant_id = %s
                  AND j.deleted_at IS NULL
                {ws_filter}
                {role_filter}
                ORDER BY j.created_at DESC
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()
        conn.commit()
    return [dict(r) for r in rows]


def list_jobs_for_tenant(
    *,
    tenant_id: int,
    workspace_id: uuid.UUID | None,
    include_global: bool,
    execution_target: str | None,
    enabled: bool | None,
    include_archived: bool = False,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Admin listing: tenant-wide jobs with optional workspace scoping.

    - workspace_id=None: list global-only when include_global=True, else all jobs (legacy)
    - workspace_id!=None:
        - include_global=True: workspace-bound + global (workspace_id IS NULL)
        - include_global=False: only workspace-bound
    """
    lim = max(1, min(500, limit))
    params: list[Any] = [tenant_id]
    where = "WHERE j.tenant_id = %s"
    if not include_archived:
        where += " AND j.deleted_at IS NULL"

    if workspace_id is not None:
        if include_global:
            where += " AND (j.workspace_id = %s OR j.workspace_id IS NULL)"
        else:
            where += " AND j.workspace_id = %s"
        params.append(workspace_id)
    else:
        if include_global:
            where += " AND j.workspace_id IS NULL"

    if execution_target is not None and str(execution_target).strip():
        where += " AND j.execution_target = %s"
        params.append(str(execution_target).strip().lower())

    if enabled is not None:
        where += " AND j.enabled = %s"
        params.append(bool(enabled))

    params.append(lim)
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT j.id, j.tenant_id, j.created_by_user_id, j.execution_user_id, j.workspace_id,
                       j.execution_target, j.title, j.instructions, j.interval_minutes, j.enabled,
                       j.ide_workflow, j.last_run_at, j.deleted_at, j.created_at, j.updated_at
                FROM scheduler_jobs j
                {where}
                ORDER BY j.created_at DESC
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()
        conn.commit()
    return [dict(r) for r in rows]


def get_job(job_id: uuid.UUID, tenant_id: int) -> dict[str, Any] | None:
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, tenant_id, created_by_user_id, execution_user_id, workspace_id,
                       execution_target, title, instructions, interval_minutes, enabled,
                       ide_workflow, last_run_at, deleted_at, created_at, updated_at
                FROM scheduler_jobs
                WHERE id = %s AND tenant_id = %s
                """,
                (job_id, tenant_id),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else None


def set_enabled(
    *,
    job_id: uuid.UUID,
    tenant_id: int,
    enabled: bool,
    actor_user_id: uuid.UUID,
    actor_is_admin: bool,
) -> dict[str, Any] | None:
    job = get_job(job_id, tenant_id)
    if not job:
        return None
    if not actor_is_admin:
        if _uuid(job.get("created_by_user_id")) != actor_user_id:
            return None
    now = datetime.now(UTC)
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE scheduler_jobs
                SET enabled = %s, updated_at = %s
                WHERE id = %s AND tenant_id = %s
                RETURNING id, tenant_id, created_by_user_id, execution_user_id, workspace_id,
                          execution_target, title, instructions, interval_minutes, enabled,
                          ide_workflow, last_run_at, created_at, updated_at
                """,
                (enabled, now, job_id, tenant_id),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else None


def update_job(
    *,
    job_id: uuid.UUID,
    tenant_id: int,
    actor_user_id: uuid.UUID,
    actor_is_admin: bool,
    title: str | None,
    instructions: str | None,
    interval_minutes: int | None,
    ide_workflow: dict[str, Any] | None,
) -> dict[str, Any] | None:
    job = get_job(job_id, tenant_id)
    if not job:
        return None
    if not actor_is_admin:
        if _uuid(job.get("created_by_user_id")) != actor_user_id:
            return None
    now = datetime.now(UTC)
    # None means "leave unchanged"
    new_title = job.get("title") if title is None else title
    new_instr = job.get("instructions") if instructions is None else instructions
    new_interval = job.get("interval_minutes") if interval_minutes is None else interval_minutes
    new_wf = job.get("ide_workflow") if ide_workflow is None else ide_workflow
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE scheduler_jobs
                SET title = %s,
                    instructions = %s,
                    interval_minutes = %s,
                    ide_workflow = %s,
                    updated_at = %s
                WHERE id = %s AND tenant_id = %s
                RETURNING id, tenant_id, created_by_user_id, execution_user_id, workspace_id,
                          execution_target, title, instructions, interval_minutes, enabled,
                          ide_workflow, last_run_at, deleted_at, created_at, updated_at
                """,
                (
                    new_title,
                    new_instr,
                    int(new_interval),
                    Json(new_wf if isinstance(new_wf, dict) else {}),
                    now,
                    job_id,
                    tenant_id,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else None


def archive_job(*, job_id: uuid.UUID, tenant_id: int, actor_user_id: uuid.UUID, actor_is_admin: bool) -> bool:
    job = get_job(job_id, tenant_id)
    if not job:
        return False
    if not actor_is_admin:
        if _uuid(job.get("created_by_user_id")) != actor_user_id:
            return False
    now = datetime.now(UTC)
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE scheduler_jobs
                SET deleted_at = %s, enabled = false, updated_at = %s
                WHERE id = %s AND tenant_id = %s
                """,
                (now, now, job_id, tenant_id),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0


def unarchive_job(*, job_id: uuid.UUID, tenant_id: int, actor_user_id: uuid.UUID, actor_is_admin: bool) -> bool:
    job = get_job(job_id, tenant_id)
    if not job:
        return False
    if not actor_is_admin:
        if _uuid(job.get("created_by_user_id")) != actor_user_id:
            return False
    now = datetime.now(UTC)
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE scheduler_jobs
                SET deleted_at = NULL, updated_at = %s
                WHERE id = %s AND tenant_id = %s
                """,
                (now, job_id, tenant_id),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0


def hard_delete_job(*, job_id: uuid.UUID, tenant_id: int, actor_user_id: uuid.UUID, actor_is_admin: bool) -> bool:
    job = get_job(job_id, tenant_id)
    if not job:
        return False
    if not actor_is_admin:
        if _uuid(job.get("created_by_user_id")) != actor_user_id:
            return False
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM scheduler_jobs WHERE id = %s AND tenant_id = %s",
                (job_id, tenant_id),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0


def fetch_due_jobs_server_periodic(*, limit: int = 10) -> list[dict[str, Any]]:
    """Jobs with execution_target=server_periodic whose interval has elapsed since last run (or creation)."""
    lim = max(1, min(50, limit))
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, tenant_id, created_by_user_id, execution_user_id, workspace_id,
                       execution_target, title, instructions, interval_minutes, enabled,
                       ide_workflow, last_run_at, created_at, updated_at
                FROM scheduler_jobs
                WHERE enabled = true
                  AND execution_target = 'server_periodic'
                  AND COALESCE(last_run_at, created_at)
                      + (interval '1 minute' * interval_minutes) <= now()
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (lim,),
            )
            rows = cur.fetchall()
        conn.commit()
    return [dict(r) for r in rows]


def fetch_due_jobs_ide_agent_for_pidea(*, limit: int = 5) -> list[dict[str, Any]]:
    """
    Due ``ide_agent`` jobs whose ``execution_user_id`` is an **admin** (PIDEA may only drive IDE for admins).

    Used by the background worker to run Playwright against the IDE composer.
    """
    lim = max(1, min(20, limit))
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT j.id, j.tenant_id, j.created_by_user_id, j.execution_user_id, j.workspace_id,
                       j.execution_target, j.title, j.instructions, j.interval_minutes, j.enabled,
                       j.ide_workflow, j.last_run_at, j.created_at, j.updated_at
                FROM scheduler_jobs j
                INNER JOIN users u ON u.id = j.execution_user_id
                WHERE j.enabled = true
                  AND j.execution_target = 'ide_agent'
                  AND lower(trim(u.role)) = 'admin'
                  AND COALESCE(j.last_run_at, j.created_at)
                      + (interval '1 minute' * j.interval_minutes) <= now()
                ORDER BY j.created_at ASC
                LIMIT %s
                """,
                (lim,),
            )
            rows = cur.fetchall()
        conn.commit()
    return [dict(r) for r in rows]


def fetch_due_jobs_ide_for_user(
    *, tenant_id: int, execution_user_id: uuid.UUID, limit: int = 20
) -> list[dict[str, Any]]:
    """IDE client: due jobs targeting this execution user."""
    lim = max(1, min(100, limit))
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, tenant_id, created_by_user_id, execution_user_id, workspace_id,
                       execution_target, title, instructions, interval_minutes, enabled,
                       ide_workflow, last_run_at, created_at, updated_at
                FROM scheduler_jobs
                WHERE tenant_id = %s
                  AND execution_user_id = %s
                  AND enabled = true
                  AND execution_target = 'ide_agent'
                  AND COALESCE(last_run_at, created_at)
                      + (interval '1 minute' * interval_minutes) <= now()
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (tenant_id, execution_user_id, lim),
            )
            rows = cur.fetchall()
        conn.commit()
    return [dict(r) for r in rows]


def mark_job_last_run(*, job_id: uuid.UUID, tenant_id: int) -> bool:
    now = datetime.now(UTC)
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE scheduler_jobs
                SET last_run_at = %s, updated_at = %s
                WHERE id = %s AND tenant_id = %s
                """,
                (now, now, job_id, tenant_id),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0


def ack_job_run_for_user(
    *,
    job_id: uuid.UUID,
    tenant_id: int,
    actor_user_id: uuid.UUID,
    actor_is_admin: bool,
) -> dict[str, Any] | None:
    """Set last_run_at after IDE executed the job (creator or execution user or admin)."""
    job = get_job(job_id, tenant_id)
    if not job:
        return None
    exec_u = _uuid(job.get("execution_user_id"))
    if not actor_is_admin and actor_user_id != exec_u:
        return None
    now = datetime.now(UTC)
    with db.pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE scheduler_jobs
                SET last_run_at = %s, updated_at = %s
                WHERE id = %s AND tenant_id = %s
                RETURNING id, tenant_id, created_by_user_id, execution_user_id, workspace_id,
                          execution_target, title, instructions, interval_minutes, enabled,
                          ide_workflow, last_run_at, created_at, updated_at
                """,
                (now, now, job_id, tenant_id),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else None


def row_to_public(row: dict[str, Any]) -> dict[str, Any]:
    """JSON-serializable dict for tool responses."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, uuid.UUID):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
