import type { AuthContextValue } from "../auth/AuthContext";

export type AgentDefinition = {
  id: string;
  name: string;
  icon: string;
  description: string;
  system_prompt: string;
  tool_domain: string | null;
  tool_names: string[];
  requires_workspace: boolean;
  execution_context: string;
  min_role: string;
  model_profile: string | null;
};

export async function fetchAgents(auth: Pick<AuthContextValue, "accessToken" | "refresh">): Promise<AgentDefinition[]> {
  const r = await apiFetch("/v1/agents", auth);
  if (!r.ok) return [];
  return r.json() as Promise<AgentDefinition[]>;
}

/**
 * Authenticated fetch with one retry after POST /auth/refresh on 401.
 */
export async function apiFetch(
  path: string,
  auth: Pick<AuthContextValue, "accessToken" | "refresh">,
  init?: RequestInit
): Promise<Response> {
  const url = path.startsWith("/") ? path : `/${path}`;
  const run = async (token: string | null) => {
    const headers = new Headers(init?.headers);
    if (
      init?.body != null &&
      !(init.body instanceof FormData) &&
      !headers.has("Content-Type")
    ) {
      headers.set("Content-Type", "application/json");
    }
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    return fetch(url, { ...init, credentials: "include", headers });
  };

  let token = auth.accessToken;
  let res = await run(token);
  if (res.status === 401) {
    const next = await auth.refresh();
    if (next) {
      res = await run(next);
    }
  }
  return res;
}
