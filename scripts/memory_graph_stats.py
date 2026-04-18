#!/usr/bin/env python3
"""GET /v1/user/memory/graph/stats — quick diagnostics (requires Bearer).

Environment:
  AGENT_BASE_URL   default http://127.0.0.1:8088
  AGENT_BEARER     JWT or API key (same as Web UI / API client)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    base = (os.environ.get("AGENT_BASE_URL") or "http://127.0.0.1:8088").rstrip("/")
    token = (os.environ.get("AGENT_BEARER") or "").strip()
    if not token:
        print("AGENT_BEARER is required", file=sys.stderr)
        return 1
    url = f"{base}/v1/user/memory/graph/stats"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        # nosec B310: operator script; URL is AGENT_BASE_URL + fixed API path (http/https only), not user file://
        with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(str(e.reason if hasattr(e, "reason") else e), file=sys.stderr)
        return 1
    print(json.dumps(json.loads(raw), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
