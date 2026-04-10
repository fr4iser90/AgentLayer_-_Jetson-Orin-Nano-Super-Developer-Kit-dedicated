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
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<"user" | "admin">("user");
  const [createBusy, setCreateBusy] = useState(false);
  const [createMsg, setCreateMsg] = useState<string | null>(null);

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

  async function createUser() {
    const email = newEmail.trim();
    const password = newPassword;
    if (!email || password.length < 8) {
      setCreateMsg("Email and password (≥ 8 chars) required.");
      return;
    }
    setCreateMsg(null);
    setCreateBusy(true);
    try {
      const res = await apiFetch("/v1/admin/users", auth, {
        method: "POST",
        body: JSON.stringify({ email, password, role: newRole }),
      });
      const data = (await res.json()) as { detail?: unknown; email?: string; role?: string };
      if (!res.ok) {
        setCreateMsg(
          typeof data.detail === "string" ? data.detail : "Create failed"
        );
        return;
      }
      setCreateMsg(`Created login for ${data.email} (role: ${data.role}). They can sign in at /login.`);
      setNewEmail("");
      setNewPassword("");
    } catch (e) {
      setCreateMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setCreateBusy(false);
    }
  }

  const row = me ?? (user ? { id: user.id, email: user.email, role: user.role } : null);

  return (
    <div className="h-full min-h-0 overflow-y-auto">
      <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-white">Users</h1>
      <p className="mt-2 text-sm text-surface-muted">
        Chat threads are stored per user in the database (server sync). Create additional logins below.
      </p>

      <section className="mt-8 rounded-xl border border-surface-border bg-surface-raised p-5">
        <h2 className="text-sm font-medium text-white">Create user</h2>
        <p className="mt-1 text-xs text-surface-muted">
          <code className="text-neutral-500">POST /v1/admin/users</code> — normal accounts use role{" "}
          <code className="text-neutral-500">user</code>.
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <label className="block text-xs text-surface-muted">
            Email
            <input
              type="email"
              className="mt-1 block w-full min-w-[12rem] rounded-md border border-surface-border bg-black/20 px-3 py-2 text-sm text-white"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              autoComplete="off"
            />
          </label>
          <label className="block text-xs text-surface-muted">
            Password (≥ 8)
            <input
              type="password"
              className="mt-1 block w-full min-w-[12rem] rounded-md border border-surface-border bg-black/20 px-3 py-2 text-sm text-white"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
            />
          </label>
          <label className="block text-xs text-surface-muted">
            Role
            <select
              className="mt-1 block rounded-md border border-surface-border bg-black/20 px-3 py-2 text-sm text-white"
              value={newRole}
              onChange={(e) => setNewRole(e.target.value as "user" | "admin")}
            >
              <option value="user">user</option>
              <option value="admin">admin</option>
            </select>
          </label>
          <button
            type="button"
            disabled={createBusy}
            className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
            onClick={() => void createUser()}
          >
            {createBusy ? "…" : "Create user"}
          </button>
        </div>
        {createMsg ? (
          <p
            className={`mt-3 text-sm ${createMsg.startsWith("Created") ? "text-emerald-400" : "text-amber-400"}`}
          >
            {createMsg}
          </p>
        ) : null}
      </section>

      {err ? <p className="mt-4 text-sm text-red-400">{err}</p> : null}

      <h2 className="mb-2 mt-10 text-sm font-medium text-surface-muted">Current session</h2>
      <div className="overflow-x-auto rounded-xl border border-surface-border">
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
    </div>
  );
}
