# Objective

Maintain one readable current company profile, with targeted research and optional
reflection. Evidence and critics qualify individual paragraphs. Historical document
copies belong to Core Dynamic Skill history, not inside the current profile.

# System Context

Company Scope, supplied CompanyContext, optional methodology, paragraph/subsection
chunking, bounded parallel Agents, one resolver attempt and existing Skill publication
remain in the same execution. Benchmark remains disabled. Version 0.1.45 keeps the
0.1.44 Agent contracts and provider limits unchanged. Historical versions are retained.

# Approach

The latest inspection found three nested Previous Memory annexes containing about
49 KB of prior text. Core had recorded four changes, but the current ZIP did not
contain a changelog. Independent source-contract failures involved long URL locators
and a 48-read adapter allowance against the runtime's 20-read bridge ceiling.

# Changes Made

- Build the current profile from new safe research plus distinct paragraphs from
  the preceding current profile. Exclude historical annexes, preserve dates and
  uncertainty, deduplicate identical prose, and never count carried memory as fresh
  verified evidence. Exact repeat inputs are a no-change; no usable new research
  leaves the existing document unchanged. Core keeps prior complete revisions.
- Retain the numeric-only Unverified Research annex and concise Need Review table.
  Missing evidence, inaccessible sources and exhausted optional reads retain useful
  qualified prose. Conflicting or paraphrased statements still require semantic
  review; deterministic text deduplication is not a claim of universal equivalence.
- Bind every long toolkit locator to a compact digest of final source URL, exact
  source-text digest and source window. Preserve the actual toolkit locator, quote,
  offsets and proof. Business citations remain human-readable source URLs, with an
  explicit binding connecting them to the attested locator.
- Share 20 public-reference attempts across the entire invocation, including initial
  website reads, companies and reflection. Initial reads count against that allowance.
  Two initial reads leave at most 18 discovered reads. No reset between passes and
  no attempt 21 is sent to the runtime. Cache, time, text and toolkit limits remain.
- Verify the latest committed history change with one history entry, instead of
  hydrating up to 50 earlier transitions after every publication.

# Modularity Impact

The companion Assets change creates a compact managed CHANGELOG block in the same
Skill ZIP. It observes one bounded page of Core metadata and records the current
document transition without inventing its not-yet-issued Core commit ID or time.
Core remains the authority for committed receipts and full historical objects.
The companion also preserves the original retention-store failure through subsequent
verification, including PHP's independent safe diagnostic projection.

These generic capabilities contain no company, pharmaceutical or adapter identity
condition. No new storage policy, authority, provider role or publication workflow
is introduced. Updating a profile requires no standalone archival upload.

# Validation

Required acceptance checks:

1. Multiple different updates produce one current profile, preserve distinct current
   knowledge once and omit nested historical annexes. Repeated identical input is stable.
2. Long discovered and initial source URLs pass the actual toolkit with the original
   returned locator intact. Partial support and corrupted spans never become verified.
3. Initial reads, concurrent reads and reflection share the same invocation allowance.
   Exhaustion is local to source enrichment and does not discard the profile.
4. Full two-pass fixture preparation, Skill apply, fresh readback and history pass
   without providers. Previous Agent contracts, chunks, benchmark-disabled behavior
   and historical adapter files remain unchanged.
5. Generic ZIP tests cover current/previous changes, bounded projection, preserved
   handwritten notes/resources, metadata-read failure and stable retry bytes.
6. Retention tests cover successful exact-byte store/readback, lost acknowledgement,
   original store timeout/HTTP failure followed by not-found, and safe PHP projection.

# Risks / Open Questions

The historical missing dossier cannot be recovered from summaries, and its original
store exception was discarded. The new diagnostics close that observability gap;
they do not establish a retrospective storage cause. Fixture tests do not certify
all external websites, semantic claim quality or a later production execution.

Deliver through the official promotion workflow after review. Merge the companion
runtime PR first, then intake, then its generated promotion. Do not manually copy
adapter files into an installed wheel. This delivery stops at pushed PRs: no merge,
promotion dispatch, local runtime installation, paid run or cloud publication.
