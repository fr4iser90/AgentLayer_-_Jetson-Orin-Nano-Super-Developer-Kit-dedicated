/**
 * Shared authentication helpers for control panel pages.
 */

const AUTH_KEYS = {
  ACCESS_TOKEN: "agent_access_token",
  REFRESH_TOKEN: "agent_refresh_token",
  USER: "agent_user"
};

let authState = {
  accessToken: localStorage.getItem(AUTH_KEYS.ACCESS_TOKEN),
  refreshToken: localStorage.getItem(AUTH_KEYS.REFRESH_TOKEN),
  user: JSON.parse(localStorage.getItem(AUTH_KEYS.USER) || "null")
};

function isLoggedIn() {
  return !!authState.accessToken && !!authState.user;
}

function requireAuth() {
  if (!isLoggedIn()) {
    window.location.href = "/control/login.html";
  }
}

async function apiRequest(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...options.headers
  };

  if (authState.accessToken) {
    headers["Authorization"] = `Bearer ${authState.accessToken}`;
  }

  let res = await fetch(`/${path}`, {
    ...options,
    headers
  });

  if (res.status === 401 && authState.refreshToken) {
    try {
      const refreshRes = await fetch("/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: authState.refreshToken })
      });

      if (refreshRes.ok) {
        const refreshData = await refreshRes.json();
        authState.accessToken = refreshData.access_token;
        localStorage.setItem(AUTH_KEYS.ACCESS_TOKEN, authState.accessToken);
        headers["Authorization"] = `Bearer ${authState.accessToken}`;
        return fetch(`/${path}`, { ...options, headers });
      }
    } catch (e) {}

    logout();
    throw new Error("Session expired");
  }

  return res;
}

async function login(email, password) {
  const res = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });

  if (!res.ok) {
    return { ok: false, error: "Invalid email or password" };
  }

  const data = await res.json();

  authState.accessToken = data.access_token;
  authState.refreshToken = data.refresh_token;
  authState.user = data.user;

  localStorage.setItem(AUTH_KEYS.ACCESS_TOKEN, authState.accessToken);
  localStorage.setItem(AUTH_KEYS.REFRESH_TOKEN, authState.refreshToken);
  localStorage.setItem(AUTH_KEYS.USER, JSON.stringify(authState.user));

  return { ok: true };
}

function logout() {
  authState.accessToken = null;
  authState.refreshToken = null;
  authState.user = null;

  localStorage.removeItem(AUTH_KEYS.ACCESS_TOKEN);
  localStorage.removeItem(AUTH_KEYS.REFRESH_TOKEN);
  localStorage.removeItem(AUTH_KEYS.USER);

  window.location.href = "/control/login.html";
}

function getCurrentUser() {
  return authState.user;
}
