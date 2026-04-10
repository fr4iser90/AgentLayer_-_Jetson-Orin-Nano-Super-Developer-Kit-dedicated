import type { AuthContextValue } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";
import type { AgentTimelineEntry, ChatMode, ChatThread, UiMessage } from "./chatThreadStorage";
import { normalizeServerContent } from "./messageFormat";

type ApiMessage = { role: "user" | "assistant" | "system"; content: unknown };

function serializeMessageContent(content: string): string | unknown[] {
  if (typeof content === "string" && content.trim().startsWith("[")) {
    try {
      const p = JSON.parse(content) as unknown;
      if (Array.isArray(p)) return p;
    } catch {
      /* keep string */
    }
  }
  return content;
}

/** List endpoint row (no message bodies). */
export function mapListItemToThread(item: Record<string, unknown>): ChatThread {
  return {
    id: String(item.id ?? ""),
    title: typeof item.title === "string" ? item.title : "",
    mode: item.mode === "agent" ? "agent" : "chat",
    model: typeof item.model === "string" ? item.model : "",
    messages: [],
    agentLog: [],
    updatedAt: Date.parse(String(item.updated_at ?? Date.now())) || Date.now(),
  };
}

export function mapServerToThread(raw: Record<string, unknown>): ChatThread {
  const messages = Array.isArray(raw.messages)
    ? (raw.messages as ApiMessage[]).map((m) => {
        const c = (m as { content?: unknown }).content;
        return {
          role: m.role === "assistant" || m.role === "user" ? m.role : "user",
          content: normalizeServerContent(c),
        };
      })
    : [];
  const agentLog = Array.isArray(raw.agent_log)
    ? (raw.agent_log as AgentTimelineEntry[])
    : [];
  return {
    id: String(raw.id ?? ""),
    title: typeof raw.title === "string" ? raw.title : "",
    mode: raw.mode === "agent" ? "agent" : "chat",
    model: typeof raw.model === "string" ? raw.model : "",
    messages,
    agentLog,
    updatedAt: Date.parse(String(raw.updated_at ?? Date.now())) || Date.now(),
  };
}

export async function fetchConversationList(auth: Pick<AuthContextValue, "accessToken" | "refresh">) {
  const r = await apiFetch("/v1/user/conversations", auth);
  const data = (await r.json()) as { conversations?: Record<string, unknown>[] };
  if (!r.ok) throw new Error("failed to list conversations");
  return data.conversations ?? [];
}

export async function fetchConversationDetail(
  auth: Pick<AuthContextValue, "accessToken" | "refresh">,
  id: string
) {
  const r = await apiFetch(`/v1/user/conversations/${encodeURIComponent(id)}`, auth);
  const data = (await r.json()) as { conversation?: Record<string, unknown> };
  if (!r.ok) throw new Error("failed to load conversation");
  return mapServerToThread(data.conversation ?? {});
}

export async function createConversation(
  auth: Pick<AuthContextValue, "accessToken" | "refresh">,
  body: {
    title: string;
    mode: ChatMode;
    model: string;
    messages: UiMessage[];
    agent_log: AgentTimelineEntry[];
  }
) {
  const r = await apiFetch("/v1/user/conversations", auth, {
    method: "POST",
    body: JSON.stringify({
      title: body.title,
      mode: body.mode,
      model: body.model,
      messages: body.messages.map((m) => ({ role: m.role, content: serializeMessageContent(m.content) })),
      agent_log: body.agent_log,
    }),
  });
  const data = (await r.json()) as { conversation?: Record<string, unknown> };
  if (!r.ok) throw new Error("failed to create conversation");
  return mapServerToThread(data.conversation ?? {});
}

export async function putConversation(
  auth: Pick<AuthContextValue, "accessToken" | "refresh">,
  thread: ChatThread
) {
  const r = await apiFetch(`/v1/user/conversations/${encodeURIComponent(thread.id)}`, auth, {
    method: "PUT",
    body: JSON.stringify({
      title: thread.title,
      mode: thread.mode,
      model: thread.model,
      messages: thread.messages.map((m) => ({
        role: m.role,
        content: serializeMessageContent(m.content),
      })),
      agent_log: thread.agentLog ?? [],
    }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(
      err && typeof err === "object" && "detail" in err ? String((err as { detail: unknown }).detail) : "save failed"
    );
  }
}

export async function deleteConversationApi(
  auth: Pick<AuthContextValue, "accessToken" | "refresh">,
  id: string
) {
  const r = await apiFetch(`/v1/user/conversations/${encodeURIComponent(id)}`, auth, {
    method: "DELETE",
  });
  if (!r.ok) throw new Error("delete failed");
}
