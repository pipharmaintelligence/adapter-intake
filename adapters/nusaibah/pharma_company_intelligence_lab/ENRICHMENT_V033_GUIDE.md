# Objective

Measure every actual Agent input before dispatch, optimize repeated context, review bounded paragraph/subsection pieces in parallel, and consolidate source-bound findings without changing lake, query, provider or publication authority.

# System Context

Live company-14 run 41b1d658-6849-41cd-888c-3f6f611a720a used 0.1.32. All twelve dispatched Agents returned valid JSON. The synthesizer was never dispatched: its aggregate input exceeded the adapter's 42,000-character packing limit. The static failure proof is intelligence_synthesizer / pre_synthesis_quality / section_input_budget_exceeded / input. No JSON resolver could fix an input rejected before an Agent call.

The fix is additive 0.1.33 in adapter-intake. Historical versions and generic Assets/Core runtime remain unchanged. Runtime version stays 0.1.105; deliver through the official promotion workflow and its verified official artifact.

# Approach

The same workflow has one processing lane:

CompanyContext -> admitted source snapshot and optional historical learning -> paragraph/subsection inventory -> measured role packets -> bounded parallel Agent calls -> original role validators and exact-span toolkit -> scoped critics -> validated chunk consolidation -> deterministic baseline-preserving memory candidate -> existing Core Dynamic Skill ZIP/CAS/history/readback.

Dependencies remain sequential; independent work within each phase is parallel. Planning uses canonical section/subsection chunks. Research uses exact source paragraph spans and their original locator, entity and snapshot. Analysis, critique and synthesis consume paragraph/subsection groups of accepted evidence. The existing structured-review toolkit validates the structural source inventory, while its exact-span operation remains the citation authority. Text is not split at arbitrary character offsets to make a request fit.

# Changes Made

Every original and backup receives final JSON-payload measurement before the runtime helper is called. Measurement records characters, UTF-8 bytes and a conservative bound including registered prompt text plus framing reserve. The actual dispatch sends that measured, prepared payload. This is not an exact token count. The existing provider token ceiling remains 32,000, including thinking headroom, and role output contracts remain bounded.

Shared optimization removes repeated input aliases, duplicate list items and unrelated full-document metadata. Synthesis receives the current piece's interpretation and scoped verdicts rather than all other sections again. Exact claim statements, IDs, dates, rights direction, source locators and qualifications remain intact. Consolidation merges only exact equivalent facts in the same company/role and preserves conflicting or differently qualified findings separately. Per-chunk provider results are validated individually; adapter consolidation is labelled explicitly and does not fabricate an Agent receipt or human approval.

Parallelism defaults to two provider calls and accepts agent_chunk_parallelism=1..3. One run-wide semaphore also covers backups, preventing nested research pools from multiplying provider concurrency. Same-role concurrent chunks have separate original invocation ordinals and one backup reservation each. A failed or oversized backup cannot recurse.

agent_chunk_input_chars defaults to 42000 and may be reduced to 8000..42000. agent_chunk_max_calls defaults to 48 and accepts 13..48; it counts original and backup dispatches together across the whole asset execution. These are optional variables, not new environment settings. Benchmark calls remain zero, and multiple source pieces still form one portfolio review pass rather than extra reflection loops.

Before dispatch, the scheduler reserves the full 600-second Agent allowance plus 180 seconds for consolidation/publication. Its internal 1,650-second scheduling window stays inside the unchanged 1,800-second asset deadline. No new provider call starts when that reserve cannot fit. Large cases can remain incomplete; parallelism cannot guarantee arbitrary work finishes within a finite deadline.

# Modularity Impact

CompanyContext is consumed without another Companies query or a duplicated input binding. No lake/backend logic, credentials, storage driver, new publish policy or memory authority is introduced. Fixed and Dynamic Skills continue through the same Core-owned lane. The E company-range runner remains standalone operator code and stores only its progress checkpoint.

Sources retain atomic paragraphs at the existing bounded-admission boundary. A source character/byte cap or an indivisible oversized paragraph is reported as incomplete; it is not silently cut and presented as a complete document. Structural inventory and exact offsets refer to the admitted snapshot, not a claim of complete public-web research.

# Validation

Required offline regressions cover every original/backup measurement, Unicode byte accounting, paragraph/subsection offsets, no character clipping, global concurrency, deterministic plan order, deadline/call caps, simultaneous same-role backup reservations, large interpretation/critic context, qualified fact consolidation, partial chunk failures and negative-critic preservation. Run these against the real SDK and CI stubs, then verify packaged imports, historical file/contract preservation and latest-main promotion CI before any further paid run.

# Risks / Open Questions

Do not equate workflow completion, complete document coverage and publication. Failed content chunks remain unresolved with their actual static diagnostics; successful independently validated siblings may continue. Failed required planning or wholly unavailable synthesis can retain an incomplete company. Negative critic decisions are never flipped to pass. Authority, privilege, unknown runtime failures and forged toolkit evidence remain strict failures.

The shared call/deadline budget can leave a later company or paragraph unprocessed; use bounded company work items and the existing continuation/epoch architecture for larger work. No unverified continuation mechanism or automatic paid resubmission is introduced here. Memory and methodology commits remain independent; partial or unconfirmed publication must not advance the E runner's last-success cursor. Live publication is unproven until actual Core receipts, storage readback and history have been checked.

The complete retained dossier is measured before any Core mutation, with 64 KiB reserved for publication receipts. A result that cannot fit the unchanged 512 KiB retention contract returns an explicit incomplete summary and withholds publication; candidates are never character-truncated or written before this check.

Phase reservations prevent a long research inventory from spending every call before critique and synthesis. Original and backup calls share these fixed role budgets: planner 8, each research role 6, strategy 6, critics 10, synthesis 6 (48 total). Extra paragraph work remains explicitly unresolved; earlier validated findings continue to downstream phases. A source-admission cap also marks research incomplete. No phase budget is described as full-document coverage.

Deferred work is rejected before reserving original/backup invocation counters, and dispatch rechecks the shared budget under its lock. A long inventory therefore cannot exhaust runtime attempt counters by repeatedly trying work already outside the phase allowance. A concurrency race may still be deferred at final admission; receipts and provider_dispatch_count are the actual dispatch evidence.

Research packets are scheduled in deterministic source rounds, preserving each packet's original paragraph/subsection grouping. This gives the governed context, historical memory and every admitted public source an initial turn before a long memory document can consume the phase budget. Deferred later pieces remain unresolved; fairness does not claim complete coverage or override evidence checks.
