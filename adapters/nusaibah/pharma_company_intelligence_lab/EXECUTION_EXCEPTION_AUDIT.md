# Execution exception and continuation audit

Date: 13 October 2026. Baseline: production pharma 0.1.38, proposed 0.1.39,
Company Scope 0.1.0, E company-range operator, runtime 0.1.105.

## Objective

Stop treating expected business outcomes as execution failures. Preserve paid
work, keep independent sections/companies running, and publish only eligible
content. A completed review need not produce a memory mutation or an upload.

## System Context

This audit covers the current production preparation/research/planner/critic/
synthesis/publication path and the E range runner. It also inspects the installed
Company Scope selector/result contract. Historical helpers are discussed only
where the current version calls them. This is not a claim that every exception
in unrelated Assets, Core, or other adapters has been audited.

Company 59 demonstrated the boundary: all 13 Agent calls and the workflow
completed, but an empty critic-supported fact set became `UnresolvedAgentResponse`,
then `withheld`, then `enrichment_publication_not_complete` in the range runner.
There was no schema error, transport retry, or upload attempt.

## Approach

Traced raises through their actual catch sites and the operator's checkpoint
advancement. Distinguished expected no-ops, retained incomplete work, and hard
failures. Used deterministic tests and retained technical evidence; no new paid
run was launched during this audit.

## Changes Made

The following three expected outcomes are corrected in proposed 0.1.39:

| Case | Previous stop path | Corrected behavior |
| --- | --- | --- |
| All resolved research has no usable facts | `company_preparation_v0_1_36.py`: `no_usable_research_evidence`; caught into incomplete state; publisher withholds; operator stops | Complete `no_change`, retain limitations, skip dependent synthesis/writes |
| Critics leave zero supported facts | `section_critic_v0_1_28.py::select_validated_sections`: `no_supported_enrichment_after_section_critic`; same escalation | Complete `no_change`; do not fabricate a critic pass or publish rejected facts |
| Deterministic memory delta is empty with no initial package | `automatic_publication_v0_1_38.py`: `initial_memory_evidence_missing` | No memory creation; optional eligible methodology keeps its normal path |

The E operator now recognizes the explicit verified no-op receipt without
requiring a nonexistent upload readback. Actual upload/readback/history failures
remain errors. Its installed default asset version is unchanged; 0.1.39 still
requires official promotion and activation.

## Modularity Impact

No Core or generic runtime source change is needed for these no-op semantics.
Storage, governance, identity, and concurrency authority remain unchanged.
Business continuation belongs in the adapter; range advancement/checkpoint
semantics belong in the E operator. Both use the existing execution lane.

## Validation and Findings

### Continuation inventory

P0 means an observed expected outcome incorrectly stops the production operator.
P1 identifies a reachable or reproduced continuation gap repaired by the current continuation extension.
These are priorities, not assertions that every listed exception is unnecessary.

| Priority / state | Condition | Current behavior and scope | Safe direction |
| --- | --- | --- | --- |
| P0 — corrected | Zero supported evidence after a resolved review | Typed exception becomes company-wide withholding and range stop | Successful no-op, limitations retained, no fabricated upload |
| P0 — corrected | No usable research evidence with valid responses | Same business-to-error escalation | Successful no-op; genuine unresolved responses stay distinguishable |
| P0 — corrected | Empty new memory delta | An absent package can trigger `initial_memory_evidence_missing` despite no mutation being needed | Do not request initialization; retain any independent eligible methodology |
| Already handled | All facts duplicate existing memory | `section_enrichment_v0_1_28.py` excludes duplicate fact IDs/statements; unchanged candidate gets `no_change` | Preserve; no Agent rerun solely to obtain a write |
| Already handled | No optional learned methodology / memory absent on first review | Read helpers allow explicit absence; no methodology candidate becomes `no_change` | Preserve; no blank Skill or false initialized state |
| Already handled within adapter | One rejected research section with valid siblings | Section filtering excludes its claims; valid sections can synthesize/publish | Preserve local withholding; do not require all sections to pass |
| Corrected | All content problems remain after the one schema backup | Recovery retains unresolved work; with no eligible sibling the publisher withholds and the operator stops the range | Retain a completed-incomplete company and continue the next independent company; do not mark invalid responses as a clean no-op |
| Corrected | One planner chunk remains unresolved | `planner_execution_v0_1_33.py` raises on any noncompleted planner outcome, so validated planner siblings are not used | Execute only actually validated planned sections; retain unplanned sections, never invent a plan |
| Corrected at runner boundary | Paragraph/subsection cannot fit intact, role-call reserve, chunk-call cap, or consolidation time reserve | `ChunkCoordinator` emits typed diagnostics; pieces are omitted; valid siblings survive. If none survive, incomplete publication halts the range | Keep the bounds and diagnostics; advance a retained incomplete item rather than retrying paid work or enlarging limits blindly |
| Corrected — reproduced offline | Two companies share role budgets | One `ChunkCoordinator` owns role counters for the whole execution. Critic ceiling 10 can be consumed by company one, leaving company two's critiques unresolved | Per-company phase accounting under a bounded shared execution budget, or explicitly restrict each work item to one company. Current E runner already uses one company per workflow |
| Corrected | No validated synthesis chunks remain | `downstream_chunks_v0_1_33.py`: `no_validated_synthesis_chunks`; retained incomplete state; publication/operator stop | Preserve validated research and diagnostics; skip synthesis-dependent mutations for that company, continue the next company |
| Corrected | Candidate fact IDs are invalid, duplicated, or unknown | `candidate_validation_v0_1_21.py` throws; orchestration retains incomplete company; operator still halts | Continue independent work with the candidate excluded. Never relax IDs or publish invented references |
| Corrected — regression tested | Source claim or toolkit-call budget exceeded | `source_evidence_v0_1_35.py` raises `ValueError` for `pharma_source_claim_limit` / `pharma_source_toolkit_call_limit`; the chunk catch handles only selected typed errors | Verify reachability with adversarial fixtures, then map model overproduction/quota exhaustion to scoped diagnostics. Keep caps and stop forged toolkit outputs |
| Corrected — regression tested | Research contract resolver returns no payload | In `research_execution_v0_1_33.py`, the `validated` guard covers source verification but the following claim-ID loop dereferences `validated` unconditionally | Add an exhausted-contract regression; preserve its diagnostic and valid sibling payloads. Do not let an accidental `TypeError` replace the intended recovery outcome |
| Corrected | Requested company is genuinely absent from an exact governed result | Company Scope `assemble_contexts` raises `result_set_mismatch`; E `scope_complete` also insists on exactly one matching row | Distinguish verified absence from wrong/partial/unauthorized results; skip only verified absent/ineligible IDs without paid calls. Keep corporate and origin checks |
| Corrected | Aggregate retained-result admission exceeds 448 KiB | `orchestration_v0_1_38.py` replaces every company state with an incomplete retention diagnostic before mutation | Preserve the no-write guard; isolate oversize work to its company or use an approved retained reference. Do not erase fitting siblings or truncate candidates and publish them |
| Checkpoint boundary, not a business error | Session/submission/poll budget ends after accepted work | E operator stops but persists submission intent/UUID and current company | Resume the same UUID/checkpoint with bounded polling; never repeat an ambiguous POST or paid workflow |
| Required hard stop | Scope/corporate/role origin mismatch, denied access, forged toolkit result, invalid retention identity/checksum | Authority or integrity cannot be established | Stop; never relabel as no evidence/no-op |
| Required stop/reconciliation | Stale baseline, concurrent first creator, upload failure, acknowledged write with unverified readback/history | A required mutation is unsafe, failed, or ambiguous | Preserve receipt and checkpoint; inspect/reconcile the exact operation before another write. Do not report successful publication |

### What the tests establish

- A fully resolved but critic-rejected company returns `no_change`, keeps its
  original memory/methodology, and invokes no synthesis or mutable Skill role.
- Missing packages are not created for this no-op.
- Supported reviews keep the existing publication path.
- Empty deterministic memory deltas do not request first-package creation.
- The E runner continues from a verified no-op to the next company and reports
  `uploaded=false`; forged upload metadata in a no-op is rejected.
- Schema exhaustion, unresolved critic chunks, and genuine Skill delivery
  failures are not falsely relabelled as clean no-ops.

The two-company budget interaction was reproduced while developing the mixed
case regression: the second company's section diagnostics reported
`phase_call_budget_reserved_for_downstream`. It is separate from company 59's
one-company live quality rejection and is repaired by company-scoped phase counters while preserving the global ceiling.

## Risks / Open Questions

1. The listed current-path continuation cases are repaired and tested offline.
   This is not a claim about every exception in unrelated assets or every possible
   live provider/storage failure. Live smoke remains required after promotion.
2. The runner distinguishes completed no-change, retained incomplete work, and
   failed/ambiguous mutations. Incomplete work advances with last_incomplete and
   its run UUID; last_successful is preserved. No upload success is invented.
3. Planner, synthesis, candidate, quota, retention and per-company budget
   isolation have deterministic regressions. Global time, call and concurrency
   ceilings remain enforced; hitting them can leave truthful incomplete work.
4. Source trust, exact spans, role identity, storage admission, optimistic
   concurrency, and receipt verification must remain enforced.
5. Promote through the existing workflow after review. No manual runtime upgrade,
   repeated provider run, schema-backup loop, or silent exception swallowing is
   part of this audit.

## Final continuation extension

Version-owned 0.1.39 helpers retain validated partial plans, contain exhausted
research contracts without NoneType failures, convert source quotas to scoped
diagnostics, count role budgets by company, and compact only an oversize company
before mutation. Required storage and integrity failures remain stops.

Company Scope 0.1.2 adds a verified missing-ID result using the unchanged approved
binding and exact-envelope/corporate guards. The E runner skips only this explicit
trusted result; it never infers absence from a generic failed workflow.

The single **Annex: Need Review** is a compact table: Section/subsection,
Paragraph, Issue, Ref. Sources use simple [1] references. No full text, quotes,
stack traces, or duplicated global error rows are propagated. Unknown locations
remain unlocated. The table is sized before writes and remains in the retained
dossier for partial publication, no-change, and incomplete outcomes.
