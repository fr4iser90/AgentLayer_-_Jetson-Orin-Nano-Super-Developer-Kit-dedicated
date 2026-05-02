"""Parse ``ide_workflow`` on ``scheduler_jobs`` and optional git step before PIDEA."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

# from apps.backend.integrations.pidea.content_library_prompts import (
#     DEFAULT_TASK_MANAGEMENT_PHASE_PATHS,
# )
# from apps.backend.integrations.pidea.workflow.git_ops import (
#     git_create_branch,
#     is_git_work_tree,
#     resolve_branch_name_template,
#     validate_branch_name,
# )

logger = logging.getLogger(__name__)

_MAX_PREAMBLE = 12_000
_MAX_JSON_BYTES = 24_000
_MAX_PHASES = 12
_ALLOWED_KEYS = frozenset(
    {
        "new_chat",
        "prompt_preamble",
        "git_repo_path",
        "git_branch_template",
        "git_source_branch",
        "project_path",
        "phase_prompt_paths",
        "use_pidea_task_management_phases",
        "pidea_workflow_name",
        "use_pidea_scheduler_pipeline",
        "scheduler_pipeline_include_review",
        "attach_task_plans_to_execute",
        "task_plan_glob",
        "task_plan_max_files",
        "task_plan_max_chars",
        "use_cdp_project_path",
    }
)


def ide_workflow_from_row(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("ide_workflow")
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return d if isinstance(d, dict) else {}
    return {}


def normalize_ide_workflow(raw: Any) -> dict[str, Any]:
    """Validate and normalize payload for DB (schedule_job_create)."""
    if raw is None:
        return {}
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            raw = json.loads(s)
        except json.JSONDecodeError as e:
            raise ValueError("ide_workflow: invalid JSON") from e
    if not isinstance(raw, dict):
        raise ValueError("ide_workflow must be a JSON object")
    extra = set(raw.keys()) - _ALLOWED_KEYS
    if extra:
        raise ValueError(f"ide_workflow unknown keys: {sorted(extra)}")
    blob = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    if len(blob.encode("utf-8")) > _MAX_JSON_BYTES:
        raise ValueError("ide_workflow too large")
    out: dict[str, Any] = {}
    if "new_chat" in raw:
        out["new_chat"] = bool(raw["new_chat"])
    if raw.get("prompt_preamble") is not None:
        p = str(raw["prompt_preamble"])
        if len(p) > _MAX_PREAMBLE:
            raise ValueError("prompt_preamble too long")
        out["prompt_preamble"] = p
    if raw.get("git_repo_path"):
        out["git_repo_path"] = str(raw["git_repo_path"]).strip()
    if raw.get("git_branch_template"):
        out["git_branch_template"] = str(raw["git_branch_template"]).strip()
    if raw.get("git_source_branch"):
        out["git_source_branch"] = str(raw["git_source_branch"]).strip()
    if raw.get("project_path"):
        out["project_path"] = str(raw["project_path"]).strip()

    wf_name_in = raw.get("pidea_workflow_name")
    if wf_name_in is not None and str(wf_name_in).strip():
        from apps.backend.integrations.pidea.pidea_workflow_json import (
            load_workflow_registry,
            workflow_exists,
        )

        wn = str(wf_name_in).strip()
        load_workflow_registry()
        if not workflow_exists(wn):
            raise ValueError(
                f"pidea_workflow_name unknown: {wn!r} (use an id from PIDEA task-workflows.json)"
            )
        out["pidea_workflow_name"] = wn

    paths_in = raw.get("phase_prompt_paths")
    use_default = bool(raw.get("use_pidea_task_management_phases"))
    if paths_in is not None:
        if not isinstance(paths_in, list):
            raise ValueError("phase_prompt_paths must be a list of strings")
        if len(paths_in) > _MAX_PHASES:
            raise ValueError(f"phase_prompt_paths: at most {_MAX_PHASES} entries")
        cleaned: list[str] = []
        for p in paths_in:
            s = str(p).strip().replace("\\", "/").lstrip("/")
            if not s or ".." in s:
                raise ValueError("phase_prompt_paths: invalid path")
            if not s.endswith(".md"):
                raise ValueError("phase_prompt_paths: expected .md paths under content-library/prompts/")
            cleaned.append(s)
        out["phase_prompt_paths"] = cleaned
    elif use_default:
        out["use_pidea_task_management_phases"] = True
        out["phase_prompt_paths"] = list(DEFAULT_TASK_MANAGEMENT_PHASE_PATHS)

    if out.get("pidea_workflow_name") and (
        raw.get("use_pidea_task_management_phases")
        or raw.get("phase_prompt_paths") is not None
    ):
        raise ValueError(
            "ide_workflow: use pidea_workflow_name alone, or phase_prompt_paths / "
            "use_pidea_task_management_phases — not both"
        )

    if "use_pidea_scheduler_pipeline" in raw:
        out["use_pidea_scheduler_pipeline"] = bool(raw.get("use_pidea_scheduler_pipeline"))
    if out.get("use_pidea_scheduler_pipeline"):
        out["scheduler_pipeline_include_review"] = bool(
            raw.get("scheduler_pipeline_include_review", False)
        )
    if out.get("use_pidea_scheduler_pipeline") and (
        raw.get("pidea_workflow_name")
        or raw.get("use_pidea_task_management_phases")
        or raw.get("phase_prompt_paths") is not None
    ):
        raise ValueError(
            "ide_workflow: use_pidea_scheduler_pipeline excludes pidea_workflow_name, "
            "phase_prompt_paths, and use_pidea_task_management_phases"
        )

    if "attach_task_plans_to_execute" in raw:
        out["attach_task_plans_to_execute"] = bool(raw.get("attach_task_plans_to_execute"))
    if raw.get("task_plan_glob") is not None:
        tg = str(raw["task_plan_glob"]).strip().replace("\\", "/").lstrip("/")
        if len(tg) > 500:
            raise ValueError("task_plan_glob too long")
        if ".." in tg:
            raise ValueError("task_plan_glob must not contain ..")
        out["task_plan_glob"] = tg
    if "use_cdp_project_path" in raw:
        out["use_cdp_project_path"] = bool(raw.get("use_cdp_project_path"))

    for key, lo, hi in (
        ("task_plan_max_files", 1, 50),
        ("task_plan_max_chars", 2_000, 200_000),
    ):
        if raw.get(key) is not None:
            try:
                v = int(raw[key])
            except (TypeError, ValueError) as e:
                raise ValueError(f"ide_workflow {key} must be an integer") from e
            if v < lo or v > hi:
                raise ValueError(f"ide_workflow {key} must be between {lo} and {hi}")
            out[key] = v

    return out


def job_context_footer(row: dict[str, Any]) -> str:
    """Block mit Job-Metadaten + Zusatzinstruktionen (unter den PIDEA-Prompt-Dateien)."""
    lines: list[str] = ["---", "[Scheduler job context]"]
    t = (str(row.get("title") or "").strip()) or None
    if t:
        lines.append(f"Title: {t}")
    ws = row.get("dashboard_id")
    if ws is not None:
        lines.append(f"Dashboard id: {ws}")
    instr = str(row.get("instructions") or "").strip()
    if instr:
        lines.append("Additional instructions:")
        lines.append(instr[:31000])
    lines.append("---")
    return "\n".join(lines)


def compose_pidea_message(
    row: dict[str, Any],
    wf: dict[str, Any],
) -> str:
    """Build composer text: optional preamble + standard job block."""
    title = (str(row.get("title") or "").strip()) or None
    instr = str(row.get("instructions") or "").strip()
    parts: list[str] = []
    pre = (wf.get("prompt_preamble") or "").strip()
    if pre:
        parts.append(pre)
        parts.append("")
    parts.append("[Scheduled job — scheduler_jobs / ide_agent]")
    if title:
        parts.append(f"Title: {title}")
    ws = row.get("dashboard_id")
    if ws is not None:
        parts.append(f"Dashboard id: {ws}")
    parts.append("Instructions:")
    parts.append(instr[:31000])
    return "\n".join(parts).strip()


def run_optional_git_branch(
    row: dict[str, Any],
    wf: dict[str, Any],
    *,
    job_id_str: str,
) -> tuple[bool, str | None]:
    """
    If ``git_branch_template`` and ``git_repo_path`` are set, create branch.

    Returns:
        ``(True, None)`` on success or when git step skipped.
        ``(False, error)`` on failure (caller should not advance last_run_at).
    """
    tmpl = (wf.get("git_branch_template") or "").strip()
    repo_s = (wf.get("git_repo_path") or wf.get("project_path") or "").strip()
    if not tmpl and not repo_s:
        return True, None
    if not tmpl or not repo_s:
        logger.warning(
            "scheduler_jobs ide_workflow: git_branch_template and git_repo_path must both be set — skipping git"
        )
        return True, None

    try:
        root = Path(repo_s).expanduser().resolve(strict=True)
    except OSError as e:
        return False, f"git_repo_path not usable: {e}"

    if not root.is_dir():
        return False, "git_repo_path is not a directory"

    if not is_git_work_tree(root):
        return False, "git_repo_path is not a git repository"

    title = (str(row.get("title") or "").strip()) or None
    branch_raw = resolve_branch_name_template(
        tmpl,
        task_id=job_id_str,
        task_title=title,
    )
    try:
        validate_branch_name(branch_raw)
    except ValueError as e:
        return False, f"invalid branch name after template: {e}"

    src = (wf.get("git_source_branch") or "").strip() or None
    r = git_create_branch(root, branch_raw, source_branch=src, timeout_sec=180.0)
    if not r.get("ok"):
        err = r.get("error") or r.get("stderr") or "git_create_branch failed"
        return False, str(err)[:2000]

    logger.info(
        "scheduler_jobs: created git branch %s in %s",
        r.get("branch"),
        root,
    )
    return True, None
