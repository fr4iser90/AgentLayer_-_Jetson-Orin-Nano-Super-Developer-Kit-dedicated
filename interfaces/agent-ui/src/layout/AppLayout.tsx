import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  [
    "rounded-md px-3 py-2 text-sm transition-colors",
    isActive
      ? "bg-white/10 text-white"
      : "text-surface-muted hover:bg-white/5 hover:text-neutral-200",
  ].join(" ");

const signInClass =
  "rounded-md px-3 py-2 text-sm text-surface-muted hover:bg-white/5 hover:text-neutral-200";

export function AppLayout() {
  const { accessToken, user, loading, logout } = useAuth();
  const signedIn = !!accessToken && !!user;
  const isAdmin = user?.role?.toLowerCase() === "admin";

  return (
    <div className="flex min-h-full flex-col">
      <header className="flex shrink-0 items-center gap-2 border-b border-surface-border bg-surface-raised px-4 py-3">
        <span className="text-sm font-semibold tracking-tight text-white">Agent Layer</span>
        <nav className="flex flex-wrap gap-1">
          {loading ? (
            <span className="px-3 py-2 text-xs text-surface-muted">…</span>
          ) : signedIn ? (
            <>
              <NavLink to="/" end className={linkClass}>
                Home
              </NavLink>
              <NavLink to="/chat" className={linkClass}>
                Chat
              </NavLink>
              <NavLink to="/studio" className={linkClass}>
                Studio
              </NavLink>
              {isAdmin ? (
                <NavLink to="/admin" className={linkClass}>
                  Admin
                </NavLink>
              ) : null}
              <button type="button" className={signInClass} onClick={() => void logout()}>
                Sign out
              </button>
            </>
          ) : (
            <a href="/login" className={signInClass}>
              Sign in
            </a>
          )}
        </nav>
      </header>
      <div className="min-h-0 flex-1">
        <Outlet />
      </div>
    </div>
  );
}
