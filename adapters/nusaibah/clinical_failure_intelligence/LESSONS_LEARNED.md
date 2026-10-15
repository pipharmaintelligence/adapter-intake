# Reviewed pharma lessons applied

This maps the inspected source to new behavior. It is not a claim to have audited
every historical PR or run all prior suites locally.

## Actual pharma_evaluation baseline: 0.2.3

Source: adapters/nusaibah/pharma_company_intelligence_lab_evaluation at intake
48bbdecc944a0458d00b40ec50cecffbdce18515. adapter.yaml identifies 0.2.3.
supplied_source_scoped_review.py separates identity from commercial requirements;
quote_review_orchestration.py separates literal support, coverage, consistency,
external truth and historical comparability.

| Lesson | Implemented safeguard | Verification |
|---|---|---|
| A correct quote can support the wrong requirement | Separate clinical dimensions and explicit scope review | Evidence/quality and outcome-coverage tests |
| Empty/excluded coverage cannot mean complete | Exact role, seed, dimension and critic obligations | Contract and orchestration negative tests |
| Quote existence is not external truth | Passage checks remain separate; external_truth_verified=false | Exact-span and output tests |
| One passage may support distinct claims | Deduplicate source identities, not claims by equal quote | Distinct-claim same-quote test |
| Global consistency cannot invent missing local evidence | Closed evidence IDs and transitive premise invalidation | Unknown-reference, conflict and dependency tests |
| Runtime inputs must not rewrite reviewed policy | Immutable policy and closed request | Configuration-override tests |
| Historical behavior needs preservation | New asset only, no frozen pharma-module imports | Package isolation and Git diff review |

## Company intelligence baseline: 0.1.45

ENRICHMENT_V045_GUIDE.md records recursive previous-memory annexes, source-locator
contract problems, shared reference limits, partial preservation and retention/history
boundaries. invocation_recovery_v0_1_41.py permits exact error/cause availability
pairs, not authority failures or uncontrolled repair loops.

| Lesson | Implemented safeguard | Verification |
|---|---|---|
| Optional failure must not erase useful work | Partial stages and surviving independent candidates | Known-availability, malformed-item and refinement tests |
| Wrapped text JSON must keep semantic metadata | Complete wrapper decoding and metadata preservation | Typed result and malformed-business-JSON tests |
| Repeating invoke_agent is not free caching | Single-flight exact task reuse; changed-input invalidation | Concurrent task/cache tests |
| Authority failures are not ordinary outages | Exact error/cause allowlist; unknown failures hard-stop | Authority and unexpected-error tests |
| Source/window identity differs from display locator | Logical IDs and exact UTF-8 digest/span checks | Digest, offset, temporal and alias tests |
| Old memory is not fresh evidence | Historical memory excluded from evidence ledger | Memory provenance test |
| Current memory is not recursive history | Scoped proposals, counterexamples, no-change duplicates | Learning preview and idempotent proposal tests |
| Absent partition is not missing node/permission | Exact not-initialized handling only | First-run negative tests |
| Valid results do not establish durable writes | Apply blocked; persistence not_attested; no resume claim | Preview/retention state tests |

No test double grants live authority. The thirteen source seeds are hypotheses,
not expected supported verdicts. Graph integrity does not prove clinical causality.
The inherited nested toolkit path is deliberately not copied into this child.
