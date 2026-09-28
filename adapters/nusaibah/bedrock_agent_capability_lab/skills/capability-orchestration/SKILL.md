---
name: capability-orchestration
description: Provide deterministic orchestration guidance for the local capability lab.
---

# Capability Orchestration

Use only the validated execution plan supplied by the consuming adapter or agent.

Process steps in declared sequence order.

Do not invent capabilities, roles, providers, tools, or execution steps that are not present in the validated plan.

Treat required steps as mandatory orchestration intent.

Do not access credentials, storage, network endpoints, provider SDKs, OBS, DLM Core, or MCP directly.

Do not execute a capability merely because it appears in the plan. Actual capability execution must occur only through an admitted runtime helper supplied by the trusted runtime.

Return only safe orchestration guidance derived from the validated plan.