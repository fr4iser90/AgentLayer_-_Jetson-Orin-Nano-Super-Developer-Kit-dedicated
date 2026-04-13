import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";
import { getDisabledToolNames } from "../settings/toolPrefs";
import { toApiContent } from "../chat/messageFormat";

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

type Props = {
  workspaceId: string;
  /** Shown in the header when provided */
  workspaceTitle?: string;
};

/**
 * In-workspace assistant: same `/v1/chat/completions` pipeline as Chat page, with
 * `agent_workspace_context` set so the model knows which workspace is active.
 */
export function WorkspaceEmbeddedChat({ workspaceId, workspaceTitle }: Props) {
  const auth = useAuth();
  const { accessToken } = auth;
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

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
        setModel((m) => m || ids[0] || "");
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const payloadBase = useMemo(
    () => ({
      agent_workspace_context: { workspace_id: workspaceId },
    }),
    [workspaceId]
  );

  useEffect(() => {
    if (open && endRef.current) {
      endRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, open, loading]);

  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text || !accessToken || loading) return;
    const mdl = model.trim() || models[0] || "";
    if (!mdl) {
      setErr("No model available.");
      return;
    }
    setErr(null);
    const nextMessages: Msg[] = [...messages, { role: "user", content: text }];
    setMessages(nextMessages);
    setDraft("");
    setLoading(true);
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
        setErr(String((data as { detail?: unknown }).detail ?? res.statusText));
        setMessages((prev) => prev.slice(0, -1));
        return;
      }
      const content = assistantFromCompletion(data) || "(empty)";
      setMessages((prev) => [...prev, { role: "assistant", content }]);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  }, [accessToken, auth, draft, loading, messages, model, models, payloadBase]);

  const canSend = draft.trim().length > 0 && !loading && !!accessToken;

  return (
    <div className="mt-6 rounded-xl border border-surface-border bg-surface-raised/40">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-medium text-white hover:bg-white/5"
      >
        <span>
          Assistant{" "}
          <span className="font-normal text-surface-muted">
            (this workspace{workspaceTitle ? `: ${workspaceTitle}` : ""})
          </span>
        </span>
        <span className="text-surface-muted">{open ? "▼" : "▶"}</span>
      </button>
      {open ? (
        <div className="border-t border-surface-border px-4 pb-4">
          <p className="mt-2 text-xs text-surface-muted">
            Messages stay in this browser session only (not synced to Chat history). The agent receives this
            workspace as context for tools (e.g. shopping list).
          </p>
          <div className="mt-2 flex flex-wrap items-end gap-2">
            <div className="min-w-[160px] flex-1">
              <label className="mb-0.5 block text-[10px] text-surface-muted">Model</label>
              <select
                className="w-full rounded-lg border border-surface-border bg-black/30 px-2 py-1.5 text-xs text-white"
                value={model || models[0] || ""}
                onChange={(e) => setModel(e.target.value)}
                disabled={!models.length}
              >
                {!models.length ? <option>Loading…</option> : models.map((id) => <option key={id} value={id}>{id}</option>)}
              </select>
            </div>
            <Link
              to={`/chat?workspace=${encodeURIComponent(workspaceId)}`}
              className="text-xs text-sky-300/90 underline hover:text-sky-200"
            >
              Open full Chat page
            </Link>
          </div>
          {err ? (
            <div className="mt-2 rounded border border-red-500/40 bg-red-950/30 px-2 py-1.5 text-xs text-red-200">
              {err}
            </div>
          ) : null}
          <div className="mt-3 max-h-64 overflow-y-auto rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm">
            {messages.length === 0 ? (
              <p className="text-xs text-surface-muted">e.g. &quot;Add milk&quot; or &quot;What&apos;s still on the list?&quot;</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {messages.map((m, i) => (
                  <li
                    key={`${i}-${m.role}`}
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
                {loading ? (
                  <li className="text-xs text-sky-300/80">…</li>
                ) : null}
                <div ref={endRef} />
              </ul>
            )}
          </div>
          <div className="mt-2 flex gap-2">
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
              disabled={loading}
            />
            <button
              type="button"
              disabled={!canSend}
              onClick={() => void send()}
              className="shrink-0 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
