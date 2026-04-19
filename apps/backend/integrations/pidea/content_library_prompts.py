"""Liest Prompts aus dem **portierten** ``content-library`` unter ``integrations/pidea/`` (kein separates PIDEA-Repo)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# …/integrations/pidea/content-library/prompts/  (Snapshot aus dem PIDEA-Upstream; Ordner ``PIDEA/`` nicht nötig)
_INTEGRATION = Path(__file__).resolve().parent
_ROOT = _INTEGRATION / "content-library" / "prompts"
_CONTENT_LIBRARY = _INTEGRATION / "content-library"

# Entspricht der üblichen Task-Pipeline (task-management/*.md im Repo).
DEFAULT_TASK_MANAGEMENT_PHASE_PATHS: tuple[str, ...] = (
    "task-management/task-analyze.md",
    "task-management/task-create.md",
    "task-management/task-execute.md",
    "task-management/task-review.md",
)

# Scheduler-Pipeline: Analyze + Create im selben Chat (nur Analyze startet mit neuem Chat), dann Git, dann Execute.
SCHEDULER_PIPELINE_ANALYZE_CREATE: tuple[str, ...] = (
    "task-management/task-analyze.md",
    "task-management/task-create.md",
)
SCHEDULER_PIPELINE_EXECUTE = "task-management/task-execute.md"
SCHEDULER_PIPELINE_REVIEW = "task-management/task-review.md"


def content_library_prompts_root() -> Path:
    return _ROOT


def read_content_library_prompt(relative_path: str) -> str:
    """
    Liest eine Datei unter ``content-library/prompts/<relative_path>`` (relativ zu ``integrations/pidea/``).

    ``relative_path`` nutzt ``/``, kein ``..``, typisch z. B.
    ``task-management/task-analyze.md``.
    """
    root = _ROOT.resolve()
    rel = relative_path.strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in rel:
        raise ValueError("invalid prompt path")
    full = (root / rel).resolve()
    try:
        full.relative_to(root)
    except ValueError as e:
        raise ValueError("prompt path outside content-library") from e
    if not full.is_file():
        raise FileNotFoundError(f"prompt not found: {rel}")
    return full.read_text(encoding="utf-8")


def read_content_library_file(relative_path: str) -> str:
    """
    Liest eine Datei unter ``content-library/<relative_path>`` (z. B. ``task-check-state.md``
    oder ``prompts/task-management/task-analyze.md``).
    """
    root = _CONTENT_LIBRARY.resolve()
    rel = relative_path.strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in rel:
        raise ValueError("invalid content-library path")
    full = (root / rel).resolve()
    try:
        full.relative_to(root)
    except ValueError as e:
        raise ValueError("path outside content-library") from e
    if not full.is_file():
        raise FileNotFoundError(f"content-library file not found: {rel}")
    return full.read_text(encoding="utf-8")


def resolved_phase_paths(wf: dict[str, Any]) -> list[str]:
    """Reihenfolge der Phasen aus ``ide_workflow`` (bereits normalisiert)."""
    raw = wf.get("phase_prompt_paths")
    if isinstance(raw, list) and len(raw) > 0:
        return [str(x).strip().replace("\\", "/").lstrip("/") for x in raw if str(x).strip()]
    if wf.get("use_pidea_task_management_phases"):
        return list(DEFAULT_TASK_MANAGEMENT_PHASE_PATHS)
    return []
