import { Link, Navigate } from "react-router-dom";
import { useIdeAgentAvailable } from "../hooks/useIdeAgentAvailable";

/**
 * Separate area from normal Chat: conversation with / through the IDE (Cursor Composer, …),
 * not the server LLM pipeline. Route is only reachable when IDE Agent is enabled (see Admin → IDE Agent).
 */
export function IdeAgentPage() {
  const { loading, enabled, playwrightInstalled } = useIdeAgentAvailable();

  if (!loading && !enabled) {
    return <Navigate to="/" replace />;
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center px-4">
        <p className="text-sm text-surface-muted">Loading…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-full min-h-0 max-w-3xl flex-col overflow-hidden px-4 py-6">
      <header className="shrink-0">
        <h1 className="text-lg font-semibold text-white">IDE Agent</h1>
        <p className="mt-1 text-sm text-surface-muted">
          Not the same as <span className="text-neutral-400">Chat</span> — here the goal is to work through your IDE&apos;s AI (e.g. Cursor
          Composer) via automation, not the server-side Ollama / external model.
        </p>
      </header>

      <div className="mt-8 min-h-0 flex-1 overflow-y-auto rounded-xl border border-surface-border bg-surface-raised/50 p-5">
        <section>
          <h2 className="text-sm font-medium text-white">Cursor</h2>
          <p className="mt-2 text-xs leading-relaxed text-surface-muted">
            Connection uses Playwright and the IDE&apos;s remote-debugging port (see{" "}
            <Link to="/admin/ide-agent" className="text-sky-400 hover:text-sky-300 hover:underline">
              Admin → IDE Agent
            </Link>
            ). Interactive composer UI will plug in here later.
          </p>
          <ul className="mt-4 space-y-1 text-xs text-surface-muted">
            <li>
              Playwright installed:{" "}
              <span className="font-mono text-neutral-300">
                {playwrightInstalled === null ? "…" : playwrightInstalled ? "yes" : "no"}
              </span>
            </li>
          </ul>
        </section>

        <section className="mt-8 border-t border-white/10 pt-6">
          <h2 className="text-sm font-medium text-surface-muted">Other IDEs</h2>
          <p className="mt-2 text-xs text-surface-muted/80">VS Code, Windsurf, … — coming later; selectors are already versioned in the backend.</p>
        </section>
      </div>
    </div>
  );
}
