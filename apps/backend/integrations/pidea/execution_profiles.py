"""Execution profiles → ``ide_workflow`` defaults (PIDEA / IDE execution domain).

These profiles are intentionally **not** workspace-domain logic (todo/projects). They only
materialize the JSON object stored on ``project_runs.ide_workflow`` / ``scheduler_jobs.ide_workflow``.
"""

from __future__ import annotations

from typing import Any

from apps.backend.integrations.pidea.pidea_workflow_json import load_workflow_registry, workflow_exists

_EXEC_PROFILES = frozenset(
    {
        "coding_pipeline",
        "coding_pipeline_git",
        "coding_pipeline_review",
        "docs_pipeline",
        # JSON workflows (workflows_data/*.json ids)
        "pidea_json_task_check_state",
        "pidea_json_task_review",
        "pidea_json_task_create",
        "pidea_json_quick_task_create",
        "pidea_json_comprehensive_analysis",
        "pidea_json_quick_analysis",
        # Escape hatch: any registered workflow id via explicit name
        "pidea_json_workflow",
    }
)


def merge_ide_workflow_overrides(
    base: dict[str, Any],
    overrides: dict[str, Any],
    *,
    default_git_branch_template: str | None,
    default_git_source_branch: str | None,
) -> dict[str, Any]:
    """
    Merge optional overrides into a base ide_workflow.

    Supported override keys (all optional):
    - pidea_workflow_name (string)
    - git_branch_template, git_source_branch
    - scheduler_pipeline_include_review (bool)

    ``default_*`` values apply only when the base does not already define them.

    If ``pidea_workflow_name`` is set, this clears pipeline mode fields that are mutually exclusive
    in ``normalize_ide_workflow`` / runtime runner selection.
    """
    out = dict(base)

    wf_name = str(overrides.get("pidea_workflow_name") or "").strip()
    if wf_name:
        load_workflow_registry()
        if not workflow_exists(wf_name):
            raise ValueError(f"unknown pidea_workflow_name: {wf_name!r}")
        out["pidea_workflow_name"] = wf_name
        out["use_pidea_scheduler_pipeline"] = False
        # JSON workflow path must not keep pipeline-only flags around.
        out.pop("scheduler_pipeline_include_review", None)

    t_git_tmpl = str(overrides.get("git_branch_template") or "").strip()
    if t_git_tmpl:
        out["git_branch_template"] = t_git_tmpl
    elif default_git_branch_template and str(default_git_branch_template).strip():
        out.setdefault("git_branch_template", str(default_git_branch_template).strip())

    t_src = str(overrides.get("git_source_branch") or "").strip()
    if t_src:
        out["git_source_branch"] = t_src
    elif default_git_source_branch and str(default_git_source_branch).strip():
        out.setdefault("git_source_branch", str(default_git_source_branch).strip())

    spr = overrides.get("scheduler_pipeline_include_review")
    if isinstance(spr, bool):
        out["scheduler_pipeline_include_review"] = spr

    return out


def ide_workflow_for_execution_profile(
    profile: str,
    *,
    project_path: str,
    task_title: str,
    default_git_branch_template: str | None,
    default_git_source_branch: str | None,
    pidea_workflow_name: str | None = None,
) -> dict[str, Any]:
    """
    Map a small string profile to a validated-shaped ide_workflow dict.

    Profiles:
    - coding_pipeline: default scheduler pipeline, anchored to project_path; git optional via overrides
    - coding_pipeline_git: pipeline + default branch template + optional source branch
    - coding_pipeline_review: like git profile, but enables review tail
    - docs_pipeline: same pipeline machinery, but adds a documentation-biased preamble
    - pidea_json_*: run a registered JSON workflow id (mutually exclusive with scheduler pipeline)
    - pidea_json_workflow: requires ``pidea_workflow_name`` (tool arg or task override)
    """
    p = (profile or "coding_pipeline").strip().lower()
    if p not in _EXEC_PROFILES:
        raise ValueError(f"unknown execution_profile: {p!r}")

    load_workflow_registry()

    def _json_wf(name: str) -> dict[str, Any]:
        n = str(name).strip()
        if not n:
            raise ValueError("pidea_workflow_name is required for JSON workflow profiles")
        if not workflow_exists(n):
            raise ValueError(f"unknown pidea_workflow_name: {n!r}")
        # project_path is still useful context for prompts/options in many workflows.
        return {"pidea_workflow_name": n, "use_pidea_scheduler_pipeline": False, "project_path": project_path}

    if p == "pidea_json_workflow":
        n = str(pidea_workflow_name or "").strip()
        if not n:
            raise ValueError("execution_profile=pidea_json_workflow requires pidea_workflow_name")
        return _json_wf(n)

    if p == "pidea_json_task_check_state":
        return _json_wf("task-check-state-workflow")

    if p == "pidea_json_task_review":
        return _json_wf("task-review-workflow")

    if p == "pidea_json_task_create":
        return _json_wf("task-create-workflow")

    if p == "pidea_json_quick_task_create":
        return _json_wf("quick-task-create-workflow")

    if p == "pidea_json_comprehensive_analysis":
        return _json_wf("comprehensive-analysis-workflow")

    if p == "pidea_json_quick_analysis":
        return _json_wf("quick-analysis-workflow")

    wf: dict[str, Any] = {"use_pidea_scheduler_pipeline": True, "project_path": project_path}

    if p == "coding_pipeline":
        return wf

    if p == "coding_pipeline_git":
        tmpl = (default_git_branch_template or "").strip() or "agent/{{task.title}}-{{timestamp}}"
        wf["git_branch_template"] = tmpl
        if (default_git_source_branch or "").strip():
            wf["git_source_branch"] = str(default_git_source_branch).strip()
        return wf

    if p == "coding_pipeline_review":
        wf["scheduler_pipeline_include_review"] = True
        tmpl = (default_git_branch_template or "").strip() or "agent/{{task.title}}-{{timestamp}}"
        wf["git_branch_template"] = tmpl
        if (default_git_source_branch or "").strip():
            wf["git_source_branch"] = str(default_git_source_branch).strip()
        return wf

    if p == "docs_pipeline":
        title = (task_title or "").strip()
        wf["prompt_preamble"] = (
            "This is a documentation / explanation task.\n"
            "- Prefer updating docs/markdown and small clarifying edits.\n"
            "- Avoid risky refactors unless explicitly required by the task title.\n"
            f"Task title: {title}\n"
        ).strip()
        return wf

    raise ValueError(f"unhandled execution_profile: {p!r}")
