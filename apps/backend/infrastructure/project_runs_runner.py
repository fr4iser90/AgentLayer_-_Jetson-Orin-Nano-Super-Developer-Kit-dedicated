"""Background worker for ``project_runs`` (execution queue).

This is the *execution* side of decoupling:
- scheduler enqueues rows into ``project_runs``
- this worker performs the IDE/PIDEA pipeline and records status.
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any

from apps.backend.domain.identity import reset_identity, set_identity
from apps.backend.infrastructure import operator_settings, project_runs_store
from apps.backend.infrastructure.db import db
from apps.backend.infrastructure.scheduler_jobs_workflow import (
    compose_pidea_message,
    job_context_footer,
    run_optional_git_branch,
)
from apps.backend.integrations.pidea.content_library_prompts import (
    SCHEDULER_PIPELINE_ANALYZE_CREATE,
    SCHEDULER_PIPELINE_EXECUTE,
    SCHEDULER_PIPELINE_REVIEW,
    read_content_library_prompt,
)
from apps.backend.integrations.pidea.pidea_workflow_executor import run_pidea_workflow_by_id

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None

_POLL_SEC = 6.0
_MAX_BATCH = 5


def start_project_runs_worker() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(
        target=_worker_loop, daemon=True, name="project-runs-worker"
    )
    _thread.start()


def stop_project_runs_worker() -> None:
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=20)


def _tenant_id(row: dict[str, Any]) -> int:
    t = row.get("tenant_id")
    return int(t) if t is not None else 0


def _uid(row: dict[str, Any], key: str) -> uuid.UUID:
    v = row.get(key)
    if isinstance(v, uuid.UUID):
        return v
    return uuid.UUID(str(v))


def _run_ide_agent_pipeline(run_row: dict[str, Any], *, timeout_s: float) -> tuple[bool, str | None]:
    tenant_id = _tenant_id(run_row)
    run_id = _uid(run_row, "id")
    exec_uid = _uid(run_row, "execution_user_id")

    if db.user_role(exec_uid) != "admin":
        return False, "execution_user_id is not admin (PIDEA IDE driving requires admin)"

    if not operator_settings.pidea_effective_enabled():
        return False, "PIDEA is disabled"

    from apps.backend.integrations.pidea.playwright_env import playwright_import_ok

    if not playwright_import_ok():
        return False, "Playwright not installed"

    try:
        from apps.backend.integrations.pidea.ide_agent_message import run_ide_agent_message_sync
    except Exception as e:
        return False, f"cannot import PIDEA ide_agent_message: {e}"

    wf = run_row.get("ide_workflow") if isinstance(run_row.get("ide_workflow"), dict) else {}
    footer = job_context_footer(run_row)  # reuse footer format
    wf_name = str(wf.get("pidea_workflow_name") or "").strip()
    use_pipeline = bool(wf.get("use_pidea_scheduler_pipeline", True))

    id_tok = set_identity(tenant_id, exec_uid)
    try:
        if wf_name:
            ok_wf, wf_err = run_pidea_workflow_by_id(
                wf_name,
                row=run_row,
                wf=wf,
                job_id_str=str(run_id),
                timeout_s=timeout_s,
                run_ide_agent_message_sync=run_ide_agent_message_sync,
                compose_pidea_message=compose_pidea_message,
                job_context_footer=job_context_footer,
            )
            return (bool(ok_wf), wf_err if not ok_wf else None)

        if not use_pipeline:
            text = compose_pidea_message(run_row, wf).strip()
            result = run_ide_agent_message_sync(
                text,
                new_chat=bool(wf.get("new_chat", True)),
                reply_timeout_s=timeout_s,
            )
            if not isinstance(result, dict) or not result.get("ok"):
                return False, f"ide_agent_message failed: {result}"
            return True, None

        # Default pipeline: analyze/create → git → execute (+ optional review).
        instr = str(run_row.get("instructions") or "").strip()
        if not instr:
            return False, "missing instructions"

        for i, rel in enumerate(SCHEDULER_PIPELINE_ANALYZE_CREATE):
            body = read_content_library_prompt(rel)
            text = "\n".join([body, "", footer]).strip()
            result = run_ide_agent_message_sync(
                text,
                new_chat=(i == 0),
                reply_timeout_s=timeout_s,
            )
            if not isinstance(result, dict) or not result.get("ok"):
                return False, f"pipeline step failed ({rel}): {result}"

        ok_git, git_err = run_optional_git_branch(run_row, wf, job_id_str=str(run_id))
        if not ok_git:
            return False, f"git step failed: {git_err}"

        tail = [SCHEDULER_PIPELINE_EXECUTE]
        if bool(wf.get("scheduler_pipeline_include_review")):
            tail.append(SCHEDULER_PIPELINE_REVIEW)
        for rel in tail:
            body = read_content_library_prompt(rel)
            text = "\n".join([body, "", footer]).strip()
            result = run_ide_agent_message_sync(
                text,
                new_chat=True,
                reply_timeout_s=timeout_s,
            )
            if not isinstance(result, dict) or not result.get("ok"):
                return False, f"pipeline step failed ({rel}): {result}"

        return True, None
    finally:
        reset_identity(id_tok)


def _worker_loop() -> None:
    logger.info("project_runs worker thread started")
    while not _stop.is_set():
        if _stop.wait(timeout=_POLL_SEC):
            break
        try:
            worker_on, ide_on, timeout_s = operator_settings.scheduler_jobs_worker_settings()
            if not worker_on or not ide_on:
                continue

            rows = project_runs_store.fetch_queued_runs_ide_agent(limit=_MAX_BATCH)
            for row in rows:
                if _stop.is_set():
                    break
                tenant_id = _tenant_id(row)
                run_id = _uid(row, "id")
                if not project_runs_store.mark_running(run_id=run_id, tenant_id=tenant_id):
                    continue
                ok, err = _run_ide_agent_pipeline(row, timeout_s=timeout_s)
                project_runs_store.mark_done(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    status="succeeded" if ok else "failed",
                    error=err,
                )
        except Exception:
            logger.exception("project_runs worker iteration failed")
    logger.info("project_runs worker stopped")

