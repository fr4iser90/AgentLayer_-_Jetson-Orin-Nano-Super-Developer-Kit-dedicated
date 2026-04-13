"""
Tool **Executor** (deterministic): map ``(tool_name, arguments)`` → JSON string result.

This module is the supported entry point for:

- The chat tool loop (Planner asks the model *what* to call; Executor runs it).
- Future step runners, tests, and orchestration (separate from cron scheduled jobs).

The **Planner** lives in ``src/domain/agent.py`` (LLM + rounds + message assembly). Do not add
LLM or HTTP-to-Ollama calls here.
"""

from __future__ import annotations

from typing import Any

from src.domain.plugin_system.tools import run_tool


def execute_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
    """
    Run a registered tool handler with operator policy, identity, and DB logging (via ``run_tool``).
    """
    return run_tool((name or "").strip(), dict(arguments or {}))
