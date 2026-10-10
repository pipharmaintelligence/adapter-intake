# Pharma first-run preview — 0.1.18

## Objective and boundary

A company can have a valid retained CompanyContext before it has any Dynamic
Skill memory package. This release permits that company's preview. Company Scope
remains the Companies reader; Core remains the sole storage/history/mutation
authority. No initialization lane, synthetic Skill, binding fallback, provider
retry loop, runtime upgrade, or direct storage access is added.

## Execution

1. Validate retained Company Scope 0.1.0 context and the pinned Fixed Skill.
2. Resolve company memory through the existing read-only Dynamic Skill helper.
   Only `dynamic_skill_not_initialized` is optional, and only in preview mode.
3. If initialized, retain the existing before-benchmark Agent path. If absent,
   pass empty memory to research and mark every fixed benchmark question
   `not_covered`, in exact question order. This deterministic baseline describes
   missing stored memory, not a research finding or an Agent evaluation.
4. Load learned company methodology when available. Its absence still permits
   preview; the Fixed Skill remains required.
5. Run bounded planning and research. `portfolio_review_passes=2` means one
   initial portfolio review and one reflection on that result. It does not run
   the entire asset twice. Market/regulatory research run once.
6. Apply unchanged critic, citation, synthesis and proposed-memory benchmark
   checks. Retain exact candidate bytes and explicit baseline absence when
   `retain_review_packet=true`; generic preview retention remains a separate
   execute-time request.

The absent-memory result adds `memory_initialized=false`,
`memory_initialization_required=true`, and
`benchmark_before_basis=deterministic_absent_memory`. Baseline digest and section
are null. A prepared memory proposal can be `preview_ready` while
`memory_mutation_eligible=false`: candidate readiness is not write authority.
Its packet carries `initialized=false`, `initialization_required=true`, a
deterministic benchmark basis, and the checksum of the complete packet.
Review state remains `not_reviewed`, apply authority false, and committed
benchmark/readback absent. The adapter does not initialize either Dynamic Skill.

Existing-memory results add explicit baseline metadata but retain prior business
behavior and calls. First-memory previews use 11/12/13 ordinary logical Agent
calls for 1/2/3 passes. Initialized-memory previews use 12/13/14. Existing hard
ceilings 24/26/28, one recovery per original call, maximum five companies,
1,800-second execution deadline and 512 KiB review-output ceiling remain.

## Failure boundaries

Access denial, transport failure, integrity errors, an empty initialized package,
missing required sections, oversized memory, wrong company identity and actual
quality rejection remain failures. Do not catch generic exceptions as absence.
Apply still checks all companies' initialized memory and methodology before its
first provider call and retains existing mutation, CAS, history/readback checks.
Schema recovery and incomplete-company behavior are inherited from 0.1.17.

## Delivery and verification

Use an intake PR and the official Assets `adapter-intake-promote-pr.yml` workflow
pinned to its exact reviewed commit. Preserve previously admitted identities and
shared helper bytes. Runtime 0.1.105 already supplies the necessary helpers; do
not bump it or patch installed modules. Install only the workflow-produced
artifact after verifying its commit, checksum, catalog and preserved identities.

Asset registration and Agent provisioning are distinct prerequisites. Before any
paid run, inspect every `agents` contract using the server's existing
`AgentRuntimeProvisioningService`; provision the exact packaged definitions
through the existing service/command when absent. Do not overwrite older chain
versions or infer Agent readiness from asset preflight. Verify the worker's exact
catalog, real read-only Skill delivery and retained CompanyContext. Provider
authority remains server-owned.

Offline regressions cover absent memory with two passes, retained exact proposal
bytes and checksum, zero mutable calls, mixed initialized/absent companies,
unchanged initialized behavior, errors that must propagate, and apply rejection
before any Agent call. Run production and frozen-evaluation suites separately.

Live proof is separate from offline tests: run company 13 with one total pass,
then company 14 with two total passes after promotion. Retain run UUIDs, failure
receipts, exact results, pass traces and call counts. Compare canonical memory
and methodology before/after; preview must change neither. A completed workflow
may contain an incomplete company; inspect its actual dossier and recovery trace
before declaring business-quality success. Do not rerun paid work merely to
recover observability values or turn an unresolved result into a claimed pass.
