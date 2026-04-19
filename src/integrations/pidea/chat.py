"""DOM-gestützter Chat: neuer Chat, senden, User-/AI-Zeilen lesen (Selectors aus JSON)."""

from __future__ import annotations

from typing import Any

from src.integrations.pidea.errors import PideaTimeoutError, SelectorNotFoundError
from src.integrations.pidea.selectors_loader import chat_selector
from src.integrations.pidea.types import ChatMessage, SelectorBundle

# Reihenfolge: typische Send-Controls in Cursor (erst sichtbares gewinnt)
_SEND_KEYS = (
    "codiconSend",
    "chatExecuteToolbar",
    "monacoActionBar",
    "actionLabelSend",
    "buttonSend",
    "buttonTitleSend",
    "sendButtonTestId",
    "sendButtonClass",
)


class PideaChat:
    def __init__(
        self,
        page: Any,
        bundle: SelectorBundle,
        *,
        default_timeout_ms: int = 30_000,
    ) -> None:
        self._page = page
        self._bundle = bundle
        self._default_timeout_ms = default_timeout_ms
        self._page.set_default_timeout(default_timeout_ms)

    def wait_input_ready(self, timeout_ms: int | None = None) -> None:
        sel = chat_selector(self._bundle, "isInputReady")
        loc = self._page.locator(sel).first
        try:
            loc.wait_for(
                state="visible",
                timeout=timeout_ms if timeout_ms is not None else self._default_timeout_ms,
            )
        except Exception as e:
            raise PideaTimeoutError(f"input not ready: {e}") from e

    def new_chat(self) -> None:
        sel = chat_selector(self._bundle, "newChatButton")
        self._page.locator(sel).first.click()

    def send_message(self, text: str) -> None:
        inp = chat_selector(self._bundle, "input")
        loc = self._page.locator(inp).first
        loc.click()
        loc.fill(text)
        self._click_send()

    def _click_send(self) -> None:
        for key in _SEND_KEYS:
            if key not in self._bundle.chat:
                continue
            sel = self._bundle.chat[key]
            loc = self._page.locator(sel).first
            try:
                if loc.is_visible():
                    loc.click()
                    return
            except Exception:
                continue
        raise SelectorNotFoundError(
            "send",
            "no visible send control matched (tried codiconSend, buttonSend, …)",
        )

    def _lines_for(self, key: str) -> list[str]:
        sel = chat_selector(self._bundle, key)
        loc = self._page.locator(sel)
        n = loc.count()
        out: list[str] = []
        for i in range(n):
            t = loc.nth(i).inner_text().strip()
            if t:
                out.append(t)
        return out

    def list_user_messages(self) -> list[str]:
        return self._lines_for("userMessages")

    def list_ai_messages(self) -> list[str]:
        return self._lines_for("aiMessages")

    def list_messages_flat(self) -> list[ChatMessage]:
        """User- und AI-Zeilen getrennt; Reihenfolge im Composer geht dabei verloren."""
        return [
            *[ChatMessage(role="user", text=t) for t in self.list_user_messages()],
            *[ChatMessage(role="assistant", text=t) for t in self.list_ai_messages()],
        ]
