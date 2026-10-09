# Company Scope developer guide

## Architecture and preservation

Author source in `pipharmaintelligence/adapter-intake` only. This package adds
`nusaibah.company_scope:0.1.0` for bounded selection and development `0.1.1`
for native full-dump pages; it edits no pharma/evaluation or toolkit source.
The entrypoint is company_scope_full_dump_adapter.py (0.1.1). The declared
legacy module company_scope_adapter.py supplies the distinct 0.1.0 identity;
scope_contract.py and scope_page_contract.py are pure helpers with no Adapter
subclasses. Both versions are intentionally packaged and discovery-tested.
No unversioned/helper Adapter or imported-class duplicate is permitted.
Both flat external-root imports and packaged relative imports are tested using
only these declared promotion files, without sys.path edits inside the asset.

The dependency manifest uses the already installed 0.1.104 runtime, Python
3.10+, standard library only, and no outbound network. It does not request an
upgrade, add a runtime wheel, or claim ECS/callable admission.

## Current evidence and gaps (2026-10-08)

Source inspection established:

- Canonical published `companies` metadata: primary `id`, name `company`,
  corporate membership field `corporate` (distinct from source `corporate_id`), address fields, and country FK `headquarter`.
  This is published metadata, not a fresh physical-table introspection proof.
- Assets node_query uses ordinary `filters_from_variables.id = company_ids`.
  Arrays reach Core's governed whereIn implementation. This is not a partition
  filter and requires no artificial materialized projection.
- Reviewed Assets binding descriptors set page size 25, not a total-result
  ceiling. The existing Assets query client follows cursors and aggregates
  bounded results. These descriptors do not provide a locked corporate
  predicate or selected columns. Core's default projection includes
  schema columns; its reviewed exact-key denylist does not exclude remember_token.
- The safe node-query envelope includes rows, exactness, count, and logical
  provenance. It does not expose retrieved_at or source schema version.
- Signed callable plans support local_worker, reject nested callable
  dependencies, and do not establish Companies child-query preparation.

These findings justify this bounded assembler but do not prove governed live
selection. Do not treat the corporate row check as row-level authorization or
safe-field rejection as proof that unsafe fields never reached Python.

## Mandatory server gates before promotion / registration / live execution

1. **Approved Companies binding:** server owns source/lake/node selection and
   client authorization; caller cannot supply or replace the companies role.
   Never repurpose an existing pharma binding or expose DB/node overrides.
2. **Preparation before retrieval:** validate exactly one selector, normalize
   to bounded ordered IDs, then construct the approved query. Align with
   normalize_selector() and its test vectors; do not execute an unrestricted
   query first and filter in Python. An adapter-local range does not modify a
   prefetched input. The primitive intentionally calls neither inputs.invoke
   nor a new remote callback. Server preparation remains work in Assets/Core.
3. **Non-overridable predicate:** Core/Assets enforce id membership AND
   corporate=1 through trusted policy. Reject caller predicate conflicts;
   do not map corporate from launch variables. Corporate group is not a
   substitute for tenant/client/lake access policy.
4. **Projection before hydration:** fetch only id, company, corporate,
   address_line1, address_line2, headquarter, website, and updated_at (or an
   approved subset containing the three required fields). Keep remember_token
   and unrelated account/admin columns outside Python, logs, and output.
5. **Governed data proof:** one controlled authorized ID first, with retained
   CompanyContext inspection and observed zero provider/mutable calls. Then
   controlled multiple IDs and a small range. Require exact output ID parity,
   fixed corporate scope, field projection, and safe errors. No paid/provider
   rerun is needed to establish these facts.

Keep the intake PR draft until these gates are grounded or explicitly approve
merging local development source while maintaining the separate promotion gate.
Default active is required by AssetIdentityResolver for valid packaging; neither
that declaration nor release_stage=development enforces these server gates.

## Bounded version 0.1.0 contract and limits

The only selectors are company_id, company_ids, or from_company_id plus
to_company_id. Unknown fields are rejected. Positive integer ceiling is
2**63-1. List raw length and inclusive range width are capped at 25 before
normalization/expansion. Input duplicates are removed in first-occurrence order;
duplicate returned rows always fail. Missing selectors and empty lists are
invalid, never an implicit all-companies request. This asset consumes complete
server-aggregated results; it owns no cursor, pagination loop, automatic retry,
partial selection, or mutable operation.

Resolved envelope required keys:

- records: list of up to 25 approved row objects;
- row_count: exact integer count, not a boolean;
- exactness: exact;
- partial_reason: null;
- provenance: source=dlm_node, authority=dlm_node, node_key=companies, a safe
  logical lake_id, and positive strict integer pages_read; optional
  input_mode=bounded_query or null. Multi-page bounded results are accepted.

No broader envelopes or materialization extensions are silently accepted.
Schema/projection changes require explicit contract review and new versioning.
Empty/missing/extra results, duplicate rows, wrong corporate scope, malformed
fields, or partial metadata abort the invocation before output assembly.

Required name is nonblank with 512-character maximum; addresses max 4096 each,
website max 2048, updated_at max 64. Null/blank optional strings become null;
other types or oversized values fail instead of being truncated. headquarter
is a country ID, never a country name or a city. updated_at is preserved source
text, not a verified timezone or freshness claim.

## Reuse existing server pagination

Pagination is already implemented. The relevant reviewed source is below.
Clickable source links are retained in the non-promoted PI-2011 review
report; declared package files follow the intake guard's no-URL policy.

- Core governed query and cursor policy,
  `dlm_core:app/Services/Lake/Dlm/Operations/DlmNodeBrokeredQueryRuntimeService.php`
  at `cbf42257b1b6906e35e8e88fc82e05c97d824d5c`:
  the current minted defaults are up to 500 rows per page, 20 client pages,
  10,000 client rows, and a 30-second query budget. Signed cursors bind the query
  selector, page size, and client/lake/node authority. These are defaults in
  this service, not permission for an asset to process every company.
- Assets query client,
  `assets:app/Services/Observability/Dlm/DlmNodeOperationRuntimeClient.php`
  at `82c45db96330766e223d7ca1af45da4af5b69447`:
  bounded_query already follows next_cursor and aggregates records under the
  supplied page/row/time policy. It reports pages_read and exactness, and marks
  cap-limited results partial. Smaller page sizes also reduce the effective
  maximum reachable under the page cap: 25 rows times 20 pages is at most 500
  rows, even if the row-policy ceiling is 10,000. Time/policy may reduce it further.
- Assets input resolver and checkpoints,
  `assets:app/Ai/Actions/PythonAdapterInputResolver.php`
  at `82c45db96330766e223d7ca1af45da4af5b69447`:
  full_dump_async has page/checkpoint handling. Version 0.1.1 consumes its
  native safe page envelope. The governed binding route still rejects dump
  admission; adapter compatibility is not permission to bypass that route.

Bounded version 0.1.0 checks that pages_read is a positive integer; it does
not authenticate that metadata, recreate the signed policy, impose its own
page ceiling, or iterate pages_read times. Adapter work is bounded by the
selector/row limit 25 and field-size limits. Assets/Core remain responsible
for enforced pagination budgets and trusted input origin. Bounded DTO/result
content digests are independent of page count when resolved records and
selector are identical. Native version 0.1.1 instead requires the one-page
delivery shape and binds page position into its page-result digest.

Every partial source fails bounded version 0.1.0, including normal
more_pages_available continuation. Native version 0.1.1 below accepts that
normal continuation state; policy/time caps fail both versions. Completing
one source page is not proof of complete company selection. Never relabel a
partial source exact or strip its metadata to bypass validation.

### Native-page version 0.1.1 and remaining activation gates

Version 0.1.1 accepts only variables={selection: all_authorized} and the actual
safe full_dump_async envelope. This is explicit source selection intent, not
permission to choose a lake, node, projection, corporate group, or query mode.
Missing/empty selectors still fail. Selected-ID semantics remain in 0.1.0.

The native page provenance requires pages_read=1, input_mode=full_dump_async,
nonnegative integer page_index/record_offset, and the same logical Companies
identity. First-page offset must be zero; later offsets must indicate positive
progress. This single-page shape check matches native delivery and does not
restore the old one-page restriction on aggregated bounded-query results.
The row cap is 25 per page. A repeated invocation is deterministic and stateless.

Normal partial/more_pages_available pages are valid batches. Original exactness
and reason are retained. Empty continuation, policy/time caps, inconsistent
metadata, extra fields/cursors, and invalid company rows fail before outputs.
An exact empty terminal page is valid. company_scope_page.v1 separates
batch_complete from source_exhausted and always leaves selection_complete null.
A terminal page alone is not evidence that all prior pages were processed or
retained. Do not infer whole-selection completion from adapter status=success.

allow_resume=true declares compatibility with framework re-invocation for 0.1.1;
it neither requests continuation nor authorizes a binding. Keep these gates open:

1. **Governed admission:** reviewed AssetInputBindingService rejects
   full_dump_allowed=true with full_dump_allowed_not_supported. Reviewed
   AssetRuntimeInputBindingResolver::nodeQueryInputContract fixes bounded_query.
   The current binding UI sends full_dump_allowed=false. Use a separately
   reviewed generic server contract, not direct Companies data, a model-role
   workaround, or removal of the rejection to get a run accepted.
2. **Scope/projection:** preserve the mandatory approved binding, fixed
   corporate=1, authorized client/lake, and approved fields before hydration.
3. **Continuation:** reuse existing success-validated InputPageCommitPlan,
   checkpoint coordinator, completion guard, and dispatcher. Automatic dispatch
   requires an asynchronous queue; sync leaves an explicit waiting state.
   Server-owned reason/idempotency metadata and source page/row/time policy
   remain required. Existing continuation metrics cap pages at 1000, dispatch
   failures at 10, and stale-claim reclaims at 10; those are safety ceilings,
   not this asset's approved total-company or paid-execution budget.
4. **Per-page outputs:** ExecutePythonAdapterAction commits prepared input
   progress after response success validation. That alone does not prove every
   page's business result was retained. PHP workflow state retains summaries,
   not full contexts. Prove distinct authorized page artifacts/outputs, replay
   idempotency, and final readback of all page results before claiming all-company
   delivery. Never accumulate company rows in PHP checkpoints or Python state.
5. **Whole-selection proof:** stable authorized membership/order, finite total
   company/page/time budgets, no skipped/repeated companies on resume, explicit
   cap/failure states, and framework-owned final completion. The adapter does
   not authenticate provenance or detect duplicates across separate invocations.

No server, runtime, binding, worker, queue, or persistence configuration is
changed by this candidate. Use existing services when the reviewed gates pass;
no alternate pagination engine or raw-source bypass is introduced.

### Future whole-selection handoff (not implemented)

Keep the 25-company limit per Scope invocation. A larger explicit list, wider
range, or admitted all_authorized selection belongs to authorized server coordination:

1. Admit the whole selection before retrieval, enforce a total company cap,
   fixed corporate=1, client/lake authorization, and approved columns.
2. Establish stable selected membership and ordering; offset pagination alone
   does not guarantee a snapshot if the source changes between requests.
3. Reuse existing server paging/checkpoints. For selected-ID batches, prepare
   at most 25 declared IDs and their complete exact records for version 0.1.0.
   For an admitted all_authorized selection, deliver native pages of at most
   25 records to version 0.1.1. No Companies re-query occurs downstream.
4. Track batch completion separately from overall selection completion. Reaching
   a cap, missing records, or unfinished continuation must remain incomplete.
   Version any new handoff envelope explicitly; use 0.1.1 for native pages
   and never disguise them as a bounded-query 0.1.0 proof.
5. Persist server-owned progress and prevent duplicate processing on resume.
   Define finite retry/deadline/concurrency and total Agent/tool budgets separately
   from retrieval limits; batch selection alone authorizes no paid execution.

None of these future coordination rules introduces Python SQL/HTTP, a second
pagination engine, new persistence authority, or an implicit all default. Use
standard promotion after the standalone server gates; no runtime upgrade is
required for accepting an already-complete multi-page bounded-query envelope.

## Digest and authority

Canonical serialization is UTF-8 JSON with ensure_ascii=False, sorted keys,
compact separators, and no nonfinite values. Digests are sha256:<hex> over the
whole respective DTO/result excluding its own digest field. A context digest
includes that company's values, logical lake/node identity, and explicit null
source metadata. It is stable for the same content and independent of other
companies. Bounded result digests bind ordering and selector normalization;
native page digests also bind page position and source completion metadata.

Every result and scalar summary keeps runtime_authority_verified=false.
Version 0.1.0 uses resolved_rows_only; version 0.1.1 uses resolved_page_only. This is deliberate: a dict with dlm_node
provenance can be forged in local code, and a content hash can be recomputed.
Future handoff must verify server-owned output/binding origin and same-company
identity; accepting arbitrary caller JSON/hash would duplicate or bypass authority.
Do not invent a local proof boolean or signature protocol in this adapter.

Current retrieved_at/schema_version are null because the runtime projection does
not expose them. A future version may forward approved runtime metadata after
its contract is established. Do not populate them using the adapter clock,
CompanyContext DTO version, a stale schema snapshot, or source updated_at.

## Tests and CI

The intake workflow runs tests/test_company_scope*.py with the existing
import-time Adapter stub for Python-only CI. Tests cover selector equivalence,
pre-allocation caps, strict types, ordering/deduplication, actual field mappings,
unknown/sensitive fields, corporate checks, exact result sets, partial query
metadata, positive page counts, complete multi-page aggregation, unchanged
batch caps, source identity, safe errors, digest binding, output isolation,
zero invocation, and flat/packaged imports for both versions. Native-page tests
also cover intermediate/final/empty pages, cap failures, safe positions, and
honest selection completion. CI still runs the existing pharma,
evaluation, and shared-toolkit suites.

Local checks use the unchanged E runtime. Intake/preflight reports establish
local package compatibility only. Do not use --check-remote or smoke as an
offline test: those are separate remote actions, not proof of row-policy safety.
Synthetic fixture values live in tests/fixtures and are excluded from the
reviewed_helpers/optional_files promotion list. Never package real company rows,
credentials, run outputs, .env files, or operational reports.

## Stable error codes

company_scope_selector_invalid, company_scope_identifier_invalid,
company_scope_selector_limit_exceeded, company_scope_range_invalid,
company_scope_input_invalid, company_scope_source_invalid,
company_scope_source_incomplete, company_scope_rows_invalid,
company_scope_row_fields_invalid, company_scope_row_value_invalid,
company_scope_row_duplicate, company_scope_corporate_scope_mismatch,
company_scope_result_set_mismatch.

Messages contain only the code. Do not add row values, lake references, headers,
raw responses, exception stacks, or source data to logs/summary/error messages.

## Downstream and memory: separate milestones

After the standalone scope proof, verify an OBS/server stage handoff to one
CompanyContext-aware consumer version. Preserve the current 0.2.3 input contract
and retained evaluation. Downstream must not re-query Companies when trusted
context is supplied. Context is governed identity data, not independent proof
of research claims; findings still need evidence and domain review.

Start with one active company execution. A later batch needs an explicit total
Agent/tool budget, concurrency limit, finite retries, and deadline. 25 scoped
companies is a selection ceiling, not authorization for 25 provider executions.
No new parent adapter is introduced around a consumer with callable children.

Existing memory preview/apply, expected digest, authorization, per-company
partition isolation, fresh readback, and history remain in Dynamic Skill/Core.
This asset neither creates a memory coordinator nor promises global batch
rollback. Memory composition and mutable apply are outside this implementation.
