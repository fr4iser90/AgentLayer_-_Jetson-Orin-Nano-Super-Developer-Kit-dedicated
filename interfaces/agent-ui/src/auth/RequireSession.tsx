import { Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

/**
 * Access token only in React memory; refresh uses httpOnly cookie (see POST /auth/login).
 */
export function RequireSession() {
  const { accessToken, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-full min-h-0 flex-1 items-center justify-center px-4 text-sm text-surface-muted">
        Loading…
      </div>
    );
  }

  if (!accessToken) {
    window.location.replace("/app/login");
    return (
      <div className="flex h-full min-h-0 flex-1 items-center justify-center px-4 text-sm text-surface-muted">
        Redirecting to sign in…
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden">
      <Outlet />
    </div>
  );
}
