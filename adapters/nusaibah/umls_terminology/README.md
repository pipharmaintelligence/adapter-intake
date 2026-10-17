# UMLS Terminology — development 0.1.0

**Logical asset identity:** `umls_terminology@0.1.0` (no `nusaibah.` prefix).
The physical intake folder and package destination remain under `nusaibah/umls_terminology` because intake requires a two-level namespace/slug folder; this path is not part of the logical asset key.

This is a **provider-blind** UMLS terminology adapter. The current branch is
for contract development, **not release, promotion or live execution**.

## Semantic operations

All operations share one `terminology_result` output role. In this draft,
`describe` is the only operation that needs no runtime-supplied input.

| Family | Operation(s) | Required selectors |
| --- | --- | --- |
| Local capability discovery | `describe` | none |
| Search | `search`, `gene_search`, `protein_search`, `drug_search` | `text`; optional `search_type`, `sources` |
| UMLS concept | `concept_get`, `gene_get`, `protein_get`, `drug_get` | `cui` |
| Concept details | `concept_atoms`, `concept_definitions`, `concept_relations`, `gene_relations`, `mechanism_relations` | `cui` |
| Source vocabulary | `source_get`, `source_atoms`, `source_relations`, `source_attributes` | `source` and `code` |
| Source hierarchy | `source_hierarchy` | `source`, `code`, `direction` |
| Crosswalk | `crosswalk` | `source`, `code`, `target_sources` |
| Atom | `atom_get`, `atom_hierarchy` | `aui`; hierarchy needs `direction` |
| Semantic-network type | `semantic_type_get` | `tui` |
| Vocabulary list | `vocabularies` | none; `limit` optional |

Every non-describe operation currently requires a *pre-normalized*,
binding-owned `umls_response`. It must contain an exact `operation`,
`status` (`ok`, `not_found`, `partial`), a `records` list and
`provenance.release` as an exact resolved UMLS release such as `2026AA`.
No HTTP envelope or caller-supplied provider credentials are accepted as
the governed data role.

### Example business requests

```json
{"variables":{"operation":"gene_search","text":"BRCA1","limit":10}}
```

```json
{"variables":{"operation":"drug_get","cui":"C0004057"}}
```

```json
{"variables":{"operation":"source_get","source":"HPO","code":"HP:0001947"}}
```

```json
{"variables":{"operation":"crosswalk","source":"HPO","code":"HP:0001947","target_sources":["SNOMEDCT_US"]}}
```

## Scientific and data boundaries

- UMLS gene terminology is **not** an NCBI Gene record. The gene semantic
  type is T028; a T028 name/CUI does not establish sequence, locus, transcript,
  variant, target engagement or expression.
- Protein terminology is a separate T116 classification. Drug terminology
  uses T121 (Pharmacologic Substance) and T200 (Clinical Drug).
- `mechanism_relations` only exposes admitted source-asserted relations.
  REL/RELA, source identity, direction and suppression metadata remain distinct.
  A named mechanism-related relation is *not* efficacy or causal proof.
- Crosswalk results are UMLS shared-CUI candidates, not automatic clinical
  equivalence across vocabularies.
- Missing semantic-type evidence is `null`, not false. Provider truncation
  is visible as `partial` and a `truncated` completeness flag.
- UMLS source-vocabulary content can have licensing and reuse restrictions.

## Current technical boundaries

The existing draft manifest keeps `variables` optional and direct, and
`umls_response` optional and **binding-owned**. `describe` reads no
governed records in adapter code; whether an optional binding is eagerly
resolved before adapter invocation still requires separate runtime proof.

No Runtime Source ID, API key, target, exact provider-request builder,
UMLS pagination policy, raw UMLS payload contract, credential, output
publication, helper-owned HTTP or source-specific Core/UI change has been
configured here. The adapter is not a generic UMLS HTTP executor.

Current source accepts a maximum of 200 pre-normalized input records and
projects a caller-bounded maximum of 50 records. It does not implement
provider paging or guarantee full retrieval; that belongs to the trusted
Runtime Source helper after authorization.

Tests use synthetic, source-informed fixtures, not a live UMLS account.
Local tests and intake CI do not establish packaged wheel/environment,
governed binding, signed-worker admission or MCP publication.

## Release hold

**Keep asset version 0.1.0. Do not merge, promote, publish or edit DLM UI
Runtime Source configuration.** Before a governed live test, obtain the
operator-selected Runtime Source ID and verify its operation/format/target,
credential authorization, source license, record projection, pagination and
worker admission. Review exact required input roles at that point.

Tracking: PI-2070; draft PR #148.
