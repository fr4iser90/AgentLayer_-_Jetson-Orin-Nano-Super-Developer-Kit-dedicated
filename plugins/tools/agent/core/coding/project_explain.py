"""Tool to explain the project structure and purpose."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.backend.domain.identity import get_workspace

TOOL_ID = "project_explain"
TOOL_BUCKET = "productivity"
TOOL_DOMAIN = "project"
TOOL_LABEL = "Project Explainer"
TOOL_DESCRIPTION = (
    "Analyze and explain the project structure, purpose, and key components. "
    "This tool provides a comprehensive overview of the project including: "
    "project type, main purpose, directory structure, key files, technologies used, "
    "and entry points. Use this when user asks about 'the project', 'explain this project', "
    "or wants to understand what the codebase does."
)
TOOL_TRIGGERS = (
    "explain the project",
    "explain project",
    "what is this project",
    "project overview",
    "project structure",
    "what does this project do",
    "describe the project",
    "explain this codebase",
    "what is this codebase",
    "tell me about this project",
)


def execute(args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute project explanation."""
    try:
        workspace = get_workspace()
        
        if not workspace:
            return {"ok": False, "error": "No workspace selected. Please select a workspace first."}
        
        workspace_path = workspace.get("path")
        if not workspace_path:
            return {"ok": False, "error": "Workspace has no path configured."}
        
        root = Path(workspace_path)
        
        if not root.exists():
            return {"ok": False, "error": f"Workspace path does not exist: {workspace_path}"}
        
        readme_content = ""
        if (root / "README.md").exists():
            readme_content = (root / "README.md").read_text()[:2000]
        
        todo_content = ""
        if (root / "TODO.md").exists():
            todo_content = (root / "TODO.md").read_text()[:1000]
        
        py_files = list(root.rglob("*.py"))[:20]
        py_summary = []
        for f in py_files[:10]:
            rel = f.relative_to(root)
            if "test_" not in f.name and "__pycache__" not in str(f):
                py_summary.append(str(rel))
        
        dirs = [d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")]
        
        agent_config = ""
        if (root / "agent-config.yaml").exists():
            agent_config = (root / "agent-config.yaml").read_text()[:500]
        
        explanation = f"""Project Overview:

Directory Structure:
{', '.join(dirs[:10])}

Key Python Files:
{chr(10).join(py_summary[:5])}

{readme_content[:1000] if readme_content else '(No README found)'}

{agent_config if agent_config else ''}
"""
        
        return {"ok": True, "explanation": explanation.strip(), "files_found": len(py_files)}
        
    except Exception as e:
        return {"ok": False, "error": str(e)}