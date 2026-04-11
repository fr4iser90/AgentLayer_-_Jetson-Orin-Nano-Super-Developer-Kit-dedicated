# ADR 0003: Capability governance (allow / block / confirm)

## Context

Tools declare capability strings (`TOOL_CAPABILITIES`, ADR 0002). Operators need deterministic control before execution, independent of the LLM.

## Decision

At `run_tool` time (`src/domain/plugin_system/tools.py`), after operator enablement and role/tenant policy:

1. **`AGENT_CAPABILITY_GATE_BLOCK`** — if the tool’s effective capabilities intersect this set → deny (`code: capability_blocked`).
2. **`AGENT_CAPABILITY_GATE_ALLOW`** — if non-empty: the tool must declare at least one capability in the allowlist; tools with no declared capabilities are denied (`capability_unclassified`); if none match → `capability_not_allowed`.
3. **`AGENT_CAPABILITY_GATE_CONFIRM`** — if the tool’s capabilities intersect this set, the caller must affirm those capability ids via:
   - Chat body `agent_capability_confirm`, or
   - Header `X-Agent-Capability-Confirm` on direct tool HTTP routes (merged with body on `POST /tools/run`).

All three env vars are comma-separated lists, compared case-insensitively. User-supplied confirm tokens are normalized to lowercase in `parse_user_capability_confirm`.

If all three are empty, the gate is a no-op (backward compatible).

## Consequences

- Central enforcement without changing individual tools.
- “YOLO” tool use is bounded when an allowlist or confirm list is configured.
- Clients that call tools outside the chat loop must send the confirm header when `AGENT_CAPABILITY_GATE_CONFIRM` applies.
