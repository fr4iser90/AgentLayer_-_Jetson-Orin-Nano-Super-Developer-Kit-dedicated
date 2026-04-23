"""CDP-Session zur IDE (Playwright ``connect_over_cdp``) — gleicher Port wie ``--remote-debugging-port``.

Playwright ist **optional** (``requirements-pidea.txt``); Import erst bei ``connect()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.backend.integrations.pidea.errors import (
    IDEUnreachableError,
    PlaywrightNotInstalledError,
    PideaDisabledError,
)

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page, Playwright

    from apps.backend.integrations.pidea.types import ConnectionConfig


def _import_sync_playwright():
    from apps.backend.integrations.pidea.playwright_env import ensure_playwright_pip_target_on_syspath

    ensure_playwright_pip_target_on_syspath()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise PlaywrightNotInstalledError(
            "Install Playwright: pip install -r requirements-pidea.txt && playwright install chromium"
        ) from e
    return sync_playwright


def _enrich_connect_error(cdp_http_url: str, exc: BaseException) -> str:
    """Hilfreiche Zusatzzeilen für typische Docker-/CDP-Fehler (UI zeigt ``detail``)."""
    base = str(exc)
    u = (cdp_http_url or "").lower()
    if "host.docker.internal" in u and "enotfound" in base.lower():
        return (
            f"{base}\n\n"
            "On Linux, Docker does not resolve host.docker.internal unless the container has "
            'extra_hosts: ["host.docker.internal:host-gateway"] (see compose.yaml in this repo). '
            "Recreate the agent-layer container after adding it. "
            "Alternatively set CDP to your host LAN IP, e.g. http://192.168.x.x:9222."
        )
    if "host.docker.internal" in u and (
        "econnrefused" in base.lower() or "connection refused" in base.lower()
    ):
        return (
            f"{base}\n\n"
            "Docker reached the host (often 172.17.0.1) but nothing accepted the port — usually the IDE debug "
            "server listens only on 127.0.0.1, not on the bridge/LAN. Try: (1) Admin → CDP URL = your PC’s LAN IP, "
            "e.g. http://192.168.x.x:9222 (Cursor with --remote-debugging-port=9222; firewall open). "
            "(2) Linux: run agent-layer with network_mode: host and use http://127.0.0.1:9222. "
            "(3) Host: expose the port on 0.0.0.0 (or socat) so Docker can connect."
        )
    if u.startswith("http://0.0.0.0") or u.startswith("http://localhost"):
        if "econnrefused" in base.lower() or "connection refused" in base.lower():
            return (
                f"{base}\n\n"
                "If the API runs inside Docker, 127.0.0.1 is the container, not your host. "
                "Use http://host.docker.internal:9222 (with extra_hosts on Linux; see compose.yaml) "
                "or your host LAN IP."
            )
    return base


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
            from apps.backend.infrastructure import operator_settings

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
            from apps.backend.infrastructure import operator_settings

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
            raise IDEUnreachableError(_enrich_connect_error(self._cfg.cdp_http_url, e)) from e
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
