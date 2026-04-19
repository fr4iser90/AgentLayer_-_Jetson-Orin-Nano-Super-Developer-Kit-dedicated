import type { ReactNode } from "react";
import { Link, Navigate, useLocation, useParams } from "react-router-dom";
import { useIdeAgentConnectionStatus } from "../../../hooks/useIdeAgentConnectionStatus";

const IDES = new Set(["cursor", "vscode", "windsurf"]);

const IDE_LABEL: Record<string, string> = {
  cursor: "Cursor",
  vscode: "VS Code",
  windsurf: "Windsurf",
};

function useIdeParam(): { ide: string; ok: boolean } {
  const { ide } = useParams<{ ide: string }>();
  const i = (ide || "").toLowerCase();
  return { ide: i, ok: IDES.has(i) };
}

function Shell(props: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8 text-neutral-100">
      <h1 className="text-xl font-semibold text-white">{props.title}</h1>
      <div className="mt-4 text-sm text-surface-muted">{props.children}</div>
    </div>
  );
}

/** Landing: IDE Agents → :ide → Overview */
export function IdeAgentIdeOverviewPage() {
  const { ide, ok } = useIdeParam();
  const location = useLocation();
  const { loading, connected, error: connErr } = useIdeAgentConnectionStatus(ok ? ide : null);
  if (!ok) return <Navigate to="/admin/ide-agents/cursor" replace />;
  const label = IDE_LABEL[ide] || ide;
  const bounced = !!(location.state as { requireConnection?: boolean } | null)?.requireConnection;

  return (
    <Shell title={`${label} — Overview`}>
      {bounced ? (
        <p className="mb-4 rounded-lg border border-amber-500/30 bg-amber-950/30 px-3 py-2 text-amber-100/90">
          Connect this IDE via CDP (see Global operator & CDP) to use Control Center, Settings, and Developer Tools.
        </p>
      ) : null}
      <p>
        Overview for <span className="font-mono text-neutral-300">{ide}</span>.
        {loading ? (
          <span className="block mt-2 text-surface-muted">Checking CDP connection…</span>
        ) : connected ? (
          <span className="block mt-2 text-emerald-400/90">CDP connected — tools are available in the sidebar.</span>
        ) : (
          <span className="block mt-2 text-amber-200/90" title={connErr || undefined}>
            Not connected to CDP for this profile. Configure the operator CDP URL and ensure the IDE is running with
            remote debugging.
          </span>
        )}
      </p>
      {connected && !loading ? (
        <ul className="mt-4 list-inside list-disc space-y-2 text-neutral-300">
          <li>
            <Link className="text-sky-400 hover:underline" to={`/admin/ide-agents/${ide}/control-center`}>
              Control Center
            </Link>
          </li>
          <li>
            <Link className="text-sky-400 hover:underline" to={`/admin/ide-agents/${ide}/settings`}>
              Settings
            </Link>
          </li>
          <li>
            <Link className="text-sky-400 hover:underline" to={`/admin/ide-agents/${ide}/dom-analyzer`}>
              Developer Tools → DOM Analyzer
            </Link>
          </li>
        </ul>
      ) : !loading ? (
        <p className="mt-4 text-sm text-surface-muted">
          Control Center, Settings, and DOM Analyzer stay hidden until the connection is live.
        </p>
      ) : null}
    </Shell>
  );
}

export function IdeAgentIdeControlCenterPage() {
  const { ide, ok } = useIdeParam();
  if (!ok) return <Navigate to="/admin/ide-agents/cursor/control-center" replace />;
  const label = IDE_LABEL[ide] || ide;
  return (
    <Shell title={`${label} — Control Center`}>
      <p>
        Runtime control surfaces for <span className="font-mono text-neutral-300">{ide}</span> can be integrated here
        (sessions, health, quick actions). This placeholder keeps navigation stable until features are wired.
      </p>
    </Shell>
  );
}

export function IdeAgentIdeSettingsPage() {
  const { ide, ok } = useIdeParam();
  if (!ok) return <Navigate to="/admin/ide-agents/cursor/settings" replace />;
  const label = IDE_LABEL[ide] || ide;
  return (
    <Shell title={`${label} — Settings`}>
      <p>
        Per-IDE preferences may appear here later. Global operator settings (CDP URL, Playwright, default selector
        profile) remain on the shared operator page.
      </p>
      <p className="mt-4">
        <Link to="/admin/ide-agent" className="text-sky-400 hover:underline">
          Open global operator & CDP settings →
        </Link>
      </p>
    </Shell>
  );
}
