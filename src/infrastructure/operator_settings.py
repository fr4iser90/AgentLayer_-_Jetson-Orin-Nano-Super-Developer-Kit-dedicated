"""Persisted operator preferences: integrations, optional connection key, agent execution class."""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.core.config import config
from src.infrastructure.db import db

_CACHE: tuple[float, dict[str, Any]] | None = None
_TTL_SEC = 2.0


def _invalidate() -> None:
    global _CACHE
    _CACHE = None


def _fetch_row() -> dict[str, Any]:
    empty = {
        "discord_application_id": None,
        "integration_notes": None,
        "optional_connection_key": None,
        "agent_mode": None,
        "discord_bot_enabled": False,
        "discord_bot_token": None,
        "discord_bot_agent_bearer": None,
        "discord_trigger_prefix": "!agent ",
        "discord_chat_model": None,
    }
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT discord_application_id, integration_notes,
                       optional_connection_key, agent_mode,
                       discord_bot_enabled, discord_bot_token, discord_bot_agent_bearer,
                       discord_trigger_prefix, discord_chat_model
                FROM operator_settings WHERE id = 1
                """
            )
            row = cur.fetchone()
    if not row:
        return dict(empty)
    return {
        "discord_application_id": row[0],
        "integration_notes": row[1],
        "optional_connection_key": row[2],
        "agent_mode": row[3],
        "discord_bot_enabled": bool(row[4]) if row[4] is not None else False,
        "discord_bot_token": row[5],
        "discord_bot_agent_bearer": row[6],
        "discord_trigger_prefix": (str(row[7]).strip() if row[7] is not None else "") or "!agent ",
        "discord_chat_model": row[8],
    }


def _cached_row() -> dict[str, Any]:
    global _CACHE
    now = time.monotonic()
    if _CACHE is not None and (now - _CACHE[0]) < _TTL_SEC:
        return dict(_CACHE[1])
    row = _fetch_row()
    _CACHE = (now, row)
    return dict(row)


def resolved_agent_mode() -> Literal["sandbox", "host"]:
    """DB ``agent_mode`` wins when set; else :envvar:`AGENT_MODE` (default ``sandbox``)."""
    r = _cached_row()
    v = r.get("agent_mode")
    if isinstance(v, str) and v.strip().lower() in ("sandbox", "host"):
        return v.strip().lower()  # type: ignore[return-value]
    em = getattr(config, "AGENT_MODE", "sandbox")
    if isinstance(em, str) and em.strip().lower() in ("sandbox", "host"):
        return em.strip().lower()  # type: ignore[return-value]
    return "sandbox"


def stored_optional_connection_key() -> str | None:
    """Optional value for selected HTTP routes; None means no Authorization required there."""
    v = (_cached_row().get("optional_connection_key") or "").strip()
    return v if v else None


def public_dict() -> dict[str, Any]:
    r = _cached_row()
    dtok = (r.get("discord_bot_token") or "").strip()
    return {
        "identity_policy": (
            "User and tenant are resolved only from Authorization: Bearer (JWT or API key); "
            "tenant is users.tenant_id. No operator-configured identity headers."
        ),
        "discord_application_id": r.get("discord_application_id") or "",
        "integration_notes": r.get("integration_notes") or "",
        "agent_mode": (r.get("agent_mode") or "") if isinstance(r.get("agent_mode"), str) else "",
        "agent_mode_effective": resolved_agent_mode(),
        "agent_mode_env": getattr(config, "AGENT_MODE", "sandbox"),
        "discord_bot_enabled": bool(r.get("discord_bot_enabled")),
        "discord_bot_token_configured": bool(dtok),
        "discord_trigger_prefix": (r.get("discord_trigger_prefix") or "!agent ")[:64],
        "discord_chat_model": (str(r.get("discord_chat_model") or "").strip())[:256],
    }


class OperatorSettingsPayload(BaseModel):
    """Full replace on PUT (empty strings clear optional fields where applicable)."""

    discord_application_id: str = Field(default="", max_length=128)
    integration_notes: str = Field(default="", max_length=8000)


class OperatorSettingsPatch(BaseModel):
    """Partial update (PATCH). Omitted fields are left unchanged; JSON null clears secrets."""

    model_config = ConfigDict(extra="forbid")

    discord_application_id: str | None = Field(default=None, max_length=128)
    integration_notes: str | None = Field(default=None, max_length=8000)
    discord_bot_enabled: bool | None = None
    discord_bot_token: str | None = Field(default=None, max_length=256)
    discord_trigger_prefix: str | None = Field(default=None, max_length=64)
    discord_chat_model: str | None = Field(default=None, max_length=256)


def interface_hints_public() -> dict[str, Any]:
    r = _fetch_row()
    am = r.get("agent_mode")
    am_s = am.strip().lower() if isinstance(am, str) else ""
    return {
        "optional_connection_key": r.get("optional_connection_key") or "",
        "discord_application_id": r.get("discord_application_id") or "",
        "agent_mode": am_s if am_s in ("sandbox", "host") else "",
        "agent_mode_effective": resolved_agent_mode(),
        "agent_mode_env": getattr(config, "AGENT_MODE", "sandbox"),
    }


class InterfaceHintsPayload(BaseModel):
    """Optional HTTP connection key + Discord application ID + agent execution class."""

    optional_connection_key: str = Field(default="", max_length=8000)
    discord_application_id: str = Field(default="", max_length=128)
    agent_mode: str = Field(default="", max_length=16)


def apply_interface_hints(body: InterfaceHintsPayload) -> None:
    key_new = body.optional_connection_key.strip()
    key_v = key_new if key_new else None
    disc_v = body.discord_application_id.strip() or None
    raw_mode = body.agent_mode.strip().lower()
    mode_v: str | None = raw_mode if raw_mode in ("sandbox", "host") else None

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE operator_settings SET
                  optional_connection_key = %s,
                  discord_application_id = %s,
                  agent_mode = %s,
                  updated_at = now()
                WHERE id = 1
                """,
                (key_v, disc_v, mode_v),
            )
        conn.commit()
    _invalidate()


def apply_operator_settings_patch(body: OperatorSettingsPatch) -> None:
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return
    r = _fetch_row()
    if "discord_application_id" in patch:
        v = patch["discord_application_id"]
        r["discord_application_id"] = (v or "").strip() or None
    if "integration_notes" in patch:
        v = patch["integration_notes"]
        r["integration_notes"] = (v or "").strip() or None
    if "discord_bot_enabled" in patch:
        r["discord_bot_enabled"] = bool(patch["discord_bot_enabled"])
    if "discord_bot_token" in patch:
        v = patch["discord_bot_token"]
        if v is None:
            r["discord_bot_token"] = None
        else:
            s = str(v).strip()
            if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
                s = s[1:-1].strip()
            s = "".join(s.split())
            r["discord_bot_token"] = s or None
    if "discord_trigger_prefix" in patch:
        tp = (patch["discord_trigger_prefix"] or "").strip() or "!agent "
        if tp and not tp.endswith(" "):
            tp = tp + " "
        r["discord_trigger_prefix"] = tp[:64]
    if "discord_chat_model" in patch:
        v = patch["discord_chat_model"]
        r["discord_chat_model"] = None if v is None else (str(v).strip() or None)

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO operator_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
            cur.execute(
                """
                UPDATE operator_settings SET
                  discord_application_id = %s,
                  integration_notes = %s,
                  optional_connection_key = %s,
                  agent_mode = %s,
                  discord_bot_enabled = %s,
                  discord_bot_token = %s,
                  discord_bot_agent_bearer = %s,
                  discord_trigger_prefix = %s,
                  discord_chat_model = %s,
                  updated_at = now()
                WHERE id = 1
                """,
                (
                    r.get("discord_application_id"),
                    r.get("integration_notes"),
                    r.get("optional_connection_key"),
                    r.get("agent_mode"),
                    r.get("discord_bot_enabled"),
                    r.get("discord_bot_token"),
                    r.get("discord_bot_agent_bearer"),
                    r.get("discord_trigger_prefix") or "!agent ",
                    r.get("discord_chat_model"),
                ),
            )
        conn.commit()
    _invalidate()


def apply_update(body: OperatorSettingsPayload) -> None:
    disc_v = body.discord_application_id.strip() or None
    notes_v = body.integration_notes.strip() or None

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO operator_settings (id, discord_application_id, integration_notes, updated_at)
                VALUES (1, %s, %s, now())
                ON CONFLICT (id) DO UPDATE SET
                  discord_application_id = EXCLUDED.discord_application_id,
                  integration_notes = EXCLUDED.integration_notes,
                  updated_at = now()
                """,
                (disc_v, notes_v),
            )
        conn.commit()
    _invalidate()
