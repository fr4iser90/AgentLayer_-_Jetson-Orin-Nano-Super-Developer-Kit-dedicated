"""Compose common navigation flows using :class:`ActionRunner`."""

from __future__ import annotations

from apps.backend.integrations.pidea.automation.action_runner import ActionRunner


class UINavigator:
    def __init__(self, runner: ActionRunner) -> None:
        self._r = runner

    def quick_open_file(self, path: str) -> None:
        self._r.open_file(path)

    def command_palette(self, command_prefix: str) -> None:
        self._r._page.keyboard.press("Control+Shift+p")
        self._r._page.keyboard.type(command_prefix, delay=25)
        self._r._page.keyboard.press("Enter")
