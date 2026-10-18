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

The `umls_response` input is an optional **direct technical API role**,
like the existing ClinicalTrials.gov lazy source roles. A real Assets run must
attach one Core-approved Runtime Source reference to this role with
`resolve: lazy`. Python calls the worker-provided `inputs.invoke` bridge; it
does **not** trust caller-supplied records or obtain provider credentials.

Currently **only `describe` and plain `search` are connected to this governed
execution path**. `search` builds the bounded allowlisted request parameters
`string`, `searchType`, and optional `sabs` from validated business selectors.
Confirm those keys against the operator's saved Runtime Source allowlist before
the first signed run. Other listed operations retain deterministic normalization
tests but require separate reviewed source mappings before live execution.

Local test fixtures use a *pure normalization helper* and may supply a strict
synthetic operation/status/release envelope. Production adapter invocation
always requires the trusted lazy invoker returning
`{"records": [...], "metadata": {...}}`. No fallback to direct records exists.
Unknown UMLS release, retrieval timestamp, search-query attestation and upstream
pagination completeness remain unknown rather than invented.

This design uses an existing worker bridge instead of creating a shared Assets
admission mechanism. The draft eager-only guard in Assets PR #648 is **not a
prerequisite for the lazy UMLS lane**. A signed, exact-asset run is still required
before calling this execution path live-qualified.


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

The manifest keeps `variables` optional/direct and `umls_response`
optional/direct as a technical Core API reference. The adapter never accepts
direct provider data as proof. `describe` requires no retrieval. For a live
`search` the operator-selected source reference must name the confirmed
`search` operation and `umls.terminology.search` capability, with lazy resolution;
the signed worker must provide the invoker in `local_worker` or ECS.

No Runtime Source ID, API key, provider target, storage placement, output
publication, or secret configuration is embedded in the adapter. This is not a
generic UMLS HTTP executor.

For future clinical-failure intelligence, this same mechanism can supply
bounded, source-attributed terminology evidence alongside independently
authorized clinical-trial inputs. It does not establish target engagement,
mechanism causality, outcome efficacy or clinical-failure attribution.


Current source accepts a maximum of 200 pre-normalized input records and
projects a caller-bounded maximum of 50 records. It does not implement
provider paging or guarantee full retrieval; that belongs to the trusted
Runtime Source helper after runtime approval.

Tests use synthetic, source-informed fixtures and a fake worker-attached lazy
invoker, not live provider records. The separately verified UMLS Runtime Source
search primitive does not establish packaged adapter execution, signed-worker
admission, semantic correctness or ECS deployment.

## Installed SDK offline contract gate (separate from intake CI)

The ordinary intake tests use a minimal `adapters.base` stub and a fake
lazy bridge. The dedicated `tests/test_umls_installed_runtime_inputs.py` module
additionally exercises **the actual `system.runtime.RuntimeInputs` class**
from an installed `pi-obs-python-runtime` wheel. It never contacts the
provider or starts a worker. Intake CI skips these tests if no wheel is
installed; a CI green result is **not** installed-wheel proof.

For the isolated E: SDK `0.1.115` virtual environment in DataSpell, first
check out the exact reviewed PR commit. Set these Run/Debug environment
variables before starting pytest:


`UMLS_REQUIRE_INSTALLED_RUNTIME=1`
`UMLS_EXPECT_RUNTIME_VERSION=0.1.115`

Execute `tests/test_umls_installed_runtime_inputs.py` using that
interpreter with pytest's `--import-mode=importlib` and no source-root
`PYTHONPATH` override. All seven tests must run rather than skip.
The tests assert the real SDK passes `cooldown_seconds` to its attached
invoker and the UMLS adapter produces the declared bounded output, rejecting
caller record injection. This still does not prove an Assets-admitted signed
adapter execution, installed ECS image or published adapter.

## Release hold

**Keep asset version 0.1.0. Do not merge, promote, publish or edit DLM UI
Runtime Source configuration.** Before a governed live test, obtain the
operator-selected Runtime Source ID and verify its operation/format/target,
credential runtime approval, source license, record projection, pagination and
worker admission. Review exact required input roles at that point.

Tracking: PI-2070; draft PR #148.
