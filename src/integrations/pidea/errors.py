"""Fehler für die PIDEA DOM/CDP-Integration."""


class PideaError(Exception):
    """Basisklasse."""


class IDEUnreachableError(PideaError):
    """CDP nicht erreichbar oder Verbindung fehlgeschlagen."""


class SelectorNotFoundError(PideaError):
    """Selector-Key fehlt in der geladenen JSON oder Datei fehlt."""

    def __init__(self, key: str, message: str | None = None) -> None:
        self.key = key
        super().__init__(message or f"unknown selector key: {key!r}")


class PideaTimeoutError(PideaError):
    """Timeout beim Warten auf DOM/IDE."""


class NoPageError(PideaError):
    """Kein Browser-Tab / keine Page für Automation gefunden."""


class PideaDisabledError(PideaError):
    """PIDEA ist in Operator-Settings / per Env deaktiviert."""


class PlaywrightNotInstalledError(PideaError):
    """Optionales Paket ``playwright`` fehlt (siehe ``requirements-pidea.txt``)."""
