import { useEffect, useState } from "react";

/**
 * P0 shell: health check against same-origin Agent Layer (or Vite proxy in dev).
 */
export function App() {
  const [health, setHealth] = useState<string>("loading…");

  useEffect(() => {
    fetch("/health")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((j) => setHealth(JSON.stringify(j)))
      .catch(() => setHealth("unreachable (start Agent Layer on :8080 or use npm run dev proxy)"));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: "2rem", maxWidth: "42rem" }}>
      <h1>Agent Layer UI</h1>
      <p>
        Served under <code>/app</code> from the same container as the API (Option A). Legacy
        control panel: <a href="/control/">/control/</a>
      </p>
      <h2>GET /health</h2>
      <pre style={{ background: "#111", color: "#eee", padding: "1rem", borderRadius: 8 }}>
        {health}
      </pre>
      <p style={{ color: "#666", fontSize: "0.9rem" }}>
        Dev: <code>cd interfaces/agent-ui && npm run dev</code> — proxies /auth and /v1 to
        localhost:8080.
      </p>
    </main>
  );
}
