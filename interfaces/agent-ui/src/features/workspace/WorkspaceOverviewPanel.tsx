import { useMemo } from "react";
import type { WorkspaceSummary } from "./types";
import { DEFAULT_HUBS, groupWorkspacesByHub, type WorkspaceHubId } from "./workspaceHubNav";

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

function accessHint(role: string | undefined): string {
  if (role === "viewer") return "Read-only";
  if (role === "editor") return "Shared";
  if (role === "co_owner") return "Co-owner";
  return "Owner";
}

function StatCard(props: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-surface-muted">{props.label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-white">{props.value}</p>
      {props.sub ? <p className="mt-0.5 text-xs text-surface-muted">{props.sub}</p> : null}
    </div>
  );
}

export function WorkspaceOverviewPanel(props: {
  list: WorkspaceSummary[];
  kindLabelFor: (kind: string) => string;
  onOpenWorkspace: (id: string) => void;
}) {
  const { list, kindLabelFor, onOpenWorkspace } = props;

  const grouped = useMemo(() => groupWorkspacesByHub(list), [list]);

  const kindCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const w of list) {
      const k = (w.kind || "").trim().toLowerCase() || "—";
      m.set(k, (m.get(k) ?? 0) + 1);
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [list]);

  const sharedWithYou = useMemo(
    () => list.filter((w) => w.access_role && w.access_role !== "owner").length,
    [list]
  );

  const hubsWithItems = useMemo(() => {
    const order = DEFAULT_HUBS.map((h) => h.id);
    return order.filter((id) => (grouped[id as WorkspaceHubId]?.items.length ?? 0) > 0);
  }, [grouped]);

  if (list.length === 0) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 py-6">
        <div>
          <h1 className="text-xl font-semibold text-white">Overview</h1>
          <p className="mt-1 text-sm text-surface-muted">No workspaces yet. Create one from the sidebar.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 py-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Overview</h1>
        <p className="mt-1 text-sm text-surface-muted">
          Everything you can open in this tenant — yours and shared — grouped by hub.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total workspaces" value={String(list.length)} />
        <StatCard
          label="Shared with you"
          value={String(sharedWithYou)}
          sub={sharedWithYou === 0 ? "Only owned workspaces" : undefined}
        />
        <StatCard label="Template kinds in use" value={String(kindCounts.length)} />
        <StatCard label="Hubs with items" value={String(hubsWithItems.length)} sub="of 6 groups" />
      </div>

      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-surface-muted">By template kind</h2>
        <ul className="mt-2 flex flex-wrap gap-2">
          {kindCounts.map(([kind, n]) => (
            <li
              key={kind}
              className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm text-neutral-200"
            >
              <span className="text-white">{kindLabelFor(kind)}</span>
              <span className="text-surface-muted"> · {n}</span>
            </li>
          ))}
        </ul>
      </div>

      {DEFAULT_HUBS.map((hub) => {
        const items = grouped[hub.id]?.items ?? [];
        if (items.length === 0) return null;
        return (
          <section key={hub.id} className="space-y-3">
            <h2 className="text-sm font-medium text-white">{hub.label}</h2>
            <ul className="grid gap-3 sm:grid-cols-2">
              {items.map((w) => (
                <li key={w.id}>
                  <button
                    type="button"
                    onClick={() => onOpenWorkspace(w.id)}
                    className="flex w-full flex-col rounded-xl border border-surface-border bg-surface-raised p-4 text-left transition hover:border-sky-500/35 hover:bg-white/[0.03]"
                  >
                    <span className="font-medium text-white">{w.title || w.kind}</span>
                    <span className="mt-1 text-xs text-surface-muted">{kindLabelFor(w.kind)}</span>
                    <span className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-white/45">
                      <span className="rounded border border-white/10 px-1.5 py-0.5">{accessHint(w.access_role)}</span>
                      <span>Updated {relativeActivityEn(w.updated_at)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
