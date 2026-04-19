"""
Port von PIDEA ``CDPConnectionManager.extractWorkspaceInfo``: Workspace-Pfad aus der IDE-Seite
(``page.evaluate`` → ``window.vscode.workspace…`` / Titel), dann lokale Prüfung.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Vereinfacht nach PIDEA backend/.../CDPConnectionManager.js extractWorkspaceInfo
_WORKSPACE_EVAL_JS = """
() => {
  const info = { workspacePath: null, workspaceName: null, extractionMethod: null };
  try {
    const pageTitle = document.title;
    if (pageTitle) {
      const titleMatch = pageTitle.match(/([^-]+)\\s*-\\s*(?:Cursor|VSCode|Windsurf)/);
      if (titleMatch) {
        info.workspaceName = titleMatch[1].trim();
        info.extractionMethod = "page_title";
      }
    }
  } catch (e) {}
  try {
    if (!info.workspacePath && window.vscode && window.vscode.workspace &&
        window.vscode.workspace.workspaceFolders && window.vscode.workspace.workspaceFolders.length) {
      const wf = window.vscode.workspace.workspaceFolders[0];
      if (wf && wf.uri && wf.uri.fsPath) {
        info.workspacePath = wf.uri.fsPath;
        info.workspaceName = wf.name || info.workspaceName;
        info.extractionMethod = "vscode_api";
      }
    }
  } catch (e) {}
  try {
    if (!info.workspacePath) {
      const els = document.querySelectorAll("[data-workspace], .workspace-name, .folder-name");
      for (const el of els) {
        const d = el.getAttribute("data-workspace") || el.getAttribute("title") || el.textContent || "";
        if (d && (d.includes("/") || d.includes("\\\\"))) {
          info.workspacePath = d.trim();
          info.extractionMethod = "dom_element";
          break;
        }
      }
    }
  } catch (e) {}
  return info;
}
"""


def _validate_local_dir(path_str: str) -> str | None:
    s = (path_str or "").strip()
    if not s or ".." in s:
        return None
    try:
        p = Path(s).expanduser().resolve()
    except OSError:
        return None
    if p.is_dir():
        return str(p)
    logger.debug("workspace_path_cdp: path not a directory or missing: %s", s)
    return None


def detect_workspace_path_from_ide_sync() -> str | None:
    """
    Verbindet per CDP (wie PIDEA), liest Workspace-Pfad aus der IDE-Seite, prüft lokal.

    Gibt ``None`` zurück bei PIDEA aus, fehlender Playwright-Verbindung oder wenn der
    erkannte Pfad auf **diesem** Rechner nicht existiert (z. B. Docker vs. Host-Pfad).
    """
    from apps.backend.integrations.pidea.connection import PideaConnection
    from apps.backend.integrations.pidea.errors import (
        IDEUnreachableError,
        PideaDisabledError,
        PlaywrightNotInstalledError,
    )

    conn = PideaConnection(None)
    try:
        page = conn.connect()
        raw: Any = page.evaluate(_WORKSPACE_EVAL_JS)
    except (PideaDisabledError, PlaywrightNotInstalledError, IDEUnreachableError) as e:
        logger.debug("workspace_path_cdp: connect/evaluate skipped: %s", e)
        return None
    except Exception:
        logger.exception("workspace_path_cdp: unexpected error during evaluate")
        return None
    finally:
        conn.close()

    if not isinstance(raw, dict):
        return None
    wp = raw.get("workspacePath")
    if isinstance(wp, str) and wp.strip():
        got = _validate_local_dir(wp)
        if got:
            logger.info(
                "workspace_path_cdp: detected via %s → %s",
                raw.get("extractionMethod"),
                got,
            )
            return got
        logger.debug(
            "workspace_path_cdp: IDE reported path not usable on this host: %s",
            wp[:200],
        )
        return None

    return None
