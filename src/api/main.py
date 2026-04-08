"""OpenAI-compatible HTTP API: proxies to Ollama and executes local tools."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.core.config import config
from src.infrastructure.ollama_gate import ollama_get_json
from src.infrastructure.db import db
from src.infrastructure.auth import (
    get_current_user,
    require_admin,
    require_permission,
    LoginRequest,
    create_access_token,
    create_refresh_token,
    verify_password,
    get_user_by_email,
    validate_refresh_token,
)
from src.infrastructure.operator_settings import (
    InterfaceHintsPayload,
    OperatorSettingsPayload,
    apply_interface_hints,
    apply_update as operator_settings_apply,
    interface_hints_public,
    public_dict as operator_settings_public,
    stored_openwebui_bearer,
)
from src.domain.admin_setup import is_first_start, setup_admin_claim_if_needed, claim_admin_user
from src.domain.agent import chat_completion
from src.domain.http_identity import resolve_user_tenant
from src.domain.identity import reset_identity, set_identity
from src.domain.plugin_system.tools_api import router as tools_router
from src.api.rag_api import router as rag_router
from src.domain.plugin_system.registry import get_registry
from src.infrastructure.user_secrets_api import router as user_secrets_router

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


from src.infrastructure.cron import start_cron_scheduler, stop_cron_scheduler

@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_pool()
    try:
        setup_admin_claim_if_needed()
    except Exception:
        logger.exception(
            "First-admin bootstrap failed (run DB migrations; need 0011_admin_claim_otp?)"
        )
    if (os.environ.get("AGENT_CORS_ORIGINS") or "*").strip() == "*":
        logger.warning(
            "AGENT_CORS_ORIGINS is '*'. For a public host, set explicit origins "
            "(e.g. https://openwebui.example) so browsers do not send creds to arbitrary sites."
        )
    get_registry()
    start_cron_scheduler()
    yield
    stop_cron_scheduler()
    db.close_pool()


app = FastAPI(title="agent-layer", version="0.7.2", lifespan=lifespan)
app.include_router(user_secrets_router)
app.include_router(tools_router)
app.include_router(rag_router)


# Auth Endpoints
@app.post("/auth/login")
async def login(request: Request, login_data: LoginRequest):
    user = get_user_by_email(login_data.email)
    if not user or not user.password_hash or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = create_access_token(user.id, user.role)
    refresh_token, refresh_token_hash = create_refresh_token(user.id)
    
    # Store refresh token
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                VALUES (%s, %s, NOW() + INTERVAL '7 days')
            """, (user.id, refresh_token_hash))
            conn.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 900,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role
        }
    }


@app.post("/auth/refresh")
async def refresh_token(request: Request):
    try:
        body = await request.json()
        refresh_token = body.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=400, detail="refresh_token required")
        
        user = validate_refresh_token(refresh_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        access_token = create_access_token(user.id, user.role)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 900
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


class ClaimRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=512)
    otp: str = Field(..., min_length=8, max_length=512)


@app.get("/auth/setup-status")
async def auth_setup_status():
    """True when no admin user exists yet (browser may show claim form)."""
    return {"needs_setup": is_first_start()}


@app.post("/auth/claim")
async def auth_claim(claim: ClaimRequest):
    """
    One-time first admin creation. Requires OTP from server logs (startup) or
    AGENT_ADMIN_CLAIM_OTP env after bootstrap (same value as printed once).
    """
    if not is_first_start():
        raise HTTPException(status_code=403, detail="setup already completed")

    if not claim_admin_user(claim.email.strip(), claim.password, claim.otp.strip()):
        raise HTTPException(
            status_code=401,
            detail="invalid or expired otp",
        )

    user = get_user_by_email(claim.email.strip())
    if not user:
        raise HTTPException(status_code=500, detail="user creation failed")

    access_token = create_access_token(user.id, user.role)
    refresh_token, refresh_token_hash = create_refresh_token(user.id)
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                VALUES (%s, %s, NOW() + INTERVAL '7 days')
                """,
                (user.id, refresh_token_hash),
            )
            conn.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 900,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
        },
    }


@app.get("/auth/me")
@require_permission("read", "user")
async def get_current_user_info(request: Request, user):
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at.isoformat()
    }


@app.get("/v1/admin/operator-settings")
async def get_operator_settings(request: Request):
    await require_admin(request)
    return operator_settings_public()


@app.put("/v1/admin/operator-settings")
async def put_operator_settings(request: Request, body: OperatorSettingsPayload):
    await require_admin(request)
    operator_settings_apply(body)
    return operator_settings_public()


@app.get("/v1/admin/interfaces")
async def get_interface_hints(request: Request):
    await require_admin(request)
    return interface_hints_public()


@app.put("/v1/admin/interfaces")
async def put_interface_hints(request: Request, body: InterfaceHintsPayload):
    await require_admin(request)
    apply_interface_hints(body)
    return interface_hints_public()


# interfaces/ lives at repo root (sibling of src/), not under src/
_control_dir = Path(__file__).resolve().parents[2] / "interfaces" / "web" / "static"
if _control_dir.is_dir():
    app.mount(
        "/control",
        StaticFiles(directory=str(_control_dir), html=True),
        name="control_panel",
    )

_cors_origins = [
    o.strip() for o in os.environ.get("AGENT_CORS_ORIGINS", "*").split(",") if o.strip()
]
_cors_credentials = "*" not in _cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


_OPENWEBUI_OPTIONAL_BEARER_PATHS: frozenset[tuple[str, str]] = frozenset(
    {("/v1/chat/completions", "POST"), ("/tools/run", "POST")}
)


def _openwebui_bearer_allows_request(request: Request) -> bool:
    """
    If no shared secret is configured, the client does not need to send Bearer.
    If a secret is configured, require Authorization: Bearer <exact match> (constant-time).
    """
    expected = stored_openwebui_bearer()
    auth = request.headers.get("authorization") or ""
    token = auth.removeprefix("Bearer ").strip()
    if expected is None:
        return True
    if not token:
        return False
    try:
        return secrets.compare_digest(token, expected)
    except (TypeError, ValueError):
        return False


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # CORS preflight must not require Bearer auth (browser sends no Authorization).
    if request.method == "OPTIONS":
        return await call_next(request)

    # Public endpoints no auth required
    public_paths = [
        "/health",
        "/v1/models",
        "/auth/login",
        "/auth/refresh",
        "/auth/claim",
        "/auth/setup-status",
        "/favicon.ico",
        "/"
    ]

    if any(path == p or path.startswith("/control/") for p in public_paths):
        return await call_next(request)

    # Allow OTP register endpoint
    if request.method == "POST" and path == "/v1/user/secrets/register-with-otp":
        return await call_next(request)

    # Open WebUI chat + tool runner: no Bearer unless a shared secret is stored; then Bearer must match
    if (path, request.method) in _OPENWEBUI_OPTIONAL_BEARER_PATHS:
        if _openwebui_bearer_allows_request(request):
            return await call_next(request)
        return JSONResponse(status_code=401, content={"error": "unauthorized"})

    # All other endpoints require valid auth
    try:
        await get_current_user(request)
    except HTTPException:
        return JSONResponse(status_code=401, content={"error": "unauthorized"})

    return await call_next(request)


@app.get("/")
def root():
    """Browser-friendly entry: control panel when shipped; otherwise a tiny JSON hint."""
    if _control_dir.is_dir():
        return RedirectResponse(url="/control/", status_code=307)
    return {
        "service": "agent-layer",
        "hint": "OpenAI API under /v1/ (e.g. POST /v1/chat/completions); GET /health; GET /v1/tools",
    }


@app.get("/health")
def health():
    try:
        with db.pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.commit()
    except Exception:
        logger.exception("database health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "down"},
        )
    return {"status": "ok", "database": "ok"}


@app.get("/v1/models")
async def models_proxy():
    """Passthrough so UIs can list Ollama models."""
    url = f"{config.OLLAMA_BASE_URL}/v1/models"
    status, text, data = await asyncio.to_thread(ollama_get_json, url, timeout=60.0)
    if status != 200:
        raise HTTPException(status_code=status, detail=text)
    return data


def _completion_to_sse_lines(completion: dict[str, Any]) -> bytes:
    """Build OpenAI-style SSE body from a full chat.completion JSON (Open WebUI sends stream=true)."""
    cid = completion.get("id") or f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = completion.get("created")
    if not isinstance(created, int):
        created = int(time.time())
    model = completion.get("model") or ""
    choice0 = (completion.get("choices") or [{}])[0]
    msg = choice0.get("message") if isinstance(choice0.get("message"), dict) else {}
    content = msg.get("content") if isinstance(msg, dict) else None
    if content is None:
        content = ""
    elif not isinstance(content, str):
        content = str(content)
    finish = choice0.get("finish_reason") or "stop"
    base = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
    }
    lines: list[bytes] = []
    lines.append(
        (
            "data: "
            + json.dumps(
                {
                    **base,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": content},
                            "finish_reason": None,
                        }
                    ],
                },
                ensure_ascii=False,
            )
            + "\n\n"
        ).encode()
    )
    lines.append(
        (
            "data: "
            + json.dumps(
                {
                    **base,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": finish,
                        }
                    ],
                },
                ensure_ascii=False,
            )
            + "\n\n"
        ).encode()
    )
    lines.append(b"data: [DONE]\n\n")
    return b"".join(lines)


def _generate_openapi_spec(title: str, tool_filter=None):
    reg = get_registry()
    
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": title,
            "version": "0.7.0"
        },
        "paths": {},
        "components": {
            "schemas": {}
        }
    }
    
    for tool_spec in reg.chat_tool_specs:
        fn = tool_spec.get("function", {})
        name = fn.get("name")
        if not name:
            continue
            
        if tool_filter and name not in tool_filter:
            continue
            
        description = fn.get("TOOL_DESCRIPTION", fn.get("description", ""))
        parameters = fn.get("parameters", {})
        
        spec["paths"][f"/{name}"] = {
            "post": {
                "summary": description,
                "operationId": name,
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": parameters
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Tool execution result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "result": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    
    return spec


@app.get("/openapi.json")
async def openapi_spec_all():
    """OpenAPI 3.0 Specification (all tools)"""
    return _generate_openapi_spec("Jetpack Agent Layer All Tools")


@app.get("/openapi/{domain}/openapi.json")
async def openapi_spec_domain(domain: str):
    """OpenAPI 3.0 Specification filtered by tool domain"""
    reg = get_registry()
    domain_tools = []
    
    for meta in reg.tools_meta:
        if meta.get("domain") == domain:
            domain_tools.extend(meta.get("tools", []))
    
    if not domain_tools:
        raise HTTPException(status_code=404, detail="domain not found")
        
    return _generate_openapi_spec(f"Jetpack Agent: {domain}", tool_filter=domain_tools)


@app.get("/openapi/{domain}.json")
async def openapi_spec_domain_legacy(domain: str):
    return await openapi_spec_domain(domain)


@app.get("/openapi/tool/{tool_name}/openapi.json")
async def openapi_spec_single_tool(tool_name: str):
    """OpenAPI 3.0 Specification for a single individual tool"""
    return _generate_openapi_spec(f"Jetpack Agent: {tool_name}", tool_filter=[tool_name])


@app.get("/openapi/domains")
async def list_openapi_domains():
    """List available tool domains for separate OpenAPI endpoints"""
    reg = get_registry()
    domains = {}
    
    for meta in reg.tools_meta:
        domain = meta.get("domain")
        if domain:
            if domain not in domains:
                domains[domain] = []
            domains[domain].extend(meta.get("tools", []))
    
    result = []
    for domain, tools in domains.items():
        result.append({
            "domain": domain,
            "tool_count": len(tools),
            "openapi_url": f"/openapi/{domain}.json"
        })
    
    return {"domains": result}


@app.post("/{tool_name}")
async def run_tool_direct(tool_name: str, request: Request):
    """Direct tool execution endpoint (Open WebUI calls this directly per tool)"""
    try:
        arguments = await request.json()
    except Exception:
        arguments = {}
    
    from src.domain.plugin_system.tools import run_tool
    
    user_id, tenant_id = resolve_user_tenant(request)
    id_token = set_identity(tenant_id, user_id)
    
    try:
        result = run_tool(tool_name, arguments)
        return {
            "result": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Direct tool execution failed for {tool_name}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        reset_identity(id_token)


@app.post("/tools/run")
async def run_tool_openwebui(request: Request):
    """Generic tool execution endpoint for Open WebUI Tool Server"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")
    
    tool_name = body.get("name")
    arguments = body.get("arguments", {})
    
    if not tool_name:
        raise HTTPException(status_code=400, detail="missing tool name")
    
    from src.domain.plugin_system.tools import run_tool
    
    user_id, tenant_id = resolve_user_tenant(request)
    id_token = set_identity(tenant_id, user_id)
    
    try:
        result = run_tool(tool_name, arguments)
        return {
            "result": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Open WebUI tool execution failed for {tool_name}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        reset_identity(id_token)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")

    want_stream = bool(body.get("stream"))
    work = dict(body)
    work["stream"] = False

    user_id, tenant_id = resolve_user_tenant(request)
    id_token = set_identity(tenant_id, user_id)

    router_hdr = (request.headers.get("X-Agent-Router-Categories") or "").strip() or None
    tool_dom_hdr = (request.headers.get("X-Agent-Tool-Domain") or "").strip() or None

    try:
        result = await chat_completion(
            work,
            router_categories_header=router_hdr,
            tool_domain_header=tool_dom_hdr,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("chat completion failed")
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        reset_identity(id_token)

    if want_stream:
        return StreamingResponse(
            iter([_completion_to_sse_lines(result)]),
            media_type="text/event-stream",
        )

    return result