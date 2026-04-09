"""
Hybrid chat model resolution: profile defaults (VLM / agent / coding), optional client override.

See docs/WEBUI_CONTRACT.md (model routing) and env AGENT_MODEL_* / AGENT_ALLOW_MODEL_OVERRIDE.
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.config import config

logger = logging.getLogger(__name__)

# Profile ids (not Ollama model names). Open WebUI may send body ``model: "agent"`` so the
# server picks ``AGENT_MODEL_PROFILE_AGENT`` (delegated / hybrid routing).
_PROFILE_KEYS = frozenset({"default", "vlm", "agent", "coding"})


def messages_contain_image_parts(messages: list[dict[str, Any]]) -> bool:
    """True if any message content uses OpenAI-style multimodal image parts."""
    for m in messages:
        if not isinstance(m, dict):
            continue
        c = m.get("content")
        if not isinstance(c, list):
            continue
        for part in c:
            if not isinstance(part, dict):
                continue
            t = str(part.get("type") or "").strip().lower()
            if t in ("image_url", "image", "input_image"):
                return True
            if t == "file" and isinstance(part.get("file"), dict):
                return True
    return False


def _normalize_profile(raw: str | None) -> str:
    if not raw or not str(raw).strip():
        return "default"
    k = str(raw).strip().lower()
    return k if k in _PROFILE_KEYS else "default"


def _profile_token_from_body(body_model: Any) -> str | None:
    """If JSON ``model`` is a reserved profile token, return it; else None."""
    s = _strip_model(body_model)
    if not s:
        return None
    k = s.lower()
    return k if k in _PROFILE_KEYS else None


def _model_for_profile(profile: str) -> str:
    base = (config.OLLAMA_DEFAULT_MODEL or "").strip() or "nemotron-3-nano:4b"
    if profile == "vlm":
        v = (config.AGENT_MODEL_PROFILE_VLM or "").strip()
        return v or base
    if profile == "agent":
        v = (config.AGENT_MODEL_PROFILE_AGENT or "").strip()
        return v or base
    if profile == "coding":
        v = (config.AGENT_MODEL_PROFILE_CODING or "").strip()
        return v or base
    v = (config.AGENT_MODEL_PROFILE_DEFAULT or "").strip()
    return v or base


def _strip_model(s: Any) -> str | None:
    if s is None:
        return None
    if isinstance(s, str):
        t = s.strip()
        return t or None
    t = str(s).strip()
    return t or None


def _override_allowed(bearer_user_role: str | None) -> bool:
    if not config.AGENT_ALLOW_MODEL_OVERRIDE:
        return False
    if bearer_user_role is None:
        return bool(config.AGENT_MODEL_OVERRIDE_ANONYMOUS)
    allowed_roles = config.AGENT_MODEL_OVERRIDE_ROLES
    if not allowed_roles:
        return True
    return bearer_user_role.strip().lower() in allowed_roles


def resolve_effective_model(
    *,
    messages: list[dict[str, Any]],
    body_model: Any,
    profile_header: str | None,
    override_header: str | None,
    bearer_user_role: str | None,
) -> tuple[str, str]:
    """
    Pick the Ollama model id for this chat completion.

    Returns ``(model_id, reason)`` where ``reason`` is a short tag for logs
    (e.g. ``profile:vlm``, ``override:header``, ``profile:default``).
    """
    auto_vlm = messages_contain_image_parts(messages)
    if auto_vlm:
        profile = "vlm"
        base = _model_for_profile("vlm")
        reason_base = "auto:vlm_images"
    else:
        hdr = (profile_header or "").strip()
        body_tok = _profile_token_from_body(body_model)
        if hdr:
            profile = _normalize_profile(hdr)
        elif body_tok:
            profile = body_tok
        else:
            profile = "default"
        base = _model_for_profile(profile)
        reason_base = f"profile:{profile}" + (
            f" (body.model token)" if body_tok and not hdr else ""
        )

    if _override_allowed(bearer_user_role):
        oh = _strip_model(override_header)
        bm = _strip_model(body_model)
        if _profile_token_from_body(body_model):
            bm = None
        chosen = oh or bm
        if chosen:
            logger.info(
                "model routing: %s -> override %r (allow_override role=%r)",
                reason_base,
                chosen,
                bearer_user_role,
            )
            return chosen, "override:header" if oh else "override:body"

    logger.info(
        "model routing: %s effective=%r (profile=%s)",
        reason_base,
        base,
        profile,
    )
    return base, reason_base
