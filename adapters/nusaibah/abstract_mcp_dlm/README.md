# abstract_mcp_dlm — 0.1.1 discovery and orchestration (PI-2047)

This folder declares one **read-only, local-first** DLM MCP adapter version. It
does not call DLM Core, Assets, providers, MCP servers, or storage from Python.
It packages the existing three read capabilities and their publication metadata.
The conversation skill is distributed separately as a ChatGPT plugin.
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
Only Core/Assets can certify actual admission and trusted execution. Validate
the selected registered profile and execution lane independently; intake does
not admit an executor or introduce a bridge or transport.

Public lake search remains `q`. The adapter sends its validated search string
through the existing Core runtime input `text`; the registered generic HTTP
connector maps that text to its query parameter. Internal `q` is not an admitted
extra parameter in the current profile. Node search continues to use `search`.
The bounded fallback clears the query and retains only the required resource
scope and limit. No caller can supply `text` through the public request schema.

Intake tests: `python -m unittest discover -s tests -p
"test_abstract_mcp_dlm_0_1_1.py" -v`.

## Generic orchestration and callable reuse preparation

`mcp_read_resolution_v0_1_1.py` is a resource-neutral reviewed helper. It checks
the normalized trusted envelope against a frozen `ReadContract` and applies a
`NameProfile` to an adapter's safe projected records. DLM supplies its existing
role/capability tuple, lake/node identity fields, bounded fallback selectors,
and positive projection. Another approved adapter can use the same helper with
its own project, collection, document, or job contract. Tests exercise a project
profile with a different tool, server, capability, ID and parent scope.

Profiles are developer-reviewed code, never caller input. The helper supplies no
transport, admission, credentials, executor registration, or capability expansion.
Each consuming adapter must package the reviewed helper through its normal intake
contract and validate its own resource scope before exposing records. The shared
`abstract_mcp_capabilities.py` remains byte-identical for 0.1.0 coexistence.

The helper accepts both existing Assets invocation-ID formats: compact lowercase
hex and the lowercase hyphenated UUID format produced by the PHP bridge. All
other envelope identity, provenance, count and output limits remain enforced.
Unicode/case and punctuation normalization now works as documented.

The internal manifest declares a bounded callable object result at `tool_results`
and an optional `variables` input. **Required `tool_request` is preserved.**
Variables accept only `q`, `page`, and `page_size` where that operation supports
them. They cannot supply operation, lake/node scope, tool role or authority;
conflicts with prepared filters fail before invocation. The runtime's existing
generic callable-variables guard still applies. Public schemas remain unchanged
and accept only the existing wrapped `tool_request`.

For reuse, a reviewed parent asset declares the exact target version through the
existing `callable_assets` contract, and the trusted execution lane must prepare
the required `tool_request` and admit the child's exact three runtime-tool roles.
Do not place `lake_id`/`node_key` in variables, rename them to bypass the guard,
or serialize a tool request into a scalar. A variables-only `invoke_asset` call
cannot satisfy this asset's required prepared input. Current direct callable
planning can reject that missing preparation; this declaration is reuse
preparation, not proof that nested runtime-tool authority is available.

Run a parent-to-child execution proof in the intended existing lane before
enabling a consumer. Propagate `tool_results.lookup.requires_confirmation` to an
interactive host; a noninteractive agent stops dependent reads until its caller
resolves the selection. Do not widen executor kinds or add a per-adapter handler
to bypass missing authority. Promotion, runtime admission, MCP publication and
ChatGPT plugin distribution are separate release steps.

Plugin `dms-dlm-discovery@1.1.0` adds a generic `mcp-resource-discovery` Skill
alongside the existing DLM-specific Skill. Neither is an adapter execution
dependency. The generic Skill follows advertised contracts without assuming lake
IDs, node fields, tool names, or a particular capability count.

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

## Skill ownership: ChatGPT conversation orchestration

`dlm-discovery-orchestration` is a **ChatGPT-facing Skill**. The adapter is
deterministic and has no Skill call. Its execution does not require those
conversational instructions. Version `0.1.1` therefore declares neither a
bundled `skills[]` dependency nor a `published_skills[]` dependency.

The Skill is owned by the independent
[`dms-dlm-discovery` plugin](../../../plugins/dms-dlm-discovery/README.md)
at repository path `plugins/dms-dlm-discovery/`. That portable package contains
root `plugin.json` and `skills/dlm-discovery-orchestration/SKILL.md`; use the
normal ChatGPT Plugin Skill distribution and installation path. It is not
copied into the Python runtime by this adapter's materializer.

The Skill teaches ChatGPT to search a spelling, inspect `lookup`, ask for
confirmation, and continue with the returned `lake_id` / `node_key`.
The adapter already performs a bounded fallback after zero literal hits;
the conversational host must not repeat that fallback. A noninteractive
caller returns the confirmation state without performing dependent reads.

Removing the runtime dependency avoids the unrelated immutable Skill
publication/client-visibility gate. It does not change DLM access checks,
OAuth, admission, or any other execution readiness requirement. No internal
Skill publication is needed for this adapter's execution.

A published Fixed Skill may still be stored canonically as a ZIP object in a
lake/node using the existing exact-version/digest publication registry.
A real Assets runtime consumer can declare it through `published_skills`
and resolve it through the admitted Skill API. That is a separate consuming
asset/agent decision; lake storage alone does not justify adding a dependency
to this adapter. The three discovery capabilities return metadata/schema,
not a Skill ZIP or `SKILL.md` content.

## Adapter-owned capability metadata

[`capabilities.v0.1.1.json`](capabilities.v0.1.1.json) remains in this adapter
folder, declared in `adapter.yaml.reviewed_support_files` for normal Assets
materialization. It contains exactly the three existing capabilities with
publication-ready descriptions (within Assets' 240-character limit), strict
per-operation input schemas and output schemas containing the actual
`lookup` fields. The shared capability helper remains byte-identical.

These are **templates only**, not published tools or a new auto-expansion
mechanism. Copy the chosen entry's `remote_mcp.tool_name`, `description`,
`input_schema`, and `output_schema` into the existing publication process
after its execution binding and server-owned launch profile are verified.
The output schema describes the current registered-asset result shape
`{"tool_results":{...}}`; local invocation returns it inside `outputs`.
The first live publication remains `dlm_list_lakes`; the other two templates
become usable only when their own publications are approved and advertised.

**What ChatGPT sees:** publishing an adapter version alone does not expose
its Python registry, manifest, or plugin Skill. The current Assets
`RemoteMcpToolProjectionAdapter` exposes each eligible publication's name,
description, input schema and optional output schema through `tools/list`.
Results put `tool_results.lookup` in model-visible `structuredContent` and
`content`. Tool-result `_meta` is hidden from the model.

For full orchestration guidance, install/enable the separate ChatGPT plugin
and the intended authorized DLM connection. The plugin provides instructions,
not MCP tools or authorization. Keep essential confirmation guidance in the
public tool descriptions even when the plugin is not installed. Refresh
custom MCP connection metadata after publication changes and verify it in a
new conversation; submitted plugins follow their normal release process.
The independent plugin README links to OpenAI's official plugin packaging,
Skill activation and tool-result references. External URLs remain outside this
materialized package to satisfy the existing intake content guard.

Regression checks cover the absence of execution Skill dependencies,
self-contained plugin packaging, capability/role parity, schema selectors and
limits, descriptor size, and a lake-to-node-to-schema trace using returned
identifiers. These are source checks; plugin installation, host instruction
loading and live ChatGPT behavior remain unproven until observed.

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
