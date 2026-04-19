"""Read composer chat lines using a selector bundle (same semantics as ``PideaChat``)."""

from __future__ import annotations

from typing import Any

from apps.backend.integrations.pidea.domkit.selector_validator import validate_selector_on_page
from apps.backend.integrations.pidea.types import ChatMessage, SelectorBundle


def _lines(page: Any, css: str) -> list[str]:
    loc = page.locator(css)
    n = loc.count()
    out: list[str] = []
    for i in range(n):
        try:
            t = loc.nth(i).inner_text().strip()
            if t:
                out.append(t)
        except Exception:
            continue
    return out


def read_chat_flat(page: Any, bundle: SelectorBundle) -> tuple[list[str], list[str]]:
    """Return (user_lines, assistant_lines) from DOM."""
    chat = bundle.chat
    u = _lines(page, chat["userMessages"]) if chat.get("userMessages") else []
    a = _lines(page, chat["aiMessages"]) if chat.get("aiMessages") else []
    return u, a


def read_chat_messages(page: Any, bundle: SelectorBundle) -> list[ChatMessage]:
    """Interleave is ambiguous without order; return user then assistant lists as separate blocks."""
    u, a = read_chat_flat(page, bundle)
    msgs: list[ChatMessage] = []
    for t in u:
        msgs.append(ChatMessage(role="user", text=t))
    for t in a:
        msgs.append(ChatMessage(role="assistant", text=t))
    return msgs


def validate_chat_selectors(page: Any, bundle: SelectorBundle) -> dict[str, Any]:
    """Quick health dict for chat keys."""
    out: dict[str, Any] = {}
    for key in ("userMessages", "aiMessages", "input"):
        if key not in bundle.chat:
            continue
        vr = validate_selector_on_page(page, key, bundle.chat[key])
        out[key] = {
            "count": vr.count,
            "visible": vr.visible_count,
            "sample": vr.first_text_sample,
            "error": vr.error,
        }
    return out
