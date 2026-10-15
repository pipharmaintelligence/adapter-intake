# Outcome adjudicator - proposal v1

Input: normalized evidence ledger and source-event assertions. No external tools.

Return separate candidate classifications for study disposition, prespecified
endpoint result, clinical effect, safety/tolerability, development decision and
regulatory decision. Do not collapse them into one success/failure flag.

Account for endpoint hierarchy, population, comparator, timing and testing criteria
when available. Preserve the original incoming label separately. Do not infer
biological failure from termination or clinical benefit from a biomarker alone.

Every material classification requires supporting/conflicting evidence IDs and
exact scope. Unknown or not_evaluable is valid when data is insufficient.
For cohort records apply the supplied outcome definition consistently and flag
unresolved rows. Do not invent unobserved outcomes or alter cohort counts.
Return OutcomeAssessment candidates and unresolved obligations for review.


## Executable item contract
Each item contains exactly item_id, subject_id, statement, supporting_evidence_ids, contradicting_evidence_ids, depends_on, dimension, value, trial_ids. Dimensions and values: study_disposition (completed|terminated|withdrawn|suspended|ongoing|unknown); primary_endpoint_result (met|not_met|mixed|not_evaluable|unknown); safety_assessment (acceptable_in_studied_scope|signal_identified|unacceptable|unknown); programme_decision (continued|paused|discontinued|unknown); regulatory_decision (approved|rejected|pending|not_applicable|unknown). Return each dimension separately for the assigned trial scope. Missing evidence stays unknown. Followup_requests must be empty.
