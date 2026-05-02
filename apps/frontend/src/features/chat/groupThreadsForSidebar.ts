import type { ChatThread } from "./chatThreadStorage";

export type SidebarThreadGroup =
  | { kind: "source"; source: string; label: string; threads: ChatThread[] }
  | { kind: "dashboard"; dashboardId: string; label: string; threads: ChatThread[] };

const byUpdated = (a: ChatThread, b: ChatThread) => b.updatedAt - a.updatedAt;

/** Sidebar heading for a bridge ``source`` id (telegram, slack, …). */
export function labelForChatSource(source: string): string {
  const s = source.trim().toLowerCase();
  if (!s || s === "web") return "Web";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/**
 * Groups first-party vs bridge vs dashboard threads for the chat sidebar.
 * Bridge sections are keyed by ``thread.source`` (any provider string from the API).
 */
export function buildSidebarGroups(
  threads: ChatThread[],
  dashboardTitles: Record<string, string>
): SidebarThreadGroup[] {
  const bySource = new Map<string, ChatThread[]>();
  const byWs = new Map<string, ChatThread[]>();

  for (const t of threads) {
    if (t.dashboardId) {
      const list = byWs.get(t.dashboardId) ?? [];
      list.push(t);
      byWs.set(t.dashboardId, list);
      continue;
    }
    const src = (t.source ?? "web").trim().toLowerCase() || "web";
    const list = bySource.get(src) ?? [];
    list.push(t);
    bySource.set(src, list);
  }

  const out: SidebarThreadGroup[] = [];

  const sourceKeys = [...bySource.keys()].sort((a, b) => {
    if (a === "web") return -1;
    if (b === "web") return 1;
    return a.localeCompare(b);
  });
  for (const source of sourceKeys) {
    const th = bySource.get(source);
    if (!th?.length) continue;
    th.sort(byUpdated);
    out.push({
      kind: "source",
      source,
      label: labelForChatSource(source),
      threads: th,
    });
  }

  const wsEntries = [...byWs.entries()].map(([wid, th]) => {
    th.sort(byUpdated);
    const titled = dashboardTitles[wid]?.trim();
    return {
      kind: "dashboard" as const,
      dashboardId: wid,
      label: titled || `Dashboard ${wid.slice(0, 8)}…`,
      threads: th,
    };
  });
  wsEntries.sort((a, b) => a.label.localeCompare(b.label));
  out.push(...wsEntries);

  return out;
}
