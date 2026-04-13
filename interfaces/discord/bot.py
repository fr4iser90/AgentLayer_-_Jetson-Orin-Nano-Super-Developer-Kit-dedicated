"""
Discord ↔ AgentLayer bridge: text channel messages → POST /v1/chat/completions → reply in Discord.

Run (from this directory):
  pip install -r requirements.txt
  export DISCORD_TOKEN=... AGENT_BEARER_TOKEN=...  # see .env.example
  python bot.py

Requires Discord privileged intent **Message Content Intent** enabled for your application.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import discord
import httpx

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("discord_bridge")


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _chunk_text(text: str, limit: int = 1900) -> list[str]:
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


def _user_linked_in_db(discord_user_id: str) -> bool:
    dsn = _env("DATABASE_URL")
    if not dsn:
        return True
    try:
        import psycopg
    except ImportError:
        logger.warning(
            "DATABASE_URL is set but psycopg is not installed; install psycopg or unset DATABASE_URL."
        )
        return True
    tenant_id = int(_env("AGENT_TENANT_ID", "1") or "1")
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM users
                    WHERE tenant_id = %s AND discord_user_id = %s
                    """,
                    (tenant_id, discord_user_id),
                )
                return cur.fetchone() is not None
    except Exception:
        logger.exception("database link check failed")
        return False


class AgentDiscordClient(discord.Client):
    def __init__(self, *, intents: discord.Intents) -> None:
        super().__init__(intents=intents)
        self._base = _env("AGENT_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
        self._prefix = _env("DISCORD_TRIGGER_PREFIX", "!agent ")
        self._bearer = _env("AGENT_BEARER_TOKEN")
        self._model = _env("AGENT_CHAT_MODEL", "nemotron-3-nano:4b")
        self._timeout = float(_env("AGENT_HTTP_TIMEOUT_SEC", "180") or "180")

    async def on_ready(self) -> None:
        assert self.user is not None
        logger.info("Discord logged in as %s (%s)", self.user.name, self.user.id)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not self._prefix or not message.content.startswith(self._prefix):
            return
        prompt = message.content[len(self._prefix) :].strip()
        if not prompt:
            await message.reply(
                f"Write your question after `{self._prefix.strip()}`, e.g. `{self._prefix.strip()} What is 2+2?`"
            )
            return
        author_id = str(message.author.id)
        if not _user_linked_in_db(author_id):
            await message.reply(
                "Your Discord account is not linked in AgentLayer. "
                "Sign in to the app → **Settings → Connections** → paste your numeric Discord user ID → Save."
            )
            return
        if not self._bearer:
            await message.reply("Server misconfiguration: AGENT_BEARER_TOKEN is missing for this bot.")
            return

        url = f"{self._base}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self._bearer}",
            "Content-Type": "application/json",
        }

        async with message.channel.typing():
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    r = await client.post(url, json=payload, headers=headers)
                    data = r.json()
                if r.status_code >= 400:
                    detail = data.get("detail") if isinstance(data, dict) else str(data)
                    await message.reply(f"HTTP {r.status_code}: {detail!s:.1500}")
                    return
                text = _extract_reply(data if isinstance(data, dict) else {})
            except httpx.TimeoutException:
                await message.reply("AgentLayer request timed out. Try a shorter question or raise AGENT_HTTP_TIMEOUT_SEC.")
                return
            except Exception as e:
                logger.exception("chat completion request failed")
                await message.reply(f"Request failed: {e!s:.500}")
                return

        parts = _chunk_text(text)
        await message.reply(parts[0])
        for part in parts[1:]:
            await message.channel.send(part)


def main() -> None:
    token = _env("DISCORD_TOKEN")
    if not token:
        logger.error("Set DISCORD_TOKEN (see interfaces/discord/.env.example)")
        sys.exit(1)
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    client = AgentDiscordClient(intents=intents)
    client.run(token)


if __name__ == "__main__":
    main()
