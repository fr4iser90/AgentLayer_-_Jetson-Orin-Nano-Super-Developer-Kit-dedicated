import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";
import type { ChatThread } from "../chat/chatThreadStorage";
import {
  createConversation,
  fetchConversationDetail,
  fetchConversationList,
  putConversation,
} from "../chat/conversationsApi";
import { getDisabledToolNames } from "../settings/toolPrefs";
import type { PendingAttachment } from "../chat/messageFormat";
import {
  buildUserMessageContent,
  filesToAttachments,
  parseContentParts,
  toApiContent,
} from "../chat/messageFormat";

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

type Msg = { role: "user" | "assistant"; content: string };

function formatUserBubbleForList(raw: string): string {
  const { parts } = parseContentParts(raw);
  if (!parts) return raw;
  const texts = parts
    .filter((p) => p.type === "text")
    .map((p) => String((p as { text?: string }).text ?? ""))
    .join(" ")
    .trim();
  const nImg = parts.filter((p) => p.type === "image_url").length;
  const head = texts || "(Bild-Anhang)";
  if (nImg) return `${head} · ${nImg} Bild${nImg > 1 ? "er" : ""}`;
  return head;
}

type Props = {
  workspaceId: string;
  workspaceTitle?: string;
  /** Workspace viewers: show history but do not send or edit. */
  readOnly?: boolean;
};

/**
 * Workspace assistant: one **shared** server conversation per workspace (all members see the same thread),
 * same completion API + `agent_workspace_context` as the full Chat page.
 */
export function WorkspaceEmbeddedChat({ workspaceId, workspaceTitle, readOnly = false }: Props) {
  const auth = useAuth();
  const { accessToken } = auth;
  const [open, setOpen] = useState(true);
  const [models, setModels] = useState<string[]>([]);
  const [thread, setThread] = useState<ChatThread | null>(null);
  const [initErr, setInitErr] = useState<string | null>(null);
  const [initLoading, setInitLoading] = useState(true);
  const [draft, setDraft] = useState("");
  const [sendLoading, setSendLoading] = useState(false);
  const [sendErr, setSendErr] = useState<string | null>(null);
  const [noSharedChatYet, setNoSharedChatYet] = useState(false);
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const payloadBase = useMemo(
    () => ({
      agent_workspace_context: { workspace_id: workspaceId },
    }),
    [workspaceId]
  );

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
    if (!accessToken || !workspaceId) {
      setInitLoading(false);
      return;
    }
    let cancelled = false;
    setInitLoading(true);
    setInitErr(null);
    setThread(null);
    setNoSharedChatYet(false);
    void (async () => {
      try {
        const list = await fetchConversationList(auth, { workspaceId });
        if (cancelled) return;
        if (list.length > 0) {
          const shared = list.find((x) => (x as { shared?: boolean }).shared === true);
          const row = (shared ?? list[0]) as { id?: string };
          const id = String(row.id ?? "");
          if (!id) throw new Error("missing conversation id");
          const full = await fetchConversationDetail(auth, id);
          if (cancelled) return;
          setThread(full);
          return;
        }
        if (readOnly) {
          if (!cancelled) setNoSharedChatYet(true);
          return;
        }
        const r = await fetch("/v1/models");
        let first = "";
        if (r.ok) {
          const d = (await r.json()) as { data?: Array<{ id?: string }> };
          first = (d.data ?? []).map((x) => x.id).filter(Boolean)[0] ?? "";
        }
        const title = workspaceTitle?.trim()
          ? `Assistant · ${workspaceTitle.trim()}`
          : "Workspace assistant";
        const created = await createConversation(auth, {
          title,
          mode: "chat",
          model: first,
          messages: [],
          agent_log: [],
          workspace_id: workspaceId,
          shared: true,
        });
        if (cancelled) return;
        setThread(created);
      } catch (e) {
        if (!cancelled) {
          setInitErr(e instanceof Error ? e.message : String(e));
        }
      } finally {
        if (!cancelled) setInitLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, auth, readOnly, workspaceId, workspaceTitle]);

  const messages: Msg[] = useMemo(() => {
    if (!thread) return [];
    return thread.messages.map((m) => ({
      role: m.role === "assistant" ? "assistant" : "user",
      content:
        m.role === "user"
          ? formatUserBubbleForList(String(m.content ?? ""))
          : String(m.content ?? ""),
    }));
  }, [thread]);

  const addPickedFiles = useCallback(async (files: FileList | null) => {
    if (!files?.length || readOnly) return;
    const next = await filesToAttachments(files);
    setPendingAttachments((prev) => [...prev, ...next]);
  }, [readOnly]);

  useEffect(() => {
    if (open && endRef.current) {
      endRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, open, sendLoading]);

  const modelValue = thread?.model?.trim() || models[0] || "";

  const setModelOnThread = useCallback(
    (m: string) => {
      setThread((t) => (t ? { ...t, model: m, updatedAt: Date.now() } : t));
    },
    []
  );

  const send = useCallback(async () => {
    if (readOnly) return;
    const userContent = buildUserMessageContent(draft, pendingAttachments);
    if (!userContent || !accessToken || !thread || sendLoading) return;
    const mdl = modelValue.trim();
    if (!mdl) {
      setSendErr("No model available.");
      return;
    }
    setSendErr(null);
    const prev = thread;
    const prior = prev.messages.map((m) => ({ role: m.role, content: m.content }));
    const nextMessages = [...prior, { role: "user" as const, content: userContent }];
    const nextThread: ChatThread = {
      ...prev,
      model: mdl,
      messages: nextMessages,
      updatedAt: Date.now(),
    };
    setThread(nextThread);
    const draftSnap = draft;
    const attachSnap = pendingAttachments;
    setDraft("");
    setPendingAttachments([]);
    setSendLoading(true);
    try {
      await putConversation(auth, nextThread);
    } catch (e) {
      setSendErr(e instanceof Error ? e.message : String(e));
      setThread(prev);
      setDraft(draftSnap);
      setPendingAttachments(attachSnap);
      setSendLoading(false);
      return;
    }
    try {
      const disabledTools = getDisabledToolNames();
      const res = await apiFetch("/v1/chat/completions", auth, {
        method: "POST",
        body: JSON.stringify({
          model: mdl,
          messages: nextMessages.map((x) => ({
            role: x.role,
            content: toApiContent(x.content),
          })),
          stream: false,
          ...payloadBase,
          ...(disabledTools.length ? { agent_disabled_tools: disabledTools } : {}),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setSendErr(String((data as { detail?: unknown }).detail ?? res.statusText));
        setThread(nextThread);
        setDraft(draftSnap);
        setPendingAttachments(attachSnap);
        setSendLoading(false);
        return;
      }
      const content = assistantFromCompletion(data) || "(empty)";
      const withAssistant: ChatThread = {
        ...nextThread,
        messages: [...nextMessages, { role: "assistant", content }],
        updatedAt: Date.now(),
      };
      setThread(withAssistant);
      await putConversation(auth, withAssistant);
    } catch (e) {
      setSendErr(e instanceof Error ? e.message : String(e));
      setThread(nextThread);
      setDraft(draftSnap);
      setPendingAttachments(attachSnap);
    } finally {
      setSendLoading(false);
    }
  }, [
    accessToken,
    auth,
    draft,
    modelValue,
    pendingAttachments,
    payloadBase,
    readOnly,
    sendLoading,
    thread,
  ]);

  const hasComposerPayload =
    draft.trim().length > 0 ||
    pendingAttachments.some((a) => a.kind === "image" || a.kind === "textfile");

  const canSend =
    !readOnly &&
    hasComposerPayload &&
    !sendLoading &&
    !!accessToken &&
    !!thread &&
    !initLoading;

  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl border border-surface-border bg-surface-raised/40">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full shrink-0 items-center justify-between gap-2 px-3 py-2.5 text-left text-sm font-medium text-white hover:bg-white/5 lg:py-2"
      >
        <span>
          Assistant
          <span className="ml-1 font-normal text-surface-muted">
            {workspaceTitle ? `· ${workspaceTitle}` : ""}
          </span>
        </span>
        <span className="text-surface-muted">{open ? "▼" : "▶"}</span>
      </button>
      {open ? (
        <div className="flex min-h-0 flex-1 flex-col border-t border-surface-border">
          <p className="shrink-0 px-3 pt-2 text-[11px] leading-snug text-surface-muted">
            {readOnly
              ? "Shared workspace chat (read-only for your role). Same history for all members."
              : "Shared workspace chat — same thread for everyone with access. Text + images (same pipeline as main Chat: attachments as data URLs in the API). Reload-safe."}
          </p>
          {initLoading ? (
            <div className="px-3 py-4 text-sm text-surface-muted">Loading chat…</div>
          ) : noSharedChatYet && !thread ? (
            <div className="px-3 py-4 text-xs leading-snug text-surface-muted">
              No shared workspace chat yet. Ask someone with edit access to open this panel once to create
              it — then everyone will see the same thread here.
            </div>
          ) : initErr ? (
            <div className="mx-3 mb-2 rounded border border-red-500/40 bg-red-950/30 px-2 py-2 text-xs text-red-200">
              {initErr}
            </div>
          ) : (
            <>
              <div className="shrink-0 px-3 pt-2">
                <label className="mb-0.5 block text-[10px] text-surface-muted">Model</label>
                <select
                  className="w-full rounded-lg border border-surface-border bg-black/30 px-2 py-1.5 text-xs text-white"
                  value={modelValue}
                  onChange={(e) => {
                    const v = e.target.value;
                    setModelOnThread(v);
                    if (thread && !readOnly) {
                      void putConversation(auth, { ...thread, model: v }).catch(() => {});
                    }
                  }}
                  disabled={readOnly || !models.length || !thread}
                >
                  {!models.length ? (
                    <option>Loading…</option>
                  ) : (
                    models.map((id) => (
                      <option key={id} value={id}>
                        {id}
                      </option>
                    ))
                  )}
                </select>
              </div>
              {sendErr ? (
                <div className="mx-3 mt-2 rounded border border-red-500/40 bg-red-950/30 px-2 py-1.5 text-xs text-red-200">
                  {sendErr}
                </div>
              ) : null}
              <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
                <div className="max-h-[min(320px,40vh)] overflow-y-auto rounded-lg border border-white/10 bg-black/20 px-2 py-2 text-sm lg:max-h-[min(480px,calc(100vh-280px))]">
                  {messages.length === 0 ? (
                    <p className="text-xs text-surface-muted">
                      Ask questions or attach images (+) — same multimodal messages as the main Chat page.
                    </p>
                  ) : (
                    <ul className="flex flex-col gap-2">
                      {messages.map((m, i) => (
                        <li
                          key={`${thread?.id ?? "t"}-${i}-${m.role}`}
                          className={`rounded-md px-2 py-1.5 text-xs ${
                            m.role === "user"
                              ? "border border-sky-900/40 bg-sky-950/20 text-neutral-100"
                              : "border border-white/10 bg-[#1a1a1a] text-neutral-200"
                          }`}
                        >
                          <span className="mb-0.5 block text-[9px] font-medium uppercase text-surface-muted">
                            {m.role === "user" ? "You" : "Assistant"}
                          </span>
                          <div className="whitespace-pre-wrap">{m.content}</div>
                        </li>
                      ))}
                      {sendLoading ? (
                        <li className="text-xs text-sky-300/80">…</li>
                      ) : null}
                      <div ref={endRef} />
                    </ul>
                  )}
                </div>
              </div>
              <div className="shrink-0 border-t border-surface-border p-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  accept="image/*,.txt,.md,.json,.csv,.log,.yaml,.yml"
                  onChange={(e) => {
                    const files = e.target.files;
                    e.target.value = "";
                    void addPickedFiles(files);
                  }}
                />
                {pendingAttachments.length > 0 ? (
                  <ul className="mb-2 flex flex-wrap gap-1.5">
                    {pendingAttachments.map((a, idx) => (
                      <li
                        key={`${a.name}-${idx}`}
                        className="flex max-w-full items-center gap-1 rounded border border-white/10 bg-black/30 px-2 py-0.5 text-[10px] text-neutral-300"
                      >
                        <span className="truncate" title={a.kind === "unsupported" ? a.hint : a.name}>
                          {a.name}
                          {a.kind === "unsupported" ? " (skip)" : ""}
                        </span>
                        <button
                          type="button"
                          className="text-surface-muted hover:text-white"
                          aria-label="Remove"
                          onClick={() => setPendingAttachments((p) => p.filter((_, i) => i !== idx))}
                        >
                          ×
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={readOnly || sendLoading || !thread}
                    className="shrink-0 rounded-lg border border-white/10 bg-black/30 px-2.5 py-2 text-surface-muted hover:bg-white/5 hover:text-white disabled:opacity-40"
                    title="Bild oder Textdatei anhängen"
                    aria-label="Attach"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    +
                  </button>
                  <input
                    type="text"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        void send();
                      }
                    }}
                    placeholder="Message…"
                    className="min-w-0 flex-1 rounded-lg border border-surface-border bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-sky-500/50"
                    disabled={readOnly || sendLoading || !thread}
                  />
                  <button
                    type="button"
                    disabled={!canSend}
                    onClick={() => void send()}
                    className="shrink-0 rounded-lg bg-sky-600 px-3 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
                  >
                    Send
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
