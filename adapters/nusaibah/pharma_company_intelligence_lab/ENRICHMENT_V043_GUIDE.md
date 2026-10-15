# Objective

Build a useful company profile in readable, section-focused prose. Research is
the primary deliverable. Evidence verification and criticism improve and label
that deliverable; they must not silently erase useful paid research. The H1 uses
the company name. This contract applies to 0.1.43; earlier releases are unchanged.

# System Context

Company Scope supplies CompanyContext. The pharma adapter does not query
Companies again. Existing Core Dynamic Skill capabilities own memory/methodology
ZIP publication, partition resolution, digest checks, history and readback.
The E runner and official promotion workflow remain the delivery path. No Core
or generic runtime change, runtime version bump, new authority or storage lane
is required. Benchmark remains disabled. Methodology is optional and supplies
critic advice for future research rather than a methodology essay.

# Approach

Research each assigned section using grounded public search and available
primary sources. A failed optional homepage read does not cancel discovery.
Keep original safe research statements before evidence admission narrows the
verified-fact set. The critic reviews supplied statements, labels support and
proposes actionable future improvements. Synthesis receives useful verified
and unverified research for its section/subsections and writes connected prose.
Failure to verify a paragraph keeps it as explicitly unverified research; missing
or malformed synthesis falls back to the original statements, without inventing
facts or connective claims. Formatting recovery keeps the existing single backup.

The profile contains research once, in the relevant numbered section. Unverified
paragraphs are visibly labelled and carry stable section/paragraph coordinates.
`Annex: Unverified Research` is a two-column table containing **only section
numbers and paragraph numbers**. It repeats no statement, quote, explanation or
URL. Evidence locators appear once in the separate evidence register, labelled
as verified sources or proposed sources whose support has not been confirmed.
Verified fact IDs/counts remain separate from research content coverage.

Historical memory, evidence registers and prior history annexes are not fresh
source paragraphs to run through research again. Only applicable whole prior
profile paragraphs enter the bounded historical-context field. Previously
unverified paragraphs remain research leads and must not be promoted to facts
merely because they are stored in memory. Old memory remains preserved in the
publication candidate and Core history. Source provenance is unchanged.

# Changes Made

- Versioned prompts for all three researchers, critic, synthesizer and the sole
  resolver prioritize profile construction and preserve useful uncertain research.
- Original proposed claims survive source/semantic admission as a separate
  research collection. Missing grounding and invalid optional semantic fields
  cannot remove a safe statement from the profile. No missing field is invented.
- Profile synthesis and consolidation keep draft paragraphs even when critic
  or paragraph verification is unresolved. Only actual supported facts populate
  the verified memory fact set. The selected-fact checks remain truthful.
- A draft-only useful profile may initialize/update the same Skill package.
  It reports zero verified facts, explicit uncertainty and exact readback.
- Historical evidence/history annexes no longer generate supplemental discovery
  calls. Claim units are grouped by section/subsection and measured before every
  dispatch. Actual source-paragraph offsets and exact-span tools are preserved.
- Unchanged SDK, methodology, title, retention and call-budget helpers are reused.
  The final profile is bounded to 96,000 characters with whole-paragraph omissions
  reported explicitly; prior memory is never silently deleted to make room.

# Modularity Impact

This is an additive intake adapter version with version-owned orchestration,
presentation and input projection. It reuses the existing runtime, provider
registry, callable review toolkit and Core Skill lane. The current manifest
declares 0.1.43; promotion preserves earlier packaged identities. No direct SQL,
bucket SDK, credential access, governance override or parallel legacy lane is
introduced. Unsafe content still fails the real generic retention checks and is
never laundered by an unverified label.

# Validation

Required acceptance criteria for the final repair:

| Requirement | Evidence |
|---|---|
| Main objective preserved | Distinct safe research appears in the profile even when grounding is absent. |
| Honest verification | Draft-only fixture publishes with zero verified-fact count and `verification_complete=false`. |
| No duplicated annex prose | Unverified annex has only numeric section/paragraph references. |
| Semantic defects do not erase research | Original statement remains unverified; missing numerical/relationship fields are not invented. |
| Same publication authority | Real SDK preview/apply/readback fixture uses the established Skill lane. |
| No historical reprocessing | Old evidence/history annexes are absent from research packets and remain in stored memory. |
| Focus and cost | Discovery is section-scoped; every dispatch fits measured input bounds and shared limits. |
| Reflection | Second pass consumes prior marked prose/advice and publishes only after all requested passes. |
| Deduplication | Equivalent draft/verified findings render once, preferring actual verified support. |
| Safety | Credentials, signed/private URLs and runtime controls cannot be published as unverified research. |
| Compatibility | Previous source/contract bytes remain unchanged; packaged imports, intake declarations and official CI pass. |

Use the real E runtime for `test_profile_primary_v0_1_43.py` as well as normal
intake CI. Stub tests alone do not prove generic retention or native grounding.
Inspect live profile content and verification separately from terminal/upload
success. Provider usage is evidence of cost, never evidence of content quality.

# Risks / Open Questions

- Unverified research can be inaccurate. It must remain visibly qualified in
  the main profile and cannot acquire verification solely through persistence.
- The preceding company-59 run retained only two statements and issue codes for
  114 withheld claims. This version cannot reconstruct absent original text.
- Search-query metadata is not source support. The preceding run recorded no
  normalized grounding chunks; whether raw provider data was absent or lost
  during normalization still needs exact evidence, not an invented diagnosis.
- Existing limits remain: 48 shared dispatches, concurrency two by default,
  1,200 seconds per Agent and 3,600 seconds per workflow. No time increase is
  made. Large inputs are chunked by paragraph/subsection and omissions remain
  explicit rather than being reported as full completion.
- Memory and methodology remain separate Core transactions. Storage failures
  and unsafe output are real boundaries, not business-quality elimination gates.
