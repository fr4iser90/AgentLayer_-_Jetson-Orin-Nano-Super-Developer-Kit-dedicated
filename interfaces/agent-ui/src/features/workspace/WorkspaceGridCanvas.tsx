import { useCallback, useMemo } from "react";
import type { Dispatch, SetStateAction } from "react";
import ReactGridLayout, {
  useContainerWidth,
  verticalCompactor,
  type Layout,
} from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

import type { BlockType, ColumnDef, UiBlock, UiLayout } from "./types";
import { WorkspaceBlockTile } from "./WorkspaceBlocks";

function newBlockId(): string {
  return `blk_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function usedDataPaths(blocks: UiBlock[]): Set<string> {
  const s = new Set<string>();
  for (const b of blocks) {
    const p = b.props.dataPath?.trim();
    if (p) s.add(p);
  }
  return s;
}

function uniqueDataPath(prefix: string, blocks: UiBlock[], data: Record<string, unknown>): string {
  const used = usedDataPaths(blocks);
  for (const k of Object.keys(data)) used.add(k);
  for (let i = 0; i < 80; i++) {
    const p = `${prefix}_${Math.random().toString(36).slice(2, 8)}`;
    if (!used.has(p)) return p;
  }
  return `${prefix}_${Date.now()}`;
}

const defaultTableColumns: ColumnDef[] = [
  { field: "done", kind: "checkbox", label: "" },
  { field: "name", kind: "text", label: "Item" },
];

function makeBlock(type: BlockType, dp: string, y: number): UiBlock {
  const grid = { x: 0, y, w: 6, h: 6 };
  if (type === "table") {
    return {
      id: newBlockId(),
      type: "table",
      grid,
      props: { dataPath: dp, columns: [...defaultTableColumns] },
    };
  }
  if (type === "markdown") {
    return {
      id: newBlockId(),
      type: "markdown",
      grid,
      props: { dataPath: dp, placeholder: "Notes" },
    };
  }
  return {
    id: newBlockId(),
    type: "gallery",
    grid,
    props: { dataPath: dp, title: "Photos" },
  };
}

function layoutFromBlocks(blocks: UiBlock[], editMode: boolean): Layout {
  return blocks.map((b) => ({
    i: b.id,
    x: Math.min(11, Math.max(0, b.grid.x)),
    y: Math.max(0, b.grid.y),
    w: Math.min(12, Math.max(2, b.grid.w)),
    h: Math.max(3, b.grid.h),
    static: !editMode,
    minW: 2,
    minH: 3,
    maxW: 12,
  }));
}

function mergeRglIntoBlocks(prev: UiLayout, rgl: Layout): UiLayout {
  const pos = new Map(rgl.map((it) => [it.i, it]));
  return {
    version: 1,
    blocks: prev.blocks.map((b) => {
      const L = pos.get(b.id);
      if (!L) return b;
      return {
        ...b,
        grid: { x: L.x, y: L.y, w: L.w, h: L.h },
      };
    }),
  };
}

export function WorkspaceGridCanvas(props: {
  layout: UiLayout;
  setLayout: Dispatch<SetStateAction<UiLayout>>;
  data: Record<string, unknown>;
  setData: Dispatch<SetStateAction<Record<string, unknown>>>;
  editMode: boolean;
  /** When true, table/markdown/gallery cells are not editable (layout may still use editMode for owner/editor). */
  contentReadOnly?: boolean;
  workspaceId?: string | null;
}) {
  const { layout, setLayout, data, setData, editMode, contentReadOnly = false, workspaceId } = props;
  const { width, containerRef, mounted } = useContainerWidth();

  const rglLayout = useMemo(
    () => layoutFromBlocks(layout.blocks, editMode),
    [layout.blocks, editMode]
  );

  const onLayoutChange = useCallback(
    (next: Layout) => {
      if (!editMode) return;
      setLayout((prev) => mergeRglIntoBlocks(prev, next));
    },
    [editMode, setLayout]
  );

  const addBlock = useCallback(
    (type: BlockType) => {
      const prefix = type === "table" ? "items" : type === "markdown" ? "notes" : "photos";
      const dp = uniqueDataPath(prefix, layout.blocks, data);
      const y =
        layout.blocks.length === 0
          ? 0
          : layout.blocks.reduce((m, b) => Math.max(m, b.grid.y + b.grid.h), 0);
      const block = makeBlock(type, dp, y);
      setLayout((prev) => ({ version: 1, blocks: [...prev.blocks, block] }));
      setData((d) => {
        const n = { ...d };
        if (type === "table" || type === "gallery") n[dp] = [];
        else n[dp] = "";
        return n;
      });
    },
    [layout.blocks, data, setLayout, setData]
  );

  const removeBlock = useCallback(
    (id: string) => {
      const b = layout.blocks.find((x) => x.id === id);
      const dp = b?.props?.dataPath;
      setLayout((prev) => ({
        version: 1,
        blocks: prev.blocks.filter((x) => x.id !== id),
      }));
      if (dp && !dp.includes(".")) {
        setData((d) => {
          const n = { ...d };
          delete n[dp];
          return n;
        });
      }
    },
    [layout.blocks, setLayout, setData]
  );

  if (!layout.blocks.length) {
    return (
      <div className="space-y-3">
        {editMode ? (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="workspace-grid-no-drag rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500"
              onClick={() => addBlock("table")}
            >
              + List
            </button>
            <button
              type="button"
              className="workspace-grid-no-drag rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500"
              onClick={() => addBlock("markdown")}
            >
              + Notes
            </button>
            <button
              type="button"
              className="workspace-grid-no-drag rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500"
              onClick={() => addBlock("gallery")}
            >
              + Photos
            </button>
          </div>
        ) : null}
        <p className="text-sm text-surface-muted">No blocks in this layout.</p>
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-3">
      {editMode ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="workspace-grid-no-drag rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500"
            onClick={() => addBlock("table")}
          >
            + List
          </button>
          <button
            type="button"
            className="workspace-grid-no-drag rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500"
            onClick={() => addBlock("markdown")}
          >
            + Notes
          </button>
          <button
            type="button"
            className="workspace-grid-no-drag rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500"
            onClick={() => addBlock("gallery")}
          >
            + Photos
          </button>
        </div>
      ) : null}

      <div ref={containerRef} className="min-h-[200px] min-w-0">
        {mounted && width > 0 ? (
          <ReactGridLayout
            width={width}
            layout={rglLayout}
            gridConfig={{ cols: 12, rowHeight: 44, margin: [8, 8], containerPadding: [4, 4] }}
            dragConfig={{
              enabled: editMode,
              bounded: true,
              cancel: ".workspace-grid-no-drag",
              threshold: 4,
            }}
            resizeConfig={{
              enabled: editMode,
              handles: ["se", "sw", "ne", "nw", "e", "w", "n", "s"],
            }}
            compactor={verticalCompactor}
            onLayoutChange={onLayoutChange}
          >
            {layout.blocks.map((b) => (
              <div
                key={b.id}
                className="overflow-hidden rounded-xl border border-surface-border bg-surface-raised/90 shadow-sm"
              >
                <div className="flex max-h-[min(520px,65vh)] flex-col overflow-auto">
                  {editMode ? (
                    <div className="sticky top-0 z-10 flex justify-end border-b border-white/5 bg-surface-raised/95 px-1 py-1">
                      <button
                        type="button"
                        className="workspace-grid-no-drag rounded px-2 py-0.5 text-xs text-red-300 hover:bg-red-950/50"
                        onClick={() => removeBlock(b.id)}
                      >
                        Remove
                      </button>
                    </div>
                  ) : null}
                  <div className="min-h-0 flex-1 p-2">
                    <WorkspaceBlockTile
                      block={b}
                      data={data}
                      setData={setData}
                      readOnly={contentReadOnly}
                      workspaceId={workspaceId ?? null}
                    />
                  </div>
                </div>
              </div>
            ))}
          </ReactGridLayout>
        ) : null}
      </div>
    </div>
  );
}
