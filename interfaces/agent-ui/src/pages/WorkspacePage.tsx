import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import { apiFetch } from "../lib/api";
import { WorkspaceBlocks } from "../features/workspace/WorkspaceBlocks";
import type { UiLayout, WorkspaceDetail, WorkspaceSummary } from "../features/workspace/types";

function asUiLayout(raw: unknown): UiLayout | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as { version?: number; blocks?: unknown };
  if (!Array.isArray(o.blocks)) return null;
  return { version: Number(o.version) || 1, blocks: o.blocks as UiLayout["blocks"] };
}

type KindCatalogRow = {
  kind: string;
  label: string;
  description: string;
  has_template: boolean;
  has_schema: boolean;
};

function humanizeKindId(kind: string): string {
  const k = (kind || "").trim().toLowerCase();
  if (!k) return "Workspace";
  return k.replace(/_/g, " ").replace(/\b\w/g, (ch) => ch.toUpperCase());
}

function parseKindCatalog(raw: unknown): KindCatalogRow[] {
  if (!Array.isArray(raw)) return [];
  const out: KindCatalogRow[] = [];
  for (const x of raw) {
    if (!x || typeof x !== "object") continue;
    const o = x as Record<string, unknown>;
    const kind = typeof o.kind === "string" ? o.kind.trim().toLowerCase() : "";
    if (!kind) continue;
    const label =
      typeof o.label === "string" && o.label.trim() ? o.label.trim() : humanizeKindId(kind);
    const description =
      typeof o.description === "string" && o.description.trim() ? o.description.trim() : "";
    out.push({
      kind,
      label,
      description,
      has_template: o.has_template === true,
      has_schema: o.has_schema === true,
    });
  }
  out.sort((a, b) => a.kind.localeCompare(b.kind));
  return out;
}

function labelForKind(kind: string, catalog: KindCatalogRow[]): string {
  const k = (kind || "").trim().toLowerCase();
  const row = catalog.find((r) => r.kind === k);
  if (row) return row.label;
  return humanizeKindId(kind);
}

function subtitleForWorkspaceKind(kind: string, catalog: KindCatalogRow[]): string {
  const row = catalog.find((r) => r.kind === (kind || "").trim().toLowerCase());
  if (row?.label) return row.label;
  return humanizeKindId(kind);
}

function normalizeKindList(raw: unknown): string[] | null {
  if (raw === null) return null;
  if (!Array.isArray(raw)) return [];
  const out: string[] = [];
  for (const x of raw) {
    if (typeof x !== "string") continue;
    const k = x.trim().toLowerCase();
    if (k) out.push(k);
  }
  return out;
}

function relativeActivityEn(iso: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "updated";
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

type HubPanel = "home" | "marketplace";

export function WorkspacePage() {
  const auth = useAuth();
  const [schemaInstalled, setSchemaInstalled] = useState<boolean | null>(null);
  const [installBusy, setInstallBusy] = useState(false);
  const [installModalRow, setInstallModalRow] = useState<KindCatalogRow | null>(null);
  const [kindCatalog, setKindCatalog] = useState<KindCatalogRow[]>([]);
  const [installedTemplateKinds, setInstalledTemplateKinds] = useState<string[] | null>(null);
  const [list, setList] = useState<WorkspaceSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hubPanel, setHubPanel] = useState<HubPanel>("home");
  const [newWsModalOpen, setNewWsModalOpen] = useState(false);
  const [marketplaceQuery, setMarketplaceQuery] = useState("");
  const [detail, setDetail] = useState<WorkspaceDetail | null>(null);
  const [data, setData] = useState<Record<string, unknown>>({});
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const uiLayout = useMemo(() => asUiLayout(detail?.ui_layout), [detail]);

  const installableCatalog = useMemo(
    () => kindCatalog.filter((r) => r.has_schema),
    [kindCatalog]
  );

  const installedKindSet = useMemo(() => {
    if (!Array.isArray(installedTemplateKinds)) return new Set<string>();
    return new Set(installedTemplateKinds);
  }, [installedTemplateKinds]);

  const kindsAllowedForNewWorkspace = useMemo(() => {
    const rows = kindCatalog.filter(
      (r) => r.kind === "custom" || (r.has_template && installedKindSet.has(r.kind))
    );
    const custom = rows.find((r) => r.kind === "custom");
    const rest = rows.filter((r) => r.kind !== "custom").sort((a, b) => a.kind.localeCompare(b.kind));
    if (custom) return [custom, ...rest];
    const synthetic: KindCatalogRow = {
      kind: "custom",
      label: "Custom",
      description: "",
      has_template: true,
      has_schema: true,
    };
    return [synthetic, ...rest];
  }, [kindCatalog, installedKindSet]);

  const loadList = useCallback(async () => {
    setError(null);
    const res = await apiFetch("/v1/workspaces", auth);
    if (!res.ok) {
      setError(await res.text());
      setList([]);
      setSchemaInstalled(null);
      setInstalledTemplateKinds(null);
      return;
    }
    const j = (await res.json()) as {
      workspaces?: WorkspaceSummary[];
      schema_installed?: boolean;
      kind_catalog?: unknown;
      installed_template_kinds?: unknown;
    };
    setList(j.workspaces || []);
    const installed = typeof j.schema_installed === "boolean" ? j.schema_installed : true;
    setSchemaInstalled(installed);
    setKindCatalog(parseKindCatalog(j.kind_catalog));
    if (!installed) setInstalledTemplateKinds([]);
    else setInstalledTemplateKinds(normalizeKindList(j.installed_template_kinds));
  }, [auth]);

  const runInstallSingle = useCallback(
    async (kind: string) => {
      setError(null);
      setInstallBusy(true);
      try {
        const res = await apiFetch("/v1/workspaces/install", auth, {
          method: "POST",
          body: JSON.stringify({ kinds: [kind] }),
        });
        if (!res.ok) {
          setError(await res.text());
          return;
        }
        setInstallModalRow(null);
        await loadList();
      } finally {
        setInstallBusy(false);
      }
    },
    [auth, loadList]
  );

  const runInstallTemplates = useCallback(
    async (kind: string) => {
      setError(null);
      setInstallBusy(true);
      try {
        const res = await apiFetch("/v1/workspaces/install-templates", auth, {
          method: "POST",
          body: JSON.stringify({ kinds: [kind] }),
        });
        if (!res.ok) {
          setError(await res.text());
          return;
        }
        setInstallModalRow(null);
        await loadList();
      } finally {
        setInstallBusy(false);
      }
    },
    [auth, loadList]
  );

  useEffect(() => {
    if (!installModalRow) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !installBusy) setInstallModalRow(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [installModalRow, installBusy]);

  const loadDetail = useCallback(
    async (id: string) => {
      setError(null);
      const res = await apiFetch(`/v1/workspaces/${id}`, auth);
      if (!res.ok) {
        setError(await res.text());
        setDetail(null);
        return;
      }
      const j = (await res.json()) as { workspace?: WorkspaceDetail };
      const w = j.workspace;
      if (!w) {
        setDetail(null);
        return;
      }
      setDetail(w);
      setTitle(w.title || "");
      setData(w.data && typeof w.data === "object" ? { ...w.data } : {});
    },
    [auth]
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      await loadList();
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [loadList]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setData({});
      setTitle("");
      return;
    }
    void loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  const recentActivity = useMemo(() => {
    return [...list]
      .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))
      .slice(0, 5);
  }, [list]);

  const marketplaceRows = useMemo(() => {
    const q = marketplaceQuery.trim().toLowerCase();
    return installableCatalog.filter((r) => {
      if (!q) return true;
      return (
        r.kind.includes(q) ||
        r.label.toLowerCase().includes(q) ||
        r.description.toLowerCase().includes(q)
      );
    });
  }, [installableCatalog, marketplaceQuery]);

  const save = async () => {
    if (!selectedId || !detail) return;
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch(`/v1/workspaces/${selectedId}`, auth, {
        method: "PATCH",
        body: JSON.stringify({
          title: title.trim() || detail.title,
          data,
        }),
      });
      if (!res.ok) {
        setError(await res.text());
        return;
      }
      const j = (await res.json()) as { workspace?: WorkspaceDetail };
      if (j.workspace) {
        setDetail(j.workspace);
        setData(
          j.workspace.data && typeof j.workspace.data === "object" ? { ...j.workspace.data } : {}
        );
      }
      await loadList();
    } finally {
      setSaving(false);
    }
  };

  const createWs = async (kind: string) => {
    setError(null);
    const res = await apiFetch("/v1/workspaces", auth, {
      method: "POST",
      body: JSON.stringify({
        kind,
        title: labelForKind(kind, kindCatalog),
      }),
    });
    if (!res.ok) {
      setError(await res.text());
      return;
    }
    const j = (await res.json()) as { workspace?: { id: string } };
    if (j.workspace?.id) {
      setNewWsModalOpen(false);
      setHubPanel("home");
      await loadList();
      setSelectedId(j.workspace.id);
    }
  };

  const removeWs = async () => {
    if (!selectedId) return;
    if (!window.confirm("Delete this workspace?")) return;
    const res = await apiFetch(`/v1/workspaces/${selectedId}`, auth, {
      method: "DELETE",
    });
    if (!res.ok) {
      setError(await res.text());
      return;
    }
    setSelectedId(null);
    await loadList();
  };

  const deleteWsEntry = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm("Delete this workspace?")) return;
    setError(null);
    const res = await apiFetch(`/v1/workspaces/${id}`, auth, { method: "DELETE" });
    if (!res.ok) {
      setError(await res.text());
      return;
    }
    if (selectedId === id) setSelectedId(null);
    await loadList();
  };

  const openMarketplace = () => {
    setSelectedId(null);
    setHubPanel("marketplace");
  };

  const selectWorkspace = (id: string) => {
    setSelectedId(id);
    setHubPanel("home");
  };

  const confirmInstallMarketRow = (row: KindCatalogRow) => {
    if (!row.has_schema) return;
    setInstallModalRow(row);
  };

  const runInstallFromModal = () => {
    if (!installModalRow) return;
    if (schemaInstalled) void runInstallTemplates(installModalRow.kind);
    else void runInstallSingle(installModalRow.kind);
  };

  if (!loading && schemaInstalled === false) {
    return (
      <div className="h-full min-h-0 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-6 py-10">
          <h1 className="text-xl font-semibold text-white">Marketplace</h1>
          <p className="mt-1 text-sm text-surface-muted">
            Install packs to enable storage. Nothing is created until you add workspaces afterward.
          </p>

          {installableCatalog.length === 0 ? (
            <p className="mt-8 text-sm text-surface-muted">No installable packs under workspace/.</p>
          ) : (
            <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {installableCatalog.map((row) => (
                <li key={row.kind}>
                  <button
                    type="button"
                    onClick={() => confirmInstallMarketRow(row)}
                    className="flex h-full min-h-[148px] w-full flex-col rounded-xl border border-surface-border bg-surface-raised p-5 text-left transition hover:border-sky-500/35 hover:bg-white/[0.03]"
                  >
                    <span className="text-base font-medium text-white">{row.label}</span>
                    {row.description ? (
                      <span className="mt-2 text-sm leading-snug text-surface-muted">{row.description}</span>
                    ) : null}
                    <span className="mt-auto pt-4 text-sm font-medium text-sky-400">Install</span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {error ? (
            <div className="mt-6 rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">
              {error}
            </div>
          ) : null}
        </div>

        {installModalRow ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="presentation">
            <div
              className="absolute inset-0 bg-black/70"
              role="button"
              tabIndex={0}
              aria-label="Close"
              onClick={() => {
                if (!installBusy) setInstallModalRow(null);
              }}
              onKeyDown={(e) => {
                if ((e.key === "Enter" || e.key === " ") && !installBusy) {
                  e.preventDefault();
                  setInstallModalRow(null);
                }
              }}
            />
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="ws-install-title"
              className="relative w-full max-w-md rounded-xl border border-surface-border bg-surface-raised p-6 shadow-xl"
            >
              <h2 id="ws-install-title" className="text-lg font-semibold text-white">
                Install {installModalRow.label}?
              </h2>
              {installModalRow.description ? (
                <p className="mt-2 text-sm text-surface-muted">{installModalRow.description}</p>
              ) : null}
              <p className="mt-3 text-sm text-surface-muted">
                Applies schema for this pack. You still create workspace rows separately.
              </p>
              <div className="mt-6 flex justify-end gap-2">
                <button
                  type="button"
                  disabled={installBusy}
                  className="rounded-lg border border-surface-border px-4 py-2 text-sm text-neutral-200 hover:bg-white/5 disabled:opacity-50"
                  onClick={() => setInstallModalRow(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={installBusy || !installModalRow.has_schema}
                  className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={() => void runInstallFromModal()}
                >
                  {installBusy ? "Installing…" : "Install"}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  if (loading || schemaInstalled === null) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-surface-muted">Loading…</div>
    );
  }

  const sidebar = (
    <aside className="flex w-full shrink-0 flex-col border-surface-border bg-surface-raised/40 md:w-56 md:border-r">
      <div className="border-b border-surface-border p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-surface-muted">Workspaces</p>
        <p className="mt-2 text-[10px] font-semibold uppercase tracking-wider text-white/40">My areas</p>
        <div className="mt-1 max-h-48 min-h-0 overflow-y-auto">
          {list.length === 0 ? (
            <p className="py-2 text-xs text-surface-muted">None yet.</p>
          ) : (
            <ul className="flex flex-col gap-0.5">
              {list.map((w) => (
                <li key={w.id}>
                  <div
                    className={[
                      "flex items-stretch gap-0.5 rounded-md",
                      selectedId === w.id ? "bg-white/15" : "hover:bg-white/5",
                    ].join(" ")}
                  >
                    <button
                      type="button"
                      onClick={() => selectWorkspace(w.id)}
                      className={[
                        "min-w-0 flex-1 px-2 py-2 text-left text-sm",
                        selectedId === w.id ? "text-white" : "text-surface-muted hover:text-neutral-200",
                      ].join(" ")}
                    >
                      <span className="block truncate font-medium">{w.title || w.kind}</span>
                      <span className="block truncate text-[10px] text-white/35">
                        {subtitleForWorkspaceKind(w.kind, kindCatalog)}
                      </span>
                    </button>
                    <button
                      type="button"
                      title="Delete"
                      className="shrink-0 px-2 text-sm text-red-300/90 hover:bg-red-950/50 hover:text-red-200"
                      onClick={(e) => void deleteWsEntry(w.id, e)}
                    >
                      ×
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <div className="flex flex-col gap-1 border-t border-surface-border p-2">
        <button
          type="button"
          onClick={() => {
            setNewWsModalOpen(true);
            setHubPanel("home");
            setSelectedId(null);
          }}
          className="rounded-lg px-2.5 py-2 text-left text-xs text-neutral-200 transition hover:bg-white/5"
        >
          Create new
        </button>
        <button
          type="button"
          disabled
          className="cursor-not-allowed rounded-lg px-2.5 py-2 text-left text-xs text-white/30"
          title="Coming soon"
        >
          Import
        </button>
        <button
          type="button"
          onClick={() => openMarketplace()}
          className={[
            "rounded-lg px-2.5 py-2 text-left text-xs transition hover:bg-white/5",
            !selectedId && hubPanel === "marketplace" ? "bg-white/10 text-white" : "text-neutral-200",
          ].join(" ")}
        >
          Marketplace
        </button>
      </div>
    </aside>
  );

  const hubHomeMain = (
    <div className="mx-auto max-w-3xl space-y-8 py-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => setNewWsModalOpen(true)}
          className="flex flex-col rounded-xl border border-surface-border bg-surface-raised p-6 text-left transition hover:border-sky-500/35 hover:bg-white/[0.03]"
        >
          <span className="text-base font-semibold text-white">New workspace</span>
          <span className="mt-2 text-sm text-surface-muted">Create a dashboard from an installed template.</span>
        </button>
        <button
          type="button"
          onClick={() => openMarketplace()}
          className="flex flex-col rounded-xl border border-surface-border bg-surface-raised p-6 text-left transition hover:border-sky-500/35 hover:bg-white/[0.03]"
        >
          <span className="text-base font-semibold text-white">Marketplace</span>
          <span className="mt-2 text-sm text-surface-muted">Install template packs and extensions.</span>
        </button>
      </div>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-surface-muted">Recent activity</p>
        {recentActivity.length === 0 ? (
          <p className="mt-2 text-sm text-surface-muted">No activity yet.</p>
        ) : (
          <ul className="mt-2 space-y-1.5 text-sm text-neutral-300">
            {recentActivity.map((w) => (
              <li key={w.id}>
                <button
                  type="button"
                  className="w-full rounded-md px-2 py-1.5 text-left hover:bg-white/5"
                  onClick={() => selectWorkspace(w.id)}
                >
                  <span className="text-white">{w.title || w.kind}</span>
                  <span className="text-surface-muted"> — {relativeActivityEn(w.updated_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );

  const marketplaceMain = (
    <div className="min-h-0 flex-1 space-y-4 p-4 md:p-6">
      <div className="flex flex-wrap items-end gap-3">
        <button
          type="button"
          onClick={() => setHubPanel("home")}
          className="text-sm text-sky-400 hover:text-sky-300"
        >
          ← Workspaces
        </button>
      </div>
      <h1 className="text-xl font-semibold text-white">Marketplace</h1>
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[200px] flex-1">
          <label className="mb-1 block text-xs text-surface-muted">Search</label>
          <input
            value={marketplaceQuery}
            onChange={(e) => setMarketplaceQuery(e.target.value)}
            placeholder="Filter by name…"
            className="w-full rounded-lg border border-surface-border bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-sky-500/50"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-surface-muted">Category</label>
          <select
            disabled
            className="rounded-lg border border-surface-border bg-black/30 px-3 py-2 text-sm text-white/50"
            value="all"
            onChange={() => {}}
          >
            <option value="all">All</option>
          </select>
        </div>
      </div>
      {marketplaceRows.length === 0 ? (
        <p className="text-sm text-surface-muted">No packs match this search.</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {marketplaceRows.map((row) => {
            const isInstalled = installedKindSet.has(row.kind);
            return (
              <li
                key={row.kind}
                className="flex flex-col rounded-xl border border-surface-border bg-surface-raised p-5"
              >
                <span className="text-base font-medium text-white">{row.label}</span>
                {row.description ? (
                  <span className="mt-2 text-sm leading-snug text-surface-muted">{row.description}</span>
                ) : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  {isInstalled ? (
                    <span className="rounded-md border border-white/10 px-2 py-1 text-xs text-surface-muted">
                      Installed
                    </span>
                  ) : (
                    <button
                      type="button"
                      disabled={installBusy || !row.has_schema}
                      className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
                      onClick={() => confirmInstallMarketRow(row)}
                    >
                      Install
                    </button>
                  )}
                  {isInstalled && row.has_template ? (
                    <button
                      type="button"
                      className="rounded-lg border border-surface-border px-3 py-1.5 text-sm text-neutral-200 hover:bg-white/5"
                      onClick={() => void createWs(row.kind)}
                    >
                      New workspace
                    </button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );

  let main: ReactNode;
  if (selectedId) {
    main = (
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="shrink-0 border-b border-surface-border px-4 py-3 md:px-6">
          <p className="text-sm text-surface-muted">
            Workspace / <span className="text-white">{detail?.title || title || "…"}</span>
          </p>
        </div>
        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          <nav className="flex shrink-0 gap-1 border-surface-border p-2 md:w-44 md:flex-col md:border-r">
            {(["Overview", "Tasks", "Calendar", "Settings"] as const).map((label, i) => (
              <button
                key={label}
                type="button"
                disabled={i > 0}
                className={[
                  "rounded-md px-3 py-2 text-left text-sm",
                  i === 0 ? "bg-white/10 text-white" : "cursor-not-allowed text-white/35",
                ].join(" ")}
              >
                {label}
              </button>
            ))}
          </nav>
          <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
            {error ? (
              <div className="mb-4 rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">
                {error}
              </div>
            ) : null}
            {!detail ? (
              <p className="text-sm text-surface-muted">Loading…</p>
            ) : (
              <>
                <div className="mb-4 flex flex-wrap items-end gap-3">
                  <div className="min-w-[200px] flex-1">
                    <label className="mb-1 block text-xs text-surface-muted">Title</label>
                    <input
                      className="w-full rounded-lg border border-surface-border bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-sky-500/50"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={saving}
                      className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
                      onClick={() => void save()}
                    >
                      {saving ? "Saving…" : "Save"}
                    </button>
                    <button
                      type="button"
                      className="rounded-lg border border-white/10 px-4 py-2 text-sm text-red-300 hover:bg-red-950/40"
                      onClick={() => void removeWs()}
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <p className="mb-4 text-xs text-surface-muted">
                  Template:{" "}
                  <span className="text-white/80">{subtitleForWorkspaceKind(detail.kind, kindCatalog)}</span>
                </p>
                <WorkspaceBlocks uiLayout={uiLayout} data={data} setData={setData} />
              </>
            )}
          </div>
        </div>
      </div>
    );
  } else if (hubPanel === "marketplace") {
    main = marketplaceMain;
  } else {
    main = (
      <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
        {error ? (
          <div className="mb-4 rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">
            {error}
          </div>
        ) : null}
        {hubHomeMain}
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-0 md:flex-row">
      {sidebar}
      {main}

      {newWsModalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="presentation">
          <div
            className="absolute inset-0 bg-black/70"
            role="button"
            tabIndex={0}
            aria-label="Close"
            onClick={() => setNewWsModalOpen(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setNewWsModalOpen(false);
              }
            }}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="ws-new-title"
            className="relative max-h-[85vh] w-full max-w-md overflow-y-auto rounded-xl border border-surface-border bg-surface-raised p-6 shadow-xl"
          >
            <h2 id="ws-new-title" className="text-lg font-semibold text-white">
              New workspace
            </h2>
            <p className="mt-2 text-sm text-surface-muted">Pick a type (only installed templates).</p>
            <ul className="mt-4 flex flex-col gap-2">
              {kindsAllowedForNewWorkspace.length === 0 ? (
                <li className="text-sm text-surface-muted">Install a pack in Marketplace first.</li>
              ) : (
                kindsAllowedForNewWorkspace.map((row) => (
                  <li key={row.kind}>
                    <button
                      type="button"
                      className="w-full rounded-lg border border-surface-border px-3 py-2 text-left text-sm text-white hover:bg-white/5"
                      onClick={() => void createWs(row.kind)}
                    >
                      {row.label}
                    </button>
                  </li>
                ))
              )}
            </ul>
            <div className="mt-6 flex justify-end">
              <button
                type="button"
                className="rounded-lg border border-surface-border px-4 py-2 text-sm text-neutral-200 hover:bg-white/5"
                onClick={() => setNewWsModalOpen(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {installModalRow && schemaInstalled ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="presentation">
          <div
            className="absolute inset-0 bg-black/70"
            role="button"
            tabIndex={0}
            aria-label="Close"
            onClick={() => {
              if (!installBusy) setInstallModalRow(null);
            }}
            onKeyDown={(e) => {
              if ((e.key === "Enter" || e.key === " ") && !installBusy) {
                e.preventDefault();
                setInstallModalRow(null);
              }
            }}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="ws-tpl-install-title"
            className="relative w-full max-w-md rounded-xl border border-surface-border bg-surface-raised p-6 shadow-xl"
          >
            <h2 id="ws-tpl-install-title" className="text-lg font-semibold text-white">
              Install {installModalRow.label}?
            </h2>
            {installModalRow.description ? (
              <p className="mt-2 text-sm text-surface-muted">{installModalRow.description}</p>
            ) : null}
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                disabled={installBusy}
                className="rounded-lg border border-surface-border px-4 py-2 text-sm text-neutral-200 hover:bg-white/5 disabled:opacity-50"
                onClick={() => setInstallModalRow(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={installBusy || !installModalRow.has_schema}
                className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
                onClick={() => void runInstallTemplates(installModalRow.kind)}
              >
                {installBusy ? "Installing…" : "Install"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
