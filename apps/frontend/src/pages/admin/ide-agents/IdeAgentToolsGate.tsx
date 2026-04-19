import type { ReactNode } from "react";
import { Navigate, useParams } from "react-router-dom";
import { useIdeAgentConnectionStatus } from "../../../hooks/useIdeAgentConnectionStatus";

const ALLOWED = new Set(["cursor", "vscode", "windsurf"]);

/**
 * Tools routes (control center, settings, DOM analyzer) require CDP connection for this IDE.
 */
export function IdeAgentToolsGate(props: { children: ReactNode }) {
  const { ide: raw } = useParams<{ ide: string }>();
  const ide = (raw || "").toLowerCase();

  if (!raw || !ALLOWED.has(ide)) {
    return <Navigate to="/admin" replace />;
  }

  const { loading, connected } = useIdeAgentConnectionStatus(ide);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center px-4 text-sm text-surface-muted">
        Checking connection to IDE (CDP)…
      </div>
    );
  }

  if (!connected) {
    return <Navigate to={`/admin/ide-agents/${ide}`} replace state={{ requireConnection: true }} />;
  }

  return props.children;
}
