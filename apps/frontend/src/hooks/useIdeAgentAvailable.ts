import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { apiFetch } from "../lib/api";

export type IdeAgentStatusPayload = {
  loading: boolean;
  /** True when PIDEA is on globally and this user is **admin** (IDE Agent / Playwright is admin-only). */
  enabled: boolean;
  playwrightInstalled: boolean | null;
  /** Operator toggle only (for settings copy). */
  globallyEnabled: boolean | null;
};

/**
 * Loads ``GET /v1/experimental/status`` on session change, on ``ide-agent-settings-changed``,
 * and when the tab becomes visible again (so status updates after Admin actions in another tab).
 */
export function useIdeAgentAvailable(): IdeAgentStatusPayload {
  const auth = useAuth();
  const [loading, setLoading] = useState(true);
  const [enabled, setEnabled] = useState(false);
  const [playwrightInstalled, setPlaywrightInstalled] = useState<boolean | null>(null);
  const [globallyEnabled, setGloballyEnabled] = useState<boolean | null>(null);

  const authRef = useRef(auth);
  authRef.current = auth;

  useEffect(() => {
    if (!auth.accessToken || !auth.user) {
      setLoading(false);
      setEnabled(false);
      setPlaywrightInstalled(null);
      setGloballyEnabled(null);
      return;
    }
    let cancelled = false;

    const run = (showLoading = true) => {
      if (cancelled) return;
      void (async () => {
        const a = authRef.current;
        if (!a.accessToken || !a.user) return;
        if (showLoading) setLoading(true);
        try {
          const r = await apiFetch("/v1/experimental/status", a);
          const d = (await r.json()) as {
            pidea_globally_enabled?: boolean;
            ide_agent_access?: boolean;
            pidea_playwright_installed?: boolean;
          };
          if (!cancelled) {
            setGloballyEnabled(r.ok ? !!d.pidea_globally_enabled : null);
            setEnabled(r.ok && !!d.ide_agent_access);
            setPlaywrightInstalled(r.ok ? !!d.pidea_playwright_installed : null);
            setLoading(false);
          }
        } catch {
          if (!cancelled) {
            setEnabled(false);
            setPlaywrightInstalled(null);
            setGloballyEnabled(null);
            setLoading(false);
          }
        }
      })();
    };

    run();

    const onRefresh = () => run(true);
    window.addEventListener("ide-agent-settings-changed", onRefresh);

    let debounceTimer: ReturnType<typeof setTimeout> | null = null;
    const onVisibility = () => {
      if (document.visibilityState !== "visible") return;
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => run(false), 400);
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelled = true;
      if (debounceTimer) clearTimeout(debounceTimer);
      window.removeEventListener("ide-agent-settings-changed", onRefresh);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [auth.accessToken, auth.user?.id]);

  return { loading, enabled, playwrightInstalled, globallyEnabled };
}
