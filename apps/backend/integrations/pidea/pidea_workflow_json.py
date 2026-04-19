"""Lädt die **originalen** PIDEA-Workflow-JSONs (Port unter ``workflows_data/``).

``resolve_workflow`` entspricht ``WorkflowLoaderService.resolveWorkflow`` (extends → Steps anhängen).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_WORKFLOWS: dict[str, Any] = {}
_TASK_TYPE_MAPPING: dict[str, str] = {}
_LOADED = False

_JSON_NAMES = (
    "task-workflows.json",
    "task-create-workflows.json",
    "analysis-workflows.json",
)


def _workflows_data_dir() -> Path:
    return Path(__file__).resolve().parent / "workflows_data"


def load_workflow_registry(*, force: bool = False) -> None:
    """Merge all JSON files into ``_WORKFLOWS`` (wie PIDEA ``WorkflowLoaderService.loadWorkflows``)."""
    global _LOADED, _WORKFLOWS, _TASK_TYPE_MAPPING
    if _LOADED and not force:
        return
    _WORKFLOWS = {}
    _TASK_TYPE_MAPPING = {}
    base = _workflows_data_dir()
    for name in _JSON_NAMES:
        path = base / name
        if not path.is_file():
            logger.warning("pidea workflow JSON missing: %s", path)
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.error("pidea workflow JSON unreadable %s: %s", path, e)
            continue
        for wid, wf in (data.get("workflows") or {}).items():
            _WORKFLOWS[wid] = wf
        if data.get("taskTypeMapping"):
            _TASK_TYPE_MAPPING.update(data["taskTypeMapping"])
    _LOADED = True
    logger.info("pidea workflows loaded: %d definitions", len(_WORKFLOWS))


def resolve_workflow(workflow_id: str) -> dict[str, Any]:
    """
    Wie ``WorkflowLoaderService.resolveWorkflow``: Basis rekursiv auflösen,
    dann ``steps = base.steps + child.steps``.
    """
    load_workflow_registry()
    wf = _WORKFLOWS.get(workflow_id)
    if not wf:
        raise KeyError(f"workflow not found: {workflow_id}")
    if not wf.get("extends"):
        return dict(wf)
    base_id = str(wf["extends"])
    base_resolved = resolve_workflow(base_id)
    merged = {**base_resolved, **wf}
    merged["steps"] = [
        *(base_resolved.get("steps") or []),
        *(wf.get("steps") or []),
    ]
    return merged


def list_workflow_ids() -> list[str]:
    load_workflow_registry()
    return sorted(_WORKFLOWS.keys())


def workflow_exists(workflow_id: str) -> bool:
    load_workflow_registry()
    return workflow_id in _WORKFLOWS


def task_type_to_workflow_id(task_type: str) -> str | None:
    load_workflow_registry()
    return _TASK_TYPE_MAPPING.get(task_type) or _TASK_TYPE_MAPPING.get("default")
