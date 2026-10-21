# Clinical 0.1.7 and SDK 0.1.136 — quality and JSON closure checklist

## Scope and observed failures

This change addresses the quality review of run `05999a28-80e9-4fe9-8834-351132a6a092` and the failure of clinical 0.1.6 run `131228b1-f1db-4122-bf22-5da10f7e3265`. No new paid scientific run, memory publication, E: installation or worker restart is part of this delivery. The monitoring automation `verify-clinical-continuation-completion` is PAUSED.

The older result is an offline reconstruction of exact saved stages, not its original signed full-result readback. It preserved 461 windows, 58 research claims, 25 outcomes and 66 hypotheses. Ninety of 91 candidates were unreviewed. Endpoint/status facts existed in the full sources and research claims while all five corresponding endpoint and disposition candidates were unknown.

The 0.1.6 run failed after 43m52s. Vertex returned HTTP 200, STOP, 22,548 characters and no output-limit finish. SDK proof identified `agent_result_json_object_invalid`. The rejected text was not retained: its exact syntax error remains unknown. All 26 completed results are preserved in canonical Core checkpoints. The auxiliary failure snapshot contains 22 matching results and explicitly reports four omissions. Offline SDK 0.1.135 validation reproduces path-pattern rejection on those four text projections; this does not establish the exact historical omission reason. No checkpoint was erased or replayed.

The saved 0.1.6 stages contain three `not_met` endpoint candidates and one `terminated` disposition candidate, alongside five endpoint unknowns and seven disposition unknowns. They include 38 hypothesis candidates, all with alternatives, indicators and falsification conditions. No critic completed and no final scientific assessment exists for that run. This supports fixing global reconciliation and preserving rich partial work; it does not establish final scientific quality.

## Implementation checklist

| Done | Finding | Implementation and evidence |
|---|---|---|
| [x] | Cross-packet endpoint/status facts were locally unseen | Share complete case-scoped identity, status, design, description, typed PRIMARY-result and case-publication windows with every outcome/hypothesis/critic packet. IDs remain explicit. Never infer an outcome from a keyword or invent a UMLS relationship. |
| [x] | Unknown local candidates could obscure reviewed known facts | Reconcile only literal `unknown` with a reviewed known value for the same trial and dimension. Preserve every candidate. Opposing known values and `not_evaluable` remain genuine review conflicts. Trial scopes are never merged. |
| [x] | Study disposition missing from structured summary | Include reviewed study disposition beside primary endpoint, safety, programme and regulatory dimensions. |
| [x] | Critic contract did not demand every assigned verdict | Role-specific item schemas include exact IDs, required fields and exact critic verdict count; post-validation still rejects duplicates and invented identities. Missing reviews stay visibly unreviewed. |
| [x] | Rich hypotheses lacked consolidated decision usability | Add deterministic priorities grouped by exact scope and reason, ordered by reviewed support. Retain the full original candidates, competing explanations, measurements, falsification conditions and evidence annex. No causal probability or certainty is fabricated. |
| [x] | Window count overstated source breadth | Report publication IDs/count and source-type window counts separately, including limited-breadth warnings and next evidence needs. When supplementary search and trusted retrieval are admitted, limited publication breadth triggers one bounded literature-discovery task even if a publication family is present. Native citations require existing trusted inspection before admission. |
| [x] | Global context could increase cost and starve review | Keep complete claims with their assigned windows; share complete critical source windows globally. Do not copy every claim's transitive closure into every packet. Reserve retry packet headroom before paid execution. Known-content plan assigns all 461 windows and all 91 critic items exactly once within the unchanged 64-call budget. Future generated cardinality is not guaranteed. |
| [x] | SDK rejected malformed JSON before adapter recovery | SDK unwraps complete Markdown/triple-quote/JSON-string wrappers, then applies lexical-only repairs for literal CR/LF/tab inside strings and trailing collection separators. Normal validation runs before returning typed content. Exact compatibility text and scientific string values are preserved. |
| [x] | One invalid response aborted unrelated work | A trusted SDK terminal-JSON proof permits one explicitly identified corrective attempt, counted against existing admission, concurrency, time and call budgets. A second rejection or deferred retry stays unresolved; valid sibling results continue. Both attempt digests/statuses remain visible and cached; a repeated caller cannot create a third attempt. |
| [x] | Recovery must not weaken boundaries | No JSON retry for timeout, unknown outcome, auth, scope, checkpoint or privileged-material failure. No prose substring extraction, missing braces/quotes/values, duplicate-key selection, nonfinite values, guessed scientific fields or hidden provider loop. Core remains admission/capacity owner; SDK remains transport/result owner; adapter owns scientific orchestration. |
| [x] | Previously published clinical versions must remain immutable | All prior manifest version objects and 142 published source/prompt bytes are checked against frozen hashes. Only new 0.1.7 files/contract 1.5.0 are added; model/thinking/output policies remain unchanged. |
| [x] | Parallelism and separate products must be distinguished | Provider-free tests exercise actual bounded 2/10/20 sibling dispatch, single retry, per-run budgets, separate product identities, evidence, memory selectors and results. Live 0.1.6 observations establish active-counter and canonical-stage overlap up to two only. They do not prove exact provider socket overlap, live 20-call qualification, or two concurrent clinical product runs. |
| [x] | Quality must not create an unrelated publication veto | Scientific review states remain explicit. No new generic memory-publication gate, automatic memory write, credential handling or lake/backend logic is introduced. |
| [x] | Scheduled monitoring must stop | Existing heartbeat paused after terminal failure was verified. No replacement run launched. |

## Response handling order and ownership

1. Provider transport checks HTTP, completion and existing safety/finish conditions. A timeout, MAX_TOKENS, safety block or unknown outcome is not relabeled malformed JSON.
2. Inside SDK terminal validation, parse one complete object. Unwrap at most four **whole-document** wrappers, including Markdown and `'''`. These wrappers already existed in SDK 0.1.135; new tests verify them.
3. On a JSON syntax error only, escape literal CR/LF/tab within quoted strings and remove trailing collection separators. Do not change scientific values, Unicode, units, negation or quotations. Reject duplicate keys and ambiguity. No provider request is made for these steps.
4. Apply the unchanged privilege/authority validator. Return typed `agent_result.v1` content plus the original compatibility text.
5. Only if the trusted private bridge reports the exact terminal-JSON rejection proof does clinical perform one separately admitted corrective task using the same scientific evidence and obligations. The failed original checkpoint is preserved. The new attempt has a distinct identity and explicit lineage; unknown outcomes cannot use this path.
6. Validate the retry normally. If it fails again, record unresolved work and continue to other candidates/critic/final partial output. A partial result is not scientific approval or a memory commit.

Company's business normalizer runs after usable SDK output. Copying it into clinical cannot rescue an upstream SDK rejection. Generic parsing belongs in the SDK; the one scientific-task retry and partial-workflow policy belong in the clinical adapter.

## Validation and remaining gates

The clinical provider-free suite, complete prior-version hash guards, official intake promotion-shape gate, saved-content packet qualification, SDK provider/private-IPC/checkpoint regressions, wheel closure and ECS source attestation are recorded with this implementation. GitHub CI must pass at the exact PR heads before merge. The checklist describes implemented behavior and offline evidence, not a guarantee that a future model will always return scientifically correct or complete content.

Pending after the requested promotion-and-stop boundary: deployment/installation of the official SDK, admission/registration of the new role prompt digests, coordinated Core quota-domain capacity for the company worker and clinical products, and an explicitly authorized live 10→20 warm-up with signed final-result retention and scientific review. New original mechanistic/PK-PD evidence still requires actual retrieval; software cannot manufacture missing evidence. No two-product paid benchmark was performed.

Evidence files: `known-content-qualification.json`, `saved-run-quality-comparison.json`, `intake-tests.xml`, `sdk-tests.xml`, `ecs-attestation.json`, and the prior `terminal-failure-report.md`/`parallelism-report.md` under the E: clinical 0.1.6 proof directory. Scientific source bodies remain private.
