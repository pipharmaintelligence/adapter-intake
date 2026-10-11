# Pharma 0.1.21: claim evidence and reviewed methodology

## Scope and authority

This candidate implements the reusable adapter repairs identified in the
Company-14 offline review. It does not rewrite that run's immutable output,
approve unverified statements or upload another Skill package. Company Scope
supplies the original CompanyContext; intelligence does not query Companies.
Core owns retention, authenticated uploads, mutable Skill commits and history.
The Fixed Skill reference, version and digest stay unchanged.

The current contract is preview-only. Independent review and later reviewed
apply admission remain required; neither CI nor an automated critic pass supplies
an apply receipt. Existing published adapter and Agent identities remain intact.

## Review requirements

| Review | Implemented behavior | Evidence still required |
| --- | --- | --- |
| R01 citation handoff | Exact admitted claim locators and bounded citation selection follow candidate fact IDs; unselected/unsupported work is identified. | A source must support the actual statement, not merely exist in the citation list. |
| R02 event dates | Separate event, publication and status-as-of fields; research, critic and synthesis instructions forbid date substitution. | Check the primary record's actual event date. |
| R03 rights direction | Preserve actor, counterparty, territory and manufacturing responsibility. | Verify which party grants and receives each right. |
| R04 current status | Keep current as-of status distinct from historical events; a launch does not establish litigation resolution. | Inspect the latest relevant primary source. |
| R05 context timing | A later external update stays distinct from the governed snapshot. | Source/date and temporal interpretation. |
| R06 entity label | Governed display name and external legal name are distinct. No Companies mutation occurs. | Owner adjudication before any governed identity change. |
| R07 transactions | Agreement and completion remain different event states. | A closing record before asserting completion. |
| R08 financial scope | Totals/components and named remainder are represented explicitly; prompts preserve reported/core, period and geography definitions. | Actual reconciliation against the primary financial table. |
| R09 safety | Potential effects and observed events have distinct observation kinds. | Primary notice/enforcement evidence for actual symptoms and classification. |
| R10 learning | Preserve existing learning; append bounded procedural rules; supply stored review lessons to planning/research. | Review the exact proposed replacement before persistence. |

`semantic_context` is model-supplied scope. Deterministic validation checks its
shape and internal requirements, not agreement with the real world. In particular,
valid date strings, plausible actor names or accepted fact IDs cannot certify the
truth of prose. The independent review packet remains the factual review boundary.

## Recovery and bounded learning

A claim with absent/unadmitted support or invalid semantic context is withheld
without discarding valid siblings. A section containing a withheld claim has its
prose replaced in downstream Agent inputs so it cannot reintroduce that claim.
Original role prose and claim evidence stay in the retained review packet.
An unknown/duplicate synthesis fact ID yields an incomplete company preview and
withholds its candidates; another company's work continues.

Global procedural lessons live under a reviewed addendum marker. Planning and
research receive only stored exact known rule lines as
`learned_methodology_addendum`, separately from their bounded section history.
The projection contains fewer than 2,400 characters and includes no company facts.
Absent learned methodology produces an empty projection and does not block preview.
Research trace accounting includes use of either learning input.

The complete proposed learning replacement must fit the existing 12,000-character
bound and preserve prior text. An optional planner snapshot is included whole only
when it fits and does not repeat existing level-three section headings. Omitted
snapshots remain inspectable in `planner_chunks`; they are never silently truncated.
When no room remains for the addendum, the result reports
`methodology_learning_update_status=withheld_learning_budget` and
`methodology_learning_withheld_reason=methodology_learning_budget_exhausted`.
There is no replacement proposal in that case. Accepted research and the memory
review continue; no full-company failure or authority expansion is introduced.

## Agent contracts and unchanged limits

| Role | 0.1.21 contract version | Change |
| --- | --- | --- |
| methodology_planner | 1.0.7 | Consume optional reviewed learning alongside section history. |
| portfolio_researcher | 1.0.8 | Claim-level support, semantic distinctions and reviewed procedural guidance. |
| market_researcher | 1.0.8 | Same contract within its existing specialist scope. |
| regulatory_risk_researcher | 1.0.8 | Same contract within its existing specialist scope. |
| evidence_critic | 1.0.8 | Explicit source/date/rights/scope review without independent approval claims. |
| intelligence_synthesizer | 1.0.6 | Preserve accepted distinctions and qualifications in dossier/memory prose. |
| strategic_analyst | 1.0.5 | Existing definition, with version-owned semantic guidance in input. |
| memory_benchmark_reviewer | 1.0.4 | Unchanged. |
| research_response_resolver | 1.0.3 | Unchanged one-time faithful formatting repair. |

All Agent steps request 600 seconds. Existing provider models, token/thinking
policies, three-way research concurrency, 1–3 sequential portfolio passes,
logical call ceilings and 1,800-second total execution deadline remain unchanged.
The deadline can shorten a provider allowance; this release does not guarantee
completion after transport/authorization failures. Semantic problems never add
unbounded research or resolver loops.

## Validation and delivery

Run the complete pharma deterministic suite and repository intake-contract test.
These fixtures cover the declared semantic distinctions, candidate-based citation
selection, claim/section isolation, incomplete synthesis recovery, historical
coexistence, zero mutation, learning-budget exhaustion and actual learning delivery
to planning/research. They do not establish production factual accuracy.

Use the existing Assets promotion tooling against the exact clean, pushed intake
commit. Its isolated materialization must preserve the historical package, find
both 0.1.20 and 0.1.21 without duplicate identities or helper conflicts, and pass
package imports/catalog discovery. Exercise the packaged adapter with deterministic
runtime fixtures before any provider call. Do not patch the E installed wheel or
bump the generic runtime to deliver this content repair.

Keep the intake manifest at the canonical filename
`nusaibah_pharma_company_intelligence_lab.asset.json`, containing only 0.1.21.
The current Assets materializer composes historical versions by matching that
filename; a renamed manifest would bypass preservation. The version-owned
`legacy_preparation_helpers_v0_1_21.py` has no Adapter subclass or runtime identity.
It supplies preparation functions without overwriting a historical entrypoint or
colliding with the packaged 0.1.20 Adapter. Catalog verification must resolve every
pre-existing version, not merely find class identities syntactically.

Official promotion, exact-version registration/capability admission, live retained
preview, independent review and approved Skill apply/readback are separate proofs.
Record each only when it actually passes; a local promotion dry-run is not deployment.
