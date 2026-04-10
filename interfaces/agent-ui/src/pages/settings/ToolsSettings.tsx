export function ToolsSettings() {
  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-lg font-semibold text-white">Tools</h1>
      <p className="mt-2 text-sm text-surface-muted">
        Choose which registered tools the agent may call for your account. Tools that need secrets
        will show a flag until the matching entry exists under Connections.
      </p>
    </div>
  );
}
