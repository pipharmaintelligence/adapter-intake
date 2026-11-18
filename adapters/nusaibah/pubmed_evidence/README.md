# PubMed Evidence Source Adapter 0.1.0

Independent, read-only biomedical literature retrieval and normalization for other
Assets consumers and later Clinical Failure Intelligence composition.

This package uses worker-admitted, Core-governed Runtime Source roles. Its
Python code does not contact NCBI, own authentication material, store files,
execute retries, declare publication authority, or draw causal conclusions.

## Contract

- Identity: `nusaibah.pubmed_evidence@0.1.0`.
- Substrates: `local_worker` and `ecs`; default is `local_worker`.
- Optional `variables` object; omission or `{}` returns a no-fetch `describe`.
- Output: `literature_result` (one bounded object); no implicit persistence.
- Read-only publication capability specifications: `templates_only`.
- Independent `0.1.0` version maintained until the approved first release.

## Included semantic capabilities

`describe`, `database_info`, `article_search`, `advanced_search`,
`article_count`, `trial_publications`, `article_get`, `article_batch`,
`abstract_get`, `publication_profile`, `publication_history`,
`integrity_get`, `identifier_resolve`, `related_articles`, `citation_links`,
`cross_database_links` and `export_citations`.

Six optional technical roles are required for different read operations, as
specified in `DLM_RUNTIME_SOURCE_CONTRACT.md`. These roles are *not* active
simply because the input names appear in the manifest. A signed worker must
have each exact role, source and substrate admitted before execution.

## Evidence boundary

PubMed search and ESummary index records are bibliographic observations, not
scientific findings. BioC supplies available abstract passages only. Exact
article PMID is different from a candidate NCT association; registry trial
outcomes, study-arm assignments and marketing approval remain separate
sources and analytical tasks.

`publication_history` preserves original date strings and explicit date
precision. Unknown day/month does not become the first day of a year. A
requested `as_of_date` does not magically make an abstract date-qualified:
`abstract_get` requires a separately inspected publication record before a
later consumer can admit the passage as time-qualified evidence.

`integrity_get` marks known notice-type signals, otherwise reports
`unknown_from_summary_only`. It must not imply that an article has been
proven free of corrections, retractions or expressions of concern.

No PMC article full text is claimed. DOI-to-PMC conversion only covers
PMC-linked records. Unpublished and non-indexed negative trial results cannot
be discovered by PubMed alone.

## Known trusted-runtime blockers to certify separately

- Complex Boolean/fielded PubMed expressions contain characters that the
  current lazy Runtime Source scalar guard can reject. Do not weaken shared
  validation or add a Python network shortcut.
- BioC's PMID path binding needs approved configured path-parameter proof.
- Querying DOI values with slashes needs explicit trusted parameter admission.
- A single worker execution can pace calls, but this is not proof of a shared
  NCBI-account rate budget across ECS and local workers.
- Direct nested callable child execution and lazy preparation in the child
  remain unqualified. Future clinical integration must choose a legal source
  projection or admitted Agent-tool composition, with a fresh joint test.

## Developer verification

From the adapter-intake repository project root in DataSpell, select Python
3.10+ and the installed approved pi-obs-python-runtime interpreter for
production contract checks. Provider-free tests also run without that package
using a narrow fallback class in the test module.

Run `python -m unittest discover -s tests -p 'test_pubmed_evidence.py' -v`.
These tests prove normalization and failure behavior only, not NCBI transport.

See `CAPABILITY_MATRIX.md` for exact operation semantics,
`DLM_RUNTIME_SOURCE_CONTRACT.md` for governed source authoring, and
`PROMOTION_CHECKLIST.md` for the two package scanners and later release gates.
