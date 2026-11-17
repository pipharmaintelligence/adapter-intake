# Contract review refinements — 9 November 2026

Disposition of the two P0 refinements in the supplied PR #174 review and the
PI-2086 review-disposition comment. These changes remain preparation only.
Contract sign-off, P1 proof and runtime admission are still outstanding.

## 128-item policy: block overflow, never truncate

This draft chooses **explicit pre-launch blocking**, not pagination. The three
independent bounds remain 128 eligible products, 128 selected products and 128
selected product/indication/trial cases. A product may have many cases, so the
case bound can be exceeded even when the product bound is respected.

The host must inspect the governed snapshot's extent before constructing a
bounded `class_scope`. `extent` records independently established eligible,
selected-product and selected-case counts. Known counts must equal the full
corresponding arrays; an unknown count is `null`, not zero or the current page
length. Unknown eligible/case extent forbids the corresponding completeness
claim. `truncated` and `pagination_applied` must both be false.

If any observed extent exceeds 128, emit the proposed bounded gateway response:

- `status: blocked`, `stage: inventory`, `run_ref: null`;
- `reason_codes` includes `class_scope_limit_exceeded`;
- `scope_limit` identifies the fixed limits and observed counts;
- `coverage: null`, no reports/citations, `next_action: revise_scope`.

The synthetic `oversized-snapshot.gateway-response.json` demonstrates 129 known
products. No class/product work is launched, no prefix of the snapshot is
passed downstream, and no completeness fraction is produced. The caller may
request a deliberately narrower governed scope; the host must not silently
convert an all-known request into a subset. If authoritative counts cannot be
established, report incomplete/blocked identity or inventory work, never a
complete class. Schema-valid extent fields alone cannot authenticate counts;
their comparison to the actual governed snapshot remains a platform gate.

Deterministic snapshot pagination is **not implemented or authorized**. A future
design would require snapshot-stable pages, exact membership/case identities,
ordering, deduplication, totals, checkpoint/join and completeness proof before
changing this policy. This refinement adds no scheduler or larger Python loop.

## Meaning of handoff `accepted`

`assessment-handoff.quality` is a normalized **retained/structural eligibility
disposition**. It is not a producer status, a scientific acceptance decision,
clinical success, independent truth verification or class-generalization grant.

Preserve original `producer_quality.status`, `scientific_accuracy_certified`,
`external_truth_verified` and `automated_review_only`. For inspected Clinical
Failure Intelligence 0.1.16, the last three values are respectively `false`,
`false` and `true`, even when producer status is `completed`. The draft schema
rejects changing those flags for that exact producer/version.

The host separately verifies retained bytes/digest, subject/case identity,
structure and freshness. The crosswalk is ordered; the first matching row wins:

| Verified condition | Normalized handoff quality |
| --- | --- |
| Retained artifact unavailable/integrity failed, identity conflict, invalid structure or unresolved structural issue | `blocked` |
| Retained integrity, identity or structure not positively verified | `unknown` |
| Freshness established as outdated | `outdated` |
| Freshness unknown | `unknown` |
| Verified current structural input; producer `completed` | `accepted` |
| Verified current structural input; producer `partial` | `partial` |
| Verified current structural input; producer `preflight` or explicit `deferred` | `deferred` |
| Unexpected producer status | `unknown`, preserving the original status |

Freshness is evaluated under an approved policy, never an invented age cutoff.
`verification` in this draft is a proposed internal receipt projection, not a
caller-authorable grant. Its flags must come from authenticated runtime checks.
Raw references and checksums without authority do not meet this requirement.

An accepted retained assessment can still have unresolved **scientific**
questions. Preserve `unresolved_reason_codes`; structural blockers are recorded
separately in `verification.structural_issue_codes`. Do not reject a scientific
counterexample merely to make an accepted input look certified.

Product `accepted` and `completed_case_count` require structurally eligible
retained joins for the selected cases; they do not set `evidence_complete`,
`scientific_review_complete` or `class_generalization_supported`. Those remain
separate reviewed dimensions. Product/case `deferred` and `unknown` dispositions
and counters are explicit and cannot be folded into accepted counts. `missing`
means no assessment reference is available, not a handoff quality and not a
clinical outcome.

The offline crosswalk and schema checks are reference behavior for preparation.
They perform no Core read and prove no real artifact, scientific quality or
authenticated input binding. P1 remains the first runtime-authority dependency;
see [read proof status](P1_READ_PROOF.md).
