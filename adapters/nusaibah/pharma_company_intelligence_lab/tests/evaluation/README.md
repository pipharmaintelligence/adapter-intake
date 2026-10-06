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

- 11 `company_research` cases can be projected into the existing bounded `governed_company_baseline` field for evaluation. This is structural compatibility, not proof that any case can pass a positive public-web smoke. The synthetic identity fixture conflicts with the frozen citation requirement; keep the positive completion gate open pending a reviewed acceptance decision.
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

Evaluation asset 0.1.2 requires explicit `diagnostic_baseline_replay` purpose and supplies a no-provider preflight. See [evaluation developer guide](../../../pharma_company_intelligence_lab_evaluation/DEVELOPER_GUIDE.md). Do not change expected findings or convert supplied-source locators into provider citations to force completion.


## Supplied-source 0.2.1 candidate evaluation

`supplied_source_candidate_evaluation.py` scores retained `0.2.1` preview artifacts against this adjudicated truth set without executing providers. This is a separate candidate-quality track; it does not complete or replace the frozen `0.1.12` WP1 baseline.

The evaluator fails closed unless it can bind the exact adjudicated fixture, truth-free input JSON, retained preview bytes, run identity, candidate asset identity, source digest and methodology digest. It verifies exact supplied-source citation spans, wrong-company exclusion, coverage accounting, summary agreement and logical-call bounds before quality scoring.

Semantic claim matching is never inferred from substrings or from the candidate model's own verifier verdict. Generate a bound review receipt and have an independent qualified reviewer complete the expected/observed finding decisions and obligation accounting:

```powershell
python adapters/nusaibah/pharma_company_intelligence_lab/tests/evaluation/supplied_source_candidate_evaluation.py `
  --case-id company-small-identity-001 `
  --inputs <truth-free-inputs.json> `
  --retained-result <retained-preview.json> `
  --emit-review-template <candidate-review.json> `
  --pretty
```

After independent review, evaluate the exact same bytes:

```powershell
python adapters/nusaibah/pharma_company_intelligence_lab/tests/evaluation/supplied_source_candidate_evaluation.py `
  --case-id company-small-identity-001 `
  --inputs <truth-free-inputs.json> `
  --retained-result <retained-preview.json> `
  --review-file <candidate-review.json> `
  --usage <existing-run-usage.json> `
  --safe-status-output <candidate-safe-status.json> `
  --pretty
```

Cases that cannot enter the focused company-review contract are reported as `not_executable`; blocked or pending-review cases remain explicit and are never dropped from a finite batch. Missing usage values remain unknown. The candidate evaluator computes finite-set quality metrics but intentionally does not apply the frozen WP1 release gate: candidate thresholds require an explicit compatibility/calibration decision.

This evaluator currently admits **development cases only**. Held-out fixture lookup, template emission and scoring fail closed until a reviewed development-freeze/admission contract is implemented. Freezing a local prompt or changing the receipt's split does not bypass this boundary. Expected findings, abstentions, reviewer labels and held-out answers must never be inserted into Agent inputs.

### Integrity and scoring boundaries

The evaluator reuses the unchanged, standard-library-only supplied-source `prepare_review` contract to derive the exact snapshot, chunks, methodology and finite plan from the input. This imports source code from this checkout; it calls no Agent. Retained plans cannot choose their own call limit, concurrency, deadline or repair count. All four domain obligations must appear exactly once for every planned chunk, including reviewed questions with no findings. Inventory, accepted/withheld findings, exact citation spans and local/global verdict digests must agree with that plan.

The bound reviewer receipt records both `methodology_digest` (the fixture's Fixed Skill) and `candidate_methodology_digest` (the actual supplied-source method). Each input/result file is read once so the receipt hashes the same bytes that were parsed and validated, even if the file changes afterwards. These different methods are not made equivalent by sharing a company name or source locator. Expected/observed matches must be reciprocal and one-to-one. Additional supported findings contribute to candidate precision, but never count as recovering missed expected truth or increase recall.

The reviewer name and qualification text are a required recorded assertion, not independent identity authentication. Keep the qualified reviewer decision traceable in the approved review record. Exact source matching establishes provenance; human adjudication establishes semantic quality for the evaluated set.

Usage evidence must explicitly contain the matching `run_uuid`; a missing run identity is rejected. Unknown usage/counter values remain unknown. Free-form usage status text is excluded from the safe projection.

For finite batches, call `aggregate_candidate_reports(reports, expected_case_ids=[...])` with an explicitly enumerated case set. Every declared case must occur exactly once; duplicate cases, omitted cases and mixed suite digests are rejected. Blocked, not-executable and pending-review cases remain visible. This API does not launch providers or infer a full-suite release gate from a selected subset.

CLI evidence failures return a structured `blocked` status and exit code 2. A zero exit code can also mean `pending_review` or `not_executable`; inspect `case_status` before drawing conclusions. `--safe-status-output` writes the safe status for template emission and non-executable cases as well as scoring.

### Existing smoke artifacts

The retained identity smoke with case ID `synthetic-source-review-001` is operational retention/contract evidence. It is not the frozen `company-small-identity-001` fixture. Their source text and identities differ. Do not edit an old retained result, inputs, suite case ID or fixture truth to force a match. New case measurements must use an exact, truth-free input projection of the adjudicated development fixture, and retain the original output bytes. Real document binding, held-out admission, candidate threshold calibration and frozen WP1 baseline completion remain separate work.
