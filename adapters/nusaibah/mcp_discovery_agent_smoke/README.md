# MCP discovery Agent smoke — development only

`nusaibah.mcp_discovery_agent_smoke@0.1.2` performs one declared callable read and
one declared Agent summary. It follows the pharma evaluation asset's ownership
pattern: Python makes the child call, the Agent receives a bounded packet, and
Python validates the Agent's result before returning success.

The child is pinned to `nusaibah.abstract_mcp_dlm@0.1.1`; it retains ownership of
discovery, spelling suggestions, scope validation and the three runtime tools.
The Agent receives only response count and resolution/confirmation flags. It
does not receive lake names, identifiers, search text, credentials or tool rights.
The count describes returned records, never the total authorized inventory.

Input: optional `variables.q`. The development server prepares the child's
required `tool_request` as `{"operation":"lakes.list","page_size":5}`. The parent
passes the fixed five-record page size and its bounded query variable. Operation, identifiers, authority and
runtime settings cannot come from those variables. A spelling suggestion remains
unconfirmed; this asset performs no dependent node read or selection.

Output: closed `smoke_result` with returned count, resolution state, confirmation
flag, bounded Agent summary and one child/one Agent call. Failed/malformed child
or Agent results fail; an actual empty read remains successful. The summary is
Agent-authored text and is not proof of complete search coverage.

## Development evidence and delivery limits

The Assets development harness provides server-owned request preparation and a
fixture Agent chain. This tests the existing PHP/Python callable and Agent IPC
paths; its optional local-Core mode uses the existing admitted DLM registration.
No paid model call, new Core admission, publication or deployment is implied.
The local PHP JSON-text result and signed `agent_result.v1` JSON result are both
validated against the same closed business contract.

Version 0.1.2 additionally accepts the existing signed Bedrock `agent_result.v1`
text envelope when its single text block contains the same bounded JSON object.
Duplicate keys, malformed JSON, changed observations and multiple text blocks
still fail. It reuses the existing provider transport and temporary worker role
identity. Versions 0.1.0 and 0.1.1 remain unchanged.

Version 0.1.1 declares the fixed semantic request in its pinned callable
dependency's `prepared_inputs.tool_request`. This requires Assets' generic
manifest preparation contract, including signed callable plan v3. Model
variables cannot replace that request. Version 0.1.0 remains unchanged and
still requires separate server preparation. Before promotion, verify support
for the new contract in the selected Assets runtime. Signed child MCP execution
and the summarizer's authority require separate substrate validation; this
declaration does not grant tool or provider rights. The summarizer's
logical contract must also be admitted before any real model run. No provider,
model, provider binding or credential is embedded in this adapter.

Use normal immutable intake/promotion steps when this development fixture is
reviewed. Preserve the working DLM versions and existing consumers. The parent
adds no MCP capability or handler and has no Skill-publication dependency.
