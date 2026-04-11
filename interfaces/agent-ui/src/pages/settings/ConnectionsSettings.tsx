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
};

function secretKeysForPackage(m: ToolsMeta): string[] {
  const raw = m.secrets_required ?? m.requires ?? [];
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

function optionLabel(key: string, forms: Record<string, UserSecretFormSpec>): string {
  const t = forms[key]?.title?.trim();
  return t ? `${key} — ${t}` : key;
}

export function ConnectionsSettings() {
  const auth = useAuth();
  const [meta, setMeta] = useState<ToolsMeta[]>([]);
  const [services, setServices] = useState<string[]>([]);
  const [secretsUnavailable, setSecretsUnavailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState("");
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
      const label = (m.TOOL_LABEL || m.id || "").trim() || pid;
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

  const activeForm = selectedKey ? formsByKey[selectedKey] : undefined;

  useEffect(() => {
    setFieldValues({});
    setRawJson("");
  }, [selectedKey]);

  async function saveSecret() {
    const sk = selectedKey.trim().toLowerCase();
    if (!sk) {
      setMsg("Choose a connection (service key) first.");
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
        setMsg("Enter a secret value or use the raw JSON field.");
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
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }

  const orphanServices = services.filter((s) => !catalogKeys.includes(s));

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-white">Connections</h1>
        <p className="mt-2 text-sm text-surface-muted">
          Credentials are stored per <span className="font-mono">service_key</span> (encrypted on the server).{" "}
          <strong className="font-medium text-neutral-300">Known tools</strong> can ship a small form schema in the tool
          module (<span className="font-mono">TOOL_USER_SECRET_FORMS</span>) so this page shows the right fields — e.g. Gmail
          wants your address plus a Google <strong>App Password</strong>, not your normal login password. Anything without
          a form still uses the raw JSON area below.
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
          Keys declared by packages you are allowed to use. For calendar, <span className="font-mono">google_calendar</span>{" "}
          and <span className="font-mono">calendar_ics</span> use the same URL — storing one is enough for the tool to work.
        </p>
        </div>
        <ul className="divide-y divide-white/5">
          {keyUsage.length === 0 && !loading ? (
            <li className="px-4 py-6 text-sm text-surface-muted">
              No packages declare secrets in the current catalog.
            </li>
          ) : (
            keyUsage.map(([key, info]) => {
              const ok = services.includes(key);
              const hasForm = !!formsByKey[key];
              return (
                <li key={key} className="flex flex-col gap-2 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
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
                        ok ? "rounded bg-emerald-500/15 px-2 py-1 text-xs text-emerald-300" : "rounded bg-amber-500/15 px-2 py-1 text-xs text-amber-200"
                      }
                    >
                      {ok ? "saved" : "missing"}
                    </span>
                    {ok && !secretsUnavailable ? (
                      <button
                        type="button"
                        className="text-xs text-red-400/90 hover:text-red-300 hover:underline"
                        onClick={() => void deleteSecret(key)}
                      >
                        Remove
                      </button>
                    ) : null}
                  </div>
                </li>
              );
            })
          )}
        </ul>
      </section>

      <section className="rounded-xl border border-surface-border bg-black/20 p-5">
        <h2 className="text-sm font-medium text-white">Add or update</h2>
        <p className="mt-1 text-xs text-surface-muted">
          Pick the connection, fill the fields (when the tool defines them), then save once.
        </p>

        <div className="mt-4 space-y-4">
          <label className="block text-xs text-surface-muted">
            Connection (service key)
            <select
              className="mt-1 block w-full rounded-md border border-surface-border bg-black/30 px-3 py-2 text-sm text-white"
              value={selectedKey}
              onChange={(e) => setSelectedKey(e.target.value)}
              disabled={secretsUnavailable}
            >
              <option value="">Select…</option>
              {catalogKeys.map((k) => (
                <option key={k} value={k}>
                  {optionLabel(k, formsByKey)}
                </option>
              ))}
              {orphanServices.map((k) => (
                <option key={`stored-${k}`} value={k}>
                  {k} (saved only — no catalog form)
                </option>
              ))}
            </select>
          </label>

          {selectedKey && activeForm?.help ? (
            <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs leading-relaxed text-neutral-300">
              {activeForm.title ? (
                <p className="mb-1 font-medium text-neutral-200">{activeForm.title}</p>
              ) : null}
              <p className="text-surface-muted">{activeForm.help}</p>
            </div>
          ) : null}

          {selectedKey && activeForm?.fields?.length ? (
            <div className="space-y-3">
              {activeForm.fields.map((f) => {
                const id = `sec-${selectedKey}-${f.name}`;
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
          ) : selectedKey ? (
            <label className="block text-xs text-surface-muted">
              Secret (plain text or JSON)
              <textarea
                className="mt-1 min-h-[7rem] w-full rounded-md border border-surface-border bg-black/30 px-3 py-2 font-mono text-xs text-white placeholder:text-neutral-600"
                placeholder='{"token":"ghp_…"} or paste app password JSON'
                value={rawJson}
                onChange={(e) => setRawJson(e.target.value)}
                disabled={secretsUnavailable}
                spellCheck={false}
              />
            </label>
          ) : null}

          <button
            type="button"
            disabled={saving || secretsUnavailable || !selectedKey}
            className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-40"
            onClick={() => void saveSecret()}
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </section>

      <p className="text-xs text-surface-muted">
        Tool authors: add <span className="font-mono">TOOL_USER_SECRET_FORMS</span> next to{" "}
        <span className="font-mono">TOOL_REQUIRES</span> / <span className="font-mono">TOOL_SECRETS_REQUIRED</span> so this
        UI stays in sync with what each tool reads server-side. See <span className="font-mono">gmail.py</span> /{" "}
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
