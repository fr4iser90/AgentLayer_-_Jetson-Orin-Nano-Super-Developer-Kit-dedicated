"""PIDEA: DOM-Steuerung für Cursor / VSCode / Windsurf (Playwright + JSON-Selektoren).

Layout::

    pidea/
    ├── __init__.py
    ├── api_router.py       # FastAPI-Routen (/v1/experimental/status, /v1/ide-agent/message, …)
    ├── playwright_env.py   # Playwright-Importcheck + pip/install (nur für PIDEA-API)
    ├── ide_agent_message.py# Sync-Runner für Composer-Nachrichten
    ├── connection.py       # CDP-Session (connect_over_cdp)
    ├── chat.py             # DOM: Chat
    ├── selectors_loader.py # JSON laden, chatSelectors
    ├── types.py            # ConnectionConfig, ChatMessage, SelectorBundle
    ├── errors.py           # PideaError, …
    ├── automation/         # Runtime-CLI & IDE-Steuerung (Playwright)
    ├── domkit/             # DOM-Diagnostik, Selektor-Validierung / Repair
    ├── selectors/          # aktive JSONs (cursor|vscode|windsurf/<version>.json)
    ├── content-library/    # portierte Prompt-Bibliothek (Upstream-PIDEA; kein separates PIDEA-Projekt im Repo nötig)
    ├── workflows_data/     # PIDEA task-workflows.json (+ task-create, analysis) — 1:1 aus PIDEA/backend/framework/workflows/
    ├── content_library_prompts.py  # liest content-library/prompts/ (Scheduler-Phasen)
    ├── pidea_workflow_json.py / pidea_workflow_executor.py  # JSON-Workflows wie WorkflowLoaderService
    ├── project_path_cdp.py # Workspace-Pfad aus IDE (page.evaluate, wie PIDEA CDPConnectionManager)
    ├── workflow/           # Git + Shell (Python-Port, kein Node)

Die App registriert nur ``app.include_router(pidea_router)`` in ``main.py`` — PIDEA-HTTP bleibt hier.

Laufzeit: Cursor mit ``--remote-debugging-port``; User-Daten typisch ``~/.pidea/…`` (``pidea-shell.nix``).
"""

from apps.backend.integrations.pidea.chat import PideaChat
from apps.backend.integrations.pidea.connection import PideaConnection, connection_from_env
from apps.backend.integrations.pidea.errors import (
    IDEUnreachableError,
    PideaDisabledError,
    PideaError,
    PideaTimeoutError,
    PlaywrightNotInstalledError,
    SelectorNotFoundError,
)
from apps.backend.integrations.pidea.selectors_loader import (
    list_available_versions,
    load_chat_selectors,
    load_raw,
    selector_json_path,
    selectors_root,
)
from apps.backend.integrations.pidea.types import ChatMessage, ConnectionConfig, SelectorBundle

__all__ = [
    "ChatMessage",
    "ConnectionConfig",
    "IDEUnreachableError",
    "PideaChat",
    "PideaConnection",
    "PideaDisabledError",
    "PideaError",
    "PideaTimeoutError",
    "PlaywrightNotInstalledError",
    "SelectorBundle",
    "SelectorNotFoundError",
    "connection_from_env",
    "list_available_versions",
    "load_chat_selectors",
    "load_raw",
    "selector_json_path",
    "selectors_root",
]
