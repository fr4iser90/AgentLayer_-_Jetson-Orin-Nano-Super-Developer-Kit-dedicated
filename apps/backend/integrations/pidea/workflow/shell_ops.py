"""Ein Befehl im Workspace ausführen (analog zu TerminalService.executeCommand, vereinfacht)."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run_shell(
    command: str,
    *,
    cwd: Path,
    timeout_sec: float = 300.0,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Führt *einen* Shell-Befehl in ``cwd`` aus (``shell=True`` — nur mit vertrauenswürdigem Input).

    Returns:
        ``{"ok": bool, "returncode": int, "stdout": str, "stderr": str}``
    """
    root = cwd.resolve()
    if not root.is_dir():
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"not a directory: {root}",
        }

    try:
        p = subprocess.run(
            command,
            shell=True,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        logger.warning("run_shell timeout cwd=%s cmd=%s", root, command[:200])
        return {
            "ok": False,
            "returncode": -1,
            "stdout": e.stdout or "" if hasattr(e, "stdout") else "",
            "stderr": f"timeout after {timeout_sec}s",
        }
    except Exception as ex:
        logger.exception("run_shell failed")
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(ex),
        }

    return {
        "ok": p.returncode == 0,
        "returncode": p.returncode,
        "stdout": p.stdout or "",
        "stderr": p.stderr or "",
    }
