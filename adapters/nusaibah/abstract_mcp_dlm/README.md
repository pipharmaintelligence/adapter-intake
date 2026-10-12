# abstract_mcp_dlm — 0.1.1 discovery and orchestration (PI-2047)

This folder declares one **read-only, local-first** DLM MCP adapter version. It
does not call DLM Core, Assets, providers, MCP servers, or storage from Python.
It packages the existing three read capabilities and a fixed conversation skill.
The existing governed runtime must prove the selected read and caller scope
before this version is published through Remote MCP.

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

## Fixed discovery skill and capability metadata

Version `0.1.1` declares the bundled fixed Skill
`nusaibah.dlm-discovery-orchestration@1.0.0` in `skills[]`, with the exact
package digest. Its source is
[`skills/dlm-discovery-orchestration/SKILL.md`](skills/dlm-discovery-orchestration/SKILL.md).
The normal materializer validates and copies this package with the asset;
no new Assets handler, tool role, Core endpoint, or fourth capability is needed.
The prior `0.1.0` version and its shared capability helper remain unchanged.

The skill teaches the host to search a spelling, inspect `lookup`, ask for
confirmation, and continue with the returned `lake_id` / `node_key`.
The adapter already performs a bounded fallback after zero literal hits;
the conversational host must not repeat that fallback. A noninteractive
runtime returns the confirmation state without performing dependent reads.
Skill instructions do not turn a deterministic adapter into a conversation
agent or establish execution authority.

The skill's [versioned capability metadata](skills/dlm-discovery-orchestration/references/capabilities.v0.1.1.json)
contains exactly the three existing capabilities with publication-ready
descriptions (within Assets' 240-character limit), strict per-operation input
schemas and output schemas that include the actual `lookup` fields.
These are **templates only**, not published tools or a new auto-expansion
mechanism. Copy the chosen entry's `remote_mcp.tool_name`, `description`,
`input_schema`, and `output_schema` into the existing publication process
after its execution binding and server-owned launch profile are verified.
The output schema describes the current registered-asset result shape
`{"tool_results":{...}}`; local invocation returns it inside `outputs`.
The first live publication remains `dlm_list_lakes`; the other two templates
become usable only when their own publications are approved and advertised.

**What ChatGPT sees:** publishing an adapter version alone does not expose
its Python registry, manifest, or bundled skill. The current Assets
`RemoteMcpToolProjectionAdapter` exposes each eligible publication's name,
description, input schema and optional output schema through `tools/list`.
Results put `tool_results.lookup` in model-visible `structuredContent` and
`content`. Tool-result `_meta` is hidden from the model and must not carry
the orchestration instructions.

For the full skill to guide ChatGPT, package/install these same skill files
through a supported ChatGPT plugin/skill-loading path. Assets' bundled
`skills[]` is an asset-runtime dependency, not automatic ChatGPT installation.
Keep essential confirmation guidance in the public tool descriptions even
when the full skill is not installed. Refresh the custom MCP connection
metadata after publication changes and verify the advertised fields in a
new conversation; submitted plugins require their normal release process.
See OpenAI's [skill model](https://developers.openai.com/plugins/concepts/skills),
[tool result reference](https://developers.openai.com/plugins/reference#tool-results),
and [connection metadata refresh](https://developers.openai.com/plugins/deploy/connect-chatgpt#refresh-metadata).

Regression checks cover digest pinning, exact capability/role parity, schema
selectors and limits, descriptor size, and a lake-to-node-to-schema trace
using fixture-returned identifiers. They are deterministic; they do not
certify ChatGPT compliance or live remote execution.

## Existing runtime proof before promotion/publication

PI-2047's 2026-10-12 delivery priority supersedes the historical Core-first
implementation sequence. Verify one declared read through the existing
governed runtime locally and on the intended signed worker, then use normal
intake promotion and the first Remote MCP publication. Change a shared
runtime/Core contract only when a targeted test proves a reusable gap.
Fixture callbacks and intake CI do not prove live execution, admission,
publication, or terminal ChatGPT behavior.

P1 readiness/object/partition capabilities and P2 data queries remain
unpublished until separately reviewed and authorized. Do not add raw HTTP,
leases, retries, worker orchestration, or publication logic to this adapter.

