"""Base definitions for agent plugins."""

from __future__ import annotations

from typing import Any, Literal

AgentExecutionContext = Literal["container", "host", "auto"]
AgentMinRole = Literal["admin", "user", "guest"]


class AgentDefinition:
    """Definition of an agent plugin."""

    __slots__ = (
        "id",
        "name",
        "icon",
        "description",
        "system_prompt",
        "tool_domain",
        "tool_names",
        "requires_workspace",
        "execution_context",
        "min_role",
        "model_profile",
    )

    def __init__(
        self,
        id: str,
        name: str,
        icon: str,
        description: str,
        system_prompt: str,
        tool_domain: str | None = None,
        tool_names: list[str] | None = None,
        requires_workspace: bool = False,
        execution_context: AgentExecutionContext = "auto",
        min_role: AgentMinRole = "user",
        model_profile: str | None = None,
    ):
        self.id = id
        self.name = name
        self.icon = icon
        self.description = description
        self.system_prompt = system_prompt
        self.tool_domain = tool_domain
        self.tool_names = tool_names or []
        self.requires_workspace = requires_workspace
        self.execution_context = execution_context
        self.min_role = min_role
        self.model_profile = model_profile

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "tool_domain": self.tool_domain,
            "tool_names": self.tool_names,
            "requires_workspace": self.requires_workspace,
            "execution_context": self.execution_context,
            "min_role": self.min_role,
            "model_profile": self.model_profile,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentDefinition:
        return cls(
            id=data["id"],
            name=data["name"],
            icon=data["icon"],
            description=data["description"],
            system_prompt=data["system_prompt"],
            tool_domain=data.get("tool_domain"),
            tool_names=data.get("tool_names", []),
            requires_workspace=data.get("requires_workspace", False),
            execution_context=data.get("execution_context", "auto"),
            min_role=data.get("min_role", "user"),
            model_profile=data.get("model_profile"),
        )


class AgentPluginMeta:
    """Metadata for an agent plugin module."""

    __slots__ = (
        "agent_id",
        "name",
        "icon",
        "description",
        "system_prompt",
        "tool_domain",
        "tool_names",
        "requires_workspace",
        "execution_context",
        "min_role",
        "model_profile",
    )

    def __init__(
        self,
        agent_id: str,
        name: str,
        icon: str,
        description: str,
        system_prompt: str,
        tool_domain: str | None = None,
        tool_names: list[str] | None = None,
        requires_workspace: bool = False,
        execution_context: AgentExecutionContext = "auto",
        min_role: AgentMinRole = "user",
        model_profile: str | None = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.icon = icon
        self.description = description
        self.system_prompt = system_prompt
        self.tool_domain = tool_domain
        self.tool_names = tool_names or []
        self.requires_workspace = requires_workspace
        self.execution_context = execution_context
        self.min_role = min_role
        self.model_profile = model_profile

    def to_definition(self) -> AgentDefinition:
        return AgentDefinition(
            id=self.agent_id,
            name=self.name,
            icon=self.icon,
            description=self.description,
            system_prompt=self.system_prompt,
            tool_domain=self.tool_domain,
            tool_names=self.tool_names,
            requires_workspace=self.requires_workspace,
            execution_context=self.execution_context,
            min_role=self.min_role,
            model_profile=self.model_profile,
        )


# Module-level agent metadata (set by plugin modules)
AGENT_META: AgentPluginMeta | None = None