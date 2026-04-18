import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type InterfaceHints = {
  discord_application_id: string;
  telegram_application_id?: string;
  agent_mode?: "" | "sandbox" | "host";
  agent_mode_effective?: "sandbox" | "host";
  agent_mode_env?: "sandbox" | "host";
};

type OperatorPublic = {
  discord_bot_enabled?: boolean;
  discord_bot_token_configured?: boolean;
  discord_trigger_prefix?: string;
  discord_chat_model?: string;
  telegram_bot_enabled?: boolean;
  telegram_bot_token_configured?: boolean;
  telegram_trigger_prefix?: string;
  telegram_chat_model?: string;
  workspace_upload_max_file_mb?: number | null;
  workspace_upload_allowed_mime?: string;
  workspace_upload_effective_max_bytes?: number;
  workspace_upload_effective_allowed_mime?: string[];
  llm_primary_backend?: "ollama" | "external";
  llm_external_base_url?: string;
  llm_external_api_key_configured?: boolean;
  llm_external_model_default?: string;
  llm_external_model_vlm?: string;
  llm_external_model_agent?: string;
  llm_external_model_coding?: string;
  llm_smart_routing_enabled?: boolean;
  llm_router_ollama_model?: string;
  llm_router_local_confidence_min?: number;
  llm_router_timeout_sec?: number;
  llm_route_long_prompt_chars?: number;
  llm_route_short_local_max_chars?: number;
  llm_route_many_code_fences?: number;
  llm_route_many_messages?: number;
  detail?: unknown;
};

function detailMessage(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return JSON.stringify(d);
  }
  return "Request failed";
}

export function AdminInterfaces() {
  const auth = useAuth();
  const [discordAppId, setDiscordAppId] = useState("");
  const [telegramAppId, setTelegramAppId] = useState("");
  const [agentMode, setAgentMode] = useState<"env" | "sandbox" | "host">("env");
  const [agentModeEnv, setAgentModeEnv] = useState<string>("sandbox");
  const [agentModeEffective, setAgentModeEffective] = useState<string>("sandbox");
  const [bridgeEnabled, setBridgeEnabled] = useState(false);
  const [tokenConfigured, setTokenConfigured] = useState(false);
  const [triggerPrefix, setTriggerPrefix] = useState("!agent ");
  const [chatModel, setChatModel] = useState("");
  const [discordToken, setDiscordToken] = useState("");
  const [tgBridgeEnabled, setTgBridgeEnabled] = useState(false);
  const [tgTokenConfigured, setTgTokenConfigured] = useState(false);
  const [tgTriggerPrefix, setTgTriggerPrefix] = useState("!agent ");
  const [tgChatModel, setTgChatModel] = useState("");
  const [telegramToken, setTelegramToken] = useState("");
  const [uploadMaxMb, setUploadMaxMb] = useState("");
  const [uploadMime, setUploadMime] = useState("");
  const [uploadEffBytes, setUploadEffBytes] = useState<number | null>(null);
  const [uploadEffMime, setUploadEffMime] = useState<string[]>([]);
  const [llmPrimaryBackend, setLlmPrimaryBackend] = useState<"ollama" | "external">("ollama");
  const [llmExternalBaseUrl, setLlmExternalBaseUrl] = useState("");
  const [llmExternalApiKey, setLlmExternalApiKey] = useState("");
  const [llmExtDefault, setLlmExtDefault] = useState("");
  const [llmExtVlm, setLlmExtVlm] = useState("");
  const [llmExtAgent, setLlmExtAgent] = useState("");
  const [llmExtCoding, setLlmExtCoding] = useState("");
  const [llmSmartRouting, setLlmSmartRouting] = useState(false);
  const [llmRouterModel, setLlmRouterModel] = useState("nemotron-3-nano:4b");
  const [llmRouterConfMin, setLlmRouterConfMin] = useState("0.7");
  const [llmRouterTimeoutSec, setLlmRouterTimeoutSec] = useState("12");
  const [llmRouteLongChars, setLlmRouteLongChars] = useState("8000");
  const [llmRouteShortChars, setLlmRouteShortChars] = useState("220");
  const [llmRouteManyFences, setLlmRouteManyFences] = useState("3");
  const [llmRouteManyMsgs, setLlmRouteManyMsgs] = useState("14");
  const [llmKeyConfigured, setLlmKeyConfigured] = useState(false);
  const [extLlmModelIds, setExtLlmModelIds] = useState<string[]>([]);
  const [extLlmModelsLoading, setExtLlmModelsLoading] = useState(false);
  const [extLlmModelsHint, setExtLlmModelsHint] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const baseUrl = `${typeof window !== "undefined" ? window.location.origin : ""}/v1`;

  const load = useCallback(async () => {
    setLoading(true);
    setSaveMsg(null);
    try {
      const [iRes, oRes] = await Promise.all([
        apiFetch("/v1/admin/interfaces", auth),
        apiFetch("/v1/admin/operator-settings", auth),
      ]);
      const iData = (await iRes.json()) as InterfaceHints | { detail?: unknown };
      if (!iRes.ok) {
        setSaveMsg({ ok: false, text: detailMessage(iData) });
        return;
      }
      const row = iData as InterfaceHints;
      setDiscordAppId(row.discord_application_id ?? "");
      setTelegramAppId(row.telegram_application_id ?? "");
      const am = row.agent_mode === "sandbox" || row.agent_mode === "host" ? row.agent_mode : "env";
      setAgentMode(am);
      setAgentModeEnv(row.agent_mode_env ?? "sandbox");
      setAgentModeEffective(row.agent_mode_effective ?? row.agent_mode_env ?? "sandbox");

      const oData = (await oRes.json()) as OperatorPublic | { detail?: unknown };
      if (!oRes.ok) {
        setSaveMsg({ ok: false, text: detailMessage(oData) });
        return;
      }
      const op = oData as OperatorPublic;
      setBridgeEnabled(!!op.discord_bot_enabled);
      setTokenConfigured(!!op.discord_bot_token_configured);
      setTriggerPrefix(
        typeof op.discord_trigger_prefix === "string" ? op.discord_trigger_prefix : "!agent "
      );
      setChatModel(op.discord_chat_model ?? "");
      setTgBridgeEnabled(!!op.telegram_bot_enabled);
      setTgTokenConfigured(!!op.telegram_bot_token_configured);
      setTgTriggerPrefix(
        typeof op.telegram_trigger_prefix === "string" ? op.telegram_trigger_prefix : "!agent "
      );
      setTgChatModel(op.telegram_chat_model ?? "");
      const umb = op.workspace_upload_max_file_mb;
      setUploadMaxMb(umb != null && Number.isFinite(Number(umb)) ? String(umb) : "");
      setUploadMime((op.workspace_upload_allowed_mime ?? "").trim());
      setUploadEffBytes(
        typeof op.workspace_upload_effective_max_bytes === "number"
          ? op.workspace_upload_effective_max_bytes
          : null
      );
      setUploadEffMime(
        Array.isArray(op.workspace_upload_effective_allowed_mime)
          ? op.workspace_upload_effective_allowed_mime
          : []
      );
      setLlmPrimaryBackend(op.llm_primary_backend === "external" ? "external" : "ollama");
      setLlmExternalBaseUrl((op.llm_external_base_url ?? "").trim());
      setLlmKeyConfigured(!!op.llm_external_api_key_configured);
      setLlmExtDefault((op.llm_external_model_default ?? "").trim());
      setLlmExtVlm((op.llm_external_model_vlm ?? "").trim());
      setLlmExtAgent((op.llm_external_model_agent ?? "").trim());
      setLlmExtCoding((op.llm_external_model_coding ?? "").trim());
      setLlmSmartRouting(!!op.llm_smart_routing_enabled);
      setLlmRouterModel((op.llm_router_ollama_model ?? "nemotron-3-nano:4b").trim() || "nemotron-3-nano:4b");
      setLlmRouterConfMin(
        op.llm_router_local_confidence_min != null && Number.isFinite(op.llm_router_local_confidence_min)
          ? String(op.llm_router_local_confidence_min)
          : "0.7"
      );
      setLlmRouterTimeoutSec(
        op.llm_router_timeout_sec != null && Number.isFinite(op.llm_router_timeout_sec)
          ? String(op.llm_router_timeout_sec)
          : "12"
      );
      setLlmRouteLongChars(
        op.llm_route_long_prompt_chars != null && Number.isFinite(op.llm_route_long_prompt_chars)
          ? String(op.llm_route_long_prompt_chars)
          : "8000"
      );
      setLlmRouteShortChars(
        op.llm_route_short_local_max_chars != null && Number.isFinite(op.llm_route_short_local_max_chars)
          ? String(op.llm_route_short_local_max_chars)
          : "220"
      );
      setLlmRouteManyFences(
        op.llm_route_many_code_fences != null && Number.isFinite(op.llm_route_many_code_fences)
          ? String(op.llm_route_many_code_fences)
          : "3"
      );
      setLlmRouteManyMsgs(
        op.llm_route_many_messages != null && Number.isFinite(op.llm_route_many_messages)
          ? String(op.llm_route_many_messages)
          : "14"
      );
      setLlmExternalApiKey("");
    } catch (e) {
      setSaveMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setLoading(false);
    }
  }, [auth]);

  const loadExternalModels = useCallback(async () => {
    setExtLlmModelsHint(null);
    setExtLlmModelsLoading(true);
    try {
      const payload: Record<string, string> = {};
      const bu = llmExternalBaseUrl.trim();
      if (bu) payload.base_url = bu;
      if (llmExternalApiKey.trim()) payload.api_key = llmExternalApiKey.trim();
      const res = await apiFetch("/v1/admin/external-llm/models", auth, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const data = (await res.json()) as { data?: Array<{ id?: string }>; detail?: unknown };
      if (!res.ok) {
        setExtLlmModelIds([]);
        setExtLlmModelsHint(detailMessage(data));
        return;
      }
      const ids = (data.data ?? [])
        .map((m) => (typeof m?.id === "string" ? m.id : null))
        .filter((x): x is string => Boolean(x));
      ids.sort((a, b) => a.localeCompare(b));
      setExtLlmModelIds(ids);
      setExtLlmModelsHint(
        ids.length > 0
          ? `${ids.length} Modellnamen geladen — Vorschläge erscheinen beim Tippen in den Feldern unten.`
          : "Die API hat keine Modelle geliefert (leere Liste)."
      );
    } catch (e) {
      setExtLlmModelIds([]);
      setExtLlmModelsHint(e instanceof Error ? e.message : String(e));
    } finally {
      setExtLlmModelsLoading(false);
    }
  }, [auth, llmExternalBaseUrl, llmExternalApiKey]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    setSaveMsg(null);
    try {
      const putRes = await apiFetch("/v1/admin/interfaces", auth, {
        method: "PUT",
        body: JSON.stringify({
          discord_application_id: discordAppId.trim(),
          telegram_application_id: telegramAppId.trim(),
          agent_mode: agentMode === "env" ? "" : agentMode,
        }),
      });
      const putData = await putRes.json();
      if (!putRes.ok) {
        setSaveMsg({ ok: false, text: detailMessage(putData) });
        return;
      }
      const row = putData as InterfaceHints;
      setDiscordAppId(row.discord_application_id ?? "");
      setTelegramAppId(row.telegram_application_id ?? "");
      const am = row.agent_mode === "sandbox" || row.agent_mode === "host" ? row.agent_mode : "env";
      setAgentMode(am);
      setAgentModeEnv(row.agent_mode_env ?? "sandbox");
      setAgentModeEffective(row.agent_mode_effective ?? row.agent_mode_env ?? "sandbox");

      const patch: Record<string, unknown> = {
        discord_bot_enabled: bridgeEnabled,
        discord_trigger_prefix: triggerPrefix.trim(),
        discord_chat_model: chatModel.trim() || null,
        telegram_bot_enabled: tgBridgeEnabled,
        telegram_trigger_prefix: tgTriggerPrefix.trim(),
        telegram_chat_model: tgChatModel.trim() || null,
      };
      const mbStr = uploadMaxMb.trim();
      if (mbStr === "") {
        patch.workspace_upload_max_file_mb = null;
      } else {
        const n = Number(mbStr);
        if (!Number.isFinite(n) || n < 1) {
          setSaveMsg({
            ok: false,
            text: "Workspace upload: max file MB must be empty (use env) or an integer ≥ 1.",
          });
          return;
        }
        patch.workspace_upload_max_file_mb = Math.min(512, Math.floor(n));
      }
      const mimeStr = uploadMime.trim();
      patch.workspace_upload_allowed_mime = mimeStr === "" ? null : mimeStr;
      patch.llm_primary_backend = llmPrimaryBackend;
      patch.llm_external_base_url = llmExternalBaseUrl.trim() || null;
      patch.llm_external_model_default = llmExtDefault.trim() || null;
      patch.llm_external_model_vlm = llmExtVlm.trim() || null;
      patch.llm_external_model_agent = llmExtAgent.trim() || null;
      patch.llm_external_model_coding = llmExtCoding.trim() || null;
      if (llmExternalApiKey.trim()) {
        patch.llm_external_api_key = llmExternalApiKey.trim();
      }
      const confMin = Number(llmRouterConfMin.trim());
      const rtSec = Number(llmRouterTimeoutSec.trim());
      const longC = Number(llmRouteLongChars.trim());
      const shortC = Number(llmRouteShortChars.trim());
      const manyF = Number(llmRouteManyFences.trim());
      const manyM = Number(llmRouteManyMsgs.trim());
      if (
        !Number.isFinite(confMin) ||
        confMin < 0 ||
        confMin > 1 ||
        !Number.isFinite(rtSec) ||
        rtSec < 1 ||
        rtSec > 120 ||
        !Number.isFinite(longC) ||
        longC < 100 ||
        longC > 500000 ||
        !Number.isFinite(shortC) ||
        shortC < 1 ||
        shortC > 50000 ||
        !Number.isFinite(manyF) ||
        manyF < 1 ||
        manyF > 100 ||
        !Number.isFinite(manyM) ||
        manyM < 1 ||
        manyM > 500
      ) {
        setSaveMsg({
          ok: false,
          text: "Smart routing: Ungültige Zahlen (siehe Hilfetext zu den Grenzen).",
        });
        return;
      }
      patch.llm_smart_routing_enabled = llmSmartRouting;
      patch.llm_router_ollama_model = llmRouterModel.trim() || "nemotron-3-nano:4b";
      patch.llm_router_local_confidence_min = confMin;
      patch.llm_router_timeout_sec = rtSec;
      patch.llm_route_long_prompt_chars = Math.floor(longC);
      patch.llm_route_short_local_max_chars = Math.floor(shortC);
      patch.llm_route_many_code_fences = Math.floor(manyF);
      patch.llm_route_many_messages = Math.floor(manyM);
      if (discordToken.trim()) {
        patch.discord_bot_token = discordToken.trim();
      }
      if (telegramToken.trim()) {
        patch.telegram_bot_token = telegramToken.trim();
      }
      const patchRes = await apiFetch("/v1/admin/operator-settings", auth, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      const patchData = await patchRes.json();
      if (!patchRes.ok) {
        setSaveMsg({
          ok: false,
          text: `Interfaces saved, but operator settings failed: ${detailMessage(patchData)}`,
        });
        return;
      }
      setDiscordToken("");
      setTelegramToken("");
      await load();
      setLlmExternalApiKey("");
      setSaveMsg({
        ok: true,
        text: "Saved. In-process Discord/Telegram bridges pick up token/enable changes after the current session reconnects (or restart the container).",
      });
    } catch (e) {
      setSaveMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    }
  }

  async function clearLlmExternalApiKey() {
    setSaveMsg(null);
    try {
      const res = await apiFetch("/v1/admin/operator-settings", auth, {
        method: "PATCH",
        body: JSON.stringify({ llm_external_api_key: null }),
      });
      const data = await res.json();
      if (!res.ok) {
        setSaveMsg({ ok: false, text: detailMessage(data) });
        return;
      }
      await load();
      setSaveMsg({ ok: true, text: "External LLM API key cleared." });
    } catch (e) {
      setSaveMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    }
  }

  async function clearTelegramToken() {
    setSaveMsg(null);
    try {
      const res = await apiFetch("/v1/admin/operator-settings", auth, {
        method: "PATCH",
        body: JSON.stringify({ telegram_bot_token: null }),
      });
      const data = await res.json();
      if (!res.ok) {
        setSaveMsg({ ok: false, text: detailMessage(data) });
        return;
      }
      await load();
      setSaveMsg({ ok: true, text: "Telegram bot token cleared." });
    } catch (e) {
      setSaveMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    }
  }

  async function clearDiscordToken() {
    setSaveMsg(null);
    try {
      const res = await apiFetch("/v1/admin/operator-settings", auth, {
        method: "PATCH",
        body: JSON.stringify({ discord_bot_token: null }),
      });
      const data = await res.json();
      if (!res.ok) {
        setSaveMsg({ ok: false, text: detailMessage(data) });
        return;
      }
      await load();
      setSaveMsg({ ok: true, text: "Discord bot token cleared." });
    } catch (e) {
      setSaveMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    }
  }

  return (
    <div className="mx-auto max-w-xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-white">Interfaces</h1>
      <p className="mt-2 text-sm text-surface-muted">
        Point OpenAI-compatible clients at <span className="font-mono text-neutral-300">{baseUrl}</span>
        ; use a JWT or user API key as Bearer. Full rules:{" "}
        <a href="/auth/policy" className="text-sky-400 hover:underline">
          GET /auth/policy
        </a>
        . Discord and Telegram gateways and application ids live here too (not on a separate admin page).
      </p>

      {loading ? (
        <p className="mt-6 text-sm text-surface-muted">Loading…</p>
      ) : (
        <>
          <section className="mt-8 rounded-xl border border-surface-border bg-surface-raised p-5">
            <h2 className="text-sm font-medium text-white">Agent mode</h2>
            <p className="mt-2 text-xs text-surface-muted">
              <span className="font-mono text-neutral-400">AGENT_MODE</span> in <span className="font-mono">.env</span>{" "}
              is the default (<span className="text-neutral-300">sandbox</span> = Docker-bound: tools
              always run as <span className="font-mono">container</span> for policy;
              <span className="text-neutral-300"> host</span> = allow host-class overrides per tool
              policy). Here you can override that for the running deployment (saved in the database).
              Choose &quot;Use environment&quot; to clear the override.
            </p>
            <p className="mt-2 text-xs text-surface-muted">
              Env: <span className="font-mono text-neutral-300">{agentModeEnv}</span>
              {" · "}
              Effective: <span className="font-mono text-neutral-300">{agentModeEffective}</span>
            </p>
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="agent-mode">
              Operator override
            </label>
            <select
              id="agent-mode"
              className="mt-1 w-full max-w-md rounded-md border border-surface-border bg-black/20 px-3 py-2 text-sm text-white"
              value={agentMode}
              onChange={(e) => setAgentMode(e.target.value as "env" | "sandbox" | "host")}
            >
              <option value="env">Use environment (AGENT_MODE)</option>
              <option value="sandbox">sandbox (force Docker-bound tool execution)</option>
              <option value="host">host (allow host-class tool policy)</option>
            </select>
          </section>

          <section className="mt-8 rounded-xl border border-surface-border bg-surface-raised p-5">
            <h2 className="text-sm font-medium text-white">Workspace uploads</h2>
            <p className="mt-2 text-xs text-surface-muted">
              Globale Grenzen für Galerie-Uploads (JPEG/PNG/GIF/WebP). Leer = Umgebungsvariablen{" "}
              <span className="font-mono text-neutral-400">AGENT_WORKSPACE_UPLOAD_MAX_MB</span> /{" "}
              <span className="font-mono text-neutral-400">AGENT_WORKSPACE_UPLOAD_ALLOWED_MIME</span>
              .
            </p>
            {uploadEffBytes != null ? (
              <p className="mt-2 text-xs text-surface-muted">
                Aktuell wirksam: max{" "}
                <span className="font-mono text-neutral-300">{uploadEffBytes}</span> Bytes · MIME:{" "}
                <span className="font-mono text-neutral-300">{uploadEffMime.join(", ") || "—"}</span>
              </p>
            ) : null}
            <label className="mt-4 block text-xs text-surface-muted" htmlFor="wu-mb">
              Max. Dateigröße (MB), leer = nur Env/Standard
            </label>
            <input
              id="wu-mb"
              type="number"
              min={1}
              max={512}
              className="mt-1 w-full max-w-xs rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={uploadMaxMb}
              onChange={(e) => setUploadMaxMb(e.target.value)}
              placeholder="z. B. 10"
            />
            <label className="mt-4 block text-xs text-surface-muted" htmlFor="wu-mime">
              Erlaubte MIME-Typen (kommagetrennt), leer = nur Env/Standard
            </label>
            <input
              id="wu-mime"
              className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={uploadMime}
              onChange={(e) => setUploadMime(e.target.value)}
              placeholder="image/jpeg,image/png,image/gif,image/webp"
            />
          </section>

          <section className="mt-8 rounded-xl border border-surface-border bg-surface-raised p-5">
            <h2 className="text-sm font-medium text-white">Agent-Chat: Backend</h2>
            <p className="mt-2 text-xs text-surface-muted">
              Nur diese eine Auswahl: wo Agent-Chat-Completions laufen.{" "}
              <span className="text-white/85">Kein API-Key in diesem Block</span> — der steht in der nächsten Karte.
            </p>
            <label className="mt-4 block text-xs text-surface-muted" htmlFor="llm-backend">
              Backend
            </label>
            <select
              id="llm-backend"
              className="mt-1 w-full max-w-md rounded-md border border-surface-border bg-black/20 px-3 py-2 text-sm text-white"
              value={llmPrimaryBackend}
              onChange={(e) => setLlmPrimaryBackend(e.target.value as "ollama" | "external")}
            >
              <option value="ollama">Ollama (OLLAMA_BASE_URL)</option>
              <option value="external">Extern (OpenAI-kompatible API)</option>
            </select>
            <p className="mt-3 text-xs text-surface-muted">
              <span className="text-white/80">Ollama</span> = alles über den lokalen Dienst.{" "}
              <span className="text-white/80">Extern</span> = Completions über die in der{" "}
              <span className="text-white/80">nächsten</span> Karte hinterlegte URL + Key (Profil-Modell-IDs dort).
            </p>
          </section>

          <section className="mt-6 rounded-xl border border-surface-border bg-surface-raised p-5">
            <h2 className="text-sm font-medium text-white">Smart LLM-Routing</h2>
            <p className="mt-2 text-xs text-surface-muted">
              Pro Anfrage zwischen lokalem Ollama und externer API wählen (Heuristik + kleines Router-Modell auf
              Ollama). Nur sinnvoll, wenn du <span className="text-white/85">beide</span> Backends nutzen willst
              (externe Zugangsdaten in der nächsten Karte). Gespeichert in der Datenbank — keine Umgebungsvariablen.
            </p>
            <label className="mt-4 flex cursor-pointer items-center gap-2 text-sm text-white">
              <input
                type="checkbox"
                className="rounded border-surface-border"
                checked={llmSmartRouting}
                onChange={(e) => setLlmSmartRouting(e.target.checked)}
              />
              Smart Routing aktivieren
            </label>
            <label className="mt-4 block text-xs text-surface-muted" htmlFor="llm-router-model">
              Router-Modell (Ollama, klein, z. B. 3–6B)
            </label>
            <input
              id="llm-router-model"
              className="mt-1 w-full max-w-md rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={llmRouterModel}
              onChange={(e) => setLlmRouterModel(e.target.value)}
              placeholder="nemotron-3-nano:4b"
              autoComplete="off"
            />
            <div className="mt-4 grid max-w-xl gap-3 sm:grid-cols-2">
              <div>
                <label className="block text-xs text-surface-muted" htmlFor="llm-router-conf">
                  Min. Konfidenz für „lokal“ (0–1)
                </label>
                <input
                  id="llm-router-conf"
                  type="number"
                  step="0.05"
                  min={0}
                  max={1}
                  className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
                  value={llmRouterConfMin}
                  onChange={(e) => setLlmRouterConfMin(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-surface-muted" htmlFor="llm-router-to">
                  Router-Timeout (Sekunden, 1–120)
                </label>
                <input
                  id="llm-router-to"
                  type="number"
                  min={1}
                  max={120}
                  step="1"
                  className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
                  value={llmRouterTimeoutSec}
                  onChange={(e) => setLlmRouterTimeoutSec(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-surface-muted" htmlFor="llm-route-long">
                  Lange letzte User-Nachricht ab (Zeichen) → eher extern
                </label>
                <input
                  id="llm-route-long"
                  type="number"
                  min={100}
                  max={500000}
                  className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
                  value={llmRouteLongChars}
                  onChange={(e) => setLlmRouteLongChars(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-surface-muted" htmlFor="llm-route-short">
                  Kurze Nachricht bis (Zeichen) → eher lokal
                </label>
                <input
                  id="llm-route-short"
                  type="number"
                  min={1}
                  max={50000}
                  className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
                  value={llmRouteShortChars}
                  onChange={(e) => setLlmRouteShortChars(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-surface-muted" htmlFor="llm-route-fences">
                  Code-Blöcke (Schwelle, ≥)
                </label>
                <input
                  id="llm-route-fences"
                  type="number"
                  min={1}
                  max={100}
                  className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
                  value={llmRouteManyFences}
                  onChange={(e) => setLlmRouteManyFences(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-surface-muted" htmlFor="llm-route-msgs">
                  Viele Turns (über) → eher extern
                </label>
                <input
                  id="llm-route-msgs"
                  type="number"
                  min={1}
                  max={500}
                  className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
                  value={llmRouteManyMsgs}
                  onChange={(e) => setLlmRouteManyMsgs(e.target.value)}
                />
              </div>
            </div>
          </section>

          <section className="mt-6 rounded-xl border border-surface-border bg-surface-raised p-5">
            <h2 className="text-sm font-medium text-white">Externe LLM-Zugangsdaten</h2>
            <p className="mt-2 text-xs text-surface-muted">
              <span className="text-white/85">Eigener Bereich</span> nur für URL, API-Key und externe Modellnamen — nicht
              mit der Backend-Wahl oben vermischt. Diese Werte werden{" "}
              <span className="text-white/85">nur verwendet, wenn Backend = Extern</span>; bei Ollama bleiben sie
              ungenutzt (du kannst sie trotzdem speichern).
            </p>
            <label className="mt-4 block text-xs text-surface-muted" htmlFor="llm-ext-url">
              Base URL (ohne trailing slash). OpenAI: z. B.{" "}
              <span className="font-mono text-neutral-300">https://api.openai.com</span> → es wird{" "}
              <span className="font-mono">/v1/chat/completions</span> angehängt. Google Gemini (OpenAI-kompatibel,{" "}
              <span className="font-mono text-neutral-300">https://ai.google.dev/gemini-api/docs/openai</span>
              , nicht die <span className="font-mono">generateContent</span>-Referenz): z. B.{" "}
              <span className="font-mono text-neutral-300">
                https://generativelanguage.googleapis.com/v1beta/openai
              </span>{" "}
              → wie OpenAI: <span className="font-mono">/v1/chat/completions</span> (vollständig:{" "}
              <span className="font-mono">…/v1beta/openai/v1/chat/completions</span>).
            </label>
            <input
              id="llm-ext-url"
              className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={llmExternalBaseUrl}
              onChange={(e) => setLlmExternalBaseUrl(e.target.value)}
              placeholder="https://api.openai.com"
              autoComplete="off"
            />
            <p className="mt-2 text-xs text-surface-muted">
              API-Key gespeichert: {llmKeyConfigured ? "ja" : "nein"}
            </p>
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="llm-ext-key">
              API-Key (Bearer)
            </label>
            <input
              id="llm-ext-key"
              type="password"
              autoComplete="off"
              className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={llmExternalApiKey}
              onChange={(e) => setLlmExternalApiKey(e.target.value)}
              placeholder={llmKeyConfigured ? "•••••• (neu eintragen zum Ersetzen)" : "Key einfügen"}
            />
            <button
              type="button"
              className="mt-3 rounded-md border border-white/15 bg-white/5 px-3 py-1.5 text-sm text-neutral-200 hover:bg-white/10 disabled:opacity-40"
              disabled={!llmKeyConfigured}
              onClick={() => void clearLlmExternalApiKey()}
            >
              API-Key löschen
            </button>
            <p className="mt-4 text-xs text-surface-muted">
              <span className="text-white/85">Modellliste:</span> Server ruft OpenAI-kompatibles{" "}
              <span className="font-mono text-neutral-400">GET …/v1/models</span> mit gespeicherten oder gerade
              eingetragenen URL/Key auf (nicht jeder Anbieter unterstützt das).
            </p>
            <button
              type="button"
              className="mt-2 rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-1.5 text-sm text-sky-200 hover:bg-sky-500/20 disabled:opacity-40"
              disabled={extLlmModelsLoading}
              onClick={() => void loadExternalModels()}
            >
              {extLlmModelsLoading ? "Lade Modelle…" : "Modelle von API laden"}
            </button>
            {extLlmModelsHint ? (
              <p
                className={`mt-2 text-xs ${
                  extLlmModelIds.length > 0 ? "text-emerald-400/90" : "text-amber-300/90"
                }`}
              >
                {extLlmModelsHint}
              </p>
            ) : null}
            <datalist id="ext-llm-model-ids">
              {extLlmModelIds.map((id) => (
                <option key={id} value={id} />
              ))}
            </datalist>

            <h3 className="mt-6 text-xs font-medium uppercase tracking-wide text-surface-muted">
              Externe Modell-IDs (OpenAI-Namen)
            </h3>
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="llm-ext-def">
              Default (bei externem Backend für Routing nötig, wenn kein Override)
            </label>
            <input
              id="llm-ext-def"
              className="mt-1 w-full max-w-md rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={llmExtDefault}
              onChange={(e) => setLlmExtDefault(e.target.value)}
              placeholder="z. B. gpt-4o-mini"
              list="ext-llm-model-ids"
              autoComplete="off"
            />
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="llm-ext-vlm">
              VLM / Vision (optional, sonst Default)
            </label>
            <input
              id="llm-ext-vlm"
              className="mt-1 w-full max-w-md rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={llmExtVlm}
              onChange={(e) => setLlmExtVlm(e.target.value)}
              list="ext-llm-model-ids"
              autoComplete="off"
            />
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="llm-ext-agent">
              Profil Agent (optional)
            </label>
            <input
              id="llm-ext-agent"
              className="mt-1 w-full max-w-md rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={llmExtAgent}
              onChange={(e) => setLlmExtAgent(e.target.value)}
              list="ext-llm-model-ids"
              autoComplete="off"
            />
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="llm-ext-coding">
              Profil Coding (optional)
            </label>
            <input
              id="llm-ext-coding"
              className="mt-1 w-full max-w-md rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={llmExtCoding}
              onChange={(e) => setLlmExtCoding(e.target.value)}
              list="ext-llm-model-ids"
              autoComplete="off"
            />
          </section>

          <section className="mt-6 rounded-xl border border-surface-border bg-surface-raised p-5">
            <h2 className="text-sm font-medium text-white">Discord</h2>
            <p className="mt-2 text-xs text-surface-muted">
              Application id is a hint for integrations. The in-process bridge runs inside agent-layer; users link their
              numeric Discord user id under <strong className="text-neutral-300">Settings → Connections</strong>. With a
              trigger prefix, only messages that start with it are handled; leave the prefix field empty so the bot
              reacts to <strong className="text-neutral-300">every</strong> text message in the channel (only linked
              users; noisy in busy servers). Chat runs in-process as the linked AgentLayer user.
            </p>
            <label className="mt-4 block text-xs text-surface-muted" htmlFor="discord-id">
              Discord application ID
            </label>
            <input
              id="discord-id"
              className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={discordAppId}
              onChange={(e) => setDiscordAppId(e.target.value)}
              autoComplete="off"
              inputMode="numeric"
            />

            <h3 className="mt-6 text-xs font-medium uppercase tracking-wide text-surface-muted">In-process bridge</h3>
            <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm text-white">
              <input
                type="checkbox"
                className="rounded border-surface-border"
                checked={bridgeEnabled}
                onChange={(e) => setBridgeEnabled(e.target.checked)}
              />
              Enable Discord bridge
            </label>
            <p className="mt-2 text-xs text-surface-muted">Token stored: {tokenConfigured ? "yes" : "no"}</p>
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="d-token">
              Discord bot token (Developer Portal)
            </label>
            <input
              id="d-token"
              type="password"
              autoComplete="off"
              className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={discordToken}
              onChange={(e) => setDiscordToken(e.target.value)}
              placeholder={tokenConfigured ? "•••••• (enter new value to replace)" : "paste token"}
            />
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="prefix">
              Message prefix (must match start of message); <strong className="text-neutral-300">empty</strong> = no
              prefix (every message is a prompt)
            </label>
            <input
              id="prefix"
              className="mt-1 w-full max-w-md rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={triggerPrefix}
              onChange={(e) => setTriggerPrefix(e.target.value)}
              placeholder="e.g. !agent  — leave empty for no prefix"
            />
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="model">
              Ollama model id (empty = server default)
            </label>
            <input
              id="model"
              className="mt-1 w-full max-w-md rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={chatModel}
              onChange={(e) => setChatModel(e.target.value)}
              placeholder="e.g. nemotron-3-nano:4b"
            />
            <button
              type="button"
              className="mt-3 rounded-md border border-white/15 bg-white/5 px-3 py-1.5 text-sm text-neutral-200 hover:bg-white/10 disabled:opacity-40"
              disabled={!tokenConfigured}
              onClick={() => void clearDiscordToken()}
            >
              Clear Discord token
            </button>
          </section>

          <section className="mt-6 rounded-xl border border-surface-border bg-surface-raised p-5">
            <h2 className="text-sm font-medium text-white">Telegram</h2>
            <p className="mt-2 text-xs text-surface-muted">
              Bot username / hint for integrations. The in-process bridge runs inside agent-layer; users link their
              numeric Telegram user id under <strong className="text-neutral-300">Settings → Connections</strong>. With a
              trigger prefix, only messages that start with it are handled; leave the prefix field empty so the bot
              reacts to <strong className="text-neutral-300">every</strong> text message (only linked users; in groups
              set @BotFather <span className="font-mono">/setprivacy</span> to <strong className="text-neutral-300">Disable</strong>{" "}
              so the bot sees normal messages). Chat runs in-process as the linked AgentLayer user.
            </p>
            <label className="mt-4 block text-xs text-surface-muted" htmlFor="telegram-app-hint">
              Telegram bot username or note (optional)
            </label>
            <input
              id="telegram-app-hint"
              className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={telegramAppId}
              onChange={(e) => setTelegramAppId(e.target.value)}
              autoComplete="off"
              placeholder="@YourBotName"
            />

            <h3 className="mt-6 text-xs font-medium uppercase tracking-wide text-surface-muted">In-process bridge</h3>
            <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm text-white">
              <input
                type="checkbox"
                className="rounded border-surface-border"
                checked={tgBridgeEnabled}
                onChange={(e) => setTgBridgeEnabled(e.target.checked)}
              />
              Enable Telegram bridge
            </label>
            <p className="mt-2 text-xs text-surface-muted">Token stored: {tgTokenConfigured ? "yes" : "no"}</p>
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="tg-token">
              Telegram bot token (@BotFather)
            </label>
            <input
              id="tg-token"
              type="password"
              autoComplete="off"
              className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={telegramToken}
              onChange={(e) => setTelegramToken(e.target.value)}
              placeholder={tgTokenConfigured ? "•••••• (enter new value to replace)" : "paste token"}
            />
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="tg-prefix">
              Message prefix (must match start of message); <strong className="text-neutral-300">empty</strong> = no
              prefix (every text message is a prompt)
            </label>
            <input
              id="tg-prefix"
              className="mt-1 w-full max-w-md rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={tgTriggerPrefix}
              onChange={(e) => setTgTriggerPrefix(e.target.value)}
              placeholder="e.g. !agent  — leave empty for no prefix"
            />
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="tg-model">
              Ollama model id (empty = server default)
            </label>
            <input
              id="tg-model"
              className="mt-1 w-full max-w-md rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={tgChatModel}
              onChange={(e) => setTgChatModel(e.target.value)}
              placeholder="e.g. nemotron-3-nano:4b"
            />
            <button
              type="button"
              className="mt-3 rounded-md border border-white/15 bg-white/5 px-3 py-1.5 text-sm text-neutral-200 hover:bg-white/10 disabled:opacity-40"
              disabled={!tgTokenConfigured}
              onClick={() => void clearTelegramToken()}
            >
              Clear Telegram token
            </button>
          </section>

          <div className="mt-6 flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
              onClick={() => void save()}
            >
              Save
            </button>
          </div>
          {saveMsg ? (
            <p className={`mt-3 text-sm ${saveMsg.ok ? "text-emerald-400" : "text-red-400"}`}>
              {saveMsg.text}
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
