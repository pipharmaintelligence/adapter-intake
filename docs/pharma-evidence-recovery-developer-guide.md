# Pharma 0.1.20: evidence recovery and issues annex

## Objective and observed failure

Company-14 run `5f6c16a4-9b39-4a20-93d6-b3443b6baf5e` reached seven completed
Agent calls in pharma 0.1.19 with 600-second timeouts admitted. It failed at
`market_researcher / pre_synthesis_quality / research_citations_missing` after
84 seconds. All three research roles requested search, but the safe provider
observations counted zero grounding chunks, native citations and admitted
citations. There was no transport retry or timeout in that attempt.

The claims-without-citations check sat outside the one-time JSON backup handler.
Its exception also bypassed incomplete-company recovery, so no dossier was
produced for retention. Formatting repair cannot create missing evidence. The
raw live responses were not retained; these facts do not establish why grounding
was absent or prove a provider projection defect.

0.1.20 preserves the evidence guard while making expected content problems
reviewable. No exception is converted into an approval, and no blanket
`except Exception` conceals authorization, execution or storage failures.

## Handling matrix

| Boundary | Action | Paid backup | Canonical effect |
| --- | --- | --- | --- |
| Complete Markdown/triple-quoted JSON | Unwrap deterministically; validate original contract | None when valid | Normal gates apply |
| Typed business JSON with repairable representation errors | Conservative cleanup, then original validator | At most one per original invocation | Only unchanged evidence/decisions may pass |
| Backup still invalid or changes facts/approval | Withhold response; retain earlier validated work and issue | No recursive backup | Affected company's candidates withheld |
| Original JSON cannot be parsed faithfully, or wrong business schema with correct identity | Retain static diagnostic; skip dependent stages or use other valid roles | None: no faithful object to compare | Affected company's candidates withheld |
| Claims without citations admitted for this pass | Withhold claims and role prose; preserve a validated earlier portfolio pass | None: evidence is not a format repair | Affected company's candidates withheld |
| Neither claims nor explicit uncertainties | Record the missing-content issue and deterministic evidence gaps | None | Affected company's candidates withheld |
| Valid claimless role with explicit uncertainty | Preserve explicit gaps; require critic disposition of its plan obligations | None | Absence alone does not reject other valid findings |
| All research roles have no usable claims | Return incomplete dossier; skip strategic/critic/synthesis/proposed benchmark | None | No replacement candidate |
| Critic fails, reports insufficient coverage, unsupported claims, missing sections or unsatisfied obligations | Retain negative verdict and issues; skip synthesis | None: never repair a negative verdict to pass | No replacement candidate |
| Wrong company/role, invalid runtime envelope/status, corrupt citation authority | Reject | No authority-changing repair | Fail closed before mutation |
| Provider/transport failure, exhausted budget, missing required Skill authority, commit/CAS/readback failure | Preserve runtime or integrity failure | Runtime-owned policy only | Never misreport an uncertain write as success |

This is a guarantee about the listed recoverable content cases, not a promise
that an asset can never fail. Invalid requests, credentials, deadlines, interrupted
workers and post-write proof failures still require truthful failure reporting.
It also cannot repair a provider response that the generic runtime rejects before
delivering a completed Agent envelope to the adapter.

## Execution and reflection

Company Scope still supplies CompanyContext through the existing composition
path. Intelligence does not query Companies again. Optional learned methodology
remains optional, and first-memory preview remains supported.

The fixed methodology and bounded planner precede three parallel research roles.
Only portfolio research can reflect sequentially, for 1–3 requested total passes.
Each pass is validated before use. A new pass with positive claims must supply
its own admitted citations; prior-pass citations cannot silently validate new
claims. A bad reflection retains the previous validated payload and its citations,
records an issue, and stops that role's remaining passes. A claimless pass is not
automatically repeated. There are no extra research retries.

Valid roles can continue through the existing strategic, critic and synthesis
path with explicit gaps. If a mandatory stage remains invalid or quality rejects
the company, validated progress is carried into an incomplete review packet.
Known critic-rejected/stale claims withhold their entire role prose because the
current citation model is role-level, not exact claim/span linkage. Unscoped
contradictions withhold the research prose that cannot safely be separated.
Retained research is marked pending final review; it is not an approved candidate.

Each company is prepared independently before the existing apply phase. The
affected company's memory and methodology writes are withheld. Another company
that passes all original gates remains eligible. No new per-section write engine,
partial memory commit, or storage lane is introduced.

## Issues annex and retained results

`company_results[].issues_annex` and the corresponding retained review-packet
company entry contain the same additive object:

```json
{
  "schema_version": "pharma_review_issues.v1",
  "issue_count": 1,
  "items": [{
    "role": "portfolio_researcher",
    "stage": "pre_synthesis_quality",
    "field": "citations",
    "rule": "research_citations_missing",
    "category": "evidence_unavailable",
    "action": "previous_validated_pass_retained",
    "section_ids": [],
    "withheld_claim_count": 2,
    "pass_number": 2
  }],
  "truncated": false,
  "canonical_candidates_withheld": true
}
```

The example omits role-owned section IDs for brevity; real entries derive those
IDs from the canonical role contract. Actions distinguish withholding, preservation
of an earlier pass and skipped dependent stages. Categories distinguish evidence
absence, unresolved response format and quality rejection. Counters do not include
raw invalid statements. Entries are bounded to 32 per company, above the current
bounded recovery paths; an overflow is explicitly marked instead of silently lost.

An incomplete result has `research_incomplete=true`, `business_result_state=incomplete`
and no mutation eligibility. `agent_schema_incomplete` distinguishes mandatory
schema interruption from evidence/quality interruption. A successfully executed
batch can return `status=success` while its business result is incomplete; consumers
must inspect completeness and quality, not infer approval from terminal completion.
Actual evidence counts and any valid negative critic judgment remain inspectable.
Unscored benchmarks remain unknown. A mandatory preparation stage that did not
finish has null replacement bytes and no fabricated verdict. If valid partial
research reaches synthesis and benchmarking, its proposed bytes remain inspectable
but mutation-ineligible while the company is incomplete. Review-packet hashes
cover the added annex.

The annex is inert business output. Core/Assets retain it using the existing
preview-artifact path. `publish_dossier` retains the existing readiness signal for
runtime-owned output admission; it neither uploads directly nor bypasses output
policy. An incomplete company does not block delivery of the explicit batch report.
This change adds no Dynamic Skill initialization or canonical publication authority.

## Prompt and backup review

The former search prompt contained both plain-text evidence-stage instructions
and a contradictory global strict-JSON suffix. Search now requests only evidence
notes. The next admitted step formats JSON, preserving evidence gaps. The formatter
explicitly allows `claims=[]`, forbids moving unsupported facts into prose or
inference, and distinguishes no evidence from not applicable or a negative fact.
The critic preserves genuine failures; it does not invent a pass to keep processing
alive. The adapter handles continuation.

The backup remains the single registered `research_response_resolver`, with zero
tools, one provider step and one reservation per rejected original invocation.
It cannot search, supply citations, alter company/role, change factual meaning,
flip critic decisions or invent benchmark coverage. Complete JSON wrappers are
parsed before and after repair. If an original response cannot be faithfully
decoded, there is no reliable business object to compare against: it is withheld
with a static diagnostic rather than sending arbitrary raw prose to a blind repair.

Changed Agent contract versions: researchers and critic `1.0.7`, resolver `1.0.3`.
Other Agent definitions retain their previous versions. Models, thinking levels,
tokens, 600-second provider requests, provider policy, tool budgets and the
1,800-second overall deadline remain unchanged.

## Validation and delivery

Run the deterministic pharma suite, intake promotion-shape guard, and evaluation
package tests. New regression cases cover missing citations in one/all roles,
reflection without its own citations, original malformed JSON for every role,
quality rejections, retained prior evidence, claimless prose sanitization, empty
claims/uncertainties, independent companies in apply, annex checksums and strict
identity/citation integrity. Existing single-backup, Markdown parsing, quota and
historical-version tests remain mandatory. Tests use fake provider/storage helpers.

Promote the exact green intake commit via Assets' existing adapter-intake workflow,
targeting current main with manifest removals disabled. Verify old identity/module
and helper parity in the generated package before merge. No Core business special
case, runtime version bump, local wheel build or installed-module patch is needed.
Deploy only an official workflow artifact after approved merges and an idle-worker
check. This code change makes no new paid live run or memory/methodology write.

## Remaining evidence limits

Offline success proves control flow and withholding, not provider grounding quality.
Review provider citation projection with representative recorded/synthetic fixtures
before attributing empty grounding to the provider. Do not treat an incomplete
preview as full research success. Future live verification should inspect the
retained dossier/annex, citation counts, per-pass trace, actual Agent counts and
unchanged canonical state before considering any apply action.
