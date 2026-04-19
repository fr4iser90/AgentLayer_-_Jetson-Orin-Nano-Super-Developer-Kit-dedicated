"""High-level UI actions against a Playwright Page (Cursor / Electron)."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class ActionRunner:
    def __init__(self, page: Any, default_timeout_ms: int = 30_000) -> None:
        self._page = page
        self._default_timeout_ms = default_timeout_ms
        self._page.set_default_timeout(default_timeout_ms)

    def click(self, css: str, *, first: bool = True) -> None:
        loc = self._page.locator(css)
        if first:
            loc.first.click()
        else:
            loc.click()

    def type_text(self, css: str, text: str, *, clear: bool = True) -> None:
        loc = self._page.locator(css).first
        loc.click()
        if clear:
            loc.fill("")
        loc.fill(text)

    def press(self, key: str) -> None:
        self._page.keyboard.press(key)

    def open_quick_open(self) -> None:
        """Ctrl+P / Cmd+P — quick open file."""
        self._page.keyboard.press("Control+p")

    def open_file(self, path: str, *, delay_s: float = 0.08) -> None:
        """Use quick open: palette, type path, Enter."""
        self.open_quick_open()
        time.sleep(delay_s)
        for ch in path:
            self._page.keyboard.type(ch, delay=int(delay_s * 1000))
        time.sleep(delay_s)
        self._page.keyboard.press("Enter")

    def open_folder(self, path: str) -> None:
        """Best-effort: rely on OS / Cursor command palette (user may need to bind)."""
        self._page.keyboard.press("Control+Shift+p")
        time.sleep(0.1)
        self._page.keyboard.type("Open Folder", delay=20)
        self._page.keyboard.press("Enter")
        time.sleep(0.2)
        for ch in path:
            self._page.keyboard.type(ch, delay=15)
        self._page.keyboard.press("Enter")

    def send_chat(self, input_css: str, message: str) -> None:
        """Focus composer input, fill, send with Enter."""
        self.type_text(input_css, message, clear=True)
        self.press("Enter")

    def read_chat(self, user_css: str, ai_css: str) -> tuple[list[str], list[str]]:
        """Return (user_lines, ai_lines) via locators (same semantics as :mod:`chat_reader`)."""
        from src.integrations.pidea.automation.chat_reader import read_chat_flat
        from src.integrations.pidea.types import SelectorBundle

        bundle = SelectorBundle(
            chat={"userMessages": user_css, "aiMessages": ai_css},
            raw={},
        )
        return read_chat_flat(self._page, bundle)

    def accept_changes(self, apply_button_css: str = ".anysphere-text-button") -> None:
        """Click primary apply / accept control (Composer code block apply, etc.)."""
        self.click(apply_button_css)
