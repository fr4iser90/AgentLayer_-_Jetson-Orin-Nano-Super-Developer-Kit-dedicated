"""Execute shell commands within the coding root directory."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from apps.backend.core.config import config as _global_config

from plugins.tools.agent.core.coding.coding_common import (
    coding_root,
    validate_coding_path,
    _disabled_error,
    _no_root_error,
)

__version__ = "1.0.0"
TOOL_ID = "coding_bash"
TOOL_BUCKET = "files"
TOOL_DOMAIN = "coding"
TOOL_TRIGGERS = ("coding bash", "run command", "shell", "execute")
TOOL_CAPABILITIES = ("coding.execute",)
TOOL_LABEL = "Coding: Bash"
TOOL_DESCRIPTION = (
    "Run a shell command within the coding workspace. "
    "Output is truncated if too large; use workdir to set the directory. "
    "Supports timeout. Dangerous commands (rm -rf /, etc.) are blocked."
)

DEFAULT_TIMEOUT = 120
MAX_OUTPUT_BYTES = 50_000

_BLOCKED_COMMANDS = frozenset({
    "rm -rf /",
    "rm -rf /*",
    "chmod -R 777 /",
    "dd if=/dev/zero",
    "mkfs",
    "fdisk",
    "parted",
    "iptables",
    "ufw",
})


def _is_blocked(command: str) -> str | None:
    lower = command.lower().strip()
    for blocked in _BLOCKED_COMMANDS:
        if blocked in lower:
            return f"command blocked: '{blocked}' is not allowed"
    return None


def _tail(text: str, max_bytes: int, max_lines: int = 200) -> tuple[str, bool]:
    lines = text.split("\n")
    if len(lines) <= max_lines and len(text.encode("utf-8")) <= max_bytes:
        return text, False
    out: list[str] = []
    total_bytes = 0
    for line in reversed(lines):
        line_bytes = len(line.encode("utf-8"))
        if total_bytes + line_bytes > max_bytes or len(out) >= max_lines:
            break
        out.append(line)
        total_bytes += line_bytes
    out.reverse()
    return "\n".join(out), True


def coding_bash(arguments: dict[str, Any]) -> str:
    command = (arguments.get("command") or "").strip()
    if not command:
        return json.dumps({"ok": False, "error": "command is required"}, ensure_ascii=False)
    blocked = _is_blocked(command)
    if blocked:
        return json.dumps({"ok": False, "error": blocked}, ensure_ascii=False)
    root = coding_root()
    if root is None:
        return _no_root_error()
    if not _global_config.CODING_ENABLED:
        return _disabled_error()
    workdir_rel = (arguments.get("workdir") or "").strip()
    if workdir_rel:
        resolved_wd, err = validate_coding_path(workdir_rel)
        if err:
            return err
        assert resolved_wd is not None
        cwd = str(resolved_wd)
    else:
        cwd = str(root.resolve())
    try:
        timeout_s = max(1, int(arguments.get("timeout", DEFAULT_TIMEOUT)))
    except (TypeError, ValueError):
        timeout_s = DEFAULT_TIMEOUT
    env = {
        **os.environ,
        "HOME": str(root),
        "PWD": cwd,
    }
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        out_text = ""
        if e.stdout:
            out_text += str(e.stdout)
        if e.stderr:
            out_text += "\n" + str(e.stderr)
        preview, cut = _tail(out_text, MAX_OUTPUT_BYTES)
        detail = "..." if cut else ""
        return json.dumps(
            {
                "ok": False,
                "error": f"command timed out after {timeout_s}s",
                "exit_code": -1,
                "truncated": cut,
                "output": f"{detail}{preview}",
            },
            ensure_ascii=False,
        )
    except OSError as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
    combined = ""
    if result.stdout:
        combined += result.stdout
    if result.stderr:
        if combined:
            combined += "\n--- stderr ---\n"
        combined += result.stderr
    if not combined:
        combined = "(no output)"
    preview, cut = _tail(combined, MAX_OUTPUT_BYTES)
    return json.dumps(
        {
            "ok": True,
            "exit_code": result.returncode,
            "truncated": cut,
            "output": preview,
        },
        ensure_ascii=False,
    )


HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "coding_bash": coding_bash,
}

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "coding_bash",
            "TOOL_DESCRIPTION": TOOL_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "TOOL_DESCRIPTION": "The shell command to execute",
                    },
                    "timeout": {
                        "type": "integer",
                        "TOOL_DESCRIPTION": f"Timeout in seconds (default {DEFAULT_TIMEOUT})",
                    },
                    "workdir": {
                        "type": "string",
                        "TOOL_DESCRIPTION": "Working directory relative to coding root",
                    },
                },
                "required": ["command"],
            },
        },
    },
]
