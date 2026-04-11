import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type SecretField = {
  name: string;
  label?: string;
  type?: string;
  required?: boolean;
};

type UserSecretFormSpec = {
  title?: string;
  help?: string;
  fields?: SecretField[];
};

type ToolsMeta = {
  id?: string;
  domain?: string;
  tools?: string[];
  secrets_required?: string[];
  requires?: string[];
  TOOL_LABEL?: string;
  user_secret_forms?: Record<string, UserSecretFormSpec>;
  ui?: { display_name?: string; category?: string };
};

function secretKeysForPackage(m: ToolsMeta): string[] {
  const raw = m.secrets_required ?? [];
  if (!Array.isArray(raw)) return [];
  return [...new Set(raw.map((x) => String(x).trim().toLowerCase()).filter(Boolean))];
}

function mergeSecretForms(meta: ToolsMeta[]): Record<string, UserSecretFormSpec> {
  const out: Record<string, UserSecretFormSpec> = {};
  for (const m of meta) {
    const f = m.user_secret_forms;
    if (!f || typeof f !== "object") continue;
    for (const [k, v] of Object.entries(f)) {
      const sk = k.trim().toLowerCase();
      if (!sk || !v || typeof v !== "object") continue;
      out[sk] = v as UserSecretFormSpec;
    }
  }
  return out;
}

export function ConnectionsSettings() {
  const auth = useAuth();
  const [meta, setMeta] = useState<ToolsMeta[]>([]);
  const [services, setServices] = useState<string[]>([]);
  const [secretsUnavailable, setSecretsUnavailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  /** Which connection row is expanded (form + save for that key only). */
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [rawJson, setRawJson] = useState("");
  const [saving, setSaving] = useState(false);

  const formsByKey = useMemo(() => mergeSecretForms(meta), [meta]);

  const load = useCallback(async () => {
    setLoading(true);
    setMsg(null);
    try {
      const tres = await apiFetch("/v1/tools", auth);
      const tdata = (await tres.json()) as { tools_meta?: ToolsMeta[] };
      if (tres.ok) {
        setMeta(Array.isArray(tdata.tools_meta) ? tdata.tools_meta : []);
      } else {
        setMeta([]);
        setMsg("Could not load tool catalog.");
      }

      const sres = await apiFetch("/v1/user/secrets", auth);
      const sdata = (await sres.json()) as { ok?: boolean; services?: string[]; detail?: unknown };
      if (sres.status === 503) {
        setSecretsUnavailable(true);
        setServices([]);
        setMsg(
          typeof sdata.detail === "string"
            ? sdata.detail
            : "Secrets storage is off until the operator sets AGENT_SECRETS_MASTER_KEY.",
        );
        return;
      }
      setSecretsUnavailable(false);
      if (!sres.ok) {
        setServices([]);
        if (!tres.ok) return;
        setMsg(typeof sdata.detail === "string" ? sdata.detail : "Could not list secrets");
        return;
      }
      setServices((sdata.services ?? []).map((k) => String(k).toLowerCase()));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    void load();
  }, [load]);

  const keyUsage = useMemo(() => {
    const map = new Map<string, { ids: string[]; labels: string[] }>();
    for (const m of meta) {
      const pid = (m.id || "").trim() || "—";
      const label = (m.ui?.display_name || m.TOOL_LABEL || m.id || "").trim() || pid;
      for (const k of secretKeysForPackage(m)) {
        if (!map.has(k)) map.set(k, { ids: [], labels: [] });
        const e = map.get(k)!;
        if (!e.ids.includes(pid)) e.ids.push(pid);
        if (!e.labels.includes(label)) e.labels.push(label);
      }
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [meta]);

  const catalogKeys = useMemo(() => keyUsage.map(([k]) => k), [keyUsage]);

  const activeForm = activeKey ? formsByKey[activeKey] : undefined;

  useEffect(() => {
    setFieldValues({});
    setRawJson("");
  }, [activeKey]);

  async function saveSecret() {
    const sk = (activeKey ?? "").trim().toLowerCase();
    if (!sk) {
      setMsg("Open a connection below first.");
      return;
    }

    let payload: { service_key: string; secret: string | Record<string, string> };

    if (activeForm?.fields?.length) {
      const obj: Record<string, string> = {};
      for (const f of activeForm.fields) {
        const n = f.name;
        let v = (fieldValues[n] ?? "").trim();
        if (n === "app_password") v = v.replace(/\s+/g, "");
        obj[n] = v;
      }
      const missing = activeForm.fields.filter((f) => f.required && !obj[f.name]?.trim());
      if (missing.length) {
        setMsg(`Please fill: ${missing.map((f) => f.label || f.name).join(", ")}`);
        return;
      }
      payload = { service_key: sk, secret: obj };
    } else {
      const raw = rawJson.trim();
      if (!raw) {
        setMsg("Enter a secret value or paste JSON in the field below.");
        return;
      }
      try {
        const parsed = JSON.parse(raw) as unknown;
        payload =
          typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
            ? { service_key: sk, secret: parsed as Record<string, string> }
            : { service_key: sk, secret: raw };
      } catch {
        payload = { service_key: sk, secret: raw };
      }
    }

    setSaving(true);
    setMsg(null);
    try {
      const res = await apiFetch("/v1/user/secrets", auth, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
      if (!res.ok) {
        setMsg(typeof data.detail === "string" ? data.detail : "Save failed");
        return;
      }
      setMsg("Saved.");
      setFieldValues({});
      setRawJson("");
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function deleteSecret(key: string) {
    if (!confirm(`Remove secret "${key}"? Tools that depend on it may stop working.`)) return;
    setMsg(null);
    try {
      const res = await apiFetch(`/v1/user/secrets/${encodeURIComponent(key)}`, auth, {
        method: "DELETE",
      });
      const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
      if (!res.ok) {
        setMsg(typeof data.detail === "string" ? data.detail : "Delete failed");
        return;
      }
      setMsg("Removed.");
      if (activeKey === key) {
        setActiveKey(null);
      }
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }

  const orphanServices = services.filter((s) => !catalogKeys.includes(s));

  function toggleKey(key: string) {
    setMsg(null);
    setActiveKey((prev) => (prev === key ? null : key));
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-white">Connections</h1>
        <p className="mt-2 text-sm text-surface-muted">
          Credentials are stored per <span className="font-mono">service_key</span> (encrypted on the server).{" "}
          <strong className="font-medium text-neutral-300">Known tools</strong> can ship a small form schema in the tool
          module (<span className="font-mono">TOOL_USER_SECRET_FORMS</span>) so this page shows the right fields — e.g. Gmail
          wants your address plus a Google <strong>App Password</strong>, not your normal login password. Keys like{" "}
          <span className="font-mono">weather</span> or <span className="font-mono">time</span> are{" "}
          <strong className="font-medium text-neutral-300">names chosen by the tool author</strong> for a secret slot (often an
          API key or URL you paste once). <strong className="font-medium text-neutral-300">Not saved</strong> means you have
          not stored anything for that key yet — not that the key name is invalid.
        </p>
      </div>

      {loading ? <p className="text-sm text-surface-muted">Loading…</p> : null}

      {msg ? (
        <p
          className={`text-sm ${msg === "Saved." || msg === "Removed." ? "text-emerald-400" : "text-amber-400"}`}
        >
          {msg}
        </p>
      ) : null}

      <section className="rounded-xl border border-surface-border bg-surface-raised">
        <div className="border-b border-surface-border px-4 py-3">
          <h2 className="text-sm font-medium text-white">From your tool catalog</h2>
          <p className="mt-0.5 text-xs text-surface-muted">
            Click a row to add or edit that connection. For calendar, <span className="font-mono">google_calendar</span> and{" "}
            <span className="font-mono">calendar_ics</span> use the same URL — storing one is enough for the tool to work.
          </p>
        </div>
        <ul className="divide-y divide-white/5">
          {keyUsage.length === 0 && !loading ? (
            <li className="px-4 py-6 text-sm text-surface-muted">
              No packages declare secrets in the current catalog.
            </li>
          ) : (
            keyUsage.map(([key, info]) => {
              const saved = services.includes(key);
              const hasForm = !!formsByKey[key];
              const open = activeKey === key;
              return (
                <li key={key} className="overflow-hidden">
                  <button
                    type="button"
                    onClick={() => toggleKey(key)}
                    className="flex w-full flex-col gap-2 px-4 py-4 text-left transition hover:bg-white/[0.03] sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm text-white">{key}</span>
                        {hasForm ? (
                          <span className="rounded bg-sky-500/15 px-1.5 py-0.5 text-[10px] text-sky-200">form in UI</span>
                        ) : null}
                      </div>
                      <div className="mt-1 text-xs text-surface-muted">
                        Packages: {info.labels.slice(0, 4).join(", ")}
                        {info.labels.length > 4 ? ` +${info.labels.length - 4}` : ""}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span
                        className={
                          saved
                            ? "rounded bg-emerald-500/15 px-2 py-1 text-xs text-emerald-300"
                            : "rounded bg-neutral-500/20 px-2 py-1 text-xs text-neutral-300"
                        }
                      >
                        {saved ? "saved" : "not saved"}
                      </span>
                      <span className="text-xs text-surface-muted">{open ? "▲" : "▼"}</span>
                    </div>
                  </button>

                  {open ? (
                    <div className="space-y-4 border-t border-white/5 bg-black/20 px-4 py-4">
                      {saved && !secretsUnavailable ? (
                        <div className="flex justify-end">
                          <button
                            type="button"
                            className="text-xs text-red-400/90 hover:text-red-300 hover:underline"
                            onClick={(e) => {
                              e.stopPropagation();
                              void deleteSecret(key);
                            }}
                          >
                            Remove stored secret
                          </button>
                        </div>
                      ) : null}

                      {activeForm?.help ? (
                        <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs leading-relaxed text-neutral-300">
                          {activeForm.title ? (
                            <p className="mb-1 font-medium text-neutral-200">{activeForm.title}</p>
                          ) : null}
                          <p className="text-surface-muted">{activeForm.help}</p>
                        </div>
                      ) : null}

                      {activeForm?.fields?.length ? (
                        <div className="space-y-3">
                          {activeForm.fields.map((f) => {
                            const id = `sec-${key}-${f.name}`;
                            const t = (f.type || "text").toLowerCase();
                            const inputType = t === "password" ? "password" : t === "email" ? "email" : "text";
                            return (
                              <label key={f.name} className="block text-xs text-surface-muted" htmlFor={id}>
                                {f.label || f.name}
                                {f.required ? <span className="text-amber-400/80"> *</span> : null}
                                <input
                                  id={id}
                                  type={inputType}
                                  autoComplete="off"
                                  className="mt-1 block w-full rounded-md border border-surface-border bg-black/30 px-3 py-2 text-sm text-white placeholder:text-neutral-600"
                                  value={fieldValues[f.name] ?? ""}
                                  onChange={(e) => setFieldValues((prev) => ({ ...prev, [f.name]: e.target.value }))}
                                  disabled={secretsUnavailable}
                                />
                              </label>
                            );
                          })}
                        </div>
                      ) : (
                        <label className="block text-xs text-surface-muted">
                          Secret (plain text or JSON)
                          <textarea
                            className="mt-1 min-h-[7rem] w-full rounded-md border border-surface-border bg-black/30 px-3 py-2 font-mono text-xs text-white placeholder:text-neutral-600"
                            placeholder='{"api_key":"…"} or paste token'
                            value={rawJson}
                            onChange={(e) => setRawJson(e.target.value)}
                            disabled={secretsUnavailable}
                            spellCheck={false}
                          />
                        </label>
                      )}

                      <button
                        type="button"
                        disabled={saving || secretsUnavailable}
                        className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-40"
                        onClick={() => void saveSecret()}
                      >
                        {saving ? "Saving…" : "Save"}
                      </button>
                    </div>
                  ) : null}
                </li>
              );
            })
          )}
        </ul>
      </section>

      {orphanServices.length > 0 ? (
        <section className="rounded-xl border border-surface-border bg-black/20 p-5">
          <h2 className="text-sm font-medium text-white">Saved keys not in current catalog</h2>
          <p className="mt-1 text-xs text-surface-muted">
            You have secrets stored under these names, but no enabled package currently lists them. You can still open and
            overwrite or remove them.
          </p>
          <ul className="mt-3 divide-y divide-white/5 rounded-lg border border-white/10">
            {orphanServices.map((k) => {
              const open = activeKey === k;
              return (
                <li key={k}>
                  <button
                    type="button"
                    onClick={() => toggleKey(k)}
                    className="flex w-full items-center justify-between px-3 py-3 text-left text-sm hover:bg-white/[0.03]"
                  >
                    <span className="font-mono text-white">{k}</span>
                    <span className="text-xs text-surface-muted">{open ? "▲" : "▼"}</span>
                  </button>
                  {open ? (
                    <div className="space-y-3 border-t border-white/5 px-3 py-3">
                      <label className="block text-xs text-surface-muted">
                        Secret (plain text or JSON)
                        <textarea
                          className="mt-1 min-h-[6rem] w-full rounded-md border border-surface-border bg-black/30 px-3 py-2 font-mono text-xs text-white"
                          value={rawJson}
                          onChange={(e) => setRawJson(e.target.value)}
                          disabled={secretsUnavailable}
                          spellCheck={false}
                        />
                      </label>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          disabled={saving || secretsUnavailable}
                          className="rounded-md bg-sky-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500 disabled:opacity-40"
                          onClick={() => void saveSecret()}
                        >
                          {saving ? "Saving…" : "Save"}
                        </button>
                        <button
                          type="button"
                          className="text-xs text-red-400/90 hover:text-red-300 hover:underline"
                          onClick={() => void deleteSecret(k)}
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <p className="text-xs text-surface-muted">
        Tool authors: set <span className="font-mono">TOOL_SECRETS_REQUIRED</span> (user secret{" "}
        <span className="font-mono">service_key</span> names) and optional{" "}
        <span className="font-mono">TOOL_USER_SECRET_FORMS</span> so this UI matches what each tool reads server-side.
        See <span className="font-mono">gmail.py</span> /{" "}
        <span className="font-mono">github.py</span>.
      </p>

      <p className="text-xs text-surface-muted">
        End-user tool toggles:{" "}
        <Link to="/settings/tools" className="text-sky-400 hover:text-sky-300 hover:underline">
          Tools
        </Link>
        .
      </p>

      <button
        type="button"
        className="text-xs text-sky-400 hover:text-sky-300 hover:underline"
        onClick={() => void load()}
      >
        Refresh
      </button>
    </div>
  );
}
