import type { ChangeEvent, Dispatch, SetStateAction } from "react";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";
import type { UiBlock, UiLayout } from "./types";

/** Supports top-level keys (`pets`) and dotted paths (`albums.0.photos`) for nested albums. */
function getPath(obj: Record<string, unknown>, path: string): unknown {
  if (!path.includes(".")) {
    return obj[path];
  }
  const segs = path.split(".").filter(Boolean);
  let cur: unknown = obj;
  for (const seg of segs) {
    if (cur === null || cur === undefined) return undefined;
    if (Array.isArray(cur)) {
      const i = Number(seg);
      if (!Number.isInteger(i) || i < 0 || i >= cur.length) return undefined;
      cur = cur[i];
    } else if (typeof cur === "object") {
      cur = (cur as Record<string, unknown>)[seg];
    } else {
      return undefined;
    }
  }
  return cur;
}

function setPath(
  obj: Record<string, unknown>,
  path: string,
  value: unknown
): Record<string, unknown> {
  if (!path.includes(".")) {
    return { ...obj, [path]: value };
  }
  const segs = path.split(".").filter(Boolean);
  const [head, ...tail] = segs;
  const tailPath = tail.join(".");
  const raw = obj[head];

  if (Array.isArray(raw)) {
    const idx = Number(tail[0]);
    if (!Number.isInteger(idx) || idx < 0) {
      return { ...obj, [head]: value };
    }
    const arr = [...raw];
    if (tail.length === 1) {
      arr[idx] = value;
      return { ...obj, [head]: arr };
    }
    const elem = arr[idx];
    const inner =
      elem !== null && typeof elem === "object" && !Array.isArray(elem)
        ? { ...(elem as Record<string, unknown>) }
        : {};
    arr[idx] = setPath(inner, tail.slice(1).join("."), value);
    return { ...obj, [head]: arr };
  }

  const child =
    raw !== null && typeof raw === "object" && !Array.isArray(raw)
      ? { ...(raw as Record<string, unknown>) }
      : {};
  return { ...obj, [head]: setPath(child, tailPath, value) };
}

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

function BlockView(props: {
  block: UiBlock;
  data: Record<string, unknown>;
  setData: Dispatch<SetStateAction<Record<string, unknown>>>;
  workspaceId: string | null;
  readOnly: boolean;
}) {
  const { block, data, setData, workspaceId, readOnly } = props;
  const dp = block.props.dataPath || "";

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
