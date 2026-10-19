# Prepared evidence integration - clinical consumer 0.1.1

## Scope and ownership

This is the **clinical-side intake implementation** on PR #143. It does not
modify, call, import, qualify or register the ClinicalTrials.gov, PubMed or UMLS
adapters. They are being validated independently. Their known result contracts
are consumed using synthetic fixtures here. No Assets/Core/UI change, source
configuration, promotion, deployment, provider execution or Skill write is made.

`variables` remains direct. `clinical_context` remains required and binding-owned.
The new `clinical_evidence` role is **optional and binding-owned**. Existing callers
without that role keep the previous context contract. Passing a local fixture to
the role is not proof of a production binding. Runtime-owned preparation must
resolve the exact client, source result, asset/version and selected clinical case.

## Execution model

```text
Existing parent / trusted evidence preparation (not implemented by this child)
    -> governed event selection
    -> independently admitted source adapters, when separately validated
    -> optional prepared clinical_evidence binding

Clinical Failure Intelligence @0.1.1
    -> validate context, source identities, digests and bounds
    -> ClinicalTrials.gov module windows + PubMed dated abstract windows
       + separate UMLS terminology candidates
    -> read selected complete product-memory paragraphs
    -> optional grounded-search / HTTP discovery for missing source families
    -> research -> outcome adjudication -> competing hypotheses
    -> focused critic batches -> consistency/dependency checks
    -> product paragraph delta -> edit critic
    -> canonical graph/report + decision summary + memory decision metadata
```

The child never calls `invoke_asset` for a source adapter. A source-result digest
is not a signature, deployment proof or entitlement. Callable nesting, lazy
source-role admission and retained-result handoff remain external gates.

## Bundle contract

See `tests/reference/clinical_evidence_bundle.v1.schema.json`. One bundle contains:

- `schema_version=clinical_evidence_bundle.v1`, `bundle_id`, exact `subject_id`,
  `product_id`, and the exact requested `event_ids` set;
- up to 24 `sources`, at most 1 MiB for the complete semantic bundle;
- per source: stable `source_result_id`, exact `asset_key`, `asset_version`,
  `output_role`, `purpose`, normalized inner `result`, and `result_digest`;
- optional `execution_ref`, only when actually supplied by the owning runtime.

`result_digest` is `sha256:` over UTF-8 canonical JSON (sorted object keys,
compact separators, Unicode preserved, nonfinite values forbidden). It detects
changed data; it does **not** authenticate the producer. `result` is the inner
`trial_result`, `literature_result` or `terminology_result`, not an HTTP response,
provider execution envelope, run context, raw source token or transport header.

| Source key | Version | Output | Consumer use |
| --- | --- | --- | --- |
| nusaibah.clinical_trials_lookup | 0.1.1 | trial_result | Exact study/arm/outcome/results module projections; search candidates and page coverage |
| nusaibah.pubmed_evidence | 0.1.0 | literature_result | Exact-PMID metadata/abstract joins, discovery results, partial dates, integrity notices |
| umls_terminology | 0.1.0 | terminology_result | `describe`/`search` terminology candidates only; no clinical efficacy/causality authority |

The UMLS key intentionally has no namespace prefix. Its other operations remain
outside this consumer's qualified contract until their owner validates them.
A source result has `purpose=case`, `comparator`, `mechanism` or `terminology`.
That value cannot authorize a new clinical identity or provider call.

## Scientific invariants

1. **One event is not one drug failure.** Preserve all original event-product
   associations. Selecting a product does not assign causality. Multi-product
   source events defer product-memory changes pending explicit arm/attribution
   review; valid research and hypotheses still return.
2. **No Cartesian join.** Trials, indications, regimens and products do not become
   interchangeable. An exact-study mismatch rejects the prepared input before
   paid work. An unidentified trial stays a candidate; there is no automatic
   event-scoped memory migration to a newly mentioned NCT.
3. **Protocol is not result.** Registered endpoints cannot establish that an
   endpoint was met or missed. Protocol arms and results analysis/safety groups
   keep separate pointers and labels. No analysis-group-to-arm join is inferred.
4. **A publication identifier is not evidence content.** Search/metadata results
   remain discovery context. Abstract text is joined to metadata by exact PMID.
   Article type comes from publication metadata, not its web hostname.
5. **Date precision survives.** A month/year stays month/year. Conservative interval
   bounds qualify only wholly pre-cutoff dates; no day is invented. Overlapping or
   unknown intervals cannot support definitive conclusions. Registry update dates
   identify the current snapshot, not the date the clinical result first occurred.
6. **Notices matter.** Retraction/correction/other reported integrity notices retain
   source text for review but block definitive use pending source-specific review.
   No notice in a summary is not a verified clean publication history.
7. **Terminology is not clinical equivalence.** CUI, vocabulary, semantic types and
   release remain candidate metadata. They never replace product IDs, prove a
   mechanism or trigger pharmacological-class learning. Reuse/licensing remains
   an external authority requirement.
8. **Hypotheses remain hypotheses.** A supported mechanistic interpretation is not
   automatically a demonstrated cause. Preserve falsification conditions,
   alternatives, adverse evidence and the actual trial/population scope.
9. **Failures alone do not define success rates.** Cohort denominators and controls
   remain explicit. No source-result bundle supplies a cohort by implication.

## Windows and model budgets

Source modules split at JSON fields/list entries or complete paragraphs; exact
JSON pointers or paragraph offsets and hashes survive. The collector admits at
most 384 windows / 768 KiB, with each window <=12,000 characters and <=16,000 UTF-8
bytes. Oversized scalar paragraphs and omitted windows have explicit digests,
counts and reasons. This is not full-source retention; the owning runtime must
retain the original prepared source result. No omitted text is called reviewed.

The 12 Agent-call, 2-research-worker and 1,800-second local policy is unchanged.
Structured sources reduce redundant discovery calls. Focused critic packets
factor common context, retain premise/source closure and validate each verdict
independently. A single unfittable complete assertion defers instead of losing
scientific qualifiers. Other research/analyst packet overflows remain explicit
`clinical_packet_requires_partitioning` results, not automatic budget increases.

Trusted SDK output-limit exhaustion becomes an unresolved stage without parsing
truncated JSON or repeating paid work. Unknown/authority failures still stop.
The ordinary small-case path stays one critic call. No extra planner Agent or
unqualified 64K generation policy is introduced.

## Preflight and outputs

`preflight_only=true` validates inputs and prepares source windows with **zero
Agent calls, source calls, HTTP reads, or Fixed/Dynamic Skill access**. Its result
has `quality.status=preflight` and `decision_summary.disposition=not_assessed`.
It proves local contract behavior only. `supplementary_search=false` suppresses
optional discovery; it does not grant access to any unprepared source.

The canonical output adds `prepared_sources`, `source_request_plan`,
`decision_summary`, `memory_decision` and `presentation`. Source-request entries
are suggested semantic needs only, explicitly `execution=not_requested`.
Decision questions come from reviewed/candidate hypotheses and are not investment,
regulatory or patient-treatment recommendations. No predictive success probability
is fabricated. Protocol/result/source/terminology graph edges remain typed.

Memory decision metadata reports real candidate presence/size/digest but always
`write_attempted=false`, `commit_observed=false`, `journal_status=not_attested`.
The adapter does not implement a durable publication journal. Optional report or
provider metadata can be omitted whole with a hash/size receipt, without changing
the canonical evidence or memory delta. An oversized canonical result still
fails closed: runtime retention and subsequent partitioned execution are separate
work, not something a hash can recover.

## Compatibility / external gates

Version stays 0.1.1 on this draft PR. Class learning remains disabled by default.
`memory_mode=apply` remains rejected. No read, write or client authority is borrowed
from the parent. Source adapters, Assets, Core, UI, source definitions and runtime
wheels are untouched. External work: validate the three source adapters, prepare
and bind their actual results, qualify the selected SDK/worker, admit models and
public-reference reads, and prove retained output / mutable Skill receipts
separately before any live composition or promotion.


### Duplicate native-source receipts and evidence byte accounting

Lookup study_get and results_get may include the same native study revision.
The collector charges the exact canonical JSON byte growth of every proposed
equivalent_source_results receipt *before* modifying an admitted evidence row.
The final retained_evidence_bytes count equals the sum of serialized prepared
evidence window bytes, including any attached duplicate source receipts.
The 768 KiB evidence budget and 384-window limit remain enforced separately
from the 120,000-byte Agent packet and 12-call budgets.

When inline provenance would exceed the evidence-byte budget, the scientific
window remains intact and unchanged. The prepared result is partial, with one
clinical_source_duplicate_receipt_budget grouped omission for each affected
source result. The compact equivalent_source_receipt_groups[] contains the
source_result_id, source_result_digest, and window_index_ranges of the affected
evidence[] entries. Each range is half-open [first, after_last]. These indexes
preserve exact lineage to the source receipt without repeating receipt fields
inside hundreds of windows or emitting an unbounded omission per window.
This marks deferred *inline* provenance, not missing scientific source text.
Separate sources[] summaries retain each source result and operation.

The coverage receipt distinguishes retained evidence bytes from counts of
duplicate native text and deferred inline receipt links. Two operations on the
same registry snapshot do not become independent corroborating sources.
