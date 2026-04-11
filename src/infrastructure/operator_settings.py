"""Persisted operator preferences: integrations, optional connection key, agent execution class."""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.core.config import config
from src.infrastructure.db import db

_CACHE: tuple[float, dict[str, Any]] | None = None
_TTL_SEC = 2.0


def _invalidate() -> None:
    global _CACHE
    _CACHE = None


def _fetch_row() -> dict[str, Any]:
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT discord_application_id, integration_notes,
                       optional_connection_key, agent_mode
                FROM operator_settings WHERE id = 1
                """
            )
            row = cur.fetchone()
    if not row:
        return {
            "discord_application_id": None,
            "integration_notes": None,
            "optional_connection_key": None,
            "agent_mode": None,
        }
    return {
        "discord_application_id": row[0],
        "integration_notes": row[1],
        "optional_connection_key": row[2],
        "agent_mode": row[3],
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
    }


class OperatorSettingsPayload(BaseModel):
    """Full replace on PUT (empty strings clear optional fields where applicable)."""

    discord_application_id: str = Field(default="", max_length=128)
    integration_notes: str = Field(default="", max_length=8000)


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
