import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiFetch } from "../lib/api";
import { useIdeAgentAvailable } from "../hooks/useIdeAgentAvailable";

type ChatLine = { role: "user" | "assistant"; text: string };

type IdeAgentMessageResponse = {
  ok?: boolean;
  timed_out?: boolean;
  last_ai?: string;
  user_messages?: string[];
  ai_messages?: string[];
  selector_ide?: string;
  selector_version?: string;
};

/** Pair user[i] with ai[i], then append any extra user or assistant lines (DOM order). */
function linesFromSnapshot(user: string[], ai: string[]): ChatLine[] {
  const out: ChatLine[] = [];
  const n = Math.min(user.length, ai.length);
  for (let i = 0; i < n; i++) {
    out.push({ role: "user", text: user[i] });
    out.push({ role: "assistant", text: ai[i] });
  }
  for (let i = n; i < user.length; i++) out.push({ role: "user", text: user[i] });
  for (let i = n; i < ai.length; i++) out.push({ role: "assistant", text: ai[i] });
  return out;
}

function parseErrorDetail(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d
        .map((x) => (typeof x === "object" && x && "msg" in x ? String((x as { msg?: string }).msg) : String(x)))
        .filter(Boolean)
        .join("; ");
    }
  }
  return "Request failed";
}

/** First line after ``` only if it matches a common fence info string (avoids treating code as “lang”). */
const FENCE_LANG_WHITELIST = new Set(
  [
    "text",
    "txt",
    "plain",
    "plaintext",
    "bash",
    "sh",
    "shell",
    "zsh",
    "fish",
    "pwsh",
    "powershell",
    "js",
    "javascript",
    "mjs",
    "cjs",
    "ts",
    "typescript",
    "tsx",
    "jsx",
    "json",
    "jsonc",
    "yaml",
    "yml",
    "html",
    "xml",
    "svg",
    "vue",
    "svelte",
    "css",
    "scss",
    "sass",
    "less",
    "md",
    "markdown",
    "py",
    "python",
    "rb",
    "ruby",
    "rs",
    "rust",
    "go",
    "golang",
    "java",
    "kt",
    "kotlin",
    "swift",
    "c",
    "h",
    "cpp",
    "cxx",
    "cc",
    "hpp",
    "cs",
    "csharp",
    "php",
    "sql",
    "graphql",
    "toml",
    "ini",
    "cfg",
    "dockerfile",
    "makefile",
    "diff",
    "patch",
    "http",
    "nginx",
  ].map((s) => s.toLowerCase()),
);

type FenceSegment = { kind: "text"; body: string } | { kind: "code"; lang?: string; body: string };

function parseFenceChunk(chunk: string): { lang?: string; body: string } {
  let s = chunk.replace(/\n$/, "");
  if (s.startsWith("\n")) s = s.slice(1);
  const nl = s.indexOf("\n");
  const firstLine = nl === -1 ? s : s.slice(0, nl);
  const rest = nl === -1 ? "" : s.slice(nl + 1);
  const cand = firstLine.trim().toLowerCase();
  if (cand && FENCE_LANG_WHITELIST.has(cand)) {
    return { lang: firstLine.trim(), body: rest };
  }
  return { body: s };
}

function splitTripleBacktickFences(raw: string): FenceSegment[] {
  const parts = raw.split("```");
  const out: FenceSegment[] = [];
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 0) {
      if (parts[i]) out.push({ kind: "text", body: parts[i] });
    } else {
      const { lang, body } = parseFenceChunk(parts[i]);
      out.push({ kind: "code", lang, body });
    }
  }
  return out;
}

function MessageBody({ text }: { text: string }) {
  const segments = splitTripleBacktickFences(text);
  if (segments.length === 0) {
    return null;
  }
  const singleText = segments.length === 1 && segments[0].kind === "text";
  if (singleText) {
    return (
      <div className="whitespace-pre-wrap break-words text-[15px] leading-relaxed text-neutral-100/95">{segments[0].body}</div>
    );
  }
  return (
    <div className="max-w-none space-y-3 text-[15px] leading-relaxed text-neutral-100/95">
      {segments.map((seg, i) =>
        seg.kind === "text" ? (
          <div key={i} className="max-w-prose whitespace-pre-wrap break-words">
            {seg.body}
          </div>
        ) : (
          <div
            key={i}
            className="overflow-hidden rounded-xl border border-white/10 bg-black/45 shadow-inner ring-1 ring-white/5"
          >
            {seg.lang ? (
              <div className="border-b border-white/10 px-3 py-1.5 font-mono text-[10px] font-medium uppercase tracking-wide text-surface-muted">
                {seg.lang}
              </div>
            ) : null}
            <pre className="max-h-[min(70vh,28rem)] overflow-auto whitespace-pre p-3 font-mono text-[13px] leading-relaxed text-neutral-200/95 [tab-size:2]">
              {seg.body}
            </pre>
          </div>
        ),
      )}
    </div>
  );
}

/**
 * IDE Agent: messages go to the IDE’s AI (e.g. Cursor Composer) via server-side Playwright + CDP,
 * not to ``/v1/chat/completions``.
 */
export function IdeAgentPage() {
  const auth = useAuth();
  const { loading, enabled, playwrightInstalled } = useIdeAgentAvailable();
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newChatNext, setNewChatNext] = useState(false);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const draftRef = useRef<HTMLTextAreaElement>(null);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
    };
  }, []);

  const scrollToBottom = useCallback(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [lines, sending, scrollToBottom]);

  const loadSnapshot = useCallback(async () => {
    if (!auth.accessToken) return;
    setSnapshotLoading(true);
    setSnapshotError(null);
    try {
      const r = await apiFetch("/v1/ide-agent/snapshot", auth);
      const data = (await r.json().catch(() => ({}))) as {
        user_messages?: string[];
        ai_messages?: string[];
        detail?: unknown;
      };
      if (!aliveRef.current) return;
      if (!r.ok) {
        setSnapshotError(parseErrorDetail(data));
        return;
      }
      const u = Array.isArray(data.user_messages) ? data.user_messages : [];
      const a = Array.isArray(data.ai_messages) ? data.ai_messages : [];
      setLines(linesFromSnapshot(u, a));
    } catch (e) {
      if (!aliveRef.current) return;
      setSnapshotError(e instanceof Error ? e.message : String(e));
    } finally {
      if (aliveRef.current) setSnapshotLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    if (loading || !enabled || !auth.accessToken) return;
    if (playwrightInstalled === false) {
      setSnapshotLoading(false);
      setSnapshotError(null);
      return;
    }
    void loadSnapshot();
  }, [loading, enabled, auth.accessToken, playwrightInstalled, loadSnapshot]);

  async function copyMessage(text: string, key: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      window.setTimeout(() => setCopiedKey((k) => (k === key ? null : k)), 2000);
    } catch {
      setCopiedKey(null);
    }
  }

  if (!loading && !enabled) {
    return <Navigate to="/" replace />;
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center px-4">
        <p className="text-sm text-surface-muted">Loading…</p>
      </div>
    );
  }

  const canSend = Boolean(!sending && draft.trim().length > 0 && auth.accessToken);

  async function onSend() {
    const text = draft.trim();
    if (!text || sending || !auth.accessToken) return;
    setError(null);
    setDraft("");
    setLines((prev) => [...prev, { role: "user", text }]);
    setSending(true);
    try {
      const r = await apiFetch("/v1/ide-agent/message", auth, {
        method: "POST",
        body: JSON.stringify({
          message: text,
          new_chat: newChatNext,
          reply_timeout_seconds: 120,
        }),
      });
      const data = (await r.json().catch(() => ({}))) as IdeAgentMessageResponse & { detail?: string };
      if (!r.ok) {
        setError(parseErrorDetail(data));
        return;
      }
      const u = Array.isArray(data.user_messages) ? data.user_messages : [];
      const a = Array.isArray(data.ai_messages) ? data.ai_messages : [];
      if (u.length > 0 || a.length > 0) {
        const merged = linesFromSnapshot(u, a);
        if (data.timed_out === true && merged.length > 0) {
          const last = merged[merged.length - 1];
          if (last.role === "assistant") {
            merged[merged.length - 1] = {
              ...last,
              text: `${last.text}\n\n— Timeout: DOM may still be updating; try again or increase timeout on the server.`,
            };
          }
        }
        setLines(merged);
      } else {
        const reply =
          (typeof data.last_ai === "string" && data.last_ai.trim()) ||
          (Array.isArray(data.ai_messages) && data.ai_messages.length ? data.ai_messages[data.ai_messages.length - 1] : "") ||
          "(No assistant text read from the IDE.)";
        const assistantText =
          data.timed_out === true ? `${reply}\n\n— Timeout: DOM may still be updating; try again or increase timeout on the server.` : reply;
        setLines((prev) => [...prev, { role: "assistant", text: assistantText }]);
      }
      if (newChatNext) setNewChatNext(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
      draftRef.current?.focus();
    }
  }

  return (
    <div className="mx-auto flex h-full min-h-0 w-full max-w-3xl flex-1 flex-col overflow-hidden px-4 py-6">
      <header className="shrink-0">
        <h1 className="text-lg font-semibold text-white">IDE Agent</h1>
        <p className="mt-1 text-sm text-surface-muted">
          Messages are sent through the server to your IDE&apos;s AI panel (Playwright + CDP), not{" "}
          <span className="text-neutral-400">Chat</span> / Ollama. Configure CDP and selectors under{" "}
          <Link to="/admin/ide-agent" className="text-sky-400 hover:text-sky-300 hover:underline">
            Admin → IDE Agent
          </Link>
          .
        </p>
      </header>

      {playwrightInstalled === false ? (
        <div className="mt-4 shrink-0 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-100/90">
          Playwright is not available in the API process yet — use{" "}
          <Link to="/admin/ide-agent" className="text-sky-400 hover:underline">
            Admin → IDE Agent
          </Link>{" "}
          to install, then reload this page.
        </div>
      ) : null}

      {error ? (
        <div className="mt-4 shrink-0 whitespace-pre-wrap rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-100/95">
          {error}
        </div>
      ) : null}

      <section
        className="mt-4 flex min-h-[min(50vh,22rem)] flex-1 basis-0 flex-col overflow-hidden rounded-xl border border-surface-border bg-surface-raised/50 shadow-inner"
        aria-label="IDE Agent conversation"
      >
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-white/10 px-4 py-2.5">
          <div className="text-xs font-medium tracking-wide text-surface-muted">
            Conversation
            {lines.length > 0 ? (
              <span className="ml-2 font-normal text-surface-muted/80">
                · {lines.length} {lines.length === 1 ? "message" : "messages"}
              </span>
            ) : null}
          </div>
          {playwrightInstalled !== false ? (
            <button
              type="button"
              disabled={snapshotLoading || sending}
              onClick={() => void loadSnapshot()}
              className="rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[11px] font-medium text-sky-200/90 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {snapshotLoading ? "Refreshing…" : "Refresh from IDE"}
            </button>
          ) : null}
        </div>
        <div
          ref={scrollRef}
          className="min-h-0 flex-1 space-y-4 overflow-y-auto scroll-smooth bg-black/15 px-3 py-4 sm:px-5"
        >
          {snapshotLoading ? (
            <p className="text-sm text-surface-muted">Loading conversation from the IDE…</p>
          ) : null}
          {snapshotError ? (
            <div className="rounded-lg border border-amber-500/30 bg-amber-950/40 px-3 py-2 text-sm text-amber-100/90">
              <p className="whitespace-pre-wrap">{snapshotError}</p>
              <button
                type="button"
                className="mt-2 text-xs font-medium text-sky-300 hover:text-sky-200 hover:underline"
                onClick={() => void loadSnapshot()}
              >
                Try again
              </button>
            </div>
          ) : null}
          {!snapshotLoading && lines.length === 0 ? (
            <p className="text-sm text-surface-muted">
              Open the IDE composer on the machine reachable via CDP (see Admin → IDE Agent), then send a message below. Existing
              turns load here automatically.
            </p>
          ) : null}
          {lines.length > 0 ? (
            lines.map((line, i) => {
              const copyKey = `${line.role}-${i}`;
              return (
                <article
                  key={copyKey}
                  className={
                    line.role === "user"
                      ? "group ml-auto max-w-[min(100%,42rem)] rounded-2xl border border-white/12 bg-gradient-to-br from-white/[0.07] to-white/[0.02] px-4 py-3 text-neutral-100 shadow-md ring-1 ring-white/5 sm:ml-12"
                      : "group mr-auto max-w-[min(100%,46rem)] rounded-2xl border border-sky-500/25 bg-gradient-to-br from-sky-950/50 to-slate-950/40 px-4 py-3 text-neutral-100 shadow-md ring-1 ring-sky-500/10 sm:mr-12"
                  }
                >
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span
                      className={
                        line.role === "user"
                          ? "rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-neutral-300"
                          : "rounded-full bg-sky-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-sky-200/90"
                      }
                    >
                      {line.role === "user" ? "You" : "IDE AI"}
                    </span>
                    <button
                      type="button"
                      onClick={() => void copyMessage(line.text, copyKey)}
                      className="shrink-0 rounded-md px-2 py-0.5 text-[11px] font-medium text-surface-muted opacity-80 transition-opacity hover:bg-white/10 hover:text-neutral-200 sm:opacity-0 sm:group-hover:opacity-100"
                      title="Copy message"
                    >
                      {copiedKey === copyKey ? "Copied" : "Copy"}
                    </button>
                  </div>
                  <MessageBody text={line.text} />
                </article>
              );
            })
          ) : null}
          {sending ? (
            <div className="mr-auto max-w-md rounded-2xl border border-white/10 bg-black/25 px-4 py-3 text-sm text-surface-muted ring-1 ring-white/5">
              <span className="inline-block animate-pulse">Waiting for the IDE…</span>
            </div>
          ) : null}
        </div>
      </section>

      <div className="mt-4 shrink-0 space-y-3">
        <label className="flex cursor-pointer items-center gap-2 text-xs text-surface-muted">
          <input
            type="checkbox"
            checked={newChatNext}
            onChange={(e) => setNewChatNext(e.target.checked)}
            className="rounded border-white/20 bg-black/30"
          />
          New chat (clicks &quot;new chat&quot; in the panel before sending)
        </label>
        <div className="flex gap-2">
          <textarea
            ref={draftRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (canSend) void onSend();
              }
            }}
            placeholder="Message to the IDE composer… (Enter to send, Shift+Enter for newline)"
            disabled={sending}
            rows={3}
            className="min-h-[4.5rem] flex-1 resize-y rounded-lg border border-surface-border bg-black/30 px-3 py-2 text-sm text-neutral-100 placeholder:text-neutral-500 focus:border-sky-500/50 focus:outline-none disabled:opacity-50"
          />
          <button
            type="button"
            disabled={!canSend}
            onClick={() => void onSend()}
            className="self-end rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
