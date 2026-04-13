import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type InterfaceHints = {
  optional_connection_key: string;
  discord_application_id: string;
  agent_mode?: "" | "sandbox" | "host";
  agent_mode_effective?: "sandbox" | "host";
  agent_mode_env?: "sandbox" | "host";
};

type OperatorPublic = {
  discord_bot_enabled?: boolean;
  discord_bot_token_configured?: boolean;
  discord_trigger_prefix?: string;
  discord_chat_model?: string;
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
  const [optionalConnectionKey, setOptionalConnectionKey] = useState("");
  const [discordAppId, setDiscordAppId] = useState("");
  const [agentMode, setAgentMode] = useState<"env" | "sandbox" | "host">("env");
  const [agentModeEnv, setAgentModeEnv] = useState<string>("sandbox");
  const [agentModeEffective, setAgentModeEffective] = useState<string>("sandbox");
  const [bridgeEnabled, setBridgeEnabled] = useState(false);
  const [tokenConfigured, setTokenConfigured] = useState(false);
  const [triggerPrefix, setTriggerPrefix] = useState("!agent ");
  const [chatModel, setChatModel] = useState("");
  const [discordToken, setDiscordToken] = useState("");
  const [loading, setLoading] = useState(true);
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [copyMsg, setCopyMsg] = useState<{ ok: boolean; text: string } | null>(null);

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
      setOptionalConnectionKey(row.optional_connection_key ?? "");
      setDiscordAppId(row.discord_application_id ?? "");
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
      setTriggerPrefix(op.discord_trigger_prefix || "!agent ");
      setChatModel(op.discord_chat_model ?? "");
    } catch (e) {
      setSaveMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    setSaveMsg(null);
    setCopyMsg(null);
    try {
      const putRes = await apiFetch("/v1/admin/interfaces", auth, {
        method: "PUT",
        body: JSON.stringify({
          optional_connection_key: optionalConnectionKey,
          discord_application_id: discordAppId.trim(),
          agent_mode: agentMode === "env" ? "" : agentMode,
        }),
      });
      const putData = await putRes.json();
      if (!putRes.ok) {
        setSaveMsg({ ok: false, text: detailMessage(putData) });
        return;
      }
      const row = putData as InterfaceHints;
      setOptionalConnectionKey(row.optional_connection_key ?? "");
      setDiscordAppId(row.discord_application_id ?? "");
      const am = row.agent_mode === "sandbox" || row.agent_mode === "host" ? row.agent_mode : "env";
      setAgentMode(am);
      setAgentModeEnv(row.agent_mode_env ?? "sandbox");
      setAgentModeEffective(row.agent_mode_effective ?? row.agent_mode_env ?? "sandbox");

      const patch: Record<string, unknown> = {
        discord_bot_enabled: bridgeEnabled,
        discord_trigger_prefix: triggerPrefix.trim() || "!agent ",
        discord_chat_model: chatModel.trim() || null,
      };
      if (discordToken.trim()) {
        patch.discord_bot_token = discordToken.trim();
      }
      const patchRes = await apiFetch("/v1/admin/operator-settings", auth, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      const patchData = await patchRes.json();
      if (!patchRes.ok) {
        setSaveMsg({
          ok: false,
          text: `Interfaces saved, but Discord bridge failed: ${detailMessage(patchData)}`,
        });
        return;
      }
      setDiscordToken("");
      await load();
      setSaveMsg({
        ok: true,
        text: "Saved. In-process Discord bridge picks up token/enable changes after the current Discord session reconnects (or restart the container).",
      });
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

  async function copyKey() {
    setCopyMsg(null);
    if (!optionalConnectionKey) {
      setCopyMsg({ ok: false, text: "Nothing to copy." });
      return;
    }
    try {
      await navigator.clipboard.writeText(optionalConnectionKey);
      setCopyMsg({ ok: true, text: "Copied." });
    } catch {
      setCopyMsg({ ok: false, text: "Copy failed — select and copy manually." });
    }
  }

  return (
    <div className="mx-auto max-w-xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-white">Interfaces</h1>
      <p className="mt-2 text-sm text-surface-muted">
        Point OpenAI-compatible clients at <span className="font-mono text-neutral-300">{baseUrl}</span>
        . Full rules:{" "}
        <a href="/auth/policy" className="text-sky-400 hover:underline">
          GET /auth/policy
        </a>
        . Discord gateway and application id live here too (not on a separate admin page).
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
            <h2 className="text-sm font-medium text-white">External clients</h2>
            <p className="mt-2 text-xs text-surface-muted">
              Optional connection key: if empty and you save, selected routes may work without an{" "}
              <span className="font-mono">Authorization</span> header. If set, clients must send that
              value as Bearer, or use a normal JWT / API key.
            </p>
            <label className="mt-4 block text-xs text-surface-muted" htmlFor="opt-key">
              Optional connection key
            </label>
            <input
              id="opt-key"
              className="mt-1 w-full rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={optionalConnectionKey}
              onChange={(e) => setOptionalConnectionKey(e.target.value)}
              autoComplete="off"
              spellCheck={false}
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                className="rounded-md bg-white/10 px-3 py-1.5 text-sm text-white hover:bg-white/15"
                onClick={() => void copyKey()}
              >
                Copy
              </button>
            </div>
            {copyMsg ? (
              <p className={`mt-2 text-sm ${copyMsg.ok ? "text-emerald-400" : "text-red-400"}`}>
                {copyMsg.text}
              </p>
            ) : null}
          </section>

          <section className="mt-6 rounded-xl border border-surface-border bg-surface-raised p-5">
            <h2 className="text-sm font-medium text-white">Discord</h2>
            <p className="mt-2 text-xs text-surface-muted">
              Application id is a hint for integrations. The in-process bridge runs inside agent-layer; users link their
              numeric Discord user id under <strong className="text-neutral-300">Settings → Connections</strong>. In
              server channels, messages must start with the trigger prefix; chat runs in-process as the linked
              AgentLayer user.
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
              Message prefix in servers (must match start of message)
            </label>
            <input
              id="prefix"
              className="mt-1 w-full max-w-md rounded-md border border-surface-border bg-black/20 px-3 py-2 font-mono text-sm text-white"
              value={triggerPrefix}
              onChange={(e) => setTriggerPrefix(e.target.value)}
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
