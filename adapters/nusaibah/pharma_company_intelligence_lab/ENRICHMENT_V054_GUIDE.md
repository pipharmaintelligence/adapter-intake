# Company Agent concurrency and Gemini 4 — 0.1.54

Version 0.1.54 uses `gemini-4-argon` for all nine declared company Agent roles,
including the compatibility planner and disabled benchmark role. Their existing
enabled/disabled state, prompts, search permissions, response formats, thinking
levels, token ceilings, timeouts and governed ProviderVault selectors remain
unchanged. Seven migrated roles receive new immutable contract versions; the
strategy and critic contracts already using Argon retain their exact definitions.
Google documents the model in the Gemini Enterprise Agent Platform model card
named "Gemini 4 Argon".

`variables.agent_chunk_parallelism` accepts integers 1 through 15, defaults to 15,
and rejects booleans, strings, fractions and out-of-range values. This is an upper
allowance: only independently ready chunks execute together. One coordinator and
one semaphore cover research, review, synthesis and bounded response repair.
Ordered results, per-company role budgets, the absolute 48-call limit, the
3300-second coordinator budget and downstream publication reserves are preserved.
Raising concurrency does not create extra research or enable benchmark/planner
calls. Companies and dependent phases retain their existing ordering.

Publication keeps 0.1.53's exact admission/redaction, readback, history, attribution
and ambiguous-write rules. No backend, governance or provider transport is added
to business code. Existing 0.1.53 entrypoints and helper files remain unchanged.

The candidate requires SDK 0.1.137. Before deployment, qualify the installed wheel,
all changed exact Agent contracts, signed session capacity of at least 15 and Core
provider admission. A worker execution slot is a workflow slot, not an Agent-call
permit; a large provider pool also does not grant more simultaneous calls. Core
still controls shared capacity and clinical work can consume some of it. Neither
an existing checkpoint nor a running worker should be switched to this version
while accepted work is active.

Provider-free tests prove the fifteen-call ceiling, overlapping scheduler use,
ordered results, bounds, unchanged call budgets, canonical output parity and
unchanged 0.1.53 behavior. They do not prove a fifteen-way live provider overlap,
speed improvement, provider quota, deployment or publication of a real company.
