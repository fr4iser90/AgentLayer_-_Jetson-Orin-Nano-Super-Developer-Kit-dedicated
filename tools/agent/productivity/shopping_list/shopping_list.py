"""Agent tools for ``kind: shopping_list`` workspaces — list, read, items, preferences, price log."""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from src.domain.identity import get_identity
from src.workspace import db as workspace_db

__version__ = "1.1.0"
TOOL_ID = "shopping_list"
TOOL_BUCKET = "productivity"
TOOL_DOMAIN = "shopping"
TOOL_LABEL = "Shopping list"
TOOL_DESCRIPTION = (
    "Read and update shopping list workspaces (kind shopping_list): lists, items, notes, "
    "store/brand preferences (data.preferences), and append-only price snapshots (data.price_log). "
    "Does not fetch live prices from the internet — use for stored prefs and documented research. "
    "If the system prompt includes [Workspace context] with a workspace_id, use that id for "
    "'this list' unless the user clearly names another. Otherwise call shopping_list_workspaces first "
    "when which list is unclear."
)
TOOL_TRIGGERS = (
    "shopping",
    "einkauf",
    "einkaufsliste",
    "shopping list",
    "groceries",
    "liste",
)
TOOL_CAPABILITIES = ("workspace.shopping.read", "workspace.shopping.write")

_MAX_ITEMS = 500
_MAX_BATCH = 40
_MAX_NAME_LEN = 400


def _err(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg}, ensure_ascii=False)


def _parse_uuid(raw: str | None) -> uuid.UUID | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


def _identity() -> tuple[int, uuid.UUID] | None:
    tid, uid = get_identity()
    if uid is None:
        return None
    return (tid, uid)


def _ensure_shopping(ws: dict[str, Any]) -> str | None:
    if (ws.get("kind") or "").strip() != "shopping_list":
        return "workspace is not a shopping_list kind"
    return None


def _normalize_row(entry: dict[str, Any]) -> dict[str, Any] | None:
    name = (entry.get("name") or "").strip()
    if not name:
        return None
    if len(name) > _MAX_NAME_LEN:
        name = name[:_MAX_NAME_LEN]
    qty_raw = entry.get("qty")
    if qty_raw is None or qty_raw == "":
        qty: float | int = 1
    else:
        try:
            q = float(qty_raw)
            qty = int(q) if q == int(q) else round(q, 3)
        except (TypeError, ValueError):
            qty = 1
    store = (entry.get("store") or "").strip() or "—"
    if len(store) > 120:
        store = store[:120]
    return {
        "id": str(uuid.uuid4()),
        "checked": bool(entry.get("checked", False)),
        "name": name,
        "qty": qty,
        "store": store,
    }


def shopping_list_workspaces(arguments: dict[str, Any]) -> str:
    """List shopping_list workspaces for the current user."""
    del arguments
    ident = _identity()
    if ident is None:
        return _err("No user identity — shopping list tools need an authenticated chat user.")
    tid, uid = ident
    rows = workspace_db.workspace_list(uid, tid, limit=200)
    out = [{"id": r["id"], "title": r["title"]} for r in rows if (r.get("kind") == "shopping_list")]
    return json.dumps({"ok": True, "workspaces": out}, ensure_ascii=False)


def shopping_list_read(arguments: dict[str, Any]) -> str:
    """Return items and notes for one shopping list workspace."""
    wid = _parse_uuid(arguments.get("workspace_id"))
    if wid is None:
        return _err("workspace_id must be a valid UUID")

    ident = _identity()
    if ident is None:
        return _err("No user identity — shopping list tools need an authenticated chat user.")
    tid, uid = ident

    ws = workspace_db.workspace_get(uid, tid, wid)
    if ws is None:
        return _err("workspace not found or no access")
    bad = _ensure_shopping(ws)
    if bad:
        return _err(bad)

    data = ws.get("data") if isinstance(ws.get("data"), dict) else {}
    items = data.get("items")
    if not isinstance(items, list):
        items = []
    notes = data.get("notes")
    if not isinstance(notes, str):
        notes = ""
    pref = data.get("preferences")
    if not isinstance(pref, dict):
        pref = {}
    plog = data.get("price_log")
    if not isinstance(plog, list):
        plog = []

    return json.dumps(
        {
            "ok": True,
            "workspace_id": str(wid),
            "title": ws.get("title") or "",
            "items": items,
            "notes": notes,
            "preferences": pref,
            "price_log": plog,
        },
        ensure_ascii=False,
    )


def shopping_list_add_items(arguments: dict[str, Any]) -> str:
    """Append items to a shopping_list workspace."""
    wid = _parse_uuid(arguments.get("workspace_id"))
    if wid is None:
        return _err("workspace_id must be a valid UUID")

    raw_items = arguments.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return _err("items must be a non-empty array of {name, qty?, store?}")

    ident = _identity()
    if ident is None:
        return _err("No user identity — shopping list tools need an authenticated chat user.")
    tid, uid = ident

    ws = workspace_db.workspace_get(uid, tid, wid)
    if ws is None:
        return _err("workspace not found or no access")
    bad = _ensure_shopping(ws)
    if bad:
        return _err(bad)

    data = dict(ws.get("data")) if isinstance(ws.get("data"), dict) else {}
    cur = data.get("items")
    if not isinstance(cur, list):
        cur = []
    if len(cur) >= _MAX_ITEMS:
        return _err(f"list already has max {_MAX_ITEMS} items — remove or archive rows in the UI first")

    new_rows: list[dict[str, Any]] = []
    for entry in raw_items[:_MAX_BATCH]:
        if not isinstance(entry, dict):
            continue
        row = _normalize_row(entry)
        if row:
            new_rows.append(row)
    if not new_rows:
        return _err("no valid items — each needs a non-empty name")

    if len(cur) + len(new_rows) > _MAX_ITEMS:
        return _err(
            f"would exceed {_MAX_ITEMS} items — add fewer items or trim the list first"
        )

    merged = list(cur) + new_rows
    data["items"] = merged
    if "notes" not in data:
        data["notes"] = ""

    updated = workspace_db.workspace_update(uid, tid, wid, data=data)
    if updated is None:
        return _err("could not update workspace (viewer role or conflict)")

    return json.dumps(
        {
            "ok": True,
            "workspace_id": str(wid),
            "added": len(new_rows),
            "items_count": len(merged),
        },
        ensure_ascii=False,
    )


HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "shopping_list_workspaces": shopping_list_workspaces,
    "shopping_list_read": shopping_list_read,
    "shopping_list_add_items": shopping_list_add_items,
}

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "shopping_list_workspaces",
            "TOOL_DESCRIPTION": (
                "List shopping list workspaces the user can open (kind shopping_list). "
                "Call when which list is unclear and there is no [Workspace context] workspace_id, "
                "or the user may mean a list other than the default context."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shopping_list_read",
            "TOOL_DESCRIPTION": (
                "Read the current items and markdown notes for one shopping list workspace. "
                "Use workspace_id from [Workspace context] in the system prompt when present, else "
                "from shopping_list_workspaces."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "TOOL_DESCRIPTION": "UUID of the shopping_list workspace",
                    },
                },
                "required": ["workspace_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shopping_list_add_items",
            "TOOL_DESCRIPTION": (
                "Add one or more rows to a shopping list (name, optional qty, optional store). "
                "Prefer workspace_id from [Workspace context] when present; otherwise shopping_list_workspaces."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "TOOL_DESCRIPTION": "UUID of the shopping_list workspace",
                    },
                    "items": {
                        "type": "array",
                        "TOOL_DESCRIPTION": "Objects with name (required), optional qty (number), optional store (string)",
                        "items": {"type": "object"},
                    },
                },
                "required": ["workspace_id", "items"],
            },
        },
    },
]
