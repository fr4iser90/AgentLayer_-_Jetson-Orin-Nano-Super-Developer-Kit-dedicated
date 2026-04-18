import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { apiFetch } from "../lib/api";

export type IdeAgentStatusPayload = {
  loading: boolean;
  /** True when PIDEA is on globally and this user may use IDE Agent (admin or ``ide_agent_allowed``). */
  enabled: boolean;
  playwrightInstalled: boolean | null;
  /** Operator toggle only (for settings copy). */
  globallyEnabled: boolean | null;
};

/**
 * Loads ``GET /v1/experimental/status`` once per session change.
 * Nav ``IDE Agent`` uses ``enabled`` (= ``ide_agent_access`` from API).
 */
export function useIdeAgentAvailable(): IdeAgentStatusPayload {
  const auth = useAuth();
  const [loading, setLoading] = useState(true);
  const [enabled, setEnabled] = useState(false);
  const [playwrightInstalled, setPlaywrightInstalled] = useState<boolean | null>(null);
  const [globallyEnabled, setGloballyEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    if (!auth.accessToken || !auth.user) {
      setLoading(false);
      setEnabled(false);
      setPlaywrightInstalled(null);
      setGloballyEnabled(null);
      return;
    }
    let cancelled = false;

    const run = () => {
      cancelled = false;
      setLoading(true);
      void (async () => {
        try {
          const r = await apiFetch("/v1/experimental/status", auth);
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

    const onRefresh = () => {
      run();
    };
    window.addEventListener("ide-agent-settings-changed", onRefresh);
    return () => {
      cancelled = true;
      window.removeEventListener("ide-agent-settings-changed", onRefresh);
    };
  }, [auth.accessToken, auth.user?.id]);

  return { loading, enabled, playwrightInstalled, globallyEnabled };
}
