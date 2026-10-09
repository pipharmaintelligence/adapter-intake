# Developer guide

## Preservation and reuse

The existing evaluation 0.2.3 and production intelligence source are unchanged.
The new package contains exact reviewed snapshots of supplied_source_review.py,
supplied_source_quote_review.py, supplied_source_scoped_review.py and
quote_review_orchestration.py. These pure helpers define no Adapter subclasses.
The sole discoverable identity is nusaibah.pharma_company_context_review:0.1.0.
Use relative imports for packaged delivery and the existing flat-root fallback
for admitted local_worker materialization. Do not import a discoverable adapter
as a helper, change sys.path in business code or embed runtime API credentials.

The real-company preparation is independent of synthetic fixture preparation.
It never passes a real record to the legacy engine with synthetic=true. It
validates the full retained scope and context digests, one-company parity,
corporate scope, declared field shapes and provenance envelope before helpers.
The shared orchestration's historical result annotation is replaced by this
contract's explicit real-record result schema and limitations. No shared module
globals are changed, so existing profiles can execute concurrently.

## Server-owned contracts

A governed Scope binding supplies integer_selector and query_constraints.
Configure single/list/range variable names, max_items=25, reject_unknown_variables,
fixed_filters={corporate_id: 1}, and the approved column projection. These are
approved binding configuration; they are not launch variables. Validation and
normalization must finish before the Core query. Do not enable a full dump or
repurpose another asset's binding for this proof.

retained_output is optional manifest metadata for a direct object reference.
The static policy supplies asset_identity=nusaibah.company_scope:0.1.0 and
output_role=company_scope_result. The caller supplies only run_uuid. Assets
checks client ownership, producer identity, completion, retention and expiry
at admission and again at execution. Core owns canonical artifact retention.
Only execution hydration adds value and safe logical provenance. No canonical
context is copied into PHP launch/checkpoint state by the handoff.

The existing direct/binding/either role sources remain compatible with runtime
0.1.104. No new worker source enum, endpoint, retry engine or wheel is required.
This retained reference is an external workflow input, not a callable child
input. The admitted structured_review_toolkit remains the only child asset.

## Validation and future work

Run the package protocol tests with historical evaluation test doubles on the
test-only import path. They cover the whole specialist/toolkit/verifier sequence,
quote receipts, no_evidence, bad digests, wrong identity and raw-input rejection.
Run historical evaluation and Company Scope suites as preservation checks.
The protocol doubles do not establish model factual accuracy.

Source access and no repeated query are established by the governed runtime
receipts and handoff, not by model statements. Review retained accepted findings
against the admitted record observation. Require no unsupported claims, no
identity-to-commercial duplication, exact quote resolution and truthful gaps.
Independent semantic approval must be recorded by an actual reviewer; do not
reuse fixture truth or invent qualification attestations for the real case.

Add approved independent research evidence in a future version when needed.
That version must bind sources, preserve entity/provenance boundaries and enforce
finite chunks/calls. Large collections should use the common iteration engine
and durable joins when qualified; do not place a long or unbounded loop here.
