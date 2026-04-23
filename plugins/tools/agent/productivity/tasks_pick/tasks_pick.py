"""Pick an open task and enqueue an IDE agent run for it (server-side orchestration)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from apps.backend.domain.identity import get_identity
from apps.backend.domain.plugin_system.plugin_invoke import invoke_registered_tool
from apps.backend.infrastructure import operator_settings
from apps.backend.infrastructure.db import db
from apps.backend.integrations.pidea.execution_profiles import (
    ide_workflow_for_execution_profile,
    merge_ide_workflow_overrides,
)
from apps.backend.workspace import db as workspace_db
from apps.backend.workspace.tool_workspace_resolve import resolve_workspace_id_for_kind

__version__ = "0.4.0"
TOOL_ID = "tasks_pick"
TOOL_BUCKET = "productivity"
TOOL_DOMAIN = "productivity"
TOOL_LABEL = "Task picker"
TOOL_DESCRIPTION = (
    "Pick one open task from a todo workspace and enqueue an IDE agent run for it (project_runs). "
    "Intended for server_periodic schedules: check tasks → pick one → queue ide_agent execution."
)
TOOL_TRIGGERS = (
    "pick task",
    "task scheduler",
    "process tasks",
    "work on tasks",
    "enqueue ide run",
    "ide agent task",
)
TOOL_CAPABILITIES = ("workspace.todo.read", "workspace.todo.write", "project.run.write")
TOOL_MIN_ROLE = "user"

AGENT_TOOL_META_BY_NAME = {
    "tasks_pick_and_enqueue_ide_run": {"min_role": "user", "capabilities": ("project.run.write",)},
}

_MAX_TASKS_SCAN = 500


def _err(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg}, ensure_ascii=False)


def _identity() -> tuple[int, uuid.UUID] | None:
    tid, uid = get_identity()
    if uid is None:
        return None
    return (int(tid), uid)


def _as_uuid(v: Any) -> uuid.UUID | None:
    if v is None:
        return None
    if isinstance(v, uuid.UUID):
        return v
    try:
        s = str(v).strip()
        if not s:
            return None
        return uuid.UUID(s)
    except (ValueError, TypeError):
        return None


def tasks_pick_and_enqueue_ide_run(arguments: dict[str, Any]) -> str:
    """
    Pick first task row where:
    - done != true
    - project_path is non-empty (required to anchor IDE work deterministically)

    Writes:
    - sets task.in_progress=true
    - sets task.picked_at ISO timestamp (UTC)

    Then enqueues:
    - project_run_create(instructions=..., execution_user_id=admin, ide_workflow={...})
    """
    ident = _identity()
    if ident is None:
        return _err("missing identity — not authenticated")
    tenant_id, caller_uid = ident

    require_pidea_enabled = bool(arguments.get("require_pidea_enabled", True))
    if require_pidea_enabled and not operator_settings.pidea_effective_enabled():
        return _err("IDE agent is not enabled (Admin → Interfaces → PIDEA)")

    default_git_branch_template = arguments.get("default_git_branch_template")
    default_git_source_branch = arguments.get("default_git_source_branch")
    tool_profile_raw = arguments.get("execution_profile")
    tool_profile = str(tool_profile_raw).strip().lower() if tool_profile_raw is not None else ""
    tool_pidea_wf_raw = arguments.get("pidea_workflow_name")
    tool_pidea_wf = str(tool_pidea_wf_raw).strip() if tool_pidea_wf_raw is not None else ""

    # Which task workspace?
    raw_wid = arguments.get("workspace_id")
    wid, res_err = resolve_workspace_id_for_kind(
        caller_uid, tenant_id, kind="todo", raw_workspace_id=raw_wid
    )
    if wid is None:
        return _err(res_err or "workspace_id required (todo workspace)")

    ws = workspace_db.workspace_get(caller_uid, tenant_id, wid)
    if ws is None:
        return _err("workspace not found or no access")
    if (ws.get("kind") or "").strip() != "todo":
        return _err("workspace is not kind todo")

    # Choose admin execution user (default: caller if admin).
    exec_uid = caller_uid
    exec_uid_raw = arguments.get("execution_user_id")
    if exec_uid_raw is not None and str(exec_uid_raw).strip():
        parsed = _as_uuid(exec_uid_raw)
        if parsed is None:
            return _err("execution_user_id must be a UUID")
        exec_uid = parsed
    if db.user_role(exec_uid) != "admin":
        return _err("execution_user_id must be an admin user (ide_agent execution is admin-only)")

    data = ws.get("data") if isinstance(ws.get("data"), dict) else {}
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        tasks = []

    picked_idx: int | None = None
    picked: dict[str, Any] | None = None
    for i, t in enumerate(tasks[:_MAX_TASKS_SCAN]):
        if not isinstance(t, dict):
            continue
        if bool(t.get("done")):
            continue
        if bool(t.get("in_progress")):
            continue
        project_path = str(t.get("project_path") or "").strip()
        if not project_path:
            continue
        title = str(t.get("title") or "").strip()
        if not title:
            continue
        picked_idx = i
        picked = t
        break

    if picked_idx is None or picked is None:
        return json.dumps(
            {"ok": True, "picked": False, "reason": "no eligible open tasks with project_path"},
            ensure_ascii=False,
        )

    now = datetime.now(timezone.utc).isoformat()
    picked2 = dict(picked)
    if not str(picked2.get("id") or "").strip():
        # Stable id for correlating task rows across runs (not the same as git ${task.id} substitution).
        picked2["id"] = str(uuid.uuid4())
    picked2["in_progress"] = True
    picked2["picked_at"] = now
    tasks2 = list(tasks)
    tasks2[picked_idx] = picked2

    new_data = dict(data)
    new_data["tasks"] = tasks2
    updated = workspace_db.workspace_update(caller_uid, tenant_id, wid, data=new_data)
    if updated is None:
        return _err("failed to mark task in_progress (no write access?)")

    project_path = str(picked2.get("project_path") or "").strip()
    task_profile_raw = picked2.get("execution_profile")
    task_profile = str(task_profile_raw).strip().lower() if task_profile_raw is not None else ""
    profile = task_profile or tool_profile or "coding_pipeline"

    instructions = str(arguments.get("instructions_prefix") or "").strip()
    if instructions:
        instructions = instructions + "\n\n"
    instructions += (
        "You are an IDE coding agent. Work on this task.\n\n"
        f"Project path: {project_path}\n"
        f"Task: {picked2.get('title')}\n"
    )

    try:
        base_wf = ide_workflow_for_execution_profile(
            profile,
            project_path=project_path,
            task_title=str(picked2.get("title") or ""),
            default_git_branch_template=str(default_git_branch_template)
            if default_git_branch_template is not None
            else None,
            default_git_source_branch=str(default_git_source_branch)
            if default_git_source_branch is not None
            else None,
            pidea_workflow_name=tool_pidea_wf or None,
        )
        arg_overrides: dict[str, Any] = {}
        if tool_pidea_wf:
            arg_overrides["pidea_workflow_name"] = tool_pidea_wf
        ide_workflow = merge_ide_workflow_overrides(
            base_wf,
            {**arg_overrides, **picked2},
            default_git_branch_template=str(default_git_branch_template)
            if default_git_branch_template is not None
            else None,
            default_git_source_branch=str(default_git_source_branch)
            if default_git_source_branch is not None
            else None,
        )
    except ValueError as e:
        return _err(str(e))

    raw = invoke_registered_tool(
        "project_run_create",
        {
            "instructions": instructions,
            "execution_user_id": str(exec_uid),
            "ide_workflow": ide_workflow,
        },
    )
    try:
        out = json.loads(raw)
    except Exception:
        return _err("project_run_create returned non-JSON")
    if not isinstance(out, dict) or not out.get("ok"):
        return json.dumps(
            {
                "ok": False,
                "error": "failed to enqueue project run",
                "tool_result": out,
            },
            ensure_ascii=False,
        )

    run = out.get("run") if isinstance(out.get("run"), dict) else None
    return json.dumps(
        {
            "ok": True,
            "picked": True,
            "workspace_id": str(wid),
            "task_index": picked_idx,
            "task": picked2,
            "execution_profile": profile,
            "ide_workflow": ide_workflow,
            "enqueued_run": run,
        },
        ensure_ascii=False,
    )


HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "tasks_pick_and_enqueue_ide_run": tasks_pick_and_enqueue_ide_run,
}

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "tasks_pick_and_enqueue_ide_run",
            "TOOL_DESCRIPTION": (
                "Pick one open task from a todo workspace (requires task.project_path) and enqueue "
                "a one-shot ide_agent run (project_runs). Marks the task as in_progress."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "TOOL_DESCRIPTION": "Todo workspace UUID (kind todo). Optional only if you have exactly one.",
                    },
                    "execution_user_id": {
                        "type": "string",
                        "TOOL_DESCRIPTION": "Admin UUID to execute the IDE run as (required for ide_agent).",
                    },
                    "instructions_prefix": {"type": "string", "TOOL_DESCRIPTION": "Optional preamble."},
                    "execution_profile": {
                        "type": "string",
                        "TOOL_DESCRIPTION": (
                            "Execution profile mapping to ide_workflow defaults. "
                            "Allowed: coding_pipeline, coding_pipeline_git, coding_pipeline_review, docs_pipeline, "
                            "pidea_json_task_check_state, pidea_json_task_review, pidea_json_task_create, "
                            "pidea_json_quick_task_create, pidea_json_comprehensive_analysis, pidea_json_quick_analysis, "
                            "pidea_json_workflow. "
                            "Task.execution_profile overrides this when set."
                        ),
                    },
                    "pidea_workflow_name": {
                        "type": "string",
                        "TOOL_DESCRIPTION": (
                            "Optional explicit PIDEA JSON workflow id (from workflows_data). "
                            "If execution_profile=pidea_json_workflow, this field is required. "
                            "Task.pidea_workflow_name overrides this when set."
                        ),
                    },
                    "default_git_branch_template": {
                        "type": "string",
                        "TOOL_DESCRIPTION": (
                            "Optional default git branch template for git-enabled profiles. "
                            "Supports {{task.title}}, {{timestamp}} placeholders (and ${task.id} if you "
                            "intentionally want the pipeline run id substituted by git_ops)."
                        ),
                    },
                    "default_git_source_branch": {
                        "type": "string",
                        "TOOL_DESCRIPTION": "Optional default git source branch (e.g. main) for git-enabled profiles.",
                    },
                    "require_pidea_enabled": {
                        "type": "boolean",
                        "TOOL_DESCRIPTION": "Default true; if false, allows enqueuing even when PIDEA is disabled.",
                    },
                },
                "required": [],
            },
        },
    }
]

