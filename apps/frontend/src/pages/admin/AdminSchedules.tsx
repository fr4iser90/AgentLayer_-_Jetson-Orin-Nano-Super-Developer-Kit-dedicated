import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type SchedulerJobRow = {
  id: string;
  workspace_id: string | null;
  execution_target: string;
  title: string | null;
  interval_minutes: number;
  enabled: boolean;
  last_run_at: string | null;
  created_at: string;
  ide_workflow?: unknown;
  instructions?: string;
};

function pill(enabled: boolean) {
  return enabled
    ? "bg-emerald-600/25 text-emerald-200 border-emerald-500/40"
    : "bg-white/10 text-surface-muted border-surface-border";
}

export function AdminSchedules() {
  const auth = useAuth();
  const [jobs, setJobs] = useState<SchedulerJobRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [scope, setScope] = useState<"all" | "global_only" | "workspace">("all");
  const [workspaceId, setWorkspaceId] = useState<string>("");
  const [includeGlobal, setIncludeGlobal] = useState(true);
  const [target, setTarget] = useState<"all" | "ide_agent" | "server_periodic">("all");
  const [enabled, setEnabled] = useState<"all" | "true" | "false">("all");

  const query = useMemo(() => {
    const q = new URLSearchParams();
    if (scope === "global_only") {
      q.set("include_global", "true");
    } else if (scope === "workspace") {
      if (workspaceId.trim()) q.set("workspace_id", workspaceId.trim());
      q.set("include_global", includeGlobal ? "true" : "false");
    }
    if (target !== "all") q.set("execution_target", target);
    if (enabled !== "all") q.set("enabled", enabled);
    q.set("limit", "200");
    return q;
  }, [scope, workspaceId, includeGlobal, target, enabled]);

  const refresh = async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await apiFetch(`/v1/admin/scheduler-jobs?${query.toString()}`, auth);
      const j = (await res.json().catch(() => null)) as any;
      if (!res.ok || !j?.ok) {
        setErr(String(j?.detail ?? j?.error ?? res.status));
        setJobs(null);
      } else {
        setJobs(Array.isArray(j.jobs) ? (j.jobs as SchedulerJobRow[]) : []);
      }
    } catch (e) {
      setErr(String(e));
      setJobs(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.toString()]);

  const toggleEnabled = async (jobId: string, next: boolean) => {
    const res = await apiFetch(`/v1/admin/scheduler-jobs/${jobId}/enabled`, auth, {
      method: "PATCH",
      body: JSON.stringify({ enabled: next }),
    });
    const j = (await res.json().catch(() => null)) as any;
    if (!res.ok || !j?.ok) {
      setErr(String(j?.detail ?? j?.error ?? res.status));
      return;
    }
    await refresh();
  };

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-white">Schedules</h1>
          <p className="mt-2 text-sm text-surface-muted">
            Persisted user-defined schedules (<span className="font-mono">scheduler_jobs</span>). Use
            this to inspect and toggle jobs. Execution happens via run queue.
          </p>
        </div>
        <button
          type="button"
          className="rounded-md border border-surface-border px-3 py-2 text-sm text-neutral-100 hover:bg-white/5"
          onClick={() => void refresh()}
          disabled={loading}
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      <div className="mt-6 rounded-xl border border-surface-border bg-surface-raised/50 p-4">
        <div className="grid gap-3 md:grid-cols-5">
          <label className="text-xs text-surface-muted">
            Scope
            <select
              className="mt-1 w-full rounded-md border border-surface-border bg-black/30 px-2 py-1 text-sm text-neutral-100"
              value={scope}
              onChange={(e) => setScope(e.target.value as any)}
            >
              <option value="all">All</option>
              <option value="global_only">Global only (workspace_id NULL)</option>
              <option value="workspace">Workspace scoped</option>
            </select>
          </label>
          <label className="text-xs text-surface-muted md:col-span-2">
            Workspace id (UUID)
            <input
              className="mt-1 w-full rounded-md border border-surface-border bg-black/30 px-2 py-1 text-sm text-neutral-100"
              value={workspaceId}
              onChange={(e) => setWorkspaceId(e.target.value)}
              placeholder="optional"
              disabled={scope !== "workspace"}
            />
          </label>
          <label className="text-xs text-surface-muted">
            Target
            <select
              className="mt-1 w-full rounded-md border border-surface-border bg-black/30 px-2 py-1 text-sm text-neutral-100"
              value={target}
              onChange={(e) => setTarget(e.target.value as any)}
            >
              <option value="all">All</option>
              <option value="ide_agent">ide_agent</option>
              <option value="server_periodic">server_periodic</option>
            </select>
          </label>
          <label className="text-xs text-surface-muted">
            Enabled
            <select
              className="mt-1 w-full rounded-md border border-surface-border bg-black/30 px-2 py-1 text-sm text-neutral-100"
              value={enabled}
              onChange={(e) => setEnabled(e.target.value as any)}
            >
              <option value="all">All</option>
              <option value="true">Enabled</option>
              <option value="false">Disabled</option>
            </select>
          </label>
        </div>
        {scope === "workspace" ? (
          <label className="mt-3 flex items-center gap-2 text-xs text-surface-muted">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-surface-border"
              checked={includeGlobal}
              onChange={(e) => setIncludeGlobal(e.target.checked)}
            />
            Include global schedules
          </label>
        ) : null}
      </div>

      {err ? (
        <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
          {err}
        </div>
      ) : null}

      <div className="mt-6 overflow-x-auto rounded-xl border border-surface-border">
        <table className="w-full min-w-[840px] border-collapse text-left text-sm">
          <thead className="bg-black/30">
            <tr className="border-b border-surface-border text-surface-muted">
              <th className="px-3 py-2 font-medium">Enabled</th>
              <th className="px-3 py-2 font-medium">Target</th>
              <th className="px-3 py-2 font-medium">Title</th>
              <th className="px-3 py-2 font-medium">Interval</th>
              <th className="px-3 py-2 font-medium">Workspace</th>
              <th className="px-3 py-2 font-medium">Last run</th>
              <th className="px-3 py-2 font-medium">Created</th>
              <th className="px-3 py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {!jobs ? (
              <tr>
                <td colSpan={8} className="px-3 py-10 text-center text-surface-muted">
                  {loading ? "Loading…" : "No data yet."}
                </td>
              </tr>
            ) : jobs.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-10 text-center text-surface-muted">
                  No schedules.
                </td>
              </tr>
            ) : (
              jobs.map((j) => (
                <tr key={j.id} className="border-b border-white/5">
                  <td className="px-3 py-2">
                    <span className={`rounded-md border px-2 py-0.5 text-xs ${pill(j.enabled)}`}>
                      {j.enabled ? "enabled" : "disabled"}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-neutral-100">{j.execution_target}</td>
                  <td className="px-3 py-2 text-neutral-100">{j.title || "—"}</td>
                  <td className="px-3 py-2 text-surface-muted">{j.interval_minutes} min</td>
                  <td className="px-3 py-2 font-mono text-[11px] text-surface-muted">
                    {j.workspace_id || "global"}
                  </td>
                  <td className="px-3 py-2 text-surface-muted">{j.last_run_at || "—"}</td>
                  <td className="px-3 py-2 text-surface-muted">{j.created_at}</td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      className="rounded-md border border-surface-border px-2 py-1 text-xs text-neutral-100 hover:bg-white/5"
                      onClick={() => void toggleEnabled(j.id, !j.enabled)}
                    >
                      {j.enabled ? "Disable" : "Enable"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

