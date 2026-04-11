/** Per-browser tool opt-out for chat/agent requests (server: ``agent_disabled_tools``). */

const STORAGE_KEY = "agentlayer.chat.disabled_tools";

export function getDisabledToolNames(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const p = JSON.parse(raw) as unknown;
    if (!Array.isArray(p)) return [];
    const names: string[] = [];
    for (const x of p) {
      if (typeof x === "string" && x.trim()) names.push(x.trim());
    }
    return [...new Set(names)];
  } catch {
    return [];
  }
}

export function setDisabledToolNames(names: string[]): void {
  const uniq = [...new Set(names.map((s) => s.trim()).filter(Boolean))];
  localStorage.setItem(STORAGE_KEY, JSON.stringify(uniq));
}

/** True if every listed tool name is allowed (not in disabled set). */
export function isPackageEnabledForChat(toolNames: string[]): boolean {
  if (!toolNames.length) return true;
  const dis = new Set(getDisabledToolNames());
  return toolNames.every((n) => !dis.has(n));
}

export function setPackageEnabledForChat(toolNames: string[], enabled: boolean): void {
  const dis = new Set(getDisabledToolNames());
  for (const n of toolNames) {
    const t = n.trim();
    if (!t) continue;
    if (enabled) dis.delete(t);
    else dis.add(t);
  }
  setDisabledToolNames([...dis]);
}
