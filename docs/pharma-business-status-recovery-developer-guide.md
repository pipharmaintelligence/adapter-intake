# Pharma 0.1.23: retain non-completed business responses

## Observed failure

The company-14 0.1.22 run `5b22cf7a-a582-4eaf-9df9-43db8c4f1da3`
failed on 11 October 2026 with `pharma_agent_status_invalid`. The live Core
session admitted 32,000 tokens and 600 seconds per request. Eight Agent
invocations completed: one benchmark, four planner chunks and three two-step
researchers. The receipts report 11 provider turns, zero retries and no provider
failure. The second portfolio pass and dependent analysis did not run.

The exact failing check was the business payload's top-level `status !=
"completed"`. This is separate from the runtime envelope's completion status.
The historical extractor treated it as fatal and excluded it from response
recovery. Its exception did not supply role/field proof metadata. The retained
failure projection cannot identify the particular researcher or original value;
do not claim those details are known. The failed run retained no dossier.

## Handling and authority

0.1.23 preserves the runtime's successful envelope requirement and exact company
and role identities. A non-completed, missing or malformed **business** status is
retained as an unresolved response with the static diagnostic:

```json
{
  "schema_version": "proof_failure_detail.v1",
  "proof_kind": "agent_contract",
  "role": "portfolio_researcher",
  "stage": "agent_business_status",
  "rule": "business_status_not_completed",
  "field": "status"
}
```

The example role is illustrative, not an attribution of the live failure.
No model prose or arbitrary status value is emitted in this diagnostic.

| Boundary | Behavior |
| --- | --- |
| Original business status not completed | Record the issue; withhold that invocation's work. Do not rewrite the status and do not call a resolver to convert a negative result into success. |
| Research status unresolved | Keep validated sibling roles; an invalid later reflection keeps its previous validated pass. Stop further passes for that role. |
| Planner, benchmark, analysis, critic or synthesis status unresolved | Return the existing incomplete company state with prepared evidence; continue the next company. |
| Backup business status not completed | Retain an unresolved issue after the one already permitted backup. No second backup. |
| All research unavailable | Skip dependent paid stages through the existing no-evidence branch. |
| Runtime not completed, malformed runtime result, wrong company or wrong role | Remain strict failures. |
| Provider transport, authority, call/time budget or commit-integrity failure | Existing runtime enforcement remains unchanged. |

An incomplete retained result is useful review evidence, not an approved company
assessment. Its memory/methodology writes remain withheld. Valid work remains
reviewable; unresolved or unsupported work must not enter authoritative Skills.

## Compatibility and bounded execution

The 0.1.22 Agent definitions are reused exactly: response-budget prompts,
32,000-token ceilings, 600-second requests, models, thinking, search and authority
are unchanged. No new Agent identity or generic runtime version is introduced.
The existing 1–3 portfolio passes, one backup per invocation, call ceilings,
company limits and 1,800-second asset deadline remain intact.

The four preparation modules are version-owned forks because changing 0.1.21's
support bytes would also change already promoted 0.1.21 and 0.1.22 identities.
Compare each new module against its 0.1.21 counterpart to review the narrow
status-handling changes. Unchanged contract, evidence, selection, methodology
and result modules are reused. Historical entrypoints and helper bytes stay
unchanged; no monkey patch, global exception suppression or separate runtime
lane is added.

## Validation and delivery

Run the complete pharma deterministic suite and intake promotion-shape guard.
Regressions cover all eight original roles, sibling and next-company retention,
failed reflection, missing/malformed/negative status, a failed backup, strict
runtime/company/role failures, historical behavior and zero mutation.

Use the existing official promotion workflow against the clean pushed intake
commit. Preserve all historical identities and validate packaged imports and
module hashes. Install only its official artifact after review/merge; retain
runtime version 0.1.105. Do not patch the E venv or retry the old failed run.

A subsequent live preview must prove actual two-pass completion, retained
claim evidence and independent review. This version still rejects `memory_mode`
`apply` before helper/provider calls: an admitted independent-review receipt
consumer is not implemented. Budget or recovery success must not be described
as publication. Core remains the owner of Dynamic Skill persistence, storage
and version history; existing stored memory/methodology must be preserved.
