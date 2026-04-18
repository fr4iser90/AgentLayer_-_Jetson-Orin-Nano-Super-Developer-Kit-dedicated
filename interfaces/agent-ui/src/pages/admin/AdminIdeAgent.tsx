import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type ExperimentalStatus = {
  pidea_globally_enabled?: boolean;
  pidea_effective_enabled?: boolean;
  ide_agent_access?: boolean;
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

/** Operator PIDEA / IDE Agent (Playwright, CDP, Cursor selectors). Admin only. */
export function AdminIdeAgent() {
  const auth = useAuth();
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [status, setStatus] = useState<ExperimentalStatus | null>(null);

  const [pideaEnabled, setPideaEnabled] = useState(false);
  const [pideaCdp, setPideaCdp] = useState("");
  const [pideaIde, setPideaIde] = useState("cursor");
  const [pideaVer, setPideaVer] = useState("1.7.17");
  const [saving, setSaving] = useState(false);
  const [installingPw, setInstallingPw] = useState(false);

  const loadStatus = useCallback(async (): Promise<ExperimentalStatus | null> => {
    try {
      const r = await apiFetch("/v1/experimental/status", auth);
      const d = (await r.json()) as ExperimentalStatus;
      if (r.ok) {
        setStatus(d);
        return d;
      }
      setMsg("Could not load IDE Agent status.");
      return null;
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, [auth]);

  const loadOperator = useCallback(async () => {
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
  }, [auth]);

  const load = useCallback(async () => {
    setLoading(true);
    setMsg(null);
    await Promise.all([loadStatus(), loadOperator()]);
    setLoading(false);
  }, [loadStatus, loadOperator]);

  useEffect(() => {
    void load();
  }, [load]);

  async function installPlaywrightFromUi(opts?: { afterSave?: boolean }) {
    if (!opts?.afterSave) setMsg(null);
    setInstallingPw(true);
    try {
      const r = await apiFetch("/v1/admin/experimental/install-playwright", auth, { method: "POST" });
      const j = (await r.json()) as { ok?: boolean; detail?: string; pidea_playwright_installed?: boolean };
      if (!r.ok) {
        const err = j as { detail?: unknown };
        setMsg(
          opts?.afterSave
            ? `Saved, but Playwright install failed: ${typeof err.detail === "string" ? err.detail : "Install failed."}`
            : typeof err.detail === "string"
              ? err.detail
              : "Install failed."
        );
        return;
      }
      if (j.ok) {
        setMsg(opts?.afterSave ? "Saved. Playwright install finished." : "Playwright install finished.");
      } else {
        setMsg(
          j.detail?.trim()
            ? opts?.afterSave
              ? `Saved, but Playwright install failed:\n${j.detail}`
              : `Install failed:\n${j.detail}`
            : opts?.afterSave
              ? "Saved, but Playwright install failed."
              : "Install failed."
        );
      }
      await loadStatus();
      window.dispatchEvent(new Event("ide-agent-settings-changed"));
    } catch (e) {
      setMsg(
        opts?.afterSave
          ? `Saved, but Playwright install failed: ${e instanceof Error ? e.message : String(e)}`
          : e instanceof Error
            ? e.message
            : String(e)
      );
    } finally {
      setInstallingPw(false);
    }
  }

  async function savePidea() {
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
      const st = await loadStatus();
      window.dispatchEvent(new Event("ide-agent-settings-changed"));
      if (pideaEnabled && st && !st.pidea_playwright_installed) {
        setMsg("Saved. Installing Playwright…");
        await installPlaywrightFromUi({ afterSave: true });
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="text-xl font-semibold text-white">IDE Agent (PIDEA)</h1>
      <p className="mt-2 text-sm text-surface-muted">
        Playwright → Cursor/VS Code over CDP (<span className="font-mono text-neutral-500">--remote-debugging-port</span>
        ). Per-user access:{" "}
        <Link to="/admin/users" className="text-sky-400 hover:text-sky-300 hover:underline">
          Admin → Users
        </Link>{" "}
        (column IDE Agent). The in-app area:{" "}
        <Link to="/ide-agent" className="text-sky-400 hover:text-sky-300 hover:underline">
          IDE Agent
        </Link>
        .
      </p>

      {loading ? (
        <p className="mt-6 text-sm text-surface-muted">Loading…</p>
      ) : (
        <section className="mt-8 rounded-xl border border-amber-500/20 bg-amber-500/5 p-5">
          <h2 className="text-sm font-medium text-amber-100/95">Cursor (CDP) · operator</h2>
          <ul className="mt-3 list-inside list-disc space-y-1 text-xs text-surface-muted">
            <li>
              PIDEA globally on:{" "}
              <span className="font-mono text-neutral-300">
                {(status?.pidea_globally_enabled ?? status?.pidea_effective_enabled) ? "yes" : "no"}
              </span>{" "}
              (operator DB + optional <span className="font-mono">AGENT_PIDEA_ENABLED</span>)
            </li>
            <li>
              Your IDE Agent access:{" "}
              <span className="font-mono text-neutral-300">{status?.ide_agent_access ? "yes" : "no"}</span> (admins
              always; others: Users → IDE Agent)
            </li>
            <li>
              Playwright installed:{" "}
              <span className="font-mono text-neutral-300">{status?.pidea_playwright_installed ? "yes" : "no"}</span>
            </li>
          </ul>
          <p className="mt-4 text-xs leading-relaxed text-surface-muted">
            Playwright runs on the <strong className="font-medium text-neutral-400">server</strong> (same Python as
            this API).
          </p>

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
              <label className={label} htmlFor="pidea-cdp-admin">
                CDP HTTP URL (empty = env default)
              </label>
              <input
                id="pidea-cdp-admin"
                className={input}
                value={pideaCdp}
                onChange={(e) => setPideaCdp(e.target.value)}
                placeholder="http://127.0.0.1:9222"
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className={label} htmlFor="pidea-ide-admin">
                  Selector IDE
                </label>
                <input
                  id="pidea-ide-admin"
                  className={input}
                  value={pideaIde}
                  onChange={(e) => setPideaIde(e.target.value)}
                  placeholder="cursor"
                />
              </div>
              <div>
                <label className={label} htmlFor="pidea-ver-admin">
                  Selector version
                </label>
                <input
                  id="pidea-ver-admin"
                  className={input}
                  value={pideaVer}
                  onChange={(e) => setPideaVer(e.target.value)}
                  placeholder="1.7.17"
                />
              </div>
            </div>
            {status?.pidea_playwright_installed ? null : (
              <div className="rounded-lg border border-amber-500/30 bg-black/20 p-3">
                <p className="text-xs text-surface-muted">
                  Playwright fehlt noch. Mit aktiviertem PIDEA installiert{" "}
                  <strong className="text-neutral-400">Save PIDEA settings</strong> Playwright automatisch nach dem
                  Speichern. Oder hier manuell (kann einige Minuten dauern, lädt Chromium):
                </p>
                <button
                  type="button"
                  disabled={installingPw || saving}
                  onClick={() => void installPlaywrightFromUi()}
                  className="mt-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50"
                >
                  {installingPw ? "Installing Playwright…" : "Install Playwright on server"}
                </button>
              </div>
            )}
            <button
              type="button"
              disabled={saving}
              onClick={() => void savePidea()}
              className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save PIDEA settings"}
            </button>
          </div>
        </section>
      )}

      {msg ? (
        <p
          className={`mt-4 text-sm whitespace-pre-wrap ${
            msg === "Saved." ||
            msg === "Playwright install finished." ||
            msg === "Saved. Playwright install finished." ||
            msg.startsWith("Saved. Installing Playwright")
              ? "text-emerald-400/90"
              : "text-rose-300/90"
          }`}
        >
          {msg}
        </p>
      ) : null}
    </div>
  );
}
