"""CDP-Session zur IDE (Playwright ``connect_over_cdp``) — gleicher Port wie ``--remote-debugging-port``.

Playwright ist **optional** (``requirements-pidea.txt``); Import erst bei ``connect()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.integrations.pidea.errors import (
    IDEUnreachableError,
    PlaywrightNotInstalledError,
    PideaDisabledError,
)

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page, Playwright

    from src.integrations.pidea.types import ConnectionConfig


def _import_sync_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise PlaywrightNotInstalledError(
            "Install Playwright: pip install -r requirements-pidea.txt && playwright install chromium"
        ) from e
    return sync_playwright


def _pick_page(browser: "Browser") -> "Page":
    for ctx in browser.contexts:
        for page in ctx.pages:
            if not page.is_closed():
                return page
    if browser.contexts:
        return browser.contexts[0].new_page()
    ctx = browser.new_context()
    return ctx.new_page()


class PideaConnection:
    """Verbindung zu einer laufenden Chromium/Electron-Instanz (z. B. Cursor) über HTTP-CDP."""

    def __init__(self, cfg: "ConnectionConfig | None" = None) -> None:
        if cfg is None:
            from src.infrastructure import operator_settings

            cfg = operator_settings.resolved_pidea_connection_config()
        self._cfg = cfg
        self._pw: Any = None
        self._browser: Any = None

    @property
    def connection_config(self) -> "ConnectionConfig":
        return self._cfg

    def connect(self, *, force: bool = False) -> "Page":
        """Verbinden und eine ``Page`` für DOM-Aktionen liefern.

        :param force: Wenn ``True``, Überspringen der „PIDEA aktiviert“-Prüfung (Debugging).
        """
        if not force:
            from src.infrastructure import operator_settings

            if not operator_settings.pidea_effective_enabled():
                raise PideaDisabledError(
                    "PIDEA is disabled (Admin → IDE Agent, or AGENT_PIDEA_ENABLED=1)"
                )
        sync_playwright = _import_sync_playwright()
        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.connect_over_cdp(self._cfg.cdp_http_url)
        except PlaywrightNotInstalledError:
            raise
        except Exception as e:
            self.close()
            raise IDEUnreachableError(str(e)) from e
        if not self._browser:
            raise IDEUnreachableError("browser handle missing after connect_over_cdp")
        page = _pick_page(self._browser)
        page.set_default_timeout(self._cfg.default_timeout_ms)
        return page

    def close(self) -> None:
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None

    def __enter__(self) -> PideaConnection:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def connection_from_env() -> PideaConnection:
    """``PideaConnection`` mit DB-Overrides / ``config`` (siehe ``resolved_pidea_connection_config``)."""
    return PideaConnection(None)
