"""Persisted operator preferences: integrations, agent execution class, LLM routing."""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.core import config as app_config
from src.core.config import config
from src.infrastructure.db import db

logger = logging.getLogger(__name__)

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
        "telegram_application_id": None,
        "telegram_bot_enabled": False,
        "telegram_bot_token": None,
        "telegram_bot_agent_bearer": None,
        "telegram_trigger_prefix": "!agent ",
        "telegram_chat_model": None,
        "workspace_upload_max_file_mb": None,
        "workspace_upload_allowed_mime": None,
        "llm_primary_backend": "ollama",
        "llm_external_base_url": None,
        "llm_external_api_key": None,
        "llm_external_model_default": None,
        "llm_external_model_vlm": None,
        "llm_external_model_agent": None,
        "llm_external_model_coding": None,
        "llm_smart_routing_enabled": False,
        "llm_router_ollama_model": "nemotron-3-nano:4b",
        "llm_router_local_confidence_min": 0.7,
        "llm_router_timeout_sec": 12.0,
        "llm_route_long_prompt_chars": 8000,
        "llm_route_short_local_max_chars": 220,
        "llm_route_many_code_fences": 3,
        "llm_route_many_messages": 14,
    }
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT discord_application_id, integration_notes,
                       optional_connection_key, agent_mode,
                       discord_bot_enabled, discord_bot_token, discord_bot_agent_bearer,
                       discord_trigger_prefix, discord_chat_model,
                       telegram_application_id, telegram_bot_enabled, telegram_bot_token,
                       telegram_bot_agent_bearer, telegram_trigger_prefix, telegram_chat_model,
                       workspace_upload_max_file_mb, workspace_upload_allowed_mime,
                       llm_primary_backend, llm_external_base_url, llm_external_api_key,
                       llm_external_model_default, llm_external_model_vlm,
                       llm_external_model_agent, llm_external_model_coding,
                       llm_smart_routing_enabled, llm_router_ollama_model,
                       llm_router_local_confidence_min, llm_router_timeout_sec,
                       llm_route_long_prompt_chars, llm_route_short_local_max_chars,
                       llm_route_many_code_fences, llm_route_many_messages
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
        "discord_trigger_prefix": (
            str(row[7]).strip()[:64] if row[7] is not None else "!agent "
        ),
        "discord_chat_model": row[8],
        "telegram_application_id": row[9],
        "telegram_bot_enabled": bool(row[10]) if row[10] is not None else False,
        "telegram_bot_token": row[11],
        "telegram_bot_agent_bearer": row[12],
        "telegram_trigger_prefix": (
            str(row[13]).strip()[:64] if row[13] is not None else "!agent "
        ),
        "telegram_chat_model": row[14],
        "workspace_upload_max_file_mb": row[15],
        "workspace_upload_allowed_mime": row[16],
        "llm_primary_backend": (str(row[17]).strip().lower() if row[17] is not None else "") or "ollama",
        "llm_external_base_url": row[18],
        "llm_external_api_key": row[19],
        "llm_external_model_default": row[20],
        "llm_external_model_vlm": row[21],
        "llm_external_model_agent": row[22],
        "llm_external_model_coding": row[23],
        "llm_smart_routing_enabled": bool(row[24]) if row[24] is not None else False,
        "llm_router_ollama_model": (str(row[25]).strip() if row[25] is not None else "") or "nemotron-3-nano:4b",
        "llm_router_local_confidence_min": float(row[26]) if row[26] is not None else 0.7,
        "llm_router_timeout_sec": float(row[27]) if row[27] is not None else 12.0,
        "llm_route_long_prompt_chars": int(row[28]) if row[28] is not None else 8000,
        "llm_route_short_local_max_chars": int(row[29]) if row[29] is not None else 220,
        "llm_route_many_code_fences": int(row[30]) if row[30] is not None else 3,
        "llm_route_many_messages": int(row[31]) if row[31] is not None else 14,
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


def effective_workspace_upload_max_bytes() -> int:
    """DB override (MB) when set; else ``WORKSPACE_UPLOAD_MAX_FILE_MB`` from env."""
    r = _cached_row()
    v = r.get("workspace_upload_max_file_mb")
    if v is not None:
        try:
            mb = int(v)
            if mb > 0:
                return mb * 1024 * 1024
        except (TypeError, ValueError):
            pass
    return app_config.WORKSPACE_UPLOAD_MAX_FILE_MB * 1024 * 1024


def resolved_primary_llm_backend() -> Literal["ollama", "external"]:
    r = _cached_row()
    v = (r.get("llm_primary_backend") or "ollama").strip().lower()
    return "external" if v == "external" else "ollama"


def smart_llm_routing_enabled() -> bool:
    return bool(_cached_row().get("llm_smart_routing_enabled"))


def _bound_int(v: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _bound_float(v: Any, default: float, lo: float, hi: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, x))


def smart_routing_params() -> dict[str, Any]:
    r = _cached_row()
    return {
        "router_model": (str(r.get("llm_router_ollama_model") or "").strip() or "nemotron-3-nano:4b"),
        "local_confidence_min": _bound_float(r.get("llm_router_local_confidence_min"), 0.7, 0.0, 1.0),
        "router_timeout_sec": _bound_float(r.get("llm_router_timeout_sec"), 12.0, 1.0, 120.0),
        "long_prompt_chars": _bound_int(r.get("llm_route_long_prompt_chars"), 8000, 100, 500_000),
        "short_local_max_chars": _bound_int(r.get("llm_route_short_local_max_chars"), 220, 1, 50_000),
        "many_code_fences": _bound_int(r.get("llm_route_many_code_fences"), 3, 1, 100),
        "many_messages": _bound_int(r.get("llm_route_many_messages"), 14, 1, 500),
    }


def _strip_opt(s: Any) -> str | None:
    if s is None:
        return None
    t = str(s).strip()
    return t or None


def normalize_external_llm_base_url(raw: str | None) -> str:
    """
    Clean operator-stored URL: trim quotes and accidental path suffixes so we do not
    build ``…/v1/chat/completions/v1/chat/completions``.

    Does **not** validate host; see :func:`external_chat_completions_url` for path rules.
    """
    if not raw:
        return ""
    s = str(raw).strip().strip("'\"")
    s = s.rstrip("/")
    low = s.lower()
    for suf in (
        "/v1/chat/completions",
        "/chat/completions",
        "/v1/models",
        "/models",
    ):
        if low.endswith(suf):
            s = s[: -len(suf)].rstrip("/")
            low = s.lower()
    return s


def external_api_headers(base_url: str, api_key: str) -> dict[str, str]:
    h: dict[str, str] = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "generativelanguage.googleapis.com" in base_url.lower():
        h["x-goog-api-key"] = api_key
    return h


def external_chat_completions_url(base_url: str) -> str:
    """
    ``POST`` target for OpenAI-compatible chat completions: ``{base}/v1/chat/completions``.

    Works for OpenAI (base ``https://api.openai.com``) and Gemini OpenAI-compat (base
    ``https://generativelanguage.googleapis.com/v1beta/openai`` →
    ``…/v1beta/openai/v1/chat/completions``). A missing ``v1`` segment under the OpenAI-compat base
    (``…/openai/chat/completions``) returns **404** from Google.
    """
    bu = normalize_external_llm_base_url(base_url) or base_url.rstrip("/")
    return f"{bu.rstrip('/')}/v1/chat/completions"


def external_models_list_url(base_url: str) -> str:
    """``GET`` for OpenAI-style model list (admin); Gemini OpenAI-compat uses ``…/openai/v1/models``."""
    bu = (normalize_external_llm_base_url(base_url) or base_url).rstrip("/")
    return f"{bu}/v1/models"


def resolve_external_llm_credentials_for_catalog(
    base_url_override: str | None,
    api_key_override: str | None,
) -> tuple[str, str]:
    """Host prefix and API key for admin model list."""
    r = _cached_row()
    if base_url_override is not None and str(base_url_override).strip():
        bu = normalize_external_llm_base_url(str(base_url_override).strip())
    else:
        bu = normalize_external_llm_base_url(_strip_opt(r.get("llm_external_base_url")))
    if api_key_override is not None and str(api_key_override).strip():
        key = str(api_key_override).strip()
    else:
        key = _strip_opt(r.get("llm_external_api_key")) or ""
    if not bu:
        raise ValueError("missing_base_url")
    if not key:
        raise ValueError("missing_api_key")
    return bu, key


def _external_model_for_profile(r: dict[str, Any], profile_key: str) -> str | None:
    def col(name: str) -> str | None:
        return _strip_opt(r.get(name))

    d = col("llm_external_model_default")
    if profile_key == "vlm":
        return col("llm_external_model_vlm") or d
    if profile_key == "agent":
        return col("llm_external_model_agent") or d
    if profile_key == "coding":
        return col("llm_external_model_coding") or d
    return d


def llm_chat_transport(
    model_from_resolution: str,
    profile_key: str,
    is_override: bool,
    *,
    backend_override: Literal["ollama", "external"] | None = None,
) -> tuple[str, dict[str, str], str, Literal["ollama", "external"]]:
    ollama_base = (getattr(config, "OLLAMA_BASE_URL", None) or "http://ollama:11434").strip().rstrip("/")
    ollama_url = f"{ollama_base}/v1/chat/completions"
    ollama_headers: dict[str, str] = {"Content-Type": "application/json"}

    primary: Literal["ollama", "external"] = (
        backend_override if backend_override is not None else resolved_primary_llm_backend()
    )

    if primary == "ollama":
        return ollama_url, ollama_headers, model_from_resolution, "ollama"

    r = _cached_row()
    base_url = normalize_external_llm_base_url(_strip_opt(r.get("llm_external_base_url")))
    key = _strip_opt(r.get("llm_external_api_key")) or ""

    pk = (profile_key or "default").strip().lower()
    if pk not in ("default", "vlm", "agent", "coding"):
        pk = "default"

    if is_override:
        raw = _strip_opt(model_from_resolution)
        # Ollama tags are ``name:tag``; OpenAI/Gemini model ids do not use that shape. Smart routing
        # may pick external while the session still has an Ollama override (e.g. Discord model) — never
        # forward those to external APIs.
        if raw and ":" in raw:
            logger.info(
                "llm: external backend but model override looks like an Ollama id (%r); using external profile model",
                raw,
            )
            ext_model = _external_model_for_profile(r, pk)
        else:
            ext_model = raw
    else:
        ext_model = _external_model_for_profile(r, pk)

    if not base_url or not key or not ext_model:
        logger.warning(
            "llm: primary=external but incomplete (url=%s key=%s model=%r); using Ollama",
            bool(base_url),
            bool(key),
            ext_model,
        )
        return ollama_url, ollama_headers, model_from_resolution, "ollama"

    chat_url = external_chat_completions_url(base_url)
    headers = external_api_headers(base_url, key)
    return chat_url, headers, ext_model, "external"


def _discord_trigger_prefix_public(r: dict[str, Any]) -> str:
    """DB value for API; empty string means *no prefix* (bridge uses whole message)."""
    v = r.get("discord_trigger_prefix")
    if v is None:
        return "!agent "
    return str(v)[:64]


def _discord_trigger_prefix_sql(r: dict[str, Any]) -> str:
    """Value persisted in ``UPDATE`` (empty string allowed)."""
    v = r.get("discord_trigger_prefix")
    if v is None:
        return "!agent "
    return str(v)[:64]


def _telegram_trigger_prefix_public(r: dict[str, Any]) -> str:
    v = r.get("telegram_trigger_prefix")
    if v is None:
        return "!agent "
    return str(v)[:64]


def _telegram_trigger_prefix_sql(r: dict[str, Any]) -> str:
    v = r.get("telegram_trigger_prefix")
    if v is None:
        return "!agent "
    return str(v)[:64]


def effective_workspace_upload_mime() -> frozenset[str]:
    """Comma allowlist from DB when set; else env ``AGENT_WORKSPACE_UPLOAD_ALLOWED_MIME``."""
    r = _cached_row()
    raw = r.get("workspace_upload_allowed_mime")
    if isinstance(raw, str) and raw.strip():
        return frozenset(x.strip().lower() for x in raw.split(",") if x.strip())
    return app_config.workspace_upload_env_allowed_mime()


def public_dict() -> dict[str, Any]:
    r = _cached_row()
    dtok = (r.get("discord_bot_token") or "").strip()
    ttok = (r.get("telegram_bot_token") or "").strip()
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
        "discord_trigger_prefix": _discord_trigger_prefix_public(r),
        "discord_chat_model": (str(r.get("discord_chat_model") or "").strip())[:256],
        "telegram_application_id": r.get("telegram_application_id") or "",
        "telegram_bot_enabled": bool(r.get("telegram_bot_enabled")),
        "telegram_bot_token_configured": bool(ttok),
        "telegram_trigger_prefix": _telegram_trigger_prefix_public(r),
        "telegram_chat_model": (str(r.get("telegram_chat_model") or "").strip())[:256],
        "workspace_upload_max_file_mb": r.get("workspace_upload_max_file_mb"),
        "workspace_upload_allowed_mime": (r.get("workspace_upload_allowed_mime") or "").strip(),
        "workspace_upload_effective_max_bytes": effective_workspace_upload_max_bytes(),
        "workspace_upload_effective_allowed_mime": sorted(effective_workspace_upload_mime()),
        "llm_primary_backend": resolved_primary_llm_backend(),
        "llm_external_base_url": (str(r.get("llm_external_base_url") or "").strip())[:512],
        "llm_external_api_key_configured": bool((r.get("llm_external_api_key") or "").strip()),
        "llm_external_model_default": (str(r.get("llm_external_model_default") or "").strip())[:256],
        "llm_external_model_vlm": (str(r.get("llm_external_model_vlm") or "").strip())[:256],
        "llm_external_model_agent": (str(r.get("llm_external_model_agent") or "").strip())[:256],
        "llm_external_model_coding": (str(r.get("llm_external_model_coding") or "").strip())[:256],
        "llm_smart_routing_enabled": bool(r.get("llm_smart_routing_enabled")),
        "llm_router_ollama_model": (str(r.get("llm_router_ollama_model") or "").strip())[:128],
        "llm_router_local_confidence_min": _bound_float(r.get("llm_router_local_confidence_min"), 0.7, 0.0, 1.0),
        "llm_router_timeout_sec": _bound_float(r.get("llm_router_timeout_sec"), 12.0, 1.0, 120.0),
        "llm_route_long_prompt_chars": _bound_int(r.get("llm_route_long_prompt_chars"), 8000, 100, 500_000),
        "llm_route_short_local_max_chars": _bound_int(r.get("llm_route_short_local_max_chars"), 220, 1, 50_000),
        "llm_route_many_code_fences": _bound_int(r.get("llm_route_many_code_fences"), 3, 1, 100),
        "llm_route_many_messages": _bound_int(r.get("llm_route_many_messages"), 14, 1, 500),
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
    telegram_bot_enabled: bool | None = None
    telegram_bot_token: str | None = Field(default=None, max_length=256)
    telegram_trigger_prefix: str | None = Field(default=None, max_length=64)
    telegram_chat_model: str | None = Field(default=None, max_length=256)
    workspace_upload_max_file_mb: int | None = None
    workspace_upload_allowed_mime: str | None = Field(default=None, max_length=2000)
    llm_primary_backend: str | None = Field(default=None, max_length=32)
    llm_external_base_url: str | None = Field(default=None, max_length=512)
    llm_external_api_key: str | None = Field(default=None, max_length=4096)
    llm_external_model_default: str | None = Field(default=None, max_length=256)
    llm_external_model_vlm: str | None = Field(default=None, max_length=256)
    llm_external_model_agent: str | None = Field(default=None, max_length=256)
    llm_external_model_coding: str | None = Field(default=None, max_length=256)
    llm_smart_routing_enabled: bool | None = None
    llm_router_ollama_model: str | None = Field(default=None, max_length=128)
    llm_router_local_confidence_min: float | None = Field(default=None, ge=0.0, le=1.0)
    llm_router_timeout_sec: float | None = Field(default=None, ge=1.0, le=120.0)
    llm_route_long_prompt_chars: int | None = Field(default=None, ge=100, le=500000)
    llm_route_short_local_max_chars: int | None = Field(default=None, ge=1, le=50000)
    llm_route_many_code_fences: int | None = Field(default=None, ge=1, le=100)
    llm_route_many_messages: int | None = Field(default=None, ge=1, le=500)


def interface_hints_public() -> dict[str, Any]:
    r = _fetch_row()
    am = r.get("agent_mode")
    am_s = am.strip().lower() if isinstance(am, str) else ""
    return {
        "discord_application_id": r.get("discord_application_id") or "",
        "telegram_application_id": r.get("telegram_application_id") or "",
        "agent_mode": am_s if am_s in ("sandbox", "host") else "",
        "agent_mode_effective": resolved_agent_mode(),
        "agent_mode_env": getattr(config, "AGENT_MODE", "sandbox"),
    }


class InterfaceHintsPayload(BaseModel):
    """Discord / Telegram application hints + agent execution class."""

    discord_application_id: str = Field(default="", max_length=128)
    telegram_application_id: str = Field(default="", max_length=128)
    agent_mode: str = Field(default="", max_length=16)


def apply_interface_hints(body: InterfaceHintsPayload) -> None:
    disc_v = body.discord_application_id.strip() or None
    tg_v = body.telegram_application_id.strip() or None
    raw_mode = body.agent_mode.strip().lower()
    mode_v: str | None = raw_mode if raw_mode in ("sandbox", "host") else None

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE operator_settings SET
                  optional_connection_key = NULL,
                  discord_application_id = %s,
                  telegram_application_id = %s,
                  agent_mode = %s,
                  updated_at = now()
                WHERE id = 1
                """,
                (disc_v, tg_v, mode_v),
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
        v = patch["discord_trigger_prefix"]
        if v is None:
            r["discord_trigger_prefix"] = "!agent "
        else:
            tp = str(v).strip()[:64]
            if tp and not tp.endswith(" "):
                tp = tp + " "
            r["discord_trigger_prefix"] = tp
    if "discord_chat_model" in patch:
        v = patch["discord_chat_model"]
        r["discord_chat_model"] = None if v is None else (str(v).strip() or None)
    if "telegram_bot_enabled" in patch:
        r["telegram_bot_enabled"] = bool(patch["telegram_bot_enabled"])
    if "telegram_bot_token" in patch:
        v = patch["telegram_bot_token"]
        if v is None:
            r["telegram_bot_token"] = None
        else:
            s = str(v).strip()
            if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
                s = s[1:-1].strip()
            s = "".join(s.split())
            r["telegram_bot_token"] = s or None
    if "telegram_trigger_prefix" in patch:
        v = patch["telegram_trigger_prefix"]
        if v is None:
            r["telegram_trigger_prefix"] = "!agent "
        else:
            tp = str(v).strip()[:64]
            if tp and not tp.endswith(" "):
                tp = tp + " "
            r["telegram_trigger_prefix"] = tp
    if "telegram_chat_model" in patch:
        v = patch["telegram_chat_model"]
        r["telegram_chat_model"] = None if v is None else (str(v).strip() or None)
    if "workspace_upload_max_file_mb" in patch:
        v = patch["workspace_upload_max_file_mb"]
        if v is None:
            r["workspace_upload_max_file_mb"] = None
        else:
            try:
                mb = int(v)
                r["workspace_upload_max_file_mb"] = mb if mb > 0 else None
            except (TypeError, ValueError):
                r["workspace_upload_max_file_mb"] = None
    if "workspace_upload_allowed_mime" in patch:
        v = patch["workspace_upload_allowed_mime"]
        if v is None:
            r["workspace_upload_allowed_mime"] = None
        else:
            s = str(v).strip()
            r["workspace_upload_allowed_mime"] = s or None
    if "llm_primary_backend" in patch:
        v = patch["llm_primary_backend"]
        if v is None:
            r["llm_primary_backend"] = "ollama"
        else:
            s = str(v).strip().lower()
            r["llm_primary_backend"] = "external" if s == "external" else "ollama"
    if "llm_external_base_url" in patch:
        v = patch["llm_external_base_url"]
        r["llm_external_base_url"] = None if v is None else (str(v).strip() or None)
    if "llm_external_api_key" in patch:
        v = patch["llm_external_api_key"]
        if v is None:
            r["llm_external_api_key"] = None
        else:
            s = str(v).strip()
            r["llm_external_api_key"] = s or None
    if "llm_external_model_default" in patch:
        v = patch["llm_external_model_default"]
        r["llm_external_model_default"] = None if v is None else (str(v).strip() or None)
    if "llm_external_model_vlm" in patch:
        v = patch["llm_external_model_vlm"]
        r["llm_external_model_vlm"] = None if v is None else (str(v).strip() or None)
    if "llm_external_model_agent" in patch:
        v = patch["llm_external_model_agent"]
        r["llm_external_model_agent"] = None if v is None else (str(v).strip() or None)
    if "llm_external_model_coding" in patch:
        v = patch["llm_external_model_coding"]
        r["llm_external_model_coding"] = None if v is None else (str(v).strip() or None)
    if "llm_smart_routing_enabled" in patch:
        r["llm_smart_routing_enabled"] = bool(patch["llm_smart_routing_enabled"])
    if "llm_router_ollama_model" in patch:
        v = patch["llm_router_ollama_model"]
        r["llm_router_ollama_model"] = (
            (str(v).strip()[:128] or "nemotron-3-nano:4b") if v is not None else "nemotron-3-nano:4b"
        )
    if "llm_router_local_confidence_min" in patch:
        v = patch["llm_router_local_confidence_min"]
        r["llm_router_local_confidence_min"] = _bound_float(v, 0.7, 0.0, 1.0) if v is not None else 0.7
    if "llm_router_timeout_sec" in patch:
        v = patch["llm_router_timeout_sec"]
        r["llm_router_timeout_sec"] = _bound_float(v, 12.0, 1.0, 120.0) if v is not None else 12.0
    if "llm_route_long_prompt_chars" in patch:
        v = patch["llm_route_long_prompt_chars"]
        r["llm_route_long_prompt_chars"] = _bound_int(v, 8000, 100, 500_000) if v is not None else 8000
    if "llm_route_short_local_max_chars" in patch:
        v = patch["llm_route_short_local_max_chars"]
        r["llm_route_short_local_max_chars"] = _bound_int(v, 220, 1, 50_000) if v is not None else 220
    if "llm_route_many_code_fences" in patch:
        v = patch["llm_route_many_code_fences"]
        r["llm_route_many_code_fences"] = _bound_int(v, 3, 1, 100) if v is not None else 3
    if "llm_route_many_messages" in patch:
        v = patch["llm_route_many_messages"]
        r["llm_route_many_messages"] = _bound_int(v, 14, 1, 500) if v is not None else 14

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
                  telegram_application_id = %s,
                  telegram_bot_enabled = %s,
                  telegram_bot_token = %s,
                  telegram_bot_agent_bearer = %s,
                  telegram_trigger_prefix = %s,
                  telegram_chat_model = %s,
                  workspace_upload_max_file_mb = %s,
                  workspace_upload_allowed_mime = %s,
                  llm_primary_backend = %s,
                  llm_external_base_url = %s,
                  llm_external_api_key = %s,
                  llm_external_model_default = %s,
                  llm_external_model_vlm = %s,
                  llm_external_model_agent = %s,
                  llm_external_model_coding = %s,
                  llm_smart_routing_enabled = %s,
                  llm_router_ollama_model = %s,
                  llm_router_local_confidence_min = %s,
                  llm_router_timeout_sec = %s,
                  llm_route_long_prompt_chars = %s,
                  llm_route_short_local_max_chars = %s,
                  llm_route_many_code_fences = %s,
                  llm_route_many_messages = %s,
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
                    _discord_trigger_prefix_sql(r),
                    r.get("discord_chat_model"),
                    r.get("telegram_application_id"),
                    r.get("telegram_bot_enabled"),
                    r.get("telegram_bot_token"),
                    r.get("telegram_bot_agent_bearer"),
                    _telegram_trigger_prefix_sql(r),
                    r.get("telegram_chat_model"),
                    r.get("workspace_upload_max_file_mb"),
                    r.get("workspace_upload_allowed_mime"),
                    r.get("llm_primary_backend") or "ollama",
                    r.get("llm_external_base_url"),
                    r.get("llm_external_api_key"),
                    r.get("llm_external_model_default"),
                    r.get("llm_external_model_vlm"),
                    r.get("llm_external_model_agent"),
                    r.get("llm_external_model_coding"),
                    bool(r.get("llm_smart_routing_enabled")),
                    (str(r.get("llm_router_ollama_model") or "").strip() or "nemotron-3-nano:4b")[:128],
                    _bound_float(r.get("llm_router_local_confidence_min"), 0.7, 0.0, 1.0),
                    _bound_float(r.get("llm_router_timeout_sec"), 12.0, 1.0, 120.0),
                    _bound_int(r.get("llm_route_long_prompt_chars"), 8000, 100, 500_000),
                    _bound_int(r.get("llm_route_short_local_max_chars"), 220, 1, 50_000),
                    _bound_int(r.get("llm_route_many_code_fences"), 3, 1, 100),
                    _bound_int(r.get("llm_route_many_messages"), 14, 1, 500),
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
