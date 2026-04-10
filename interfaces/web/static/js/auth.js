/**
 * Session: refresh token in httpOnly cookie (set by POST /auth/login).
 * Access token + user only in memory (never localStorage).
 */

let authState = {
  accessToken: null,
  user: null,
};

function isLoggedIn() {
  return !!authState.accessToken && !!authState.user;
}

/**
 * Restore access token from refresh cookie. Call on each admin HTML page before requireAuth.
 */
async function bootstrapSession() {
  if (authState.accessToken && authState.user) {
    return true;
  }
  try {
    const res = await fetch("/auth/refresh", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (!res.ok) {
      authState.accessToken = null;
      authState.user = null;
      return false;
    }
    const data = await res.json();
    authState.accessToken = data.access_token;
    authState.user = data.user || null;
    return !!authState.accessToken && !!authState.user;
  } catch (e) {
    authState.accessToken = null;
    authState.user = null;
    return false;
  }
}

function requireAuth() {
  if (!isLoggedIn()) {
    window.location.href = "/login";
  }
}

async function apiRequest(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (authState.accessToken) {
    headers["Authorization"] = `Bearer ${authState.accessToken}`;
  }

  let res = await fetch(`/${path}`, {
    ...options,
    credentials: "include",
    headers,
  });

  if (res.status === 401) {
    try {
      const refreshRes = await fetch("/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (refreshRes.ok) {
        const refreshData = await refreshRes.json();
        authState.accessToken = refreshData.access_token;
        if (refreshData.user) authState.user = refreshData.user;
        headers["Authorization"] = `Bearer ${authState.accessToken}`;
        return fetch(`/${path}`, { ...options, credentials: "include", headers });
      }
    } catch (e) {}
    await logout();
    throw new Error("Session expired");
  }

  return res;
}

async function login(email, password) {
  const res = await fetch("/auth/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    return { ok: false, error: "Invalid email or password" };
  }

  const data = await res.json();
  authState.accessToken = data.access_token;
  authState.user = data.user;

  return { ok: true };
}

async function logout() {
  authState.accessToken = null;
  authState.user = null;
  try {
    await fetch("/auth/logout", { method: "POST", credentials: "include" });
  } catch (e) {}
  window.location.href = "/login";
}

function getCurrentUser() {
  return authState.user;
}
