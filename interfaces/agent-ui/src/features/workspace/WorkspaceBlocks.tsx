import type { Dispatch, SetStateAction } from "react";
import type { UiBlock, UiLayout } from "./types";

function getPath(obj: Record<string, unknown>, path: string): unknown {
  return obj[path];
}

function setPath(
  obj: Record<string, unknown>,
  path: string,
  value: unknown
): Record<string, unknown> {
  return { ...obj, [path]: value };
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
    return (
      <p className="text-sm text-surface-muted">
        Keine Blöcke in ui_layout.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {uiLayout.blocks.map((block) => (
        <BlockView key={block.id} block={block} data={data} setData={setData} />
      ))}
    </div>
  );
}

function BlockView(props: {
  block: UiBlock;
  data: Record<string, unknown>;
  setData: Dispatch<SetStateAction<Record<string, unknown>>>;
}) {
  const { block, data, setData } = props;
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
          className="min-h-[120px] w-full resize-y rounded-lg border border-surface-border bg-black/30 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-sky-500/50"
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
    const rowsUnknown = dp ? getPath(data, dp) : [];
    const photos: Row[] = Array.isArray(rowsUnknown)
      ? (rowsUnknown as Row[])
      : [];
    const sectionTitle = block.props.title || "Fotos";

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
          <button
            type="button"
            className="rounded-md bg-violet-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-violet-500"
            onClick={addPhoto}
          >
            Foto +
          </button>
        </div>
        {photos.length === 0 ? (
          <p className="rounded-lg border border-dashed border-white/15 py-10 text-center text-sm text-surface-muted">
            Noch keine Einträge — Bild-URL und optional Beschriftung hinzufügen.
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {photos.map((row, ri) => {
              const url = String(row.url ?? "").trim();
              return (
                <div
                  key={String(row.id ?? ri)}
                  className="overflow-hidden rounded-xl border border-surface-border bg-black/25 shadow-sm"
                >
                  <div className="aspect-video bg-gradient-to-br from-white/5 to-black/40">
                    {url ? (
                      <img
                        src={url}
                        alt={String(row.caption ?? "")}
                        className="h-full w-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = "none";
                        }}
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center text-xs text-surface-muted">
                        URL eintragen
                      </div>
                    )}
                  </div>
                  <div className="space-y-2 p-3">
                    <input
                      type="url"
                      placeholder="https://…"
                      className="w-full rounded-md border border-surface-border bg-black/40 px-2 py-1.5 text-xs text-neutral-100 placeholder:text-white/25"
                      value={url}
                      onChange={(e) => updatePhoto(ri, "url", e.target.value)}
                    />
                    <input
                      type="text"
                      placeholder="Beschriftung"
                      className="w-full rounded-md border border-surface-border bg-black/40 px-2 py-1.5 text-xs text-neutral-100"
                      value={String(row.caption ?? "")}
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
            })}
          </div>
        )}
      </section>
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
          <button
            type="button"
            className="rounded-md bg-sky-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500"
            onClick={addRow}
          >
            Zeile +
          </button>
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
                <th className="w-10 px-2 py-2" />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td
                    colSpan={cols.length + 1}
                    className="px-2 py-6 text-center text-surface-muted"
                  >
                    Noch keine Zeilen — „Zeile +“.
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
                          onChange={(v) => updateRow(ri, c.field, v)}
                        />
                      </td>
                    ))}
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
  onChange: (v: unknown) => void;
}) {
  const { col, value, onChange } = props;
  if (col.kind === "checkbox") {
    return (
      <input
        type="checkbox"
        className="h-4 w-4 rounded border-surface-border"
        checked={Boolean(value)}
        onChange={(e) => onChange(e.target.checked)}
      />
    );
  }
  if (col.kind === "number") {
    return (
      <input
        type="number"
        className="w-full min-w-[4rem] rounded border border-surface-border bg-black/30 px-2 py-1 text-neutral-100"
        value={typeof value === "number" ? value : Number(value) || 0}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    );
  }
  if (col.kind === "select" && col.options?.length) {
    return (
      <select
        className="w-full rounded border border-surface-border bg-black/30 px-2 py-1 text-neutral-100"
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
      className="w-full rounded border border-surface-border bg-black/30 px-2 py-1 text-neutral-100"
      value={value == null ? "" : String(value)}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
