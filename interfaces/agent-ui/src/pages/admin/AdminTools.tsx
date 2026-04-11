import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type ToolMeta = {
  id?: string;
  version?: string;
  source?: string;
  tools?: string[];
  tags?: string[];
  capabilities?: string[];
  secrets_required?: string[];
  requires?: string[];
  min_role?: string;
  allowed_tenant_ids?: number[] | null;
  families?: string[];
  domain?: string;
  admin_bucket?: string;
  admin_tags?: string[];
  execution_context?: string;
  os_support?: string[];
  risk_level?: string;
  tool_effective?: Record<
    string,
    {
      enabled: boolean;
      min_role: string;
      allowed_tenant_ids?: number[] | null;
      execution_context?: string;
    }
  >;
  policy_row?: {
    enabled?: boolean;
    min_role?: string;
    allowed_tenant_ids?: number[] | null;
    execution_context?: string | null;
  };
};

type PolicyRow = {
  package_id: string;
  tool_name: string;
  enabled: boolean;
  min_role: "user" | "admin";
  allowed_tenant_ids: number[] | null;
  execution_context: string | null;
};

function parseTenantIdsInput(s: string): number[] | null {
  const trimmed = s.trim();
  if (!trimmed) return null;
  const ids = [
    ...new Set(
      trimmed
        .split(/[\s,;]+/)
        .filter(Boolean)
        .map((p) => parseInt(p, 10))
        .filter((n) => Number.isFinite(n) && n >= 1),
    ),
  ].sort((a, b) => a - b);
  return ids.length ? ids : null;
}

function formatTenantIds(t: number[] | null | undefined): string {
  if (!t?.length) return "";
  return t.join(", ");
}

function sortPackagesById(pkgs: ToolMeta[]): ToolMeta[] {
  return [...pkgs].sort((a, b) =>
    (a.id || "").localeCompare(b.id || "", undefined, { sensitivity: "base" }),
  );
}

const ADMIN_BUCKET_ORDER = [
  "files",
  "network",
  "knowledge",
  "secrets",
  "comms",
  "verticals",
  "meta",
  "media",
  "unsorted",
] as const;

const ADMIN_BUCKET_SET = new Set<string>(ADMIN_BUCKET_ORDER);

const ADMIN_BUCKET_LABELS: Record<string, string> = {
  files: "Local filesystem",
  network: "Outbound network",
  knowledge: "Knowledge & memory",
  secrets: "Secrets & identity",
  comms: "Comms & schedule",
  verticals: "Domain verticals",
  meta: "Meta & factory",
  media: "Media",
  unsorted: "Unsorted (set TOOL_BUCKET in the tool module)",
};

function shouldSubdivideByDomain(pkgs: ToolMeta[]): boolean {
  const keys = new Set(pkgs.map((p) => (p.domain || "").trim().toLowerCase() || "—"));
  return keys.size > 1;
}

function partitionByDomain(pkgs: ToolMeta[]): { domain: string; items: ToolMeta[] }[] {
  return sectionsByDomain(pkgs).map((s) => ({ domain: s.domain, items: s.items }));
}

/** One section per ``TOOL_DOMAIN`` (router category), A–Z; missing domain → „—“. */
function sectionsByDomain(pkgs: ToolMeta[]): { key: string; domain: string; items: ToolMeta[] }[] {
  const map = new Map<string, ToolMeta[]>();
  for (const p of pkgs) {
    const raw = (p.domain || "").trim();
    const key = raw.toLowerCase() || "—";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(p);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([domainKey, items]) => ({
      key: domainKey,
      domain: items[0]?.domain?.trim() || (domainKey === "—" ? "—" : domainKey),
      items: sortPackagesById(items),
    }));
}

function riskBadgeClass(rl: string | undefined): string {
  switch (rl) {
    case "l3":
      return "bg-rose-900/80 text-rose-100";
    case "l2":
      return "bg-amber-900/70 text-amber-100";
    case "l1":
      return "bg-sky-900/60 text-sky-100";
    case "l0":
      return "bg-white/10 text-neutral-200";
    default:
      return "bg-white/5 text-neutral-400";
  }
}

export function AdminTools() {
  const auth = useAuth();
  const [meta, setMeta] = useState<ToolMeta[]>([]);
  const [policyByPkg, setPolicyByPkg] = useState<Record<string, PolicyRow>>({});
  const [tenantInputByPkg, setTenantInputByPkg] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadAdmin = useCallback(async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await apiFetch("/v1/admin/tools", auth);
      const data = (await res.json()) as { tools?: ToolMeta[]; policy_rows?: PolicyRow[] };
      if (!res.ok) {
        setMsg("Failed to load admin tools");
        return;
      }
      const list = data.tools ?? [];
      setMeta(list);
      const rows = data.policy_rows ?? [];
      const map: Record<string, PolicyRow> = {};
      const tin: Record<string, string> = {};
      for (const r of rows) {
        if (r.tool_name === "*" || !r.tool_name) {
          const mr = r.min_role === "admin" ? "admin" : "user";
          const at = r.allowed_tenant_ids ?? null;
          map[r.package_id] = {
            ...r,
            tool_name: "*",
            min_role: mr,
            allowed_tenant_ids: at,
            execution_context: r.execution_context ?? null,
          };
          tin[r.package_id] = formatTenantIds(at);
        }
      }
      for (const t of list) {
        const pid = t.id ?? "";
        if (!pid || map[pid]) continue;
        const te = t.tool_effective?.[t.tools?.[0] ?? ""];
        map[pid] = {
          package_id: pid,
          tool_name: "*",
          enabled: te?.enabled ?? true,
          min_role: te?.min_role === "admin" ? "admin" : "user",
          allowed_tenant_ids: te?.allowed_tenant_ids ?? null,
          execution_context: null,
        };
        tin[pid] = formatTenantIds(te?.allowed_tenant_ids ?? null);
      }
      setPolicyByPkg(map);
      setTenantInputByPkg(tin);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    void loadAdmin();
  }, [loadAdmin]);

  async function reloadRegistry() {
    setBusy(true);
    setMsg(null);
    try {
      const res = await apiFetch("/v1/admin/reload-tools", auth, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail =
          data && typeof data === "object" && "detail" in data
            ? String((data as { detail: unknown }).detail)
            : res.statusText;
        setMsg(detail);
        return;
      }
      await loadAdmin();
      setMsg("Registry reloaded.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function savePolicies() {
    setBusy(true);
    setMsg(null);
    try {
      const policies = packages.map((p) => {
        const pid = p.id ?? "";
        const pol = policyByPkg[pid];
        const row = pol?.package_id
          ? pol
          : {
              package_id: pid,
              tool_name: "*" as const,
              enabled: true,
              min_role: "user" as const,
              allowed_tenant_ids: null,
              execution_context: null,
            };
        const rawTenants = tenantInputByPkg[pid] ?? "";
        const parsed = parseTenantIdsInput(rawTenants);
        return {
          ...row,
          allowed_tenant_ids: parsed,
          execution_context: null,
        };
      });
      const res = await apiFetch("/v1/admin/tool-policies", auth, {
        method: "PUT",
        body: JSON.stringify({ policies }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail =
          data && typeof data === "object" && "detail" in data
            ? String((data as { detail: unknown }).detail)
            : res.statusText;
        setMsg(detail);
        return;
      }
      setMsg("Policy saved.");
      await loadAdmin();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const packages = useMemo(() => meta.filter((m) => m.id), [meta]);

  const groupedPackages = useMemo(() => {
    const buckets: Record<string, ToolMeta[]> = {};
    for (const b of ADMIN_BUCKET_ORDER) buckets[b] = [];
    for (const p of packages) {
      const raw = (p.admin_bucket || "unsorted").trim().toLowerCase() || "unsorted";
      const b = ADMIN_BUCKET_SET.has(raw) ? raw : "unsorted";
      if (!buckets[b]) buckets[b] = [];
      buckets[b].push(p);
    }
    return buckets;
  }, [packages]);

  const totalPackages = packages.length;

  function updatePolicy(pid: string, patch: Partial<PolicyRow>) {
    setPolicyByPkg((prev) => {
      const base: PolicyRow =
        prev[pid] ??
        ({
          package_id: pid,
          tool_name: "*",
          enabled: true,
          min_role: "user",
          allowed_tenant_ids: null,
          execution_context: null,
        } as PolicyRow);
      return {
        ...prev,
        [pid]: {
          ...base,
          ...patch,
          package_id: pid,
          execution_context: null,
        },
      };
    });
  }

  function renderCard(p: ToolMeta) {
    const pid = p.id ?? "";
    const pol = policyByPkg[pid] ?? {
      package_id: pid,
      tool_name: "*",
      enabled: true,
      min_role: "user",
      allowed_tenant_ids: null,
      execution_context: null,
    };
    const sec = p.secrets_required?.length ? p.secrets_required : p.requires;
    const firstTool = p.tools?.[0] ?? "";
    const manCtx = p.execution_context || "container";
    const effCtx =
      (firstTool && p.tool_effective?.[firstTool]?.execution_context) || manCtx;
    const effMr = firstTool && p.tool_effective?.[firstTool]?.min_role;
    const effTenants = firstTool ? p.tool_effective?.[firstTool]?.allowed_tenant_ids : null;

    return (
      <li
        key={pid}
        className="rounded-lg border border-surface-border bg-surface-raised/80 p-3 text-xs text-neutral-200"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="font-mono text-sm font-semibold text-white">{pid}</span>
              {p.version ? <span className="text-[11px] text-surface-muted">v{p.version}</span> : null}
              {p.admin_bucket ? (
                <span className="rounded bg-emerald-950/60 px-1.5 py-0.5 text-[10px] text-emerald-200/90">
                  bucket:{p.admin_bucket}
                </span>
              ) : null}
              {p.domain ? (
                <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-neutral-300">
                  domain:{p.domain}
                </span>
              ) : null}
              <span
                className="rounded bg-violet-900/50 px-1.5 py-0.5 text-[10px] text-violet-100"
                title="Effective run context from manifest + Interfaces (AGENT_MODE). Not set on this page."
              >
                run:{effCtx}
                {effCtx !== manCtx ? (
                  <span className="text-violet-200/80"> (manifest:{manCtx})</span>
                ) : null}
              </span>
              {effMr ? (
                <span
                  className="rounded bg-amber-950/50 px-1.5 py-0.5 text-[10px] text-amber-100"
                  title="Effective minimum role for this caller (manifest + operator policy)."
                >
                  access:min_role={effMr}
                </span>
              ) : null}
              {effTenants?.length ? (
                <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-200">
                  tenants:{effTenants.join(",")}
                </span>
              ) : null}
              {p.os_support?.length ? (
                <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-neutral-300">
                  os:{p.os_support.join(",")}
                </span>
              ) : null}
              {p.risk_level ? (
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${riskBadgeClass(p.risk_level)}`}
                >
                  risk:{p.risk_level}
                </span>
              ) : null}
            </div>
            <p className="truncate font-mono text-[11px] text-surface-muted" title={p.source}>
              {p.source}
            </p>
            <div className="grid gap-1.5 sm:grid-cols-2">
              <div>
                <span className="text-surface-muted">Tools:</span>{" "}
                <span className="break-all font-mono text-[11px] text-neutral-300">
                  {(p.tools ?? []).join(", ")}
                </span>
              </div>
              {p.tags?.length ? (
                <div>
                  <span className="text-surface-muted">Manifest tags:</span>{" "}
                  <span className="text-neutral-300">{p.tags.join(", ")}</span>
                </div>
              ) : null}
              {p.admin_tags?.length ? (
                <div>
                  <span className="text-surface-muted">Registry tags:</span>{" "}
                  <span className="text-neutral-300">{p.admin_tags.join(", ")}</span>
                </div>
              ) : null}
              {p.capabilities?.length ? (
                <div>
                  <span className="text-surface-muted">Capabilities:</span>{" "}
                  <span className="text-neutral-300">{p.capabilities.join(", ")}</span>
                </div>
              ) : null}
              {sec?.length ? (
                <div>
                  <span className="text-surface-muted">Secrets:</span>{" "}
                  <span className="text-amber-200/90">{sec.join(", ")}</span>
                </div>
              ) : null}
              {p.families?.length ? (
                <div>
                  <span className="text-surface-muted">Families:</span>{" "}
                  <span className="text-neutral-300">{p.families.join(", ")}</span>
                </div>
              ) : null}
              <div className="sm:col-span-2">
                <span className="text-surface-muted">Manifest access (optional in module):</span>{" "}
                <span className="font-mono text-neutral-300">
                  TOOL_MIN_ROLE={p.min_role ?? "user"}
                  {p.allowed_tenant_ids?.length
                    ? ` · TOOL_ALLOWED_TENANT_IDS=[${p.allowed_tenant_ids.join(", ")}]`
                    : ""}
                </span>
              </div>
            </div>
          </div>
          <label className="flex shrink-0 cursor-pointer items-center gap-2 whitespace-nowrap text-[11px] text-neutral-200">
            <input
              type="checkbox"
              checked={pol.enabled}
              onChange={(e) => updatePolicy(pid, { enabled: e.target.checked })}
            />
            Enabled
          </label>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 border-t border-white/10 pt-3 sm:grid-cols-2">
          <label className="flex min-w-0 flex-col gap-1 text-[11px] text-surface-muted">
            <span className="text-neutral-400">Minimum role to use this package</span>
            <select
              className="w-full rounded-md border border-surface-border bg-black/30 px-2 py-1.5 text-xs text-white"
              value={pol.min_role}
              onChange={(e) =>
                updatePolicy(pid, { min_role: e.target.value === "admin" ? "admin" : "user" })
              }
            >
              <option value="user">user (all signed-in users)</option>
              <option value="admin">admin only</option>
            </select>
          </label>
          <label className="flex min-w-0 flex-col gap-1 text-[11px] text-surface-muted">
            <span className="text-neutral-400">
              Allowed tenant IDs (empty = any tenant; numbers = <span className="font-mono">tenants.id</span>)
            </span>
            <input
              type="text"
              className="w-full rounded-md border border-surface-border bg-black/30 px-2 py-1.5 font-mono text-xs text-white placeholder:text-neutral-500"
              placeholder="e.g. 1, 2"
              value={tenantInputByPkg[pid] ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                setTenantInputByPkg((prev) => ({ ...prev, [pid]: v }));
              }}
            />
          </label>
        </div>
      </li>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <h1 className="text-2xl font-semibold text-white">Tool registry</h1>
      <p className="mt-2 max-w-2xl text-sm text-surface-muted">
        Grouping comes from each module&apos;s <span className="font-mono">TOOL_BUCKET</span> /{" "}
        <span className="font-mono">TOOL_ADMIN_TAGS</span> (shown as bucket and registry tags).{" "}
        <strong className="font-medium text-neutral-300">Save policy</strong> updates package enabled state,
        minimum role, and optional tenant allowlist (comma-separated <span className="font-mono">tenants.id</span>;
        leave empty for any tenant). Run context is from the manifest and operator interfaces, not this page.{" "}
        <span className="text-neutral-500">
          Assign users to tenants under <span className="text-neutral-400">Admin → Users</span>.
        </span>
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          onClick={() => void loadAdmin()}
        >
          Refresh
        </button>
        <button
          type="button"
          disabled={busy}
          className="rounded-md bg-white/10 px-4 py-2 text-sm font-medium text-white hover:bg-white/15 disabled:opacity-50"
          onClick={() => void reloadRegistry()}
        >
          Reload registry
        </button>
        <button
          type="button"
          disabled={busy || loading}
          className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
          onClick={() => void savePolicies()}
        >
          Save policy
        </button>
      </div>

      {msg ? <p className="mt-3 text-sm text-surface-muted">{msg}</p> : null}

      {loading ? (
        <p className="mt-8 text-sm text-surface-muted">Loading…</p>
      ) : (
        <div className="mt-6 max-h-[min(72vh,calc(100dvh-11rem))] overflow-y-auto overscroll-contain rounded-lg border border-surface-border bg-black/20 pr-1">
          <div className="flex flex-col divide-y divide-white/10">
            {ADMIN_BUCKET_ORDER.map((bucket) => {
              const raw = groupedPackages[bucket] ?? [];
              const sectionPkgs = sortPackagesById(raw);
              if (!sectionPkgs.length) return null;
              const subdiv = shouldSubdivideByDomain(sectionPkgs);
              const blocks = subdiv
                ? partitionByDomain(sectionPkgs)
                : [{ domain: "", items: sectionPkgs }];

              return (
                <details key={bucket} className="group px-2 py-0.5 open:bg-white/[0.03]">
                  <summary className="cursor-pointer list-none py-2.5 pl-1 [&::-webkit-details-marker]:hidden">
                    <div className="flex flex-wrap items-baseline justify-between gap-2 pr-1">
                      <span className="text-sm font-medium text-neutral-200">
                        <span className="font-mono text-neutral-500">{bucket}</span> ·{" "}
                        {ADMIN_BUCKET_LABELS[bucket] ?? bucket}
                      </span>
                      <span className="font-mono text-xs text-surface-muted">
                        {sectionPkgs.length} packages
                      </span>
                    </div>
                  </summary>
                  <div className="space-y-4 pb-4 pl-1">
                    {blocks.map((block) => (
                      <div key={block.domain || "_"}>
                        {subdiv ? (
                          <h3 className="mb-2 border-l-2 border-sky-600/60 pl-2 text-[11px] font-semibold uppercase tracking-wide text-sky-200/90">
                            Domain · {block.domain}{" "}
                            <span className="font-mono font-normal text-surface-muted">
                              ({block.items.length})
                            </span>
                          </h3>
                        ) : null}
                        <ul className="flex flex-col gap-2">{block.items.map((p) => renderCard(p))}</ul>
                      </div>
                    ))}
                  </div>
                </details>
              );
            })}
          </div>
        </div>
      )}

      {!loading && totalPackages === 0 ? (
        <p className="mt-8 text-sm text-surface-muted">No tool packages loaded.</p>
      ) : null}
    </div>
  );
}
