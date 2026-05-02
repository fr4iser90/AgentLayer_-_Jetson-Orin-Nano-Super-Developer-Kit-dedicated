import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../../auth/AuthContext";
import { apiFetch } from "../../../lib/api";

const IDES = ["cursor", "vscode", "windsurf"] as const;

const IDE_LABEL: Record<(typeof IDES)[number], string> = {
  cursor: "Cursor",
  vscode: "VS Code",
  windsurf: "Windsurf",
};

type StatusPayload = {
  ide?: string;
  selector_version?: string;
  cdp_http_url?: string;
  connected?: boolean;
  inferred_semver?: string | null;
  cdp_json_version?: string | null;
  document_title?: string | null;
  active_page_url?: string | null;
  navigator_user_agent?: string | null;
  dashboard_hints?: unknown;
  last_refresh?: string;
  error?: string;
};

type ValidateRow = {
  key: string;
  selector: string;
  count: number;
  visible: number;
  clickable: number;
  sample: string | null;
  status: string;
  error?: string | null;
};

type ExploreItem = {
  tag: string;
  role?: string | null;
  ariaLabel?: string | null;
  placeholder?: string | null;
  dataAttrs?: Record<string, string>;
  textPreview?: string;
  suggestSelector?: string;
};

type RepairCandidate = {
  css: string;
  source: string;
  rank: number;
  matches: number;
};

type RepairData = {
  ide?: string;
  selector_version?: string;
  candidates?: Record<string, RepairCandidate[]>;
};

type SelfHealPayload = {
  ok?: boolean;
  ide?: string;
  base_version?: string;
  changed_keys?: string[];
  failed_keys?: { key: string; reason?: string }[];
  critical_keys_ok?: boolean;
  critical_failures?: string[];
  validation_before?: ValidateRow[];
  validation_after?: ValidateRow[];
  updated_selectors?: Record<string, string>;
  new_version?: string | null;
  path?: string | null;
  dry_run?: boolean;
  persisted?: boolean;
  message?: string;
};

const CHAT_KEY_LABELS: Record<string, string> = {
  aiMessages: "AI messages",
  userMessages: "Your messages",
  input: "Chat input",
};

function labelChatKey(key: string): string {
  return CHAT_KEY_LABELS[key] ?? key;
}

/** One sentence for banners; avoids “nothing happened” on dry-run. */
function selfHealSummaryLine(data: SelfHealPayload, didPersist: boolean): string {
  if (data.message === "nothing_to_heal") {
    return "Dry run: all selectors match this page — nothing to fix (no file changed).";
  }
  if (didPersist && data.new_version) {
    return `Profile saved as ${data.new_version}.`;
  }
  if (didPersist) {
    return "Profile saved.";
  }
  const n = data.changed_keys?.length ?? 0;
  const fails = data.failed_keys?.length ?? 0;
  if (data.dry_run && n > 0 && data.critical_keys_ok) {
    return `Dry run: ${n} selector${n === 1 ? "" : "s"} would be updated — click “Self-heal & persist” to save (no file written yet).`;
  }
  if (data.dry_run && fails > 0 && n === 0) {
    return "Dry run: could not auto-fix every broken selector — see details below.";
  }
  if (!data.critical_keys_ok) {
    return "Critical chat areas still need attention — see below.";
  }
  return "Self-heal finished.";
}

function selfHealNextStep(data: SelfHealPayload): string | null {
  if (data.message === "nothing_to_heal") {
    return "No action needed. Run again after an IDE update if selectors break.";
  }
  if (data.persisted) {
    return "Optional: open the Validator tab and run “Validate all” to confirm.";
  }
  if (data.dry_run && data.critical_keys_ok && (data.changed_keys?.length ?? 0) > 0) {
    return "To save, click “Self-heal & persist”. The server writes a new versioned file; older profiles are kept.";
  }
  if (!data.critical_keys_ok) {
    return "Open the chat panel in the IDE, focus this window, then retry — or use “Load candidates” below.";
  }
  return null;
}

function SelfHealSummaryCard({ data, developerMode }: { data: SelfHealPayload; developerMode?: boolean }) {
  const changed = data.changed_keys ?? [];
  const failed = data.failed_keys ?? [];
  const dry = data.dry_run === true;
  const nothing = data.message === "nothing_to_heal";
  const border =
    data.critical_keys_ok && (nothing || data.persisted || changed.length > 0)
      ? "border-emerald-500/35 bg-emerald-950/20"
      : "border-amber-500/40 bg-amber-950/25";

  return (
    <div className={`mt-4 rounded-xl border p-4 ${border}`}>
      <p className="text-sm font-semibold text-white">{selfHealSummaryLine(data, data.persisted === true)}</p>
      {dry ? (
        <p className="mt-2 text-xs text-neutral-400">
          <span className="font-medium text-neutral-300">Dry run</span> only simulates fixes against the live page. It does{" "}
          <span className="text-neutral-200">not</span> write or replace profile files — that is expected.
        </p>
      ) : null}
      {!nothing ? (
        <div className="mt-3 space-y-2 text-xs text-neutral-300">
          <p>
            <span className="text-surface-muted">Profile checked: </span>
            <span className="font-mono text-neutral-200">{data.base_version ?? "—"}</span>
          </p>
          <p>
            <span className="text-surface-muted">Chat essentials: </span>
            {data.critical_keys_ok ? (
              <span className="text-emerald-300/95">All OK (AI messages, your messages, input)</span>
            ) : (
              <span className="text-amber-200">
                Needs attention
                {data.critical_failures?.length
                  ? `: ${data.critical_failures.map(labelChatKey).join(", ")}`
                  : ""}
              </span>
            )}
          </p>
          {changed.length > 0 ? (
            <div>
              <span className="text-surface-muted">
                {dry ? "Would update" : "Updated"} ({changed.length}):{" "}
              </span>
              <span>{changed.map(labelChatKey).join(", ")}</span>
            </div>
          ) : null}
          {developerMode && data.updated_selectors && Object.keys(data.updated_selectors).length > 0 ? (
            <div className="mt-2 rounded-lg border border-white/10 bg-black/30 p-2">
              <p className="text-[10px] font-medium uppercase tracking-wide text-neutral-500">Chosen CSS (developer)</p>
              <ul className="mt-1 space-y-1.5 font-mono text-[10px] text-neutral-400">
                {Object.entries(data.updated_selectors).map(([k, css]) => (
                  <li key={k}>
                    <span className="text-neutral-500">{k}: </span>
                    <span className="break-all text-neutral-300">{css}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {failed.length > 0 ? (
            <div>
              <span className="text-surface-muted">Could not auto-fix: </span>
              <ul className="mt-1 list-inside list-disc text-amber-100/90">
                {failed.map((f) => (
                  <li key={f.key}>
                    {labelChatKey(f.key)}
                    {f.reason ? ` — ${f.reason}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {data.persisted && data.new_version ? (
            <p className="text-emerald-200/90">
              Saved as version <span className="font-mono">{data.new_version}</span>
              {data.path ? (
                <>
                  {" "}
                  <span className="text-surface-muted">({data.path})</span>
                </>
              ) : null}
            </p>
          ) : null}
        </div>
      ) : null}
      {selfHealNextStep(data) ? (
        <p className="mt-3 border-t border-white/10 pt-3 text-xs text-neutral-300">
          <span className="font-medium text-neutral-200">Next: </span>
          {selfHealNextStep(data)}
        </p>
      ) : null}
    </div>
  );
}

function basePath(ide: string) {
  return `/v1/admin/ide-agents/${encodeURIComponent(ide)}`;
}

function useVersionQuery(version: string) {
  const ref = useRef(version);
  ref.current = version;
  return useCallback(() => {
    const v = ref.current.trim();
    return v ? `?version=${encodeURIComponent(v)}` : "";
  }, []);
}

const DANGEROUS = new Set([
  "open_file",
  "open_folder",
  "send_chat",
  "accept_changes",
  "click_selector",
  "press_key",
]);

const DOM_ANALYZER_UX_MODE_KEY = "agentLayer.domAnalyzer.uxMode";

type DomAnalyzerUxMode = "operator" | "developer";

function readStoredUxMode(): DomAnalyzerUxMode {
  try {
    const v = localStorage.getItem(DOM_ANALYZER_UX_MODE_KEY);
    if (v === "developer" || v === "operator") return v;
  } catch {
    /* ignore */
  }
  return "operator";
}

export function DomAnalyzerPage() {
  const { ide: ideParam } = useParams<{ ide: string }>();
  const navigate = useNavigate();
  const auth = useAuth();
  const ide = (ideParam || "cursor").toLowerCase();
  const [version, setVersion] = useState("");
  const versionQs = useVersionQuery(version);
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [rows, setRows] = useState<ValidateRow[]>([]);
  const [repairData, setRepairData] = useState<RepairData | null>(null);
  const [repairRaw, setRepairRaw] = useState<string>("");
  const [selfHealRaw, setSelfHealRaw] = useState<string>("");
  const [lastSelfHeal, setLastSelfHeal] = useState<SelfHealPayload | null>(null);
  const [uxMode, setUxMode] = useState<DomAnalyzerUxMode>(() => readStoredUxMode());
  const [technicalDetailsOpen, setTechnicalDetailsOpen] = useState(() => readStoredUxMode() === "developer");

  useEffect(() => {
    setTechnicalDetailsOpen(uxMode === "developer");
  }, [uxMode]);

  const setUxModePersist = useCallback((m: DomAnalyzerUxMode) => {
    setUxMode(m);
    try {
      localStorage.setItem(DOM_ANALYZER_UX_MODE_KEY, m);
    } catch {
      /* ignore */
    }
  }, []);
  const [pendingOverrides, setPendingOverrides] = useState<Record<string, string>>({});
  const [newProfileVersion, setNewProfileVersion] = useState("");
  const [explore, setExplore] = useState<ExploreItem[]>([]);
  const [exploreSearch, setExploreSearch] = useState("");
  const [snapshotHtml, setSnapshotHtml] = useState("");
  const [snapshotB, setSnapshotB] = useState("");
  const [diffOut, setDiffOut] = useState("");
  const [loading, setLoading] = useState(false);
  const [banner, setBanner] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [tab, setTab] = useState<"conn" | "val" | "repair" | "ex" | "act" | "snap">("conn");
  const [actionResult, setActionResult] = useState<string>("");
  const versionRef = useRef(version);
  versionRef.current = version;

  const toast = useCallback((text: string, type: "ok" | "err" = "ok") => {
    setBanner({ type, text });
    window.setTimeout(() => setBanner(null), 7000);
  }, []);

  const run = useCallback(
    async (fn: () => Promise<void>) => {
      setLoading(true);
      try {
        await fn();
      } catch (e) {
        toast(e instanceof Error ? e.message : String(e), "err");
      } finally {
        setLoading(false);
      }
    },
    [toast],
  );

  const loadStatus = useCallback(() => {
    return run(async () => {
      const r = await apiFetch(`${basePath(ide)}/status${versionQs()}`, auth);
      const data = (await r.json().catch(() => ({}))) as StatusPayload & { detail?: unknown };
      if (!r.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "status failed");
      }
      setStatus(data);
      if (!versionRef.current.trim() && data.selector_version) setVersion(data.selector_version);
    });
  }, [auth, ide, run, versionQs]);

  useEffect(() => {
    if (!IDES.includes(ide as (typeof IDES)[number])) {
      setBanner({ type: "err", text: `Unknown IDE: ${ide}` });
      return;
    }
    setBanner(null);
    setVersion("");
    setStatus(null);
    setRows([]);
    setRepairData(null);
    setRepairRaw("");
    setSelfHealRaw("");
    setLastSelfHeal(null);
    setPendingOverrides({});
    setNewProfileVersion("");
    setActionResult("");
  }, [ide]);

  useEffect(() => {
    if (!IDES.includes(ide as (typeof IDES)[number])) return;
    void loadStatus();
  }, [ide, loadStatus]);

  const validateAll = () =>
    run(async () => {
      const r = await apiFetch(`${basePath(ide)}/validate${versionQs()}`, auth, {
        method: "POST",
        body: JSON.stringify({ keys: null }),
      });
      const data = (await r.json().catch(() => ({}))) as { rows?: ValidateRow[]; detail?: unknown };
      if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "validate failed");
      setRows(data.rows || []);
      toast("Validation complete");
    });

  const recheckKey = (key: string) =>
    run(async () => {
      const r = await apiFetch(`${basePath(ide)}/validate${versionQs()}`, auth, {
        method: "POST",
        body: JSON.stringify({ keys: [key] }),
      });
      const data = (await r.json().catch(() => ({}))) as { rows?: ValidateRow[] };
      if (!r.ok) throw new Error("validate failed");
      const next = data.rows || [];
      setRows((prev) => {
        const m = new Map(prev.map((x) => [x.key, x]));
        for (const row of next) m.set(row.key, row);
        return Array.from(m.values());
      });
      toast(`Rechecked ${key}`);
    });

  const runRepair = () =>
    run(async () => {
      const keys = ["aiMessages", "userMessages", "input"];
      const r = await apiFetch(`${basePath(ide)}/repair${versionQs()}`, auth, {
        method: "POST",
        body: JSON.stringify({ keys }),
      });
      const data = (await r.json().catch(() => ({}))) as RepairData & { detail?: unknown };
      if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "repair failed");
      setRepairData(data);
      setRepairRaw(JSON.stringify(data, null, 2));
      toast("Repair candidates loaded");
    });

  const runSelfHeal = (persist: boolean) =>
    run(async () => {
      const r = await apiFetch(`${basePath(ide)}/self-heal${versionQs()}`, auth, {
        method: "POST",
        body: JSON.stringify({
          dry_run: !persist,
          confirm: persist,
        }),
      });
      const data = (await r.json().catch(() => ({}))) as SelfHealPayload & { detail?: unknown };
      if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "self-heal failed");
      setLastSelfHeal(data);
      setSelfHealRaw(JSON.stringify(data, null, 2));
      if (data.new_version) setVersion(data.new_version);
      toast(selfHealSummaryLine(data, data.persisted === true));
    });

  const loadExplore = () =>
    run(async () => {
      const qs = new URLSearchParams();
      const v = version.trim();
      if (v) qs.set("version", v);
      qs.set("search", exploreSearch);
      qs.set("limit", "400");
      const r = await apiFetch(`${basePath(ide)}/explore?${qs.toString()}`, auth);
      const data = (await r.json().catch(() => ({}))) as { items?: ExploreItem[]; detail?: unknown };
      if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "explore failed");
      setExplore(data.items || []);
    });

  const captureSnapshot = () =>
    run(async () => {
      const r = await apiFetch(`${basePath(ide)}/snapshot${versionQs()}`, auth, {
        method: "POST",
        body: JSON.stringify({ mode: "html", max_chars: 120_000 }),
      });
      const data = (await r.json().catch(() => ({}))) as { content?: string; detail?: unknown };
      if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "snapshot failed");
      setSnapshotHtml(data.content || "");
      toast("Snapshot captured");
    });

  const doDiff = () => {
    run(async () => {
      const r = await apiFetch(`${basePath(ide)}/diff`, auth, {
        method: "POST",
        body: JSON.stringify({ a: snapshotHtml, b: snapshotB }),
      });
      const data = (await r.json().catch(() => ({}))) as { unified_diff?: string; detail?: unknown };
      if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "diff failed");
      setDiffOut(data.unified_diff || "");
      toast("Diff computed");
    });
  };

  const runAction = (name: string, body: Record<string, unknown>) => {
    const needsClientConfirm = DANGEROUS.has(name);
    if (needsClientConfirm && !window.confirm(`Run action “${name}” on the connected IDE?`)) return;
    run(async () => {
      const r = await apiFetch(`${basePath(ide)}/action${versionQs()}`, auth, {
        method: "POST",
        body: JSON.stringify({ action: name, confirm: true, ...body }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(
          typeof data === "object" && data && "detail" in data ? String((data as { detail: unknown }).detail) : "action failed",
        );
      }
      setActionResult(JSON.stringify(data, null, 2));
      toast(`Action ${name} ok`);
    });
  };

  const applyProfile = () =>
    run(async () => {
      const nv = newProfileVersion.trim();
      if (!nv) throw new Error("Enter new profile version");
      if (Object.keys(pendingOverrides).length === 0) throw new Error("Pick at least one candidate (Use selector)");
      if (!window.confirm(`Write new selector file version “${nv}” and backup the base profile?`)) return;
      const r = await apiFetch(`${basePath(ide)}/profile/apply`, auth, {
        method: "POST",
        body: JSON.stringify({
          base_version: version.trim() || null,
          new_version: nv,
          overrides: pendingOverrides,
          confirm: true,
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(
          typeof data === "object" && data && "detail" in data ? String((data as { detail: unknown }).detail) : "apply failed",
        );
      }
      toast(`Profile saved: ${(data as { path?: string }).path || nv}`);
      setPendingOverrides({});
    });

  const ideBad = !IDES.includes(ide as (typeof IDES)[number]);
  const ideLabel = IDES.includes(ide as (typeof IDES)[number]) ? IDE_LABEL[ide as (typeof IDES)[number]] : ide;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 text-neutral-100">
      {banner ? (
        <div
          className={`mb-4 rounded-lg border px-3 py-2 text-sm ${
            banner.type === "ok" ? "border-emerald-500/40 bg-emerald-950/40 text-emerald-100" : "border-red-500/40 bg-red-950/40 text-red-100"
          }`}
        >
          {banner.text}
        </div>
      ) : null}

      <header className="border-b border-white/10 pb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-white">DOM Analyzer</h1>
            <p className="mt-1 text-sm text-surface-muted">
              <span className="font-medium text-neutral-200">{ideLabel}</span>
              {status?.inferred_semver ? (
                <>
                  {" "}
                  · <span className="text-neutral-300">v{status.inferred_semver}</span>
                </>
              ) : null}
              {status?.selector_version ? (
                <>
                  {" "}
                  · selector profile{" "}
                  <span className="font-mono text-neutral-300">{status.selector_version}</span>
                </>
              ) : null}
            </p>
            <p className="mt-1 text-xs text-surface-muted">
              Current selector profile (query):{" "}
              <span className="font-mono text-neutral-400">{version.trim() || "(resolved by server)"}</span>
            </p>
          </div>
          <div className="text-right text-xs text-surface-muted">
            <div>
              Connection:{" "}
              <span className={status?.connected ? "text-emerald-400" : "text-amber-400"}>
                {status?.connected ? "connected" : "disconnected / error"}
              </span>
            </div>
            <div className="mt-0.5 max-w-md truncate" title={status?.active_page_url || ""}>
              Active page: {status?.active_page_url || "—"}
            </div>
            <div className="mt-0.5 truncate" title={status?.document_title || ""}>
              Window: {status?.document_title || "—"}
            </div>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-surface-muted">IDE</span>
          <div className="flex flex-wrap gap-1">
            {IDES.map((id) => (
              <button
                key={id}
                type="button"
                disabled={loading}
                onClick={() => navigate(`/admin/ide-agents/${id}/dom-analyzer`)}
                className={`rounded-md px-2 py-1 text-xs font-medium ${
                  id === ide ? "bg-sky-600 text-white" : "border border-white/15 bg-white/5 text-surface-muted hover:bg-white/10"
                }`}
              >
                {IDE_LABEL[id]}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-xs text-surface-muted">
            Selector version
            <input
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="(server default)"
              className="w-40 rounded border border-white/15 bg-black/30 px-2 py-1 font-mono text-xs text-neutral-200"
            />
          </label>
          <button
            type="button"
            disabled={loading || ideBad}
            onClick={() => void loadStatus()}
            className="rounded-md border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium hover:bg-white/10 disabled:opacity-40"
          >
            Refresh status
          </button>
          <Link to="/admin/ide-agent" className="text-xs text-sky-400 hover:underline">
            Operator settings
          </Link>
          <span className="text-xs text-surface-muted">View</span>
          <div className="flex flex-wrap gap-1 rounded-md border border-white/10 bg-black/20 p-0.5">
            {(
              [
                ["operator", "Operator"],
                ["developer", "Developer"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                title={
                  id === "operator"
                    ? "Summary-first UI; technical JSON stays tucked away"
                    : "Raw JSON, full selectors, counts — for debugging"
                }
                aria-pressed={uxMode === id}
                onClick={() => setUxModePersist(id)}
                className={`rounded px-2 py-1 text-xs font-medium ${
                  uxMode === id ? "bg-sky-600 text-white" : "text-surface-muted hover:bg-white/10"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <span className="text-xs text-surface-muted">
            API <code className="text-neutral-400">/v1/admin/ide-agents/{`{ide}`}/…</code>
          </span>
        </div>
      </header>

      {ideBad ? (
        <p className="mt-4 text-sm text-red-300">
          Unsupported IDE in URL. Use one of: {IDES.join(", ")}.{" "}
          <Link className="text-sky-400 underline" to="/admin/ide-agents/cursor/dom-analyzer">
            Open Cursor
          </Link>
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2 border-b border-white/10 pb-2">
        {(
          [
            ["conn", "Connection"],
            ["val", "Validator"],
            ["repair", "Repair"],
            ["ex", "DOM Explorer"],
            ["act", "Actions"],
            ["snap", "Snapshot / Diff"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            onClick={() => setTab(k)}
            className={`rounded-t-md px-3 py-1.5 text-sm font-medium ${
              tab === k ? "bg-white/10 text-white" : "text-surface-muted hover:bg-white/5"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-4">
        {tab === "conn" && (
          <section className="rounded-xl border border-surface-border bg-surface-raised/40 p-4">
            <h2 className="text-sm font-semibold text-white">Connection status</h2>
            <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
              <dt className="text-surface-muted">CDP URL</dt>
              <dd className="break-all font-mono text-xs text-neutral-300">{status?.cdp_http_url || "—"}</dd>
              <dt className="text-surface-muted">IDE (route)</dt>
              <dd className="font-mono">{ide}</dd>
              <dt className="text-surface-muted">IDE version (hint)</dt>
              <dd>{status?.inferred_semver || status?.cdp_json_version || "—"}</dd>
              <dt className="text-surface-muted">Connected</dt>
              <dd>{status?.connected ? "yes" : "no"}</dd>
              <dt className="text-surface-muted">Active page</dt>
              <dd className="break-all font-mono text-xs">{status?.active_page_url || "—"}</dd>
              <dt className="text-surface-muted">Current selector profile</dt>
              <dd className="font-mono text-xs">{status?.selector_version || "—"}</dd>
              <dt className="text-surface-muted">Last refresh</dt>
              <dd>{status?.last_refresh || "—"}</dd>
              <dt className="text-surface-muted">Error</dt>
              <dd className="text-amber-200/90">{status?.error || "—"}</dd>
            </dl>
            <pre className="mt-3 max-h-40 overflow-auto rounded-lg bg-black/40 p-2 text-xs text-neutral-400">
              {JSON.stringify(status?.dashboard_hints ?? {}, null, 2)}
            </pre>
          </section>
        )}

        {tab === "val" && (
          <section className="rounded-xl border border-surface-border bg-surface-raised/40 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-white">Selector validator</h2>
                {uxMode === "operator" ? (
                  <p className="mt-0.5 text-[11px] text-surface-muted">Long selectors are truncated; switch to Developer for full strings.</p>
                ) : null}
              </div>
              <button
                type="button"
                disabled={loading}
                onClick={() => void validateAll()}
                className="rounded-md bg-sky-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500 disabled:opacity-40"
              >
                Validate all
              </button>
            </div>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[880px] border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-surface-muted">
                    <th className="py-2 pr-2">Key</th>
                    <th className="py-2 pr-2">Selector</th>
                    <th className="py-2 pr-2">Count</th>
                    <th className="py-2 pr-2">Visible</th>
                    <th className="py-2 pr-2">Clickable</th>
                    <th className="py-2 pr-2">Sample text</th>
                    <th className="py-2 pr-2">Status</th>
                    <th className="py-2"> </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.key} className="border-b border-white/5">
                      <td className="py-2 pr-2 align-top font-mono text-neutral-300">{row.key}</td>
                      <td
                        className={`py-2 pr-2 align-top font-mono text-[10px] text-neutral-500 ${
                          uxMode === "developer" ? "max-w-[min(520px,85vw)] break-all" : "max-w-[160px] truncate"
                        }`}
                        title={row.selector}
                      >
                        {row.selector}
                      </td>
                      <td className="py-2 pr-2 align-top">{row.count}</td>
                      <td className="py-2 pr-2 align-top">{row.visible}</td>
                      <td className="py-2 pr-2 align-top">{row.clickable}</td>
                      <td className="max-w-xs py-2 pr-2 align-top text-neutral-400" title={row.sample || ""}>
                        {(row.sample || "").slice(0, 120)}
                        {row.error ? <span className="mt-1 block text-red-300/90">{row.error}</span> : null}
                      </td>
                      <td className="py-2 pr-2 align-top">{row.status}</td>
                      <td className="py-2 align-top">
                        <button
                          type="button"
                          className="text-sky-400 hover:underline"
                          onClick={() => void recheckKey(row.key)}
                        >
                          Recheck
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length === 0 ? <p className="mt-2 text-sm text-surface-muted">Run “Validate all”.</p> : null}
            </div>
          </section>
        )}

        {tab === "repair" && (
          <section className="rounded-xl border border-surface-border bg-surface-raised/40 p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-sm font-semibold text-white">Repair center</h2>
              {uxMode === "developer" ? (
                <span className="rounded border border-violet-500/30 bg-violet-950/40 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-violet-200">
                  Developer view
                </span>
              ) : null}
            </div>
            <p className="mt-1 text-xs text-surface-muted">
              Ranked replacement candidates. “Preview” copies the CSS; “Use selector” stages an override for “Save profile”.
              Saving generates a new version file and backs up the base JSON (server-side).
            </p>
            <p className="mt-2 text-xs text-surface-muted">
              <span className="font-medium text-neutral-200">Automatic self-heal</span> finds and validates replacements
              for broken selectors. <span className="text-neutral-300">Dry run</span> shows what would change (no file
              write). <span className="text-neutral-300">Persist</span> saves a new version{" "}
              <code className="font-mono text-neutral-500">{`{base}-heal-{UTC}`}</code> when chat essentials pass checks.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={loading}
                onClick={() => void runSelfHeal(false)}
                className="rounded-md border border-emerald-500/40 bg-emerald-950/30 px-3 py-1.5 text-xs font-medium text-emerald-100 hover:bg-emerald-900/40 disabled:opacity-40"
              >
                Self-heal (dry run)
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={() => void runSelfHeal(true)}
                className="rounded-md border border-emerald-600/50 bg-emerald-800/40 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700/50 disabled:opacity-40"
              >
                Self-heal &amp; persist
              </button>
            </div>
            {lastSelfHeal ? <SelfHealSummaryCard data={lastSelfHeal} developerMode={uxMode === "developer"} /> : null}
            <button
              type="button"
              disabled={loading}
              onClick={() => void runRepair()}
              className="mt-2 rounded-md border border-amber-500/40 bg-amber-950/30 px-3 py-1.5 text-xs font-medium text-amber-100 hover:bg-amber-900/40 disabled:opacity-40"
            >
              Load candidates (aiMessages, userMessages, input)
            </button>

            {repairData?.candidates
              ? Object.entries(repairData.candidates).map(([key, cands]) => (
                  <div key={key} className="mt-4">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-surface-muted">{key}</h3>
                    <div className="mt-2 overflow-x-auto">
                      <table className="w-full min-w-[640px] border-collapse text-left text-xs">
                        <thead>
                          <tr className="border-b border-white/10 text-surface-muted">
                            <th className="py-1 pr-2">Rank</th>
                            <th className="py-1 pr-2">Matches</th>
                            <th className="py-1 pr-2">Selector</th>
                            <th className="py-1 pr-2">Source</th>
                            <th className="py-1"> </th>
                          </tr>
                        </thead>
                        <tbody>
                          {(cands || []).map((c, i) => (
                            <tr key={`${key}-${i}`} className="border-b border-white/5">
                              <td className="py-1.5 pr-2">{c.rank}</td>
                              <td className="py-1.5 pr-2">{c.matches}</td>
                              <td className="max-w-md py-1.5 pr-2 font-mono text-[10px] text-neutral-400">{c.css}</td>
                              <td className="py-1.5 pr-2 text-neutral-500">{c.source}</td>
                              <td className="space-x-2 py-1.5">
                                <button
                                  type="button"
                                  className="text-sky-400 hover:underline"
                                  onClick={() => {
                                    void navigator.clipboard.writeText(c.css);
                                    toast("Copied CSS");
                                  }}
                                >
                                  Preview (copy)
                                </button>
                                <button
                                  type="button"
                                  className="text-emerald-400 hover:underline"
                                  onClick={() => {
                                    setPendingOverrides((o) => ({ ...o, [key]: c.css }));
                                    toast(`Staged ${key}`);
                                  }}
                                >
                                  Use selector
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))
              : null}

            <div className="mt-4 rounded-lg border border-white/10 bg-black/30 p-3">
              <p className="text-xs font-medium text-white">Save updated profile</p>
              <p className="mt-1 text-xs text-surface-muted">
                Pending overrides:{" "}
                {Object.keys(pendingOverrides).length ? (
                  <span className="font-mono text-neutral-300">{Object.keys(pendingOverrides).join(", ")}</span>
                ) : (
                  "none"
                )}
              </p>
              <div className="mt-2 flex flex-wrap items-end gap-2">
                <label className="text-xs text-surface-muted">
                  New version id
                  <input
                    value={newProfileVersion}
                    onChange={(e) => setNewProfileVersion(e.target.value)}
                    placeholder="e.g. 0.0.2-custom"
                    className="ml-2 w-48 rounded border border-white/15 bg-black/40 px-2 py-1 font-mono text-xs"
                  />
                </label>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => void applyProfile()}
                  className="rounded-md bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-600 disabled:opacity-40"
                >
                  Save profile (writes JSON + backup)
                </button>
              </div>
            </div>

            <details
              className="mt-4 rounded-lg border border-white/10 bg-black/25 p-2"
              open={technicalDetailsOpen}
              onToggle={(e) => setTechnicalDetailsOpen(e.currentTarget.open)}
            >
              <summary className="cursor-pointer px-1 py-1 text-xs font-medium text-surface-muted">
                Technical details (JSON, raw responses)
              </summary>
              <p className="mt-2 px-1 text-[11px] leading-relaxed text-neutral-500">
                {uxMode === "developer"
                  ? "Developer mode: this section opens by default. Use for debugging and support tickets."
                  : "Operator mode: keep this closed unless support asks for a paste. Switch to Developer to focus on raw data."}
              </p>
              {selfHealRaw ? (
                <div className="mt-2 px-1">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-neutral-600">Self-heal</p>
                  <pre className="mt-1 max-h-48 overflow-auto rounded-lg bg-black/50 p-3 text-[10px] text-neutral-500">
                    {selfHealRaw}
                  </pre>
                </div>
              ) : null}
              {repairRaw && repairRaw !== "{}" ? (
                <div className="mt-3 px-1">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-neutral-600">Repair candidates</p>
                  <pre className="mt-1 max-h-48 overflow-auto rounded-lg bg-black/50 p-3 text-[10px] text-neutral-500">
                    {repairRaw}
                  </pre>
                </div>
              ) : null}
            </details>
          </section>
        )}

        {tab === "ex" && (
          <section className="rounded-xl border border-surface-border bg-surface-raised/40 p-4">
            <h2 className="text-sm font-semibold text-white">Live DOM explorer</h2>
            <p className="mt-1 text-xs text-surface-muted">
              Buttons, inputs, roles, aria-labels, and data-* attributes (server-side scan). Use search to filter the blob.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <input
                value={exploreSearch}
                onChange={(e) => setExploreSearch(e.target.value)}
                placeholder="Search (text, role, aria, data-*)"
                className="min-w-[200px] flex-1 rounded border border-white/15 bg-black/30 px-2 py-1 text-sm"
              />
              <button
                type="button"
                disabled={loading}
                onClick={() => void loadExplore()}
                className="rounded-md bg-sky-600 px-3 py-1 text-xs font-medium text-white hover:bg-sky-500 disabled:opacity-40"
              >
                Scan DOM
              </button>
            </div>
            <ul className="mt-3 max-h-[480px] space-y-2 overflow-auto text-xs">
              {explore.map((it, i) => {
                const dataCount = it.dataAttrs ? Object.keys(it.dataAttrs).length : 0;
                return (
                  <li key={i} className="rounded-lg border border-white/10 bg-black/25 p-2">
                    <div className="flex flex-wrap justify-between gap-2">
                      <span className="font-mono text-sky-300">
                        {it.tag}
                        {it.role ? (
                          <span className="ml-2 text-neutral-500">
                            role={it.role}
                          </span>
                        ) : null}
                      </span>
                      <button
                        type="button"
                        className="text-neutral-400 hover:text-white"
                        onClick={() => {
                          void navigator.clipboard.writeText(it.suggestSelector || "");
                          toast("Copied selector");
                        }}
                      >
                        Copy selector
                      </button>
                    </div>
                    {it.ariaLabel ? (
                      <div className="mt-1 text-neutral-400">aria-label: {it.ariaLabel}</div>
                    ) : null}
                    {it.placeholder ? (
                      <div className="mt-0.5 text-neutral-500">placeholder: {it.placeholder}</div>
                    ) : null}
                    {dataCount > 0 ? (
                      <div className="mt-0.5 font-mono text-[10px] text-neutral-600">
                        data-* ({dataCount}): {JSON.stringify(it.dataAttrs)}
                      </div>
                    ) : null}
                    <div className="mt-1 text-neutral-500">{it.textPreview}</div>
                    <div className="mt-1 font-mono text-[10px] text-neutral-600">{it.suggestSelector}</div>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {tab === "act" && (
          <section className="rounded-xl border border-surface-border bg-surface-raised/40 p-4">
            <h2 className="text-sm font-semibold text-white">Action console</h2>
            <p className="text-xs text-surface-muted">
              Requires Playwright + live IDE. Dangerous actions ask for confirmation in the browser, then send{" "}
              <code className="text-neutral-500">confirm: true</code> to the API.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <ActionBtn label="Read chat" onClick={() => runAction("read_chat", {})} disabled={loading} />
              <ActionBtn label="Accept changes" onClick={() => runAction("accept_changes", {})} disabled={loading} />
            </div>
            <OpenForm
              loading={loading}
              onOpenFile={(path) => runAction("open_file", { path })}
              onOpenFolder={(path) => runAction("open_folder", { path })}
              onSend={(message) => runAction("send_chat", { message })}
              onPress={(key) => runAction("press_key", { key })}
              onClickSel={(selector) => runAction("click_selector", { selector })}
            />
            {actionResult ? (
              <pre className="mt-4 max-h-64 overflow-auto rounded-lg border border-white/10 bg-black/40 p-3 text-xs text-neutral-400">
                {actionResult}
              </pre>
            ) : null}
          </section>
        )}

        {tab === "snap" && (
          <section className="rounded-xl border border-surface-border bg-surface-raised/40 p-4">
            <h2 className="text-sm font-semibold text-white">Snapshot / diff</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={loading}
                onClick={() => void captureSnapshot()}
                className="rounded-md bg-sky-600 px-3 py-1 text-xs text-white hover:bg-sky-500 disabled:opacity-40"
              >
                Capture snapshot A
              </button>
              <button
                type="button"
                disabled={loading || !snapshotHtml}
                onClick={() => {
                  const blob = new Blob([snapshotHtml], { type: "text/html;charset=utf-8" });
                  const a = document.createElement("a");
                  a.href = URL.createObjectURL(blob);
                  a.download = `dom-snapshot-${ide}-${Date.now()}.html`;
                  a.click();
                  URL.revokeObjectURL(a.href);
                  toast("Download started");
                }}
                className="rounded-md border border-white/20 px-3 py-1 text-xs disabled:opacity-40"
              >
                Save snapshot A (download)
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={() => void doDiff()}
                className="rounded-md border border-white/20 px-3 py-1 text-xs"
              >
                Compare A vs B
              </button>
            </div>
            <label className="mt-3 block text-xs text-surface-muted">
              Snapshot B (paste HTML for diff)
              <textarea
                value={snapshotB}
                onChange={(e) => setSnapshotB(e.target.value)}
                rows={4}
                className="mt-1 w-full rounded border border-white/15 bg-black/30 p-2 font-mono text-xs"
              />
            </label>
            <label className="mt-2 block text-xs text-surface-muted">
              Snapshot A (preview, truncated)
              <textarea
                readOnly
                value={snapshotHtml.slice(0, 8000)}
                rows={6}
                className="mt-1 w-full rounded border border-white/10 bg-black/40 p-2 font-mono text-xs text-neutral-500"
              />
            </label>
            <pre className="mt-3 max-h-64 overflow-auto rounded-lg bg-black/50 p-2 text-xs text-neutral-400">{diffOut || "—"}</pre>
          </section>
        )}
      </div>

      {loading ? (
        <div className="fixed bottom-4 right-4 z-10 rounded-lg border border-white/20 bg-black/80 px-3 py-2 text-xs text-white shadow-lg">
          Loading…
        </div>
      ) : null}
    </div>
  );
}

function ActionBtn(props: { label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      disabled={props.disabled}
      onClick={props.onClick}
      className="rounded-md border border-white/20 bg-white/5 px-3 py-1.5 text-xs hover:bg-white/10 disabled:opacity-40"
    >
      {props.label}
    </button>
  );
}

function OpenForm(props: {
  loading: boolean;
  onOpenFile: (path: string) => void;
  onOpenFolder: (path: string) => void;
  onSend: (message: string) => void;
  onPress: (key: string) => void;
  onClickSel: (selector: string) => void;
}) {
  const [path, setPath] = useState("");
  const [msg, setMsg] = useState("");
  const [key, setKey] = useState("Enter");
  const [sel, setSel] = useState("");
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <div className="space-y-2 rounded-lg border border-white/10 p-3">
        <input
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="/path/to/file"
          className="w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm"
        />
        <div className="flex gap-2">
          <button
            type="button"
            disabled={props.loading}
            onClick={() => props.onOpenFile(path)}
            className="rounded bg-sky-600 px-2 py-1 text-xs text-white"
          >
            Open file
          </button>
          <button
            type="button"
            disabled={props.loading}
            onClick={() => props.onOpenFolder(path)}
            className="rounded border border-white/20 px-2 py-1 text-xs"
          >
            Open folder
          </button>
        </div>
      </div>
      <div className="space-y-2 rounded-lg border border-white/10 p-3">
        <textarea
          value={msg}
          onChange={(e) => setMsg(e.target.value)}
          placeholder="Chat message"
          rows={3}
          className="w-full rounded border border-white/15 bg-black/30 p-2 text-sm"
        />
        <button
          type="button"
          disabled={props.loading}
          onClick={() => props.onSend(msg)}
          className="rounded bg-sky-600 px-2 py-1 text-xs text-white"
        >
          Send chat
        </button>
      </div>
      <div className="space-y-2 rounded-lg border border-white/10 p-3">
        <input
          value={key}
          onChange={(e) => setKey(e.target.value)}
          className="w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm"
        />
        <button type="button" disabled={props.loading} onClick={() => props.onPress(key)} className="rounded border border-white/20 px-2 py-1 text-xs">
          Press key
        </button>
      </div>
      <div className="space-y-2 rounded-lg border border-white/10 p-3">
        <input
          value={sel}
          onChange={(e) => setSel(e.target.value)}
          placeholder="CSS selector"
          className="w-full rounded border border-white/15 bg-black/30 px-2 py-1 font-mono text-sm"
        />
        <button type="button" disabled={props.loading} onClick={() => props.onClickSel(sel)} className="rounded border border-white/20 px-2 py-1 text-xs">
          Click selector
        </button>
      </div>
    </div>
  );
}
