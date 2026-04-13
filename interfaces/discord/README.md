# Discord (optional)

**Production path:** the Discord gateway runs **inside the same `agent-layer` process** (see `src/integrations/discord_bridge.py`). Operators enable it and paste the **Discord bot token** in the Web UI: **Admin → Interfaces** (`PATCH /v1/admin/operator-settings`). Linked users are resolved from `users.discord_user_id`; chat runs in-process (no HTTP bearer for Discord). No separate Docker service.

End users still link their numeric Discord user id under **Settings → Connections** (`PUT /v1/user/discord`).

Database migration **`schema_003`** adds `operator_settings.discord_bot_*` columns.

## Local script (optional)

`bot.py` + `requirements.txt` in this folder can still be used for **local debugging** without running the full API image. Prefer the in-process bridge for deployments.
