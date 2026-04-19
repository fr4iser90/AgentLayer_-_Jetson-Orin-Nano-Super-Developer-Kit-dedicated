"""Best-effort workspace / active-editor hints from DOM (fragile across versions)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_ACTIVE_EDITOR_JS = """
() => {
  const ed = document.querySelector(".monaco-editor");
  const tab = document.querySelector(".tab.active, .tab.active-modified");
  const label = tab && tab.querySelector(".label-name, .tab-label");
  return {
    hasMonaco: !!ed,
    tabTitle: label ? (label.textContent || "").trim() : null,
  };
}
"""


def read_workspace_hints(page: Any) -> dict[str, Any]:
    try:
        return page.evaluate(_ACTIVE_EDITOR_JS)
    except Exception as e:
        logger.debug("workspace hints: %s", e)
        return {"error": str(e)}
