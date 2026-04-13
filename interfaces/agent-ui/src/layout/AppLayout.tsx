import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { UserMenu } from "../components/UserMenu";

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
  const { accessToken, user, loading } = useAuth();
  const signedIn = !!accessToken && !!user;

  return (
    <div className="flex h-dvh min-h-0 flex-col overflow-hidden">
      <header className="flex shrink-0 items-center gap-3 border-b border-surface-border bg-surface-raised px-4 py-3">
        <span className="shrink-0 text-sm font-semibold tracking-tight text-white">Agent Layer</span>
        <nav className="flex min-w-0 flex-1 flex-wrap gap-1">
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
                Image generation
              </NavLink>
              <NavLink to="/workspace" className={linkClass}>
                Workspace
              </NavLink>
            </>
          ) : (
            <Link to="/login" className={signInClass}>
              Sign in
            </Link>
          )}
        </nav>
        {loading ? null : signedIn ? (
          <div className="ml-auto shrink-0">
            <UserMenu />
          </div>
        ) : null}
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
