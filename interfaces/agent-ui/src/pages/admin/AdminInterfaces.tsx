import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type InterfaceHints = {
  optional_connection_key: string;
  discord_application_id: string;
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
  const [loading, setLoading] = useState(true);
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [copyMsg, setCopyMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const baseUrl = `${typeof window !== "undefined" ? window.location.origin : ""}/v1`;

  const load = useCallback(async () => {
    setLoading(true);
    setSaveMsg(null);
    try {
      const res = await apiFetch("/v1/admin/interfaces", auth);
      const data = (await res.json()) as InterfaceHints | { detail?: unknown };
      if (!res.ok) {
        setSaveMsg({ ok: false, text: detailMessage(data) });
        return;
      }
      const row = data as InterfaceHints;
      setOptionalConnectionKey(row.optional_connection_key ?? "");
      setDiscordAppId(row.discord_application_id ?? "");
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
    try {
      const res = await apiFetch("/v1/admin/interfaces", auth, {
        method: "PUT",
        body: JSON.stringify({
          optional_connection_key: optionalConnectionKey,
          discord_application_id: discordAppId.trim(),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setSaveMsg({ ok: false, text: detailMessage(data) });
        return;
      }
      const row = data as InterfaceHints;
      setOptionalConnectionKey(row.optional_connection_key ?? "");
      setDiscordAppId(row.discord_application_id ?? "");
      setSaveMsg({ ok: true, text: "Saved." });
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
    <div className="h-full min-h-0 overflow-y-auto">
      <div className="mx-auto max-w-xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-white">Interfaces</h1>
      <p className="mt-2 text-sm text-surface-muted">
        Point OpenAI-compatible clients at <span className="font-mono text-neutral-300">{baseUrl}</span>
        . Full rules:{" "}
        <a href="/auth/policy" className="text-sky-400 hover:underline">
          GET /auth/policy
        </a>
        .
      </p>

      {loading ? (
        <p className="mt-6 text-sm text-surface-muted">Loading…</p>
      ) : (
        <>
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
            <label className="mt-3 block text-xs text-surface-muted" htmlFor="discord-id">
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
            <p className="mt-2 text-xs text-surface-muted">
              In the bot, set <span className="font-mono">Authorization: Bearer …</span>. Per request
              add <span className="font-mono">X-Agent-User-Sub: discord:&lt;snowflake&gt;</span> for the
              message author.
            </p>
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
    </div>
  );
}
