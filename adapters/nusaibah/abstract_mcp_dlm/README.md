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

## Pagination and response inspection

The adapter version packages **all three roles** (`lakes.list`, `nodes.list`,
`nodes.schema`) once. Remote MCP visibility is a separate Assets publication
decision: existing publication records advertise **one public tool name each**,
not an automatic expansion of the adapter's roles. Do not claim three separately
named ChatGPT tools are exposed by one publication until the current publication
configuration is verified. No special-case Assets executor is needed in this
adapter.

- Lakes list accepts `q` and `page_size` (1–50). The current Core lakes API
  has `limit` but **no page/cursor selector**. A bounded first-page result
  can include `has_more=true` and `truncated=true`, but **never** a
  fabricated `next_page`. If the trusted executor omits `has_more`, the
  adapter omits it too; absence is **unknown**, not `false`.
- Nodes list accepts `lake_id`, `q`, `page` (1–1000) and `page_size`
  (1–50). A real `has_more=true` with a page below 1000 permits `next_page`.
  The upstream admitted capability must honor page selection, not merely
  echo the same records.
- A successful empty lake/node list is `status=completed`,
  `records=[]`, `record_count=0`. A missing or unavailable node schema is
  an error; it must not be mislabeled as a successful empty schema.
- If a backend exceeds a requested limit, exceeds the byte/field budget,
  returns malformed pagination, or reports `has_more=true` with no records,
  the adapter fails closed. It does not silently discard records or make up
  a continuation token.

### Inspecting real API responses safely

Use an **approved authenticated server-side** Core client to capture sanitized
response-shape evidence (status, array locations, safe counts and pagination
keys). Operators may use cURL in their authorized environment, but **do not**
add Core URL, credentials, tokens, headers, or network calls to adapter code or
commit raw cURL responses as fixtures. Confirm these Core API envelopes before
any live MCP binding:

| Core read | Response data | Continuation evidence |
| --- | --- | --- |
| Lakes list | `data.lakes` | `meta.counts.has_more`; no Core page selector |
| Node inventory | `data.nodes` | `meta.pagination.page`, `meta.pagination.has_more` |
| Node schema | `data.schema_definition` and presentation | 404/unavailable is not an empty successful schema |

The current Python adapter expects a **trusted normalized tool envelope** with
`records` and verified provenance, **not** an unfiltered HTTP/cURL response.
Only the server-owned runtime/Core integration can map the Core API envelope to
those records. Do not implement a custom HTTP client in the Python adapter.

## Search correction and conversational selection

The existing lakes and nodes list roles provide bounded typo-tolerant name
suggestions. For example, a search for `hyser` can suggest an authorized lake
named `Hyper` after a filtered search returns no rows. The adapter does not
use a language model, embedding service, external network call, or Core query
outside its declared `invoke_tool` role.

The `lookup` output distinguishes `exact`, `suggestions`, `ambiguous`,
`no_match` and `unresolved`, includes at most three safe candidates, and
reports `requires_confirmation`. Only an exact ID/name with sufficiently
known coverage can emit `resolved_id`. Suggestions are **never selected**
silently. ChatGPT should ask the user to confirm a suggestion before using it.

A fallback unfiltered catalogue read runs only when a filtered name search
returns no records; it remains bounded to the same approved role and 50
records. Without explicit completed pagination evidence the adapter must
not assert that a lake or node does not exist. This is deterministic spelling
assistance, **not semantic embeddings or a comprehensive fuzzy-index search**.
A missing match in an incomplete catalogue remains `unresolved`.

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
