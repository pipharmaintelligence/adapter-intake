# Current scope clarification

This update is adapter-intake only. The clinical consumer now accepts optional
binding-owned clinical_evidence alongside clinical_context. See
PREPARED_EVIDENCE_CONTRACT.md. The user is validating the three source adapters
separately; this change does not ask for or perform their implementation work.
No nested callable, runtime handoff API, source registration or mutable Skill
bridge is introduced. The following platform gates remain external and are not
claimed by local tests.

# PI-2061 Assets and repository handoff

Reviewed baselines: adapter-intake 48bbdecc944a0458d00b40ec50cecffbdce18515;
Assets d23e019d6efa3fb33dc85e38141603f598d1f6f3 (paragraph/changeset and callable Skill restriction rechecked). Recheck current source before changes.
No Assets, Core, UI, deployment or installed-wheel change is included in this PR.

## A1. Child-owned Agent session - Assets/trusted runtime, blocking

Inspect app/Services/Observability/Agents/DirectRuntimeCallablePlanBuilder.php,
python_runtime/devtools/trusted_runtime_callable_invocation.py and
python_runtime/devtools/agent_execution_mcp_executor.py::_safe_callable_context.
Merged Assets PR #633 attaches child-scoped Agent and public-reference bridges in the generic callable path; clinical combined live qualification remains outstanding.
Build capabilities from the exact admitted child manifest and run/client scope.
Never borrow unrestricted parent authority.

Acceptance: signed parent -> exact child -> its admitted role -> typed terminal
result, plus wrong-client/role/revocation/deadline/isolation negative tests.

## A2. Governed clinical context - Assets/input resolver, blocking

Merged Assets PR #633 supports the deferred child-owned file_object binding selector; actual Core object/binding readiness remains unverified. Agree real parent selectors and event
DTO, then resolve the binding-owned clinical_context before child execution. Preserve
event/product/trial identity, versions, dates, cohort grain and denominators.
Do not smuggle records as a JSON string in variables, weaken binding overrides or
rename row filters into partitions. Core work is conditional on an observed Core gap.

## A3. Research capabilities and source projection - Assets/config + adapter

Admit provider-grounded discovery for the clinical research roles and trusted child-owned HTTP reference inspection; citations are leads until source text is inspected. Keep
native grounded event search separate unless that precise search+tool path is proven.
Integrate safe retrieved source projections into evidence.py; current code only
assesses the supplied context. A generated URL cannot self-attest source retrieval; the adapter now projects only native provider citations and inspects them through trusted public-web.

Reuse AgentCitationView/ReferenceTarget/open_reference primitives where admitted.
Preserve citation origin, actual accessible extent, source/window digest and dates.
Qualify PDF/full-text/abstract behavior and share reference limits across refinement.
Do not add a nested review-toolkit callable; the child path rejects nesting. Local
span checks are not an attested toolkit receipt or semantic factual proof.

## A4. Exact admission - configuration and intake qualification

admission_requirements.json lists seven proposed reference-only contracts with prompt
hashes. Provide real reviewed definitions/model/tool policies and exact-version
registration. Do not guess a binding or reuse shared-registry metadata accidentally.
Select the approved product-memory source and product_id partition and declare its read-only role. Class roles are optional.
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

Clinical manifest remains local_worker-only; ECS is a separate qualification gate. Prove the
generic ECS path, exact image/package, child capabilities, bounds, cleanup and terminal
result before expanding this manifest. Green intake CI is not an ECS deployment.

## A7. Durable interruption recovery - runtime, Core only if a proven gap

In-process task reuse is implemented. Durable stage retention is not. No public
checkpoint API was established. Use an existing governed retention lane with receipts,
input/prompt/Skill/source identities, new-run authorization and safe rehydration.
Test container termination and lost write acknowledgement. A hash is not a checkpoint;
scientific product/class memory must not become an execution journal.

## A8. Delivery and scientific qualification

Run official intake/diagnose/materialization, true package and Fixed Skill validation,
input/capability admission, then a combined no-write live case. Preserve historical
published versions through the official promotion PR. Separately prove output
retention, mutation/readback/history, source accuracy and adjudicated positive/negative
cohorts. No new UI is needed for this core; UI work requires a demonstrated authoring
or result-display gap, not an assumed platform redesign.

## 0.1.1 product-first amendment (supersedes group-primary assumptions)

Primary roles: product_memory / product_memory_update selected by product_id.
The internal case is indication_id / trial_id / regimen_id. Different cases of
one product must not share one mixed clinical conclusion. Class work defaults to
false and has separate optional read/update roles. Current true behavior is a
candidate-reference preview, not complete cross-product synthesis or a class write.

Admit seven exact 1.1.0 Agent roles and Fixed methodology 1.1.0. Add the editor and
critic edit-review task. Validate actual Gemini 3.8 model/tool/structured-output
transport rather than assuming Markdown prompts prove admission.

The SDK already has paragraph reads and structural changesets. The inspected
callable child still restricts Dynamic Skills to read-only. Qualify product writes
first: retained analysis, content/package CAS, approved if-absent initialization,
same-product concurrency, receipt, fresh readback, history and unchanged siblings.
Do not lend parent authority or bypass the mutation restriction. Optional class
failure must not misreport a completed product effect; no global atomicity assumed.

A smaller model packet does not imply partial storage retrieval: the document
view operates after hydration. Investigate server-side bounded reads only if the
package/hydration boundary is actually the measured blocker. ECS, new-source
retrieval, exact admission and durable process-loss recovery remain separate gates.


## Staging node contract addendum (isolated intake wiring)

The read-only product_memory `runtime_skills` role now names
`test_database_lake / clinical_product_memory_packages` with `product_id`
selection; runtime-owned ZIP package resolution and first package upload/readback
are outstanding. Mutable roles are deliberately omitted because callable child
Skill composition currently rejects mutation.

For canonical result retention the adapter now provides an opt-in
`clinical_intelligence_records` records envelope, shaped for one complete
JSONL record per assessment. The existing callable `clinical_intelligence`
payload is unchanged when not requested. Output preparation is separate from
publish: the trusted server must approve a target policy for
`test_database_lake / clinical_failure_intelligence_results`, select that
output role, prove schema inspection, complete Core's output-write operation
and return an authoritative receipt. The manifest is not a publish policy.

Both staging nodes are reported active but empty, both catalog flags still
require correction, ZIP schema waiver is absent, and signed runtime read/write
and persistence remain not proven. The official intake checker also presently
rejects nested prompt/schema/reference paths under reviewed_support_files;
that packaging contract is a separate hard gate before promotion.

## Dual substrate and official intake packaging checkpoint

The manifest declares `local_worker` and `ecs` as allowed substrates, with `local_worker` as default. Each requires independent exact package/catalog, client-bound Agent/Fixed/Dynamic Skill, governed-input and terminal composition proof. ECS declaration is not a deployed image or working ECS child Skill proof.

Reviewed runtime prompts live as same-folder `prompt_*.md` optional files, read by the packaged `prompt_catalog.py`. Static schemas and hypothesis seeds are same-folder reviewed JSON support files. Fixed methodology remains at the manifest-authorized Skill root. Runtime nested prompt/schema/reference folders are removed, not silently ignored. The official intake validator and package-mode import tests remain mandatory.
