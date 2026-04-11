# User data, secrets, and access (Agent Layer)

This document describes how **secrets**, **structured profile**, **persona text**, and **shared KB notes** fit together. It complements [WEBUI_CONTRACT.md](WEBUI_CONTRACT.md).

## Principles

1. **Secrets** (API keys, OAuth tokens, Gmail app passwords) belong in **`user_secrets`** only — encrypted at rest (`AGENT_SECRETS_MASTER_KEY`). They are loaded **only** inside trusted tool code for the authenticated user, never bulk-injected into the model prompt.
2. **Structured profile** (`user_agent_profile`) holds **non-secret** fields. The server builds a compact **“User profile:”** bullet list (only non-empty fields) when **`inject_structured_profile`** is true — not a raw JSON dump of the row.
3. **Persona** (`user_agent_persona`) is **free-text** on top. **`inject_into_agent`** merges it after the structured summary when enabled.
4. **Sharing** applies to **KB notes** via **`user_kb_note_shares`**: read-only for another user in the **same tenant**.

## `user_agent_profile` (columns)

| Area | Fields |
|------|--------|
| Identity / locale | `display_name`, `preferred_output_language`, `locale`, `timezone` |
| Location / travel | `home_location`, `work_location`, `travel_mode`, `travel_preferences` (JSONB) |
| Communication | `tone`, `verbosity`, `language_level` |
| Interests | `interests`, `hobbies` — JSONB array of **strings** or **`[{ "name": "…", "weight": 0.0–1.0 }]`** (sorted by weight for the prompt) |
| Work / tech | `job_title`, `organization`, `industry`, `experience_level`, `primary_tools` (JSONB strings) |
| Agent behaviour | `proactive_mode`, `interaction_style` |
| Injection (coarse) | `inject_structured_profile`, `inject_dynamic_traits`, `dynamic_traits` (JSONB) |
| Injection (fine) | **`injection_preferences`** (JSONB) — optional `include_*` flags (see below) |
| Usage / rhythm | **`usage_patterns`** (JSONB) — e.g. active hours, common topics (for future tooling) |
| Versioning | **`profile_version`** (monotonic counter on each save), **`profile_hash`** (SHA-256 of canonical profile content for diff/cache) |

**`injection_preferences`** optional keys (all booleans; omitted = treat as true). Explicit **`false`** hides that block:

- `include_identity`, `include_location`, `include_communication`, `include_interests`, `include_work`, `include_tools`, `include_behavior`, `include_usage_patterns`, `include_dynamic_traits` (only relevant if `inject_dynamic_traits` is true).

**`interaction_style`** (documented; mapped in the prompt): `assistant` | `coach` | `operator` | `companion` | custom string (passed through without a fixed hint).

## Database migration

Fresh installs: run Alembic **`schema_001`** only (`alembic upgrade head`); it applies `src/infrastructure/db/migrations/sql/schema.sql`.

## HTTP API (same identity as chat)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/user/profile` | Full profile (defaults if empty); includes `profile_version`, `profile_hash`. |
| `PUT` | `/v1/user/profile` | Partial patch; nested objects **`injection_preferences`**, **`usage_patterns`**, **`travel_preferences`**, **`dynamic_traits`** are **merged** with existing keys when you send a partial dict. |
| `GET` / `PUT` | `/v1/user/persona` | Free-text persona. |

## Behaviour

- **Chat:** Structured summary first (gated by flags), then persona text.
- **`profile_version` / `profile_hash`:** Server-maintained on each successful profile save; clients should not send them (they are stripped if present).

## Future work

- Per-secret ACL, per-user encryption keys, automated `dynamic_traits` / `usage_patterns` from opt-in telemetry.
