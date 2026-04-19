"""Git-Operationen im Repo (Port von ``git_create_branch``-Logik, ohne Node/DDD)."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Erlaubte Zeichen für Branch-Namen (strikt; vermeidet Injection in ``git``-Args).
_BRANCH_RE = re.compile(r"^[a-zA-Z0-9._/-]+$")
_MAX_BRANCH_LEN = 244


def sanitize_task_title_for_branch(title: str) -> str:
    """Wie im alten Step: Kleinbuchstaben, nur a-z0-9 und Bindestriche."""
    s = title.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    return s or "task"


def resolve_branch_name_template(
    template: str,
    *,
    task_id: str | None = None,
    task_title: str | None = None,
) -> str:
    """
    Ersetzt ``${task.id}``, ``{{task.title}}``, ``{{timestamp}}`` im Branch-Namen.
    """
    out = template
    if task_id and "${task.id}" in out:
        safe_id = re.sub(r"[^a-zA-Z0-9._-]", "", str(task_id))[:64]
        out = out.replace("${task.id}", safe_id or "task")
    if task_title and "{{task.title}}" in out:
        out = out.replace("{{task.title}}", sanitize_task_title_for_branch(task_title))
    if "{{timestamp}}" in out:
        from time import time as _time

        out = out.replace("{{timestamp}}", str(int(_time() * 1000)))
    return out


def validate_branch_name(name: str) -> None:
    if not name or len(name) > _MAX_BRANCH_LEN:
        raise ValueError("invalid branch name length")
    if name.startswith(("-", "/")) or name.endswith("/"):
        raise ValueError("invalid branch name boundaries")
    if ".." in name:
        raise ValueError("invalid branch name")
    if not _BRANCH_RE.match(name):
        raise ValueError("branch name contains disallowed characters")


def _git_run(
    repo: Path,
    args: list[str],
    *,
    timeout_sec: float,
) -> subprocess.CompletedProcess[str]:
    repo = repo.resolve()
    cmd = ["git", "-C", str(repo), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )


def is_git_work_tree(repo: Path) -> bool:
    p = _git_run(repo, ["rev-parse", "--is-inside-work-tree"], timeout_sec=10.0)
    return p.returncode == 0 and (p.stdout or "").strip() == "true"


def git_create_branch(
    repo: Path,
    branch_name: str,
    *,
    source_branch: str | None = None,
    timeout_sec: float = 120.0,
) -> dict[str, Any]:
    """
    Legt einen lokalen Branch an (``git switch -c`` / ``git checkout -b``).

    Optional: zuerst ``source_branch`` auschecken (muss existieren/lösbar sein).

    Returns:
        ``{"ok": bool, "branch": str, "stdout": str, "stderr": str, "error": str | None}``
    """
    validate_branch_name(branch_name)
    root = repo.resolve()
    if not root.is_dir():
        return _err("repository path is not a directory")

    if not is_git_work_tree(root):
        return _err("not a git repository")

    if source_branch:
        # Erlaubt z. B. ``main``, ``origin/main`` (kein striktes validate_branch_name).
        if not re.match(r"^[a-zA-Z0-9._/@/-]+$", source_branch) or len(source_branch) > _MAX_BRANCH_LEN:
            return _err("invalid source_branch")
        co = _git_run(root, ["checkout", source_branch], timeout_sec=timeout_sec)
        if co.returncode != 0:
            return _err(
                f"checkout {source_branch!r} failed: {(co.stderr or co.stdout or '').strip()}",
            )

    # Prefer git switch -c (Git 2.23+)
    sw = _git_run(root, ["switch", "-c", branch_name], timeout_sec=timeout_sec)
    if sw.returncode == 0:
        logger.info("git: created branch %s in %s", branch_name, root)
        return {
            "ok": True,
            "branch": branch_name,
            "stdout": (sw.stdout or "").strip(),
            "stderr": (sw.stderr or "").strip(),
            "error": None,
        }

    # Fallback: checkout -b (older git)
    ck = _git_run(root, ["checkout", "-b", branch_name], timeout_sec=timeout_sec)
    if ck.returncode == 0:
        logger.info("git: created branch %s in %s (checkout -b)", branch_name, root)
        return {
            "ok": True,
            "branch": branch_name,
            "stdout": (ck.stdout or "").strip(),
            "stderr": (ck.stderr or "").strip(),
            "error": None,
        }

    msg = (sw.stderr or sw.stdout or ck.stderr or ck.stdout or "").strip()
    return _err(msg or "git switch/checkout failed")


def _err(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "branch": "",
        "stdout": "",
        "stderr": message,
        "error": message,
    }
