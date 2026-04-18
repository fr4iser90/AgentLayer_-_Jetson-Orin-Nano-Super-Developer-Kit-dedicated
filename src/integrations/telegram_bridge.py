"""
In-process Telegram gateway: daemon thread inside the same process as Uvicorn.

Configuration from ``operator_settings`` (Admin → Interfaces). Text messages matching the
prefix are handled only for Telegram user ids linked in ``users.telegram_user_id``; chat runs
via :func:`src.domain.agent.chat_completion` in-process. Same identity semantics as Discord.

**Groups:** With BotFather ``/setprivacy`` → *Disable*, the bot sees all messages (like Discord
channels). Otherwise only commands and mentions are delivered to the bot.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from src.core.config import config
from src.domain.agent import chat_completion
from src.domain.identity import reset_identity, set_identity
from src.infrastructure.db import db

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None
_started = False
_last_idle_log_m: float = 0.0


@dataclass
class _BridgeCfg:
    token: str
    model: str
    prefix: str


def _chunk_text(text: str, limit: int = 4000) -> list[str]:
    t = (text or "").strip() or "(empty reply)"
    out: list[str] = []
    while t:
        out.append(t[:limit])
        t = t[limit:]
    return out


def _extract_reply(data: dict[str, Any]) -> str:
    err = data.get("error") or data.get("detail")
    if isinstance(err, dict):
        err = err.get("message") or str(err)
    if err and not data.get("choices"):
        return f"AgentLayer error: {err}"
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return f"Unexpected response: {data!r:.2000}"
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    return f"(no text in response: {data!r:.1500})"


def _normalize_bot_token(raw: str) -> str:
    s = (raw or "").strip()
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()
    return "".join(s.split())


def _load_bridge_cfg_with_reason() -> tuple[_BridgeCfg | None, str]:
    try:
        with db.pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT telegram_bot_enabled, telegram_bot_token,
                           telegram_trigger_prefix, telegram_chat_model
                    FROM operator_settings WHERE id = 1
                    """
                )
                row = cur.fetchone()
    except Exception:
        logger.exception("telegram_bridge: could not read operator_settings (migrations applied?)")
        return None, "database error (see log above)"
    if not row:
        return None, "no operator_settings row for id=1"
    enabled, ttoken, trigger, cmodel = row
    if not enabled:
        return None, "telegram_bot_enabled is false (Admin → Interfaces → Telegram)"
    tok = _normalize_bot_token(str(ttoken) if ttoken is not None else "")
    if not tok:
        return None, "telegram_bot_token is empty (paste token in Admin → Interfaces → Telegram)"
    if trigger is None:
        prefix = "!agent "
    else:
        prefix = str(trigger).strip()
    if prefix and not prefix.endswith(" "):
        prefix = prefix + " "
    model_raw = (str(cmodel).strip() if cmodel is not None else "") or ""
    model = model_raw or getattr(config, "OLLAMA_DEFAULT_MODEL", "llama3.2") or "llama3.2"
    return _BridgeCfg(token=tok, model=model, prefix=prefix), ""


async def _run_polling_session(cfg: _BridgeCfg) -> None:
    from telegram.constants import ChatAction
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

    async def cmd_start(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg:
            await msg.reply_text(
                "AgentLayer: link your numeric Telegram user id in the web app "
                "(Settings → Connections), then send text with the configured prefix "
                "(or any message if prefix is empty)."
            )

    async def on_text(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        user = update.effective_user
        if not msg or not user or user.is_bot or not (msg.text or "").strip():
            return
        text = (msg.text or "").strip()
        if cfg.prefix:
            if not text.startswith(cfg.prefix):
                return
            prompt = text[len(cfg.prefix) :].strip()
        else:
            prompt = text
        if not prompt:
            if cfg.prefix:
                await msg.reply_text(
                    f"Add your question after `{cfg.prefix.strip()}`, e.g. `{cfg.prefix.strip()}What is 2+2?`"
                )
            return
        author_id = str(user.id)
        linked = db.user_id_tenant_for_telegram_global(author_id)
        if linked is None:
            await msg.reply_text(
                "Your Telegram account is not linked in AgentLayer (or the link is ambiguous). "
                "Open the web app → Settings → Connections → save your numeric Telegram user id."
            )
            return
        user_id, tenant_id = linked
        logger.info(
            "telegram_bridge: chat request (telegram_user_id=%s, agentlayer_user=%s, model=%s)",
            author_id,
            user_id,
            cfg.model,
        )
        work: dict[str, Any] = {
            "model": cfg.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        role = db.user_role(user_id).lower()
        bearer_role = role if role in ("user", "admin") else None
        id_token = set_identity(tenant_id, user_id)
        chat = msg.chat
        try:
            await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
            try:
                result = await chat_completion(work, bearer_user_role=bearer_role)
                reply_text = _extract_reply(result if isinstance(result, dict) else {})
            except ValueError as e:
                await msg.reply_text(f"AgentLayer: {e!s:.1500}")
                return
            except Exception as e:
                logger.exception("telegram_bridge: chat completion failed")
                await msg.reply_text(f"Request failed: {e!s:.500}")
                return
            parts = _chunk_text(reply_text)
            await msg.reply_text(parts[0])
            for part in parts[1:]:
                await context.bot.send_message(chat_id=chat.id, text=part)
        finally:
            reset_identity(id_token)

    application = (
        Application.builder()
        .token(cfg.token)
        .concurrent_updates(True)
        .build()
    )
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,
    )
    try:
        while not _stop.is_set():
            await asyncio.sleep(0.4)
    finally:
        try:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
        except Exception:
            logger.debug("telegram_bridge: shutdown", exc_info=True)


def _async_worker_session(cfg: _BridgeCfg) -> None:
    from telegram.error import InvalidToken

    try:
        asyncio.run(_run_polling_session(cfg))
    except InvalidToken:
        logger.warning(
            "telegram_bridge: Telegram rejected the bot token (401 / invalid). "
            "Paste the token from @BotFather (format `123456:ABC...`). Retrying in 120s."
        )
        time.sleep(120)
    except Exception:
        logger.exception("telegram_bridge: session crashed")
        time.sleep(4)


def _worker() -> None:
    global _last_idle_log_m
    while not _stop.is_set():
        cfg, idle_reason = _load_bridge_cfg_with_reason()
        if cfg is None:
            now = time.monotonic()
            if now - _last_idle_log_m >= 60.0:
                logger.warning(
                    "telegram_bridge: not connecting to Telegram — %s",
                    idle_reason,
                )
                _last_idle_log_m = now
            time.sleep(12)
            continue
        _last_idle_log_m = 0.0
        logger.info(
            "telegram_bridge: connecting to Telegram (message prefix=%r, model=%s)",
            cfg.prefix,
            cfg.model,
        )
        _async_worker_session(cfg)


def start_background() -> None:
    global _started, _thread
    if _started:
        return
    _started = True
    _thread = threading.Thread(target=_worker, name="telegram-bridge", daemon=True)
    _thread.start()
    logger.info("telegram_bridge: background worker started")


def stop_background() -> None:
    _stop.set()
    logger.info("telegram_bridge: stop requested (polling may exit on next wake)")
