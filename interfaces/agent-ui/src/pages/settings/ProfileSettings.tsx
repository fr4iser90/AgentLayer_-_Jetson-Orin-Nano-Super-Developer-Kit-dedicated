import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type MeResponse = {
  id?: string;
  email?: string;
  role?: string;
  created_at?: string;
  discord_user_id?: string | null;
  detail?: unknown;
};

export function ProfileSettings() {
  const auth = useAuth();
  const { user, logout } = auth;
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await apiFetch("/auth/me", auth);
      const data = (await res.json()) as MeResponse;
      if (!res.ok) {
        setErr(typeof data.detail === "string" ? data.detail : "Could not load profile");
        setMe(null);
        return;
      }
      setMe(data);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not load profile");
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    void load();
  }, [load]);

  const email = me?.email ?? user?.email ?? "—";
  const role = me?.role ?? user?.role ?? "—";
  const id = me?.id ?? user?.id ?? "—";
  const discordLinked = me?.discord_user_id?.trim() || null;
  const created = me?.created_at
    ? new Date(me.created_at).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : null;

  return (
    <div className="mx-auto max-w-xl space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-white">Profile</h1>
        <p className="mt-2 text-sm text-surface-muted">
          Session and account data from <code className="rounded bg-white/5 px-1 text-xs">GET /auth/me</code>.
          To link your Discord user id for bridge bots, use{" "}
          <Link to="/settings/connections" className="text-sky-400 hover:underline">
            Settings → Connections
          </Link>
          . Password changes are not exposed in the API yet; use an admin account to reset access if needed.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-surface-muted">Loading…</p>
      ) : err ? (
        <p className="text-sm text-amber-400">{err}</p>
      ) : (
        <div className="rounded-xl border border-surface-border bg-surface-raised p-5">
          <dl className="space-y-4 text-sm">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-muted">Email</dt>
              <dd className="mt-1 text-white">{email}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-muted">User id</dt>
              <dd className="mt-1 break-all font-mono text-xs text-neutral-300">{id}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-muted">Discord user id (linked)</dt>
              <dd className="mt-1 font-mono text-xs text-neutral-300">{discordLinked ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-muted">Role</dt>
              <dd className="mt-1">
                <span
                  className={
                    String(role).toLowerCase() === "admin"
                      ? "rounded bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-300"
                      : "rounded bg-sky-500/20 px-2 py-0.5 text-xs text-sky-300"
                  }
                >
                  {role}
                </span>
              </dd>
            </div>
            {created ? (
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-surface-muted">Member since</dt>
                <dd className="mt-1 text-neutral-300">{created}</dd>
              </div>
            ) : null}
          </dl>
          <button
            type="button"
            className="mt-6 text-xs text-sky-400 hover:text-sky-300 hover:underline"
            onClick={() => void load()}
          >
            Refresh
          </button>
        </div>
      )}

      <div className="rounded-xl border border-surface-border bg-black/20 p-5">
        <h2 className="text-sm font-medium text-white">Session</h2>
        <p className="mt-1 text-xs text-surface-muted">
          You stay signed in with an HTTP-only refresh cookie. Access tokens are short-lived.
        </p>
        <button
          type="button"
          className="mt-4 rounded-md border border-white/15 bg-white/5 px-4 py-2 text-sm text-neutral-200 hover:bg-white/10"
          onClick={() => void logout()}
        >
          Sign out
        </button>
      </div>
    </div>
  );
}
