# PubMed Evidence 0.1.0  -  operation and source matrix

All rows marked **Implemented locally** mean deterministic adapter dispatch
exists and can be verified using synthetic source-shaped responses. They do
not mean an NCBI source is configured, registered, or live.

| Operation | Technical role | Response format | Evidence returned | Limit/qualification |
|---|---|---|---|---|
| `describe` | None | No fetch | Operation/menu contract | No external request |
| `database_info` | `pubmed_info_runtime` | EInfo JSON root | Field/index/link definitions | PubMed database only |
| `article_search` | `pubmed_search_runtime` | ESearch JSON root | PMIDs, result count and query translation | One page, 40 IDs max |
| `advanced_search` | `pubmed_search_runtime` | ESearch JSON root | Fielded query discovery only | Trusted Boolean compiler/character admission pending |
| `article_count` | `pubmed_search_runtime` | ESearch JSON root | Count without article records | PubMed ESearch first-10k window caveat |
| `trial_publications` | `pubmed_search_runtime` | ESearch JSON root | NCT candidate PMID list | Candidate association only |
| `article_get` | `pubmed_summary_runtime` | ESummary v2 JSON root | Single PubMed article metadata | PMID identity verification |
| `article_batch` | `pubmed_summary_runtime` | ESummary v2 JSON root | Bounded metadata + missing PMIDs | 20 IDs max, one call |
| `abstract_get` | `pubmed_abstract_runtime` | BioC PubMed JSON root | Passage sections, offsets, text digests | One PMID, 12k chars max, no fulltext |
| `publication_profile` | `pubmed_summary_runtime` | ESummary v2 JSON root | Author/journal/type/MeSH metadata | Not article adjudication |
| `publication_history` | `pubmed_summary_runtime` | ESummary v2 JSON root | Reported pub/epub/sort date precision | Unknown precision preserved |
| `integrity_get` | `pubmed_summary_runtime` | ESummary v2 JSON root | Available notice-type signals | Absence is `unknown_from_summary_only` |
| `identifier_resolve` | `pmc_identity_runtime` | PMC ID Converter JSON root | DOI, PMCID and PMID for PMC-linked records | DOI path/character admission pending |
| `related_articles` | `pubmed_link_runtime` | ELink JSON root | Related linked IDs | Explicit linkname only |
| `citation_links` | `pubmed_link_runtime` | ELink JSON root | Citing/reference IDs | Separate `cited_by` vs `references` |
| `cross_database_links` | `pubmed_link_runtime` | ELink JSON root | PMC/Gene/ClinVar/GEO linked IDs | Relationship is not clinical causality |
| `export_citations` | `pubmed_summary_runtime` | ESummary v2 JSON root | Bibliographic reference strings | 20 PMIDs, no persistent export |

## Search input vocabulary

Free text, drug name, aliases, condition, outcome, author, journal, MeSH,
publication type, language, NCT ID, publication-date window,
Entrez-update-date window, page size, offset, sort order, cutoff date, and
research/summary view. Every caller selector is bounded and validated.

The adapter does not run unrestricted arbitrary queries on behalf of a
caller. It does not silently retrieve beyond a page or turn 10,000 visible
PubMed ESearch IDs into a claim of complete search coverage. For larger result
sets, a future governed segment planner must make its own precise coverage
claims.

## Conditional capability extensions  -  NOT advertised as runnable in 0.1.0

| Capability | NCBI primitive or other service | Why deferred |
|---|---|---|
| `spell_suggest` | ESpell | XML replies may contain a DTD that current parser correctly rejects |
| `citation_match` | ECitMatch | Requires tested citation input construction and text parsing |
| `batch_history` | EPost/Entrez History | Temporary server state and POST input safety need proof |
| `cross_database_counts` | EGQuery | Availability and current XML response contract need proof |
| `linkout_availability` | ELink LinkOut | Separate external link/rights semantics need proof |
| `full_text_availability` | PMC data services | Different service and availability semantics |
| `open_access_excerpt` | PMC Open Access and BioC PMC | Separate license and response-budget admission |
| `biomedical_entities` | PubTator 3 | Extracted candidates, not direct publication facts |

This list preserves future scope without adding fake live operations or
requiring new provider-specific runtime machinery. The version stays 0.1.0
until initial scope is reviewed and the implementation is frozen.

## Downstream clinical-failure handoff

A search hit is a **lead**, not a ledger-ready evidence item. A future clinical
consumer must inspect a bounded passage, verify source type, PMID and any NCT
link, preserve text digest, verify date precision against its `as_of_date`,
and set the actual clinical subject scope. The literature asset may supply
publication metadata and inspected text; it does not decide efficacy,
safety, failure reason, hypothesis confidence, or trial-arm interpretation.

Current clinical-failure 0.1.1 is unchanged. Future integration requires
separate legal Agent-tool or prepared-input admission and a combined run.
