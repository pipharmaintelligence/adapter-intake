# DLM Runtime Source authoring contract  -  PubMed 0.1.0

This guide specifies **proposed** Core-owned source contracts. Nothing here
asserts that a source ID, credential profile, runtime binding or deployment
already exists. Verify the deployed DLM UI and client scope before creating
any source. Never copy an account authentication value into this package.

## Six exact technical roles

| Adapter role | External API / output | Governed operator configuration | Logical per-call parameters |
|---|---|---|---|
| `pubmed_search_runtime` | NCBI ESearch, JSON, root `esearchresult` | Core-targeted PubMed ESearch v2 HTTP GET with fixed db=pubmed | `term`, `retmax`, `retstart`, `retmode`, optional `sort`, `datetype`, `mindate`, `maxdate` |
| `pubmed_summary_runtime` | NCBI ESummary v2, JSON, root `result` | Core-targeted PubMed ESummary HTTP GET with fixed db=pubmed | `id`, `retmode`, `version` |
| `pubmed_abstract_runtime` | NCBI BioC PubMed JSON, root `documents` | Governed fixed BioC JSON target with safe PMID path binding | `pmid` path parameter; prove trusted path substitution |
| `pubmed_link_runtime` | NCBI ELink, JSON, root `linksets` | Core-targeted PubMed ELink HTTP GET with fixed dbfrom=pubmed | `id`, allowlisted `linkname`, `retmode` |
| `pmc_identity_runtime` | PMC ID Converter, JSON, root `records` | Core-targeted converter GET with format=json | `ids`, `format` (format may be fixed in Core) |
| `pubmed_info_runtime` | NCBI EInfo, JSON, root `einforesult` | Core-targeted EInfo GET with fixed db=pubmed | No caller parameters |

Preserve the entire **root response object** as one normalized record.
Records path should be empty unless a provider-specific conformance test
proves another path preserves every required count, error and identity field.
Set native source `max_records=1` for one root response, while the adapter
separately bounds its PMID page size and output record count.

For ESearch, request the JSON reply and preserve count, retstart, retmax,
idlist and querytranslation. For ESummary, preserve the `result.uids` index and
the keyed summaries, rather than extracting an unordered list. For BioC,
verify `documents[*].id` equals the requested PMID, and never infer journal
publication dates from that response alone. ELink names are fixed to the
approved relationship enum and returned groups must name the same link.

## Authentication and request limits

User-provided NCBI E-utilities API Key Management supports 3 requests per
second without a key and 10 requests per second with a key, subject to NCBI
usage policy. The quota is shared by all simultaneous callers using the same
key. The key changes throughput, **not** article access rights.

In DLM UI, the static query authentication scheme is supported, with placement
name specified by NCBI. Select an existing **active, matching** credential
profile for the exact client/lake, runtime handle, server ref and capability.
If profiles are handle-scoped, do not blindly reuse one source's profile for
another source. A Core-controlled tool name and maintainer contact may be
required by NCBI policy and must be supplied by the authorized operator, not
by the business adapter.

Both `local_worker` and ECS need positive safe source-allowed-substrate proof.
The current worker's cooldown is execution-local; do not claim 10 requests
per second **per worker**. Before production parallelism, verify a shared
quota policy and observed 429/backoff behavior at the trusted layer.

## Validation order

1. Inventory existing client-scope Runtime Sources and credential profiles.
2. Create/reuse exact matching sources with fixed request targets and
   declared safe parameters; use client-wide scope where governance permits.
3. Publish each source and recheck canonical Core readiness independently.
4. Qualify primitive selected-executor calls using the approved runtime tool,
   without disclosing article bodies or auth material in shared logs.
5. Bind each exact role in the signed adapter's admitted runtime inputs.
6. Prove search, summary, BioC, link and identity response shapes using safe
   counts and digests on both requested execution substrates.
7. Finally qualify provider-backed business adapter outputs and later clinical
   composition. A ready Core source is not a deployed adapter.

## Known compatibility questions

- The current shared lazy-variable guard accepts bounded scalar text but
  rejects some PubMed field syntax, quoted expressions, DOI slashes and
  encoded path-like identifiers. Resolve with an approved capability-scoped
  trusted compiler or verified binding, never by globally relaxing safety.
- BioC uses a path variable; production path-substitution admission needs a
  real conformance test on the exact configured target.
- The E-utilities key does not grant PMC licensed full text or improve PMC
  service limits. PMC and BioC source policies require independent review.
- EFetch's commonly returned XML may contain DTD declarations; current
  generic XML decoder deliberately rejects them. Do not bypass that defense.
- Direct callable children cannot assume nested asset calls or lazy child
  source preparation under the present runtime plan contract.
