import type { ChangeEvent, Dispatch, SetStateAction } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";
import type { UiBlock, UiLayout } from "./types";
import { EmbedBlockBody } from "./EmbedBlock";
import { KanbanBlockBody, RichMarkdownBlockBody } from "./KanbanRichMarkdownBlocks";
import { ChartBlockBody, SparklineBlockBody } from "./chart/ChartBlockViews";
import { getPath, setPath } from "./workspaceDataPaths";

type Row = Record<string, unknown>;

function newRowId(): string {
  return `r_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export function WorkspaceBlocks(props: {
  uiLayout: UiLayout | null | undefined;
  data: Record<string, unknown>;
  setData: Dispatch<SetStateAction<Record<string, unknown>>>;
}) {
  const { uiLayout, data, setData } = props;
  if (!uiLayout?.blocks?.length) {
    return <p className="text-sm text-surface-muted">No blocks in this layout.</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      {uiLayout.blocks.map((block) => (
        <WorkspaceBlockTile key={block.id} block={block} data={data} setData={setData} />
      ))}
    </div>
  );
}

/** Single block (used by list view and by the drag grid). */
export function WorkspaceBlockTile(props: {
  block: UiBlock;
  data: Record<string, unknown>;
  setData: Dispatch<SetStateAction<Record<string, unknown>>>;
  readOnly?: boolean;
  workspaceId?: string | null;
}) {
  return (
    <BlockView
      block={props.block}
      data={props.data}
      setData={props.setData}
      readOnly={props.readOnly === true}
      workspaceId={props.workspaceId ?? null}
    />
  );
}

const WS_FILE_PREFIX = "wsfile:";

function GalleryImage(props: { url: string; alt: string }) {
  const auth = useAuth();
  const { url, alt } = props;
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const blobRef = useRef<string | null>(null);

  useEffect(() => {
    if (!url.startsWith(WS_FILE_PREFIX)) {
      if (blobRef.current) {
        URL.revokeObjectURL(blobRef.current);
        blobRef.current = null;
      }
      setBlobUrl(null);
      return;
    }
    const id = url.slice(WS_FILE_PREFIX.length).trim();
    if (!id) {
      if (blobRef.current) {
        URL.revokeObjectURL(blobRef.current);
        blobRef.current = null;
      }
      setBlobUrl(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      const res = await apiFetch(`/v1/workspaces/files/${id}/content`, auth);
      if (!res.ok || cancelled) return;
      const b = await res.blob();
      if (cancelled) return;
      if (blobRef.current) URL.revokeObjectURL(blobRef.current);
      const created = URL.createObjectURL(b);
      blobRef.current = created;
      setBlobUrl(created);
    })();
    return () => {
      cancelled = true;
      if (blobRef.current) {
        URL.revokeObjectURL(blobRef.current);
        blobRef.current = null;
      }
    };
  }, [url, auth, auth.accessToken]);

  if (url.startsWith(WS_FILE_PREFIX)) {
    if (!blobUrl) {
      return (
        <div className="flex h-full items-center justify-center text-xs text-surface-muted">
          Laden…
        </div>
      );
    }
    return <img src={blobUrl} alt={alt} className="h-full w-full object-cover" />;
  }
  return (
    <img
      src={url}
      alt={alt}
      className="h-full w-full object-cover"
      onError={(e) => {
        (e.target as HTMLImageElement).style.display = "none";
      }}
    />
  );
}

function GalleryBlockBody(props: {
  dp: string;
  data: Record<string, unknown>;
  setData: Dispatch<SetStateAction<Record<string, unknown>>>;
  sectionTitle: string;
  workspaceId: string | null;
  readOnly: boolean;
}) {
  const { dp, data, setData, sectionTitle, workspaceId, readOnly } = props;
  const auth = useAuth();
  const rowsUnknown = dp ? getPath(data, dp) : [];
  const photos: Row[] = Array.isArray(rowsUnknown) ? (rowsUnknown as Row[]) : [];

  const updatePhoto = (index: number, field: string, value: unknown) => {
    setData((d) => {
      const list = [...((getPath(d, dp) as Row[]) || [])];
      const row = { ...(list[index] || {}) };
      row[field] = value;
      list[index] = row;
      return setPath(d, dp, list);
    });
  };

  const addPhoto = () => {
    setData((d) => {
      const list = [...((getPath(d, dp) as Row[]) || [])];
      list.push({ id: newRowId(), url: "", caption: "" });
      return setPath(d, dp, list);
    });
  };

  const removePhoto = (index: number) => {
    setData((d) => {
      const list = [...((getPath(d, dp) as Row[]) || [])];
      list.splice(index, 1);
      return setPath(d, dp, list);
    });
  };

  return (
    <section className="rounded-xl border border-surface-border bg-surface-raised/60 p-4">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-white">{sectionTitle}</h3>
        {!readOnly ? (
          <button
            type="button"
            className="rounded-md bg-violet-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-violet-500"
            onClick={addPhoto}
          >
            Foto +
          </button>
        ) : null}
      </div>
      {photos.length === 0 ? (
        <p className="rounded-lg border border-dashed border-white/15 py-10 text-center text-sm text-surface-muted">
          {readOnly
            ? "Noch keine Fotos in diesem Bereich."
            : "Einträge hinzufügen — Bild hochladen (Workspace speichern) oder externe URL eintragen."}
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {photos.map((row, ri) => (
            <GalleryPhotoCard
              key={String(row.id ?? ri)}
              ri={ri}
              url={String(row.url ?? "").trim()}
              caption={String(row.caption ?? "")}
              workspaceId={workspaceId}
              auth={auth}
              readOnly={readOnly}
              updatePhoto={updatePhoto}
              removePhoto={removePhoto}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function GalleryPhotoCard(props: {
  ri: number;
  url: string;
  caption: string;
  workspaceId: string | null;
  auth: ReturnType<typeof useAuth>;
  readOnly: boolean;
  updatePhoto: (index: number, field: string, value: unknown) => void;
  removePhoto: (index: number) => void;
}) {
  const { ri, url, caption, workspaceId, auth, readOnly, updatePhoto, removePhoto } = props;
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState<string | null>(null);

  const onPickFile = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f || !workspaceId) {
      if (!workspaceId) setUploadErr("Workspace speichern, dann Upload möglich.");
      return;
    }
    setUploading(true);
    setUploadErr(null);
    const fd = new FormData();
    fd.append("file", f);
    void (async () => {
      try {
        const res = await apiFetch(`/v1/workspaces/${workspaceId}/files`, auth, {
          method: "POST",
          body: fd,
        });
        const raw = await res.text();
        let j: { file?: { gallery_ref?: string }; detail?: unknown } = {};
        try {
          j = JSON.parse(raw) as typeof j;
        } catch {
          j = {};
        }
        if (!res.ok) {
          const msg =
            typeof j.detail === "string"
              ? j.detail
              : `Upload fehlgeschlagen (${res.status})`;
          setUploadErr(msg);
          return;
        }
        const ref = j.file?.gallery_ref;
        if (ref) updatePhoto(ri, "url", ref);
      } catch (err) {
        setUploadErr(err instanceof Error ? err.message : String(err));
      } finally {
        setUploading(false);
      }
    })();
  };

  if (readOnly) {
    return (
      <div className="overflow-hidden rounded-xl border border-surface-border bg-black/25 shadow-sm">
        <div className="aspect-video bg-gradient-to-br from-white/5 to-black/40">
          {url ? (
            <GalleryImage url={url} alt={caption} />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-surface-muted">
              Kein Bild
            </div>
          )}
        </div>
        {caption ? (
          <p className="border-t border-white/5 p-3 text-xs text-neutral-200">{caption}</p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-surface-border bg-black/25 shadow-sm">
      <div className="aspect-video bg-gradient-to-br from-white/5 to-black/40">
        {url ? (
          <GalleryImage url={url} alt={caption} />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-surface-muted">
            URL oder Upload
          </div>
        )}
      </div>
      <div className="space-y-2 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <label className="workspace-grid-no-drag cursor-pointer rounded-md bg-white/10 px-2 py-1 text-xs text-white hover:bg-white/15">
            {uploading ? "…" : "Hochladen"}
            <input
              type="file"
              accept="image/jpeg,image/png,image/gif,image/webp"
              className="hidden"
              disabled={uploading || !workspaceId}
              onChange={onPickFile}
            />
          </label>
          {!workspaceId ? (
            <span className="text-[10px] text-amber-200/90">Speichern für Upload</span>
          ) : null}
        </div>
        {uploadErr ? <p className="text-[10px] text-red-400">{uploadErr}</p> : null}
        <input
          type="url"
          placeholder="https://… oder wsfile:…"
          className="w-full rounded-md border border-surface-border bg-black/40 px-2 py-1.5 text-xs text-neutral-100 placeholder:text-white/25"
          value={url}
          onChange={(e) => updatePhoto(ri, "url", e.target.value)}
        />
        <input
          type="text"
          placeholder="Beschriftung"
          className="w-full rounded-md border border-surface-border bg-black/40 px-2 py-1.5 text-xs text-neutral-100"
          value={caption}
          onChange={(e) => updatePhoto(ri, "caption", e.target.value)}
        />
        <button
          type="button"
          className="w-full rounded-md py-1 text-xs text-red-400 hover:bg-red-950/30"
          onClick={() => removePhoto(ri)}
        >
          Entfernen
        </button>
      </div>
    </div>
  );
}

type HeroState = { url: string; caption: string; headline: string };

function readHero(raw: unknown): HeroState {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const o = raw as Record<string, unknown>;
    return {
      url: String(o.url ?? "").trim(),
      caption: String(o.caption ?? ""),
      headline: String(o.headline ?? ""),
    };
  }
  return { url: "", caption: "", headline: "" };
}

function HeroBlockBody(props: {
  dp: string;
  data: Record<string, unknown>;
  setData: Dispatch<SetStateAction<Record<string, unknown>>>;
  sectionTitle: string;
  workspaceId: string | null;
  readOnly: boolean;
}) {
  const { dp, data, setData, sectionTitle, workspaceId, readOnly } = props;
  const auth = useAuth();
  const hero = readHero(dp ? getPath(data, dp) : undefined);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState<string | null>(null);

  const patchHero = (partial: Partial<HeroState>) => {
    setData((d) => {
      const cur = readHero(dp ? getPath(d, dp) : undefined);
      return setPath(d, dp, { ...cur, ...partial });
    });
  };

  const onPickFile = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f || !workspaceId) {
      if (!workspaceId) setUploadErr("Workspace speichern, dann Upload möglich.");
      return;
    }
    setUploading(true);
    setUploadErr(null);
    const fd = new FormData();
    fd.append("file", f);
    void (async () => {
      try {
        const res = await apiFetch(`/v1/workspaces/${workspaceId}/files`, auth, {
          method: "POST",
          body: fd,
        });
        const raw = await res.text();
        let j: { file?: { gallery_ref?: string }; detail?: unknown } = {};
        try {
          j = JSON.parse(raw) as typeof j;
        } catch {
          j = {};
        }
        if (!res.ok) {
          const msg =
            typeof j.detail === "string"
              ? j.detail
              : `Upload fehlgeschlagen (${res.status})`;
          setUploadErr(msg);
          return;
        }
        const ref = j.file?.gallery_ref;
        if (ref) patchHero({ url: ref });
      } catch (err) {
        setUploadErr(err instanceof Error ? err.message : String(err));
      } finally {
        setUploading(false);
      }
    })();
  };

  const imageArea = (
    <div className="relative isolate min-h-[200px] w-full overflow-hidden rounded-xl border border-white/10 bg-gradient-to-br from-sky-950/40 via-black/50 to-violet-950/30 aspect-[2.2/1] max-h-[min(420px,55vh)]">
      {hero.url ? (
        <>
          <div className="absolute inset-0">
            <GalleryImage url={hero.url} alt={hero.headline || hero.caption || "Hero"} />
          </div>
          {hero.headline ? (
            <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/40 to-transparent px-5 pb-4 pt-16">
              <p className="text-lg font-semibold tracking-tight text-white drop-shadow-md md:text-xl">
                {hero.headline}
              </p>
            </div>
          ) : null}
        </>
      ) : (
        <div className="flex h-full min-h-[200px] flex-col items-center justify-center gap-2 px-6 text-center">
          <p className="text-sm text-surface-muted">
            {readOnly
              ? "Kein Hero-Bild gesetzt."
              : "Hero-Bild: URL eintragen oder hochladen (Workspace speichern)."}
          </p>
        </div>
      )}
    </div>
  );

  if (readOnly) {
    return (
      <section className="rounded-xl border border-surface-border bg-surface-raised/60 p-3 md:p-4">
        <h3 className="mb-3 text-xs font-medium uppercase tracking-wide text-surface-muted">
          {sectionTitle}
        </h3>
        {imageArea}
        {hero.caption ? (
          <p className="mt-3 text-sm leading-relaxed text-neutral-200">{hero.caption}</p>
        ) : null}
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-surface-border bg-surface-raised/60 p-3 md:p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-white">{sectionTitle}</h3>
        <label className="workspace-grid-no-drag cursor-pointer rounded-md bg-violet-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-violet-500">
          {uploading ? "…" : "Bild hochladen"}
          <input
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            className="hidden"
            disabled={uploading || !workspaceId}
            onChange={onPickFile}
          />
        </label>
      </div>
      {!workspaceId ? (
        <p className="mb-2 text-[10px] text-amber-200/90">Zuerst Workspace speichern, dann Upload.</p>
      ) : null}
      {uploadErr ? <p className="mb-2 text-xs text-red-400">{uploadErr}</p> : null}
      {imageArea}
      <div className="mt-4 space-y-3">
        <div>
          <label className="mb-1 block text-[10px] uppercase tracking-wide text-surface-muted">
            Bild-URL
          </label>
          <input
            type="url"
            placeholder="https://… oder wsfile:…"
            className="workspace-grid-no-drag w-full rounded-lg border border-surface-border bg-black/40 px-3 py-2 text-sm text-neutral-100 placeholder:text-white/25"
            value={hero.url}
            onChange={(e) => patchHero({ url: e.target.value })}
          />
        </div>
        <div>
          <label className="mb-1 block text-[10px] uppercase tracking-wide text-surface-muted">
            Überschrift (auf dem Bild)
          </label>
          <input
            type="text"
            placeholder="z. B. Name des Tieres"
            className="workspace-grid-no-drag w-full rounded-lg border border-surface-border bg-black/40 px-3 py-2 text-sm text-neutral-100"
            value={hero.headline}
            onChange={(e) => patchHero({ headline: e.target.value })}
          />
        </div>
        <div>
          <label className="mb-1 block text-[10px] uppercase tracking-wide text-surface-muted">
            Untertitel / Beschreibung
          </label>
          <textarea
            className="workspace-grid-no-drag min-h-[72px] w-full resize-y rounded-lg border border-surface-border bg-black/40 px-3 py-2 text-sm text-neutral-100"
            placeholder="Kurzer Text unter dem Bild…"
            value={hero.caption}
            onChange={(e) => patchHero({ caption: e.target.value })}
          />
        </div>
      </div>
    </section>
  );
}

type StatTrend = "" | "up" | "down";

type StatState = { value: string; label: string; suffix: string; trend: StatTrend };

function readStat(raw: unknown): StatState {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const o = raw as Record<string, unknown>;
    const tr = String(o.trend ?? "").trim().toLowerCase();
    const trend: StatTrend =
      tr === "up" || tr === "down" ? tr : "";
    return {
      value: o.value == null ? "" : String(o.value),
      label: String(o.label ?? ""),
      suffix: String(o.suffix ?? ""),
      trend,
    };
  }
  return { value: "", label: "", suffix: "", trend: "" };
}

function StatBlockBody(props: {
  dp: string;
  data: Record<string, unknown>;
  setData: Dispatch<SetStateAction<Record<string, unknown>>>;
  sectionTitle: string;
  readOnly: boolean;
}) {
  const { dp, data, setData, sectionTitle, readOnly } = props;
  const stat = readStat(dp ? getPath(data, dp) : undefined);

  const patchStat = (partial: Partial<StatState>) => {
    setData((d) => {
      const cur = readStat(dp ? getPath(d, dp) : undefined);
      return setPath(d, dp, { ...cur, ...partial });
    });
  };

  const trendGlyph =
    stat.trend === "up" ? (
      <span className="text-emerald-400" title="Trend aufwärts">
        ↑
      </span>
    ) : stat.trend === "down" ? (
      <span className="text-rose-400" title="Trend abwärts">
        ↓
      </span>
    ) : null;

  return (
    <section className="flex h-full min-h-[140px] flex-col rounded-xl border border-surface-border bg-gradient-to-br from-slate-900/80 to-black/50 p-4">
      <p className="text-[10px] font-medium uppercase tracking-wide text-surface-muted">
        {sectionTitle}
      </p>
      {stat.label ? (
        <p className="mt-1 line-clamp-2 text-xs text-neutral-300">{stat.label}</p>
      ) : null}
      <div className="mt-auto flex flex-wrap items-end gap-2 pt-3">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="truncate text-3xl font-semibold tabular-nums tracking-tight text-white">
            {stat.value || "—"}
          </span>
          {stat.suffix ? (
            <span className="shrink-0 text-sm text-surface-muted">{stat.suffix}</span>
          ) : null}
          {trendGlyph ? <span className="text-xl leading-none">{trendGlyph}</span> : null}
        </div>
      </div>
      {!readOnly ? (
        <div className="mt-4 space-y-2 border-t border-white/5 pt-3">
          <input
            type="text"
            placeholder="Beschriftung (optional)"
            className="workspace-grid-no-drag w-full rounded-md border border-surface-border bg-black/40 px-2 py-1.5 text-xs text-neutral-100"
            value={stat.label}
            onChange={(e) => patchStat({ label: e.target.value })}
          />
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Wert"
              className="workspace-grid-no-drag min-w-0 flex-1 rounded-md border border-surface-border bg-black/40 px-2 py-1.5 text-xs text-neutral-100"
              value={stat.value}
              onChange={(e) => patchStat({ value: e.target.value })}
            />
            <input
              type="text"
              placeholder="Suffix"
              className="workspace-grid-no-drag w-20 shrink-0 rounded-md border border-surface-border bg-black/40 px-2 py-1.5 text-xs text-neutral-100"
              value={stat.suffix}
              onChange={(e) => patchStat({ suffix: e.target.value })}
            />
          </div>
          <select
            className="workspace-grid-no-drag w-full rounded-md border border-surface-border bg-black/40 px-2 py-1.5 text-xs text-neutral-100"
            value={stat.trend}
            onChange={(e) => patchStat({ trend: e.target.value as StatTrend })}
          >
            <option value="">Kein Trend</option>
            <option value="up">↑ Aufwärts</option>
            <option value="down">↓ Abwärts</option>
          </select>
        </div>
      ) : null}
    </section>
  );
}

function parseEventDateMs(raw: string): number {
  const s = raw.trim();
  if (!s) return Number.POSITIVE_INFINITY;
  const t = Date.parse(s);
  return Number.isFinite(t) ? t : Number.POSITIVE_INFINITY;
}

function formatEventDate(raw: string): string {
  const s = raw.trim();
  if (!s) return "—";
  const t = Date.parse(s);
  if (!Number.isFinite(t)) return s;
  try {
    return new Date(t).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return s;
  }
}

function TimelineBlockBody(props: {
  dp: string;
  data: Record<string, unknown>;
  setData: Dispatch<SetStateAction<Record<string, unknown>>>;
  sectionTitle: string;
  readOnly: boolean;
}) {
  const { dp, data, setData, sectionTitle, readOnly } = props;

  const sorted = useMemo(() => {
    const rowsUnknown = dp ? getPath(data, dp) : [];
    const rows: Row[] = Array.isArray(rowsUnknown) ? (rowsUnknown as Row[]) : [];
    return [...rows].sort(
      (a, b) =>
        parseEventDateMs(String(a.date ?? "")) - parseEventDateMs(String(b.date ?? ""))
    );
  }, [dp, data]);

  const updateRow = (indexInSorted: number, field: string, value: unknown) => {
    const id = sorted[indexInSorted]?.id;
    setData((d) => {
      const list = [...((getPath(d, dp) as Row[]) || [])];
      const ix = id != null ? list.findIndex((r) => r.id === id) : -1;
      if (ix < 0) return d;
      const row = { ...(list[ix] || {}) };
      row[field] = value;
      list[ix] = row;
      return setPath(d, dp, list);
    });
  };

  const addEvent = () => {
    setData((d) => {
      const list = [...((getPath(d, dp) as Row[]) || [])];
      const day = new Date().toISOString().slice(0, 10);
      list.push({
        id: newRowId(),
        title: "",
        date: day,
        note: "",
      });
      return setPath(d, dp, list);
    });
  };

  const removeRow = (indexInSorted: number) => {
    const id = sorted[indexInSorted]?.id;
    setData((d) => {
      const list = [...((getPath(d, dp) as Row[]) || [])];
      const ix = id != null ? list.findIndex((r) => r.id === id) : -1;
      if (ix < 0) return d;
      list.splice(ix, 1);
      return setPath(d, dp, list);
    });
  };

  return (
    <section className="rounded-xl border border-surface-border bg-surface-raised/60 p-4">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-white">{sectionTitle}</h3>
        {!readOnly ? (
          <button
            type="button"
            className="rounded-md bg-sky-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500"
            onClick={addEvent}
          >
            Eintrag +
          </button>
        ) : null}
      </div>
      {sorted.length === 0 ? (
        <p className="rounded-lg border border-dashed border-white/15 py-8 text-center text-sm text-surface-muted">
          {readOnly
            ? "Keine Einträge."
            : "Ereignisse mit Datum — chronologisch sortiert (älteste oben)."}
        </p>
      ) : (
        <div className="relative pl-1">
          <div
            className="absolute bottom-2 left-[7px] top-2 w-px bg-gradient-to-b from-sky-500/50 via-white/15 to-violet-500/40"
            aria-hidden
          />
          <ul className="space-y-0">
          {sorted.map((row, si) => (
            <li key={String(row.id ?? si)} className="relative flex gap-3 pb-6 last:pb-0">
              <div className="relative z-[1] mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full border-2 border-sky-500/80 bg-black shadow-[0_0_12px_rgba(56,189,248,0.35)]" />
              <div className="min-w-0 flex-1 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
                <p className="text-[11px] font-medium uppercase tracking-wide text-sky-400/90">
                  {formatEventDate(String(row.date ?? ""))}
                </p>
                {readOnly ? (
                  <>
                    <p className="mt-1 text-sm font-medium text-white">
                      {String(row.title ?? "").trim() || "—"}
                    </p>
                    {String(row.note ?? "").trim() ? (
                      <p className="mt-1 text-xs text-surface-muted">{String(row.note)}</p>
                    ) : null}
                  </>
                ) : (
                  <div className="mt-2 space-y-2">
                    <input
                      type="text"
                      placeholder="Titel"
                      className="workspace-grid-no-drag w-full rounded-md border border-surface-border bg-black/40 px-2 py-1.5 text-sm text-white"
                      value={String(row.title ?? "")}
                      onChange={(e) => updateRow(si, "title", e.target.value)}
                    />
                    <div className="flex flex-wrap gap-2">
                      <input
                        type="date"
                        className="workspace-grid-no-drag rounded-md border border-surface-border bg-black/40 px-2 py-1.5 text-xs text-neutral-100"
                        value={String(row.date ?? "").slice(0, 10)}
                        onChange={(e) => updateRow(si, "date", e.target.value)}
                      />
                      <button
                        type="button"
                        className="ml-auto rounded px-2 py-1 text-xs text-red-400 hover:bg-white/5"
                        onClick={() => removeRow(si)}
                      >
                        Entfernen
                      </button>
                    </div>
                    <textarea
                      placeholder="Notiz (optional)"
                      className="workspace-grid-no-drag min-h-[56px] w-full resize-y rounded-md border border-surface-border bg-black/40 px-2 py-1.5 text-xs text-neutral-200"
                      value={String(row.note ?? "")}
                      onChange={(e) => updateRow(si, "note", e.target.value)}
                    />
                  </div>
                )}
              </div>
            </li>
          ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function BlockView(props: {
  block: UiBlock;
  data: Record<string, unknown>;
  setData: Dispatch<SetStateAction<Record<string, unknown>>>;
  workspaceId: string | null;
  readOnly: boolean;
}) {
  const { block, data, setData, workspaceId, readOnly } = props;
  const dp = block.props.dataPath || "";

  if (block.type === "hero") {
    return (
      <HeroBlockBody
        dp={dp}
        data={data}
        setData={setData}
        sectionTitle={block.props.title || "Hero"}
        workspaceId={workspaceId}
        readOnly={readOnly}
      />
    );
  }

  if (block.type === "stat") {
    return (
      <StatBlockBody
        dp={dp}
        data={data}
        setData={setData}
        sectionTitle={block.props.title || "KPI"}
        readOnly={readOnly}
      />
    );
  }

  if (block.type === "timeline") {
    return (
      <TimelineBlockBody
        dp={dp}
        data={data}
        setData={setData}
        sectionTitle={block.props.title || "Timeline"}
        readOnly={readOnly}
      />
    );
  }

  if (block.type === "chart") {
    return (
      <ChartBlockBody
        dp={dp}
        data={data}
        setData={setData}
        sectionTitle={block.props.title || "Diagramm"}
        readOnly={readOnly}
      />
    );
  }

  if (block.type === "sparkline") {
    return (
      <SparklineBlockBody
        dp={dp}
        data={data}
        setData={setData}
        sectionTitle={block.props.title || "Sparkline"}
        readOnly={readOnly}
      />
    );
  }

  if (block.type === "kanban") {
    return (
      <KanbanBlockBody
        dp={dp}
        data={data}
        setData={setData}
        sectionTitle={block.props.title || "Kanban"}
        readOnly={readOnly}
      />
    );
  }

  if (block.type === "rich_markdown") {
    return (
      <RichMarkdownBlockBody
        dp={dp}
        data={data}
        setData={setData}
        sectionTitle={block.props.title || "Rich Markdown"}
        placeholder={block.props.placeholder || ""}
        readOnly={readOnly}
      />
    );
  }

  if (block.type === "embed") {
    return (
      <EmbedBlockBody
        dp={dp}
        data={data}
        setData={setData}
        sectionTitle={block.props.title || "Embed"}
        readOnly={readOnly}
      />
    );
  }

  if (block.type === "markdown") {
    const raw = getPath(data, dp);
    const text = typeof raw === "string" ? raw : "";
    return (
      <section className="rounded-xl border border-surface-border bg-surface-raised/60 p-4">
        <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-surface-muted">
          {block.props.placeholder || dp || "Text"}
        </label>
        <textarea
          readOnly={readOnly}
          className="min-h-[120px] w-full resize-y rounded-lg border border-surface-border bg-black/30 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-sky-500/50 read-only:cursor-default read-only:opacity-90"
          value={text}
          placeholder={block.props.placeholder || ""}
          onChange={(e) =>
            setData((d) => setPath(d, dp, e.target.value))
          }
        />
      </section>
    );
  }

  if (block.type === "gallery") {
    return (
      <GalleryBlockBody
        dp={dp}
        data={data}
        setData={setData}
        sectionTitle={block.props.title || "Fotos"}
        workspaceId={workspaceId}
        readOnly={readOnly}
      />
    );
  }

  if (block.type === "table") {
    const rowsUnknown = dp ? getPath(data, dp) : [];
    const rows: Row[] = Array.isArray(rowsUnknown)
      ? (rowsUnknown as Row[])
      : [];
    const cols = block.props.columns || [];

    const updateRow = (index: number, field: string, value: unknown) => {
      setData((d) => {
        const list = [...((getPath(d, dp) as Row[]) || [])];
        const row = { ...(list[index] || {}) };
        row[field] = value;
        list[index] = row;
        return setPath(d, dp, list);
      });
    };

    const addRow = () => {
      setData((d) => {
        const list = [...((getPath(d, dp) as Row[]) || [])];
        const base: Row = { id: newRowId() };
        for (const c of cols) {
          if (c.kind === "checkbox") base[c.field] = false;
          else if (c.kind === "number") base[c.field] = 1;
          else if (c.kind === "select") base[c.field] = c.options?.[0] ?? "";
          else base[c.field] = "";
        }
        list.push(base);
        return setPath(d, dp, list);
      });
    };

    const removeRow = (index: number) => {
      setData((d) => {
        const list = [...((getPath(d, dp) as Row[]) || [])];
        list.splice(index, 1);
        return setPath(d, dp, list);
      });
    };

    return (
      <section className="rounded-xl border border-surface-border bg-surface-raised/60 p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-surface-muted">
            Tabelle ({dp})
          </span>
          {!readOnly ? (
            <button
              type="button"
              className="rounded-md bg-sky-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500"
              onClick={addRow}
            >
              Zeile +
            </button>
          ) : null}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-surface-border text-surface-muted">
                {cols.map((c) => (
                  <th key={c.field} className="px-2 py-2 font-medium">
                    {c.label || c.field}
                  </th>
                ))}
                {!readOnly ? <th className="w-10 px-2 py-2" /> : null}
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td
                    colSpan={cols.length + (readOnly ? 0 : 1)}
                    className="px-2 py-6 text-center text-surface-muted"
                  >
                    {readOnly ? "Noch keine Einträge." : "Noch keine Zeilen — „Zeile +“."}
                  </td>
                </tr>
              ) : (
                rows.map((row, ri) => (
                  <tr key={String(row.id ?? ri)} className="border-b border-white/5">
                    {cols.map((c) => (
                      <td key={c.field} className="px-2 py-1 align-middle">
                        <CellInput
                          col={c}
                          value={row[c.field]}
                          readOnly={readOnly}
                          onChange={(v) => updateRow(ri, c.field, v)}
                        />
                      </td>
                    ))}
                    {!readOnly ? (
                      <td className="px-1">
                        <button
                          type="button"
                          className="rounded p-1 text-xs text-red-400 hover:bg-white/5"
                          onClick={() => removeRow(ri)}
                          title="Zeile löschen"
                        >
                          ✕
                        </button>
                      </td>
                    ) : null}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    );
  }

  return (
    <p className="text-sm text-amber-200/90">
      Unbekannter Block-Typ: {(block as UiBlock).type}
    </p>
  );
}

function CellInput(props: {
  col: { field: string; kind: string; options?: string[] };
  value: unknown;
  readOnly?: boolean;
  onChange: (v: unknown) => void;
}) {
  const { col, value, readOnly = false, onChange } = props;
  if (col.kind === "checkbox") {
    return (
      <input
        type="checkbox"
        disabled={readOnly}
        className="h-4 w-4 rounded border-surface-border disabled:cursor-not-allowed disabled:opacity-60"
        checked={Boolean(value)}
        onChange={(e) => onChange(e.target.checked)}
      />
    );
  }
  if (col.kind === "number") {
    return (
      <input
        type="number"
        readOnly={readOnly}
        className="w-full min-w-[4rem] rounded border border-surface-border bg-black/30 px-2 py-1 text-neutral-100 read-only:cursor-default read-only:opacity-90"
        value={typeof value === "number" ? value : Number(value) || 0}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    );
  }
  if (col.kind === "select" && col.options?.length) {
    return (
      <select
        disabled={readOnly}
        className="w-full rounded border border-surface-border bg-black/30 px-2 py-1 text-neutral-100 disabled:cursor-not-allowed disabled:opacity-60"
        value={String(value ?? "")}
        onChange={(e) => onChange(e.target.value)}
      >
        {col.options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    );
  }
  return (
    <input
      type="text"
      readOnly={readOnly}
      className="w-full rounded border border-surface-border bg-black/30 px-2 py-1 text-neutral-100 read-only:cursor-default read-only:opacity-90"
      value={value == null ? "" : String(value)}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
