import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function RequireAdmin() {
  const { accessToken, user, loading } = useAuth();

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

  if (user?.role?.toLowerCase() !== "admin") {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
