# Pharma specialized-review evaluation suite

This folder starts **PI-1974 / WP1**. It is evaluation infrastructure, not a claim that the future review graph is implemented or that the proposed quality thresholds have been met.

## Current status

- Baseline identity is pinned to asset `0.1.12`, runtime `0.1.97`, and preview run `6e95802c-2336-47f5-b7c2-1e30476a0fef`.
- The suite contains 24 deterministic synthetic cases split into 16 development and 8 held-out cases.
- Cases cover the planned adversarial strata: company isolation, wrong-entity distractors, tables/footnotes, boundary-spanning claims, duplicated overlap, source-version drift, conflicting dates/jurisdictions, OCR/access gaps, source prompt injection, citation laundering, unsupported paraphrase, mandatory-requirement omission, malformed/truncated output, budget exhaustion, preview no-write, and final-synthesis new-claim rejection.
- Every case is currently `pending_domain_review`. Synthetic expected findings are **candidates** until a qualified domain reviewer adjudicates them.
- Source content hashes are intentionally unset until fixtures are frozen after review.
- Unobserved source/input/answer/thinking/cost counters remain `null`; do not manufacture a baseline from the one successful preview.

## Adjudication workflow

1. Review each synthetic source and candidate expected finding against the intended methodology obligation.
2. Confirm applicable requirements and acceptable abstentions.
3. Freeze the source fixture and record its SHA-256 digest.
4. Set a named primary domain reviewer and mark the case `adjudicated`.
5. If there is disagreement, record a second reviewer before resolving the case.
6. Keep development and held-out cases separate. Do not tune prompts or budgets against held-out truth.
7. Only after every case is adjudicated may WP1 claim an evaluation baseline exists.

The test suite deliberately fails closed if a case claims `adjudicated` without reviewer identity, frozen source digest, expected-finding support locators, or explicit abstention coverage.

## Scope boundary

These fixtures do not add document input authority, new provider calls, chunking, retries, memory writes, publication, or runtime configuration. WP2 and later work remain dependency-blocked until WP1 adjudication and baseline decisions are complete.
