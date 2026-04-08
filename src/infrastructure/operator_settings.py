"""Persisted operator preferences: external user headers, optional integration hints."""

from __future__ import annotations

import time
from typing import Any

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
                SELECT require_user_sub_header, user_sub_header_csv, tenant_id_header,
                       discord_application_id, integration_notes,
                       optional_connection_key
                FROM operator_settings WHERE id = 1
                """
            )
            row = cur.fetchone()
    if not row:
        return {
            "require_user_sub_header": False,
            "user_sub_header_csv": None,
            "tenant_id_header": None,
            "discord_application_id": None,
            "integration_notes": None,
            "optional_connection_key": None,
        }
    return {
        "require_user_sub_header": bool(row[0]),
        "user_sub_header_csv": row[1],
        "tenant_id_header": row[2],
        "discord_application_id": row[3],
        "integration_notes": row[4],
        "optional_connection_key": row[5],
    }


def _cached_row() -> dict[str, Any]:
    global _CACHE
    now = time.monotonic()
    if _CACHE is not None and (now - _CACHE[0]) < _TTL_SEC:
        return dict(_CACHE[1])
    row = _fetch_row()
    _CACHE = (now, row)
    return dict(row)


def effective_user_sub_headers() -> list[str]:
    r = _cached_row()
    csv = (r.get("user_sub_header_csv") or "").strip()
    if csv:
        return [x.strip() for x in csv.split(",") if x.strip()]
    return list(config.USER_SUB_HEADERS)


def effective_tenant_id_header() -> str:
    r = _cached_row()
    h = (r.get("tenant_id_header") or "").strip()
    if h:
        return h
    return config.TENANT_ID_HEADER


def require_user_sub_header() -> bool:
    return bool(_cached_row().get("require_user_sub_header"))


def stored_optional_connection_key() -> str | None:
    """Optional value for selected HTTP routes; None means no Authorization required there."""
    v = (_cached_row().get("optional_connection_key") or "").strip()
    return v if v else None


def public_dict() -> dict[str, Any]:
    r = _cached_row()
    return {
        "require_user_sub_header": r["require_user_sub_header"],
        "user_sub_header_csv": r["user_sub_header_csv"] or "",
        "user_sub_headers_effective": effective_user_sub_headers(),
        "tenant_id_header": r["tenant_id_header"] or "",
        "tenant_id_header_effective": effective_tenant_id_header(),
        "discord_application_id": r["discord_application_id"] or "",
        "integration_notes": r["integration_notes"] or "",
        "env_fallback_user_sub_headers": list(config.USER_SUB_HEADERS),
        "env_fallback_tenant_id_header": config.TENANT_ID_HEADER,
    }


class OperatorSettingsPayload(BaseModel):
    """Full replace on PUT (empty strings clear optional overrides)."""

    require_user_sub_header: bool = False
    user_sub_header_csv: str = Field(default="", max_length=2000)
    tenant_id_header: str = Field(default="", max_length=256)
    discord_application_id: str = Field(default="", max_length=128)
    integration_notes: str = Field(default="", max_length=8000)


def interface_hints_public() -> dict[str, Any]:
    r = _fetch_row()
    return {
        "optional_connection_key": r.get("optional_connection_key") or "",
        "discord_application_id": r.get("discord_application_id") or "",
    }


class InterfaceHintsPayload(BaseModel):
    """Optional HTTP connection key + Discord application ID. Empty key on save clears it."""

    optional_connection_key: str = Field(default="", max_length=8000)
    discord_application_id: str = Field(default="", max_length=128)


def apply_interface_hints(body: InterfaceHintsPayload) -> None:
    key_new = body.optional_connection_key.strip()
    key_v = key_new if key_new else None
    disc_v = body.discord_application_id.strip() or None

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE operator_settings SET
                  optional_connection_key = %s,
                  discord_application_id = %s,
                  updated_at = now()
                WHERE id = 1
                """,
                (key_v, disc_v),
            )
        conn.commit()
    _invalidate()


def apply_update(body: OperatorSettingsPayload) -> None:
    csv_v = body.user_sub_header_csv.strip() or None
    th_v = body.tenant_id_header.strip() or None
    disc_v = body.discord_application_id.strip() or None
    notes_v = body.integration_notes.strip() or None

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO operator_settings (
                  id, require_user_sub_header, user_sub_header_csv, tenant_id_header,
                  discord_application_id, integration_notes, updated_at
                ) VALUES (1, %s, %s, %s, %s, %s, now())
                ON CONFLICT (id) DO UPDATE SET
                  require_user_sub_header = EXCLUDED.require_user_sub_header,
                  user_sub_header_csv = EXCLUDED.user_sub_header_csv,
                  tenant_id_header = EXCLUDED.tenant_id_header,
                  discord_application_id = EXCLUDED.discord_application_id,
                  integration_notes = EXCLUDED.integration_notes,
                  updated_at = now()
                """,
                (body.require_user_sub_header, csv_v, th_v, disc_v, notes_v),
            )
        conn.commit()
    _invalidate()
