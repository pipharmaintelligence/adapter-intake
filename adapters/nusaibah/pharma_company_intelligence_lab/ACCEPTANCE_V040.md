> Version 0.1.40 implementation candidate. Implementation is authorized; merge, promotion and paid live qualification are not part of this change. This retained requirements baseline describes the target. See [current implementation and limitations](ENRICHMENT_V040_GUIDE.md) and [verification evidence](VERIFICATION_V040.md) before treating any criterion as satisfied.

# Company intelligence — acceptance criteria and verification plan

Date: 14 October 2026, Asia/Amman. Status: **implementation candidate; verification status tracked separately**.

Companion: [Prioritized requirements](REQUIREMENTS_V040.md). Stage-specific evidence is recorded in VERIFICATION_V040.md; deployment and live stages remain pending. Old workflow completion, successful package build or upload 164 does not satisfy this matrix.

## Objective

Prove grounded research gathers useful new evidence, scoped critics improve quality, future-work guidance is actually persisted/reused, and the published document contains supported company intelligence plus unresolved review items. Preserve the framework and existing assets.

## System Context

Baseline regression: company 59 / pharma 0.1.39 produced one historical address/website finding after a website failure, with provider search disabled. Fourteen Agent calls completed; the memory upload was valid but enrichment incomplete. The retained Annex did not reach Markdown. Company methodology remained absent because no aggregate-pass learning proposal was generated.

Tests must reproduce that failure shape and demonstrate corrected behavior. They must not just mock every Agent into a pass or mirror the implementation's flags.

## Approach

Use three evidence stages within the standard intake/promotion process:

1. **Deterministic qualification:** provider-free tests using runtime-shaped grounding, citations, sources, critic responses and Skill fixtures. These prove contracts and containment, not live provider quality.
2. **Promoted runtime qualification:** exact official artifact, imports/catalog, Agent contract admission and zero-provider capability/read tests. These prove deployed availability, not research success.
3. **Authorized live content qualification:** one later authorized company case, with actual provider grounding and actual published ZIP/readback inspection. This proves the tested live case; it does not prove all companies or large-scale ECS operation.

Acceptance does not mean every research question gets an answer. It means actual discovery was attempted, supported results survive, missing evidence is honest, useful feedback is recorded, and publication/readback reflects reality.

This matrix is for release verification. It does not add 30 runtime checks, approval stages or Agent calls to each company. The operational flow remains grounded research, scoped critique, consolidation and the existing publication lane.

## Changes Made

Acceptance definitions only. No test executions, implementation, provisioning, merging, installation or paid run were performed for this proposed repair.

### P0 acceptance matrix

All P0 criteria are required for release closure. A missing result stays pending; a failed result requires a focused repair rather than a new paid run through the unchanged defect.

| ID | Requirements | Scenario | Observable acceptance |
| --- | --- | --- | --- |
| A01 | R01, R03 | Company has no readable website | The research-role contract requests grounded search using the identified company and assigned section. Neither absent website nor HTTP failure turns search off. Native search invocation/citation observations reflect what actually ran. |
| A02 | R01, R15 | Exact researcher contracts | Only intended researcher roles have search enabled. New exact contract versions are provisioned/admitted consistently with the manifest; historical role contracts are untouched. Benchmark remains disabled. |
| A03 | R02 | Valid native grounding; page reread fails | A traceable runtime-admitted grounded claim reaches semantic critique. Direct-read failure is recorded separately and does not automatically discard that claim. No fabricated literal quote or webpage offset appears. |
| A04 | R02, R11 | Model invents a URL or uses another claim's citation | The affected claim cannot acquire admitted-evidence authority from its own strings. Its issue is retained; unrelated valid grounded claims continue. |
| A05 | R02, R04 | Readable source with exact text | The existing exact-span path still resolves correct offsets/snapshots, rejects corrupted spans and preserves citation provenance. Native grounding does not weaken literal-source checks where those checks apply. |
| A06 | R03, R11 | Wrong company/parent, historical date or conflicting evidence | Critics preserve entity/date qualifications and localize contradictions. A historical baseline is not presented as a current legal-entity/product/regulatory fact. |
| A07 | R04, R18 | Long source and several sections | Packets follow paragraph/subsection boundaries, are measured before dispatch, preserve source coordinates, and fit budgets. Parallel calls never exceed configured concurrency; no Agent receives the entire growing corpus by default. |
| A08 | R05, R07, R11 | A section contains a supported finding and an unresolved question; another section is supported | Both sections' supported claims continue toward synthesis/publication, including the supported claim in the deficient section. Missing answers yield explicit gaps and actionable guidance. Neither section-level nor aggregate failure erases supported facts or blocks valid procedural feedback. |
| A09 | R05, R06, R16 | Critic reviews an evidence/freshness issue | The same critic response supplies a specific improvement, target role/section, observed basis and verification expectation. No extra Agent call is created merely to describe methodology. |
| A10 | R06, R07 | Failed/insufficient section yields useful advice | Valid procedural advice can be proposed/persisted despite non-pass aggregate quality. It contains no new unsupported company fact or fabricated positive verdict. |
| A11 | R06, R08 | First run, no memory/methodology | Absence is accepted. Research continues. Supported memory and valid guidance use existing first-package initialization. Missing packages are not replaced by fabricated upload receipts. |
| A12 | R06, R08 | Subsequent run with stored guidance | The relevant research/critic input includes selected previous guidance, identified by origin/digest. The changed query/focus/verification behavior is inspectable; a bare 'loaded=true' flag is insufficient. |
| A13 | R06, R14 | No new useful guidance | No duplicate boilerplate or fake history event is written. `no_change` has a clear reason and correctly reports existing or absent baseline/readback. |
| A14 | R09, R13 | Grounded company fixture with adjudicated relevant facts | Published memory preserves baseline and contains the supported profile/enrichment expected from the fixture, with source/date qualifications. It is not merely a copied company-ID/address record or generic unresolved-chunk text. |
| A15 | R09, R11 | Honest zero-finding result | No ungrounded fact is fabricated to create a larger document. Retained result explains actual search attempts, evidence outcomes and next-work guidance. It does not claim fresh enrichment or an upload that did not happen. |
| A16 | R10, R19 | Outstanding scoped issue in published memory | Fresh readback Markdown contains `Annex: Need Review` as a table with section/subsection, paragraph when known, short issue and simple reference. It does not copy full source text. |
| A17 | R10, R19 | Unknown paragraph or missing citation | Published Annex uses `—` for unknown location/reference. It does not fabricate a paragraph number or cite an identity baseline as support for unrelated conclusions. |
| A18 | R11, R12 | Markdown/fenced JSON or one malformed Agent response | Deterministic normalization and no more than one applicable backup run. Persistent role failure becomes a scoped issue. Supported sibling results survive; backup cannot invent citations or change a negative verdict. |
| A19 | R11, R14 | Admission/authentication/integrity/destination problem | The legitimate platform boundary remains enforced. No fallback bypasses governance, private-network safety, client scope, stale baseline protection or storage authority. A confirmed failed write cannot be reported as a successful publication. |
| A20 | R13 | Completed execution with partial content | Existing result fields distinguish execution completion, real publication receipts, incomplete research and remaining gaps. Counts reflect actual native search, accepted/withheld facts and usable feedback. Upload success alone is never the content-quality acceptance. |
| A21 | R14 | First creation and subsequent update | ZIP targets the correct company partition, uses current initialization/update/CAS capabilities, preserves other resources, and has matching fresh content/package readback. Updates expose actual history/changelog; first creation is not misreported as an apply-history change. |
| A22 | R14 | Memory commits but guidance write/readback fails | Preserve the real memory receipt and show the guidance failure. No invented cross-Skill atomicity, blind resubmission or rerun of paid research to recover a storage observation. |
| A23 | R15 | Promotion coexists with prior assets | Source closure, immutable historical files, manifest versions, catalog identities and package imports pass. Official workflow artifact provenance is verified. No new execution lane or manual runtime replacement is introduced. |
| A24 | R18, R19 | Search/read timeout or bounded work exhaustion | Finite budgets and safe phase/status/role/section diagnostics remain visible. Timeout is not silently converted to sufficient evidence. Exhaustion does not trigger an infinite loop or erase unrelated work. |
| A25 | R20 | Developer follows current README | The current model leads to grounded research, scoped critique and automated enrichment/publication. Historical manual approval/source-only instructions are clearly versioned and do not prescribe the new release. |

### P1 acceptance matrix

These are required when claiming the corresponding optional feature or efficiency improvement. They must not be smuggled into every one-pass run as additional mandatory Agents.

| ID | Requirements | Scenario | Observable acceptance |
| --- | --- | --- | --- |
| A26 | R16 | Shared facts/sources and repeated guidance | Deterministic deduplication avoids repeated facts and guidance without deleting conflicting evidence. Agent inputs contain only task-relevant rules and selected prior feedback. |
| A27 | R16, R18 | Fixed fixture before/after | Report per-role calls, packet sizes and provider usage with business coverage. Explain required discovery/critic work; fewer calls or tokens do not count as an improvement if research quality regresses. No invented zero-cost or token savings. |
| A28 | R17 | Default runner invocation | One targeted pass, no reflection, consolidated publication once. Benchmark stays disabled. |
| A29 | R08, R17 | Explicit two-pass request | Pass 2 consumes pass-1 supported findings and critic guidance in RAM and addresses assigned gaps. It does not reload the unchanged pre-run package and falsely claim to have reflected on the first result. Publish the final result once. |
| A30 | R17, R18 | Explicit three-pass request or insufficient remaining budget | Pass 3 uses updated prior results/guidance when admitted and budgeted. Otherwise preserve completed work and report the skipped/incomplete pass honestly. Never claim current one-pass 0.1.39 already satisfies this. |

### Verification scenarios to build

| Scenario family | Required fixtures |
| --- | --- |
| Acquisition | Missing website, HTTP failure, thin homepage, valid native grounding, fabricated URL, same-company external source, misleading parent-company source |
| Source packets | Long multi-paragraph document, overlapping sections, duplicate source, corrupted literal span, native grounding without readable page text |
| Critics and feedback | Supported section plus insufficient sibling, stale baseline, duplicate claim, contradictory sources, actionable feedback, vague boilerplate feedback |
| Learning lifecycle | First-run absence, real feedback initialization, subsequent selected feedback read, resolved/superseded advice, unchanged guidance, partial Skill commit |
| Response recovery | Complete JSON wrapper, malformed original, successful single backup, exhausted backup, transport timeout and negative verdict preservation |
| Publication | Supported profile with Annex, unknown paragraph, preserved prior memory/ZIP resources, first creation, fresh readback, CAS conflict and failed write |
| Compatibility | Historical adapters unchanged, exact new role contracts, intake tests, packaged imports, catalog, official artifact and pre-existing assets preserved |

Use synthetic/adjudicated fixtures for deterministic factual assertions. Keep runtime-shaped citation metadata intact. A test that mocks only a 'search enabled' flag does not prove native grounding admission or claim-citation mapping.

## Modularity Impact

The matrix validates existing capability contracts and their composition. It does not authorize a new Core storage API, bespoke lane, manual Skill policy, direct database/storage access from adapters, benchmark stage or separate methodology-authoring Agent.

## Validation

### Required later live proof

After provider-free and promoted-package qualification, a separately authorized live case must show:

- Correct CompanyContext and optional prior memory/guidance were used; Companies were not re-queried downstream.
- Native grounded research actually occurred, with real runtime receipts/citations and available claim support; it was not confined to the old company baseline.
- At least one relevant discovery result beyond baseline reaches the appropriate section/critic in the selected demonstration case. If live evidence is unavailable, mark the business demonstration inconclusive/partial rather than manufacture a pass or use an arbitrary minimum fact count.
- Fresh cloud readback contains the supported company profile/enrichment and any `Annex: Need Review` rows.
- Actual selected critic guidance appears in methodology when there is a valid delta; otherwise a precise no-change reason is shown.
- A subsequent provider-free runtime-shaped consumption check proves the saved guidance is read and routed into future Agent inputs. Claim a paid second-pass improvement only if such a run was separately requested and actually performed.
- All actual upload, readback and history receipts, sizes and incomplete outcomes are recorded faithfully.

Do not run a new paid case simply to make a failed deterministic contract green. Do not rerun research to compensate for a recoverable read-only storage-observation failure.

### Evidence record

For each criterion record ID, pending/pass/fail/not-applicable status, scenario, exact intake commit, promoted commit/artifact, runtime/asset/Agent contract versions, command or run UUID, relevant artifact/digest, observed outcome and limitations. A not-applicable decision needs a reason; it cannot hide a required missing proof.

Operational summaries retain technical metadata; no credentials or full business documents are copied into logs. Inspect actual business Markdown in RAM or an authorized document view rather than saving extra local copies for this E runner.

### Completion rule

The repair is complete only when the P0 matrix is satisfied at its stated evidence stages and the actual published document is inspected. Provider-free tests alone cannot certify live discovery; workflow/upload success alone cannot certify useful content. P1 reflection claims require their corresponding qualification. One live company case does not establish arbitrary-company accuracy or 15,000-company ECS scale.

## Risks / Open Questions

- Confirm which native claim-support and citation shapes the deployed SDK exposes before defining the new research response/validation contract.
- Confirm source capabilities and Agent contracts are admitted in the intended substrate. Do not assume a browser fallback or search result can bypass current governance.
- Final schema field names and guidance/item/input bounds remain design decisions. They must be finite, measurable and compatible with the existing lane; this document invents no deployed schema or budget value.
- The current 0.1.39 production contract is one-pass-only. Optional two/three-pass support must be explicitly qualified, not claimed retroactively.
- Provider-free evidence is recorded in VERIFICATION_V040.md. Merge, promotion, installation and paid execution remain stopped at the user-requested review boundary.
