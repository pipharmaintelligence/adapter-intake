# Grounded company profiles — 0.1.40

## Objective

Produce useful, evidence-backed company profiles. Discovery expands the profile; critics improve it and identify claim-local problems. Company methodology stores the critic's concrete advice for the next research run. A completed upload is not evidence of profile completeness.

This is an implementation candidate, **not merged, promoted, deployed, or live-qualified**. The runtime package version is unchanged. See [requirements](REQUIREMENTS_V040.md) and [acceptance criteria](ACCEPTANCE_V040.md) for release qualification.

## System Context

The company-59 run `ab2ff4ca-e9da-4cc5-93eb-a65d5132eca0` published a 931-byte memory containing one old governed-baseline fact after 14 Agent calls. Its researchers requested no native search. A failed optional website read left only the historical CompanyContext. Successful storage did not repair missing research. Version 0.1.27 had deliberately changed researchers to source-only generation; later recovery improvements retained that restriction.

Authority remains unchanged:

- Company Scope resolves companies through Assets/Core and supplies CompanyContext. Pharma does not re-query Companies.
- Runtime-admitted Agent metadata owns native citation provenance. An Agent-authored URL is not provenance.
- The existing callable review toolkit owns exact offsets for readable source text.
- Core owns Dynamic Skill ZIP initialization, updates, partition/storage resolution, concurrency, history and readback.
- Memory and methodology use the same Skill capabilities. This change adds no output lake, approval policy, direct cloud upload or alternate persistence path.

## Approach

1. Read CompanyContext, optional company memory and optional learned company methodology. Preserve the existing fixed-methodology dependency.
2. Route canonical section/subsection tasks deterministically. Do not pay a planner to restate those sections or write a methodology essay.
3. Run bounded section discovery through the three research Agents. Each is explicitly configured for provider grounding. Discovery is scheduled even when the optional homepage fetch fails. Readable evidence is additionally processed in paragraph/subsection packets.
4. Admit readable claims through exact spans, or native-grounded claims through the runtime citation projection. Keep the distinction in retained evidence and published source notes. Native grounding does not manufacture webpage quotes or offsets.
5. Run scoped analysis and section critics. Every supplied claim receives a disposition. A section may need more work while some claims remain supported. Unresolved claims are excluded individually. The same critic response supplies specific future research advice.
6. Consolidate all surviving supported facts, deduplicate exact statements, preserve existing memory and render concise source references. Optional synthesis failure cannot erase reviewed facts.
7. Append the compact **Annex: Need Review** table to the memory candidate. Paragraph numbers are provided only for known source spans; unavailable locations remain `—`. Long source text is not repeated in the Annex.
8. Publish eligible memory and independently useful methodology through the existing Skill lane. Verify receipts and fresh readback. Store no empty first-run memory just to show a successful upload.

Default `portfolio_review_passes=1` performs one pass. Explicit `2` or `3` reads the preceding in-memory candidate and updated critic guidance, then refines it before one final publication. Reflection shares the original 48-call ceiling, provider concurrency, and execution deadline; it does not reset them. If its budget is exhausted, earlier supported findings survive and unresolved work is recorded. A later explicit claim rejection removes that newly proposed fact before publication. Already stored history is preserved.

## Changes Made

### Grounding and claim integrity

Researcher contracts advance to `1.0.12`; critic contract advances to `1.0.12`. Historical contracts and helpers remain immutable. Researchers use a single search-enabled text-generation step with a strict JSON instruction and the existing JSON parsing/one-backup path. Forced JSON generation mode is not combined with native grounding.

Two evidence representations are deliberately different:

| Evidence | Admission | What it proves | What it does not prove |
|---|---|---|---|
| Readable source | Exact locator and unique quote resolved by pinned toolkit | Quote occurs at the retained snapshot offsets | That the source is correct or the claim interpretation is sound |
| Native grounding | Exact runtime-admitted citation, or explicit provider support-segment/chunk mapping | Provider supplied this source association | Independent retrieval or verbatim webpage support |

Both still receive a claim critic. Company, entity, historical/current, date and rights-direction qualifications remain. No fuzzy URI rewriting, invented links, unsupported identity merge, or automatic approval of every generated claim is introduced.

### Feedback and content

The critic returns `claim_reviews` plus up to four `future_guidance` items per chunk: subsection, observation, next action and success check. Feedback can be useful even when the critic gives a negative section verdict. It is stored as readable advice plus a bounded versioned marker, deduplicated, and selected by section on future calls. It grants no tool or storage authority. Missing optional company methodology remains a valid first run; the fixed Skill contract is unchanged.

The critic can identify supplied guidance IDs whose success checks are met by current supported evidence. Resolution markers preserve the earlier text/history while preventing those items from being forwarded again. Unknown IDs and resolutions without supported evidence are rejected within that critic chunk.

The renderer publishes supported facts and their references, not unvalidated synthesis prose. Empty or failed sections are quality gaps recorded in the Annex. Older memory and non-target ZIP resources stay on the existing preservation path. An empty new fact delta does not overwrite memory. Useful critic advice may still be persisted.

### Recovery and stop boundaries

| Condition | Behavior |
|---|---|
| Missing company memory/methodology | Continue first-run research; initialize eligible packages via existing capabilities |
| Optional homepage unavailable | Continue grounded section discovery |
| Citation absent/unmatched | Keep other claims; record the affected claim for review |
| Coverage incomplete or task not applicable | Keep supported work; record missing work without inventing a negative company fact |
| Malformed Agent JSON | Existing deterministic unwrap/parse and one faithful backup; then contain the unresolved chunk |
| Optional strategy/synthesis unavailable | Retain reviewed research and deterministic profile rendering |
| Call, input, time or output budget reached | Record incomplete work; do not label it a full profile or endlessly retry |
| Authentication, company scope, forged toolkit integrity | Preserve hard authority rejection |
| Concurrent Skill change | Do not overwrite the changed package |
| Upload/readback ambiguous or failed | Report the actual receipt/failure; do not claim publication or blindly retry |

“Avoid interruption” applies to research-quality and optional enrichment failures. It does not justify publishing unsupported claims or hiding a failed write.

## Modularity Impact

The implementation lives in adapter-intake and adds version-owned helpers. Assets/Core behavior and runtime source code are untouched. Current manifest references only the current asset version; the previous manifest is retained as a test fixture. Official promotion remains the only delivery path. No manual runtime wheel replacement is part of this PR.

## Validation

Run the repository's dependency-free contract suite and full pharma suite. Also run `test_grounded_profile_v0_1_40.py` with the actual installed runtime to validate native citation projection; the repository's minimal citation stub cannot establish that behavior. All fixtures are synthetic. No provider calls or live storage writes are required for these tests.

The acceptance report separates offline evidence from pending post-promotion qualification. Live acceptance must inspect the actual profile content, source diversity/relevance, coverage gaps, critic feedback and persisted readback, not just terminal status or byte count. There is no minimum fact quota that encourages fabricated filler.

## Risks / Open Questions

- A current deployed provider may return sparse/no grounding metadata or unsupported JSON. Real-provider behavior remains a post-promotion acceptance check; offline fixtures cannot prove research quality.
- An admitted citation is not automatically semantic entailment. The critic must assess the association; native-only claims are labelled distinctly from exact readable-source spans.
- The 30-minute execution and finite shared call/input budgets remain. Several 600-second calls cannot all fit sequentially; late work is partial, never guaranteed complete.
- A large existing memory can reach its established document limit. Preserve it and report unadmitted additions; do not truncate it or silently enlarge runtime resources.
- Package writes are not atomic across memory and methodology. Preserve known successful receipts if a later write fails.
- This PR must stop before merge. Official promotion, admission, installation and a separately authorized live content/readback evaluation follow review.
