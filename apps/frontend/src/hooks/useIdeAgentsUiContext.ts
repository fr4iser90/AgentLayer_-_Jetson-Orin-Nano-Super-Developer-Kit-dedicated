import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { apiFetch } from "../lib/api";

export type IdeAgentsUiContextPayload = {
  visible_ides: string[];
  operator_selector_ide: string | null;
  operator_selector_version: string | null;
  playwright_import_ok: boolean;
};

export function useIdeAgentsUiContext() {
  const auth = useAuth();
  const [data, setData] = useState<IdeAgentsUiContextPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch("/v1/admin/ide-agents/meta/ui-context", auth);
      const j = (await r.json().catch(() => ({}))) as IdeAgentsUiContextPayload & { detail?: unknown };
      if (!r.ok) {
        throw new Error(typeof j.detail === "string" ? j.detail : "ui-context failed");
      }
      setData({
        visible_ides: Array.isArray(j.visible_ides) ? j.visible_ides : [],
        operator_selector_ide: j.operator_selector_ide ?? null,
        operator_selector_version: j.operator_selector_version ?? null,
        playwright_import_ok: !!j.playwright_import_ok,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    void load();
  }, [load]);

  return { data, loading, error, refresh: load };
}
