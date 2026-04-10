"""
Optional operator-configured value for selected public-style HTTP routes.

Any client that speaks OpenAI-compatible HTTP (or calls these paths) may use the same
``optional_connection_key``: send ``Authorization: Bearer <value>`` when the key is set.
Not tied to a single product name (Web UI, bots, scripts, etc.).
"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import HTTPException, Request

from src.infrastructure.auth import get_current_user
from src.infrastructure.operator_settings import stored_optional_connection_key

_MIDDLEWARE_PUBLIC_EXACT: frozenset[str] = frozenset(
    {
        "/",
        "/health",
        "/v1/models",
        "/auth/login",
        "/auth/refresh",
        "/auth/logout",
        "/auth/setup-status",
        "/auth/policy",
        "/favicon.ico",
        "/login",
        "/chat",
        "/dashboard",
    }
)


def middleware_path_is_public(path: str, method: str) -> bool:
    """Paths that skip global Bearer/JWT checks entirely."""
    if path.startswith("/js/"):
        return True
    if path == "/app" or path.startswith("/app/"):
        return True
    if path in _MIDDLEWARE_PUBLIC_EXACT:
        return True
    if (method or "").upper() == "POST" and path == "/v1/user/secrets/register-with-otp":
        return True
    return False


def is_optional_connection_route(path: str, method: str) -> bool:
    """Routes that honor ``optional_connection_key`` when set (see operator_settings)."""
    m = (method or "").upper()
    if m == "POST" and path == "/v1/chat/completions":
        return True
    if m == "POST" and path == "/tools/run":
        return True
    if m == "GET" and path == "/v1/tools":
        return True
    if m == "GET" and path == "/v1/router/categories":
        return True
    if m == "GET" and path == "/v1/studio/catalog":
        return True
    if m == "GET" and path == "/v1/studio/comfy/checkpoints":
        return True
    if m == "POST" and path == "/v1/studio/jobs":
        return True
    if m == "GET" and (
        path == "/openapi.json"
        or path == "/openapi/domains"
        or path.startswith("/openapi/")
    ):
        return True
    return False


async def optional_connection_allows(request: Request) -> bool:
    """
    No key configured → allow without Authorization.
    Key configured → require matching Bearer value, or valid JWT / API key.
    """
    expected = stored_optional_connection_key()
    auth = request.headers.get("authorization") or ""
    token = auth.removeprefix("Bearer ").strip()
    if expected is None:
        return True
    if not token:
        return False
    try:
        if secrets.compare_digest(token, expected):
            return True
    except (TypeError, ValueError):
        pass
    try:
        await get_current_user(request)
        return True
    except HTTPException:
        return False


def public_http_auth_policy() -> dict[str, Any]:
    """Machine-readable policy for ``GET /auth/policy``."""
    configured = stored_optional_connection_key() is not None
    return {
        "description": "Middleware order: public paths → optional connection routes → JWT/API key.",
        "middleware": {
            "options_preflight": "OPTIONS passes without Authorization.",
            "no_authorization": {
                "exact_paths": sorted(_MIDDLEWARE_PUBLIC_EXACT),
                "path_prefixes": ["/js/", "/app/"],
                "post_path": "/v1/user/secrets/register-with-otp",
            },
            "optional_connection_key": {
                "operator_settings_column": "optional_connection_key",
                "configured": configured,
                "when_not_configured": "Listed routes accept requests without Authorization.",
                "when_configured": (
                    "Same routes require Authorization: Bearer matching the stored value, "
                    "or a valid JWT / API key."
                ),
                "routes": [
                    {"method": "WebSocket", "path": "/ws/v1/chat"},
                    {"method": "POST", "path": "/v1/chat/completions"},
                    {"method": "POST", "path": "/tools/run"},
                    {"method": "GET", "path": "/v1/tools"},
                    {"method": "GET", "path": "/v1/router/categories"},
                    {"method": "GET", "path": "/v1/studio/catalog"},
                    {"method": "GET", "path": "/v1/studio/comfy/checkpoints"},
                    {"method": "POST", "path": "/v1/studio/jobs"},
                    {"method": "GET", "path": "/openapi.json"},
                    {"method": "GET", "path": "/openapi/domains"},
                    {"method": "GET", "path_prefix": "/openapi/"},
                ],
            },
            "all_other_routes": "Valid JWT access token or api_keys entry in Authorization: Bearer.",
        },
        "admin_routes": [
            "GET/PUT /v1/admin/operator-settings",
            "GET/PUT /v1/admin/interfaces",
            "POST /v1/admin/users",
        ],
        "note_admin": "Bearer must resolve to a user with role=admin; then require_admin().",
    }
