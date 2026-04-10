import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type AuthUser = { id: string; email: string; role: string };

type AuthContextValue = {
  accessToken: string | null;
  user: AuthUser | null;
  loading: boolean;
  /** Returns new access token on success, or null if refresh failed. */
  refresh: () => Promise<string | null>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async (): Promise<string | null> => {
    const r = await fetch("/auth/refresh", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (r.ok) {
      const d = (await r.json()) as { access_token: string; user: AuthUser };
      setAccessToken(d.access_token);
      setUser(d.user ?? null);
      return d.access_token;
    }
    setAccessToken(null);
    setUser(null);
    return null;
  }, []);

  useEffect(() => {
    void (async () => {
      await refresh();
      setLoading(false);
    })();
  }, [refresh]);

  const logout = useCallback(async () => {
    await fetch("/auth/logout", { method: "POST", credentials: "include" });
    setAccessToken(null);
    setUser(null);
    window.location.href = "/login";
  }, []);

  const value = useMemo(
    () => ({ accessToken, user, loading, refresh, logout }),
    [accessToken, user, loading, refresh, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const c = useContext(AuthContext);
  if (!c) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return c;
}
