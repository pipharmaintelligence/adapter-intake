# Nusaibah Pharma Company Intelligence Lab

## 0.1.17 response resolution and portfolio reflection

The current intake version adds safe field/rule diagnostics, deterministic cleanup
and one registered `research_response_resolver` backup per rejected original Agent
invocation, covering planner, all three researchers, strategic analyst, critic,
synthesizer and every benchmark stage. Complete Markdown/triple-quote JSON wrappers
are parsed before validation and after backup; normal wrapped JSON needs no paid
repair. There is no retry or recursive backup of the resolver.

The resolver cannot search, rewrite facts or invent approval. Persistent research
schema errors become withheld evidence with critic gap accounting. Persistent
schema errors in other preparation roles retain an incomplete company preview,
skip its dependent stages and writes, and continue the batch. Incomplete packets
have no replacement candidate or fabricated critic/benchmark verdict. Identity,
provider/runtime and actual quality failures remain protected boundaries.

Set `variables.portfolio_review_passes` to **1, 2 or 3 total passes** (default 1).
The first reviews the portfolio using optional learned company methodology when
available; later passes reflect sequentially on the previous validated result.
Market/regulatory research and final critic/synthesis are not repeated. The pinned
Fixed Skill remains the global contract; missing learned methodology does not block
preview. Existing apply authority and package-initialization requirements remain.

Missing public information can be an explicit evidence gap, rather than an invented
claim. Positive claims still need admitted citations and critic acceptance.
Not-applicable/no-evidence work with explicit critic disposition does not mark the
company incomplete or itself block its writes. Unresolved schema withholds all
memory/methodology writes for that company; approved companies continue. The batch
report retains explicit gaps without a blanket publication stop. `publish_dossier`
keeps its existing output-policy readiness meaning and does not prove an upload.
Normal preview calls are 12/13/14 per company for 1/2/3 passes. One backup is reserved per
original call, making hard maxima 24/26/28; apply maxima are 26/28/30. Unused reserves
produce no calls. The five-company and
1,800-second limits remain. Earlier versions keep their existing contracts.

See [the resolution/reflection developer guide](../../../docs/pharma-research-resolution-and-reflection-developer-guide.md)
for the model, exact budgets, receipts, boundaries and official promotion sequence.

## 0.1.16 exact proposed-change review

Set `variables.retain_review_packet=true` to include `review_packet` inside the
existing `intelligence_dossier` output. The default is false. Request generic Core
preview retention separately (`retain_preview_result=true` at execute time).
This retains exact prepared memory/methodology section replacements and their
SHA-256 digests, baseline digests, selected claim IDs, validated claims, complete
research-role citations, planner chunks/requirements, critic decisions, before
and projected benchmarks, and residual uncertainties. No extra Agent calls occur.

The packet is a proposal with `review_state=not_reviewed` and no apply authority.
Role citations do not establish an individual claim-to-source mapping. Model
critic acceptance and projected benchmarks are not independent semantic review
or committed readback. Core supplies retention, access control, expiry and the
immutable run/artifact reference; the adapter does not choose a storage backend.

Apply now checks every company's existing memory and initialized methodology
before any provider call. Missing first-object methodology still requires the
generic governed Core create-if-absent capability. This release does not create
packages, apply a retained packet, or weaken write policy. Existing CAS,
readback/history and post-commit benchmark checks remain in force.

The optional packet plus company results has a 512 KiB bound and fails before
mutation without truncating proposals. Existing five-company, 12 preview / 13
apply calls-per-company bounds remain. Ship through pinned intake promotion;
retain every previously promoted identity. SDK 0.1.105 already supports generic
retention: no wheel upgrade or new environment setting is required.

See [the prepared-review developer guide](../../../docs/pharma-prepared-review-developer-guide.md).


## 0.1.14 CompanyContext handoff

The new version consumes a retained complete Company Scope result. Company Scope
is the only Companies reader in this path. Full intelligence receives database
observations from `CompanyContext`; it does not request a Companies binding,
re-query the lake/node, or infer a country name from a country ID.

```text
Caller: selector + intelligence options
  -> Company Scope 0.1.0: governed Companies acquisition, corporate = 1
  -> Core-retained company_scope_result
  -> Assets: authorized run-reference hydration + integrity/retention checks
  -> Intelligence 0.1.14: validate CompanyContext, research, critic, synthesis
  -> Preview dossier and candidates
  -> Eligible apply: existing governed Dynamic Skill memory/methodology flow
```

Caller input `company_context` is only `{"run_uuid": "<completed Scope run UUID>"}`.
The manifest pins producer `nusaibah.company_scope:0.1.0` and output role
`company_scope_result`. Assets/Core verifies client access, completed status,
retention and artifact checksum, and supplies the `{value, provenance}` envelope
to Python. Caller-supplied records, producer overrides and extra `companies`
inputs are rejected. Python's DTO/digest checks are defense in depth, not an
authentication mechanism.

The existing batch `variables` contract is retained, including required
`company_ids`, `memory_mode=preview|apply`, `research_depth=deep`, and
`objective=company_intelligence_memory`. These IDs confirm the exact target set;
they do not trigger data acquisition. Scope order may differ; intelligence
processes the requested order. No subsetting or partial-results fallback occurs.
The entire Scope result must contain 1â€“5 companies and match that requested set.
Scope's maximum of 25 does not increase intelligence's five-company run limit.
Paginated `company_scope:0.1.1/company_scope_page` is not this complete-result
contract and is intentionally rejected. Larger jobs require admitted bounded
epoch orchestration; this change does not introduce a large in-process loop.

Research Agents, prompts/chains, budgets, quality gates, output schema, published
methodology, Dynamic Skills and apply ordering are unchanged from 0.1.13.
Source/provenance refs stay outside Agent business prompts. A stored company
record is baseline information, not independently verified public research.
Agent research still needs the existing citation and critic acceptance gates.

**Compatibility and release:** use the official pinned intake promotion workflow.
It adds 0.1.14 and preserves every previously admitted identity and shared helper.
0.1.13 continues to use its Companies binding. Evaluation 0.2.3 is unchanged.
The installed E runtime 0.1.104 already meets the unchanged minimum of 0.1.98;
no wheel upgrade or new `.env` values are needed. Registration/admission for the
new exact identity and the promoted source catalog must pass before a live run.

**Persistence boundary:** preview performs no writes. Apply still requires
critic/benchmark eligibility, existing initialized methodology where a candidate
is needed, and governed Dynamic Skill mutation/readback/history. This handoff
does not create a missing methodology partition or publish to a new output node.
The first-object create-if-absent gap remains separate; the existing guard stops
before either mutable call. A successful context review is not evidence of a
full intelligence result or an eligible apply candidate.

See [the handoff developer guide](../../../docs/pharma-company-context-handoff-developer-guide.md)
for exact input, ownership, validation and rollout requirements.

## Historical 0.1.13 critic diagnostics candidate

This additive production version identifies the critic payload field or
pre-synthesis quality rule that failed. It reuses the existing generic
`proof_failure_detail.v1` contract and reviewed
`pharma_agent_business_schema_invalid` code. `stage=critic_payload` denotes
business-shape validation; `stage=pre_synthesis_quality` denotes a valid critic
payload that cannot pass the existing quality gate. Fields and rules are static
identifiers, without company values, claim IDs, notes or provider responses.

This follows run `8ff89da6-2870-431a-8e2a-94d4e60a745d`, which completed the critic
call but failed before synthesis without a retained rule. That historical rule
remains unknown. Absence of a methodology partition is not its established cause:
the supported first-run read path had already passed. First-object creation and
quality remediation remain separate work.

Agent definitions, prompts, chains, provider budgets, Fixed/Dynamic Skills,
validation decisions, write ordering and iteration limits are unchanged from
0.1.12. Shared helpers and the frozen evaluation baseline remain unchanged.
Deliver the new version through the pinned adapter-intake promotion workflow;
do not hand-edit packaged adapters or upgrade the installed runtime wheel.
Its minimum runtime is 0.1.98 for generic diagnostic transport; the installed
E runtime 0.1.104 already qualifies. No new environment values are required.

See [the diagnostic developer guide](../../../docs/pharma-critic-diagnostics-developer-guide.md) for release gates,
interpretation and recovery.

## Current validated baseline and future review direction

The validated baseline is asset `0.1.12` with runtime wheel `0.1.97`, intake commit `21cc6b39492cbd3c090de537a2ee27c599f0f0ec`. Company-13 preview `6e95802c-2336-47f5-b7c2-1e30476a0fef` completed in 303 execution seconds and produced the `intelligence_dossier` output role. This establishes that preview's execution; it does not establish expert-verified factual quality, large-document review, memory apply or file publication. Assets promotion reached main through PR #458 (reference in the developer guide).

The current planner uses four section calls. Three research roles receive their own plan fragments and required sections, but also full bounded company memory. Each research invocation has two provider steps: grounded evidence collection, then structured formatting with the original role input and evidence notes. Analysis, critique and synthesis receive joined evidence. Specialist names therefore do not yet imply fully isolated, minimal context. The existing hard limits below still apply.

The methodology-driven specialized review design (reference in the developer guide) and PI-1972 (reference in the developer guide) define the future architecture. **WP1 evaluation infrastructure is now under implementation on PR #74; the executable 0.1.12 review graph is unchanged.** Priority order is factual faithfulness, precise findings with complete review accounting, bounded execution, specialist relevance, then efficiency. Chunking is a mechanism to preserve evidence and focus review; smaller prompts alone are not a quality metric.

WP1 now provides a versioned 24-case synthetic evaluation suite with a fixed 16/8 development/held-out split, 24/24 domain-adjudicated cases, frozen source digests, an adjudicated criticality taxonomy, calibrated quality thresholds, fail-closed baseline measurement contracts, and an evaluation-only replay harness. Adjudication readiness is complete, but the unchanged 0.1.12 factual-quality/cost baseline is still unmeasured; WP2 remains blocked until complete validated baseline evidence exists. After that WP1 completion gate is satisfied, implementation may proceed to evidence/coverage contracts, relevant-memory projection, then source inventories, structure-aware chunks and a finite task plan. Preserve tables, footnotes, dates and cross-section dependencies; distinguish reviewed material from evidence that actually supports a claim. Verify specialist findings, reconcile global contradictions and check the assembled result for newly introduced unsupported claims. A budget stop or unreviewed required material must produce an honest incomplete result. Retain preview/apply separation, company isolation, immutable versions and existing Core/runtime authority boundaries.

Large-document review begins with fixtures or dummy source bindings. Real source access requires a separately reviewed binding contract. The WP1 implementation changes evaluation fixtures/tests only: it does not reduce budgets, change the Agent graph, modify runtime configuration, add source authority, or bump the executable asset version. Release entries below preserve historical candidate investigations; their version-specific statements are not a claim that every candidate is currently active.

## Release history: 0.1.12 claim identity and diagnostics candidate

The candidate is `0.1.12`, retaining all 0.1.11 agent contracts and budgets. Independent research roles may reuse local claim IDs. The deterministic join now namespaces each ID by its role and a full SHA-256 of the local identifier before analysis, critique and memory-candidate references are created. All claim statements and evidence flags are preserved; within-role duplicates and empty claims still fail. Research payload, citation and join failures carry safe role/stage/rule diagnostics without output values.

This follows `67984280-3382-4d87-92cb-ad849d2043c3`, where all research calls completed but a post-research business check failed before strategy. The old safe trace did not identify the exact check; cross-role ID collision was independently reproduced from valid role-local inputs. No claim is that the hidden historical exception is proven. Business quality gates remain enforced.

## 0.1.11 bounded synthesis candidate

The candidate is `0.1.11`. It retains the two-step research chains from 0.1.10 and advances the strategic analyst, evidence critic and synthesizer to chain `1.0.3`, each with a 16384-token output budget. Analysis and critique retain high thinking; synthesis uses medium thinking, still one provider step and a 180-second request timeout. Run `d717e0ef-fcbb-4420-bb45-021f62208fcf` reached the final high-thinking, 8192-token synthesizer and terminated with `provider_execution_output_limit_reached`. Run `c7a6f862-b9d7-40bc-9262-9e9aa16adec1` separately proved the critic exhausted its 6144-token budget with 5898 thought tokens and only 232 candidate tokens. This budget change preserves the full typed dossier contract; it does not accept truncated output or bypass quality gates.

The existing Vertex registration must admit a bounded 64000-character input and 16384-token output ceiling for these chains. The original 12000-character input ceiling rejected evidence-to-JSON continuations. Set these through Core's guarded provider-policy update command for the exact registration; no client/server dotenv copying is required. Publish both generated catalogs, admit the exact new chain versions and activate the version-specific Companies node-query binding.

Require Assets PR #456 including the completion/output-limit receipt detail parity fix. The worker and smoke CLI load the E: project .env. Company, planner, invocation, retry and task limits remain the same as documented below. Live verification is required before treating this candidate as ready.

## 0.1.10 grounded research candidate

The candidate at this investigation stage was `0.1.10`, with runtime floor `0.1.94`. The three research chains advance to `1.0.3`: an evidence step uses native Google Search with text output (8192 tokens, medium thinking, 180 seconds), then a separate non-search formatting step produces typed JSON (8192 tokens, medium thinking, 120 seconds). Native citations from the evidence turn remain in the runtime's existing multi-turn evidence contract and are required by the unchanged quality gate. Planner `1.0.4` and the other role definitions remain unchanged.

This follows live run `453f2d07-ac67-48a2-8a33-3576439764b3`: the corrected Core lifetime allowed all retries, but combined grounded JSON research returned repeated empty HTTP 200 candidates or exhausted three 120-second attempts. Separation is a compatibility mitigation to verify live, not proof of the provider's internal failure cause.

The adapter still permits at most five companies, four planner chunks and 12 preview/13 apply logical agent invocations per company. Research now has exactly two admitted provider steps per invocation; each step uses the existing maximum of three attempts. The 1800-second task deadline and separate 60-second cleanup budget remain. No automatic whole-workflow retry or memory write is added.

Deployment requires Core PR #160 and Assets PR #456 (or descendants). Promote this exact intake commit, retain all published versions, provision only the three new research chain versions, and prove a company-13 preview before declaring the candidate ready. The notes below preserve the preceding 0.1.9 investigation and deployment history.


Canonical adapter-intake source for `nusaibah.pharma_company_intelligence_lab`.

## Historical 0.1.9 immutable candidate

`0.1.9` was the intake candidate at this investigation stage. It preserves the `0.1.8` provider budgets and hard orchestration limits, raises the runtime floor to `pi-obs-python-runtime>=0.1.93`, and hardens the methodology-planner response contract after live company-13 preview proved that JSON mode alone did not guarantee the exact business shape enforced by Python. The planner chain advances to `1.0.4`; all other Agent chains remain at `1.0.2`.

| Role | Provider request timeout | Agent contract/chain version |
| --- | ---: | --- |
| `methodology_planner` | 60 seconds | `1.0.4` |
| `memory_benchmark_reviewer` | 60 seconds | `1.0.2` |
| `portfolio_researcher` | 120 seconds | `1.0.2` |
| `market_researcher` | 120 seconds | `1.0.2` |
| `regulatory_risk_researcher` | 120 seconds | `1.0.2` |
| `strategic_analyst` | 180 seconds | `1.0.2` |
| `evidence_critic` | 180 seconds | `1.0.2` |
| `intelligence_synthesizer` | 180 seconds | `1.0.2` |

The manifest declares these as `provider_policy.timeout_seconds`. The task deadline remains 1800 seconds. Model selection, token ceilings, thinking levels, search permissions, prompts, intended call counts, provider references and storage contracts are unchanged. The adapter enforces its logical call limits; the runtime continues to own transport, retries and material refresh.

Every changed Agent definition receives a new contract/chain version. Never use `--update-existing` to overwrite chains used by published `0.1.8` or older assets. Promote the new version through the pinned intake workflow and retain older versions.

## Hard iteration limits

The version-owned adapter applies these fixed limits to each invocation. Caller variables and Agent output cannot raise them.

| Scope | Hard maximum |
| --- | ---: |
| Companies per run | 5 |
| Planner iterations per company | 4 |
| Each researcher, analyst, critic or synthesizer per company | 1 logical call |
| Benchmark per company | 2 in preview; 3 in apply, including committed-memory verification |
| All Agent calls per company | 12 in preview; 13 in apply |
| All Agent calls per five-company run | 60 in preview; 65 in apply |

A single run-local counter covers the complete prepare/apply flow. It reserves each call under a lock before invoking the trusted helper, so concurrent research cannot race past a limit. A failed dispatch still consumes its logical call; the adapter does not retry it. Unknown roles and companies are rejected before invocation, each run gets fresh counters, and the apply phase verifies remaining committed-benchmark capacity for the whole batch before any mutation.

The planner loop also checks its iteration number directly, including if an erroneous future iterator repeats indefinitely. Excess calls raise `AgentContractValidationError` with the existing reviewed `pharma_agent_business_schema_invalid` code and an iteration-limit message. The successful `logical_agent_invocations` metric comes from the actual counter.

These are business orchestration limits, separate from runtime-owned provider retries and the 1800-second execution deadline. A call-count guard cannot interrupt a stalled network call; the governed transport timeout and worker watchdog provide that bound. In the validated 0.1.12 graph, each research invocation has exactly two provider steps; each other role has one. Every step retains the runtime maximum of three transport attempts. Native search is admitted only by the research evidence-step contract; logical invocation limits do not count individual provider steps or attempts.

## Live-readiness lessons learned

The 0.1.4 through 0.1.8 closure work exposed several failure classes that must be treated as separate gates. These are now part of the release discipline for this adapter.

1. **Prompt text is not the business contract.** A provider can return valid JSON with `STOP` and still violate the exact adapter validator. Every provider-facing `response_contract` must describe the same field set, field types, required values, minimum/maximum list sizes, normalization rules, enum values, and identity constraints that Python enforces. Tests must compare the model-facing contract with validator invariants before promotion.
2. **JSON mode is syntax, not schema enforcement.** `response_format=json_object` requests JSON output, but it does not prove the model followed the adapter business schema. Keep deterministic validation in Python and do not treat provider completion as business-contract success.
3. **Failure diagnostics must be safe, specific, and runtime-generic.** Do not store raw model output merely to debug contract failures. The adapter may emit bounded identifiers such as role, validation stage, field, and violated rule, but the shared runtime must not contain adapter keys, role lists, schema-field lists, or business-specific enums. Generated text, prompts, credentials, URLs, raw provider payloads, and storage details must never cross the diagnostic boundary.
4. **Published versions are immutable.** Business-contract, prompt, manifest, dependency, or adapter-code changes require a new asset version. Changed Agent definitions require new contract/chain versions. Never repair an older published identity with `--update-existing`.
5. **Shared helper coexistence is a package gate.** Retained published versions may share support files. Version-specific behavior belongs in the version-owned adapter unless a migration is explicitly compatible with every retained identity. A `shared_runtime_file_conflict` is not a provider or business-logic failure.
6. **Package closure is separate from catalog correctness.** A runtime catalog can reference a valid versioned dependency manifest while the wheel omits that file. Built package inspection must prove every catalog-referenced manifest is present before live execution.
7. **Registration, binding, admission, worker reachability, provider completion, and business validation are distinct gates.** Passing one does not imply the next. In particular, a ready governed binding does not admit Agent chains, and an admitted Agent chain does not prove the live planner output satisfies the adapter contract.
8. **Row filters are not partitions.** The Companies contract remains `filters_from_variables: id <- company_ids` on an unpartitioned node. Do not convert relational IDs into partition selectors to work around authoring limitations.
9. **Runtime and provider budgets must be proven independently.** Provider request timeout, Core material lifetime, scoped session lifetime, isolated worker watchdog, HTTP margin, queue timeout, and orchestration call caps are separate controls. Raising one does not repair another.
10. **Windows worker stability is an environment gate.** A native interpreter/OpenSSL crash is not an adapter contract failure. Record the exact worker interpreter/runtime identity and keep native crash diagnostics enabled; do not rebuild adapter logic to compensate for a base-Python crash.
11. **Preview precedes mutation.** A company-13 `memory_mode=preview` run must complete benchmark, all planner chunks, research, analysis, critic, synthesis, and final preview result before `memory_mode=apply` is attempted. Dynamic Skill mutation and output publication require separate readback/persistence proof.
12. **Historical success is not current-version readiness.** A binding, Agent chain, package, or live run for 0.1.7/0.1.8 does not establish readiness for 0.1.9. Certify the exact asset version, runtime wheel, catalog identity, binding, Agent versions, and run UUID together.

### 0.1.8 live failure that motivated 0.1.9

Company-13 preview run `14479e38-8958-4c85-b2dd-f89b6704fd36` established the following boundary: the governed Companies selector resolved `id=13`, the replacement worker stayed alive, `memory_benchmark_reviewer@1.0.2` completed, and the first `methodology_planner@1.0.3` provider call completed with `STOP`. The adapter then failed with `pharma_agent_business_schema_invalid` before a second planner call or any research role ran.

Because output storage was disabled and several validator rules shared the same failure code, the historical run could not reveal the exact invalid field. 0.1.9 therefore does two things: it makes the provider-visible planner contract explicit enough to match `_validate_planner_section()`, and it attaches enum-only proof metadata that a compatible trusted runtime can project without exposing response content.

Do not call this failure repaired until a freshly promoted/package-installed 0.1.9 company-13 preview completes the entire graph.

## Inherited planner behavior

The `0.1.7` planner reliability changes remain in `0.1.9`:

- methodology planner Agent contract/chain: `1.0.1 -> 1.0.2`;
- `max_tokens: 2048 -> 8192`;
- `thinking_level=medium` unchanged;
- `response_format=json_object` unchanged;
- the version-owned adapter deterministically routes the canonical research-section table of contents into section-sized planner chunks;
- benchmark coverage supplies a deterministic priority hint when one is known;
- if a section has no deterministic priority mapping, that bounded planner call may choose only low/medium/high;
- every mandatory research section is still planned exactly once;
- the planner receives only the selected section/subsection slice, section-scoped benchmark evidence, and bounded global methodology rules;
- Python deterministically merges all validated chunks into one complete methodology plan and runs the existing full-plan validator.

The budgets above are the only changes to the provider policies inherited from `0.1.7`.

Create a new asset version whenever adapter code, manifest metadata, reviewed helpers, dependency contract, or portable Skill bytes change. Environment-only repairs do not mutate an existing published version.

## Shared-helper coexistence

Retained published versions share the reviewed helper files in this folder. Version-specific behavior must stay in the version-owned adapter implementation unless a shared-helper migration is explicitly designed for every retained identity.

For `0.1.9`:

- `agent_contract.py`, `methodology_contract.py`, `input_contract.py`, `dossier_contract.py`, and `memory_contract.py` remain byte-identical to the published `0.1.6` package;
- the adapter retains the reviewed optional first-run methodology-read behavior from `0.1.7` and keeps the new iteration guard in its version-owned implementation;
- `adapter.dependencies.json` raises the runtime floor to `pi-obs-python-runtime>=0.1.93`, which includes the long-request governance from 0.1.91, the corrected isolated-worker watchdog from 0.1.92, and bounded generic Agent-contract proof-detail projection;
- Assets promotion must retain older versions' dependency bytes and materialize the changed `0.1.9` dependency contract as a version-owned dependency manifest. It must not rewrite dependency metadata used by `0.1.0` through `0.1.8`.

This keeps the intake package current-version oriented while preserving published-version coexistence.

## Planner token-safety boundary

`max_tokens` remains a hard total-output authorization. `0.1.9` does not add hidden thinking budget, retries, provider changes, or weaker validation.

The planner receives an 8192-token hard ceiling with medium thinking, but each provider call plans only one research section. Version 0.1.9 permits exactly four routed planner calls per company; a future change to the routed research-section count fails closed and requires a reviewed new version rather than silently increasing provider spend. Section calls are bounded to one question, one freshness-focus item, and one evidence-focus item, each at most 280 characters.

The deterministic merge then enforces the final-plan limits:

- at most 3 questions per research role;
- at most 2 freshness-focus items per research role;
- at most 2 evidence-focus items per research role;
- at most 4 cross-cutting questions;
- at most 4 known-memory gaps;
- at most 4 expected uncertainties;
- at most 280 characters per planner prose item;
- at most 12000 serialized JSON characters in the accepted final plan.

This avoids requiring one model turn to read and plan the entire research scope. Provider output-limit termination remains a runtime failure and is never accepted as completed JSON.

## Batch and governed-input contract

The launch variable is a bounded `company_ids` array such as `[13]` or `[13, 59]`. `companies` is binding-owned and `variables` is direct.

The governed company source is:

- lake: `test_database_lake`;
- node: `companies`;
- database primary key: `id`;
- company-name column: `company`.

The approved row/data mapping is `id <- company_ids`. This is not a partition mapping.

Assets/Core resolves the governed `companies` input before Python starts. The adapter normalizes `id -> company_id` and `company -> company_name`, validates exact requested/resolved ID parity, and processes company contexts independently.

A new asset version requires its own exact governed binding identity; readiness of a `0.1.7` or `0.1.8` binding does not prove `0.1.9` binding readiness.

## Fixed Skill and Dynamic Skill

The Fixed Skill remains publication-backed:

`nusaibah.pharma-intelligence-methodology@1.0.0`

with its existing canonical digest.

Existing factual Dynamic Skill roles and authority are unchanged:

- `company_memory`: read-only current company partition;
- `company_memory_update`: mutable current company partition when apply mode is explicitly used.

The separate company methodology Dynamic Skill is company-scoped procedural memory. It is read-only to planning and mutable only through the adapter's post-critic learning path. It does not replace factual company memory and it cannot override the Fixed Skill, current benchmark evidence, or runtime safety authority.

Its lifecycle is:
- read current methodology before section planning;
- use only the selected section's bounded learned slice as a planner hint;
- after research and evidence-critic quality gates pass, require projected company-memory benchmark non-regression before building one complete bounded learning snapshot;
- if the benchmark regresses, keep the completed company result but mark methodology learning `no_change_recommended`;
- in `memory_mode=preview`, expose the eligible candidate without mutation;
- in `memory_mode=apply`, commit one complete company snapshot through preview and `apply(expected_digest)`, verify persisted content through a fresh read-only role, then verify committed history through a freshly resolved mutable role;
- if the generated methodology snapshot is byte-equivalent to the current snapshot, treat it as an idempotent no-change outcome rather than failing the run.

No Skill publication, mutation-authority, storage, or persistence behavior changes for the Fixed Skill in `0.1.9`.

## Format ownership

`dossier_contract.py` owns exact section IDs, subsection IDs, titles, and order. Agents return machine IDs and content only. Titles and hierarchy are rendered deterministically by the adapter.

## Promotion ownership

This adapter-intake folder is the reviewed source package. Published Assets materialization must be produced through the pinned adapter-intake promotion workflow rather than by hand-editing the packaged Assets directory.

Promotion must preserve every already-published pharma version and must not use manifest-removal authorization.

## Coordinated deployment profile

The manifest is request intent. It cannot raise Core's policy ceiling, material lifetime, or session authority. Deploy Core PR #158 and Assets PR #444/#453 (or descendants) and runtime `0.1.93` or later before enabling this profile. The UI policy preservation fix is needed if editing through the UI; the guarded Core command below preserves omitted policy fields.

Apply the following settings in their owning application environments. These affect newly admitted work on that deployment; do not change authority beneath active sessions. Keep the global Assets `OBS_VERTEX_TIMEOUT_SECONDS` default unchanged: this asset now supplies explicit per-role budgets, so unrelated Vertex workloads retain their current request timeouts.

Core environment:

```dotenv
DLM_PROVIDER_EXECUTION_MATERIAL_TTL_SECONDS=240
DLM_AGENT_EXECUTION_SESSION_MAX_SCOPED_LIFETIME_SECONDS=1800
```

Retain the existing `DLM_AGENT_EXECUTION_SESSION_LIFETIME_SECONDS` for v1 clients. The scoped ceiling is opt-in through admission v2 and does not make session authority unlimited. Keep pool allocation and fallback permissions unchanged; extra credentials do not repair read timeouts.

Assets environment:

```dotenv
PYTHON_ADAPTER_AGENT_BRIDGE_SEPARATE_CLEANUP_BUDGET=true
PYTHON_ADAPTER_AGENT_BRIDGE_RESPONSE_MARGIN_SECONDS=60
PYTHON_ADAPTER_WORKFLOW_JOB_TIMEOUT_SECONDS=1920
```

Local worker environment (the file used to start the worker, not merely the smoke client):

```dotenv
OBS_AGENT_EXECUTION_SESSION_SCOPED_LIFETIME_ENABLED=true
```

For the 1800-second task this gives worker execution plus cleanup 1860 seconds, gateway HTTP wait 1865 seconds and queue job timeout 1920 seconds. Database/Redis `retry_after` must exceed 1920; an existing 9000-second reservation is sufficient. Supervisor shutdown grace must cover the job. Retain the Python process watchdog on Windows. The task deadline still bounds retries and the entire company batch; three worst-case attempts at every sequential role are not guaranteed to fit.

Raise `max_timeout_seconds` to 180 on each exact Core provider registration governing these admitted roles. Resolve the registration and owner identities through the existing safe provider projection; do not guess them or substitute a binding UUID for a registration ID. From the Core checkout, use its guarded command with the verified identity values:

```powershell
$PolicyArgs = @(
  'dlm:provider-execution-policy-update',
  "--registration-id=$RegistrationId",
  "--owner-integration-id=$OwnerIntegrationId",
  "--client-id=$ClientId",
  '--provider-family=vertex_ai',
  '--provider-instance=vertex-primary',
  '--capability=llm.generate',
  '--max-timeout-seconds=180'
)
php artisan @PolicyArgs
# Inspect the exact identity and timeout-only diff before applying it.
php artisan @PolicyArgs --apply
```

Omit every unrelated policy option. Preserve model/location selectors, tokens, thinking, grounding, structured output, execution enablement and fallback. Above-ceiling requests must still fail with `timeout_limit_exceeded`; an insufficient material window must still fail with `agent_execution_provider_material_lifetime_insufficient`. Never bypass those gates in adapter code.

Rebuild/clear each owning Laravel config cache according to deployment practice and restart its long-lived workers. Restart the local worker with the intended environment. Keep the existing reviewed executor identity. New runs must receive the new settings; an existing admitted session is not extended.

After pinned promotion of `0.1.9` and exact version binding/catalog readiness, dry-run **all eight** Agent admissions before applying them:

```powershell
$AgentRoles = @(
  'methodology_planner', 'memory_benchmark_reviewer',
  'portfolio_researcher', 'market_researcher', 'regulatory_risk_researcher',
  'strategic_analyst', 'evidence_critic', 'intelligence_synthesizer'
)
foreach ($Role in $AgentRoles) {
  & $AgentAdmit --env-file $ClientEnv `
    --asset-key nusaibah.pharma_company_intelligence_lab `
    --asset-version 0.1.9 --agent-role $Role --pretty
  if ($LASTEXITCODE -ne 0) { throw "Admission inspection failed: $Role" }
}
# After every dry-run passes and the new versions/budgets are correct:
foreach ($Role in $AgentRoles) {
  & $AgentAdmit --env-file $ClientEnv `
    --asset-key nusaibah.pharma_company_intelligence_lab `
    --asset-version 0.1.9 --agent-role $Role --apply --pretty
  if ($LASTEXITCODE -ne 0) { throw "Admission failed: $Role" }
}
```

`$AgentAdmit` is the installed `obs-agent-runtime-admit` executable. Reuse the existing company 13 preview inputs; provider timeout fields do not belong in caller variables. Launch `--asset-version 0.1.9 --poll-timeout 2100 --poll-interval 3`. The poll timeout controls client observation only.

## Live proof boundary

A green intake or promotion PR is not live proof.

After promotion/deployment of `0.1.9`, prove independently:

1. exact `0.1.9` governed Companies binding;
2. planner `1.0.4` and all other Agent `1.0.2` admissions;
3. exact worker/runtime catalog identity for `0.1.9` with runtime `0.1.93` or later;
4. company 13 preview;
5. benchmark reviewer completion followed by methodology planner completion;
6. remaining roles in execution order;
7. Dynamic Skill mutation separately from runtime result;
8. dossier file publication separately from runtime result.

Inspect safe session/attempt metadata: admitted requests must show 60/120/180 seconds by role, Core must allow 180 seconds, material must cover the selected attempt, and the scoped session must cover the remaining task deadline without extension. Confirm the queue envelope and unchanged Bedrock primitive independently. A synthetic test or a green PR does not establish Vertex latency/capacity or end-to-end live success.

Rollback: stop new `0.1.9` launches and let admitted work finish. Route back to the retained `0.1.7` package, exact binding and Agent versions, and restore the saved environment/policy values. Do not overwrite older published bytes or shorten an active session's authority.

## Runtime Skill dependency compatibility â€” 0.1.15

The caller still supplies only `company_context` and `variables`. Assets adds
four manifest-declared Runtime Skill slots before SDK invocation:
`company_memory`, `company_memory_update`, `company_methodology`, and
`company_methodology_update`. These are dependency slots, not caller inputs or
additional Companies acquisition.

Version 0.1.14's exact two-key check rejected that legitimate six-role map before
any provider call. Version 0.1.15 preserves the two required business roles and
permits only those four optional runtime-owned names. Their values remain opaque
to CompanyContext validation and never become research evidence. SDK
`dynamic_skill(...)` retains all read/mutation authority. Unknown roles, caller
Skill overrides, raw contexts, partial scopes and digest mismatches remain
rejected. The server manifest boundary still rejects caller Skill slots with 422;
local role-name acceptance does not establish runtime authority.

Before a provider test, validate the complete runtime input map including
manifest dependency slots, not just an inputs-only fixture. Regressions cover
all slot subsets, opaque values, unknown and missing roles, the full two-company
preview with 24 Agent calls and zero mutation, real installed SDK RuntimeInputs,
and retained 0.1.12/0.1.13/0.1.14 business suites. Publish through the official
workflow. Runtime 0.1.104 and previous version/helper bytes remain unchanged.
