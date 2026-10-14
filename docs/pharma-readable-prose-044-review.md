# Company profile 0.1.44: readable prose and bounded source verification

## Objective and acceptance

The company profile is the primary output. Evidence verification and critique
improve its reliability without eliminating useful safe research when a publisher
cannot be read. Unverified prose remains explicitly qualified; `Annex: Unverified
Research` contains only Section/Paragraph numbers and never repeats claim text.

Acceptance criteria for this additive candidate:

1. Whole claim meanings, material dates, entity/rights scope and uncertainty survive
   focused section/subsection synthesis. No concatenated three-statement fallback
   or duplicate equivalent leading dates.
2. Missing native grounding may use an actual runtime-fetched source, exact-span
   toolkit verification and the existing semantic critic. A URL, HTTP 200, lexical
   match or quote alone never makes a claim verified.
3. Challenges, unavailable PDFs, exhausted budgets and partial support leave local
   claims unverified while the readable profile and eligible Skill publication
   continue. No new human approval or whole-profile grounding gate.
4. The critic receives literal quotes; the prose writer receives qualified claims
   and evidence references. Full fetched documents stay out of Agent prompts and
   retained dossiers.
5. Existing native citations, optional methodology, requested reflection, resolver,
   disabled benchmark, Core publication/readback and historical versions remain.
6. Provider-free tests and official intake validation pass. Deployment and live
   business-quality proof are separate, later authorized work.

The version-owned [package guide](../adapters/nusaibah/pharma_company_intelligence_lab/ENRICHMENT_V044_GUIDE.md)
documents implementation, finite limits, compatibility and failure behavior.

## Evidence behind the change

Completed company-59 run `95954812-a386-4e43-b77f-f7c439bdeccc` used 17 Agent
calls. Four search-enabled research calls reported 40 queries and zero projected
grounding chunks/admitted native citations. The 50-claim profile contained 27
paragraphs: 15 synthesized and 12 fallback. These are normalized receipts, not the
historical raw Vertex response; they do not establish a provider root cause.

Read-only URL verification examined 43 distinct opaque source URLs: 27 returned
HTTP 200, 14 publisher 403, one redirect-service 404 and one timeout. Forty-one
resolved to publishers, yielding 37 distinct final URLs; 12 responses were PDFs.
One HTTP 200 response was a Scribd challenge, demonstrating why status alone is
insufficient. Sample Pfizer filings and FDA pages supported real research details;
the investigation did not certify all 50 claims.

Existing provider metadata projection tests preserve known grounding chunks.
That is a contract check, not proof of the unretained historical response.

[Google's grounding documentation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/grounding/grounding-with-google-search)
describes circumstances where source-link metadata is absent, including low source
relevance or incomplete information. [A first-hand report about missing metadata](https://discuss.ai.google.dev/t/billedtoolcalls-and-groundingmetadata-missing-from-generatecontent-response-but-ai-studio-logs-show-billed-searches-gemini-3-5-flash/174074)
discusses search activity during thinking. Such reports are context, not a confirmed
Vertex incident affecting this run. Researchers currently use text responses with
JSON requested by the prompt; structured-output reports are not an exact match.

## Implementation boundaries

PR #138 retains its prose repair and adds `source_verification_v0_1_44.py` to the
reviewed promotion surface. Research discovery remains grounded search. The new
fallback uses the existing runtime `open_reference` capability; the adapter has no
raw network or storage code. Readable passages go through toolkit 0.1.2 and the
existing critic. The native-citation path is unchanged.

The generic [Assets companion #603](https://github.com/piusaibah/assets/pull/603)
adds bounded PDF text extraction to the same public reader/result contract.
It is needed for PDF verification, not for basic adapter
continuation. Existing runtimes without it leave those documents unverified. No
pharma identity or logic belongs in the generic reader. The runtime version stays
0.1.106; any later installation must use the official workflow artifact.

Source reading is finite: first two locators/claim, 16 new attempts/piece, 48/company
preparation, two concurrent reads, 120 seconds of active read scheduling, 300,000
characters/document, 1,500,000 cached characters and the existing shared 32 toolkit
calls. In-flight reads finish under existing runtime timeouts. Thinking between
research pieces does not spend the retrieval allowance. Full source bodies remain
ephemeral; retained evidence contains bounded quotes, provenance and offsets.

The prose replay before this addition fit all 50 retained claims into four packets
with zero unfit claims and all 12 applicable guidance items. Inputs measured 35,002 /
33,188 / 33,571 / 32,185 characters under the unchanged 42,000 ceiling. This is a
replay of that retained case, not a guarantee that every future case fits four calls.
The six-call synthesis allowance and global execution limits are unchanged.

## Validation and release state

Local validation uses fake public readers, real exact-span toolkit operations,
real-SDK fixture publication/readback, historical contract checks and synthetic PDF
fixtures. No paid provider call or real Skill/storage mutation is performed.

Final local results: 638 real-SDK tests passed; the CI-stub suite ran 627 tests
with 18 expected skips; both root intake-contract tests passed; the official
local intake validator reports `ready` with no network calls or mutations. The
generic reader companion passed 127 focused and integration tests, including its
actual Windows parser child. GitHub CI must still pass on the published heads.

The PR update is deliberately unmerged. No promotion, runtime installation,
registration or live run is part of this change. Before deployment, confirm both
PRs and official promotion/package checks, then verify active synthesis contract
1.0.11 and exact admitted asset/runtime identities. Published README/developer-guide
bytes and all earlier manifest versions remain unchanged.
