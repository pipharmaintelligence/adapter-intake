# Delivery gates and acceptance plan

## Authorized boundary

This change includes source reconciliation, draft schemas, synthetic fixtures
and offline contract checks only. It excludes runnable adapter admission,
materialization, Assets promotion, release/version bump, workflow enablement,
MCP publication, deployment, source/provider execution and Skill mutation.

No `adapter.yaml` is created: `release_stage: development` alone would not
prevent an intake from being materialized. Documentation is intentionally kept
outside `adapters/` and is absent from every helper/support-file allowlist.

## Ordered implementation slices

| Gate | Owner / reuse | Required proof before advancing | Current state |
| --- | --- | --- | --- |
| P0 Draft contracts | adapter-intake | Optional identity, explicit coverage, retained handoff and class review reviewed; offline positive/negative fixtures | Two review refinements addressed; contract sign-off outstanding; not runtime-admitted |
| P1 Retained source authority | Core + Assets operator verification | One exact governed retained assessment; producer/run/output role; digest; child-owned input binding; dry-run distinguished from persistence | Started; configured database read unavailable; no real source verified |
| P2 Read-only inspection candidate | Future `clinical_reasoning_review@0.1.0` | No Agent/provider/write initially; wrong identity, missing graph, tampered digest, partial/deferred and unavailable inputs fail safely | Not implemented |
| P3 Independent review | Existing trusted Agent and fixed Skill roles | Exact child-owned provider/input/Skill version; contradictory/wrong-trial/wrong-indication/withdrawn evidence; original immutable | Not implemented |
| P4 Neutral missing-assessment path | PI-1751 | Generic admitted ruleset, source compliance, bounded scan/continuation; no failure/success inference; explicit retention handoff preserving no-publish engine | Dependency |
| P5 Class normalization / synthesis | Future class specialist | Frozen membership and case inventory, independent product runs, verified join, heterogeneous strata, duplicate evidence, denominator and missingness checks | Not implemented |
| P6 Independent class critic | Admitted separate review role | Challenges causality, selection, subclass/molecule specificity, unsupported generalization and source coverage | Not implemented |
| P7 Durable public lifecycle | Existing facade/jobs extended generically if required | Accepted run identity; status and authorized readback; timeout/replay/expiry/scope tests; bounded result projection | Not certified |
| P8 Optional publication / Skill work | Separate authorization | Governed output schema/idempotency/readback; separately attested human consent, CAS and receipts for any mutable Skill | Excluded |
| P9 Promotion and live qualification | Separate user instruction | Reviewed intake source, exact package/runtime/worker and admitted roles; signed provider/source/Skill combination; external MCP proof | Explicitly prohibited now |

The proposed class sequence uses an independent-product join followed by ordered
specialist stages. Existing effect-free test coverage is not certification of
that entire multi-stage clinical sequence. Do not enable the shipped empty
registered handler map or FIFO dispatch switch during preparation.

## Contract checks in this branch

The dedicated test suite validates every draft schema, synthetic examples and
negative mutations for unauthorized fields, subset completeness, incomplete
coverage, unreviewed generalization, lost retained provenance and write flags.
Overflow is explicitly blocked before launch; no truncation or pagination is
admitted. Handoff acceptance is structural/read eligibility only, with original
scientific flags preserved and deferred/unknown counters retained.
The existing repository intake guard also runs to check unrelated admission
contracts remain intact. These checks prove shape and conservative structural
gates only. They do not certify live authority, scientific quality or a runtime.

The independent Fixed usage Skill design adds approved-section discovery/read
contracts while P1 remains blocked. It creates no runnable Skill, manifest or
publication. Its text/audience sign-off, sealed digest, exact runtime declaration,
optional host installation and actual ChatGPT compatibility are separate later
gates; none is inferred from the generic Skill Reader development proof.

## Later behavioral acceptance matrix

| Scenario | Required outcome |
| --- | --- |
| Valid supplied mapping | Use as context; authority validation only where needed; no mandatory redundant DLM lookup |
| Missing / ambiguous / conflicting identity | Resolve through admitted governed mapping or return actionable blocked state; invent no ID |
| Class versus legacy group mismatch | Require verified explicit mapping; never silent alias |
| One molecule in multiple classes | Preserve classification system and many-to-many relationships |
| Selected subset fully assessed | Label subset coverage; no complete class/generalized conclusion |
| All-known products, unknown or stale membership | Refreeze or report incomplete; no complete-class claim |
| Retained result missing / digest changed / wrong product | Block that input and preserve recorded reason; no substitution |
| Partial / deferred assessment | Preserve quality, gaps and original graph; exclude from fully assessed denominator |
| No failure record | Neutral assessment dependency, not success; if unavailable expose missing coverage |
| Duplicate trial/publication across products | Deduplicate corroboration; preserve links and affected strata |
| Incomparable indication/endpoint/comparator/population | Separate strata; withhold pooled interpretation |
| Class critic challenges generalization | Preserve contradiction and withhold class conclusion |
| All products succeed but one indication/trial case missing | Case coverage incomplete; no full review claim |
| Provider budget / timeout / one child failure | Durable partial/blocked run with missing case list and authorized recovery |
| Caller timeout or duplicate request | Same durable run identity; no automatic duplicate scientific execution |
| Foreign tenant / revoked publication / expired admission | Reject start and readback; no retained/source leakage |
| Output dry-run or no-publish | Do not claim governed persisted evidence or committed result |
| Model returns approval or arbitrary tool instruction | Treat as data, never platform authority; no write or escalation |
| Skill improvement requested | Preview only; fixed Skill immutable; future mutation needs separate attested approval and CAS |

## Decisions still to settle

1. Which governed source and classification systems define class membership,
   and is there an authoritative class-to-legacy-group crosswalk?
2. Which exact persisted assessment is eligible for the first read-only proof,
   and what child input binding/retention policy authorizes it?
3. Which scientific methodology governs comparability, class interpretation and
   independent criticism? This branch deliberately invents no clinical rules.
4. Which generic durable MCP run/status/readback contract will be qualified for
   long requests, with finite server-owned budgets and cancellation/recovery?

Both membership coverage modes remain explicit draft options. No answer to
these questions is needed to prepare this branch; unresolved answers block
dependent implementation or certification, not the offline preparation.
