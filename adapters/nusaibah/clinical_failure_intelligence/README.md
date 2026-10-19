# Clinical Failure Intelligence 0.1.2

PI-2061. Product-first clinical assessment with traceable evidence, scoped
independent review and a non-writing product-memory proposal. This is a development
candidate; source CI, package qualification, runtime admission and scientific
evaluation are separate gates. See tests/reference/EXECUTION_MODEL.md for the full
requirements/model and CHECKLIST.md for the current evidence boundaries.

## Execution

The clinical asset accepts a governed clinical_context and either a governed
clinical_evidence bundle or exact retained-output references. It validates identity,
normalizes evidence, then runs trial/literature/event research, outcome adjudication,
hypothesis analysis and independent criticism. A single targeted reflection round
may correct gaps. A single product-memory editor and independent edit critic produce
a preview from accepted findings. Class work is disabled by default.

Use preflight_only=true, memory_mode=off, supplementary_search=false for the
zero-Agent/zero-Skill contract path. A preflight result is not scientific validation.
mechanistic_case and denominator-aware cohort_pattern remain supported; failure-only
events cannot provide a cohort denominator.

## Invoking the three sources

tests/operator/run_clinical_workflow.py is an operator workflow using only the
official SDK. It runs independently admitted source assets before the clinical
asset. source_workflow.py owns deterministic semantic selectors and bounded source
coordination; it contains no transport. retained_sources.py assembles the normal
clinical bundle from Assets-hydrated retained outputs. No source implementation is
imported, no provider endpoint is constructed, and no child invokes grandchildren.

Pinned producers:
- nusaibah.clinical_trials_lookup 0.1.1: study_get and results_get for the selected NCT.
- nusaibah.pubmed_evidence 0.1.0: trial_publications, article_batch, abstract_get,
  integrity_get using actual discovered PMIDs, at most three publications.
- umls_terminology 0.1.1: exact bounded search using the governed product name.

The operator first obtains a signed clinical preflight subject. The exact NCT must
already belong to that governed context. Missing/ambiguous identity stops before
source submission; there is no paid identity planner or invented association.
The operator currently prepares one exact case. Cohort analysis uses a separately
governed denominator and prepared cohort evidence, not this one-case acquisition loop.

Only {run_uuid} references enter the final clinical request. Core/Assets owns
client/producer/version/output-role/checksum/expiry validation and hydration.
Local envelopes or digest checks alone do not establish live authority.
Confirmed source unavailability preserves successful independent source runs and
returns partial preparation. Unknown submission outcomes stop for reconciliation.

UMLS query attestation and its closed fetch receipt are preserved. The producer and
trusted worker validate the full fetch before result limiting; clinical checks the
selector commitment and receipt shape without attempting to authenticate it again.
Unknown release, provider retrieval time, vocabulary and completeness stay unknown.
Terminology candidates cannot support an outcome or establish clinical equivalence.

## Bounds, reflection and public search

At most 32 shared logical Agent calls, two concurrent researchers, 1,800 seconds
and a 120-second completion reserve. Complete Agent packets are at most 120,000
bytes. Research, outcome, hypothesis and critic work partition between complete
windows and assertions; results/safety precede contact/location metadata. Atomic
oversize work is explicitly deferred. Canonical scientific windows are not sliced.

Reflection: at most one round, at most two distinct targets and four extra Agent
calls total. The current coordinator selects one highest-priority follow-up within
that ceiling. Repeated role/question/evidence work is deduplicated. No new evidence
or corrected claims stops downstream repetition. Missing revised premises withhold
affected conclusions while preserving independent valid siblings.
Unselected follow-ups, exhausted allowances and further-round requests are recorded
explicitly; a known unaddressed research request cannot be labeled complete.
Reflexion: at most one product edit proposal and one independent edit review; no
self-rewriting loop, learning from unaccepted hypotheses or mutation is performed.

Governed public search supplements named gaps and contradictions. Only researcher
roles may request it. At most six logical search tasks, two per role, and twelve
trusted reference reads across the whole assessment. Provider-native citations are
leads until open_reference(..., mode=http) inspects actual text. Generated URLs and
snippets are not clinical evidence. An accessible excerpt is not full-text access.
Provider-internal grounding calls must also be bounded by the admitted Agent profile.

Research extraction uses standard reasoning, with deeper interpretation for
contradictions. Outcome, hypothesis and independent critic roles require high
reasoning profiles. Product editing uses standard reasoning and deeper correction
review. Actual model and provider thinking settings are runtime-owned and must be
admitted; prompts do not set unsupported provider parameters or request private
chain-of-thought. Exact seven role/prompt digests are in admission_requirements.json.

## Size and effects

Source bundle and canonical result warnings begin at 4 MiB; an oversized warning
does not discard scientific content or raise an adapter size exception. Optional
report/provider presentation may be omitted with a receipt. Canonical evidence
indexing remains bounded and reports every omitted window. Runtime transport,
retention and callable limits remain authoritative; a warning grants no bypass.
The callable result contract declares 4 MiB separately from model packet budgets.

Product Skill access is read-only, selected by product_id. memory_mode=preview is
the default; off skips it; apply is not admitted and fails before paid work.
prepare_result_for_persistence optionally emits a records envelope, with dry_run
output policy only. There is no Skill initialization, CAS write, publication or
durable clinical-stage recovery in this candidate. Those capabilities require their
own admission, schema/QC, receipts, readback and history qualification.

## Development and packaging

From this folder:

    python -B -m unittest discover -s tests -p "test_*.py"
    python -B tests/build_prompt_catalog.py --check
    python -B tests/run_fixture.py prepared_evidence_preflight

prompt_*.md files are editable prompt sources. Run tests/build_prompt_catalog.py
after editing them and update admission hashes. Runtime uses generated Python
constants because SDK and ECS asset wheels do not package arbitrary Markdown.
Fixed methodology remains version 1.1.0 at its exact unchanged digest. Clinical
Agent contracts and prompts are version 1.2.0; prior 0.1.1 source is preserved in
the preceding intake changes. Development references/fixtures/operator scripts
stay under tests and are excluded from the promoted runtime file plan.

The manifest declares local_worker and ecs with independent qualification gates.
Do not equate a local package import, synthetic transport double or ECS declaration
with signed execution, deployed image parity or scientific accuracy.
