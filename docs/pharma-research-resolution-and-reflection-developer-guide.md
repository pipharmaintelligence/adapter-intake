# Pharma Agent response recovery and portfolio reflection — 0.1.17

## Objective

Reduce avoidable whole-run interruptions from malformed research responses,
support companies with different amounts of public information, and add deliberate
portfolio reflection. Keep accepted claims grounded, company scope isolated,
execution finite, and Skill storage/history owned by Core. This is one additive
adapter-intake release, delivered through the existing promotion workflow.

## System context

The company-13 production preview `e30f37b0-9f54-45a0-8205-3d8765cd5ae2`
failed at `portfolio_researcher / research_payload / invalid_schema`. Its portfolio
Agent had admitted citations. The original business response was not retained,
so the exact rejected field remains unknown. Offline fixtures demonstrate the
new handling; they do not reconstruct that hidden response or prove live quality.

Company Scope supplies the retained `CompanyContext`. Intelligence does not query
Companies again. Python calls the existing trusted `inputs.invoke_agent` and
Skill helpers; Assets/Core own provider execution, credentials, storage,
retention, retries, deadlines and publication. The evaluation asset remains 0.2.3.

The published Fixed Skill remains the required, pinned global methodology and
schema/benchmark baseline. **Company-specific learned methodology is optional.**
`dynamic_skill_not_initialized` yields an empty procedural hint in preview; access,
delivery or validation failures are not disguised as absence. Factual memory is
evidence context, not authority to override methodology.

## Approach and model

```mermaid
flowchart TD
    C[Retained CompanyContext] --> P[Four bounded methodology planning chunks]
    M[Optional company methodology] --> P
    P --> A[Portfolio review pass 1]
    P --> B[Market research once]
    P --> D[Regulatory research once]
    M --> A
    A --> N[Deterministic cleanup and validation]
    N -->|Recoverable schema rejection| R[Registered response resolver: one call]
    R --> V[Revalidate shape and preserve original evidence]
    V -->|Valid| F[Validated portfolio result]
    N -->|Valid| F
    V -->|Still invalid or changed facts| G[Withhold response; retain previous valid result or explicit gaps]
    F -->|Requested total is 2 or 3| Q[Reflect on previous validated result]
    Q --> N
    F --> J[Join final role evidence]
    G --> J
    B --> J
    D --> J
    J --> S[Strategic reasoning then evidence critic]
    S -->|Valid support and disposed gaps| Y[Synthesis and benchmark]
    Y --> O[Retained preview: repairs, pass trace, evidence and completeness]
    Y -->|Complete and eligible only| W[Existing guarded Skill apply lane]
```

The three initial research lanes run in parallel. Only portfolio review repeats,
sequentially within its lane. Each pass uses the same company context and role
scope. Reflection consumes the previous validated research object, bounded admitted
citation projection, role plan, fixed evidence rules and relevant optional learned
methodology. It may seek new grounded evidence through the existing two-step
research chain. It is not a search-free rewrite and does not repeat market,
regulatory, planner, strategic, critic or benchmark roles.

The final strategic/critic/synthesis stages run once, after research joins. The
resolver has no search authority and never supplies citation authority. All
citations come from admitted research execution. Role-level citations remain
role-level evidence; this release does not create claim-to-source mappings.

### Total portfolio passes

Add this field to the existing `variables` object:

```json
{"portfolio_review_passes": 2}
```

| Value | Behavior |
|---|---|
| omitted or `1` | Initial portfolio review, using learned methodology when available |
| `2` | Initial review, then reflect on and improve its validated result |
| `3` | Initial review and two successive reflection passes |

These are **total passes**, not additional retries. Only integers 1–3 are accepted;
booleans, strings, zero and larger values reject before Skill/Agent calls. Missing
company methodology does not block any preview pass. Apply retains its existing
initialized-package, quality, CAS, readback and history requirements. A first Skill
package uses the ordinary Core Skill ZIP upload lifecycle shared by fixed and
dynamic Skills; no additional persistence service or Skill publish policy is added.

### Response resolution

1. Validate the typed runtime envelope and expected company/role/schema identity.
2. Deterministically restore section/subsection order only when the complete exact
   ID set is present. Normalize casing/whitespace only for known confidence and
   evidence-kind enums. Reuse retained primitive whitespace normalization. Unknown
   IDs, aliases, booleans and facts are not guessed; text is never truncated.
3. Validate the business payload using a version-owned diagnostic validator that
   preserves the retained validator's ordering, accepted values, defaults and bounds.
   Emit static `role`, `stage`, `field`, `rule` identifiers, never response prose.
4. For a business-schema rejection, invoke declared Agent
   `research_response_resolver` once for that research pass. Pass only declared
   business fields, the static diagnostic and exact typed response contract.
5. Validate its result again and deterministically compare original versus repaired
   evidence. Claim cardinality, statements, section scope, existing factual section
   content by section/subsection identity and uncertainties are preserved. Valid
   evidence/inference metadata cannot change; invalid confidence can only become
   `low`, and invalid evidence kind cannot become a stronger grounded claim. Unknown
   dates can become null. Only explicit boolean strings can become booleans.
6. If repair remains invalid or changes evidence, withhold it. Keep an earlier
   validated portfolio pass when available; otherwise emit canonical evidence-gap
   text with no accepted claims. Stop further reflection in that lane. Other
   research lanes continue. The critic must dispose every claimless role's planned
   requirements as `unresolved_evidence`; missing accounting still rejects.

### All-role backup amendment

`research_response_resolver` is the same registered Agent, now used as the one-time
schema backup for all eight ordinary role contracts: methodology planner, the three
researchers, strategic analyst, evidence critic, synthesizer and benchmark reviewer.
The four planner chunks and each portfolio/benchmark invocation are distinct original
calls. One backup is allowed for each rejected original call, not an extra research
iteration and not one global backup for the whole batch. Its chain has one provider
step and zero tools. Transport retries remain runtime-owned.

The dispatcher reserves `(company_id, original_role, invocation_ordinal)` before
backup. Reservations are never refunded; duplicate dispatch and repairing the
resolver itself reject. The backup's response passes JSON diagnostics and its
original role validator once. There is no loop back to another backup.

```mermaid
flowchart TD
    A[One original Agent invocation] --> P[Generic terminal JSON parser]
    P --> D[Role diagnostics and deterministic cleanup]
    D -->|Valid| V[Continue with validated result]
    D -->|Invalid original business schema| B[One reserved backup Agent call]
    B --> Q[JSON parser and original role validator]
    Q --> E[Preserve original evidence and decisions]
    E -->|Valid| V
    E -->|Still invalid| W[Withhold response; no second backup]
    W --> R[Research: prior valid pass or explicit gaps]
    W --> C[Mandatory preparation: incomplete company preview]
    C --> N[Skip dependent work and writes; next company]
    R --> G[Mandatory critic and benchmark gates]
    V --> G
```

The normal typed-object fast path preserves its original citation envelope without
copying or parsing it again. Complete JSON inside Markdown fences, triple quotes,
single outer quotes or JSON-string wrappers is decoded through at most four layers.
The parser never extracts an object from prose or evaluates Python. Truncation,
multiple fenced objects, single-quoted JSON keys, non-object values and non-finite
numbers reject. The generic Assets terminal parser must perform this cleanup before
creating `agent_result.v1`; otherwise a fenced response never reaches the adapter.
It preserves the original compatibility text and existing privileged-material checks.

For non-research roles, deterministic cleanup can normalize known enum casing,
primitive whitespace, singleton array representations and complete known ordering.
The backup receives declared business fields only. Its output must preserve the
same normalized business content, including negative critic/coverage decisions,
IDs, cardinality and memory text. It cannot add missing approval or factual content.
Role-specific validators and subsequent quality gates remain authoritative.

If a non-research preparation response remains invalid, the adapter stops dependent
work for that company, retains an explicitly incomplete preview, and continues the
next company. `agent_schema_incomplete=true`, `quality_gate_passed=false`,
`unresolved_agent_responses` and static `agent_response_recovery_trace` explain it.
No memory/methodology proposal or verdict is invented; optional review packets have
null replacement text, no accepted claims and `mutation_eligible=false`. This does not silently approve a failed
critic or substitute a zero score for a successful benchmark.

Committed benchmarking also has one backup. A persistent schema failure there
remains a reported failure after a verified write, rather than being described as
an unwritten/incomplete preparation. Post-commit storage/readback/history errors
remain hard boundaries; a schema backup cannot undo a committed mutation.

This is bounded recovery, not a promise that every asset run succeeds. Wrong-company
or wrong-role envelopes, provider/runtime failures, exhausted deadlines, invalid
citations, unsupported claims and quality rejection remain hard boundaries. They
are not converted into apparent success or extra unscheduled repair calls.

### Relaxed constraints for different companies

Research no longer needs to manufacture a positive claim in every specialist lane.
A role can return an empty claim list, explicit uncertainty and canonical evidence-
gap text. Such a role may have no citations because it accepts no positive claims;
the critic must explicitly dispose every corresponding plan obligation. Any role
with positive claims still needs admitted citations. Required sections, real JSON
types, company/role identity, inference labeling, text/list bounds, critic rejection,
unsupported-claim checks and benchmark non-regression remain enforced.

### Finite budgets

One resolver attempt is reserved per ordinary Agent invocation; unused reservations
produce no calls. Ordinary call quotas remain
separate, so a repair reservation cannot authorize an extra research/planner call.

| Portfolio passes | Planned calls/company preview / apply | Maximum repair calls/company preview / apply | Maximum total calls/company preview / apply |
|---|---|---|---|
| 1 | 12 / 13 | 12 / 13 | 24 / 26 |
| 2 | 13 / 14 | 13 / 14 | 26 / 28 |
| 3 | 14 / 15 | 14 / 15 | 28 / 30 |

The five-company ceiling remains: at most 140 logical preview calls or 150 logical
apply calls with three passes and every possible repair. Each research invocation
has two provider steps; the resolver has one. Provider attempts/retries are governed
separately by the runtime. The existing 1,800-second asset deadline, provider timeouts,
runtime input ceilings and optional 512 KiB review-packet/output bound remain.
Three passes are not guaranteed to fit every real execution deadline. Large company
populations belong in the existing generic partition/epoch orchestration, not this
five-company inner adapter loop.

## Changes made and review evidence

Only the new 0.1.17 adapter imports the new version-owned research diagnostics,
cleanup and pass configuration. Shared `agent_contract.py`, `input_contract.py`,
`dossier_contract.py`, `methodology_contract.py` and historical helpers remain
unchanged. All changed Agent prompts have new contract versions; the repair
Agent has its own declared version and the same shared provider registry entry.

Company results retain repair receipts and `portfolio_review_trace` with pass
numbers, status, before/after result hashes, optional methodology usage and counts.
`research_resolver_agent_call_count` separates repair calls from research calls.
`unresolved_research_responses` contains static diagnostics only.

An unrepaired response sets `research_incomplete=true` and dossier
`business_result_state=incomplete`. Transport completion means a retained preview
is available, not that all research succeeded. Its company's memory mutation is
ineligible and no methodology replacement is produced. All memory and methodology
writes for that company are withheld, not just the invalid document fragment.
Other approved companies continue independently, including in apply mode. Valid
research sections remain in the retained preview with explicit gaps; mandatory
preparation failure retains diagnostics rather than inventing an approved dossier.

Not-applicable or no-evidence specialist work is different from invalid schema.
A valid claimless response with explicit uncertainty and critic disposition is
ordinary reviewed work: it does not set `research_incomplete`, consume a backup,
or by itself block that company's memory/methodology eligibility. No positive
claim or evidence is invented to fill such a section. Subsequent company quality
and benchmark gates still apply.

`publish_dossier` preserves the existing runtime output-policy readiness signal.
It does not perform a storage upload or prove canonical publication. An incomplete
company does not reject the entire batch or suppress other companies' approved
results. The full returned report keeps the company's gaps and batch
`business_result_state=incomplete` visible; it is never labeled fully reviewed.
Actual output admission/publication stays runtime-owned and must preserve these
markers. No new per-company publication writer or alternate storage lane is added.

## Modularity impact

No Core/Assets runtime business special case, credential, direct HTTP client,
storage backend, new queue, manual wheel build or environment setting is introduced.
The Assets parser improvement is generic syntax cleanup, with no pharma identity,
business schema or approval rules in the runtime. Valid existing JSON behavior is
preserved; complete wrapped objects become accepted after the same safety checks.
The resolver is an ordinary registered Agent role. Fixed and dynamic Skills remain
on the existing shared lifecycle, with their respective binding/mutation contracts.
Promotion preserves existing adapter versions and shared helper bytes.

## Validation and delivery

Offline tests cover diagnostic parity, no raw-value projection, harmless cleanup,
strict evidence-preserving Agent repair, unresolved-response withholding, finite
quotas, one/two/three-pass sequencing, company isolation, optional methodology,
critic gap accounting, review-packet retention and unchanged default business fields.
The full suite also runs pinned historical adapters and the unchanged evaluation
fixtures. These tests use fakes and make zero provider/storage writes.

Use the official Assets **Promote adapter-intake package PR** workflow with the
exact green intake commit and this adapter's `adapter.yaml`; target current Assets
`main`, leave `allow_manifest_removals=false`. The intake manifest intentionally
describes only the current source. The materializer preserves omitted historical
versions/modules and merges them into the aggregate manifest; listing an old
version without its old module can suppress preservation and is incorrect.

Before merging the generated promotion PR, verify every existing identity/module
and shared helper is preserved, the new Agent contract passes package/registration
checks, and CI is green at its current head. Use only the official resulting runtime
artifact when deployment is required. Do not bump/build a wheel locally or replace
the live E worker while another run is active. A future authorized company-13
preview must request retention and inspect both completeness and repair/pass counters
before any claim of live success or eligibility.

## Risks / open questions

The resolver is an additional paid call only on rejection and may itself fail or
propose an unsafe repair; deterministic validation never accepts that proposal.
Reflection can increase cost or reduce quality; more passes are not automatically
better. Benchmark non-regression and independent semantic review remain necessary.
This release does not recover the original failed response, prove full WP1–10
completion, make missing methodology writable without an initialized package,
or solve the separate generic retention crash-consistency gap.

## Optimization review

- **No extra normal calls:** exact typed JSON is a fast path. Valid wrapped JSON,
  known enum casing and singleton arrays are fixed deterministically before paying
  for backup. Default review depth remains one pass.
- **Finite recovery:** exactly one logical backup reservation per failed original
  invocation; zero tools, one provider step, no recursion/refund and independent
  ordinary/backup budgets. Existing asset and provider timeouts still apply.
- **Less interruption:** unrepaired optional research is withheld; unrepaired
  mandatory preparation retains an incomplete company and allows the batch to
  continue. Dependent stages are skipped rather than paid for using invalid inputs.
- **No optimistic repair:** role/company identity, factual content, negative
  quality decisions, benchmark scores and exact memory proposal text stay protected.
  Absence of a valid verdict means no eligible update.
- **Inspectable diagnostics:** static role/stage/field/rule receipts, parser layer
  counts, original invocation ordinals and resolver counts; no raw response prose
  in failure/status projection. Canonical review-packet digests are recomputed after
  explicit incomplete-company entries are added.
- **Compatibility:** prior release modules/shared helpers remain byte-identical;
  global parser cleanup has no business-specific branch. Existing direct inputs,
  CompanyContext, Skill lifecycle, storage ownership and orchestration lane remain.
- **Remaining limits:** arbitrary malformed provider JSON rejected before an Agent
  result exists cannot be repaired by an adapter that never receives it. This change
  recovers exact valid wrapped JSON at that boundary. Provider/transport faults,
  genuine critic rejection and post-commit proof failures are not hidden as success.
