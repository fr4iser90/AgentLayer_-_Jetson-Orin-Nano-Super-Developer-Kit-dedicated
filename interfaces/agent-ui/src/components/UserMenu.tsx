import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const email = user?.email ?? "";
  const initial = (email.split("@")[0]?.[0] ?? user?.email?.[0] ?? "?").toUpperCase();
  const isAdmin = user?.role?.toLowerCase() === "admin";

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className="flex h-9 w-9 items-center justify-center rounded-full bg-orange-500/90 text-sm font-medium text-black outline-none ring-sky-500/40 hover:bg-orange-400 focus-visible:ring-2"
        aria-expanded={open}
        aria-haspopup="menu"
        title={email || "Account"}
        onClick={() => setOpen((v) => !v)}
      >
        {initial}
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-1 min-w-[12rem] rounded-lg border border-surface-border bg-[#1a1a1a] py-1 shadow-xl"
        >
          {email ? (
            <p className="truncate border-b border-white/10 px-3 py-2 text-xs text-surface-muted" title={email}>
              {email}
            </p>
          ) : null}
          <Link
            role="menuitem"
            to="/settings"
            className="block px-3 py-2 text-sm text-neutral-200 hover:bg-white/10"
            onClick={() => setOpen(false)}
          >
            Settings
          </Link>
          {isAdmin ? (
            <Link
              role="menuitem"
              to="/admin"
              className="block px-3 py-2 text-sm text-neutral-200 hover:bg-white/10"
              onClick={() => setOpen(false)}
            >
              Admin
            </Link>
          ) : null}
          <button
            type="button"
            role="menuitem"
            className="w-full px-3 py-2 text-left text-sm text-surface-muted hover:bg-white/10 hover:text-neutral-200"
            onClick={() => {
              setOpen(false);
              void logout();
            }}
          >
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
