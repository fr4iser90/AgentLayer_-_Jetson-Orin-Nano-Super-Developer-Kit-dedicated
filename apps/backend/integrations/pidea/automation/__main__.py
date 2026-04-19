"""``python -m apps.integrations.pidea.automation`` → CLI."""

from __future__ import annotations

import sys

from apps.backend.integrations.pidea.automation.cli import main

if __name__ == "__main__":
    sys.exit(main())
