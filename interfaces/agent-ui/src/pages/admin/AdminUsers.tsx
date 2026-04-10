import { useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type MeResponse = {
  id: string;
  email: string;
  role: string;
  created_at?: string;
};

export function AdminUsers() {
  const auth = useAuth();
  const { user } = auth;
  const [me, setMe] = useState<MeResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiFetch("/auth/me", auth);
        const data = await res.json();
        if (!res.ok) {
          if (!cancelled) setErr("Could not load profile");
          return;
        }
        if (!cancelled) setMe(data as MeResponse);
      } catch {
        if (!cancelled) setErr("Could not load profile");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [auth]);

  const row = me ?? (user ? { id: user.id, email: user.email, role: user.role } : null);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-white">Users</h1>
      <p className="mt-2 text-sm text-surface-muted">
        Full directory management will use a future API; here is your signed-in account.
      </p>

      {err ? <p className="mt-4 text-sm text-red-400">{err}</p> : null}

      <div className="mt-8 overflow-x-auto rounded-xl border border-surface-border">
        <table className="w-full min-w-[20rem] text-left text-sm">
          <thead className="border-b border-surface-border bg-black/20 text-surface-muted">
            <tr>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {row ? (
              <tr className="hover:bg-white/[0.03]">
                <td className="px-4 py-3 text-white">{row.email}</td>
                <td className="px-4 py-3">
                  <span
                    className={
                      row.role?.toLowerCase() === "admin"
                        ? "rounded bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-300"
                        : "rounded bg-sky-500/20 px-2 py-0.5 text-xs text-sky-300"
                    }
                  >
                    {row.role}
                  </span>
                </td>
                <td className="px-4 py-3 text-surface-muted">
                  {row.created_at
                    ? new Date(row.created_at).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })
                    : "—"}
                </td>
              </tr>
            ) : (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-surface-muted">
                  No user loaded.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
