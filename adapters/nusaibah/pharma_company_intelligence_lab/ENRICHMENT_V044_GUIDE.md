# Objective

Improve readable prose in the existing company profile. Preserve all safe research,
its uncertainty, company-name title and numeric-only Unverified Research annex.
This release changes editorial preparation and rendering only.

# System Context

Company Scope and pharma retain the existing CompanyContext handoff. Research,
source verification, critics, optional methodology, reflection, Core Skill ZIP
publication, partition selection, history and readback use their existing contracts.
No runtime version, provider, timeout, call limit or concurrency increase is needed.
Only the synthesis Agent contract advances, from 1.0.10 to 1.0.11.

# Approach

In completed company-59 run `95954812-a386-4e43-b77f-f7c439bdeccc`, synthesis
planned 19 packets against its six-call allowance; 16 claim units did not fit even
individually. The packets included global critic/analysis/plan context which was
unnecessary for the editorial task. The result used 15 synthesized paragraphs
and 12 fallback paragraphs. The fallback concatenated groups of three statements
and prefixed an ISO date even when the statement already contained the same date
in words.

Give the prose writer whole claim statements for one section/subsection, their
complete qualifications and applicable learned guidance. Keep the global critic
record and source inventory in the dossier. Schedule the first packet from each
section before overflow. Separate complete claim statements to fit input/output
budgets; never slice a sentence or silently discard an oversized claim.

# Changes Made

- Synthesis receives focused claim packets and the existing complete JSON response
  contract. The prompt requests connected topical paragraphs, every distinct claim
  once, and no invented transitions or causal explanations.
- Whole statements are packed within the existing measured input ceiling. A
  5,000-character statement-text grouping bound also avoids oversized prose tasks;
  individual long statements remain indivisible and retain the existing fallback.
- If synthesis remains unavailable, each original statement gets its own paragraph
  instead of arbitrary groups of three. Equivalent written/ISO dates are recognized;
  repeated equivalent leading dates are collapsed. Different material dates,
  historical scope, negative findings, interpretation and qualifications remain.
- Verification status is unchanged. Missing grounding does not stop editorial work,
  erase useful research or create a new publication gate.

# Modularity Impact

Version-owned 0.1.44 wiring reuses the 0.1.43 acquisition, critique, context,
publication and retention helpers. Historical Python files and manifest versions
remain unchanged. Core remains the sole persistence authority. Use official
adapter-intake promotion for deployment; do not build or upgrade a runtime wheel.

# Validation

Provider-free regressions cover equivalent/different dates, uncertainty preservation,
one-statement fallback, numeric-only annexes, 50 claims fitting four section packets,
fair overflow ordering, actual SDK fixture publication/readback, optional reflection
and historical contract preservation. No live provider invocation is part of these
tests. A readable generated paragraph cannot be guaranteed by a prompt or fixture;
inspect the next separately authorized live result for editorial quality.

Before live use: confirm intake CI, official promotion/package CI, official artifact
delivery, exact asset admission, and actual availability of synthesis contract
1.0.11. Planned chain inspection is not activation. Keep the existing eight Agent
contracts; verify all roles resolve before launching paid work.

# Risks / Open Questions

Vertex source behavior is separate from this prose repair. The completed run's
four search-enabled calls reported 40 queries and zero projected grounding chunks.
Those receipts are normalized metadata, not retained raw HTTP response bodies.
They do not prove which provider/normalization boundary lost or omitted sources.

Google's grounding documentation
explains that source-link metadata can be absent, including when source relevance
is low or information incomplete. A first-hand developer report and forum reply
describe missing grounding chunks with structured output; the reply recommends a
source-URL field in JSON. Later first-hand reports
describe related symptoms, including reports without structured output. These are
community reports, not confirmation of an incident affecting this exact run.

Our current researchers use `response_format=text` with JSON requested in the
prompt. Therefore the structured-output report is not an exact configuration
match. A model-written URL alone is not proof of grounding. This change neither
adds mandatory source fields nor changes native citation admission. Sources remain
an independent investigation; all uncertain research stays visibly qualified.

External source links and retained-case replay measurements are in the repository
review note: docs/pharma-readable-prose-044-review.md. The package guide contains
no external URLs, consistent with the existing intake scan.
