# PI-2047 - Lake Knowledge & Engineering: implementation handoff

22 November 2026. Development candidate only; no deployment or live mutation.

## Delivered boundaries

Source: `development/nusaibah/abstract_mcp_dlm_0_1_3/`.
Consumer tests: `tests/test_dlm_lake_memory.py`.
Fixed host instructions: `plugins/dms-dlm-discovery/skills/dlm-discovery-orchestration/SKILL.md`.
Private ChatGPT plugin: https://chatgpt.com/plugins/Plugin_c2f8ef7bd08c819196dcc9ae1b427314
Plugin 1.3.0, release `pluginrel_6b02dfa63970819187c08fdfea5a108e`.

The existing adapter manifest still selects 0.1.2. This is deliberate: current
source does not implement the required authority-derived Skill partition provider.
The code must not be represented as an admitted or deployable 0.1.3 release.

The runtime caller foundation observed in Assets `f763635d5f6109f380f3cd0ff6d779f1746fd77d`
is `RemoteMcpOauthAuthenticator` -> `AuthenticateRemoteMcpCaller` ->
`RemoteMcpExecutionCallerContextFactory`. It derives the business client from the
verified user and installs `obs_resolved_client_id` separately from OAuth app identity.
`AssetRuntimeSkillRoleComposer` currently supports static values and variable
mappings, not the new verified-context binding requested here. Generic callable
variables must not be weakened or renamed to smuggle tenant/lake authority.

## Exact remaining engineering

| Gate | Owner | Required result |
| --- | --- | --- |
| Receiving authority binding | Assets | Reuse authenticated client/actor; bind the exact subject lake and permitted operation to the four declared read/update roles. Construct a server-only, request-bound safe scope projection. Reject public context/tenant overrides, missing authority and queued revocation. This is the first blocking gate. |
| Tenant isolation | Core + trusted Assets runtime | Enforce `client_id + lake_id + memory_kind` on current read, initialize, update, history, delivery, receipts, caches, locks and ordinary backing-object access. The storage lake/node grant alone must not expose other partitions. Same-client sharing still obeys actor permissions. |
| Core implementation observation | Core + Assets tool projection | Provide an admitted fresh allowlisted node/schema/partition/revision/approval/readiness/acceptance result. `dlm_node_implementation` is the proposed consumer role, not existing authority. Required checks unavailable -> unverified, never synthetic approval. |
| Read-only history | Assets/Core | Qualify committed revision reads without granting mutation rights. Current-only handles return truthful `history_unavailable`. |
| Final adapter intake | adapter-intake | Wire exact supported declarations in the incoming 0.1.3 descriptor/manifest, approved governed storage and scope contracts; run actual runtime wheel fixture/profile, official intake checks, packaged wrapper imports and old-version coexistence. No placeholder tenant or invented provider fields. |
| Controlled release | Assets/operator | Promote exact reviewed intake SHA, build and verify worker/wheel, separately deploy, admit roles and publish four narrow operations with real read/write policy. Existing holds remain unchanged. |
| ChatGPT and live persistence | Host + operator | Install/enable the private fixed Skill; in a fresh conversation inspect advertised tools, read context, preview, authorize apply, verify receipt and fresh independent read/history. Two clients accessing the same lake must remain isolated; two permitted agents in the same client must share committed knowledge. |

The proposed `context.dlm_lake_memory_scope` and Core observation JSON schemas are
exported from code for owner review. They are not claims about present SDK fields.
An alternate approved existing safe projection can replace them before release;
do not add another identity, Skill storage or execution subsystem.

## Behavior and acceptance

Knowledge has seven extensible logical sections, stable assertions, typed source
references and explicit supersession. Engineering has one stable register with
proposed schema, expected outcome, acceptance checks, dependencies, progress,
protected approval/actual observations and immutable completion-time evidence.
Later Core schema drift is separate from historic completion. Node creation and
schema application are not performed by these memory tools.

Preview is the default. Apply requires the exact base and proposal digests plus
server-authorized operation scope. Readback and history are independent flags.
Unknown mutation outcomes never trigger automatic retry. Initialization is a
separate admitted first-write path, not an update receipt. Two memory partitions
are not a transaction; partial outcomes must stay visible.

Current explicit bounds: 64 KiB request/result, 256 KiB document and 200 current
records per memory. Exceeding these fails rather than silently deleting history.
No limit on revision count is introduced. A later governed archival/rollover
extension is needed before unbounded current-register growth. Partial-visibility
callers currently fail closed; do not imply per-record redaction is implemented.
Context is stored-memory projection only; callers use separate authorized Core
reads for current inventory. Links are typed references, never HTTP execution.

## Validation and non-claims

The consumer test harness is explicitly fake and provider-free. It tests tenant
identity mismatches, stale writes, read-only preview, exact digest gates, uncertain
commit handling, independent reads, history projection, proposed/observed schema,
protected completion and drift. It does NOT certify middleware, Core permissions,
provider ZIP persistence, actual runtime wheel integration, ECS or ChatGPT writes.

The new workflow runs syntax + consumer tests on Python 3.10 and 3.13 and exports
closed input templates. Read its exact-SHA result before asserting CI success.
Existing repository intake/read-only regressions remain separate and unchanged.

## Host reachability

The private plugin was actually created in the current workspace, not merely
saved as a source file. It is instructions-only and requires the separately
authorized DLM MCP connection. Creation does not prove installation in every
conversation. Open/enable it through the host and verify a fresh conversation can
load `dlm-discovery-orchestration`; unavailable memory tools must be reported as
unavailable. Fixed instructions do not grant tenant identity or write authority.

Official references checked: https://developers.openai.com/plugins/concepts/skills
and https://help.openai.com/en/articles/20001066-skills-in-chatgpt .

Do not merge or promote this draft until the first four engineering gates are
qualified and the final incoming manifest is reviewed. Keep normal read-only
DLM discovery working throughout.
