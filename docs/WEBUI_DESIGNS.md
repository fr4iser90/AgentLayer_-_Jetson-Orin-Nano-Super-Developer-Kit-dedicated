# Open WebUI × Agent Layer — UI- und Produkt-Design

Dieses Dokument ergänzt **[WEBUI_CONTRACT.md](WEBUI_CONTRACT.md)**. Der Contract beschreibt **HTTP, Auth, Header, Endpoints**; hier steht **wo im WebUI-Fork was hingehört** (Workspace, Chat, Badges, Bild-Seite) und welche Prinzipien ihr einhalten solltet.

Zielgruppe: ihr implementiert das im **Open-WebUI-Repo** (Fork); dieses File könnt ihr dorthin kopieren oder per Link referenzieren.

---

## 1. Rollen der beiden Repos

| Repo | Inhalt |
|------|--------|
| **Agent Layer** (dieses) | Multi-User-Auflösung, Chat-Logik, Tools, RAG, Secrets, **Operator-Admin-UI/API**, später Bild-/Workflow-APIs. |
| **Open WebUI (Fork)** | **Nutzung:** Oberfläche, Chat, Routing, Workspace, Bild-Seite, Badges, Formulare — kein Ersatz für Agent-Operator-Admin. |

Die WebUI braucht **keinen** vollen Agent-Code — nur den **Contract** + dieses Design-Dokument für konsistente Umsetzung.

### Admin vs. Nutzung (festgelegt)

- **Agent Layer:** **Operator-Admin** bleibt hier — z. B. Control-Panel (`/control/` wenn ausgeliefert), oder `curl`/interne Tools gegen `GET/POST /v1/admin/*` (Reload-Tools, Create-Tool, RAG-Ingest, …). Hohe Rechte, enges Netz / wenige Personen.
- **Open WebUI:** nur **Endnutzung** gegen den Agent (Auth + Header wie im Contract). Der **WebUI-eigene** Admin (WebUI-Nutzer, Gruppen, …) ist etwas anderes und betrifft nicht die Agent-Backend-Operator-Funktionen.

---

## 2. Multi-User

- **Wahrheit für Nutzer/Tenant** liegt im Agent Layer (DB-User pro externem Sub + Tenant).
- Die WebUI muss auf **jede** Anfrage an den Agent dieselben **Identitäts-Header** setzen (siehe Contract §3), z. B. Open-WebUI-User-Id.
- **Ein gemeinsamer Workspace** pro „Produkt“ ist möglich; Multi-User wird **nicht** durch mehrere Workspaces ersetzt, sondern durch korrektes Header-Forwarding.

---

## 3. Workspace: ein Rahmen, nicht alle Features

**Empfehlung:** **ein** Workspace (oder wenige klare Varianten) als **Rahmen** — nicht jedes Feature als eigener Workspace-Zoo.

| Im Workspace sinnvoll | Besser außerhalb / eigene Route |
|----------------------|----------------------------------|
| Modellwahl, Verbindung zum Agent-Endpoint | — |
| Capabilities/Schalter: „Agent“, „Bild-Pipeline“, ggf. Router-Hinweise | — |
| Kurze Meta-Infos („nutzt Agent Layer“) | — |
| **Vollständige** Tool-Dokumentation | Chat-Badge + Detail-Panel oder Docs-Link |
| Workflow-Auswahl, mehrere Bilder, Maske, Inpaint-Parameter | **Eigene Seite** „Bilder“ / „Studio“ mit Formularen |

So bleibt das Modell-Formular lesbar; schwere Arbeitsabläufe bekommen UI, die dafür gebaut ist.

---

## 4. System-Prompts: eine klare Regel

Wenn „Steuerung über Agent Layer“ gewünscht ist, **festlegen**, wer gewinnt:

- **Variante A:** WebUI-Systemfeld nur für **UI-reine** Zusätze; der **inhaltliche** Systemteil kommt aus dem Agent (Konfig/Policy).
- **Variante B:** WebUI ist führend; Agent Layer hängt nur technische Zusätze an.

Ohne Regel: doppelte oder widersprüchliche Systemblöcke. Diese Entscheidung gehört in eure Runbooks/README des Forks, nicht nur „implizit“.

---

## 5. Chat: Badges / „Welche Tools hat der Agent?“

- **Datenquelle:** `GET /v1/tools` (Contract §6) — registrierte Tool-Specs.
- **UI-Idee:** kleines **Badge** oder Icon neben dem Modell/Titel; Klick öffnet **Popover/Drawer** mit Tool-Namen (und optional Kurzbeschreibung aus dem Schema).
- **Optional schlanker:** Badge zeigt nur **Anzahl** oder **Kategorien** (`GET /v1/router/categories`), Details on demand.
- **Optional kontextnah:** Wenn ihr Router/Domain nutzt, könnt ihr die angezeigte Liste an **aktuelle** `X-Agent-Tool-Domain` / Kategorien koppeln — dann zeigt das Badge „was dieser Chat-Pfad nutzen darf“, nicht zwingend die gesamte Registry.

Capabilities im Workspace können steuern: **Badge/Panel ein- oder ausblenden**, ohne jedes Tool einzeln im Workspace zu pflegen.

---

## 6. Bild-Generierung, Inpaint, Workflows

- **Normaler Chat** bleibt Chat (ggf. mit Tool-Calls an den Agent).
- **Bild-Studio-Seite** (eigene Route im Fork) für:
  - Workflow-Auswahl (ComfyUI o. ä.)
  - mehrere Inputs (Referenz, Maske, …)
  - Inpaint-Bearbeitung, Parameter, Vorschau, Job-Status

**Formular-Unterstützung:** langfristig **schema-getrieben** — der Agent Layer (oder ein dedizierter Dienst) liefert JSON „welche Felder dieser Workflow braucht“; die WebUI rendert einfache Typen (string, number, enum, Bild-Upload mit Rolle). Solange diese APIs noch fehlen (Contract §11 „planned“), sind feste Formulare pro Workflow ein legitimer Zwischenschritt.

---

## 7. Was ihr im WebUI-Fork konkret anfasst

- **Einstellungen:** OpenAI-kompatible Base URL → Agent Layer; Auth-Token; **Header-Forwarding** für User/Tenant.
- **Komponenten:** Badge/Tool-Panel, ggf. Capability-Toggles passend zu eurem Workspace-Modell.
- **Neue Route:** Bild/Studio mit Formularen → später gegen Agent-Layer-Endpoints; bis dahin Stub oder direkter Comfy-Proxy nach eurer Sicherheitspolicy.

---

## 8. Pflege

- Änderungen an **URLs, Auth, JSON-Formen** → **WEBUI_CONTRACT.md** + Changelog dort.
- Änderungen an **Workspace-Konzept, Badges, Seitenstruktur** → dieses Dokument.

---

## Changelog

| Datum | Inhalt |
|-------|--------|
| 2026-04-07 | Erste Fassung (Workspace, Multi-User, Prompts, Badges, Bild-Seite). |
| 2026-04-07 | Admin vs. Nutzung: Operator-Admin im Agent Layer, WebUI nur Nutzung. |
| 2026-04-07 | §9: Workspace-Capability `agent-layer`, eigene Agent-Chat-Route, Tabs Bild, Nutzer-Settings. |

---

## 9. Konkrete Fork-Ideen (Workspace, Agent-Chat, Settings)

### 9.1 Workspace-Modell (`/workspace/models/create`)

- Bestehende Capabilities (z. B. `vision`, `usage`, `citations`) bleiben wie in Open WebUI üblich.
- **Neu:** Capability **`agent-layer`** (oder gleichwertiger Name) mit Tooltip: *Redirects all chat through Agent Layer* — signalisiert: dieses Modell nutzt die konfigurierte Agent-Base-URL + Header, nicht „roh“ nur Ollama.

### 9.2 Routing: Query vs. eigene Route

- **`/?models=agent`** (oder ähnlicher Query) kann ein Modell/Workspace vorauswählen — **optional**, wenn ihr die Standard-Chat-Route beibehalten wollt.
- **Klarer im Fork:** eigene Route, z. B. **`/agent/chat`** oder **`/c/agent`**, statt nur Query-Parameter — einfacher für Deep-Links, Lesezeichen und klare Trennung vom **normalen** Chat.
- **Normaler WebUI-Chat** bleibt unverändert („NORMALER CHAT NICHT!!!!“); alle Agent-spezifischen Verbesserungen nur auf der **dedizierten Agent-Chat-Seite**.

**MVP-Navigation (fix, damit es keine Diskussion mehr ist):**

TOP WA- **Sidebar/Hauptnavigation (Open WebUI):** genau **1** Eintrag: **Agent**
- **Agent-Bereich:** Tabs, die als **echte URLs** funktionieren:
  - **`/agent/chat`** (Default)
  - **`/agent/images`** (Studio; kann anfangs „coming soon“ sein)
  - **`/agent/settings`** (Secrets/Defaults/Diagnostics; kann teilweise „coming soon“ sein)

### 9.3 Agent-Chat (dedizierte Seite)

- Chatten gegen Agent Layer (ein Connection-Endpoint).
- **Badges / Panel:** welche Tools der Agent aktuell einplanen kann (`GET /v1/tools`); optional nach Kategorien (`GET /v1/router/categories`).
- **Manuelle Steuerung:** Nutzer kann **Tool-Kategorien** oder **einzelne Tools** aktivieren/deaktivieren (setzt z. B. `X-Agent-Tool-Domain` / `X-Agent-Router-Categories` oder einen späteren Body/Header-Kontrakt — sobald fest, in **WEBUI_CONTRACT** nachziehen).
- **Tab „Image generation“** (oder Unterroute): Modus wählen → **Formular je nach Workflow** (schema-getrieben oder fest verdrahtet) → **Ausgabe als Bild im Verlauf** (Message mit Bild-Anhang), konsistent mit §6.

### 9.4 Nutzer-Settings (nicht Operator-Admin)

Eigene Seite **„Agent“ / „Integration“** im WebUI-Fork:

| Bereich | Inhalt |
|---------|--------|
| **Tool-Berechtigung** | Was der **Admin** dem Nutzer erlaubt vs. was der Nutzer **für sich** noch abschalten kann (Client-Filter und/oder später Policy im Agent Layer — wenn serverseitig erzwungen, braucht ihr dafür API + Speicher im Backend). |
| **Workflows** | Auswahl/Defaults für Bild-Pipelines (wenn Agent Layer Metadaten liefert). |
| **Credentials / Secrets** | Statt nur OTP + `curl`: **UI** gegen **`/v1/user/secrets`** (Contract) mit normalem Login — OTP bleibt optional für den Chat-Flow ohne Browser. |

**Hinweis:** Server-seitige „Admin erlaubt User X nur Tool Y“ ist heute nicht jedes Mal im Agent Layer modelliert; das kann **Phase 2** sein (Policy-API), während **reine UI-Filter** schon in Phase 1 helfen.

### 9.5 ASCII-Skizzen (Seitenlayout grob)

#### Agent-Chat (dedizierte Route, normaler Chat bleibt unverändert)

```text
/agent/chat
+----------------------------------------------------------------------------------+
| Workspace/Model: [agent-layer]     Tools: [ 12 ]     Categories: [web] [files]   |
| Router: (x) strict   Header preview: X-Agent-Router-Categories=web,files         |
+----------------------------------------------+-----------------------------------+
| Chat                                         | Tools/Context Panel               |
|  [system + history]                          | - Enabled categories (toggles)    |
|                                              | - Enabled tools (optional)        |
|  user: ...                                   | - Tool list / search              |
|  asst: ...  [tool-call badge: read_file]     | - Last tool calls + outputs       |
|                                              | - Errors / retries                |
+----------------------------------------------+-----------------------------------+
| [ message input ...................................................... ] [Send] |
+----------------------------------------------------------------------------------+
```

#### Image / Studio (Workflow → dynamisches Formular → Job → Ergebnis im Verlauf)

```text
/agent/images   (oder Tab in /agent/chat)
+----------------------------------------------------------------------------------+
| Workflow: [ comfy:inpaint_v3  v]   Preset: [fast]   Queue: (2 running)            |
+----------------------------------------------+-----------------------------------+
| Inputs / Form                                | Preview / History                 |
|  - Prompt:  [............................]   |  [preview image]                  |
|  - Negative:[............................]   |  Status: queued/running/done      |
|  - Mode: (txt2img) (img2img) (inpaint)       |  Logs: last steps...              |
|  - Image:  [upload]                          |                                   |
|  - Mask:   [upload/paint] (only in inpaint)  |  History:                         |
|  - Params: steps, cfg, seed, size ...        |   - job #123 -> image + metadata  |
|                                              |   - job #122 -> image + metadata  |
+----------------------------------------------+-----------------------------------+
| [Run workflow]   [Cancel]   [Save as preset]                                    |
+----------------------------------------------------------------------------------+
```

#### Settings → Agent/Integration (Nutzer-Settings, nicht Operator-Admin)

```text
/settings/agent
+----------------------------------------------------------------------------------+
| Agent Layer connection:  https://agent.example.com   Auth: (logged in)           |
+----------------------------------------------------------------------------------+
| Tabs: [Tools] [Workflows] [Secrets] [Diagnostics]                                 |
|                                                                                  |
| Tools:                                                                            |
|  - Allowed by admin (server policy):  web, files, rag                             |
|  - My toggles (client filter):        [x] web  [ ] files  [x] rag                 |
|                                                                                  |
| Workflows:                                                                        |
|  - Default workflow: [ comfy:txt2img_v1 v]                                        |
|  - Favorites: [..]                                                                |
|                                                                                  |
| Secrets (calls /v1/user/secrets):                                                  |
|  - service_key: gmail     [Set/Update] [Delete]                                   |
|  - service_key: comfyui   [Set/Update] [Delete]                                   |
+----------------------------------------------------------------------------------+
```

---

## 10. Implementer-Checkliste (Open WebUI Fork, ohne Rückfragen)

Diese Liste ist absichtlich „do this / call that“, damit man direkt loscoden kann.

### 10.1 Navigation + Routing

- Sidebar/Hauptnavigation: **Agent** → Route **`/agent/chat`**
- Tabs im Agent-Bereich navigieren per URL: **`/agent/chat`**, **`/agent/images`**, **`/agent/settings`**

### 10.2 Capability

- Workspace/Model Capability: **`agent-layer`**
- Bedeutung: Modell/Workspace nutzt Agent Layer als Chat-Backend; UI kann Agent-Defaults aktivieren (Tool-Panel, Default-Kategorien, etc.).

### 10.3 Agent-Chat: Daten laden

Beim Laden von `/agent/chat`:

- `GET {AGENT_BASE}/v1/tools` → Tool-Liste für Badges/Panel
- optional `GET {AGENT_BASE}/v1/router/categories` → Kategorie-Chips

UI-States:

- **401** → Re-Login / Token erneuern
- **Network/5xx** → Retry + Error banner

### 10.4 Agent-Chat: Nachricht senden

**Empfohlen für den Agent-Chat:** `WebSocket /ws/v1/chat` (Duplex), damit die UI **Runden, Tool-Läufe und optional „Schritt für Schritt“** aus Server-Events bauen kann — siehe **`docs/WEBUI_CONTRACT.md` §4.3** (`agent.session`, `agent.llm_round_*`, `agent.tool_*`, `agent.step_wait`, `continue_step`, Toggle **`agent_pause_between_rounds`** im `chat.body`). Modellwahl: **Hybrid-Routing** (Profile/Auto-VLM/Override) und Header **`X-Agent-Model-Profile`** / **`X-Agent-Model-Override`** bzw. gleichnamige Felder am `chat`-Frame — Details im Contract-Abschnitt *Hybrid model routing*.

Alternativ oder parallel für einfache Clients:

- `POST {AGENT_BASE}/v1/chat/completions` (kein Pausieren zwischen internen Runden möglich)
- Optional (wenn Nutzer toggled):
  - Header `X-Agent-Router-Categories: cat1,cat2`
  - oder `X-Agent-Tool-Domain: domain`

### 10.5 Secrets UI (Agent Settings)

Auf `/agent/settings` (oder Untertab):

- Liste: `GET {AGENT_BASE}/v1/user/secrets`
- Upsert: `POST {AGENT_BASE}/v1/user/secrets` mit `{service_key, secret}`
- Delete: `DELETE {AGENT_BASE}/v1/user/secrets/{service_key}`

### 10.6 Nicht implementieren im WebUI (Operator-Admin)

- Keine „Operator-Admin“-Funktionen im WebUI nachbauen (Reload-Tools, Create-Tool, RAG-Ingest) → bleibt im Agent Layer Operator-Panel / internen Tools.