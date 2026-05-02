"""Delegate a subtask to a subagent session."""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable

__version__ = "1.0.0"
TOOL_ID = "coding_task"
TOOL_BUCKET = "meta"
TOOL_DOMAIN = "coding"
TOOL_TRIGGERS = ("coding task", "subagent", "delegate")
TOOL_CAPABILITIES = ("coding.task",)
TOOL_LABEL = "Coding: Task"
TOOL_DESCRIPTION = (
    "Delegate a subtask to run in an isolated subagent session. "
    "The subagent gets its own context and can use coding tools independently. "
    "Returns a task_id for tracking and resuming."
)

_active_tasks: dict[str, dict[str, Any]] = {}


def coding_task(arguments: dict[str, Any]) -> str:
    description = (arguments.get("description") or "").strip()
    if not description:
        return json.dumps({"ok": False, "error": "description is required"}, ensure_ascii=False)
    prompt = (arguments.get("prompt") or "").strip()
    if not prompt:
        return json.dumps({"ok": False, "error": "prompt is required"}, ensure_ascii=False)
    task_id = (arguments.get("task_id") or "").strip()
    if task_id and task_id in _active_tasks:
        existing = _active_tasks[task_id]
        return json.dumps(
            {
                "ok": False,
                "error": f"task_id {task_id!r} already exists. Use a different description or wait for completion.",
                "existing_task": existing,
            },
            ensure_ascii=False,
        )
    new_id = f"task-{uuid.uuid4().hex[:12]}"
    _active_tasks[new_id] = {
        "id": new_id,
        "description": description,
        "prompt": prompt,
        "status": "pending",
        "parent_id": arguments.get("_parent_id"),
    }
    return json.dumps(
        {
            "ok": True,
            "task_id": new_id,
            "description": description,
            "status": "pending",
            "detail": (
                f"Task {new_id!r} created. "
                "In a full deployment, this would spawn a subagent session. "
                "For now, use this as a structured planning/organization tool."
            ),
        },
        ensure_ascii=False,
    )


HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "coding_task": coding_task,
}

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "coding_task",
            "TOOL_DESCRIPTION": TOOL_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "TOOL_DESCRIPTION": "A short (3-5 words) description of the task",
                    },
                    "prompt": {
                        "type": "string",
                        "TOOL_DESCRIPTION": "The full task prompt/instructions for the subagent",
                    },
                    "task_id": {
                        "type": "string",
                        "TOOL_DESCRIPTION": "Resume a prior task by ID (optional)",
                    },
                },
                "required": ["description", "prompt"],
            },
        },
    },
]
