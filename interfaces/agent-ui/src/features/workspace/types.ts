export type BlockType = "table" | "markdown" | "gallery";

export interface GridPos {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface ColumnDef {
  field: string;
  kind: "checkbox" | "text" | "number" | "select";
  label: string;
  options?: string[];
}

export interface UiBlock {
  id: string;
  type: BlockType;
  grid: GridPos;
  props: {
    dataPath?: string;
    columns?: ColumnDef[];
    placeholder?: string;
    /** gallery block */
    title?: string;
  };
}

export interface UiLayout {
  version: number;
  blocks: UiBlock[];
}

export interface WorkspaceSummary {
  id: string;
  kind: string;
  title: string;
  updated_at: string;
  created_at: string;
}

export interface WorkspaceDetail extends WorkspaceSummary {
  ui_layout: UiLayout | Record<string, unknown>;
  data: Record<string, unknown>;
}
