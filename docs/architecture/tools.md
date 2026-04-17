---
doc_id: architecture-tools
domain: agentlayer_docs
tags: [architecture, tools, registry]
---

## What it is

Tools are Python modules loaded from disk and exposed to the chat model in an Ollama/OpenAI-compatible `tools` schema.

## Where it lives

- Registry: `src/domain/plugin_system/registry.py`
- Planner loop: `src/domain/agent.py`
- Executor: `src/domain/tool_executor.py`
- Tool runtime/policy: `src/domain/plugin_system/tools.py`

Tool packages live under:

- `tools/agent/core/`
- `tools/agent/productivity/`
- `tools/agent/knowledge/`
- `tools/agent/external/`
- `tools/agent/domains/`

## Tool package contract

Each tool package exports:

- `__version__`
- `TOOL_ID`, `TOOL_DOMAIN`, `TOOL_LABEL`, `TOOL_DESCRIPTION`
- `TOOL_TRIGGERS` (keywords)
- `TOOL_CAPABILITIES` (capability strings, see ADR 0002)
- `HANDLERS`: mapping `tool_name -> callable`
- `TOOLS`: list of OpenAI-style tool specs

Examples:

- `tools/agent/knowledge/kb/kb.py`
- `tools/agent/knowledge/rag/rag.py`
- `tools/agent/knowledge/memory/memory.py`

## Capabilities (routing + governance)

- Convention: `docs/adr/0002-tool-capabilities-convention.md`
- Governance gates: `docs/adr/0003-capability-governance.md`

### Client hints (optional)

The chat request may include `agent_capability_hints` to narrow the tools forwarded to the model.

## Execution model

- **Planner** decides tool calls.
- **Executor** runs tool calls deterministically and returns JSON strings back into the loop.

This avoids “LLM side effects”: tools are audited and can be gated centrally.

