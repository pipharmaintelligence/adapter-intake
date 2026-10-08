# Company Scope developer guide

## Architecture and preservation

Author source in `pipharmaintelligence/adapter-intake` only. This package adds
`nusaibah.company_scope:0.1.0`; it edits no pharma/evaluation or toolkit source.
The runtime files are `company_scope_adapter.py` and `scope_contract.py`, with
one Adapter subclass/identity. Helpers must never declare another Adapter.
Both flat external-root imports and packaged relative imports are tested using
only these declared promotion files, without sys.path edits inside the asset.

The dependency manifest uses the already installed 0.1.104 runtime, Python
3.10+, standard library only, and no outbound network. It does not request an
upgrade, add a runtime wheel, or claim ECS/callable admission.

## Current evidence and gaps (2026-10-08)

Source inspection established:

- Canonical published `companies` metadata: primary `id`, name `company`,
  corporate FK `corporate_id`, address fields, and country FK `headquarter`.
  This is published metadata, not a fresh physical-table introspection proof.
- Assets node_query uses ordinary `filters_from_variables.id = company_ids`.
  Arrays reach Core's governed whereIn implementation. This is not a partition
  filter and requires no artificial materialized projection.
- Reviewed Assets descriptors cap rows at 25 but do not provide a locked
  corporate predicate or selected columns. Core's default projection includes
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
   corporate_id=1 through trusted policy. Reject caller predicate conflicts;
   do not map corporate_id from launch variables. Corporate group is not a
   substitute for tenant/client/lake access policy.
4. **Projection before hydration:** fetch only id, company, corporate_id,
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

## Contract and limits

The only selectors are company_id, company_ids, or from_company_id plus
to_company_id. Unknown fields are rejected. Positive integer ceiling is
2**63-1. List raw length and inclusive range width are capped at 25 before
normalization/expansion. Input duplicates are removed in first-occurrence order;
duplicate returned rows always fail. No resumable cursor, pagination, while loop,
automatic retry, partial selection, or mutable operation exists in this asset.

Resolved envelope required keys:

- records: list of up to 25 approved row objects;
- row_count: exact integer count, not a boolean;
- exactness: exact;
- partial_reason: null;
- provenance: source=dlm_node, authority=dlm_node, node_key=companies, a safe
  logical lake_id, pages_read=1; optional input_mode=bounded_query or null.

No broader envelopes or materialization extensions are silently accepted.
Schema/projection changes require explicit contract review and new versioning.
Empty/missing/extra results, duplicate rows, wrong corporate scope, malformed
fields, or partial metadata abort the invocation before output assembly.

Required name is nonblank with 512-character maximum; addresses max 4096 each,
website max 2048, updated_at max 64. Null/blank optional strings become null;
other types or oversized values fail instead of being truncated. headquarter
is a country ID, never a country name or a city. updated_at is preserved source
text, not a verified timezone or freshness claim.

## Digest and authority

Canonical serialization is UTF-8 JSON with ensure_ascii=False, sorted keys,
compact separators, and no nonfinite values. Digests are sha256:<hex> over the
whole respective DTO/result excluding its own digest field. A context digest
includes that company's values, logical lake/node identity, and explicit null
source metadata. It is stable for the same content and independent of other
companies. The result digest also binds ordering and selector normalization.

Every result and scalar summary says resolved_rows_only and
runtime_authority_verified=false. This is deliberate: a dict with dlm_node
provenance can be forged in local code, and a content hash can be recomputed.
Future handoff must verify server-owned output/binding origin and same-company
identity; accepting arbitrary caller JSON/hash would duplicate or bypass authority.
Do not invent a local proof boolean or signature protocol in this adapter.

Current retrieved_at/schema_version are null because the runtime projection does
not expose them. A future version may forward approved runtime metadata after
its contract is established. Do not populate them using the adapter clock,
CompanyContext DTO version, a stale schema snapshot, or source updated_at.

## Tests and CI

The intake workflow runs tests/test_company_scope.py with the existing
import-time Adapter stub for Python-only CI. Tests cover selector equivalence,
pre-allocation caps, strict types, ordering/deduplication, actual field mappings,
unknown/sensitive fields, corporate checks, exact result sets, partial query
metadata, source identity, safe errors, digest binding, output isolation,
zero invocation, and flat/packaged imports. CI still runs the existing pharma,
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
