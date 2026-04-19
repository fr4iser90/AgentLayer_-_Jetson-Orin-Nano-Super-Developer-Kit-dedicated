import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { apiFetch } from "../lib/api";

type StatusJson = { connected?: boolean; error?: string };

/**
 * CDP + Playwright connection for a single IDE (uses operator-resolved selector profile).
 */
export function useIdeAgentConnectionStatus(ide: string | null) {
  const auth = useAuth();
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!ide) {
      setLoading(false);
      setConnected(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch(`/v1/admin/ide-agents/${encodeURIComponent(ide)}/status`, auth);
      const data = (await r.json().catch(() => ({}))) as StatusJson & { detail?: unknown };
      if (!r.ok) {
        setConnected(false);
        setError(typeof data.detail === "string" ? data.detail : "status failed");
        return;
      }
      setConnected(!!data.connected);
      if (!data.connected && data.error) setError(data.error);
    } catch (e) {
      setConnected(false);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [auth, ide]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { loading, connected, error, refresh };
}
