"""Liest Task-Pläne aus dem Workspace (PIDEA: ``docs/agent/tasks/...``) für den Execute-Schritt."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TASK_PLAN_GLOB = "docs/agent/tasks/**/*.md"


def bundle_task_plans_from_repo(
    repo_root: Path,
    *,
    glob_pattern: str | None = None,
    max_files: int = 30,
    max_total_chars: int = 100_000,
) -> str:
    """
    Sammelt Markdown unter dem Repo, typisch die Pläne aus der Task-Create-Phase.

    Pfade müssen unter ``repo_root`` liegen (kein ``..``).
    """
    root = repo_root.resolve()
    if not root.is_dir():
        return ""

    pat = (glob_pattern or DEFAULT_TASK_PLAN_GLOB).strip().replace("\\", "/").lstrip("/")
    if not pat or ".." in pat:
        return ""

    try:
        matches = [p for p in root.glob(pat) if p.is_file()]
    except (OSError, ValueError) as e:
        logger.debug("task_plan_bundle glob failed: %s", e)
        return ""

    def _under_root(p: Path) -> bool:
        try:
            p.resolve().relative_to(root)
            return True
        except ValueError:
            return False

    matches = [p for p in matches if _under_root(p)]
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    matches = matches[: max(1, min(max_files, 50))]

    if not matches:
        return ""

    parts: list[str] = [
        "---",
        "[Task plans / files from workspace — from task-create phase; paths relative to repo root]",
        "",
    ]
    total = 0
    for p in matches:
        rel = p.resolve().relative_to(root)
        rel_s = rel.as_posix()
        try:
            raw = p.read_text(encoding="utf-8")
        except OSError:
            continue
        block = f"### `{rel_s}`\n\n{raw}\n"
        if total + len(block) > max_total_chars:
            remain = max_total_chars - total - 80
            if remain > 200:
                block = f"### `{rel_s}`\n\n{raw[:remain]}…\n\n_(truncated)_\n"
                parts.append(block)
            else:
                parts.append(f"_(Omitted further files; max_total_chars={max_total_chars})_\n")
            break
        parts.append(block)
        total += len(block)

    return "\n".join(parts).strip()
