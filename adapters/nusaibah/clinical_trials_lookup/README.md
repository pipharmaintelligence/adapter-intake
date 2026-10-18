# ClinicalTrials.gov source lookup â€” `nusaibah.clinical_trials_lookup@0.1.1`

**Independent, read-only adapter-intake package.** Its source-of-truth is the
ClinicalTrials.gov v2 study record, not an inference or registration assessment.
The Python adapter has no network transport, credentials, Core API client,
storage writes, provider retry loop or publication authority.

## Why it exists

Provide normalized **registry facts** to registration-programme and clinical
failure intelligence assets. `GetRegistrationTrials.ipynb` is a requirements
reference, **not** code copied into this asset. Downstream consumers retain
ownership of drug-name matching, target/comparator judgement, sponsor-lineage
inference, FDA relevance assessment, protocol-family grouping, trial
classification, and programme readiness.

## Exact identity and input ownership

- `key`: `nusaibah.clinical_trials_lookup`; version and manifest default: `0.1.1`; legacy `0.1.0` files remain unchanged.
- Input `variables` is an **optional direct** semantic object. Absent or `{}`
  invokes `describe` without fetching a source. A retrieval operation requires
  valid selectors. An omitted `operation` is inferred only from `nct_id`,
  `nct_ids`, or meaningful search selectors.
- Output: required `trial_result` object, callable result key `trial_result`,
  2 MiB (2,097,152 bytes) advisory threshold. `size_policy` reports exact
  serialized UTF-8 result bytes and `warnings` highlights threshold crossings.
  Crossing 2 MiB preserves the complete result and does not reject execution.
  The new callable manifest allows 16 MiB for transport; that framework ceiling
  is independent from the adapter warning. Existing Core source read limits and
  selected executor policies remain authoritative and unchanged.
- Source roles `trials_search_runtime`, `trials_phase3_runtime`, and
  `trials_detail_runtime` are **optional direct technical role declarations**.
  For a real request, the trusted worker must attach the corresponding
  governed lazy Runtime Source invoker; a caller cannot replace it with raw
  provider data. The 0.1.0 manifest does *not* automatically create/source-bind
  provider authority.
- `local_worker` is the default; both `local_worker` and `ecs` are allowed in the 0.1.0 manifest. Signed execution, image/catalog delivery, and source allowance require independent proof on each substrate; nested callable use needs
  independent admission/proof. No output publication is part of this intake.

## Source-only capabilities

| Operation | Input selectors | Result |
| --- | --- | --- |
| `describe` | none | Operations, parameter names and no-fetch contract |
| `study_search` | free text (`text`), structured search/filter controls | One bounded page with studies, exact pagination metadata and source digest |
| `study_get` | `nct_id`, optional `view` | One exact study, `research` view by default |
| `study_batch` | `nct_ids` list, optional cursor/view | Up to 50 exact IDs, one provider page; missing IDs definitive only on final page |
| `arms_get` | `nct_id` | Registered arm groups and intervention identities/assignments |
| `outcomes_get` | `nct_id` | Registered primary/secondary/other outcome measures |
| `results_get` | `nct_id` | Posted results modules and independent reported group definitions when available |

Search arguments: `text`, `condition`, `intervention`, `intervention_terms`,
`title`, `outcome`, `sponsor`, `lead_sponsor`, `location`,
`study_identifier`, `patient_text`, `phase`, `status`, `study_type`,
`sponsor_class`, `country`, `updated_from`, `updated_to`, `advanced_filter`,
`preset`, `page_size`, `page_token`, `sort`, `count_total`, `view`.

- `intervention` can be used **together** with `intervention_terms`; these are
  explicitly caller-supplied alternatives, *not inferred drug synonyms*.
- `phase`/`study_type`/`status` are syntactically validated codes, not a frozen
  API enum list. Core/the registry decides actual validity. Phase 2/3 is not
  discarded from a Phase 3 search solely because more than one phase is listed.
- `sort` allows one or two API field names with optional `:asc` or `:desc`
  (or `@relevance`); authoritative field validity remains with the registry.
- Search returns **one page per call**, max 50 records, default 10; caller owns
  continuing via `next_page_token` and keeping identical query parameters.
  An empty page with a nonempty cursor is **not** classified as absence.
- No selector means no broad registry-wide scan. A `preset` still requires a
  meaningful search filter. `preset=phase3_interventional` uses a separate
  Core-pinned Phase 3/interventional Runtime Source; never trust the label alone.
- Search normally uses `view=summary`. `study_get` defaults to `research`.
  `research` retains the **complete source study**, including future protocol
  modules, results/derived/document/annotation sections if present. No list of
  named fields truncates future records. Large source results carry size
  warnings; model consumers partition complete evidence instead of discarding it.

## Arm group and results-group fidelity

`summary.arm_groups` preserves each registered arm's `label`, `type`,
`description`, and `interventionNames`; `summary.interventions` preserves
`name`, `type`, `description`, `otherNames`, and `armGroupLabels`.
`summary.declared_arm_links` joins **only** interventions' explicitly registered
`armGroupLabels` against arm labels, exposing `arm_label_found` and
`unmatched_arm_labels` rather than inferring a comparator from a name.
When arm assignments are not registered, this tool does **not** invent them.

`results_get` preserves the original `resultsSection` (participant flow,
baseline characteristics, outcome measures, adverse events, more info). Where
group arrays exist, `results_group_module_refs` keeps their actual source field
names as record-relative JSON Pointers with canonical content digests.
`results_outcome_measures_ref` points to the native outcome-measure array.
`registry_study` retains the complete native study once; neither reference copies
the results. Pointers use RFC 6901 escaping and never identify an external read.
Group definitions are not automatically matched to protocol arms.

Compatibility: callers requiring copied `results_group_modules` and
`results_outcome_measures` can continue using unchanged version `0.1.0`.
Version `0.1.1` is an explicit reference-format opt-in, with
`results_reference_schema=clinical_trials_results_refs.v1`. Consumers can read
the same native `registry_study.resultsSection` in both versions.

Absence remains distinct from false: `hasResults` can be true, false or absent;
`results_state` is `posted`, `not_posted` or `not_present_in_record`.
`is_fda_regulated_drug` retains the registry's true/false/missing semantics;
`why_stopped` is a reported statement, **not a verified cause**. Registry
completion, Phase 3, posted results and regulatory approval are different.

## Provider/runtime response contract

The source must use a reviewed JSON-object-compatible Runtime Source v2 response
parser. For `/studies`, **do not set `records_path=studies`**: it loses
`nextPageToken` and `totalCount`. Keep the page root, so normalized records are:

```json
{"records":[{"studies":[],"totalCount":0}]}
```

`nextPageToken` and `totalCount` are **optional** in real API responses.
A single-study GET returns a study object, normalized as one record. If the
provider responds with 404/429/500 or invalid JSON, the trusted runtime handles
transport and returns its bounded safe failure; the business adapter does not
suppress that as a false `no_match` or retry raw HTTP. Exact semantics for HTTP
404-to-empty-record conversion must be verified at the source execution owner.

**Live limitation:** runtime `validate_callable_variables` currently rejects
some safe-but-expressive Essie filter strings, quotes/parentheses and some
provider cursor tokens. Basic scalar queries and approved Core-pinned filters
are candidates for a first signed-worker proof. This is a *capability-specific
trusted query/cursor admission gap*, not permission to relax global validation,
add a provider SDK to this adapter, or claim every search mode works remotely.
Direct callable-child eager preparation and nested-depth restrictions are
separate gates. They are **not** closed by synthetic tests or `callable.enabled`.

## Validation and failures

Tests use **synthetic** API-shaped responses and an injected fake resolver. In
DataSpell open the `adapter-intake` folder as the project root, select a Python
3.10+ interpreter and install the approved wheel into that interpreter before
real project checks. For standalone logic tests, run:

```text
python -m unittest discover -s tests -p test_clinical_trials_lookup.py -v
```

Failure cases are stable safe codes (no provider body/log): missing selector,
invalid NCT ID, invalid cursor/pagination/sort, duplicate IDs, wrong detail
identity, ambiguous results, malformed page/list, missing trusted role,
trusted timeout/provider rejection, and output byte-budget violation.
A source failure is **not** a zero-result study search. Transport limits are
explicit; they protect callable/remote consumers without imposing a semantic
upper limit on registry arm group counts or clinical text fields.

`capabilities.v0.1.0.json` is **templates_only**, not a published MCP tool.
Promotion, signed runtime, source admission, direct callable composition and
public ChatGPT publication are each separately gated.

## Official references

- ClinicalTrials.gov Data API â€” API v2 endpoint reference (National Library of Medicine)
- ClinicalTrials.gov Data API â€” Study Data Structure reference
- ClinicalTrials.gov Data API â€” Search Areas reference
- ClinicalTrials.gov Data API â€” API version and data timestamp reference

The official documentation destinations are preserved in PR #147's review history.
The published intake handoff deliberately contains no literal provider endpoint URLs
or HTTP request targets; DLM Core owns the runtime source request configuration.
