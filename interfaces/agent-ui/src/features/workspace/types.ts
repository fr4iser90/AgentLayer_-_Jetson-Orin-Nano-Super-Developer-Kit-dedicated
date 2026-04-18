export type BlockType =
  | "table"
  | "markdown"
  | "gallery"
  | "hero"
  | "timeline"
  | "stat"
  | "chart"
  | "sparkline"
  | "kanban"
  | "rich_markdown"
  | "embed";

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
    /** gallery / hero section label */
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
  /** owner | editor | viewer — absent on older APIs (treat as owner) */
  access_role?: string;
}

/** Reserved namespace inside workspace ``data`` (JSON). Safe alongside template-specific keys. */
export type WorkspaceDataAgentlayer = {
  /** Appended to the server system prompt when this workspace is active (embedded + API with context). */
  system_prompt_extra?: string;
  /** Alias for ``system_prompt_extra`` (same behavior). */
  instructions?: string;
  /**
   * If non-empty: only these OpenAI tool function names are forwarded for this workspace
   * (after routing/policy/client disabled-tools). Empty/unset = no extra restriction.
   */
  tool_allowlist?: string[];
  /** Alias for ``tool_allowlist``. */
  allowed_tools?: string[];
};

export interface WorkspaceDetail extends WorkspaceSummary {
  ui_layout: UiLayout | Record<string, unknown>;
  /** Template payload; may include ``_agentlayer`` for AgentLayer agent settings. */
  data: Record<string, unknown>;
}

export interface WorkspaceMemberRow {
  user_id: string;
  email: string;
  role: string;
  created_at: string | null;
}
