# UMLS Terminology 0.1.1 — attested search intake candidate

This current-version handoff selects `umls_terminology@0.1.1` and requires
`pi-obs-python-runtime>=0.1.123`. It is a development candidate, with no
deployment or live provider execution implied by intake acceptance.

## Governed search contract

Plain `search` uses the existing Core-governed `umls_response` role.
The adapter calls `inputs.invoke(..., include_evidence=True, on_error="raise")`
and verifies the closed receipt schema, operation and capability, exact business
selectors, full fetched-record digest, record count and receipt timestamp
before applying a local result limit.

The trusted worker authenticates helper HMAC and binds the receipt to the
Core-selected source. The adapter independently checks the returned selector
commitment and records; caller-provided records or locally fabricated receipts
do not establish source authority.

Successful validation sets `query_attested=true` and retains the bounded
receipt in `provenance.runtime_fetch_evidence`. This establishes the runtime
fetch commitment, not scientific correctness, UMLS release, source vocabulary,
provider-owned retrieval time or upstream completeness. Those remain unknown
unless independently supplied.

`describe` is offline. Other advertised semantic operations retain their
existing validation rules and do not gain a live governed mapping in this
candidate. The adapter owns no credentials, provider URLs, storage selection,
output publication or Core/UI configuration.

## Frozen 0.1.0 helper and package coexistence

`umls_terminology_adapter.py` is a reviewed dependency of the 0.1.1 module.
It is the exact published 0.1.0 implementation, retained without edits. Its
canonical Git-byte SHA-256 is:

`062c235832e8bf4b152eced290e4ec887d3832fa8b18e28e55baf7353839054d`

This intake manifest declares only 0.1.1. It does not republish 0.1.0.
During a later approved Assets promotion, the existing materializer composes
the candidate with the already-published 0.1.0 identity. It must preserve that
version's code, manifest contract and dependency requirements. The new
`0.1.123` minimum belongs to 0.1.1.

`adapter.yaml` declares the versioned entry module, frozen helper, manifest
and dependency manifest. Tests, synthetic fixtures and local qualification
reports remain development-only and are excluded from the runtime copy plan.

## Provider-free verification

Run the UMLS tests with the installed official SDK, without the intake CI
stubs. Set `UMLS_REQUIRE_INSTALLED_RUNTIME=1` and
`UMLS_EXPECT_RUNTIME_VERSION=0.1.123` to make missing or incorrect SDK
installations fail closed. The candidate folder must be on the test import
path.

The intake workflow separately checks promotion shape and UMLS fixtures.
Its installed-wheel tests visibly skip when that CI environment has no SDK;
local installed-wheel certification must pass with zero skips.

Final-head qualification also checks real signed synthetic helper/worker
composition, tampering rejection, child-process IPC, local/package imports and
Assets materializer coexistence. Core resolution and external provider GET are
synthetic for those tests; no live provider result is claimed.

## Release gates

Keep this PR draft and unmerged until final-head CI, official promotion-plan
review, provider-free installed-SDK qualification and package coexistence are
reviewed. A separately admitted 0.1.1 live qualification remains a release gate.
The published 0.1.0 implementation and running worker stay unchanged.

This handoff supersedes the intake-only 0.1.0 proposal in PR #148. That draft
can be closed as superseded after review of the reconciled 0.1.1 change.
