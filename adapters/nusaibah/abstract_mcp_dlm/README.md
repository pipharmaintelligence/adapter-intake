# abstract_mcp_dlm — 0.1.1 intake handoff (PI-2047)

This folder declares one **read-only, local-first** DLM MCP adapter version. It
does not call DLM Core, Assets, providers, MCP servers, or storage from Python.
A separate trusted runtime must prove the exact Core capability/executor and
caller scope before this version is published through Remote MCP.

## Version and promotion rules

- `adapter.yaml` selects `abstract_mcp_dlm_v0_1_1_adapter.py`.
- The manifest contains only `0.1.1`. Assets materialization preserves the
  previously published `0.1.0` adapter and merges its manifest entry.
- `abstract_mcp_capabilities.py` is intentionally byte-identical to the
  shared helper already packaged for `0.1.0`. Do not modify it: changes can
  fail the promotion with `shared_runtime_file_conflict`.
- Use the **exact immutable intake SHA** when invoking the official
  `adapter-intake-promote-pr.yml` workflow; `allow_manifest_removals=false`.
- Draft intake PR and a green intake CI do not imply Assets promotion, signed
  ECS image build, deployment, governed MCP admission, or ChatGPT readiness.

## Input/output contract

One direct input role named `tool_request` containing **one** operation:

- `{"operation":"lakes.list","page_size":20}`
- `{"operation":"nodes.list","lake_id":"approved_lake","page":1,"page_size":20}`
- `{"operation":"nodes.schema","lake_id":"approved_lake","node_key":"records"}`

A public Remote MCP tool must use `{"tool_request":{...}}` because Assets
currently passes registered-asset arguments directly to the adapter's input
map. Each publication must use a schema that fixes `operation` to one enum
value and rejects unknown properties; do not publish a generic multi-operation
tool. No actor/client/authorization/executor identifier is a caller argument.

Success requires an injected, admitted runtime `invoke_tool` role returning
the existing Assets trusted envelope: `status=completed`, `operation=invoke`,
exact `capability_ref` / `tool_handle` / `tool_server_ref`, typed `records`
and `provenance` containing the matching role, runtime marker, invocation ID,
cache flag, duration and exact record count. Missing bridges, errors, absent or
mismatched provenance, invalid shapes, unexpected statuses, mismatched lake/node,
and limits fail closed. A successful empty result is not an absent invocation.
The adapter never exposes raw runtime provenance, exception messages, Core
envelopes, credentials, URLs, paths, object contents, SQL or provider data.

The provenance checks here validate an expected **shape**, not a signed receipt.
Only Core/Assets can certify actual admission and trusted execution. This
documented envelope may need a contract revision after the G0 first-party
executor is selected; no new bridge or transport is invented in intake.

Intake tests: `python -m unittest discover -s tests -p
"test_abstract_mcp_dlm_0_1_1.py" -v`.

## Server-owned gate before promotion/publication

Per PI-2047 G0, verify **real** DLM read execution for the exact declared
`@tool.abstract_mcp_dlm / mcp.abstract_dlm` tuples, client/user/lake
authorization, and signed local_worker/ECS behavior. Ordinary
`inputs.invoke_tool` callbacks are local-only in the canonical runtime
contract absent a reviewed trusted production bridge. This intake PR neither
creates that bridge nor claims one exists.

P1 readiness/object/partition capabilities and P2 data queries remain
unpublished until separately reviewed and authorized. Do not add raw HTTP,
leases, retries, worker orchestration, or publication logic to this adapter.
