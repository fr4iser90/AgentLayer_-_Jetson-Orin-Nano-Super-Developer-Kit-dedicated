export function ConnectionsSettings() {
  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-lg font-semibold text-white">Connections</h1>
      <p className="mt-2 text-sm text-surface-muted">
        Store API keys and OAuth connections (e.g. Gmail) per user, encrypted at rest. Each row will
        show status: <span className="text-emerald-400/90">connected</span> or{" "}
        <span className="text-amber-400/90">missing secret</span>, with a link to fix it here.
      </p>
    </div>
  );
}
