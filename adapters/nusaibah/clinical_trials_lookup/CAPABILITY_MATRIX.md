# `nusaibah.clinical_trials_lookup@0.1.0` — capability and proof matrix

This is a source tool, not a reimplementation of `GetRegistrationTrials.ipynb`.
The notebook's registration-programme classification and group-inference
algorithms remain in future consumers.

## Study-source input coverage

| Input / operation | Source mapping | Qualifier |
| --- | --- | --- |
| `text` | `query.term` | General free text / bounded Essie expression |
| `intervention`; optional `intervention_terms` | `query.intr` | Caller-supplied aliases; combined Essie OR needs worker compatibility proof |
| `condition` | `query.cond` | Disease or condition terms |
| `title` | `query.titles` | Title/acronym text |
| `outcome` | `query.outc` | Registered outcome text |
| `sponsor`, `lead_sponsor` | `query.spons`, `query.lead` | Sponsor/collaborators versus lead sponsor |
| `location`, `country` | `query.locn`, `filter.advanced` | Geographic text; advanced AREA syntax not yet worker-qualified |
| `study_identifier`, `nct_id`, `nct_ids` | `query.id`, exact GET path, `filter.ids` | NCT primary and secondary identifiers; batch up to 50 |
| `patient_text` | `query.patient` | Registry patient-search area, not patient medical records |
| `phase`, `study_type`, `sponsor_class`, `updated_from/to` | `filter.advanced` | Registry enums/Essie; no adapter-fixed stale enum set |
| `status` | `filter.overallStatus` | One or multiple registry statuses |
| `advanced_filter` | `filter.advanced` | Reviewed caller Essie; not unrestricted HTTP; worker gap |
| `preset=phase3_interventional` | separate Core-pinned source role | Must prove pinned filter and study type independently |
| `sort`, `page_size`, `page_token`, `count_total` | API sort/page/cursor/count parameters | Up to 2 sort fields, 1..50 page, no invented totals |
| `view` | adapter projection only | `summary` or full `research` (plus dedicated arms/outcomes/results views) |

Metadata/enumerations, search-area discovery, statistics, bulk/download, FHIR,
RIS and geo-distance endpoints exist in the **broader ClinicalTrials.gov API**
but are **not** advertised as executed capabilities by this seven-operation
study-lookup adapter. If future assets need them, add separately qualified
source tools; do not expose a generic provider HTTP proxy by default.

## Downstream `GetRegistrationTrials.ipynb` field coverage

| Notebook use | Lookup output | Who interprets |
| --- | --- | --- |
| Phase 3 intervention names/codes/aliases | `summary.interventions` or full `armsInterventionsModule` | Programme asset owns cross-alias dedup and drug equivalence |
| **Experimental, placebo, active-comparator arms** | `summary.arm_groups[].type/label/description/intervention_names` | Programme asset owns target/comparator inference |
| **Intervention-to-arm link evidence** | `summary.declared_arm_links` and `unmatched_arm_labels` | Programme asset decides inference from titles if needed |
| Trial enrolment, protocol design, allocation/masking | `summary.enrollment`, `enrollment_type`, `design_info` and full `designModule` | Registration asset |
| Primary/secondary endpoints | `summary.primary_outcomes`, `secondary_outcomes`; `outcomes_get` | Registration asset |
| Posted outcome evidence / adverse events | `results_get.registry_study.resultsSection`, group indices | Outcome evidence asset, not the lookup tool |
| Sponsors, organization IDs, trial title | `summary.lead_sponsor`, IDs and identification module | Lineage asset |
| Regulatory flags and US sites | `summary.is_fda_regulated_drug`, source oversight/locations | FDA relevance logic in future asset |
| Trial date/status and stopping explanation | `summary.overall_status/why_stopped/last_update_posted` | No causal inference in lookup |
| Record coverage/updates | exact NCT IDs, cursor, provider total count if present, source digest | Caller owns pagination, alias dedup, snapshot consistency |
| Protocol families, programme status and CSV | None | Future programme asset/Assets output publication |

## Failure and recovery boundaries

| Case | Behavior | Recovery owner |
| --- | --- | --- |
| Absent `variables` | `describe`, no source access | None |
| Missing broad-search selector | Fail before fetch | Caller adds one bounded query/filter |
| Invalid/duplicate ID, field type, sort, cursor, page size | Stable validation error before fetch | Caller fixes semantic input |
| Scope preset phase mismatch | Reject mismatched returned study | Core source preset review, provider data inspection |
| Exact GET 404 | Worker-owned error unless reviewed resolver projects explicit empty records | Trusted source execution / not an adapter inference |
| Rate limit/timeout/5xx | Safe typed provider/runtime failure when available; no raw body or adapter retry | Trusted runtime/operations |
| Malformed JSON/root page, wrong NCT, duplicate IDs, malformed registered lists | Fail visibly without replacing with empty evidence | Source configuration or provider/schema review |
| No results module | `not_posted` if `hasResults=false`; otherwise `not_present_in_record` | Consumer treats unknown separately |
| Valid empty page with cursor | `status=completed`, 0 records, `has_more=true` | Caller continues exact query |
| Output > 240KB | Explicit `clinical_trials_result_too_large` | Caller selects summary/arms/outcomes view or smaller page |
| Essie punctuation/cursor rejected by current lazy invoker | No covert fallback | Assets/Core approved query compiler/cursor contract |
| Child callable/nested depth unavailable | No claim of runtime composition | Assets callable admission/proof |

## Stage evidence

- Code: deterministic local source-only adapter and seven publication schema **templates**.
- Tests: provider-free synthetic calls, schema validation, arm identity/relationship cases,
  pagination identity/completeness, corrupt provider shapes and safe failures.
- Unknown until explicitly tested: official intake CLI, packaged imports, source binding,
  signed local_worker, production provider calls, child use, remote MCP publication.
