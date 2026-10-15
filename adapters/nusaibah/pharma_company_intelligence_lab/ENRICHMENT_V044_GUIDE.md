# Objective

Build a readable company profile and improve its source verification. Preserve
useful safe research when a source cannot be verified, with visible qualification
and a numeric-only `Annex: Unverified Research` table (Section, Paragraph).
Verification enriches the profile; it is not a new whole-profile publication gate.

# System Context

Company Scope supplies CompanyContext through the existing handoff. The existing
section research, exact-span toolkit, critic, optional methodology, reflection,
Core Skill ZIP publication, partition history and readback remain in place.
Only the synthesis Agent contract advances, from 1.0.10 to 1.0.11. Agent count,
call/concurrency budgets and provider/workflow timeouts are unchanged. Benchmark
remains disabled. No new Agent or storage authority is introduced.

# Approach

The completed company-59 run planned 19 synthesis packets against a six-call
allowance and had 16 individually unfit claim units. Global critic/analysis/plan
context made editorial prompts unnecessarily large. The resulting profile had
15 synthesized and 12 fallback paragraphs. The fallback grouped three statements
and repeated dates already present in prose.

That run also reported search queries without projected native grounding chunks.
Model-returned URLs are discovery leads, not proof. Version 0.1.44 can retrieve a
bounded selection through the existing runtime public-reference capability, select
a literal passage and pass it through the exact-span toolkit and existing critic.
It does not guess missing provider grounding or treat a successful HTTP response
as semantic verification.

# Changes Made

- Synthesis receives whole statements for one section/subsection, their complete
  dates, entity/rights qualifications, verification state and learned guidance.
  Quotes remain with the critic and retained evidence; only their references and
  offsets go to the prose writer. A section gets its first packet before overflow.
  Statements are never silently sliced or dropped to meet the input budget.
- Synthesis requests connected topical prose without invented transitions. When
  unavailable, each original statement becomes its own paragraph. Equivalent
  written/ISO dates are recognized; distinct material dates and uncertainty remain.
- Existing native-citation and supplied-readable-source paths keep their authority.
  Only unresolved discovered-source claims use the additional retrieval fallback.
  HTTPS targets go through the runtime's DNS, IP and redirect checks. The adapter
  has no direct HTTP client or credentials.
- Source text stays in a company-local RAM cache. Requested/final URL cache entries
  avoid repeated reads; two different opaque redirects may need separate reads
  before their common final URL is known. Full fetched documents are not added to
  Agent prompts or the retained dossier.
- Complete paragraph/sentence passages and adjacent PDF table lines are ranked for
  relevance. A unique literal passage of at most 600 characters is resolved by the
  existing toolkit against an 8,000-character source window. Evidence records keep
  window and document offsets, text digests, final locator and PDF page if present.
  Offsets refer to the extracted text, not to original PDF bytes.
- The critic must assess every material clause, entity, date, number, units,
  territory and relationship. Lexical overlap, URL matching and literal occurrence
  alone never establish entailment. Partial evidence remains `needs_review`;
  contradictions remain `unsupported`. Both preserve visibly unverified research.
- Challenges, blocked/empty sources, malformed PDFs, time/read limits and unresolved
  exact-span results leave claims unverified and continue the company profile.

## Finite retrieval limits

| Resource | Bound |
| --- | --- |
| Candidate locators | First two per unresolved claim |
| New source attempts | 16 per research piece; 48 per company preparation |
| Concurrent public reads | Two |
| Active retrieval allowance | 120 seconds; no new read after exhaustion |
| Source text | 300,000 characters/document; 1,500,000 cached characters |
| Exact-span calls | Existing shared 32-call ceiling |
| Toolkit input window / quote | 8,000 / 600 characters |

The time allowance counts retrieval work, not intervening Agent thinking. An
already-started read can finish under the existing runtime timeout (bridge ceiling
45 seconds); this is not a strict 120-second wall-clock cancellation guarantee.
Budgets reset for a separately requested preparation/reflection pass. No provider
retry is launched solely to recover missing source metadata.

# Modularity Impact

The additive 0.1.44 helper uses the existing public-reference result contract and
structured-review toolkit 0.1.2. PDF extraction belongs to a generic Assets reader
change, not this adapter. On a runtime without that reader capability, unreadable
PDFs stay unverified and the profile still proceeds. The companion reader limits
PDF bytes, pages, extracted text, parser time, memory and concurrent parser children;
encrypted/scanned documents are not decrypted or OCR-processed.

Historical adapter files, manifests and published guides remain immutable. Core
remains the sole persistence authority. Deploy later through official intake
promotion and packaged-runtime CI; this PR does not install or upgrade a wheel.

# Validation

Provider-free tests exercise fetched-source exact spans reaching the existing
critic, native-citation compatibility, partial clauses, source failure continuation,
cache reuse, concurrency/read/time budgets, PDF locations and unchanged source text.
They also prove full fixture publication/readback with every source unavailable,
quote separation between critic and writer, reflection, numeric-only annexes and
historical contracts. Synthetic PDFs exercise the generic reader separately.

Acceptance requires all of those checks, official intake validation and PR CI.
Before a later authorized live run, also require official promotion/package CI,
artifact delivery, exact asset admission and active synthesis contract 1.0.11.
Fixture success does not establish the next generated profile's editorial quality
or certify every real claim. No live provider execution belongs to this PR update.

# Risks / Open Questions

The original raw Vertex HTTP response was not retained. Normalized receipts prove
zero projected chunks, not which provider/normalization boundary omitted them.
Google documentation allows absent source-link metadata; forum reports do not
establish an incident for this exact run. A bounded document excerpt can be partial
or stale, and PDF tables can lose layout. The critic must retain qualifications and
must not infer that unexamined pages contain no evidence.

No access-control bypass or browser challenge solving is added. Source retrieval
can improve evidence coverage without guaranteeing complete verification. The
repository review note records investigation evidence, external references and
the companion runtime PR. This package guide deliberately contains no external URLs.
