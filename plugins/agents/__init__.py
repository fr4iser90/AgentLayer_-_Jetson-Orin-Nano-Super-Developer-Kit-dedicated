"""Agent plugins - plug & play agents for AgentLayer."""

import sys
from pathlib import Path

_plugins_dir = Path(__file__).parent.parent
if str(_plugins_dir) not in sys.path:
    sys.path.insert(0, str(_plugins_dir))

from plugins.agents.registry import AgentRegistry, get_agent_registry

__all__ = ["AgentRegistry", "get_agent_registry"]