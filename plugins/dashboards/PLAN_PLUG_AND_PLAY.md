# Plan: Plug & Play — Tools, Dashboards, Studio, UI

**Ziel:** Forks sollen **ohne Kern-Code-Änderungen** neue Tools, Dashboard-Bundles und (wo sinnvoll) Studio-Presets ergänzen; weniger zentrale Verdrahtung, klare Konventionen und eine **einzige** geführte „Katalog“-Story.

**Stand:** Analyse abgeschlossen — Registry & Dashboard-Discovery sind schon gut; Reibung liegt bei **Studio**, **SPA-/HTTP-Routen**, **UI-Taxonomie**, **Admin-Buckets** und optional **Feature-Toggles**.

**Nicht in diesem Plan:** Geschäftslogik für Dashboard↔Tasks (siehe `PLAN_TASKS_PHASE_2_3.md`), Upload/Sharing (siehe `PLAN_UPLOAD_AND_SHARING.md`).

---

## Prinzipien

1. **Daten statt Code:** Wo möglich, Presets, Kategorie-Fallbacks und Routen-Listen aus **JSON/YAML** im Repo oder unter konfigurierbaren Pfaden.
2. **Eine Wahrheit:** Keine doppelte Pflege derselben Route in FastAPI **und** React ohne Generator oder Catch-All.
3. **Graceful defaults:** Unbekannte `TOOL_DOMAIN` / `TOOL_BUCKET` degradieren sauber (Warnung + „unsorted“), nicht Crash.
4. **Rückwärtskompatibel:** Bestehende Pfade und APIs bleiben gültig; neue Mechanismen sind opt-in oder Fallback.

---

## Abhängigkeiten (vereinfacht)

```
P0 (Quick wins)     ── unabhängig, sofort Nutzen
P1 (Studio)         ── größter Fork-Gewinn; kann P0 nutzen (JSON-Pfade)
P2 (SPA-Routen)     ── UX für Deep-Links; berührt main.py + agent-ui
P3 (Onboarding-UI)  ── optional; nutzt P0-Katalog + Dashboard install-status
```

Empfohlene Reihenfolge: **P0 → P1 → P2 → (P3)**.

---

## P0 — Quick Wins (Konfiguration & Taxonomie)

### P0.1 — `TOOL_BUCKET` entschärfen

- **Ist:** `registry.py` — `_ALLOWED_ADMIN_BUCKETS` verwirft unbekannte Buckets auf `unsorted`.
- **Soll:** Unbekannte Bucket-Strings **zulassen** (oder automatisch in `unsorted` mit **einem** Log pro neuer Bucket-ID), statt nur „unsorted“ ohne Hinweis auf den gewünschten Namen.
- **Akzeptanz:** Neues Modul mit `TOOL_BUCKET="my_vertical"` erscheint in der Admin-Tool-Liste unter sinnvollem Namen ohne Codeänderung in der Frozenset-Liste.

### P0.2 — UI-Kategorie-Fallback generisch

- **Ist:** `tool_ui_constants.py` — `DOMAIN_CATEGORY_FALLBACK` ist manuell gepflegt.
- **Soll:** Fehlender Eintrag → eindeutiger Default (z. B. `productivity` oder `system`) **plus** optionale Datei `interfaces/tool-ui/domain_category_map.json` (oder unter `dashboard/`) die bei Existenz **geladen** und mit Defaults gemerged wird.
- **Akzeptanz:** Neuer `TOOL_DOMAIN` ohne Map-Eintrag landet in der UI trotzdem in einer konsistenten Sektion; Fork kann nur JSON ergänzen.

### P0.3 — Dashboard-Bundle-Root optional

- **Ist:** `bundle.py` — `dashboard_tree_root()` fix auf `…/dashboard`.
- **Soll:** Env z. B. `AGENT_DASHBOARD_BUNDLES_DIR` — wenn gesetzt, zusätzlich (oder ausschließlich) diesen Pfad scannen; Dokumentation in `.env.example`.
- **Akzeptanz:** Fork kann Bundles nur per Volume mounten, ohne Repo-`dashboard/` zu duplizieren.

### P0.4 — Feature-Router optional (Minimal-Images)

- **Ist:** `main.py` immer `rag_router`, `studio_router`, optional Discord im Lifespan.
- **Soll:** Env-Flags z. B. `AGENT_STUDIO_ENABLED`, `AGENT_RAG_ROUTER_ENABLED` (Default: true) — wenn false, Router nicht `include`en und Lifespan-Teile überspringen.
- **Akzeptanz:** Deployment ohne Comfy/RAG spart Oberfläche und offene Endpunkte.

---

## P1 — Image Studio: Datengetrieben & erweiterbar

### P1.1 — Preset-Definition aus Dateien

- **Ist:** `studio_catalog.py` — großer Python-Dict mit `run_key`, `workflow_file`, `inputs_schema`.
- **Soll:** Ein Verzeichnis z. B. `image_generation/presets/*.json` — Schema: `run_key`, `title`, `description`, `kind`, `engine`, `workflow_file` (relativ zu Repo-Root), `inputs_schema`. Loader merged mit Defaults (`engine_default`, `studio_version`). Comfy-Graph-JSON liegt unter **`image_generation/workflows/`** (siehe `image_generation/README.md`).
- **Akzeptanz:** Neues Preset = neue JSON-Datei + vorhandenes Workflow-JSON; kein Python-Edit für reine UI-Metadaten.

### P1.2 — Runner-Registry statt nur `_RUNNERS`-Dict

- **Ist:** `studio_jobs.py` — `_RUNNERS = {"comfy_txt2img_default": _run_…, …}`.
- **Soll:** Mindestens für **Standard-Flow** ein generischer Pfad: `run_key` → Workflow JSON laden → bestehende `_queue_prompt` / Node-Patch-Logik mit **deklariertem** Mapping (z. B. welche `inputs`-Keys welche Node-IDs treffen), wo möglich aus JSON. Spezialfälle (Inpaint mit Base64-Upload) bleiben als **explizite** Python-Handler registrierbar (`register_studio_runner(run_key, fn)` oder Dict aus Metadaten-Datei).
- **Akzeptanz:** Ein weiteres txt2img-ähnliches Preset ohne neue Python-Funktion, wenn das JSON-Mapping reicht.

### P1.3 — Absolute Docker-Pfade in Tools entfernen

- **Ist (erledigt):** `inpainting_realvision.py` — `WORKFLOW_PATH` = Repo-Root / `image_generation/workflows/inpainting_realvision.json` via `Path(__file__).resolve().parents[4]`.
- **Soll:** Relativ zu Repo-Root / `Path(__file__).resolve().parents[…]` wie andere Module; oder nur aus Env/JSON.
- **Akzeptanz:** Kein `/src/...` Hardcode in Tool-Modulen.

### P1.4 — Dokumentation

- Kurzes Kapitel in **TOOLS.md** oder **README**: „Studio-Preset hinzufügen“ (Schritte 1–3).

---

## P2 — SPA & FastAPI: Eine Routing-Story

### P2.1 — FastAPI: Catch-All für `/app/*`

- **Ist:** Viele `@app.get("/app/…")` Zeilen + `mount /app`.
- **Soll:** Eine Route `GET /app/{full_path:path}` (oder feste Prefix-Regel), die für **alle** unter `/app` liegenden Client-Routen `index.html` liefert — **vor** dem StaticFiles-Mount nur für HTML-Navigation; statische Assets weiter über `/app/assets/…` wie bisher.
- **Vorsicht:** Reihenfolge der Middleware/Route-Registrierung testen (kein Verschlucken von API).

### P2.2 — React: Routen als Daten oder Konvention

- Entweder **eine** `routes.config.ts` (Pfad → Lazy-Component), oder beibehaltene `App.tsx` aber **ohne** FastAPI-Duplikat (P2.1 macht jeden neuen React-`path` ohne FastAPI-Änderung erreichbar).
- **Akzeptanz:** Neue Seite unter `/app/foo` nur in React + ggf. Nav-Link; kein neuer `@app.get` in `main.py`.

---

## P3 — Onboarding / „Katalog“ (optional, später)

### P3.1 — Ein Screen „Ersteinrichtung“

- Kombiniert: `GET /v1/dashboards/install-status` (Kinds, Schema) + Tool-Registry-Metadaten (z. B. Anzahl Packages) + optional P0.4 (fehlende Features).
- Zeigt: „Dashboard-Schema installieren“, „Bereits entdeckte Tools“, Link zu Connections/Secrets.

### P3.2 — Optionale Verknüpfung Dashboard-Kind ↔ Tool-Paket

- Erweiterung `dashboard.kind.json`: z. B. `suggested_tool_packages: ["tasks"]` — nur Anzeige/Docs, keine harte Laufzeitbindung.
- **Akzeptanz:** Fork-Doku kann in einer Datei lesen: „dieses Kind passt zu diesen Tools“.

---

## Test- & Migrations-Checkliste (pro Phase)

- [ ] Bestehende E2E/Unit-Tests grün (Registry, Dashboard-API).
- [ ] Manuell: `/app/...` Deep-Reload nach P2.
- [ ] Studio: bestehende Presets `comfy_txt2img_default` / Inpaint unverändert funktional.

---

## Out of Scope (hier nicht detailliert)

- Öffentliche Plugin-Marketplace-URL oder Remote-Download von Tools.
- Vollständig generischer Comfy-Graph-Interpreter ohne Python (langfristig utopisch).

---

## Kurz: Reihenfolge zum „schön haben“

1. **P0** — weniger Friktion für neue Domains/Bundles/Deployments.
2. **P1** — Studio wirklich plug-in-fähig für Forks.
3. **P2** — keine doppelte Route-Pflege.
4. **P3** — Nutzerführung, wenn P0–P2 stehen.

Bei Bedarf einzelne P0-Punkte in **kleine PRs** splitten (P0.1+P0.2, dann P0.3+P0.4, dann P1, …).
