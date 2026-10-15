# PI-2061 Assets and repository handoff

Reviewed baselines: adapter-intake 48bbdecc944a0458d00b40ec50cecffbdce18515;
Assets d850262f092422decfbd2795e5bdc2954dce6f1b. Recheck current source before changes.
No Assets, Core, UI, deployment or installed-wheel change is included in this PR.

## A1. Child-owned Agent session - Assets/trusted runtime, blocking

Inspect app/Services/Observability/Agents/DirectRuntimeCallablePlanBuilder.php,
python_runtime/devtools/trusted_runtime_callable_invocation.py and
python_runtime/devtools/agent_execution_mcp_executor.py::_safe_callable_context.
The inspected child path does not attach its own Agent/public-reference bridge.
Build capabilities from the exact admitted child manifest and run/client scope.
Never borrow unrestricted parent authority.

Acceptance: signed parent -> exact child -> its admitted role -> typed terminal
result, plus wrong-client/role/revocation/deadline/isolation negative tests.

## A2. Governed clinical context - Assets/input resolver, blocking

The existing direct-callable plan supports bounded fixed/prepared Runtime Source
inputs, not arbitrary node/DB dataset handoff. Agree real parent selectors and event
DTO, then resolve the binding-owned clinical_context before child execution. Preserve
event/product/trial identity, versions, dates, cohort grain and denominators.
Do not smuggle records as a JSON string in variables, weaken binding overrides or
rename row filters into partitions. Core work is conditional on an observed Core gap.

## A3. Research capabilities and source projection - Assets/config + adapter

Admit exact ClinicalTrials.gov and PubMed semantic search/read capabilities. Keep
native grounded event search separate unless that precise search+tool path is proven.
Integrate safe retrieved source projections into evidence.py; current code only
assesses the supplied context. A generated URL cannot self-attest source retrieval.

Reuse AgentCitationView/ReferenceTarget/open_reference primitives where admitted.
Preserve citation origin, actual accessible extent, source/window digest and dates.
Qualify PDF/full-text/abstract behavior and share reference limits across refinement.
Do not add a nested review-toolkit callable; the child path rejects nesting. Local
span checks are not an attested toolkit receipt or semantic factual proof.

## A4. Exact admission - configuration and intake qualification

admission_requirements.json lists six proposed reference-only contracts with prompt
hashes. Provide real reviewed definitions/model/tool policies and exact-version
registration. Do not guess a binding or reuse shared-registry metadata accidentally.
Select the approved group-memory source and partition and declare its read-only role.
Do not infer deployment or admission from the bundled Fixed Skill or method names.

## A5. Child mutable Skill and retention barrier - Assets/trusted runtime

python_runtime/devtools/callable_skill_runtime.py::_dynamic_roles currently requires
read_only; tests reject mutable declarations. Keep this adapter's apply guard until
generic child-owned mutation is admitted. Reuse existing Core-owned initialization,
CAS, package digest and history contracts; never build adapter storage authority.

Require durable analysis retention before learning commit, prior content AND package
checks, per-partition receipts, fresh read-only readback and history comparison.
Uncertain writes require reconciliation, not blind retries. Analysis and Skill writes
are separate effects, not an assumed global transaction. Inspect Core only for a
concrete missing authority/persistence contract.

## A6. ECS parity - Assets, separate release gate

The inspected DirectRuntimeCallablePlanBuilder permits local_worker only. Prove the
generic ECS path, exact image/package, child capabilities, bounds, cleanup and terminal
result before expanding this manifest. Green intake CI is not an ECS deployment.

## A7. Durable interruption recovery - runtime, Core only if a proven gap

In-process task reuse is implemented. Durable stage retention is not. No public
checkpoint API was established. Use an existing governed retention lane with receipts,
input/prompt/Skill/source identities, new-run authorization and safe rehydration.
Test container termination and lost write acknowledgement. A hash is not a checkpoint;
scientific group memory must not become an execution journal.

## A8. Delivery and scientific qualification

Run official intake/diagnose/materialization, true package and Fixed Skill validation,
input/capability admission, then a combined no-write live case. Preserve historical
published versions through the official promotion PR. Separately prove output
retention, mutation/readback/history, source accuracy and adjudicated positive/negative
cohorts. No new UI is needed for this core; UI work requires a demonstrated authoring
or result-display gap, not an assumed platform redesign.
