# WebUI integration contract (Agent Layer)

This document is the **stable integration surface** for front ends (e.g. Open WebUI fork) that talk to Agent Layer over HTTP. Copy it into the UI repo or link to this path in git; implementation details belong here, UI wiring belongs there.

**UI/product layout** (workspaces, badges, image page, system-prompt rules): see [WEBUI_DESIGNS.md](WEBUI_DESIGNS.md).

**Service identity:** FastAPI app title `agent-layer` (version aligned with `src/api/main.py`).  
**Canonical spec changes:** bump version in code when you change response shapes or auth rules, and add a short note under [Changelog](#changelog) below.

---

## 1. Base URL and transport

- **Base:** operator-defined, e.g. `https://agent.example.com` or `http://agent:8088` in Docker.
- **JSON** for request/response bodies unless noted (SSE for streaming chat).
- **TLS:** recommended on any non-loopback deployment.

---

## 2. Authentication

### 2.1 Login (browser or server-side token exchange)

`POST /auth/login`  
**Auth:** none  
**Body:** `{ "email": string, "password": string }`  
**200:** `{ "access_token", "token_type": "bearer", "expires_in": 900, "user": { "id", "email", "role" } }` — **no `refresh_token` in JSON.**  
**Set-Cookie:** httpOnly session cookie `agent_refresh` (refresh token); use `credentials: "include"` on fetches. Over HTTPS, set env **`AGENT_COOKIE_SECURE=true`** so the cookie is **Secure**.  
**401:** invalid credentials

### 2.2 Refresh

`POST /auth/refresh`  
**Auth:** none  
**Cookie:** `agent_refresh` (preferred for browsers), **or** **Body:** `{ "refresh_token": string }` for non-browser clients.  
**200:** `{ "access_token", "token_type": "bearer", "expires_in": 900, "user": { "id", "email", "role" } }`  
**401:** invalid or expired refresh token

### 2.2.1 Logout

`POST /auth/logout`  
**Auth:** none (cookie-based session)  
**Effect:** revokes the refresh token server-side and clears the `agent_refresh` cookie.  
**200:** `{ "ok": true }`

### 2.3 First admin (one-time bootstrap)

When no user with `role = admin` exists, the HTTP server **does not start** until you set **`AGENT_INITIAL_ADMIN_EMAIL`** and **`AGENT_INITIAL_ADMIN_PASSWORD`** (≥ 8 chars) **before** the first process start — the first admin is created at startup. Remove those variables after login and change the password.

`GET /auth/setup-status`  
**Auth:** none  
**200:** `{ "needs_setup": true | false }` — `true` only if no admin exists (e.g. misconfiguration while running); normal installs exit at boot if unset.

### 2.4 Protected routes

Almost all routes require **`Authorization: Bearer <token>`** where `<token>` is either:

- a **JWT access token** from `/auth/login` or `/auth/refresh`, or  
- a **per-user API key** (stored hashed server-side; same header format).

If the header is missing or invalid, the API returns **401** with body `{"error":"unauthorized"}`.

### 2.5 Public routes (no `Authorization`)

Exact paths (see `auth_middleware` in `src/api/main.py`):

- `GET /health`
- `GET /v1/models` (Ollama passthrough for model lists)
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/setup-status`
- `GET /` (redirect or JSON hint)
- Paths under `/admin/` (static admin HTML when shipped)

**Exception:** `POST /v1/user/secrets/register-with-otp` is allowed without Bearer (OTP-bound registration from chat).

---

## 3. User and tenant identity (multi-user)

Chat, tools, RAG ingest, user profile/secrets, and related routes resolve **user id** and **tenant id** only from **trusted auth**, not from client-supplied identity headers (those are ignored for identity).

**Source of truth**

1. **`Authorization: Bearer`** with a **JWT access token** from `POST /auth/login` (subject = `users.id`), or a **user API key** that maps to a `users` row.
2. **Tenant** is always **`users.tenant_id`** for that user (PostgreSQL). Tool-policy allowlists use the same numeric ids as `tenants.id`.
3. **Optional shared secret** (`operator_settings.optional_connection_key`): if the Bearer value matches that secret, the server uses the fixed UUID in **`AGENT_OPTIONAL_KEY_USER_ID`** (must be an existing `users.id`) — configure in `.env` / deployment.

See `src/domain/http_identity.py` (`resolve_chat_identity`, `resolve_tools_list_identity`).

---

## 4. OpenAI-compatible chat (primary UI integration)

### 4.1 Chat completions

`POST /v1/chat/completions`  
**Auth:** required  
**Body:** OpenAI-style `chat.completions` request (model, messages, optional `tools`, `tool_choice`, `stream`, etc.).  
**Response:** OpenAI-style `chat.completions` JSON; if `stream: true`, **SSE** (`text/event-stream`) with chunked completion (compatible with clients that expect a single completion converted to stream — see `_completion_to_sse_lines` in `main.py`).

### 4.2 Optional routing headers (agent behavior)

| Header | Meaning |
|--------|--------|
| `X-Agent-Router-Categories` | Comma-separated router category ids (tool domains) to bias routing. |
| `X-Agent-Tool-Domain` | Single domain hint for tool filtering. |
| `X-Agent-Model-Profile` | `default` \| `vlm` \| `agent` \| `coding` — server-side default model profile (see hybrid routing). |
| `X-Agent-Model-Override` | Explicit Ollama model id; honoured only when override policy allows (see hybrid routing). |

These are **optional**; omit for default router behavior.

**JSON body (agent-only, stripped before Ollama):** `agent_capability_hints` — array of capability strings (e.g. `["mail.read","weather.get"]`) to narrow merged `tools[]` to tools that declare matching `TOOL_CAPABILITIES` in the registry. If no tool matches, the filter is ignored (same safe fallback as domain filtering). Index: `GET /v1/capabilities`. See `docs/adr/0001-tool-and-agent-architecture.md`.

### Hybrid model routing (env + headers; optional client override)

Agent Layer picks the Ollama model id **before** each `chat_completion` run:

1. **Auto VLM:** If any message `content` is a **multimodal** list containing an image part (`type` `image_url`, `image`, or `input_image`), the profile **`vlm`** is forced for that request (vision-capable model on the server).
2. **Profile selection** (when not auto-VLM): If `X-Agent-Model-Profile` is set (non-empty), it selects the profile: `default` \| `vlm` \| `agent` \| `coding` (unknown values → `default`). **Otherwise**, if the JSON body field **`model`** is exactly one of those four tokens (case-insensitive), it is treated as a **delegated profile id**, not an Ollama model name — e.g. Open WebUI can send **`model: "agent"`** so the server uses **`AGENT_MODEL_PROFILE_AGENT`**. If neither applies, profile is **`default`**.
3. **Profile → model:** Each profile maps to an env-defined model id, falling back to `OLLAMA_DEFAULT_MODEL` when unset:
   - `AGENT_MODEL_PROFILE_DEFAULT`, `AGENT_MODEL_PROFILE_VLM`, `AGENT_MODEL_PROFILE_AGENT`, `AGENT_MODEL_PROFILE_CODING`
4. **Override (optional):** If `AGENT_ALLOW_MODEL_OVERRIDE` is true **and** the caller is allowed:
   - **`X-Agent-Model-Override`** (header) wins over the JSON **`model`** field when both are set. The body **`model`** is used as a **literal Ollama id** only if it is **not** one of the four reserved profile tokens above.
   - If `AGENT_MODEL_OVERRIDE_ROLES` is **empty**, any **authenticated** Bearer user (JWT/API key resolving to a DB user) may override.
   - If `AGENT_MODEL_OVERRIDE_ROLES` is **non-empty** (e.g. `admin`), only users whose `role` is listed may override.
   - Without Bearer user, override is allowed only if **`AGENT_MODEL_OVERRIDE_ANONYMOUS=true`** (use with care on optional anonymous routes).

**WebSocket:** Per-`chat` frame optional strings **`model_profile_header`**, **`model_override_header`** (frame values override handshake headers for that turn), or handshake `X-Agent-Model-*` headers — these affect routing only, not user/tenant identity.

**Transparency:** The first event **`agent.session`** includes **`effective_model`** and **`model_resolution`** (short tag, e.g. `auto:vlm_images`, `profile:agent`, `override:body`) so the WebUI can show which model ran.

### 4.3 WebSocket chat (duplex, per-round events)

`WebSocket /ws/v1/chat`  
**Auth:** `?token=<JWT_or_API_key>` on the handshake URL **or** header `Authorization: Bearer <same>`. When `optional_connection_key` is set, the handshake may use that shared secret as the token **only if** `AGENT_OPTIONAL_KEY_USER_ID` maps to a real `users` row (same as HTTP). If the optional key is **not** configured, the WebSocket **requires** a valid JWT or user API key (no anonymous handshake).

**User/tenant:** From the token only (see §3); identity headers are not used.

#### What the WebUI agent should render (recommended)

For **`/agent/*`** chat wired to this socket, treat the stream of server frames as a **timeline** (sidebar, collapsible strip, or step list), not only the final assistant bubble:

1. **`agent.session`** — routed category, router categories, `forwarded_tools`, plus **`effective_model`** / **`model_resolution`** (hybrid model routing, see above).
2. **`agent.llm_round_start`** / **`agent.llm_round`** — round index, tool names the model chose (`tool_calls`), short `content_excerpt`.
3. **`agent.tool_start`** / **`agent.tool_done`** — each executed tool (name; done includes `result_chars`).
4. **`agent.step_wait`** — optional human-in-the-loop pause (see below); show a **Continue** control that sends `continue_step`.
5. **`agent.done`** — round finished with final text, or `max_tool_rounds` / other end states.
6. **`chat.completion`** — final OpenAI-shaped completion for the transcript (same as HTTP).

**Cancel** should map to a UI control that sends `cancel` (honoured before the next internal round; does not abort a request already in flight at Ollama).

#### Step-by-round mode (optional)

In the **`chat`** frame, set inside `body`:

- **`agent_pause_between_rounds`:** `true` (or `"true"` / `1`) — after the model returns **tool calls** and the server has **finished running those tools**, the server emits **`agent.step_wait`** and **blocks** until the client sends **`{"type":"continue_step"}`**. Then the next LLM round runs. There is **no** pause after a round that ends with plain text (final reply) or on the last possible round (no further round slot).

While waiting, the client may still send **`add_tools`** (merge names for subsequent rounds) and **`cancel`**.

**HTTP `POST /v1/chat/completions`** does **not** support this pause (no control queue); step mode is **WebSocket-only**. If `agent_pause_between_rounds` is set over HTTP, it is ignored.

**Client → server** (JSON text frames):

| `type` | Purpose |
|--------|---------|
| `ping` | Server replies `{"type":"pong"}`. |
| `cancel` | Abort before the **next** internal LLM round (does not interrupt a request already in flight at Ollama). Also aborts while blocked on **`agent.step_wait`**. |
| `add_tools` | Body `names: string[]` — register extra tool function names for **subsequent** LLM rounds (must exist in server registry; denylist still applies). |
| `continue_step` | After **`agent.step_wait`**, resume when **`agent_pause_between_rounds`** was set on this turn’s `chat.body`. Ignored if not waiting (may be discarded with a debug log). |
| `chat` | Start a turn: `body` = same object as `POST /v1/chat/completions` (minus `stream`); optional `router_categories_header`, `tool_domain_header`, `model_profile_header`, `model_override_header` strings. |

**Server → client** (JSON): `agent.session`, `agent.llm_round_start`, `agent.llm_round`, `agent.tool_start`, `agent.tool_done`, optional **`agent.step_wait`**, `agent.done`, `agent.cancelled` / `agent.aborted`, then `{"type":"chat.completion","data":{...}}` with the final OpenAI-shaped completion (or `error` fields on failure). Multiple `chat` turns may be sent on one connection.

---

## 5. Models

`GET /v1/models`  
**Auth:** public  
**Response:** JSON from Ollama’s `/v1/models` (passthrough).

---

## 6. Tools (discovery and execution)

### 6.1 List tools (OpenAI `tools[]` shape + metadata)

`GET /v1/tools`  
**Auth:** required  
**Response:**

```json
{
  "tools": [ /* OpenAI tool specs */ ],
  "tools_meta": [ /* per-module metadata */ ]
}
```

### 6.1.1 Capability index (machine-readable)

`GET /v1/capabilities`  
**Auth:** required (same as `GET /v1/tools`)  
**Response:** `{ "schema_version": 1, "by_capability": { "<cap>": [ { "tool_name", "package_id", "domain" } ] }, "tools_unclassified": [ ... ] }` — built from the same policy-filtered metadata as `GET /v1/tools` for this caller. `tools_unclassified` lists registered function names with no declared capabilities (migration aid).

### 6.2 Generic runner (Open WebUI “tool server” style)

`POST /tools/run`  
**Auth:** required  
**Body:** `{ "name": "<tool_function_name>", "arguments": { ... } }`  
**200:** `{ "result": <JSON-serializable> }`  
**400:** missing name or bad input  
**500:** execution error

### 6.3 Per-tool POST (direct path)

`POST /{tool_name}`  
**Auth:** required  
**Body:** JSON object = tool arguments (same as `arguments` above).  
**200:** `{ "result": ... }`

Tool names must not collide with reserved top-level paths (e.g. `v1`, `auth`, `health`, `openapi`, `tools`).

### 6.4 Router categories (for UI presets)

`GET /v1/router/categories`  
**Auth:** required  
**Response:** `{ "categories": [ ... ] }` — catalog for operator/WebUI labels.

### 6.5 OpenAPI specs for tools (codegen / docs)

| Method | Path | Auth | Purpose |
|--------|------|------|--------|
| GET | `/openapi.json` | required | All registered tools as synthetic paths `/{toolName}` POST. |
| GET | `/openapi/domains` | required | List domains + `openapi_url` per domain. |
| GET | `/openapi/{domain}.json` | required | Tools filtered by domain. |
| GET | `/openapi/tool/{tool_name}/openapi.json` | required | Single tool. |

---

## 7. Admin (operator)

**Auth:** required; some routes use `@require_permission("write", "tool")` (admin role passes).

| Method | Path | Purpose |
|--------|------|--------|
| GET | `/v1/admin/tools` | Tool metadata only. |
| POST | `/v1/admin/reload-tools` | Rescan tool directories. Query: `scope=all|extra` (both full rescan). |
| POST | `/v1/admin/create-tool` | Create/replace tool module (same contract as chat `create_tool`). |
| POST | `/v1/admin/rag/ingest` | RAG text ingest (requires `AGENT_RAG_ENABLED=true`). Body: `text` (required), optional `domain`, `title`, `source_uri`. |

---

## 8. User secrets API

Prefix: `/v1/user/secrets`  
**Auth:** required for all except OTP registration.

| Method | Path | Purpose |
|--------|------|--------|
| POST | `/v1/user/secrets/register-with-otp` | **Public:** body `otp`, `service_key`, `secret` (string or JSON object). |
| GET | `/v1/user/secrets` | List service keys (no values). |
| POST | `/v1/user/secrets` | Upsert secret: `service_key`, `secret`. |
| DELETE | `/v1/user/secrets/{service_key}` | Delete secret. |

Requires `AGENT_SECRETS_MASTER_KEY` on the server for encrypt-at-rest.

---

## 9. Health

`GET /health`  
**Auth:** public  
**200:** `{ "status": "ok", "database": "ok" }`  
**503:** database unavailable

---

## 10. CORS

Controlled by **`AGENT_CORS_ORIGINS`** (comma-separated). If the list does not contain `*`, credentials may be enabled in middleware. Align the WebUI origin with this env in deployment.

---

## 11. Image Studio (schema-driven UI)

**Auth:** same optional-connection rules as `GET /v1/tools` (see §2.5 / `GET /auth/policy`).

### 11.1 Catalog

`GET /v1/studio/catalog`  
**200:** JSON with `studio_version`, `engine_default`, `presets[]`. Each preset includes:

| Field | Meaning |
|--------|--------|
| `run_key` | Stable id for `POST /v1/studio/jobs` (e.g. `comfy_txt2img_default`). |
| `title` / `description` | UI copy. |
| `kind` | e.g. `txt2img`, `inpaint`. |
| `engine` | e.g. `comfyui`. |
| `workflow_file` | Repo-relative path to the API-format workflow JSON (informational). |
| `inputs_schema` | JSON-Schema-style object for **dynamic forms** (`properties`, `required`, `default`). |

The Studio front end should **only** render presets from this response (no hardcoded duplicate list).

`studio_version` is bumped when preset or schema semantics change (e.g. new optional fields).

**Checkpoint dropdown:** When ComfyUI is reachable, the server augments each preset’s `inputs_schema.properties.checkpoint` (and `ckpt_name` if present) with **`enum`**: `[ "" , ...filenames ]` — same filenames as `GET /v1/studio/comfy/checkpoints`, sorted, with a leading empty string for **workflow default** (omit `checkpoint` or submit `""`). Schema-driven UIs should render **`type: string` + `enum`** as a **&lt;select&gt;**. If ComfyUI is down at catalog fetch time, those properties have **no** `enum` — fall back to `GET /v1/studio/comfy/checkpoints` or a text field with server-side validation on submit.

### 11.1b ComfyUI checkpoints (dropdown)

`GET /v1/studio/comfy/checkpoints`  
**Auth:** same optional-connection rules as the catalog.  
**200:** `{ "checkpoints": [ "<filename.safetensors>", ... ] }` — filenames from ComfyUI `GET /object_info` for `CheckpointLoaderSimple` / `ckpt_name`, sorted uniquely.

**502:** ComfyUI unreachable or `/object_info` error.

**Operator:** `AGENT_STUDIO_ALLOWED_CKPTS` (comma-separated exact filenames) restricts the list to an intersection with Comfy’s list. Without it, all checkpoints Comfy reports are returned. Cache TTL: `AGENT_STUDIO_CKPT_LIST_CACHE_SEC` (default 60).

### 11.2 Jobs (runner)

`POST /v1/studio/jobs`  
**Body:** `{ "run_key": string, "inputs": { ... } }` — `inputs` must match the catalog `inputs_schema` for that `run_key`.  

Optional **`inputs.checkpoint`** (alias **`ckpt_name`**) for txt2img and inpaint presets: must equal one entry from `GET /v1/studio/comfy/checkpoints` (after allowlist), or **`""`** / omitted for workflow default. Path separators and `..` are rejected.  

**200:** `{ "ok": true, "run_key", "prompt_id", "images": [ <imageObj>, ... ], "primary_image": <imageObj> }` where each **imageObj** is `{ "mime": "image/png", "base64": "<raw>", "data_url": "data:image/png;base64,..." }`. Agent Layer **downloads** each file from ComfyUI `/view` server-side and **embeds** pixels in JSON so the browser never calls the Comfy host. WebUI: `<img src={primary_image.data_url} />` (or build from `mime` + `base64`).

**400:** unknown `run_key` or invalid `inputs` (e.g. missing required fields).  
**502:** ComfyUI unreachable, `/prompt` error, `/view` error, output larger than `AGENT_STUDIO_MAX_OUTPUT_BYTES` (default 25_000_000), or no output before poll timeout (`AGENT_STUDIO_COMFY_POLL_TIMEOUT`, default 180s).  

Requires **`COMFYUI_URL`** reachable **from the Agent Layer container** (not from the browser). Inpaint inputs: client base64 → Agent **`/upload/image`** → Comfy `LoadImage` filenames.

---

## 12. Planned / out of scope (coordinate before implementing in UI)

The following are **not** fully specified until extended here:

- **ComfyUI job execution:** `POST /v1/studio/jobs` runs txt2img + inpaint presets; **async job queue**, **multipart upload** to Comfy input, and **rich status** are still optional follow-ups.
- **Capabilities flags** in WebUI (e.g. `image_pipeline`, `agent_routing`) are **UI/workspace concerns**; Agent Layer only needs the correct headers + endpoints above.

When you add backend endpoints, extend this file and optionally publish **OpenAPI** for those routes.

---

## 13. How the WebUI repo should use this

1. **Point** the OpenAI API base URL (or custom connection) at Agent Layer’s origin.  
2. **Send** `Authorization: Bearer …` on every protected call (login or API key).  
3. **Forward** user id (and tenant if you use it) via the headers in §3.  
4. **Tools:** either configure Open WebUI’s tool server to `POST /tools/run` or register tools whose server URL maps to `POST /{tool_name}`.  
5. **Image Studio:** `GET {AGENT_BASE}/v1/studio/catalog` → build forms from `presets[].inputs_schema`; submit with `POST /v1/studio/jobs` when the runner is implemented.  
6. **Regressions:** if Agent Layer changes status codes or JSON keys, update this document and the UI in the same release train.

---

## Changelog

| Date | Note |
|------|------|
| 2026-04-07 | Initial contract document; `/auth/refresh` documented as public for refresh-token flow. |
| 2026-04-08 | `WebSocket /ws/v1/chat`: duplex chat, per-round `agent.*` events, `cancel`, `add_tools`. |
| 2026-04-08 | WebSocket: optional `agent_pause_between_rounds` on `chat.body`, `continue_step` client frame, `agent.step_wait` server event; contract documents recommended WebUI timeline + Continue control. |
| 2026-04-09 | Hybrid model routing: env profile models, auto-VLM from multimodal messages, `X-Agent-Model-Profile` / `X-Agent-Model-Override`, optional override policy; `agent.session` adds `effective_model`, `model_resolution`. |
| 2026-04-09 | Body `model`: reserved tokens `default`/`vlm`/`agent`/`coding` select profile (delegated id); literal Ollama id only when override policy allows and token is not reserved. |
| 2026-04-09 | `GET /v1/studio/catalog` (optional auth) — Image Studio presets + `inputs_schema`; `POST /v1/studio/jobs` runs ComfyUI for `comfy_txt2img_default` / `comfy_inpaint_masked_default`. |
| 2026-04-09 | Studio job **200**: `images` / `primary_image` embed Comfy outputs as `mime` + `base64` + `data_url` (server-side fetch; no Comfy URL to browser). |
| 2026-04-09 | `GET /v1/studio/comfy/checkpoints` + optional `inputs.checkpoint` / `ckpt_name` (allowlist `AGENT_STUDIO_ALLOWED_CKPTS`); catalog `studio_version` 2. |
| 2026-04-09 | `GET /v1/studio/catalog` injects `enum` on `checkpoint` / `ckpt_name` when ComfyUI list succeeds (dropdown-friendly schema). |
