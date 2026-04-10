import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type ToolRow = {
  function?: { name?: string; description?: string; TOOL_DESCRIPTION?: string };
};

export function AdminTools() {
  const auth = useAuth();
  const [tools, setTools] = useState<ToolRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadTools = useCallback(async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await apiFetch("/v1/tools", auth);
      const data = (await res.json()) as { tools?: ToolRow[] };
      if (!res.ok) {
        setMsg("Failed to load tools");
        return;
      }
      setTools(data.tools ?? []);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    void loadTools();
  }, [loadTools]);

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
      await loadTools();
      setMsg("Registry reloaded.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="h-full min-h-0 overflow-y-auto">
      <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-white">Tool registry</h1>
      <p className="mt-2 text-sm text-surface-muted">Registered MCP tools and chat tool specs.</p>

      <div className="mt-6 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          onClick={() => void loadTools()}
        >
          Refresh list
        </button>
        <button
          type="button"
          disabled={busy}
          className="rounded-md bg-white/10 px-4 py-2 text-sm font-medium text-white hover:bg-white/15 disabled:opacity-50"
          onClick={() => void reloadRegistry()}
        >
          Reload registry
        </button>
      </div>

      {msg ? <p className="mt-3 text-sm text-surface-muted">{msg}</p> : null}

      <div className="mt-6 overflow-x-auto rounded-xl border border-surface-border">
        <table className="w-full min-w-[28rem] text-left text-sm">
          <thead className="border-b border-surface-border bg-black/20 text-surface-muted">
            <tr>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Description</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={2} className="px-4 py-6 text-center text-surface-muted">
                  Loading…
                </td>
              </tr>
            ) : tools.length === 0 ? (
              <tr>
                <td colSpan={2} className="px-4 py-6 text-center text-surface-muted">
                  No tools loaded.
                </td>
              </tr>
            ) : (
              tools.map((tool, i) => {
                const fn = tool.function ?? {};
                const name = fn.name ?? "—";
                const desc = fn.description ?? fn.TOOL_DESCRIPTION ?? "";
                return (
                  <tr key={`${name}-${i}`} className="border-b border-surface-border/80 hover:bg-white/[0.03]">
                    <td className="px-4 py-3 font-mono text-xs text-white">{name}</td>
                    <td className="px-4 py-3 text-surface-muted">{desc}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      </div>
    </div>
  );
}
