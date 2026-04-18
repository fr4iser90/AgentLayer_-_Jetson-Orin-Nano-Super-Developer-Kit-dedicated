#!/usr/bin/env python3
"""
POST /v1/admin/rag/ingest-docs with an admin Bearer token.

Environment:
  AGENT_BASE_URL   Base URL (default http://127.0.0.1:8088)
  AGENT_ADMIN_TOKEN JWT or API key for a user with role=admin

Optional JSON overrides (same keys as the HTTP body):
  AGENT_INGEST_DOCS_JSON  e.g. {"docs_root":"/path/to/docs","purge_first":true}
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    base = (os.environ.get("AGENT_BASE_URL") or "http://127.0.0.1:8088").rstrip("/")
    token = (os.environ.get("AGENT_ADMIN_TOKEN") or "").strip()
    if not token:
        print("AGENT_ADMIN_TOKEN is required", file=sys.stderr)
        return 1
    raw = (os.environ.get("AGENT_INGEST_DOCS_JSON") or "").strip()
    body: dict = {}
    if raw:
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"AGENT_INGEST_DOCS_JSON: {e}", file=sys.stderr)
            return 1
        if not isinstance(body, dict):
            print("AGENT_INGEST_DOCS_JSON must be a JSON object", file=sys.stderr)
            return 1

    url = f"{base}/v1/admin/rag/ingest-docs"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        # nosec B310: operator script; URL is AGENT_BASE_URL + fixed admin path (http/https only), not user file://
        with urllib.request.urlopen(req, timeout=600) as resp:  # nosec B310
            payload = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {err}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(str(e.reason if hasattr(e, "reason") else e), file=sys.stderr)
        return 1

    print(payload)
    try:
        j = json.loads(payload)
    except json.JSONDecodeError:
        return 0
    if isinstance(j, dict) and j.get("ok") is False:
        return 1
    if isinstance(j, dict) and j.get("errors"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
