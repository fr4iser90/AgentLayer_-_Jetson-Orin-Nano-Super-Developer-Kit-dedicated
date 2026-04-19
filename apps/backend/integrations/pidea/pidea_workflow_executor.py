"""
Führt einen aus ``task-workflows.json`` geladenen Workflow aus (Scheduler / ide_agent).

Unterstützt dieselben Kern-Schritte wie PIDEA (Git, neuer Chat, IDE-Nachricht, optionale Bestätigung).
Analyse/Test/Dev-Server/DB-Status-Schritte sind im Node-PIDEA implementiert — hier: strikt optional
(``strict: false`` → log + weiter; ``strict: true`` → Abbruch).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable

from apps.backend.integrations.pidea.content_library_prompts import (
    read_content_library_file,
    read_content_library_prompt,
)
from apps.backend.integrations.pidea.pidea_workflow_json import resolve_workflow
from apps.backend.integrations.pidea.workflow.git_ops import (
    git_create_branch,
    is_git_work_tree,
    resolve_branch_name_template,
    validate_branch_name,
)

logger = logging.getLogger(__name__)

# taskMode (PIDEA IDE options) → Prompt unter content-library/prompts/ oder Root-Datei
_TASK_MODE_PROMPT: dict[str, str | None] = {
    "task-review": "task-management/task-review.md",
    "task-check-state": None,  # content-library/task-check-state.md
    "task-execution": "task-management/task-execute.md",
}

_UNIMPLEMENTED_STRICT = (
    "Step type not implemented in AgentLayer PIDEA port "
    "(exists in original PIDEA Node backend only)."
)

# step / type-Werte aus PIDEA JSON, die hier nicht nachgebaut sind (Node-Backend)
_UNIMPLEMENTED_KINDS = frozenset(
    {
        "codequalityanalysisorchestrator",
        "projectanalysistep",
        "projectteststep",
        "rundevstep",
        "analysis",
        "validation",
        "project_test_step",
        "run_dev_step",
        "task_status_update_step",
        "organization",
        "layerviolationanalysisstep",
        "createtaskstep",
        "task",
    }
)


def _step_key(step: dict[str, Any]) -> str:
    return str(step.get("step") or step.get("type") or "").strip()


def _eval_simple_condition(
    cond: str | None,
    *,
    prev_ok: bool,
) -> bool:
    if not cond or not str(cond).strip():
        return True
    s = cond.strip()
    if "previousStep.success" in s:
        if "&&" in s:
            parts = [p.strip() for p in s.split("&&")]
            for p in parts:
                if p == "previousStep.success" and not prev_ok:
                    return False
                if "previousStep.result.success" in p and not prev_ok:
                    return False
            return prev_ok
        return prev_ok
    return True


def _resolve_branch_name_template(
    template: str,
    *,
    job_id_str: str,
    task_title: str | None,
) -> str:
    t = template.strip()
    if "${task.id}" in t:
        safe_id = re.sub(r"[^a-zA-Z0-9._-]", "", job_id_str)[:64] or "task"
        t = t.replace("${task.id}", safe_id)
    return resolve_branch_name_template(
        t,
        task_id=job_id_str,
        task_title=task_title,
    )


def _build_ide_message(
    step: dict[str, Any],
    row: dict[str, Any],
    wf: dict[str, Any],
    *,
    compose_pidea_message: Callable[..., str],
    job_context_footer: Callable[..., str],
) -> str:
    options = step.get("options") or {}
    use_task_prompt = bool(options.get("useTaskPrompt"))
    task_mode = str(options.get("taskMode") or "").strip()
    footer = job_context_footer(row)
    pre = (wf.get("prompt_preamble") or "").strip()

    body: str
    if use_task_prompt:
        rel = _TASK_MODE_PROMPT.get(task_mode, "task-management/task-execute.md")
        try:
            if rel is None:
                body = read_content_library_file("task-check-state.md")
            else:
                body = read_content_library_prompt(rel)
        except (OSError, ValueError) as e:
            logger.warning("workflow ide step: fallback to compose message (%s)", e)
            body = compose_pidea_message(row, wf)
    else:
        msg = options.get("message")
        body = str(msg) if msg is not None else compose_pidea_message(row, wf)

    parts: list[str] = []
    if pre:
        parts.extend([pre, ""])
    parts.append(body.strip())
    parts.append("")
    parts.append(footer)
    return "\n".join(parts).strip()


def _repo_path(wf: dict[str, Any]) -> Path | None:
    for key in ("git_repo_path", "workspace_path"):
        s = (wf.get(key) or "").strip()
        if s:
            try:
                return Path(s).expanduser().resolve(strict=True)
            except OSError:
                return None
    return None


def run_resolved_pidea_workflow(
    resolved: dict[str, Any],
    *,
    row: dict[str, Any],
    wf: dict[str, Any],
    job_id_str: str,
    timeout_s: float,
    run_ide_agent_message_sync: Callable[..., dict[str, Any]],
    compose_pidea_message: Callable[..., str],
    job_context_footer: Callable[..., str],
) -> tuple[bool, str | None]:
    steps = resolved.get("steps") or []
    prev_ok = True
    pending_new_chat_from_create = False
    first_ide_step = True

    for i, step in enumerate(steps):
        name = step.get("name") or f"step-{i}"
        if step.get("enabled") is False:
            logger.info("pidea workflow: skip disabled step %s", name)
            continue
        cond = step.get("condition")
        if not _eval_simple_condition(cond if isinstance(cond, str) else None, prev_ok=prev_ok):
            logger.info("pidea workflow: skip step %s (condition false)", name)
            continue

        kind = _step_key(step)
        strict = bool(step.get("strict"))
        options = step.get("options") or {}

        if kind in ("git_create_branch",):
            repo = _repo_path(wf)
            tmpl = (options.get("branchName") or "").strip()
            if not repo or not tmpl:
                err = "git_create_branch: need ide_workflow.git_repo_path (or workspace_path) and branchName in JSON"
                logger.warning("pidea workflow %s: %s", name, err)
                if strict:
                    return False, err
                prev_ok = False
                continue
            if not repo.is_dir() or not is_git_work_tree(repo):
                err = "git_create_branch: invalid git_repo_path"
                if strict:
                    return False, err
                prev_ok = False
                continue
            title = (str(row.get("title") or "").strip()) or None
            branch_raw = _resolve_branch_name_template(
                tmpl,
                job_id_str=job_id_str,
                task_title=title,
            )
            try:
                validate_branch_name(branch_raw)
            except ValueError as e:
                err = f"invalid branch name: {e}"
                if strict:
                    return False, err
                prev_ok = False
                continue
            src = (options.get("sourceBranch") or options.get("fromBranch") or "").strip() or None
            if options.get("createBranch") is False:
                logger.info("pidea workflow: skip git (createBranch false) %s", name)
                prev_ok = True
                continue
            r = git_create_branch(repo, branch_raw, source_branch=src, timeout_sec=180.0)
            prev_ok = bool(r.get("ok"))
            if not prev_ok:
                err = str(r.get("error") or r.get("stderr") or "git failed")[:2000]
                logger.warning("pidea workflow git %s: %s", name, err)
                if strict:
                    return False, err
            continue

        if kind in ("create_chat_step",):
            pending_new_chat_from_create = True
            prev_ok = True
            continue

        if kind in (
            "ide_send_message_step",
            "IDESendMessageStep",
            "ide_send_message",
        ):
            text = _build_ide_message(
                step,
                row,
                wf,
                compose_pidea_message=compose_pidea_message,
                job_context_footer=job_context_footer,
            )
            opt_click = bool(options.get("clickNewChat"))
            new_chat = opt_click or pending_new_chat_from_create
            if first_ide_step and wf.get("new_chat") is not None:
                new_chat = bool(wf.get("new_chat"))
            pending_new_chat_from_create = False
            first_ide_step = False
            logger.info(
                "pidea workflow: ide_send %s new_chat=%s chars=%s",
                name,
                new_chat,
                len(text),
            )
            result = run_ide_agent_message_sync(
                text,
                new_chat=new_chat,
                reply_timeout_s=timeout_s,
            )
            prev_ok = isinstance(result, dict) and bool(result.get("ok"))
            if not prev_ok and strict:
                return False, f"ide step failed: {name}"
            continue

        if kind in ("confirmation_step", "ConfirmationStep"):
            if options.get("enabled") is False:
                prev_ok = True
                continue
            prompt = (options.get("confirmationPrompt") or "").strip()
            if not prompt:
                prev_ok = True
                continue
            text = f"{prompt}\n\n{job_context_footer(row)}".strip()
            logger.info("pidea workflow: confirmation_step %s", name)
            co_timeout = timeout_s
            raw_to = options.get("timeout")
            if isinstance(raw_to, (int, float)) and raw_to > 0:
                co_timeout = min(timeout_s, float(raw_to) / 1000.0)
            result = run_ide_agent_message_sync(
                text,
                new_chat=False,
                reply_timeout_s=co_timeout,
            )
            prev_ok = isinstance(result, dict) and bool(result.get("ok"))
            if not prev_ok and strict:
                return False, f"confirmation failed: {name}"
            continue

        # Node-only / nicht portiert — anhand step/type (case-insensitive)
        k_norm = kind.lower().replace("_", "")
        if k_norm in _UNIMPLEMENTED_KINDS or kind.lower() in _UNIMPLEMENTED_KINDS:
            logger.warning(
                "pidea workflow: %s step %r (%s) — %s",
                "abort" if strict else "skip",
                name,
                kind,
                _UNIMPLEMENTED_STRICT,
            )
            if strict:
                return False, f"{kind}: {_UNIMPLEMENTED_STRICT}"
            prev_ok = True
            continue

        logger.warning("pidea workflow: unknown step type %r (%s) — skip", kind, name)
        if strict:
            return False, f"unknown step {kind}"
        prev_ok = True

    return True, None


def run_pidea_workflow_by_id(
    workflow_id: str,
    *,
    row: dict[str, Any],
    wf: dict[str, Any],
    job_id_str: str,
    timeout_s: float,
    run_ide_agent_message_sync: Callable[..., dict[str, Any]],
    compose_pidea_message: Callable[..., str],
    job_context_footer: Callable[..., str],
) -> tuple[bool, str | None]:
    try:
        resolved = resolve_workflow(workflow_id)
    except KeyError as e:
        return False, str(e)
    return run_resolved_pidea_workflow(
        resolved,
        row=row,
        wf=wf,
        job_id_str=job_id_str,
        timeout_s=timeout_s,
        run_ide_agent_message_sync=run_ide_agent_message_sync,
        compose_pidea_message=compose_pidea_message,
        job_context_footer=job_context_footer,
    )
