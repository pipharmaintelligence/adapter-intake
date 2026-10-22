# Clinical 0.1.9: bounded review and durable deferred work

The 0.1.8 live run completed its transport, but one absent candidate dependency demoted all 97 candidates. This release isolates invalid/cyclic branches and their transitive dependants before critic dispatch. Independent review decisions survive. Original unresolved dependencies remain recorded; no evidence or scientific acceptance is invented.

## Execution and scientific states

The analysis defaults to at most 64 logical calls and a 3600-second work budget. It stops admitting new calls when less than the admitted 1200-second stage allowance plus 300-second completion reserve remains. In-flight provider requests retain their existing runtime timeout; this is not cancellation or an end-to-end SLA. Source preparation precedes this analysis timer. `max_agent_calls` can lower the call ceiling (1..64); `max_product_seconds` can select 1501..48300, subject to the operator policy's stricter bounds. Existing 20-Agent parallelism and two product workflow slots are preserved; the shared pool remains Core-owned.

One input reconciler and one original-role retry remain scoped to affected input, with the existing four-task/eight-call reconciliation limits. Critic scheduling preserves two recovery slots and allows their recovery work to consume them. Insufficient recovery capacity produces a saved deferral without spending a reconciliation task. Reflection remains bounded to one round; unresolved follow-up questions are retained rather than recursively dispatched.

Critic packets use reversible local reference aliases and count/digest summaries for unassigned-source inventory. Every assigned source passage, support/contradiction polarity, dependency closure and case anchor remains intact. Unassigned sources remain in the canonical result and are explicitly not read/citable in that critic packet. Atomic closures that do not fit remain deferred. This does not claim a complete scientific review within every budget.

`quality.required_roles_completed` keeps its strict semantic meaning. `execution.disposition` separately reports returned invocations, scientifically unresolved tasks, deferred tasks and reviewed candidates.

## Durable pending work

`deferred_work` retains failed/deferred stage inputs, semantic gaps, unreviewed candidates, rejected out-of-packet candidates and deferred follow-up questions. Source text is stored once in the canonical evidence ledger. Pending packets refer to those exact rows and content-addressed candidate snapshots. `hydrate_task()` reconstructs the exact input digest offline and rejects source/context drift.

This is data, not a new runtime authorization or automatic resume feature. Every task has `retry_authorized=false`. A later consumer must explicitly select work, establish current governed bindings/admission and avoid replaying successful siblings. The completed 0.1.8 run has no retained per-Agent checkpoints; this release cannot recreate its missing model responses or certify its science.

## Governed publication

`prepare_result_for_persistence=true` emits the existing `clinical_intelligence_records={"records":[result]}` output, including partial quality and deferred-work metadata. `self_inspect()` validates exact staged JSON/JSONL against Core's full hash-bound node schema, then validates business reference closure. It produces value-free errors, never fetches external schema references and never writes storage.

Use `clinical_failure_intelligence.v1` as the payload schema version and JSONL at the approved file-artifact node. `core_node_schema_v1_1_0.json` is the compatible node handoff; it preserves historical 0.1.1..0.1.8 results and requires new deferred/publication fields for 0.1.9. Schema validity is distinct from scientific completeness. Partial artifacts may be published with their labels; unreviewed assertions never become accepted facts or memory lessons.

The manifest remains `dry_run` and does not grant write authority. Actual publication requires an approved policy for the exact installed asset version, server-owned output preparation, descriptor/dry-run, idempotency and a confirmed Core receipt. The inspected local policy is still 0.1.2; do not reuse it as 0.1.9 authority. Never rerun paid analysis merely to obtain a publishable output or forge a signed instruction for the retained old run.

## Delivery and qualification

Old adapter versions and all eight Agent 1.6.0 prompts/model policies remain immutable. Gemini-4-argon targets, credentials and pool selectors are unchanged. This adapter uses the existing Core-owned callable source and Fixed Skill interfaces. It does not implement storage, catalog or governance.

Provider-free tests cover independent siblings among 97 candidates, unknown/cyclic/transitive dependencies, strict reference alias/polarity validation, exact deferred reconstruction, deadline/call limits, retained rejected inputs, full output schema and staged self-inspection. Local Core qualification separately exercises the real schema controller, synchronized snapshot and SDK139 decoder. A new signed 0.1.9 paid run remains unperformed and requires reviewed delivery/admission.
