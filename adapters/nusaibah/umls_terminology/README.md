# UMLS Terminology Adapter — 0.1.0

One source-specific, provider-blind UMLS terminology asset. **Development only**.

## Scientific semantics

- `gene_search` and `gene_get` mean UMLS **Gene or Genome** terminology (`T028`), **not** retrieval of an NCBI Gene record.
- `mechanism_relations` returns raw source-attributed UMLS relations. A relationship label is not evidence of efficacy or causal mechanism.
- A real gene record, pathway, target engagement or mechanism claim may require a separately admitted NCBI Gene/UniProt/ChEMBL/Reactome source.
- All UMLS source license restrictions and release provenance must be honored.

## Initial operations

`describe`, `search`, `gene_search`, `concept_get`, `gene_get`,
`concept_relations`, `mechanism_relations`.

The operation is supplied in optional `variables` (direct object). No variables or `{}` means `describe` and makes **zero provider requests**.

Business query examples:

```json
{"variables":{"operation":"gene_search","text":"BRCA1","limit":10}}
```

```json
{"variables":{"operation":"mechanism_relations","cui":"C0004057","limit":20}}
```

## Trusted-input contract

All non-describe requests require `umls_response`, a **binding-owned governed object** with:
`operation`, `status` (`ok|not_found|partial`), `records[]`, and
`provenance.release`. The business adapter never makes API calls.

A development fixture may inject this payload for deterministic tests; doing
so **does not** certify remote binding authority or live UMLS retrieval.
Caller-provided direct overrides of `umls_response` must be rejected by
the admitted input contract.

The current bundle deliberately does not claim dynamic provider lookup,
callable-child composition, UMLS auth, live worker admission, or MCP publication.
Provider endpoint mapping and source response normalization require a distinct
governed configuration and signed-worker proof.

## Remaining `0.1.0` catalog

Atoms, definitions, source IDs/relations/attributes, source hierarchy,
crosswalk, exact atoms, semantic type metadata and vocabulary listing.
Only add `batch` after repeated-call budgeting is proven.
