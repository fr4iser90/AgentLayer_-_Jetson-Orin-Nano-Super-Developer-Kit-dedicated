"""Sync runner for ``POST /v1/ide-agent/message`` (executed via ``asyncio.to_thread``)."""

from __future__ import annotations

import logging
import time
from typing import Any

from src.integrations.pidea.chat import PideaChat
from src.integrations.pidea.connection import PideaConnection
from src.integrations.pidea.selectors_loader import load_chat_selectors

logger = logging.getLogger(__name__)

_MAX_LOG_LINE = 800


def _trunc_for_log(text: str) -> str:
    t = text.replace("\r", "").replace("\n", "⏎")
    if len(t) > _MAX_LOG_LINE:
        return f"{t[:_MAX_LOG_LINE]}…({len(text)} chars)"
    return t


def _log_pidea_chat_snapshot(tag: str, user_lines: list[str], ai_lines: list[str]) -> None:
    """Loggt, was laut Selektoren im IDE-Chat gelesen wurde (nur Diagnose)."""
    logger.info(
        "pidea chat [%s] user_count=%d ai_count=%d",
        tag,
        len(user_lines),
        len(ai_lines),
    )
    for i, line in enumerate(user_lines):
        logger.info("pidea chat [%s] user[%d]: %s", tag, i, _trunc_for_log(line))
    for i, line in enumerate(ai_lines):
        logger.info("pidea chat [%s] ai[%d]: %s", tag, i, _trunc_for_log(line))


def run_ide_agent_snapshot_sync() -> dict[str, Any]:
    """Nur verbinden und aktuelle User-/AI-Zeilen aus dem Composer lesen (kein Senden)."""
    conn = PideaConnection(None)
    try:
        page = conn.connect()
        cfg = conn.connection_config
        bundle = load_chat_selectors(cfg.selector_ide, cfg.selector_version)
        chat = PideaChat(page, bundle)
        chat.wait_input_ready()
        user_msgs = chat.list_user_messages()
        ai_msgs = chat.list_ai_messages()
        _log_pidea_chat_snapshot("snapshot_only", user_msgs, ai_msgs)
        return {
            "ok": True,
            "user_messages": user_msgs,
            "ai_messages": ai_msgs,
            "selector_ide": cfg.selector_ide,
            "selector_version": cfg.selector_version,
        }
    finally:
        conn.close()


def _ai_list_changed(before: list[str], after: list[str]) -> bool:
    if len(after) > len(before):
        return True
    if not after and not before:
        return False
    if len(after) == len(before) and after and before:
        return after[-1] != before[-1]
    return after != before


def run_ide_agent_message_sync(
    message: str,
    *,
    new_chat: bool = False,
    reply_timeout_s: float = 120.0,
    poll_interval_s: float = 0.75,
) -> dict[str, Any]:
    conn = PideaConnection(None)
    try:
        page = conn.connect()
        cfg = conn.connection_config
        bundle = load_chat_selectors(cfg.selector_ide, cfg.selector_version)
        chat = PideaChat(page, bundle)
        chat.wait_input_ready()
        pre_ai = chat.list_ai_messages()
        _log_pidea_chat_snapshot("after_input_ready", chat.list_user_messages(), pre_ai)
        if new_chat:
            chat.new_chat()
            chat.wait_input_ready(timeout_ms=60_000)
            pre_ai = chat.list_ai_messages()
            _log_pidea_chat_snapshot("after_new_chat", chat.list_user_messages(), pre_ai)
        _log_pidea_chat_snapshot("before_send", chat.list_user_messages(), pre_ai)
        chat.send_message(message)
        timed_out = True
        deadline = time.monotonic() + reply_timeout_s
        while time.monotonic() < deadline:
            time.sleep(poll_interval_s)
            now = chat.list_ai_messages()
            if _ai_list_changed(pre_ai, now):
                timed_out = False
                _log_pidea_chat_snapshot("ai_list_changed", chat.list_user_messages(), now)
                break
        user_msgs = chat.list_user_messages()
        ai_msgs = chat.list_ai_messages()
        _log_pidea_chat_snapshot("final", user_msgs, ai_msgs)
        last_ai = ai_msgs[-1] if ai_msgs else ""
        return {
            "ok": True,
            "timed_out": timed_out,
            "user_messages": user_msgs,
            "ai_messages": ai_msgs,
            "last_ai": last_ai,
            "selector_ide": cfg.selector_ide,
            "selector_version": cfg.selector_version,
        }
    finally:
        conn.close()
