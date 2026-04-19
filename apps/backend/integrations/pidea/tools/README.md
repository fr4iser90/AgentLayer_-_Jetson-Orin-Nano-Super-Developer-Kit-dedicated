# PIDEA – DOM- & Selector-Tools (Python)

## Vollständiges Automation-Toolkit (CLI `pidea`)

**Runtime-CLI** (`doctor` / `scan` / `repair` / `snapshot` / `ask` / `read-chat` / `interactive`) liegt unter `src/integrations/pidea/automation/`; DOM-/Selector-Hilfen (Validierung, Finder, Snapshots, Profile-Generator) unter `src/integrations/pidea/domkit/`. Start vom Repo-Root:

```bash
export PIDEA_CDP_HTTP_URL=http://127.0.0.1:9222
./scripts/pidea doctor --ide cursor --version 1.7.17
# oder: PYTHONPATH=src python -m apps.integrations.pidea.automation doctor
```

## Was wir haben (dünnes CLI)

| Tool | Zweck |
|------|--------|
| `scan_chat_selectors.py` | Per CDP (wie der IDE-Agent) **Treffer zählen** für die CSS-Selektoren aus einer Selector-JSON — **schnell prüfen**, ob `userMessages` / `aiMessages` / … noch matchen. |
| API `GET /v1/ide-agent/snapshot` | Gleiche Logik wie im Betrieb: liefert **Text** in `user_messages` / `ai_messages` (zum Lesen im UI), nicht nur Counts. |

## Was das Tool **nicht** tut

- Es **schreibt keine JSON** und **erfindet keine neuen Selektoren**. Wenn `aiMessages` in der JSON falsch ist, siehst du `count=0` — du musst den String **selbst** in `selectors/<ide>/<version>.json` anpassen (oder eine neue Version-Datei anlegen) und Admin/Operator auf diese Version zeigen lassen.
- „Alle Selektoren analysieren“ bedeutet hier: **für jeden Key in der JSON Zähler ausgeben** — nicht automatisch „richtig raten“.

## Bedienung (kurz)

1. Cursor mit Remote-Debugging starten, Composer offen, gleiche CDP-URL wie für den Agent (`PIDEA_CDP_HTTP_URL`).
2. Repo-Root, Abhängigkeiten: `pip install -r requirements-pidea.txt`, `playwright install chromium`.
3. Run:

```bash
export PIDEA_CDP_HTTP_URL=http://127.0.0.1:9222
PYTHONPATH=src python -m apps.integrations.pidea.tools.scan_chat_selectors
```

**Nur die wichtigsten Keys** (input, user/ai, send, …): wie oben.

**Alle Keys** aus `chatSelectors` der gewählten JSON:

```bash
PYTHONPATH=src python -m apps.integrations.pidea.tools.scan_chat_selectors --all src/integrations/pidea/selectors/cursor/1.7.17.json
```

**Output:** Pro Browser-Page: `count=` pro Key; am Ende eine Zeile `summary: userMessages=… aiMessages=…`. **`aiMessages=0`** heißt: Selektor passt nicht mehr zum aktuellen Cursor-DOM — **neuen CSS-String ermitteln** (siehe unten).

## Workflow für „jeden“ (DevTools → JSON)

1. Im Composer eine **AI-Antwort** sichtbar lassen (nicht nur deine Eingabe).
2. **Rechtsklick** auf den **Text** der Antwort → „Untersuchen“ / Inspect.
3. Im Elements-Panel nach oben zum **sinnvollen Container** gehen (eine **logische Nachricht**, nicht jeder innere `<span>`): oft ein Wrapper mit Rollen-Attributen.
4. Im DevTools mit Rechtsklick auf den Knoten → **Copy → Copy selector** (Chrome) — oft zu spezifisch; manchmal besser: Klassen/`data-*`-Attribute **von Hand** zu einem stabilen CSS bauen.
5. String in `chatSelectors.aiMessages` (und ggf. `userMessages`) in der passenden Datei unter `src/integrations/pidea/selectors/…` eintragen, **neue Cursor-Version** als neue `x.y.z.json` anlegen, wenn nötig.
6. `scan_chat_selectors` erneut laufen lassen → `aiMessages` sollte **> 0** sein (so viele wie sichtbare AI-Textblasen — bei zu breitem Selektor auch höher).
7. IDE-Agent/Snapshot testen: lesen die Texte **vollständig** und **ohne** Tool-Karten-Müll? Wenn nein: Selektor enger wählen (z. B. nur Text-Assistant, nicht Tool-Calls).

## Hinweis zu neuerem Cursor-DOM (Beispiel)

In aktuellen Builds tauchen u. a. auf: `data-message-role="human" | "ai"`, `data-message-kind="assistant" | "tool" | …`, Container wie `composer-rendered-message`, Text oft in `.markdown-root`. Die alte Zeile `span.anysphere-markdown-container-root` kann **0 Treffer** liefern, obwohl der Chat da ist — dann z. B. testen (nur als Startpunkt, im DOM verifizieren):

- ` [data-message-role="ai"][data-message-kind="assistant"] .markdown-root`
- oder äußerer Bubble: `.composer-rendered-message[data-message-kind="assistant"]`

**Wichtig:** Zu breit erwischt auch Tool-UI; zu eng fehlen Zeilen. Immer mit Snapshot/API prüfen, ob `ai_messages` sinnvoll lesbar sind.

## Alternative ohne CLI

**`GET /v1/ide-agent/snapshot`** (mit Token) — gleiche Extraktion wie im Server. Logs: `pidea chat [snapshot_only] …`.



Zielbild

Dein Tool sollte:

IDE Version erkennen (/version, DOM, package.json, window vars)
Passende selector profile laden
Selektoren testen
Broken selectors erkennen
Neue selectors automatisch finden
Human review Vorschläge machen
Actions ausführen
open file
open folder
click send
read chat
insert text
switch tabs
accept diff
run command
Snapshots speichern
DOM diffen zwischen Versionen
Neue JSON profiles generieren