import { Link } from "react-router-dom";

const cardClass =
  "block rounded-xl border border-surface-border bg-surface-raised px-5 py-4 text-white hover:bg-white/5";

export function AdminDashboard() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-white">Operator admin</h1>
      <p className="mt-2 text-sm text-surface-muted">
        Connection keys, tools, and registry — same APIs as before, now under the first-party app.
      </p>
      <ul className="mt-8 grid gap-3 sm:grid-cols-2">
        <li>
          <Link to="/admin/interfaces" className={cardClass}>
            <span className="font-medium">Interfaces</span>
            <span className="mt-1 block text-sm text-surface-muted">
              Optional connection key, Discord application ID
            </span>
          </Link>
        </li>
        <li>
          <Link to="/admin/tools" className={cardClass}>
            <span className="font-medium">Tools</span>
            <span className="mt-1 block text-sm text-surface-muted">
              Registry list and reload
            </span>
          </Link>
        </li>
        <li>
          <Link to="/admin/users" className={cardClass}>
            <span className="font-medium">Users</span>
            <span className="mt-1 block text-sm text-surface-muted">
              Session user and profile
            </span>
          </Link>
        </li>
        <li>
          <Link to="/admin/workflows" className={cardClass}>
            <span className="font-medium">Workflows</span>
            <span className="mt-1 block text-sm text-surface-muted">Placeholder</span>
          </Link>
        </li>
      </ul>
    </div>
  );
}
