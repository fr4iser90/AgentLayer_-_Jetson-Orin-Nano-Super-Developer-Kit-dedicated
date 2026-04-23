"""
Background worker for persisted ``scheduler_jobs``.

- ``execution_target=server_periodic``: ``chat_completion`` (plain) as ``execution_user_id``.
- ``execution_target=ide_agent``: **PIDEA** — optional ``ide_workflow`` (``new_chat``, ``prompt_preamble``,
  optional git branch before composer); sends composed text to the IDE; ``execution_user_id`` must be **admin**.

Worker enable/disable, IDE/PIDEA branch, and reply timeout are read from ``operator_settings``
(Admin → Interfaces), not from environment variables.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from pathlib import Path
from typing import Any

from apps.backend.core.config import config
from apps.backend.domain.agent import chat_completion
from apps.backend.domain.identity import reset_identity, set_identity
from apps.backend.infrastructure import operator_settings
from apps.backend.infrastructure import scheduler_jobs_store
from apps.backend.infrastructure import project_runs_store
from apps.backend.infrastructure.db import db
from apps.backend.integrations.pidea.content_library_prompts import (
    SCHEDULER_PIPELINE_ANALYZE_CREATE,
    SCHEDULER_PIPELINE_EXECUTE,
    SCHEDULER_PIPELINE_REVIEW,
    read_content_library_prompt,
    resolved_phase_paths,
)
from apps.backend.infrastructure.scheduler_jobs_workflow import (
    compose_pidea_message,
    ide_workflow_from_row,
    job_context_footer,
    run_optional_git_branch,
)
from apps.backend.integrations.pidea.pidea_workflow_executor import (
    run_pidea_workflow_by_id,
)
from apps.backend.integrations.pidea.task_plan_bundle import bundle_task_plans_from_repo
from apps.backend.integrations.pidea.project_path_cdp import detect_project_path_from_ide_sync

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None

_POLL_SEC = 45.0
_MAX_BATCH = 5


def start_scheduler_jobs_worker() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(
        target=_worker_loop, daemon=True, name="scheduler-jobs-server-worker"
    )
    _thread.start()


def stop_scheduler_jobs_worker() -> None:
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


async def _run_server_job(row: dict[str, Any]) -> None:
    tenant_id = _tenant_id(row)
    user_id = _uid(row, "execution_user_id")
    job_id = _uid(row, "id")
    role = db.user_role(user_id)

    title = (str(row.get("title") or "").strip()) or None
    instr = str(row.get("instructions") or "").strip()
    if not instr:
        logger.warning("scheduler_jobs: empty instructions job_id=%s — skipping", job_id)
        scheduler_jobs_store.mark_job_last_run(job_id=job_id, tenant_id=tenant_id)
        return

    ws = row.get("workspace_id")
    ws_hint = ""
    if ws is not None:
        ws_hint = f"\nWorkspace scope (id): {ws}\n"

    sys_prompt = (
        "You are executing a persisted scheduled server job (scheduler_jobs, execution_target=server_periodic). "
        "Follow the instructions. Reply concisely.\n"
        f"{ws_hint}"
    )
    if title:
        sys_prompt += f"Title: {title}\n"
    sys_prompt += f"Instructions:\n{instr[:31000]}"

    body: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": "Run this scheduled task now."},
        ],
        "stream": False,
        # Allow tool-calling for server_periodic schedules (otherwise they can't do real work).
        "agent_plain_completion": False,
        # Heuristic: most server schedules are productivity automation (RSS, workspace updates, etc.).
        "TOOL_DOMAIN": "productivity",
        "model": str(getattr(config, "OLLAMA_DEFAULT_MODEL", "llama3.2") or "llama3.2"),
    }

    id_tok = set_identity(tenant_id, user_id)
    try:
        await chat_completion(
            body,
            bearer_user_role=role if role in ("user", "admin") else None,
        )
    except Exception:
        logger.exception(
            "scheduler_jobs: server job failed job_id=%s user=%s", job_id, user_id
        )
        return
    finally:
        reset_identity(id_tok)

    if scheduler_jobs_store.mark_job_last_run(job_id=job_id, tenant_id=tenant_id):
        logger.info("scheduler_jobs: finished server job job_id=%s user=%s", job_id, user_id)
    else:
        logger.warning("scheduler_jobs: could not mark last_run_at job_id=%s", job_id)


def _run_ide_agent_pidea_job(row: dict[str, Any], *, timeout_s: float) -> None:
    """Send job text to IDE via PIDEA; mark ``last_run_at`` on success."""
    tenant_id = _tenant_id(row)
    job_id = _uid(row, "id")
    exec_uid = _uid(row, "execution_user_id")

    wf = ide_workflow_from_row(row)
    paths = resolved_phase_paths(wf)
    wf_name = str(wf.get("pidea_workflow_name") or "").strip()
    use_pipeline = bool(wf.get("use_pidea_scheduler_pipeline"))
    instr_ok = bool(str(row.get("instructions") or "").strip())
    if use_pipeline and not instr_ok:
        logger.warning(
            "scheduler_jobs: use_pidea_scheduler_pipeline needs non-empty instructions job_id=%s",
            job_id,
        )
        scheduler_jobs_store.mark_job_last_run(job_id=job_id, tenant_id=tenant_id)
        return
    if not instr_ok and not paths and not wf_name and not use_pipeline:
        logger.warning(
            "scheduler_jobs: ide_agent needs instructions, ide_workflow phases, "
            "pidea_workflow_name, or use_pidea_scheduler_pipeline job_id=%s — skipping",
            job_id,
        )
        scheduler_jobs_store.mark_job_last_run(job_id=job_id, tenant_id=tenant_id)
        return

    if db.user_role(exec_uid) != "admin":
        logger.warning(
            "scheduler_jobs: ide_agent PIDEA skip — execution_user_id not admin job_id=%s",
            job_id,
        )
        return

    if not operator_settings.pidea_effective_enabled():
        logger.debug("scheduler_jobs: ide_agent PIDEA skip — PIDEA disabled job_id=%s", job_id)
        return

    from apps.backend.integrations.pidea.playwright_env import playwright_import_ok

    if not playwright_import_ok():
        logger.warning(
            "scheduler_jobs: ide_agent PIDEA skip — Playwright not installed job_id=%s",
            job_id,
        )
        return

    if not wf_name and not use_pipeline:
        ok_git, git_err = run_optional_git_branch(row, wf, job_id_str=str(job_id))
        if not ok_git:
            logger.warning(
                "scheduler_jobs: ide_agent git step failed job_id=%s — %s",
                job_id,
                git_err,
            )
            return

    try:
        from apps.backend.integrations.pidea.ide_agent_message import run_ide_agent_message_sync
    except Exception:
        logger.exception("scheduler_jobs: cannot import PIDEA ide_agent_message job_id=%s", job_id)
        return

    id_tok = set_identity(tenant_id, exec_uid)
    result: dict[str, Any] | None = None
    try:
        if wf_name:
            ok_wf, wf_err = run_pidea_workflow_by_id(
                wf_name,
                row=row,
                wf=wf,
                job_id_str=str(job_id),
                timeout_s=timeout_s,
                run_ide_agent_message_sync=run_ide_agent_message_sync,
                compose_pidea_message=compose_pidea_message,
                job_context_footer=job_context_footer,
            )
            if not ok_wf:
                logger.warning(
                    "scheduler_jobs: pidea JSON workflow failed job_id=%s workflow=%s — %s",
                    job_id,
                    wf_name,
                    wf_err,
                )
                return
            result = {"ok": True, "timed_out": False}
        elif use_pipeline:
            # Analyze + Create im selben Chat (Create ohne neuen Chat), dann Git-Branch, dann Execute (+ optional Review).
            wf_run: dict[str, Any] = dict(wf)
            if wf_run.get("use_cdp_project_path", True) and not (
                str(wf_run.get("git_repo_path") or "").strip()
                or str(wf_run.get("project_path") or "").strip()
            ):
                det = detect_project_path_from_ide_sync()
                if det:
                    wf_run["project_path"] = det
                    logger.info(
                        "scheduler_jobs: pipeline CDP project_path=%s job_id=%s",
                        det,
                        job_id,
                    )
            footer = job_context_footer(row)
            pre = (wf_run.get("prompt_preamble") or "").strip()
            if not (wf_run.get("git_repo_path") or wf_run.get("project_path")) or not (
                wf_run.get("git_branch_template") or ""
            ).strip():
                logger.warning(
                    "scheduler_jobs: pipeline job_id=%s — set git_branch_template and "
                    "git_repo_path or project_path (or rely on CDP workspace detection) "
                    "for branch / task-plan files",
                    job_id,
                )
            for i, rel in enumerate(SCHEDULER_PIPELINE_ANALYZE_CREATE):
                body = read_content_library_prompt(rel)
                parts: list[str] = []
                if pre and i == 0:
                    parts.append(pre)
                    parts.append("")
                parts.append(body)
                parts.append("")
                parts.append(footer)
                text = "\n".join(parts).strip()
                nc = i == 0
                logger.info(
                    "scheduler_jobs: pipeline analyze/create %s job_id=%s new_chat=%s",
                    rel,
                    job_id,
                    nc,
                )
                result = run_ide_agent_message_sync(
                    text,
                    new_chat=nc,
                    reply_timeout_s=timeout_s,
                )
                if not isinstance(result, dict) or not result.get("ok"):
                    logger.warning(
                        "scheduler_jobs: pipeline step failed job_id=%s file=%s result=%s",
                        job_id,
                        rel,
                        result,
                    )
                    return
            ok_git, git_err = run_optional_git_branch(row, wf_run, job_id_str=str(job_id))
            if not ok_git:
                logger.warning(
                    "scheduler_jobs: pipeline git failed job_id=%s — %s",
                    job_id,
                    git_err,
                )
                return
            tail_paths = [SCHEDULER_PIPELINE_EXECUTE]
            if bool(wf.get("scheduler_pipeline_include_review")):
                tail_paths.append(SCHEDULER_PIPELINE_REVIEW)
            for rel in tail_paths:
                body = read_content_library_prompt(rel)
                chunks: list[str] = [body, ""]
                if (
                    rel == SCHEDULER_PIPELINE_EXECUTE
                    and wf_run.get("attach_task_plans_to_execute", True)
                ):
                    repo_s = (
                        str(wf_run.get("git_repo_path") or "").strip()
                        or str(wf_run.get("project_path") or "").strip()
                    )
                    if repo_s:
                        try:
                            rpath = Path(repo_s).expanduser().resolve(strict=True)
                            plan = bundle_task_plans_from_repo(
                                rpath,
                                glob_pattern=str(wf_run.get("task_plan_glob") or "") or None,
                                max_files=int(wf_run.get("task_plan_max_files") or 30),
                                max_total_chars=int(wf_run.get("task_plan_max_chars") or 100_000),
                            )
                            if plan:
                                chunks.extend([plan, ""])
                            else:
                                chunks.extend(
                                    [
                                        "---\n"
                                        "[No task-plan .md files matched the glob — task-create may not have "
                                        "written under docs/agent/tasks/ yet, or adjust ide_workflow.task_plan_glob.]\n",
                                        "",
                                    ]
                                )
                        except OSError as e:
                            logger.warning(
                                "scheduler_jobs: cannot read task plans job_id=%s — %s",
                                job_id,
                                e,
                            )
                            chunks.extend(
                                [
                                    f"---\n[Could not read task plans from repo: {e}]\n",
                                    "",
                                ]
                            )
                    else:
                        chunks.extend(
                            [
                                "---\n"
                                "[No repo path and CDP did not yield a usable local path — set "
                                "ide_workflow.git_repo_path or project_path, or fix CDP/Docker so the IDE path "
                                "matches this host’s filesystem.]\n",
                                "",
                            ]
                        )
                chunks.append(footer)
                text = "\n".join(chunks).strip()
                logger.info(
                    "scheduler_jobs: pipeline execute/review %s job_id=%s new_chat=True",
                    rel,
                    job_id,
                )
                result = run_ide_agent_message_sync(
                    text,
                    new_chat=True,
                    reply_timeout_s=timeout_s,
                )
                if not isinstance(result, dict) or not result.get("ok"):
                    logger.warning(
                        "scheduler_jobs: pipeline step failed job_id=%s file=%s result=%s",
                        job_id,
                        rel,
                        result,
                    )
                    return
        elif paths:
            footer = job_context_footer(row)
            pre = (wf.get("prompt_preamble") or "").strip()
            new_chat_first = bool(wf.get("new_chat", True))
            for i, rel in enumerate(paths):
                try:
                    body = read_content_library_prompt(rel)
                except (OSError, ValueError) as e:
                    logger.warning(
                        "scheduler_jobs: cannot read PIDEA prompt %s job_id=%s — %s",
                        rel,
                        job_id,
                        e,
                    )
                    return
                parts: list[str] = []
                if pre and i == 0:
                    parts.append(pre)
                    parts.append("")
                parts.append(body)
                parts.append("")
                parts.append(footer)
                text = "\n".join(parts).strip()
                nc = new_chat_first if i == 0 else False
                logger.info(
                    "scheduler_jobs: ide_agent phase %d/%s file=%s new_chat=%s job_id=%s",
                    i + 1,
                    len(paths),
                    rel,
                    nc,
                    job_id,
                )
                result = run_ide_agent_message_sync(
                    text,
                    new_chat=nc,
                    reply_timeout_s=timeout_s,
                )
                if not isinstance(result, dict) or not result.get("ok"):
                    logger.warning(
                        "scheduler_jobs: ide_agent phase failed job_id=%s file=%s result=%s",
                        job_id,
                        rel,
                        result,
                    )
                    return
        else:
            text = compose_pidea_message(row, wf).strip()
            result = run_ide_agent_message_sync(
                text,
                new_chat=bool(wf.get("new_chat", True)),
                reply_timeout_s=timeout_s,
            )
    except Exception:
        logger.exception("scheduler_jobs: ide_agent PIDEA run failed job_id=%s", job_id)
        return
    finally:
        reset_identity(id_tok)

    if not isinstance(result, dict) or not result.get("ok"):
        logger.warning("scheduler_jobs: ide_agent PIDEA bad result job_id=%s result=%s", job_id, result)
        return

    if scheduler_jobs_store.mark_job_last_run(job_id=job_id, tenant_id=tenant_id):
        logger.info(
            "scheduler_jobs: ide_agent PIDEA done job_id=%s timed_out=%s phases=%s workflow=%s pipeline=%s",
            job_id,
            result.get("timed_out"),
            len(paths) if paths else 1,
            wf_name or "",
            use_pipeline,
        )
    else:
        logger.warning("scheduler_jobs: could not mark last_run_at job_id=%s", job_id)


def _worker_loop() -> None:
    logger.info("scheduler_jobs worker thread started (toggles: operator_settings / Admin → Interfaces)")
    while not _stop.is_set():
        if _stop.wait(timeout=_POLL_SEC):
            break
        try:
            worker_on, ide_pidea_on, timeout_s = operator_settings.scheduler_jobs_worker_settings()
            if not worker_on:
                continue
            jobs = scheduler_jobs_store.fetch_due_jobs_server_periodic(limit=_MAX_BATCH)
            for row in jobs:
                if _stop.is_set():
                    break
                try:
                    asyncio.run(_run_server_job(row))
                except Exception:
                    logger.exception("scheduler_jobs: server run failed")

            if ide_pidea_on:
                ide_rows = scheduler_jobs_store.fetch_due_jobs_ide_agent_for_pidea(limit=_MAX_BATCH)
                for row in ide_rows:
                    if _stop.is_set():
                        break
                    try:
                        # Decoupled: scheduler enqueues a one-shot run; execution worker processes it.
                        tenant_id = _tenant_id(row)
                        job_id = _uid(row, "id")
                        exec_uid = _uid(row, "execution_user_id")
                        created_by = _uid(row, "created_by_user_id")
                        instr = str(row.get("instructions") or "").strip()
                        wf = ide_workflow_from_row(row)
                        if not instr:
                            scheduler_jobs_store.mark_job_last_run(job_id=job_id, tenant_id=tenant_id)
                            continue
                        run = project_runs_store.insert_run(
                            tenant_id=tenant_id,
                            created_by_user_id=created_by,
                            execution_user_id=exec_uid,
                            scheduler_job_id=job_id,
                            workspace_id=_uid(row, "workspace_id") if row.get("workspace_id") else None,
                            project_row_id=None,
                            project_title=None,
                            execution_target="ide_agent",
                            instructions=instr,
                            ide_workflow=wf,
                        )
                        if run:
                            logger.info("scheduler_jobs: enqueued project_run id=%s from job_id=%s", run.get("id"), job_id)
                            scheduler_jobs_store.mark_job_last_run(job_id=job_id, tenant_id=tenant_id)
                    except Exception:
                        logger.exception("scheduler_jobs: ide_agent PIDEA run failed")
        except Exception:
            logger.exception("scheduler_jobs worker iteration failed")
    logger.info("scheduler_jobs server worker stopped")
