# Pharma 0.1.41: bounded heavy research and critic priority

The 3,600-second workflow allowance is declared inside the 0.1.41 version's
execution contract. The shared manifest execution contract stays at 1,800 seconds,
preserving previously promoted versions and the package-history composition guard.

This release preserves CompanyContext, grounded public search, exact readable
source spans, per-claim criticism, optional prior methodology, one-time format
recovery and the existing Dynamic Skill ZIP publication lane.

The workflow allowance doubles to 3,600 seconds, with a 3,300-second internal
coordinator. Explicit Agent ceilings double to 1,200 seconds; generation remains
32,000 tokens. These are upper bounds, not consumption targets. Source-backed
findings, uncertainty and complete JSON take priority over verbose output.

## Scheduling and scalability

Measured paragraph/subsection packets use one fair queue interleaving researcher
roles. One role's supplemental paragraphs cannot monopolize dispatch ahead of
other roles' discovery. Provider parallelism stays two by default, bounded to
1–3, and the shared cap stays 48 calls including recovery and reflection.

Evidence criticism runs before optional strategy and synthesis. Sections with
findings take priority over empty sections within the critic queue. Research
admission reserves a critic allowance and 180 seconds for publication. The
critic may use that allowance itself and preserves only the publication reserve.
Unfit tasks become bounded diagnostics, preserving successful siblings.
Source-admitted and critic-reviewed facts survive unavailable presentation calls
through the existing deterministic renderer. Missing/unsupported evidence is
never made into a valid fact. Previous production helpers stay byte-identical.

Every task cannot take 20 minutes inside a 60-minute work item. Excess work is
recorded in `Annex: Need Review` with section/paragraph/source references.
Scale with bounded company/section work items and existing continuation, not an
infinite loop or unbounded provider concurrency. Partial coverage remains
explicit. Optional 1–3 reflection passes share the absolute budget and publish
once after actually completed passes.

The runtime bounds the new 1,200-second provider-step allowance across retries.
An exhausted explicit transport/availability wait is recorded against its chunk
without another paid JSON resolver. Other successful roles continue. Credential,
scope, policy and unknown failures are not converted into research findings or
successful writes. Format failures retain their existing one-time backup path.

## Deployment prerequisites

Merge generic Core timeout/material support and Assets receipt/runtime support
before official intake promotion. Explicitly apply `max_timeout_seconds=1200`
only to the intended provider registration via the existing owner-scoped policy
update. Existing registrations are unchanged automatically.

Core material must cover the selected timeout:
`DLM_PROVIDER_EXECUTION_MATERIAL_TTL_SECONDS=1200`. Credential expiry and the
admitted session deadline remain upper caps. The scoped-session ceiling must
admit a 3,600-second work item.

Assets' job budget must cover work and cleanup:
`PYTHON_ADAPTER_WORKFLOW_JOB_TIMEOUT_SECONDS=3840`. Use a dedicated consumer with
`--timeout=3840`, and a queue reservation exceeding that duration (the verified
local `retry_after` is 9,000 seconds). Poll at least 3,900 seconds and allow at
least 4,200 seconds of operator session time for Scope, preflight, the long pharma
job and final readback together. Verify effective server/process settings:
changing a client `.env` does not reconfigure servers.

Install only the official workflow artifact after promotion, retaining the runtime
version and historical catalog entries. Check exact package hashes, admission,
policy/material/session limits and E-worker readiness before any paid submission.
The earlier failed company-59 UUID is evidence, not an automatic retry target.

## Acceptance

- Long signed responses remain receipted throughout admitted work; stale,
  tampered, replayed and cross-identity responses remain invalid.
- Simulated slow research leaves criticism admissible after the old 14½-minute
  cutoff. Optional presentation never precedes criticism.
- Queue fairness and provider concurrency limits are observed.
- JSON/Markdown parsing and one-time backup remain active for every role.
- Mixed successful/unresolved chunks preserve eligible findings and diagnostic
  positions, with benchmark disabled and no human approval gate.
- Methodology is optional; actual critic advice is reused when available.
- Actual ZIP upload/history and exact partition readback determine publication.
- A synthetic cycle passes before a newly authorized paid live proof.
