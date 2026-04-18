"""PIDEA: DOM-Steuerung für Cursor / VSCode / Windsurf (Playwright + JSON-Selektoren).

Layout::

    pidea/
    ├── __init__.py
    ├── connection.py       # CDP-Session (connect_over_cdp)
    ├── chat.py             # DOM: Chat
    ├── selectors_loader.py # JSON laden, chatSelectors
    ├── types.py            # ConnectionConfig, ChatMessage, SelectorBundle
    ├── errors.py           # PideaError, …
    ├── selectors/          # aktive JSONs (cursor|vscode|windsurf/<version>.json)
    └── reference/        # JS-Referenz aus PIDEA (Portierung), kein Runtime

Laufzeit: Cursor mit ``--remote-debugging-port``; User-Daten typisch ``~/.pidea/…`` (``pidea-shell.nix``).
"""

from src.integrations.pidea.chat import PideaChat
from src.integrations.pidea.connection import PideaConnection, connection_from_env
from src.integrations.pidea.errors import (
    IDEUnreachableError,
    PideaDisabledError,
    PideaError,
    PideaTimeoutError,
    PlaywrightNotInstalledError,
    SelectorNotFoundError,
)
from src.integrations.pidea.selectors_loader import (
    list_available_versions,
    load_chat_selectors,
    load_raw,
    selector_json_path,
    selectors_root,
)
from src.integrations.pidea.types import ChatMessage, ConnectionConfig, SelectorBundle

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
