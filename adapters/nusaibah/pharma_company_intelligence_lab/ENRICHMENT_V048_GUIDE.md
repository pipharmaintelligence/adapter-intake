## 0.1.48 bounded schema recovery and source preflight

Research responses with a wrong schema label may use their existing one-resolver
reservation. The resolver can correct that label only: all other business values
must match exactly and the original admitted citation envelope is preserved.
Shared provider-call, concurrency and elapsed-time budgets remain unchanged.

With runtime 0.1.107, confirmed timeouts of the pinned pure exact-span operation
can retry twice with 5- and 10-second waits. Each attempt consumes the existing
32-call limit and requires enough remaining time for the call plus publication
reserve. Unknown failures, other callables, Agent execution and Skill writes are
not replayed by this helper. Use runtime 0.1.107 for this qualification.

`preflight_only` now uses the same source verifier and toolkit 0.1.2 as enrichment.
It performs no Agent calls or Skill writes. This repairs the inherited preflight's
0.1.1 result-version mismatch. Historical adapter versions remain available.

Offline qualification includes publication, readback and history using synthetic
Skill I/O. Live publication qualification is still required before production use;
passing these tests is not evidence of an actual Core write.
