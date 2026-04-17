import type { ReactNode } from "react";

export function WorkspaceSettingsDrawer(props: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const { open, title, onClose, children } = props;
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        aria-label="Close settings"
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-xl flex-col border-l border-surface-border bg-surface-raised shadow-xl">
        <div className="flex items-center justify-between gap-3 border-b border-surface-border px-4 py-3">
          <p className="min-w-0 truncate text-sm font-medium text-white">{title}</p>
          <button
            type="button"
            className="rounded-md px-2 py-1 text-xs text-surface-muted hover:bg-white/5 hover:text-neutral-200"
            onClick={onClose}
          >
            Close
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
      </aside>
    </div>
  );
}

