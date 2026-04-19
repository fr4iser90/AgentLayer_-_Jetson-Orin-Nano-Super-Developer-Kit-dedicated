"""
PIDEA runtime automation: productive IDE control via Playwright CDP.

Run::

    PYTHONPATH=src python -m apps.integrations.pidea.automation --help

Or use the ``scripts/pidea`` launcher from the repository root.

DOM diagnostics (validators, repair, snapshots) live in :mod:`apps.integrations.pidea.domkit`.
For backward compatibility, key :mod:`domkit` submodules are re-exported here.
"""

from __future__ import annotations

from apps.backend.integrations.pidea.automation import action_runner
from apps.backend.integrations.pidea.automation import chat_reader
from apps.backend.integrations.pidea.automation import cli
from apps.backend.integrations.pidea.automation import ui_navigator
from apps.backend.integrations.pidea.automation import workspace_reader
from apps.backend.integrations.pidea.domkit import dom_diff
from apps.backend.integrations.pidea.domkit import dom_snapshot
from apps.backend.integrations.pidea.domkit import models
from apps.backend.integrations.pidea.domkit import profile_generator
from apps.backend.integrations.pidea.domkit import selector_finder
from apps.backend.integrations.pidea.domkit import selector_loader
from apps.backend.integrations.pidea.domkit import selector_ranker
from apps.backend.integrations.pidea.domkit import selector_validator
from apps.backend.integrations.pidea.domkit import version_detector

__all__ = [
    "action_runner",
    "chat_reader",
    "cli",
    "dom_diff",
    "dom_snapshot",
    "models",
    "profile_generator",
    "selector_finder",
    "selector_loader",
    "selector_ranker",
    "selector_validator",
    "ui_navigator",
    "version_detector",
    "workspace_reader",
]
