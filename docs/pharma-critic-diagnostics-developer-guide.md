# Critic diagnostic delivery and recovery

## Objective and evidence

Make failed production critic validation actionable without weakening quality
or retaining provider payloads. The October 9 run
`8ff89da6-2870-431a-8e2a-94d4e60a745d` reached ten completed Agent invocations,
including the critic, but not synthesis. Its exact failing rule cannot be
recovered from the permitted result projections. Do not label that unknown
failure a missing-methodology error or treat a new injected failure as proof of
its cause.

## Contract and ownership

`critic_diagnostics_v0_1_13.py` belongs to this intake version. It mirrors the
retained critic contract's validation order, limits, defaults and normalized
output, using its primitive validators. The shared `agent_contract.py`, frozen evaluation executor, and pinned production
source snapshot stay unchanged. The historical manifest is pinned under
`tests/fixtures/baseline-production-0.1.12.asset.json`, outside the promotion
surface, with a digest guard. The production promotion manifest declares only
0.1.13; the official materializer retains previous packaged versions.
Contract regressions compare rejection and
acceptance with the retained validator and verify safe rule/field projection.

The adapter emits the existing reviewed failure code
`pharma_agent_business_schema_invalid`. This code covers both payload rejection
and the existing business-quality stops; read `proof_failure_detail.stage` to
distinguish them. Runtime accepts only the generic bounded proof contract:

```json
{
  "schema_version": "proof_failure_detail.v1",
  "proof_kind": "agent_contract",
  "role": "evidence_critic",
  "stage": "critic_payload",
  "rule": "bounded_list_required",
  "field": "unmet_plan_requirements"
}
```

`field_invalid` means the retained primitive rejected that named field's type,
text/token shape, length, list size or uniqueness. Specific cross-reference,
shape and enumeration failures have distinct rules. Nested fields use underscores
so each identifier satisfies the existing runtime's 64-character safety bound.
Never include actual values, indexes, raw exception text or provider responses.

## Quality stops and recovery

| Rule | Existing stop | Next investigation |
| --- | --- | --- |
| research_citations_missing | A research role has no admitted citations | Inspect that role's safe grounding receipts |
| critic_rejected | Critic recommendation is fail | Review a permitted retained evidence artifact; do not override the verdict |
| citation_coverage_insufficient | Critic coverage is insufficient | Examine evidence coverage |
| unsupported_claims_remaining | Unsupported claims remain | Repair evidence generation or correct reviewed contract semantics |
| required_sections_missing | A mandatory section is missing | Check role coverage and source availability |
| planner_requirements_unsatisfied | A requirement remains unsatisfied | Distinguish a workflow omission from explicitly unresolved evidence |

Explicit `unresolved_evidence` still passes this gate under the original contract;
`unsatisfied` still stops. This change does not deduplicate claims, change Agent
prompts, retry paid calls, relax gates or authorize writes after failed review.

## First-run methodology and persistence

Core owns partition resolution and Dynamic Skill persistence. A reviewed
`dynamic_skill_not_initialized` read allows the original empty methodology state.
Other readiness, active-object and delivery failures remain errors. The existing
late pre-apply guard still rejects an eligible methodology candidate if its
methodology handle is absent, before mutation. Read fallback does not create a
Skill or grant create-if-absent authority. First-object creation needs a separate
Core/SDK contract and proof; do not fabricate a partition, object, candidate or
upload token in the adapter.

## Release and qualification

1. Run promotion-shape and complete deterministic production tests. Run the
   frozen evaluation baseline suite to prove no baseline edits.
2. Commit and push only the intake changes. Dispatch
   `adapter-intake-promote-pr.yml` in Assets from `main`, pinned to the full
   source commit, with manifest removals disabled.
3. Review the generated PR. All prior manifest/runtime identities and their
   runtime files must remain intact. Agent/Skill definitions and runtime package
   version must remain unchanged. The official workflow owns ECS package builds.
4. Exercise the promoted import and the actual installed generic isolated runner
   offline using injected inputs: malformed critic and quality-stop details must
   survive, with no provider calls or mutation. This is diagnostic transport proof,
   not live business success.
5. Before a future live run, admit the exact new version and Companies binding,
   verify the E worker's catalog/module hash, and use a preview-only one-company
   request with explicit result retention. Use the real `/assets/preflight`
   contract for remote preflight; older installed admission helpers may call the
   launch endpoint. Do not use them as read-only checks.
6. Inspect the retained preview or the new safe rule. Only a complete reviewed
   business result and eligible memory/methodology candidates can justify apply.
   Do not rerun the paid path solely to compensate for missing result retention.

Existing running/published versions stay usable. No wheel upgrade, worker
restart, environment migration or new output policy is part of this repair.
A live success and first-object methodology apply are not established by tests
or promotion CI. Record those remaining gaps explicitly.

## Local qualification on 9 October 2026

The complete production suite passed 272 tests, including the retained-baseline process
that reruns 50 existing orchestration, apply-safety and budget regressions.
The frozen evaluation suite passed 90 tests; the promotion-shape guard passed.
Payload regressions cover more than 65 malformed shapes and unchanged valid
normalization. Injected critic failures stop the actual adapter graph before
synthesis and either mutable Dynamic Skill role.

A separate offline proof loaded the exact candidate/support hashes through the
actual installed E isolated runner on runtime 0.1.104, using injected inputs and
no test SDK stubs. Malformed critic, quality rejection and successful first-run
preview cases passed with zero provider and mutation calls. This proves installed
runtime diagnostic transport, not live evidence quality or first-object apply.
The worker, installed catalog and runtime wheel were not modified.

## Architecture references

- [PR #458](https://github.com/piusaibah/assets/pull/458)
- [methodology-driven specialized review design](https://github.com/piusaibah/assets/blob/1eb32db0353a3f20ef2fe5121d8a9258bfaea4be/docs/observability/methodology-specialized-review/README.md)
- [PI-1972](https://linear.app/pipharma/issue/PI-1972)
