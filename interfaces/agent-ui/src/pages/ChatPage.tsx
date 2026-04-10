import { useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";

const SUGGESTED = [
  "Show me a code snippet of a website's sticky header",
  "Explain options trading if I'm familiar with buying and selling stocks",
  "Help me study vocabulary for a college entrance exam",
];

/**
 * P2: wire WebSocket /ws/v1/chat, model list GET /v1/models, headers for agent profile.
 * Layout mirrors Open WebUI-style shell (dark, sidebar + main).
 */
export function ChatPage() {
  const { user } = useAuth();
  const [draft, setDraft] = useState("");
  const displayName = useMemo(() => {
    const e = user?.email;
    if (!e) return "there";
    return e.split("@")[0] ?? "there";
  }, [user?.email]);

  return (
    <div className="flex min-h-[calc(100vh-52px)] bg-surface">
      {/* Chat sidebar — history / nav (P2: real threads) */}
      <aside className="flex w-[260px] shrink-0 flex-col border-r border-surface-border bg-[#111]">
        <div className="border-b border-surface-border p-3">
          <button
            type="button"
            className="w-full rounded-lg border border-surface-border bg-white/5 px-3 py-2 text-left text-sm text-neutral-200 hover:bg-white/10"
          >
            + New chat
          </button>
        </div>
        <nav className="flex flex-col gap-0.5 p-2 text-sm">
          <span className="px-2 py-1 text-xs font-medium uppercase tracking-wide text-surface-muted">
            Navigate
          </span>
          {["Workspace", "Agent", "Search"].map((item) => (
            <button
              key={item}
              type="button"
              className="rounded-md px-2 py-2 text-left text-neutral-300 hover:bg-white/5"
            >
              {item}
            </button>
          ))}
        </nav>
        <div className="mt-4 flex-1 overflow-y-auto px-2">
          <p className="px-2 text-xs font-medium uppercase tracking-wide text-surface-muted">Chats</p>
          <p className="px-2 py-1 text-xs text-surface-muted">Today</p>
          <div className="rounded-md bg-white/5 px-2 py-2 text-sm text-neutral-200">New chat</div>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-start justify-between gap-4 border-b border-surface-border px-6 py-4">
          <div>
            <label className="block text-xs text-surface-muted">Model</label>
            <select className="mt-1 rounded-lg border border-surface-border bg-[#1a1a1a] px-3 py-2 text-sm text-neutral-100">
              <option>Select a model</option>
              <option disabled>— load GET /v1/models in P2 —</option>
            </select>
            <p className="mt-1 text-xs text-surface-muted">Set as default (coming in settings)</p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="flex h-9 w-9 items-center justify-center rounded-full bg-orange-500/90 text-sm font-medium text-black"
              title="Profile"
            >
              {(displayName[0] ?? "?").toUpperCase()}
            </span>
          </div>
        </div>

        <div className="flex flex-1 flex-col items-center justify-center px-6 pb-32 pt-12">
          <div className="mb-10 flex flex-col items-center gap-3 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full border border-surface-border bg-white/5 text-lg font-semibold text-neutral-300">
              AL
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-white">
              Hello, {displayName}
            </h1>
            <p className="max-w-md text-sm text-surface-muted">
              P2 connects this screen to <code className="text-neutral-400">/ws/v1/chat</code> with
              model selection and agent profiles per contract.
            </p>
          </div>

          <div className="relative w-full max-w-3xl">
            <div className="rounded-2xl border border-surface-border bg-[#141414] p-3 shadow-xl">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="rounded-md border border-dashed border-surface-border px-2 py-1 text-xs text-surface-muted"
                >
                  +
                </button>
                <span className="rounded-full bg-white/5 px-2 py-1 text-xs text-neutral-400">
                  Code Interpreter
                </span>
              </div>
              <textarea
                className="min-h-[52px] w-full resize-none bg-transparent text-sm text-neutral-100 placeholder:text-neutral-500 focus:outline-none"
                placeholder="How can I help you today?"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={2}
              />
              <div className="mt-2 flex justify-end gap-2 text-surface-muted">
                <span className="text-xs">⌨</span>
                <span className="text-xs">🎧</span>
              </div>
            </div>

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
          </div>
        </div>
      </main>
    </div>
  );
}
