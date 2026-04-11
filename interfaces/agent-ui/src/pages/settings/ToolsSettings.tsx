import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";
import { isPackageEnabledForChat, setPackageEnabledForChat } from "../../features/settings/toolPrefs";

type ToolsMeta = {
  id?: string;
  domain?: string;
  admin_bucket?: string;
  tools?: string[];
  TOOL_LABEL?: string;
  TOOL_DESCRIPTION?: string;
  secrets_required?: string[];
  requires?: string[];
  risk_level?: string | number;
};

function secretKeysForPackage(m: ToolsMeta): string[] {
  const raw = m.secrets_required ?? m.requires ?? [];
  if (!Array.isArray(raw)) return [];
  return [...new Set(raw.map((x) => String(x).trim().toLowerCase()).filter(Boolean))];
}

function groupKey(m: ToolsMeta): string {
  const d = (m.domain || "").trim();
  if (d) return d.toLowerCase();
  const b = (m.admin_bucket || "").trim();
  if (b) return b.toLowerCase();
  return "general";
}

function groupTitle(m: ToolsMeta): string {
  const d = (m.domain || "").trim();
  if (d) return d;
  const b = (m.admin_bucket || "").trim();
  if (b) return b;
  return "General";
}

export function ToolsSettings() {
  const auth = useAuth();
  const [meta, setMeta] = useState<ToolsMeta[]>([]);
  const [services, setServices] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [, bump] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await apiFetch("/v1/tools", auth);
      const data = (await res.json()) as { tools_meta?: ToolsMeta[]; detail?: unknown };
      if (!res.ok) {
        setMeta([]);
        setMsg(typeof data.detail === "string" ? data.detail : "Could not load tools");
        return;
      }
      setMeta(Array.isArray(data.tools_meta) ? data.tools_meta : []);

      const sres = await apiFetch("/v1/user/secrets", auth);
      const sdata = (await sres.json()) as { services?: string[] };
      if (sres.ok) {
        setServices((sdata.services ?? []).map((k) => String(k).toLowerCase()));
      } else {
        setServices([]);
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    void load();
  }, [load]);

  const grouped = useMemo(() => {
    const map = new Map<string, { title: string; items: ToolsMeta[] }>();
    for (const m of meta) {
      if (!(m.id || "").trim()) continue;
      const k = groupKey(m);
      if (!map.has(k)) map.set(k, { title: groupTitle(m), items: [] });
      map.get(k)!.items.push(m);
    }
    for (const g of map.values()) {
      g.items.sort((a, b) => (a.id || "").localeCompare(b.id || "", undefined, { sensitivity: "base" }));
    }
    return [...map.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([, v]) => v);
  }, [meta]);

  function refreshToggles() {
    bump((n) => n + 1);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-white">Tools</h1>
        <p className="mt-2 text-sm text-surface-muted">
          Packages listed for your account come from <code className="rounded bg-white/5 px-1 text-xs">GET /v1/tools</code>{" "}
          (operator policy already applied). Use the toggles to <strong className="text-neutral-300">opt out</strong> of
          whole packages for Chat and Agent on <strong className="text-neutral-300">this browser</strong> — the app
          sends <code className="rounded bg-white/5 px-1 text-xs">agent_disabled_tools</code> on each request. Secrets
          live under{" "}
          <Link to="/settings/connections" className="text-sky-400 hover:text-sky-300 hover:underline">
            Connections
          </Link>
          .
        </p>
      </div>

      {msg ? <p className="text-sm text-amber-400">{msg}</p> : null}
      {loading ? <p className="text-sm text-surface-muted">Loading…</p> : null}

      <div className="space-y-10">
        {grouped.map((g) => (
          <section key={g.title}>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-sky-200/90">{g.title}</h2>
            <ul className="flex flex-col gap-3">
              {g.items.map((m) => {
                const pid = (m.id || "").trim();
                const names = (m.tools ?? []).filter((x): x is string => typeof x === "string" && !!x.trim());
                const enabled = names.length ? isPackageEnabledForChat(names) : true;
                const reqs = secretKeysForPackage(m);
                const missing = reqs.filter((k) => !services.includes(k));
                const desc = (m.TOOL_DESCRIPTION || "").trim().slice(0, 280);
                const risk = m.risk_level != null ? String(m.risk_level) : "";
                return (
                  <li
                    key={pid}
                    className="rounded-xl border border-surface-border bg-surface-raised/90 p-4 shadow-sm shadow-black/20"
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0 flex-1 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-sm font-semibold text-white">{pid}</span>
                          {m.TOOL_LABEL ? (
                            <span className="text-xs text-surface-muted">{m.TOOL_LABEL}</span>
                          ) : null}
                          {risk ? (
                            <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-neutral-400">
                              risk:{risk}
                            </span>
                          ) : null}
                          {missing.length ? (
                            <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-200">
                              needs secret: {missing.join(", ")}
                            </span>
                          ) : reqs.length ? (
                            <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] text-emerald-200/90">
                              secrets ok
                            </span>
                          ) : null}
                        </div>
                        {desc ? <p className="text-xs leading-relaxed text-surface-muted">{desc}</p> : null}
                        {names.length ? (
                          <p className="text-[11px] text-neutral-500">
                            <span className="text-surface-muted">Tools:</span>{" "}
                            <span className="font-mono text-neutral-400">{names.join(", ")}</span>
                          </p>
                        ) : (
                          <p className="text-[11px] text-neutral-500">No discrete tool names in catalog metadata.</p>
                        )}
                      </div>
                      <label className="flex shrink-0 cursor-pointer items-center gap-2 whitespace-nowrap text-xs text-neutral-200">
                        <span className="text-surface-muted sm:hidden">Enabled</span>
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-surface-border bg-black/40"
                          checked={enabled}
                          disabled={!names.length}
                          onChange={(e) => {
                            setPackageEnabledForChat(names, e.target.checked);
                            refreshToggles();
                          }}
                        />
                        <span className="hidden sm:inline">On for chat</span>
                      </label>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>

      {!loading && meta.length === 0 ? (
        <p className="text-sm text-surface-muted">No tool packages available for your account.</p>
      ) : null}

      <button
        type="button"
        className="text-xs text-sky-400 hover:text-sky-300 hover:underline"
        onClick={() => void load()}
      >
        Refresh catalog
      </button>
    </div>
  );
}
