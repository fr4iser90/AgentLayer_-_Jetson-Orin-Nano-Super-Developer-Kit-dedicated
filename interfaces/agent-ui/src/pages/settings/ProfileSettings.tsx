export function ProfileSettings() {
  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-lg font-semibold text-white">Profile</h1>
      <p className="mt-2 text-sm text-surface-muted">
        Account basics and password changes will live here once wired to the auth API. Session data
        comes from <code className="rounded bg-white/5 px-1 text-xs">GET /auth/me</code>.
      </p>
    </div>
  );
}
