import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";

type TenantRow = { id: number; name?: string | null };

type UserRow = {
  id: string;
  email: string;
  role: string;
  created_at: string;
  external_sub?: string | null;
  display_name?: string | null;
  tenant_id?: number;
  tenant_name?: string | null;
  discord_user_id?: string | null;
};

function rowLabel(r: UserRow): string {
  if (r.email?.trim()) return r.email.trim();
  if (r.display_name?.trim()) return r.display_name.trim();
  if (r.external_sub?.trim()) return r.external_sub.trim();
  return r.id;
}

function tenantLabel(t: TenantRow): string {
  const n = (t.name ?? "").trim();
  return n ? `${n} (${t.id})` : `Tenant ${t.id}`;
}

export function AdminUsers() {
  const auth = useAuth();
  const { user } = auth;
  const [rows, setRows] = useState<UserRow[]>([]);
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listErr, setListErr] = useState<string | null>(null);
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<"user" | "admin">("user");
  const [newTenantId, setNewTenantId] = useState("1");
  const [createBusy, setCreateBusy] = useState(false);
  const [createMsg, setCreateMsg] = useState<string | null>(null);
  const [savingUserId, setSavingUserId] = useState<string | null>(null);
  const [newTenantName, setNewTenantName] = useState("");
  const [tenantCreateBusy, setTenantCreateBusy] = useState(false);
  const [tenantCreateMsg, setTenantCreateMsg] = useState<string | null>(null);

  const loadTenants = useCallback(async () => {
    try {
      const res = await apiFetch("/v1/admin/tenants", auth);
      const data = (await res.json()) as { tenants?: TenantRow[] };
      if (!res.ok) {
        setTenants([]);
        return;
      }
      setTenants(data.tenants ?? []);
    } catch {
      setTenants([]);
    }
  }, [auth]);

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

  const reloadAll = useCallback(async () => {
    await Promise.all([loadUsers(), loadTenants()]);
  }, [loadUsers, loadTenants]);

  useEffect(() => {
    void reloadAll();
  }, [reloadAll]);

  async function patchUserTenant(userId: string, tenantId: number) {
    setSavingUserId(userId);
    setListErr(null);
    try {
      const res = await apiFetch(`/v1/admin/users/${userId}`, auth, {
        method: "PATCH",
        body: JSON.stringify({ tenant_id: tenantId }),
      });
      const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
      if (!res.ok) {
        setListErr(typeof data.detail === "string" ? data.detail : "Could not update tenant");
        return;
      }
      await loadUsers();
    } catch (e) {
      setListErr(e instanceof Error ? e.message : "Could not update tenant");
    } finally {
      setSavingUserId(null);
    }
  }

  async function createUser() {
    const email = newEmail.trim();
    const password = newPassword;
    const tid = parseInt(newTenantId, 10);
    if (!email || password.length < 8) {
      setCreateMsg("Email and password (≥ 8 chars) required.");
      return;
    }
    if (!Number.isFinite(tid) || tid < 1) {
      setCreateMsg("Pick a valid tenant.");
      return;
    }
    setCreateMsg(null);
    setCreateBusy(true);
    try {
      const res = await apiFetch("/v1/admin/users", auth, {
        method: "POST",
        body: JSON.stringify({ email, password, role: newRole, tenant_id: tid }),
      });
      const data = (await res.json()) as {
        detail?: unknown;
        email?: string;
        role?: string;
        tenant_id?: number;
      };
      if (!res.ok) {
        setCreateMsg(typeof data.detail === "string" ? data.detail : "Create failed");
        return;
      }
      setCreateMsg(
        `Created login for ${data.email} (role: ${data.role}, tenant_id: ${data.tenant_id ?? tid}). They can sign in at /login.`,
      );
      setNewEmail("");
      setNewPassword("");
      await reloadAll();
    } catch (e) {
      setCreateMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setCreateBusy(false);
    }
  }

  async function createTenant() {
    const name = newTenantName.trim();
    if (!name) {
      setTenantCreateMsg("Name required (e.g. work, friends).");
      return;
    }
    setTenantCreateMsg(null);
    setTenantCreateBusy(true);
    try {
      const res = await apiFetch("/v1/admin/tenants", auth, {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      const data = (await res.json()) as { detail?: unknown; tenant?: { id: number } };
      if (!res.ok) {
        setTenantCreateMsg(typeof data.detail === "string" ? data.detail : "Create failed");
        return;
      }
      const id = data.tenant?.id;
      setTenantCreateMsg(`Created tenant “${name}”${id != null ? ` (id ${id})` : ""}.`);
      setNewTenantName("");
      await loadTenants();
      if (id != null) setNewTenantId(String(id));
    } catch (e) {
      setTenantCreateMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setTenantCreateBusy(false);
    }
  }

  const tenantOptions =
    tenants.length > 0
      ? tenants
      : [{ id: 1, name: "default" }];

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-white">Users</h1>
      <p className="mt-2 text-sm text-surface-muted">
        Password accounts in the database. Each user belongs to one{" "}
        <strong className="font-medium text-neutral-300">tenant</strong> (<span className="font-mono">users.tenant_id</span>
        ): same login always resolves to that tenant for chat, tools, and policy (Bearer/JWT or API key — no
        identity headers). Create named tenants (e.g. work, friends), then assign users here; use those numeric{" "}
        <span className="font-mono">id</span> values in tool allowlists on{" "}
        <Link to="/admin/tools" className="text-sky-400 hover:text-sky-300 hover:underline">
          Admin → Tools
        </Link>
        .
        {user?.email ? (
          <span className="ml-1 text-neutral-500">
            You are signed in as <span className="text-neutral-300">{user.email}</span>.
          </span>
        ) : null}
      </p>

      <section className="mt-8">
        <h2 className="text-sm font-medium text-white">All accounts</h2>
        <p className="mt-1 text-xs text-surface-muted">
          <code className="text-neutral-500">GET /v1/admin/users</code> ·{" "}
          <code className="text-neutral-500">PATCH /v1/admin/users/{"{id}"}</code> (<span className="font-mono">tenant_id</span>)
        </p>
        <div className="mt-3 overflow-x-auto rounded-xl border border-surface-border">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <thead className="border-b border-surface-border bg-black/20 text-surface-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Email / identity</th>
                <th className="px-4 py-3 font-medium">Tenant</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Discord id</th>
                <th className="px-4 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {listLoading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-surface-muted">
                    Loading…
                  </td>
                </tr>
              ) : listErr ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-red-400">
                    {listErr}
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-surface-muted">
                    No users found.
                  </td>
                </tr>
              ) : (
                rows.map((r) => {
                  const tid = r.tenant_id ?? 1;
                  const saving = savingUserId === r.id;
                  return (
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
                        <select
                          className="max-w-[14rem] rounded-md border border-surface-border bg-black/20 px-2 py-1.5 text-xs text-white"
                          value={tid}
                          disabled={saving}
                          onChange={(e) => {
                            const next = parseInt(e.target.value, 10);
                            if (!Number.isFinite(next) || next === tid) return;
                            void patchUserTenant(r.id, next);
                          }}
                        >
                          {tenantOptions.map((t) => (
                            <option key={t.id} value={t.id}>
                              {tenantLabel(t)}
                            </option>
                          ))}
                        </select>
                        {saving ? (
                          <span className="ml-2 text-[10px] text-surface-muted">Saving…</span>
                        ) : null}
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
                      <td className="px-4 py-3 font-mono text-xs text-neutral-400">
                        {r.discord_user_id?.trim() ? r.discord_user_id.trim() : "—"}
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
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        <button
          type="button"
          className="mt-2 text-xs text-sky-400 hover:text-sky-300 hover:underline"
          onClick={() => void reloadAll()}
        >
          Refresh list
        </button>
      </section>

      <section className="mt-10 rounded-xl border border-surface-border bg-surface-raised p-5">
        <h2 className="text-sm font-medium text-white">Create tenant</h2>
        <p className="mt-1 text-xs text-surface-muted">
          <code className="text-neutral-500">POST /v1/admin/tenants</code> — adds a row in{" "}
          <span className="font-mono">tenants</span> (new numeric <span className="font-mono">id</span> for allowlists
          and user assignment).
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <label className="block text-xs text-surface-muted">
            Display name
            <input
              type="text"
              className="mt-1 block w-full min-w-[12rem] rounded-md border border-surface-border bg-black/20 px-3 py-2 text-sm text-white"
              value={newTenantName}
              onChange={(e) => setNewTenantName(e.target.value)}
              placeholder="work"
              autoComplete="off"
            />
          </label>
          <button
            type="button"
            disabled={tenantCreateBusy}
            className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
            onClick={() => void createTenant()}
          >
            {tenantCreateBusy ? "…" : "Create tenant"}
          </button>
        </div>
        {tenantCreateMsg ? (
          <p
            className={`mt-3 text-sm ${tenantCreateMsg.startsWith("Created") ? "text-emerald-400" : "text-amber-400"}`}
          >
            {tenantCreateMsg}
          </p>
        ) : null}
      </section>

      <section className="mt-10 rounded-xl border border-surface-border bg-surface-raised p-5">
        <h2 className="text-sm font-medium text-white">Create user</h2>
        <p className="mt-1 text-xs text-surface-muted">
          <code className="text-neutral-500">POST /v1/admin/users</code> — optional{" "}
          <span className="font-mono">tenant_id</span> (default <span className="font-mono">1</span>).
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
            Tenant
            <select
              className="mt-1 block rounded-md border border-surface-border bg-black/20 px-3 py-2 text-sm text-white"
              value={newTenantId}
              onChange={(e) => setNewTenantId(e.target.value)}
            >
              {tenantOptions.map((t) => (
                <option key={t.id} value={t.id}>
                  {tenantLabel(t)}
                </option>
              ))}
            </select>
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
