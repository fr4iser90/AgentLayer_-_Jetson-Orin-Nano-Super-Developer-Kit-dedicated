# Tasks: Phase 2 & 3 (Roadmap)

Phase 1 ist umgesetzt: Tabelle `tasks`, Alembic `schema_004`, DB-API in `src/infrastructure/db/db.py`, Tool-Paket `tools/agent/productivity/tasks/tasks.py` (CRUD + `set_task_status`), Legacy `todos` entfernt.

Dieses Dokument fasst die **noch offenen** Schritte zusammen — absichtlich nicht gebaut, für spätere Iteration.

---

## Phase 2 — Dashboard ↔ `tasks` (Kanban / Table / Sync)

**Ziel:** Dashboard-UI (z. B. Kanban- oder Tabellen-View) liest/schreibt dieselben Zeilen wie die Agent-Tools (`tasks`), oder es gibt eine definierte Synchronisation.

**Mögliche Richtungen (eine wählen oder hybrid):**

1. **Single source of truth = Postgres `tasks`**
   - Dashboard-„Boards“ sind Views/Filters auf `tasks` (z. B. nach `status`, `category`, `tags`).
   - UI ruft neue oder erweiterte HTTP-Endpunkte auf (neben/nach `GET/PATCH /v1/dashboards`), z. B. `GET /v1/tasks` + `PATCH /v1/tasks/:id`, **oder** die bestehende Dashboard-API speichert nur noch Referenzen/Filter und lädt Daten serverseitig aus `tasks`.

2. **Dashboard-JSON bleibt Kanban-Daten**
   - Expliziter **Sync-Job** oder **on-save Hook**: Spalten/Karten ↔ `tasks` (höherer Pflegeaufwand, doppelte Wahrheit vermeiden oder klar trennen).

3. **Kind-spezifisch**
   - Dashboard-Kind `todo` (heute JSON-Template unter `dashboard/examples/todo/`) an **echte** `tasks`-Zeilen anbinden statt nur freies JSON — Template `data` müsste dann Schema + API-Vertrag bekommen.

**Technische Anker im Repo:**

- HTTP: `src/dashboard/router.py`, UI: `interfaces/agent-ui/src/pages/DashboardPage.tsx`, Bundles: `dashboard/examples/*/dashboard.kind.json`.
- DB: `tasks`-Spalten bereits geeignet für Filter (`status`, `priority`, `due_at`, `tags`, `parent_task_id`, `metadata`).

**Einkaufsliste:** Dashboard-Kind `shopping_list` (`dashboard/examples/shopping-list/`) bleibt ein **separates** Datenmodell (Tabellen-`items` im JSON), solange es kein dediziertes Tool gibt. Option später: Kategorie/Tag `shopping` auf `tasks` **oder** Agent-Tool „Dashboard-Patch“ nur für dieses Kind — in Phase 2 klären.

---

## Phase 3 — Planner-Tools & Discord

**Planner-Tools (Beispiele, neu unter z. B. `tools/agent/productivity/tasks/` oder eigenes Modul):**

- `break_task_into_subtasks` (Parent + Kinder in `tasks.parent_task_id`)
- `estimate_task_time` / `summarize_progress` (lesen `tasks` + optional `metadata`)
- Alles über dieselbe Registry wie bestehende Tools; Capabilities ggf. erweitern (`tasks.plan` o. ä.).

**Discord:**

- Die Bridge (`src/integrations/discord_bridge.py`) nutzt bereits dieselbe `chat_completion`-Pipeline wie die Web-UI → **keine Pflicht** für viele feste Prefix-Commands, wenn der Router + Tools zuverlässig sind.
- Optional: **dünne Prefix-Commands** (`!task add …`) nur als Shortcut, der intern trotzdem Chat/Tool-Flow oder direkte DB-Calls auslöst — mit Duplikat-Risiko zur LLM-Route abwägen.

**Router / NL (Web + Discord):**

- Trigger-Wörter liegen am Tool-Modul (`TOOL_TRIGGERS` in `tasks.py`), z. B. `reminder`, `task`, `todo`, `deadline`, …
- Beispiel: *„reminder: Milch kaufen“* kann das Modell auf `create_task` leiten, z. B. mit `tags: ["shopping"]` — **Konvention in Tool-Beschreibungen** dokumentieren, damit LLM Shopping vs. generische Task sinnvoll trennt.

---

## Kurz-Checkliste vor Start Phase 2

- [ ] Produktentscheid: eine Wahrheit (`tasks` only) vs. expliziter Sync mit Dashboard-JSON.
- [ ] API-Oberfläche für die UI (REST-Shape, Pagination, Filter).
- [ ] Auth: weiterhin pro User/Tenant wie bei `task_*` in `db.py`.

---

## Kurz-Checkliste vor Start Phase 3

- [ ] Welche Planner-Funktionen wirklich zuerst (1–2 Tools besser als zehn halbfertige).
- [ ] Capability / Operator-Policy für neue Tools.
- [ ] Discord: nur NL reicht vs. zusätzliche Commands testen.
