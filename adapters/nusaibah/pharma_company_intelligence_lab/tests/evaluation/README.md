# Pharma specialized-review evaluation suite

This folder starts **PI-1974 / WP1**. It is evaluation infrastructure, not a claim that the future review graph is implemented or that the proposed quality thresholds have been met.

## Current status

- Baseline identity is pinned to asset `0.1.12`, runtime `0.1.97`, and preview run `6e95802c-2336-47f5-b7c2-1e30476a0fef`.
- The suite contains 24 deterministic synthetic cases split into 16 development and 8 held-out cases.
- Cases cover the planned adversarial strata: company isolation, wrong-entity distractors, tables/footnotes, boundary-spanning claims, duplicated overlap, source-version drift, conflicting dates/jurisdictions, OCR/access gaps, source prompt injection, citation laundering, unsupported paraphrase, mandatory-requirement omission, malformed/truncated output, budget exhaustion, preview no-write, and final-synthesis new-claim rejection.
- All 24 cases are adjudicated with a named primary reviewer and frozen matching source digests; the criticality taxonomy is adjudicated and thresholds are calibrated.
- Adjudication/contract readiness is therefore distinct from WP1 completion.
- The unchanged `0.1.12` factual-quality and cost baseline is still unmeasured. Unobserved source/input/answer/thinking/cost counters remain `null`; do not manufacture a baseline from the one successful preview.

## Adjudication workflow

1. Review each synthetic source and candidate expected finding against the intended methodology obligation.
2. Confirm applicable requirements and acceptable abstentions.
3. Freeze the source fixture and record its SHA-256 digest.
4. Set a named primary domain reviewer and mark the case `adjudicated`.
5. If there is disagreement, record a second reviewer before resolving the case.
6. Keep development and held-out cases separate. Do not tune prompts or budgets against held-out truth.
7. Adjudication establishes the evaluation truth set; it does **not** complete WP1. A complete validated baseline measurement is still required before WP2 can unblock.

The test suite deliberately fails closed if a case claims `adjudicated` without reviewer identity, frozen source digest, expected-finding support locators, or explicit abstention coverage.

## Scope boundary

These fixtures do not add document input authority, new provider calls, chunking, retries, memory writes, publication, or runtime configuration. WP2 and later work remain dependency-blocked until WP1 adjudication and baseline decisions are complete.

## Readiness report

Run this from the adapter test directory or project root:

```powershell
python adapters/nusaibah/pharma_company_intelligence_lab/tests/evaluation/review_evaluation_status.py
```

The report is value-safe and exposes only counts/status. `wp1_contract_ready` reports adjudication/taxonomy/calibration readiness. `wp1_complete` and `wp2_unblocked` remain `false` until a complete baseline measurement bound to the exact adjudicated suite validates successfully.


## Adjudication receipt workflow

Do not hand-edit the suite into an adjudicated state. Generate a receipt that is bound to the exact current suite and taxonomy:

```powershell
python adapters/nusaibah/pharma_company_intelligence_lab/tests/evaluation/review_adjudication.py --emit-template wp1-adjudication-receipt.json
```

A qualified pharma-domain reviewer must complete the receipt with:

- reviewer name and qualification basis;
- an explicit taxonomy decision and notes;
- one decision for every case;
- a second reviewer and resolution for every disagreement;
- a named domain owner and calibrated quality-threshold decision.

After independent review is complete, apply the receipt:

```powershell
python adapters/nusaibah/pharma_company_intelligence_lab/tests/evaluation/review_adjudication.py --apply-receipt wp1-adjudication-receipt.json
python adapters/nusaibah/pharma_company_intelligence_lab/tests/evaluation/review_evaluation_status.py
```

The applicator fails closed if the receipt was created against different suite/taxonomy content, omits a case, lacks reviewer qualification text, leaves taxonomy/thresholds pending, or records a disagreement without a second reviewer. Applying a structurally valid receipt is mechanical evidence processing; it does not independently authenticate the human identity or qualification asserted in the receipt. Reviewer/domain-owner identity must therefore also be traceable in the approved review record (for example PI-1984).


## Pinned-baseline replay

`review_baseline_replay.py` is an **evaluation-only** bridge for PI-1986. It does not add a production input, change the 0.1.12 manifest, change Agent definitions, change provider/model policy, or authorize any write.

Current adjudicated-suite compatibility:

- 11 `company_research` cases can be projected into the existing bounded `governed_company_baseline` field for evaluation.
- 13 `document_review` cases remain `not_executable`; 0.1.12 has no document/file input contract.
- Synthetic replay uses preview mode, a neutral read-only synthetic company memory, and the production-supported `company_methodology` first-run state.
- Mutable Dynamic Skill roles are rejected by the replay wrapper.
- Expected findings, adjudication truth, held-out labels, and release thresholds are never inserted into provider input.

The replay deliberately bypasses the production Companies binding because the fixtures are synthetic. This is an evaluation comparability difference, not production capability. The per-case replay record must retain that difference explicitly.

A runtime delegate used for an actual replay must expose only the normal trusted helpers needed here:

```text
invoke_agent(...)
skill(...)
```

Agent calls still execute the pinned 0.1.12 role graph and validators. The fixed methodology handle must validate to:

```text
nusaibah.pharma-intelligence-methodology@1.0.0
sha256:2fa082aca1c100abb60a4bf77aa4cf796da2707bb951a3b51f11948efd2dd564
```

Do not supply `company_memory_update` or `company_methodology_update` authority to this evaluation lane.

The harness is not itself a quality measurement. PI-1985 remains incomplete until actual provider-backed replay observations are recorded and scored through `review_baseline_measurement.py`. Document cases stay explicitly unmeasured rather than receiving inferred values.
