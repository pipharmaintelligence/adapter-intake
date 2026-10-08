# PI-2011 Company Scope implementation and readiness — 2026-10-08

## Outcome

Implemented nusaibah.company_scope:0.1.0 in adapter-intake only. This is a
bounded, API-blind assembler over a binding-only resolved Companies role.
The local development implementation is complete. Governed live selection,
downstream composition, and memory integration remain separate proof gates;
PI-2011's overall live milestone is not closed by local tests.

## Changes

- Strict single/list/inclusive-range normalization; maximum 25 raw input IDs,
  25 range width, and 25 returned rows. Stable input deduplication and ordering.
- Required id/company/corporate_id with corporate integer 1; approved optional
  address, numeric headquarters country FK, website, and source updated text.
- Exact returned ID-set checks. Missing/extra/duplicate/wrong-corporate rows,
  partial envelopes, unapproved fields, and invalid page metadata fail without
  outputs. Complete bounded results may span several server-retrieved pages.
- Immutable typed intermediate contracts, fresh per-company outputs, and
  reproducible content digests. No fabricated schema revision/retrieval time.
- Full CompanyContext result plus scalar summary, explicitly resolved_rows_only
  and runtime_authority_verified=false. Conformance/hash is not authorization.
- Standard development manifest, reviewed helper list, zero new dependencies,
  offline synthetic fixture excluded from promotion, and intake CI coverage.
- README and developer guide covering contracts, limits, server gates,
  official promotion, and later CompanyContext-aware consumer integration.

## Initial implementation validation

| Check | Result |
| --- | --- |
| New Company Scope tests | PASS — 29 |
| Existing pharma tests | PASS — 264 |
| Existing evaluation tests | PASS — 90 |
| Shared review toolkit tests | PASS — 41 |
| Exact-span tests | PASS — 12 |
| Repository intake-contract test | PASS — 1 |
| Total local unit tests | PASS — 437 |
| Installed SDK fixture discovery/invocation/response validation | PASS; socket connections blocked |
| obs-adapter-intake-check for exact adapter.yaml | ready; no mutation/network |
| obs-asset-diagnose --quick, local package/dependencies | ready; no remote admission |
| Current Assets PHP AssetIdentityResolver manifest parser | PASS in memory; empty config; no environment loading/registration/query |
| Intake workflow YAML parsing | PASS |
| Installed E runtime | unchanged — 0.1.104 |

Local/package ready is not governed binding, query-policy, or business-data
live ready. SDK fixture values are synthetic and provide no real Companies proof.
The adapter made zero Agent, tool, child, mutable, or query invocations. The
intended upstream Core query is outside the adapter invocation count.

## Preservation and release

No existing pharma/evaluation/toolkit source, fixtures, retained results,
server source, .env, worker, binding, schema, wheel, or installed runtime changed.
The current 0.2.3 evidence route remains available. Source base is intake main
964182db6001d01d3767146463c1b008ef3679b1.

Keep the PR draft and promotion blocked pending the developer-guide gates.
The runtime requires an active default for a valid manifest; that declaration
and release_stage=development do not enforce server policy or activate a binding.
Do not hand-copy into Assets or upgrade the local wheel. Use the official
promotion workflow when promotion is authorized and these gates are proven.

## Remaining acceptance evidence

1. Server owns selector preparation before Companies retrieval, with the
   agreed bounded semantics for single/list/range.
2. Approved binding/Core authorization and non-overridable corporate_id=1
   predicate, independent of client/lake access policy.
3. Approved field projection before hydration, including no remember_token or
   unrelated account/admin fields. Python rejection is defense in depth only.
4. Controlled zero-provider governed read and retained context inspection:
   first one authorized ID, then multiple IDs, then a bounded range.
5. Trusted output handoff to a future consumer version, no downstream Companies
   re-query, same-company isolation, and regressions preserving 0.2.3.
6. Separate existing governed memory preview/apply/readback/history proof.

No provider/live run or promotion workflow was dispatched for this implementation.

## Multi-page contract revision — 2026-10-08

The first candidate unnecessarily required pages_read=1. Regression tests
reproduced rejection of otherwise complete multi-page results in direct, flat,
and packaged execution. The validation now accepts any positive strict integer
page count while retaining complete-envelope, exact-ID, corporate, field, and
25-company batch checks. Page count is transport metadata, not authenticated
policy or an instruction to loop. Output content/digests remain identical for
the same normalized selector and resolved records across page layouts.

Reuse the existing Core signed pagination and Assets bounded_query aggregation.
The binding descriptor's limit=25 is a page size, not the platform's total
company ceiling. Server page/row/time limits remain authoritative; partial
results after a cap are rejected even if requested rows happen to be present.
README/developer guide separate page size, adapter batch size, and whole-workflow
scope and document the existing async checkpoint path and future batch gates.

Missing/empty selection still fails. All-company selection, larger total scopes,
a coordinator, full_dump_async input, downstream execution, and server-policy
changes are not implemented by this revision. No runtime upgrade is needed.
The PR remains draft with the original governed live/promotion gates open.

### Pagination source references (not promoted)

- [Core query and signed cursor policy](https://github.com/piusaibah/dlm_core/blob/cbf42257b1b6906e35e8e88fc82e05c97d824d5c/app/Services/Lake/Dlm/Operations/DlmNodeBrokeredQueryRuntimeService.php).
- [Assets cursor aggregation and policy caps](https://github.com/piusaibah/assets/blob/82c45db96330766e223d7ca1af45da4af5b69447/app/Services/Observability/Dlm/DlmNodeOperationRuntimeClient.php).
- [Assets input delivery and async page checkpoints](https://github.com/piusaibah/assets/blob/82c45db96330766e223d7ca1af45da4af5b69447/app/Ai/Actions/PythonAdapterInputResolver.php).

The declared package guide uses repository/path/commit references because
the installed intake guard forbids URLs in all declared package files.
No guard exception or runtime change was needed.

### Revision validation

- PASS: 33 Company Scope tests, including multi-page order/digest parity,
  the 25-company boundary, malformed page counts, cap-limited partial inputs,
  exact result-set/corporate checks, no invocation, and flat/packaged imports.
- PASS: existing 264 pharma, 90 evaluation, 41 toolkit, 12 exact-span, and 1
  intake-contract tests. Total local unit tests after this revision: 441.
- PASS: real installed SDK fixture discovery/invocation/response validation for
  two synthetic companies delivered across two source pages, with socket
  connections blocked and zero Agent/child/mutable/adapter-query calls.
- PASS: exact obs-adapter-intake-check and local obs-asset-diagnose --quick;
  no network, mutation, or remote admission check. E runtime remains 0.1.104.
- PASS: diff/declared-file checks. Only Scope validation, Scope tests, and its
  documentation/report changed; manifest, dependencies, server source, bindings,
  workers, runtime wheel, and existing pharma/evaluation/toolkit are unchanged.

These are offline contract/package proofs, not real Companies pagination,
binding authorization, source projection, or downstream live evidence.

## Native full-dump follow-up

Development 0.1.1 now projects native full-dump pages; 0.1.0 retains bounded
selection. See PI-2011-Company-Scope-Full-Dump-Compatibility-2026-10-08.md
for the implemented page contract, verified framework lifecycle, and exact
governed binding admission/retention gates. No live/full-selection proof is claimed.
