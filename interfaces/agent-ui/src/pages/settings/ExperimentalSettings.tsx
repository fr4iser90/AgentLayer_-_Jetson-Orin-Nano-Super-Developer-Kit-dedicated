import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type ExperimentalStatus = {
  pidea_effective_enabled?: boolean;
  pidea_playwright_installed?: boolean;
};

type OperatorPublic = {
  pidea_enabled?: boolean;
  pidea_effective_enabled?: boolean;
  pidea_cdp_http_url?: string;
  pidea_selector_ide?: string;
  pidea_selector_version?: string;
};

const label = "mb-1 block text-xs font-medium text-surface-muted";
const input =
  "mt-0.5 w-full rounded-lg border border-surface-border bg-black/30 px-3 py-2 text-sm text-neutral-100 placeholder:text-surface-muted focus:border-sky-500/60 focus:outline-none focus:ring-1 focus:ring-sky-500/40";

export function ExperimentalSettings() {
  const auth = useAuth();
  const isAdmin = auth.user?.role === "admin";
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [status, setStatus] = useState<ExperimentalStatus | null>(null);

  const [pideaEnabled, setPideaEnabled] = useState(false);
  const [pideaCdp, setPideaCdp] = useState("");
  const [pideaIde, setPideaIde] = useState("cursor");
  const [pideaVer, setPideaVer] = useState("1.7.17");
  const [saving, setSaving] = useState(false);

  const loadStatus = useCallback(async () => {
    setMsg(null);
    try {
      const r = await apiFetch("/v1/experimental/status", auth);
      const d = (await r.json()) as ExperimentalStatus;
      if (r.ok) setStatus(d);
      else setMsg("Could not load experimental status.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }, [auth]);

  const loadAdmin = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const r = await apiFetch("/v1/admin/operator-settings", auth);
      const d = (await r.json()) as OperatorPublic;
      if (!r.ok) return;
      setPideaEnabled(Boolean(d.pidea_enabled));
      setPideaCdp((d.pidea_cdp_http_url ?? "").trim());
      setPideaIde((d.pidea_selector_ide ?? "cursor").trim() || "cursor");
      setPideaVer((d.pidea_selector_version ?? "1.7.17").trim() || "1.7.17");
    } catch {
      /* ignore */
    }
  }, [auth, isAdmin]);

  const load = useCallback(async () => {
    setLoading(true);
    await Promise.all([loadStatus(), loadAdmin()]);
    setLoading(false);
  }, [loadStatus, loadAdmin]);

  useEffect(() => {
    void load();
  }, [load]);

  async function savePidea() {
    if (!isAdmin) return;
    setSaving(true);
    setMsg(null);
    try {
      const r = await apiFetch("/v1/admin/operator-settings", auth, {
        method: "PATCH",
        body: JSON.stringify({
          pidea_enabled: pideaEnabled,
          pidea_cdp_http_url: pideaCdp.trim() || null,
          pidea_selector_ide: pideaIde.trim() || null,
          pidea_selector_version: pideaVer.trim() || null,
        }),
      });
      if (!r.ok) {
        const err = (await r.json().catch(() => ({}))) as { detail?: unknown };
        setMsg(typeof err.detail === "string" ? err.detail : "Save failed.");
        return;
      }
      setMsg("Saved.");
      await loadStatus();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-lg font-semibold text-white">Experimental</h1>
      <p className="mt-1 text-sm text-surface-muted">
        Unstable integrations. PIDEA drives Cursor/VS Code via Playwright and the remote-debugging port (
        <span className="font-mono text-neutral-400">--remote-debugging-port</span>).
      </p>

      {loading ? (
        <p className="mt-6 text-sm text-surface-muted">Loading…</p>
      ) : (
        <section className="mt-8 rounded-xl border border-amber-500/20 bg-amber-500/5 p-5">
          <h2 className="text-sm font-medium text-amber-100/95">PIDEA (DOM / CDP)</h2>
          <ul className="mt-3 list-inside list-disc space-y-1 text-xs text-surface-muted">
            <li>
              Effective enabled:{" "}
              <span className="font-mono text-neutral-300">
                {status?.pidea_effective_enabled ? "yes" : "no"}
              </span>{" "}
              (DB + optional <span className="font-mono">AGENT_PIDEA_ENABLED</span>)
            </li>
            <li>
              Playwright installed:{" "}
              <span className="font-mono text-neutral-300">
                {status?.pidea_playwright_installed ? "yes" : "no"}
              </span>
            </li>
          </ul>
          <p className="mt-4 text-xs leading-relaxed text-surface-muted">
            If PIDEA is on, install the optional dependency on the server:{" "}
            <code className="rounded bg-black/40 px-1 py-0.5 font-mono text-[11px] text-amber-100/90">
              pip install -r requirements-pidea.txt &amp;&amp; playwright install chromium
            </code>
          </p>

          {isAdmin ? (
            <div className="mt-6 space-y-4 border-t border-white/10 pt-6">
              <label className="flex cursor-pointer items-center gap-2 text-sm text-neutral-200">
                <input
                  type="checkbox"
                  className="rounded border-surface-border"
                  checked={pideaEnabled}
                  onChange={(e) => setPideaEnabled(e.target.checked)}
                />
                Enable PIDEA (operator default when <span className="font-mono">AGENT_PIDEA_ENABLED</span> is unset)
              </label>
              <div>
                <label className={label} htmlFor="pidea-cdp">
                  CDP HTTP URL (empty = env default)
                </label>
                <input
                  id="pidea-cdp"
                  className={input}
                  value={pideaCdp}
                  onChange={(e) => setPideaCdp(e.target.value)}
                  placeholder="http://127.0.0.1:9222"
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className={label} htmlFor="pidea-ide">
                    Selector IDE
                  </label>
                  <input
                    id="pidea-ide"
                    className={input}
                    value={pideaIde}
                    onChange={(e) => setPideaIde(e.target.value)}
                    placeholder="cursor"
                  />
                </div>
                <div>
                  <label className={label} htmlFor="pidea-ver">
                    Selector version
                  </label>
                  <input
                    id="pidea-ver"
                    className={input}
                    value={pideaVer}
                    onChange={(e) => setPideaVer(e.target.value)}
                    placeholder="1.7.17"
                  />
                </div>
              </div>
              <button
                type="button"
                disabled={saving}
                onClick={() => void savePidea()}
                className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save PIDEA settings"}
              </button>
            </div>
          ) : (
            <p className="mt-4 text-xs text-surface-muted">
              Only administrators can change PIDEA toggles and URLs. Ask an admin to open{" "}
              <span className="text-white/80">Settings → Experimental</span> or use env{" "}
              <span className="font-mono">AGENT_PIDEA_ENABLED</span>.
            </p>
          )}
        </section>
      )}

      {msg ? (
        <p className={`mt-4 text-sm ${msg === "Saved." ? "text-emerald-400/90" : "text-rose-300/90"}`}>{msg}</p>
      ) : null}
    </div>
  );
}
