import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type UserRow = {
  id: string;
  email: string;
  role: string;
  created_at: string;
  external_sub?: string | null;
  display_name?: string | null;
};

function rowLabel(r: UserRow): string {
  if (r.email?.trim()) return r.email.trim();
  if (r.display_name?.trim()) return r.display_name.trim();
  if (r.external_sub?.trim()) return r.external_sub.trim();
  return r.id;
}

export function AdminUsers() {
  const auth = useAuth();
  const { user } = auth;
  const [rows, setRows] = useState<UserRow[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listErr, setListErr] = useState<string | null>(null);
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<"user" | "admin">("user");
  const [createBusy, setCreateBusy] = useState(false);
  const [createMsg, setCreateMsg] = useState<string | null>(null);

  const loadUsers = useCallback(async () => {
    setListLoading(true);
    setListErr(null);
    try {
      const res = await apiFetch("/v1/admin/users", auth);
      const data = (await res.json()) as { users?: UserRow[]; detail?: unknown };
      if (!res.ok) {
        setListErr(typeof data.detail === "string" ? data.detail : "Could not load users");
        setRows([]);
        return;
      }
      setRows(data.users ?? []);
    } catch (e) {
      setListErr(e instanceof Error ? e.message : "Could not load users");
      setRows([]);
    } finally {
      setListLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

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
        setCreateMsg(typeof data.detail === "string" ? data.detail : "Create failed");
        return;
      }
      setCreateMsg(`Created login for ${data.email} (role: ${data.role}). They can sign in at /login.`);
      setNewEmail("");
      setNewPassword("");
      await loadUsers();
    } catch (e) {
      setCreateMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setCreateBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-white">Users</h1>
      <p className="mt-2 text-sm text-surface-muted">
        All password accounts in the database. Chat threads are stored per user.
        {user?.email ? (
          <span className="ml-1 text-neutral-500">
            You are signed in as <span className="text-neutral-300">{user.email}</span>.
          </span>
        ) : null}
      </p>

      <section className="mt-8">
        <h2 className="text-sm font-medium text-white">All accounts</h2>
        <p className="mt-1 text-xs text-surface-muted">
          <code className="text-neutral-500">GET /v1/admin/users</code>
        </p>
        <div className="mt-3 overflow-x-auto rounded-xl border border-surface-border">
          <table className="w-full min-w-[28rem] text-left text-sm">
            <thead className="border-b border-surface-border bg-black/20 text-surface-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Email / identity</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {listLoading ? (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-center text-surface-muted">
                    Loading…
                  </td>
                </tr>
              ) : listErr ? (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-center text-red-400">
                    {listErr}
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-center text-surface-muted">
                    No users found.
                  </td>
                </tr>
              ) : (
                rows.map((r) => (
                  <tr key={r.id} className="border-b border-surface-border/80 hover:bg-white/[0.03]">
                    <td className="px-4 py-3 text-white">
                      <span className="font-medium">{rowLabel(r)}</span>
                      {r.email?.trim() ? null : (
                        <span className="mt-0.5 block text-xs font-normal text-surface-muted">
                          no mailbox on file
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={
                          r.role?.toLowerCase() === "admin"
                            ? "rounded bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-300"
                            : "rounded bg-sky-500/20 px-2 py-0.5 text-xs text-sky-300"
                        }
                      >
                        {r.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-surface-muted">
                      {r.created_at
                        ? new Date(r.created_at).toLocaleString(undefined, {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <button
          type="button"
          className="mt-2 text-xs text-sky-400 hover:text-sky-300 hover:underline"
          onClick={() => void loadUsers()}
        >
          Refresh list
        </button>
      </section>

      <section className="mt-10 rounded-xl border border-surface-border bg-surface-raised p-5">
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
    </div>
  );
}
