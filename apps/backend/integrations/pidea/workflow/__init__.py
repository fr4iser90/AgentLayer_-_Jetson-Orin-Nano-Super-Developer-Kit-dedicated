"""Portierte Workflow-Helfer (Git + Shell) — ohne Node-Runtime.

Nutzt Subprozesse mit festen Argumentlisten (kein ``shell=True`` für Git).
Policies (wer darf welches Repo) liegen bei den Aufrufern (Admin/API).
"""

from apps.backend.integrations.pidea.workflow.git_ops import (
    git_create_branch,
    is_git_work_tree,
    resolve_branch_name_template,
    sanitize_task_title_for_branch,
    validate_branch_name,
)
from apps.backend.integrations.pidea.workflow.shell_ops import run_shell

__all__ = [
    "git_create_branch",
    "is_git_work_tree",
    "resolve_branch_name_template",
    "run_shell",
    "sanitize_task_title_for_branch",
    "validate_branch_name",
]
