import { Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

/**
 * Access token only in React memory; refresh uses httpOnly cookie (see POST /auth/login).
 */
export function RequireSession() {
  const { accessToken, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center px-4 text-sm text-surface-muted">
        Loading…
      </div>
    );
  }

  if (!accessToken) {
    window.location.replace("/login");
    return (
      <div className="flex min-h-[40vh] items-center justify-center px-4 text-sm text-surface-muted">
        Redirecting to sign in…
      </div>
    );
  }

  return <Outlet />;
}
