# PI-2011 Company Scope full-dump compatibility — 2026-10-08

## Outcome and exact scope

Added development nusaibah.company_scope:0.1.1 in adapter-intake only. It
projects one native full_dump_async page using existing safe runtime metadata,
with at most 25 approved Companies rows and no query/provider/mutation. The
bounded 0.1.0 implementation remains available with its selector/output contract;
shared row validation is reused and regression-tested. One asset key has two
explicit versioned implementations, with no child asset invocation.

This completes the offline native-page contract milestone. Governed all-company
execution is not enabled or proven. No runtime upgrade, promotion, registration,
queue change, source query, provider call, output publication, or live run occurred.

## Why platform full dump is not yet this binding's full dump

The lower-level runtime supports full_dump_async and native page checkpoints.
However, current AssetInputBindingService rejects full_dump_allowed=true with
full_dump_allowed_not_supported, and AssetRuntimeInputBindingResolver forces
node_query contracts to bounded_query. The binding UI sends false. Adapter
allow_resume or semantic selection cannot override these server decisions.
Removing that rejection or accepting caller-supplied Companies rows would not
establish fixed corporate scope, projection, source authorization, or retention.

## Native input and honest output

Version 0.1.1 requires explicit variables={selection: all_authorized}; no missing
or empty input means all. The Companies role remains required and binding-only.
The safe native envelope includes records/count/exactness/partial_reason plus
source/authority/lake/node, pages_read=1, input_mode=full_dump_async, page_index,
and record_offset. Python receives no cursor, credential, SQL, or next endpoint.

Normal partial/more_pages_available pages are validated without changing source
truth. An exact terminal page, including an empty terminal page, is valid.
Nonadvancing empty continuation, cap/time failures, malformed position/count,
wrong scope, unapproved fields, and duplicate IDs within a page fail without
outputs. Separate invocations do not share company rows or persistent state.

company_scope_page.v1 reports batch_complete, source_exhausted, original source
exactness/reason, page position, contexts, and a content/position digest.
selection_complete is null on every page because the adapter cannot attest
prior-page processing, retained output, or whole-run completeness. Scalar summary
reports framework_owned completion and carries no company identifiers or digests.
Repeated input produces the same output; this is deterministic replay behavior,
not proof of exactly-once output persistence or cross-page deduplication.

## Framework lifecycle verified

1. Native full dump prepares one source page and safe input metadata.
2. PythonAdapterInputResolver prepares a pending/completed InputPageCommitPlan;
   cursor/progress remains PHP-owned and outside the Python payload.
3. ExecutePythonAdapterAction validates adapter response success before committing
   input progress. This does not by itself prove page business-output persistence.
4. Completion guard prevents terminal completion while continuation is pending.
5. Dispatcher claims the same run and queues continuation when the queue is async.
   Sync queues remain waiting with async_queue_required_for_auto_continuation.
6. Existing server metrics impose finite page/dispatch-failure/stale-claim limits;
   source policy separately limits pages/rows/time. No Python paging loop is added.

Existing tests verified this lifecycle using isolated in-memory test databases.
They are generic framework tests, not a real Companies binding/output proof.

## Source evidence

- [Binding admission rejection](https://github.com/piusaibah/assets/blob/82c45db96330766e223d7ca1af45da4af5b69447/app/Observability/Platform/Assets/AssetInputBindingService.php).
- [Binding query preparation](https://github.com/piusaibah/assets/blob/82c45db96330766e223d7ca1af45da4af5b69447/app/Observability/Platform/Assets/AssetRuntimeInputBindingResolver.php).
- [Native full-dump runtime client](https://github.com/piusaibah/assets/blob/82c45db96330766e223d7ca1af45da4af5b69447/app/Services/Observability/Dlm/DlmNodeOperationRuntimeClient.php).
- [Safe payload and commit plan](https://github.com/piusaibah/assets/blob/82c45db96330766e223d7ca1af45da4af5b69447/app/Ai/Actions/PythonAdapterInputResolver.php).
- [Success validation and input progress commit](https://github.com/piusaibah/assets/blob/82c45db96330766e223d7ca1af45da4af5b69447/app/Ai/Actions/ExecutePythonAdapterAction.php).
- [Completion/continuation job](https://github.com/piusaibah/assets/blob/82c45db96330766e223d7ca1af45da4af5b69447/app/Ai/Execution/Jobs/ExecuteWorkflowRunJob.php).

URLs are in this non-promoted report. Declared package docs use plain source
references to comply with the installed intake no-URL guard.

## Remaining gates in priority order

1. Establish an approved generic full-dump binding contract with fixed corporate
   predicate, safe projection, client/lake authorization, and server-owned source
   mode/reason/idempotency. No bypass of current binding admission.
2. Prove per-page result retention/readback and replay idempotency through the
   existing governed data plane; PHP summaries and a last-page result are not a
   complete all-company deliverable.
3. Prove async continuation, finite total scope/deadline, source consistency,
   empty/final/capped states, and no skipped/repeated companies under resume.
4. Controlled zero-provider Companies proof after those gates, with independent
   retained context inspection. Use official workflow promotion when authorized.
5. Future trusted CompanyContext consumer handoff, preserving pharma 0.2.3;
   existing governed memory remains a separate downstream proof.

Keep PR draft. Active/default/resume declarations are package metadata, not
binding enablement, authorization, proof of retained results, or release approval.

## Validation receipts

- 458 offline Python regressions passed: 50 Scope (33 bounded plus 17 native
  page), 264 pharma, 90 evaluation, 41 toolkit, 12 exact-span, 1 intake contract.
- Flat and packaged import tests use only the declared four runtime modules;
  both distinct version identities resolve without imported-class collisions.
- The real installed SDK 0.1.104 passed external-root discovery, fixture
  invocation and response validation for bounded, intermediate, terminal and
  replayed native-page inputs with socket connections blocked. This establishes
  isolated page compatibility, not an integrated whole-selection proof.
- Exact installed intake guard and local diagnostics returned ready with no
  network, mutation, remote admission, or workflow/provider launch.
- The Assets manifest parser resolved both 0.1.0 and 0.1.1 using an in-memory
  application/config, without environment loading or service/database boot.
- 22 existing generic framework tests passed, with 255 assertions: native
  payload projection, commit/checkpoint coordination, and queued continuation.
  PHP 8.4.20 used isolated in-memory SQLite databases; no live data or queue
  configuration was changed.

GitHub CI must pass on the exact new PR head before treating the development
change as reviewed. These receipts do not close the remaining admission,
projection, per-page retention, or whole-selection proof gates above.
