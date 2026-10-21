# Clinical 0.1.6 parallel execution and coverage

Status: locally implemented and provider-free qualified; not promoted or live-qualified. Published 0.1.2–0.1.5 files and manifest contracts remain frozen.

## Execution model

The optional `variables.agent_parallelism` integer is bounded to 1–20, default 20, and may only lower the reviewed ceiling. One run-wide semaphore bounds every Agent call, including research, outcome, hypothesis, critic and later dependent work. Each independent phase uses one flat pool. Reservations follow plan order before dispatch and results join in that order, making budget allocation and output deterministic despite completion order. The next dependent phase starts only after its predecessors finish. Prepared work rechecks the completion reserve immediately before provider dispatch.

The new execution policy allows 64 total logical calls, compared with 32 in 0.1.5. This is an explicit scientific coverage budget increase, independent of simultaneous-call capacity. Packet bytes may reach 262144 while respecting the runtime's 160000-character and actual byte allowances. The 48300-second workflow deadline, 300-second completion reserve and 1200-second per-call allowance remain unchanged. Existing seven Gemini-4-Argon role prompts, request policies, thinking levels and prompt digests are unchanged.

Canonical evidence retains all scientific text, source IDs, windows and provenance. Agent packets factor repeated operational receipt fields only; a grouped critic index keeps all other evidence IDs, source types and trial scopes. No text truncation, invented claims, unsupported certainty or weakened scientific acceptance is used to obtain concurrency.

On the preserved partial case (461 windows, 58 claims, 25 outcome assessments, 66 hypotheses), provider-free packet sizing yields research 10 + outcome 8 + hypothesis 12 + critic 15 = 45 calls before optional memory/refinement work, with zero indivisible packets exceeding allowances. Future model output cardinality is unknown. Work exceeding bounds is explicitly deferred and retained as partial; 64 calls cannot guarantee every possible scientific task will finish.

## Runtime and Core admission

Two product runs need two clinical worker run slots, twenty bridge requests per process (`OBS_RUNTIME_AGENT_MAX_INFLIGHT=20`) and `OBS_PROVIDER_SHARED_CAPACITY_REQUIRED=1`. Core must already enforce actual shared quota domains. The current observed four-target deployment has no active shared capacity profile; it must not be silently activated at twenty calls. A conservative reviewed profile could admit four globally/two per run and use caller parallelism two. A future fifty-independent-domain profile could admit forty globally/twenty per run. These are candidate profiles, not configured live capacity or measured throughput.

Every invocation still enters existing Core admission. The adapter never selects targets, credentials, storage backends or quota policy. No memory mutation is added; existing preview/read-only rules remain. Two concurrent products have distinct subject/context/result/memory scopes. Unknown attempts do not trigger adapter retries, and valid independent sibling results remain retained by the existing SDK checkpoints.

## Qualification checklist

- [x] Concurrency 1, 2, 3 and 20, deterministic budget and joins.
- [x] Failed independent sibling, unknown repeat fence and cache-hit accounting.
- [x] Queued dispatch completion reserve recheck.
- [x] Two product fan-outs share simulated admission; complete adapter runs preserve distinct product identities.
- [x] Scientific text/provenance preservation and grouped critic index.
- [x] Reviewed metadata equals executed policy; earlier version bytes/contracts remain exact.
- [x] Provider-free package/import and official SDK intake validation.
- [ ] Intake review, immutable Assets promotion and Core role/binding admission.
- [ ] Reviewed shared capacity cutover and clinical-only worker activation.
- [ ] Authorized paid scientific coverage/speed benchmark for two real products.

This revision does not repair the historical 0.1.5 archive by paying for new analysis. Archive recovery must use the same original version and inputs under explicit replay-only mode. An archived partial result is useful retained evidence, not a fully completed scientific review or published memory.
