"""Agent Registry - dynamically loads agent plugins from configured directories."""

from __future__ import annotations

import importlib.util
import logging
import os
import threading
from pathlib import Path
from typing import Any

from apps.backend.core.config import config, PLUGINS_DIR

logger = logging.getLogger(__name__)

DEFAULT_AGENT_PLUGINS_DIR = PLUGINS_DIR / "agents"


class AgentRegistry:
    """Registry that loads agent plugins from Python files."""

    def __init__(self) -> None:
        self._agents: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self._lock = threading.Lock()

    def _load_agents(self) -> None:
        """Scan plugin directories and load all agent definitions."""
        plugins_dirs = self._get_plugins_dirs()
        seen_ids: set[str] = set()

        for plugins_dir in plugins_dirs:
            if not plugins_dir.is_dir():
                logger.warning("plugins directory not found: %s", plugins_dir)
                continue

            for py_file in plugins_dir.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue

                try:
                    self._load_agent_from_file(py_file, seen_ids)
                except Exception as e:
                    logger.warning("failed to load agent from %s: %s", py_file, e)

        if "general" not in self._agents:
            logger.warning("no general agent loaded, creating default")
            self._create_default_general_agent()

        logger.info("agent registry loaded: %d agents", len(self._agents))

    def _get_plugins_dirs(self) -> list[Path]:
        """Get list of directories to scan for agent plugins."""
        dirs = [DEFAULT_AGENT_PLUGINS_DIR]

        env_dirs = os.environ.get("AGENT_PLUGINS_DIR", "").strip()
        if env_dirs:
            for d in env_dirs.split(","):
                p = Path(d.strip())
                if p.is_dir():
                    dirs.append(p)

        return dirs

    def _load_agent_from_file(self, py_file: Path, seen_ids: set[str]) -> None:
        """Load agent definition from a Python file."""
        spec = importlib.util.spec_from_file_location(f"agent_{py_file.stem}", py_file)
        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        agent_id = getattr(module, "AGENT_ID", None)
        if not agent_id:
            logger.debug("no AGENT_ID found in %s", py_file.name)
            return

        if agent_id in seen_ids:
            logger.warning("duplicate agent_id %s in %s, skipping", agent_id, py_file.name)
            return

        seen_ids.add(agent_id)

        definition = {
            "id": agent_id,
            "name": getattr(module, "AGENT_NAME", agent_id),
            "icon": getattr(module, "AGENT_ICON", "🤖"),
            "description": getattr(module, "AGENT_DESCRIPTION", ""),
            "system_prompt": getattr(module, "AGENT_SYSTEM_PROMPT", ""),
            "tool_domain": getattr(module, "AGENT_TOOL_DOMAIN", None),
            "tool_names": getattr(module, "AGENT_TOOL_NAMES", []),
            "requires_workspace": getattr(module, "AGENT_REQUIRES_WORKSPACE", False),
            "execution_context": getattr(module, "AGENT_EXECUTION_CONTEXT", "auto"),
            "min_role": getattr(module, "AGENT_MIN_ROLE", "user"),
            "model_profile": getattr(module, "AGENT_MODEL_PROFILE", None),
        }

        self._agents[agent_id] = definition
        logger.debug("loaded agent: %s from %s", agent_id, py_file.name)

    def _create_default_general_agent(self) -> None:
        """Create a default general agent if none loaded."""
        self._agents["general"] = {
            "id": "general",
            "name": "General",
            "icon": "🧠",
            "description": "General purpose assistant",
            "system_prompt": "You are a helpful AI assistant.",
            "tool_domain": None,
            "tool_names": [],
            "requires_workspace": False,
            "execution_context": "auto",
            "min_role": "user",
            "model_profile": None,
        }

    def ensure_loaded(self) -> None:
        """Ensure agents are loaded (thread-safe, lazy loading)."""
        if self._loaded:
            return
        with self._lock:
            if not self._loaded:
                self._load_agents()
                self._loaded = True

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent definition by ID."""
        self.ensure_loaded()
        return self._agents.get(agent_id)

    def list_agents(self) -> list[dict[str, Any]]:
        """List all registered agents."""
        self.ensure_loaded()
        return list(self._agents.values())

    def agent_ids(self) -> list[str]:
        """List all agent IDs."""
        self.ensure_loaded()
        return list(self._agents.keys())

    def to_list_dict(self) -> list[dict[str, Any]]:
        """Return list of agent definitions as dicts (for API)."""
        self.ensure_loaded()
        return list(self._agents.values())


_agent_registry: AgentRegistry | None = None
_registry_lock = threading.Lock()


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry instance."""
    global _agent_registry
    if _agent_registry is None:
        with _registry_lock:
            if _agent_registry is None:
                _agent_registry = AgentRegistry()
    return _agent_registry