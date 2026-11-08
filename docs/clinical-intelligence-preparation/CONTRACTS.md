# Proposed clinical contracts

All names and schemas in this directory are draft design contracts. They must
be mapped to exact admitted runtime contracts before any executable intake.

## Ownership and logical responsibilities

| Responsibility | Direction | Boundary |
| --- | --- | --- |
| `clinical_intelligence_gateway` | New future public asset | Semantic request and bounded safe projection only |
| Identity / membership preparation | Reuse admitted mapping first; specialist only if needed | Conditional governed resolution, no invented canonical IDs |
| `clinical_trials_lookup`, `pubmed_evidence`, `umls_terminology` | Reuse exact admitted versions | Evidence acquisition belongs to source/runtime authority |
| `clinical_failure_intelligence` | Preserve existing versions | Failure-specific investigation, not neutral or class-wide evidence collection |
| `clinical_trial_assessment_engine` | PI-1751 dependency | Generic deterministic engine plus registered governed ruleset; no publication |
| `clinical_reasoning_review` | First future review-only candidate | Exact retained snapshot, independent review and new correction artifact |
| `clinical_class_synthesis` | Future specialist | Verified normalized product assessments, descriptive synthesis and independent critic |

These are logical roles, not a request for nine new packages. Exact source
versions, runtime versions, Skill digests, Agent/provider roles and input roles
must be pinned during admission, never guessed by these draft schemas.

## Public request and conditional identity resolution

`gateway-request.schema.json` accepts a natural-language request, typed scope,
semantic product/molecule/class selectors and optional supplied mappings.
Supplied mapping is starting context, not an authority grant. Do not perform
DLM lookup solely because a mapping was supplied. Resolve only missing,
ambiguous, conflicting, stale or authority-dependent identity/membership.

Class IDs and legacy `pharmacological_group_id` have distinct fields. A legacy
mapping carries its source reference; the platform must validate equivalence
before adapting it. Multiple class relationships per molecule are allowed.
Absence of mapping is a resolution requirement, never permission to rename an
ID or infer one from a label. A mapping source ref does not attest its truth.

The public request cannot select a lake, node, binding, tenant, actor, provider,
model, runtime, arbitrary ruleset, approval flag or output destination. It
cannot carry retained scientific payloads. Its product IDs are semantic scope,
not storage authorization. Existing facade byte limits and untrusted-content
handling remain required even when a string passes this draft schema.

## Frozen membership and coverage

Before product work, the host must freeze an immutable inventory containing:

- authoritative classification system, class ID, membership revision/digest,
  source/as-of, product/molecule relationships and any verified legacy mapping;
- `all_known_in_snapshot` or `selected_subset`, explicit selected products, known
  excluded products, unresolved identities and inventory completeness;
- product–indication–trial cases and the exact assessment inventory per case;
- independently recorded run IDs, join contract, finite product/concurrency/
  source/provider/elapsed/result-byte budgets and continuation boundary.

`class-scope.schema.json` is independently versioned as
`clinical_class_scope.draft.v1`. All-known coverage is relative to the frozen source and date. A subset
never becomes a complete class review, even if every selected product succeeds.
Product coverage and product–indication–trial case coverage are separate. A
complete list of products does not prove that every clinical case is covered.
Unknown inventory size prevents a claim of complete class evidence.

The draft fixes all three scope arrays at 128 and chooses pre-launch blocking
for any larger governed extent. `extent` preserves known totals and prohibits
truncation or unqualified pagination; overflow returns an explicit blocked
gateway response instead of a shortened scope. See [review refinements](REVIEW_REFINEMENTS.md).

## Existing versus missing assessment

For each frozen case, the inventory distinguishes `existing_verified`,
`missing`, `partial`, `deferred`, `unavailable` and `identity_conflict`.
Only `existing_verified` may enter normal retained re-review. Partial/deferred
inputs may be inspected but must retain their quality and cannot count as fully
assessed coverage. Missing failure is not evidence of clinical success.

`assessment-handoff.schema.json` proposes the internal retained input reference:
exact producer key/version/run/output role, semantic subject, content digest,
evidence-as-of and source snapshot, reason graph, methodology digest, model
revision and quality state. The host must verify all fields against retained
readback and Core-owned input authority; none is a ChatGPT argument or trusted
merely because its JSON validates. A digest alone is not authority.

Normalized `quality: accepted` means verified retained/structural eligibility,
never scientific validation. Preserve `producer_quality` separately and retain
the source's uncertified-science flags. The ordered crosswalk maps completed,
partial, preflight/deferred, verification failure, staleness and unknown states
without upgrading scientific truth. Structural issues and unresolved scientific
questions remain distinct. See the exact [crosswalk](REVIEW_REFINEMENTS.md).

Preserve the original snapshot and graph. Corrections are new artifacts with
parent review/assessment references. Never rewrite the prior result in place.
If no governed retained original is available, report `unavailable` and stop
that review path. Do not present a dry-run output as durable governed evidence.

A missing assessment is routed to the PI-1751 neutral path only when that exact
engine/ruleset/source combination is admitted. The generic engine's no-publish
output needs a separately authorized host retention/readback handoff before a
later specialist consumes it; do not silently change the engine lifecycle.

## Orchestration and normalization

Reuse recorded Assets/OBS host orchestration: freeze plan, independent bounded
product work, verified retained-result join, normalization, ordered class
synthesis, independent critic, versioned report. No nested Python callable
recursion, generic write-anything tool, new scheduler or private API client.

Normalize identity, indication, endpoint, comparator, phase, population,
mechanism, evidence date and quality before comparing products. Preserve
contradictions, source overlap, duplicate trials, negative selection bias and
missing cases. Incomparable strata remain separate. Source studies reused by
multiple products cannot be counted as independent corroboration.

## Class review and scientific limits

`class-review.schema.json` proposes a full internal report with coverage,
stratified findings, citations, reason-graph refs, independent critic and
limitations. Findings distinguish class, subclass, molecule and product–
indication scope. Numeric pooling, causal conclusions, effect estimates or
probabilities require an independently admitted methodology; descriptive
denominator reuse is not meta-analysis.

`coverage.class_generalization_supported = true` is structurally allowed only for
all-known complete inventory, complete assessment coverage, established
comparability, completed independent criticism and no unresolved critic
findings. These are necessary conditions, not scientific sufficiency. The
platform must additionally verify set membership, denominators, provenance,
case coverage, cited findings and critic independence. Schema flags cannot
self-authorize a conclusion. An empty assessment set withholds generalization.

This boolean is distinct from `membership_complete`, `selection_complete`,
`execution_complete`, `evidence_complete` and `scientific_review_complete`.
The first five may also be unknown (`null`). `coverage.schema.json` retains
product and case disposition counts separately, source-specific coverage and
an explicit unknown inventory denominator. A completed execution may still have
partial evidence and missing/blocked assessment dispositions.

The offline reference checker verifies identities, count/set consistency,
retained-reference joins and structural generalization prerequisites. It does
not authenticate refs, verify actual source digests or prove reviewer
independence, cited scientific truth or statistical comparability.

The report is versioned and links retained inputs. Any Skill improvement is
preview-only, with `apply_authorized: false` and `write_attempted: false`.
Fixed methodology requires a reviewed new version. Product/class Dynamic Skill
mutation is outside this preparation; future human attestation, scoped role,
CAS digest, committed receipt and fresh readback are separate gates.

## Public accepted/status/readback projection

`gateway-response.schema.json` drafts the safe response shape. The request's
`request_assessment`, `get_status` and `get_result` operations are proposed names,
not existing registered MCP tools. A future bounded response must carry an opaque
server-owned run reference and a safe state (`accepted`, `running`, `partial`,
`completed`, `failed`, `blocked`), stage/progress counts, safe error code and
authorized next action. Result readback returns bounded conclusions, coverage,
versioned report refs and approved citations, not a full clinical payload.

Repeated reads and transport retries must resolve the same admitted run;
readback must recheck caller/surface/publication scope. Timeout is not success,
must not erase run identity, and must not trigger new paid work. Current MCP's
bounded terminal waiter does not establish this complete lifecycle. No public
start/status/read function is certified by this preparation.

The draft examples cover existing review, neutral missing-assessment, class
review, status/readback requests and accepted/partial/blocked responses. The
32 KiB public projection ceiling and per-array bounds are conservative proposed
design limits, not current publication settings or scientific budget approval.
Exact authenticated ref types and publication limits must be reconciled at
admission; the draft's bounded semantic strings do not create a new authority.
