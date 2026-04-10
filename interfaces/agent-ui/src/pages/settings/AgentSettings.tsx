export function AgentSettings() {
  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-lg font-semibold text-white">Agent</h1>
      <p className="mt-2 text-sm text-surface-muted">
        Personas, default system prompts, and workspace defaults will be configured here for your
        user scope (and persisted server-side when the API is ready).
      </p>
    </div>
  );
}
