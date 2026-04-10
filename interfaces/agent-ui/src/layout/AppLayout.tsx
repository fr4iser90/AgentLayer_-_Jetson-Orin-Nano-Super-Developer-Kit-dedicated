import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const GITHUB_REPO =
  "https://github.com/fr4iser90/AgentLayer_-_Jetson-Orin-Nano-Super-Developer-Kit-dedicated";

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
    <div className="flex h-dvh min-h-0 flex-col overflow-hidden">
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
      <div className="min-h-0 flex-1 overflow-hidden [&>*]:h-full [&>*]:min-h-0">
        <Outlet />
      </div>
      <footer className="shrink-0 border-t border-surface-border bg-surface-raised/80 px-4 py-2">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[11px] text-surface-muted">
          <a
            href={GITHUB_REPO}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-neutral-300"
          >
            GitHub
          </a>
          <span className="text-white/15" aria-hidden>
            ·
          </span>
          <NavLink to="/docs" className="hover:text-neutral-300">
            Docs
          </NavLink>
          <span className="text-white/15" aria-hidden>
            ·
          </span>
          <span className="text-white/25">Agent Layer</span>
        </div>
      </footer>
    </div>
  );
}
