import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiFetch } from "../lib/api";
import {
  NEW_CHAT_TITLE,
  type AgentTimelineEntry,
  type ChatMode,
  type ChatThread,
  type UiMessage,
  exportThreadJson,
  titleFromFirstMessage,
} from "../features/chat/chatThreadStorage";
import {
  createConversation,
  deleteConversationApi,
  fetchConversationDetail,
  fetchConversationList,
  mapListItemToThread,
  putConversation,
} from "../features/chat/conversationsApi";
import {
  buildUserMessageContent,
  filesToAttachments,
  parseContentParts,
  toApiContent,
  type PendingAttachment,
} from "../features/chat/messageFormat";
import { getDisabledToolNames } from "../features/settings/toolPrefs";

const SUGGESTED = [
  "Show me a code snippet of a website's sticky header",
  "Explain options trading if I'm familiar with buying and selling stocks",
  "Help me study vocabulary for a college entrance exam",
];

function wsUrl(token: string): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/v1/chat?token=${encodeURIComponent(token)}`;
}

/** `?workspace=<uuid>` — validated; server re-checks access. */
function parseWorkspaceQueryParam(raw: string | null): string | null {
  if (!raw || !raw.trim()) return null;
  const s = raw.trim();
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(s)
  ) {
    return null;
  }
  return s;
}

function assistantFromCompletion(data: unknown): string {
  if (!data || typeof data !== "object") return "";
  const d = data as {
    choices?: Array<{ message?: { content?: unknown } }>;
  };
  const c = d.choices?.[0]?.message?.content;
  if (typeof c === "string") return c;
  if (Array.isArray(c)) {
    return c
      .map((part: unknown) => {
        if (part && typeof part === "object" && "text" in part) {
          return String((part as { text?: string }).text ?? "");
        }
        return "";
      })
      .join("");
  }
  return "";
}

function MessageBody({ content }: { content: string }) {
  const { plain, parts } = parseContentParts(content);
  if (parts) {
    return (
      <div className="space-y-2">
        {parts.map((p, i) => {
          if (p.type === "text" && p.text) {
            return (
              <div key={i} className="whitespace-pre-wrap">
                {p.text}
              </div>
            );
          }
          if (p.type === "image_url" && p.image_url?.url) {
            return (
              <img
                key={i}
                src={p.image_url.url}
                alt=""
                className="max-h-64 max-w-full rounded-md border border-white/10 object-contain"
              />
            );
          }
          return null;
        })}
      </div>
    );
  }
  return <div className="whitespace-pre-wrap">{plain}</div>;
}

export function ChatPage() {
  const auth = useAuth();
  const { accessToken, user } = auth;
  const userId = user?.id ?? "";
  const [searchParams, setSearchParams] = useSearchParams();

  const workspaceChatId = useMemo(
    () => parseWorkspaceQueryParam(searchParams.get("workspace")),
    [searchParams]
  );
  const [workspaceChatTitle, setWorkspaceChatTitle] = useState<string | null>(null);
  const agentWorkspacePayload = useMemo(
    () =>
      workspaceChatId
        ? { agent_workspace_context: { workspace_id: workspaceChatId } }
        : ({} as Record<string, unknown>),
    [workspaceChatId]
  );

  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [composerDragActive, setComposerDragActive] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const agentHandlerRef = useRef<(ev: MessageEvent) => void>(() => {});
  const activeThreadIdRef = useRef<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  activeThreadIdRef.current = activeThreadId;

  const displayName = useMemo(() => {
    const e = user?.email;
    if (!e) return "there";
    return e.split("@")[0] ?? "there";
  }, [user?.email]);

  const activeThread = useMemo(
    () => threads.find((t) => t.id === activeThreadId) ?? null,
    [threads, activeThreadId]
  );

  const messages = activeThread?.messages ?? [];
  const mode: ChatMode = activeThread?.mode ?? "chat";
  const model = activeThread?.model ?? "";
  const agentLog: AgentTimelineEntry[] = activeThread?.agentLog ?? [];

  const defaultModel = models[0] ?? "";

  useEffect(() => {
    setHydrated(false);
  }, [userId]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const r = await fetch("/v1/models");
        if (!r.ok) return;
        const d = (await r.json()) as { data?: Array<{ id?: string }> };
        const ids = (d.data ?? []).map((x) => x.id).filter(Boolean) as string[];
        if (cancelled) return;
        setModels(ids);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!workspaceChatId || !accessToken) {
      setWorkspaceChatTitle(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiFetch(`/v1/workspaces/${workspaceChatId}`, auth);
        const j = (await res.json()) as { workspace?: { title?: string } };
        if (cancelled) return;
        if (res.ok && j.workspace?.title) setWorkspaceChatTitle(j.workspace.title);
        else setWorkspaceChatTitle(null);
      } catch {
        if (!cancelled) setWorkspaceChatTitle(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceChatId, accessToken, auth]);

  useEffect(() => {
    if (!accessToken || !userId) return;
    let cancelled = false;
    void (async () => {
      try {
        const listRaw = await fetchConversationList(auth);
        if (cancelled) return;
        if (listRaw.length === 0) {
          let modelForNew = "";
          try {
            const mr = await fetch("/v1/models");
            if (mr.ok) {
              const md = (await mr.json()) as { data?: Array<{ id?: string }> };
              modelForNew = (md.data ?? []).map((x) => x.id).filter(Boolean)[0] ?? "";
            }
          } catch {
            /* use empty */
          }
          const t = await createConversation(auth, {
            title: NEW_CHAT_TITLE,
            mode: "chat",
            model: modelForNew,
            messages: [],
            agent_log: [],
          });
          if (cancelled) return;
          setThreads([t]);
          setActiveThreadId(t.id);
          setSearchParams({ c: t.id }, { replace: true });
          setHydrated(true);
          return;
        }
        const mapped = listRaw.map((row) => mapListItemToThread(row as Record<string, unknown>));
        setThreads(mapped);
        const fromUrl = new URLSearchParams(window.location.search).get("c");
        const pick =
          fromUrl && mapped.some((x) => x.id === fromUrl) ? fromUrl : mapped[0].id;
        setActiveThreadId(pick);
        const full = await fetchConversationDetail(auth, pick);
        if (cancelled) return;
        setThreads((prev) => prev.map((th) => (th.id === full.id ? full : th)));
        setSearchParams({ c: pick }, { replace: true });
        setHydrated(true);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Could not load chats (server sync)");
          setHydrated(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, userId, auth, setSearchParams]);

  /** Prefill composer from Tools settings: `/chat?try=${encodeURIComponent(prompt)}` */
  useEffect(() => {
    const tryText = searchParams.get("try");
    if (!tryText?.trim() || !hydrated) return;
    let decoded = tryText;
    try {
      decoded = decodeURIComponent(tryText.replace(/\+/g, " "));
    } catch {
      /* use raw */
    }
    setDraft((prev) => (prev.trim() ? prev : decoded));
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev);
        n.delete("try");
        return n;
      },
      { replace: true },
    );
  }, [hydrated, searchParams, setSearchParams]);

  useEffect(() => {
    if (mode !== "agent" && wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, [mode]);

  useEffect(() => {
    if (!loading) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [loading]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, loading, activeThreadId]);

  const selectThread = useCallback(
    async (id: string) => {
      if (id === activeThreadId) return;
      setActiveThreadId(id);
      setSearchParams({ c: id });
      setError(null);
      try {
        const full = await fetchConversationDetail(auth, id);
        setThreads((prev) => prev.map((th) => (th.id === id ? full : th)));
      } catch {
        /* keep list row */
      }
    },
    [activeThreadId, auth, setSearchParams]
  );

  const patchThread = useCallback((id: string, patch: Partial<ChatThread>) => {
    setThreads((prev) =>
      prev.map((t) => (t.id === id ? { ...t, ...patch, updatedAt: Date.now() } : t))
    );
  }, []);

  const addPickedFiles = useCallback(async (files: FileList | File[] | null) => {
    if (!files?.length) return;
    try {
      const next = await filesToAttachments(files);
      setPendingAttachments((prev) => [...prev, ...next]);
    } catch {
      setError("Could not read file");
    }
  }, []);

  const setMode = useCallback(
    (m: ChatMode) => {
      if (!activeThreadId) return;
      setThreads((prev) => {
        const next = prev.map((t) =>
          t.id === activeThreadId ? { ...t, mode: m, updatedAt: Date.now() } : t
        );
        const th = next.find((x) => x.id === activeThreadId);
        if (th) void putConversation(auth, th).catch(() => {});
        return next;
      });
    },
    [activeThreadId, auth]
  );

  const setModel = useCallback(
    (m: string) => {
      if (!activeThreadId) return;
      setThreads((prev) => {
        const next = prev.map((t) =>
          t.id === activeThreadId ? { ...t, model: m, updatedAt: Date.now() } : t
        );
        const th = next.find((x) => x.id === activeThreadId);
        if (th) void putConversation(auth, th).catch(() => {});
        return next;
      });
    },
    [activeThreadId, auth]
  );

  const appendAgentLine = useCallback((kind: string, text: string) => {
    const tid = activeThreadIdRef.current;
    if (!tid) return;
    setThreads((prev) =>
      prev.map((t) => {
        if (t.id !== tid) return t;
        const next: AgentTimelineEntry[] = [
          ...(t.agentLog ?? []),
          { id: `${Date.now()}-${(t.agentLog ?? []).length}`, kind, text },
        ];
        return { ...t, agentLog: next, updatedAt: Date.now() };
      })
    );
  }, []);

  const runChatHttp = useCallback(async () => {
    if (!accessToken || !activeThreadId) return;
    const tid = activeThreadId;
    const t = threads.find((x) => x.id === tid);
    if (!t || !t.model.trim()) return;

    const userContent = buildUserMessageContent(draft, pendingAttachments);
    if (!userContent) return;

    setError(null);
    setLoading(true);
    const firstUser = t.messages.length === 0;
    const nextMessages: UiMessage[] = [...t.messages, { role: "user", content: userContent }];
    const nextTitle = firstUser ? titleFromFirstMessage(userContent) : t.title;
    patchThread(tid, { messages: nextMessages, title: nextTitle });
    setDraft("");
    setPendingAttachments([]);

    try {
      const disabledTools = getDisabledToolNames();
      const res = await apiFetch("/v1/chat/completions", auth, {
        method: "POST",
        body: JSON.stringify({
          model: t.model,
          messages: nextMessages.map((m) => ({ role: m.role, content: toApiContent(m.content) })),
          stream: false,
          ...agentWorkspacePayload,
          ...(disabledTools.length ? { agent_disabled_tools: disabledTools } : {}),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(String((data as { detail?: unknown }).detail ?? res.statusText));
        return;
      }
      const content = assistantFromCompletion(data);
      setThreads((prev) => {
        const next = prev.map((th) => {
          if (th.id !== tid) return th;
          const updated: ChatThread = {
            ...th,
            messages: [...th.messages, { role: "assistant", content: content || "(empty)" }],
            updatedAt: Date.now(),
          };
          void putConversation(auth, updated).catch(() => {});
          return updated;
        });
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [accessToken, activeThreadId, agentWorkspacePayload, auth, draft, pendingAttachments, patchThread, threads]);

  const ensureAgentWs = useCallback((): Promise<WebSocket> => {
    return new Promise((resolve, reject) => {
      const tok = accessToken;
      if (!tok) {
        reject(new Error("Not signed in"));
        return;
      }
      const existing = wsRef.current;
      if (existing?.readyState === WebSocket.OPEN) {
        resolve(existing);
        return;
      }
      if (existing) {
        existing.close();
        wsRef.current = null;
      }
      const ws = new WebSocket(wsUrl(tok));
      ws.onopen = () => {
        wsRef.current = ws;
        ws.onmessage = (ev) => agentHandlerRef.current(ev);
        resolve(ws);
      };
      ws.onerror = () => reject(new Error("WebSocket connection failed"));
      ws.onclose = () => {
        if (wsRef.current === ws) wsRef.current = null;
      };
    });
  }, [accessToken]);

  const runAgentWs = useCallback(async () => {
    if (!accessToken || !activeThreadId) return;
    const tid = activeThreadId;
    const t = threads.find((x) => x.id === tid);
    if (!t || !t.model.trim()) return;

    const userContent = buildUserMessageContent(draft, pendingAttachments);
    if (!userContent) return;

    setError(null);
    setLoading(true);
    const firstUser = t.messages.length === 0;
    const nextMessages: UiMessage[] = [...t.messages, { role: "user", content: userContent }];
    const nextTitle = firstUser ? titleFromFirstMessage(userContent) : t.title;
    patchThread(tid, { messages: nextMessages, agentLog: [], title: nextTitle });
    setDraft("");
    setPendingAttachments([]);

    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      setLoading(false);
      const id = activeThreadIdRef.current;
      if (id) {
        setThreads((prev) => {
          const th = prev.find((x) => x.id === id);
          if (th) void putConversation(auth, th).catch(() => {});
          return prev;
        });
      }
    };

    agentHandlerRef.current = (ev: MessageEvent) => {
      try {
        const msg = JSON.parse(String(ev.data)) as Record<string, unknown>;
        const typ = msg.type;
        if (typ === "pong") return;
        if (typ === "error") {
          setError(typeof msg.detail === "string" ? msg.detail : "Agent error");
          finish();
          return;
        }
        if (typ === "chat.completion") {
          if (msg.error) {
            setError(typeof msg.detail === "string" ? msg.detail : "Cancelled or failed");
            finish();
            return;
          }
          const data = msg.data;
          const content = assistantFromCompletion(data);
          const id = activeThreadIdRef.current;
          if (id && content) {
            setThreads((prev) => {
              const next = prev.map((th) => {
                if (th.id !== id) return th;
                const updated: ChatThread = {
                  ...th,
                  messages: [...th.messages, { role: "assistant", content }],
                  updatedAt: Date.now(),
                };
                void putConversation(auth, updated).catch(() => {});
                return updated;
              });
              return next;
            });
          }
          finish();
          return;
        }
        if (typ === "agent.session") {
          const em = msg.effective_model != null ? String(msg.effective_model) : "";
          const mr = msg.model_resolution != null ? String(msg.model_resolution) : "";
          appendAgentLine("session", [em && `model: ${em}`, mr && `(${mr})`].filter(Boolean).join(" "));
          return;
        }
        if (typ === "agent.llm_round_start" || typ === "agent.llm_round") {
          const r = msg.round != null ? `round ${msg.round}` : "round";
          const ex =
            msg.content_excerpt != null ? String(msg.content_excerpt).slice(0, 200) : "";
          appendAgentLine("llm", `${r}${ex ? ` — ${ex}` : ""}`);
          return;
        }
        if (typ === "agent.tool_start") {
          appendAgentLine("tool", `→ ${String(msg.name ?? "tool")}`);
          return;
        }
        if (typ === "agent.tool_done") {
          const n = msg.name != null ? String(msg.name) : "tool";
          const ch = msg.result_chars != null ? String(msg.result_chars) : "";
          appendAgentLine("tool", `← ${n}${ch ? ` (${ch} chars)` : ""}`);
          return;
        }
        if (typ === "agent.step_wait") {
          appendAgentLine("wait", "Paused (step mode)");
          return;
        }
        if (typ === "agent.done" || typ === "agent.aborted" || typ === "agent.cancelled") {
          appendAgentLine(String(typ), String(msg.detail ?? ""));
          return;
        }
        appendAgentLine(String(typ ?? "event"), JSON.stringify(msg).slice(0, 300));
      } catch {
        setError("Invalid WebSocket message");
        finish();
      }
    };

    try {
      const ws = await ensureAgentWs();
      const disabledTools = getDisabledToolNames();
      ws.send(
        JSON.stringify({
          type: "chat",
          body: {
            model: t.model,
            messages: nextMessages.map((m) => ({ role: m.role, content: toApiContent(m.content) })),
            ...agentWorkspacePayload,
            ...(disabledTools.length ? { agent_disabled_tools: disabledTools } : {}),
          },
        })
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setLoading(false);
    }
  }, [
    accessToken,
    activeThreadId,
    agentWorkspacePayload,
    appendAgentLine,
    draft,
    pendingAttachments,
    ensureAgentWs,
    patchThread,
    threads,
    auth,
  ]);

  const onSend = () => {
    if (mode === "chat") void runChatHttp();
    else void runAgentWs();
  };

  const startNewChat = async () => {
    try {
      const t = await createConversation(auth, {
        title: NEW_CHAT_TITLE,
        mode: "chat",
        model: defaultModel,
        messages: [],
        agent_log: [],
      });
      setThreads((prev) => [t, ...prev]);
      setActiveThreadId(t.id);
      setSearchParams({ c: t.id });
      setDraft("");
      setError(null);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const deleteThread = async (id: string) => {
    if (!confirm("Delete this chat?")) return;
    try {
      await deleteConversationApi(auth, id);
      setThreads((prev) => {
        const next = prev.filter((t) => t.id !== id);
        if (next.length === 0) {
          void (async () => {
            try {
              const t = await createConversation(auth, {
                title: NEW_CHAT_TITLE,
                mode: "chat",
                model: defaultModel,
                messages: [],
                agent_log: [],
              });
              setThreads([t]);
              setActiveThreadId(t.id);
              setSearchParams({ c: t.id });
            } catch (err) {
              setError(err instanceof Error ? err.message : String(err));
            }
          })();
          return [];
        }
        if (id === activeThreadId) {
          const n = next[0];
          setActiveThreadId(n.id);
          setSearchParams({ c: n.id });
        }
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const renameThread = (id: string) => {
    const t = threads.find((x) => x.id === id);
    if (!t) return;
    const next = window.prompt("Chat title", t.title);
    if (next === null) return;
    const trimmed = next.trim();
    if (!trimmed) return;
    patchThread(id, { title: trimmed });
    void putConversation(auth, { ...t, title: trimmed }).catch(() => {});
  };

  const shareThread = async (t: ChatThread) => {
    const url = `${window.location.origin}/app/chat?c=${encodeURIComponent(t.id)}`;
    try {
      await navigator.clipboard.writeText(url + "\n\n" + exportThreadJson(t));
    } catch {
      setError("Could not copy");
    }
  };

  const sortedThreads = useMemo(
    () => [...threads].sort((a, b) => b.updatedAt - a.updatedAt),
    [threads]
  );

  const canSend = useMemo(() => {
    if (loading || !(model || defaultModel) || !accessToken) return false;
    return buildUserMessageContent(draft, pendingAttachments) !== "";
  }, [loading, model, defaultModel, accessToken, draft, pendingAttachments]);

  if (!hydrated || !userId) {
    return (
      <div className="flex h-full min-h-0 flex-1 items-center justify-center overflow-hidden text-sm text-surface-muted">
        Loading chats…
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-1 overflow-hidden bg-surface">
      <aside className="flex h-full min-h-0 w-[280px] shrink-0 flex-col border-r border-surface-border bg-[#111]">
        <div className="shrink-0 border-b border-surface-border p-3">
          <button
            type="button"
            onClick={() => void startNewChat()}
            className="w-full rounded-lg border border-surface-border bg-white/5 px-3 py-2 text-left text-sm text-neutral-200 hover:bg-white/10"
          >
            + New chat
          </button>
          <div className="mt-3 mb-2 text-xs font-medium uppercase tracking-wide text-surface-muted">
            Mode (this chat)
          </div>
          <div className="flex rounded-lg border border-surface-border bg-black/30 p-0.5">
            <button
              type="button"
              className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium ${
                mode === "chat" ? "bg-white/15 text-white" : "text-surface-muted hover:text-neutral-200"
              }`}
              onClick={() => setMode("chat")}
            >
              Chat
            </button>
            <button
              type="button"
              className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium ${
                mode === "agent" ? "bg-white/15 text-white" : "text-surface-muted hover:text-neutral-200"
              }`}
              onClick={() => setMode("agent")}
            >
              Agent
            </button>
          </div>
          <p className="mt-2 text-[11px] leading-snug text-surface-muted">
            <strong className="text-neutral-400">Chat:</strong> HTTP completion.{" "}
            <strong className="text-neutral-400">Agent:</strong> WebSocket. Chats sync to the server.
          </p>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-2">
          <p className="px-2 pb-1 text-xs font-medium uppercase tracking-wide text-surface-muted">
            Your chats
          </p>
          <ul className="flex flex-col gap-1">
            {sortedThreads.map((t) => (
              <li key={t.id}>
                <div
                  className={`group flex items-start gap-1 rounded-md px-2 py-2 ${
                    t.id === activeThreadId ? "bg-white/10" : "hover:bg-white/5"
                  }`}
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left text-sm text-neutral-200"
                    onClick={() => void selectThread(t.id)}
                  >
                    <span className="line-clamp-2">{t.title}</span>
                    <span className="mt-0.5 block text-[10px] text-surface-muted">
                      {new Date(t.updatedAt).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </button>
                  <div className="flex shrink-0 flex-col gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      type="button"
                      className="rounded px-1 text-[10px] text-surface-muted hover:text-white"
                      title="Rename"
                      onClick={() => renameThread(t.id)}
                    >
                      Ren
                    </button>
                    <button
                      type="button"
                      className="rounded px-1 text-[10px] text-surface-muted hover:text-white"
                      title="Copy link + JSON"
                      onClick={() => void shareThread(t)}
                    >
                      Share
                    </button>
                    <button
                      type="button"
                      className="rounded px-1 text-[10px] text-red-400/90 hover:text-red-300"
                      title="Delete"
                      onClick={() => void deleteThread(t.id)}
                    >
                      Del
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-surface-border px-6 py-4">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{activeThread?.title ?? "Chat"}</p>
            <label className="mt-2 block text-xs text-surface-muted">Ollama model</label>
            <select
              className="mt-1 rounded-lg border border-surface-border bg-[#1a1a1a] px-3 py-2 text-sm text-neutral-100"
              value={model || defaultModel}
              onChange={(e) => setModel(e.target.value)}
              disabled={!models.length}
            >
              {!models.length ? (
                <option>Loading models…</option>
              ) : (
                models.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))
              )}
            </select>
            <p className="mt-1 text-xs text-surface-muted">
              Titles from the first message. Open a shared chat: URL query <code className="text-neutral-500">?c=&lt;id&gt;</code>
              . From Workspaces: <code className="text-neutral-500">?workspace=&lt;uuid&gt;</code> sends{" "}
              <code className="text-neutral-500">agent_workspace_context</code> to the agent.
            </p>
          </div>
        </div>

        {workspaceChatId ? (
          <div className="shrink-0 border-b border-sky-900/40 bg-sky-950/25 px-6 py-2 text-sm text-sky-100/90">
            <span className="font-medium text-sky-200">Workspace context</span>
            {": "}
            {workspaceChatTitle ?? workspaceChatId}
            <span className="ml-2 text-xs text-sky-300/80">
              (this workspace id is passed to the agent; say &quot;add milk&quot; for this list)
            </span>
          </div>
        ) : null}

        {error ? (
          <div className="shrink-0 border-b border-red-900/50 bg-red-950/40 px-6 py-2 text-sm text-red-300">
            {error}
          </div>
        ) : null}

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row">
          <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-6 py-6">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-full border border-surface-border bg-white/5 text-lg font-semibold text-neutral-300">
                  AL
                </div>
                <h1 className="mt-4 text-2xl font-semibold tracking-tight text-white">
                  Hello, {displayName}
                </h1>
                <p className="mt-2 max-w-md text-sm text-surface-muted">
                  {mode === "chat"
                    ? "One completion per send. History is stored on the server. Attach images or text files below."
                    : "Agent: WebSocket with multiple rounds; activity on the right."}
                </p>
              </div>
            ) : (
              <ul className="mx-auto flex w-full max-w-3xl flex-col gap-3">
                {messages.map((m, i) => (
                  <li
                    key={`${i}-${m.role}-${m.content.slice(0, 24)}`}
                    className={`flex w-full ${m.role === "user" ? "justify-start" : "justify-end"}`}
                  >
                    <div
                      className={`max-w-[min(100%,42rem)] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                        m.role === "user"
                          ? "border border-sky-900/40 bg-[#1a2a3d] text-neutral-100"
                          : "border border-white/10 bg-[#1e1e1e] text-neutral-200"
                      }`}
                    >
                      <span className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-surface-muted">
                        {m.role === "user" ? "You" : "Assistant"}
                      </span>
                      {m.role === "user" ? (
                        <MessageBody content={m.content} />
                      ) : (
                        <div className="whitespace-pre-wrap">{m.content}</div>
                      )}
                    </div>
                  </li>
                ))}
                {loading ? (
                  <li className="flex w-full justify-end">
                    <div className="max-w-[min(100%,42rem)] rounded-2xl border border-sky-900/50 bg-sky-950/25 px-4 py-3 text-sm text-sky-100/90 shadow-sm">
                      <span className="mb-1 flex items-center gap-2 text-[10px] font-medium uppercase tracking-wide text-sky-300/80">
                        <span className="inline-flex h-2 w-2 animate-pulse rounded-full bg-sky-400" />
                        Assistant
                      </span>
                      <p className="text-neutral-300">
                        {mode === "agent" ? "Agent running (LLM / tools)…" : "Generating a reply…"}
                      </p>
                    </div>
                  </li>
                ) : null}
              </ul>
            )}
            <div ref={messagesEndRef} className="h-px w-full shrink-0" aria-hidden />
          </div>

          {mode === "agent" && agentLog.length > 0 ? (
            <div className="flex min-h-0 w-full shrink-0 flex-col border-t border-surface-border bg-black/20 lg:w-[300px] lg:border-l lg:border-t-0">
              <div className="shrink-0 border-b border-surface-border px-3 py-2 text-xs font-medium uppercase tracking-wide text-surface-muted">
                Agent activity
              </div>
              <ul className="min-h-0 flex-1 overflow-y-auto px-3 py-2 text-xs">
                {agentLog.map((e) => (
                  <li key={e.id} className="mb-2 border-l-2 border-sky-500/40 pl-2 text-neutral-400">
                    <span className="text-[10px] text-surface-muted">{e.kind}</span>
                    <div className="whitespace-pre-wrap text-neutral-300">{e.text}</div>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="shrink-0 border-t border-surface-border bg-[#0c0c0c] px-6 py-4">
          <div className="relative mx-auto max-w-3xl">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              accept="image/*,.txt,.md,.json,.csv,.log,.yaml,.yml,.zip"
              onChange={(e) => {
                const files = e.target.files;
                e.target.value = "";
                void addPickedFiles(files);
              }}
            />
            <div
              role="group"
              aria-label="Message composer — drop files here or use the attach button"
              className={`relative rounded-2xl border bg-[#141414] p-3 shadow-xl transition-colors ${
                composerDragActive
                  ? "border-sky-500/70 ring-2 ring-sky-500/25"
                  : "border-surface-border"
              }`}
              onDragEnter={(e) => {
                e.preventDefault();
                if (!Array.from(e.dataTransfer.types).includes("Files")) return;
                setComposerDragActive(true);
              }}
              onDragLeave={(e) => {
                const next = e.relatedTarget as Node | null;
                if (next && e.currentTarget.contains(next)) return;
                setComposerDragActive(false);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "copy";
              }}
              onDrop={(e) => {
                e.preventDefault();
                setComposerDragActive(false);
                if (loading) return;
                void addPickedFiles(e.dataTransfer.files);
              }}
            >
              {composerDragActive ? (
                <div
                  className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-sky-950/50 backdrop-blur-[1px]"
                  aria-hidden
                >
                  <p className="rounded-lg border border-sky-500/40 bg-black/50 px-4 py-2 text-sm font-medium text-sky-100">
                    Drop files to attach
                  </p>
                </div>
              ) : null}
              {pendingAttachments.length > 0 ? (
                <ul className="mb-2 flex flex-wrap gap-2">
                  {pendingAttachments.map((a, idx) => (
                    <li
                      key={`${a.name}-${idx}`}
                      className="flex max-w-full items-center gap-1 rounded-lg border border-white/10 bg-black/30 px-2 py-1 text-xs text-neutral-300"
                    >
                      <span className="truncate" title={a.kind === "unsupported" ? a.hint : a.name}>
                        {a.name}
                        {a.kind === "unsupported" ? " (not sent)" : ""}
                      </span>
                      <button
                        type="button"
                        className="shrink-0 rounded px-1 text-surface-muted hover:text-white"
                        aria-label="Remove attachment"
                        onClick={() => setPendingAttachments((prev) => prev.filter((_, i) => i !== idx))}
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
              <textarea
                className="min-h-[52px] w-full resize-none bg-transparent text-sm text-neutral-100 placeholder:text-neutral-500 focus:outline-none"
                placeholder="How can I help you today?"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={2}
                disabled={loading}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (canSend) onSend();
                  }
                }}
              />
              <div className="mt-2 flex items-center justify-between gap-2">
                <button
                  type="button"
                  disabled={loading}
                  className="rounded-lg border border-white/10 bg-black/20 p-2 text-surface-muted hover:bg-white/5 hover:text-neutral-200 disabled:opacity-40"
                  title="Attach or drag & drop files (images, text; zip not unpacked)"
                  aria-label="Attach files"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                  </svg>
                </button>
                <button
                  type="button"
                  disabled={!canSend}
                  className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-40"
                  onClick={() => onSend()}
                >
                  {loading ? "…" : "Send"}
                </button>
              </div>
            </div>

            {messages.length === 0 ? (
              <div className="mt-6">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-surface-muted">
                  Suggested
                </p>
                <ul className="flex flex-col gap-2">
                  {SUGGESTED.map((s) => (
                    <li key={s}>
                      <button
                        type="button"
                        className="w-full rounded-lg border border-surface-border bg-[#141414] px-4 py-3 text-left text-sm text-neutral-300 hover:bg-white/5"
                        onClick={() => setDraft(s)}
                      >
                        {s}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}
