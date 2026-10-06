# Reusable review tools developer guide

## Ownership and composition

Generic deterministic utilities live in this source intake. Domain assets keep methodology identity/requirements, schemas and source scope. Core owns credentials/admission/source authority; Assets owns execution, deadlines, cancellation, invocation receipts and packaging. A review utility is not a scheduler or storage backend.

Stable invocation shape:

```python
request = {
    "schema_version": "review_tool_request.v1",
    "operation": "assemble_preview",
    "arguments": {
        "source": source_snapshot_input,
        "policy": {"max_chars": 6000, "neighbor_units": 0},
        "source_hash": prepared_source_hash,
        "methodology": {"ref": "your.review-method", "version": "1.0.0",
                        "requirements": ["your.requirement"]},
        "evidence": exact_spans,
        "findings": domain_findings,
        "semantic_verdicts": supplied_verdicts,
        "result": coverage_result,
    },
}
result = inputs.invoke_asset("review_toolkit", variables=request, on_error="raise")
```

Every operation uses exactly `schema_version`, `operation`, and an `arguments` object. Unknown operations, fields, authority material, non-finite JSON numbers, or oversized requests/results fail without truncation. Result envelopes contain a canonical request digest, toolkit version, operation, validation scope, zero Agent/mutable counters and `output`.

| Operation | Exact argument fields | Output |
| --- | --- | --- |
| `prepare_sources` | `source`, `policy` | Inventory, chunks, inaccessible IDs |
| `prepare_packet` | `entity_id`, `role`, `requirement_ids`, `allowed_section_ids`, `global_rules`, `domain_rules`, `memory_records`, `evidence_refs`, `selected_memory_ids`, `omitted_context_reasons` | Selected role packet |
| `verify_findings` | `source`, `policy`, `source_hash`, `methodology`, `evidence`, `findings`, `semantic_verdicts` | Checked findings and methodology/source digests |
| `check_coverage` | `source`, `policy`, `source_hash`, `methodology`, `result` | Coverage result and gap/count summary |
| `reconcile_findings` | Same fields as `verify_findings` | Checked findings plus conflict ledger |
| `assemble_preview` | Same fields as `verify_findings`, plus `result` | Exact accepted statements, withheld IDs, coverage and conflict ledger |

`source` contains `entity_id`, `source_id`, `source_version`, `extraction_version` and `units`. `policy` contains strict integer `max_chars` (1-6000) and `neighbor_units` (0-4). `methodology` contains `ref`, `version` and unique `requirements`. These fields identify inputs; they do not authorize source access or a Fixed Skill.

For packets, `global_rules` has exactly `entity_isolation`, `evidence_attribution`, `uncertainty` and `mutation_prohibition`, each with nonempty text. Memory records contain exactly `memory_id`, `entity_id` and `text`; every record must belong to the active entity, including unselected records. Rules/reasons are lists, not strings iterated into characters. The packet has a 16,384-byte cap and records why context was omitted.

Preparation takes source identity, extraction version and original structural units. Preserve original Unicode text: offsets are Python character indices, not byte/UTF-16 indices. Each unit has a unique locator, original text, optional quality flags and structural relationships. Table rows must explicitly reference required headers/footnotes. Cycles are bounded by the finite unit set; inaccessible required context blocks.

Evidence records contain exactly `ref`, `entity_id`, `source_hash`, `locator`, `start`, `end` and `quote`. Verification checks those against a recomputed inventory, not a caller-asserted evidence strength. Context-only or inaccessible units cannot become primary evidence.

Findings use the `review_finding.v1` structural schema. Supplied verdicts use `review_semantic_verdict.v1` and must bind to the exact finding/evidence digest via `finding_semantic_input_digest`. An ID-only verdict or reused digest is rejected. Supplying a correct digest is not authenticated semantic authority.

Coverage uses `review_result.v1` / `review_coverage.v1`. Every admitted source/requirement appears exactly once. Missing, duplicate, extra or excluded admitted obligations fail. Inaccessible units cannot be reported reviewed. Complete outcomes cannot conceal unreviewed items, gaps or blocking contradictions.

Accepted findings cannot cite unreviewed or not-applicable obligations. A withheld finding for a requirement must remain an explicit evidence gap even when another finding for that requirement is accepted. Positive supplied verdicts cannot upgrade non-positive finding states. Execution and review terminal states must agree in both directions.

`assemble_preview` rechecks evidence, coverage and reconciliation; callers cannot provide an already-accepted finding list to bypass gates. It renders exact accepted statements rather than generating new final prose. Production synthesis/semantic admission remains a separate reviewed integration.

## Adding another asset

1. Declare an exact `callable_assets.review_toolkit` target, currently `nusaibah.structured_review_toolkit:0.1.0`, result key `tool_result` and object result shape.
2. Keep domain methodology and requirements in the consumer's reviewed configuration. Do not introduce asset identity dispatch into the toolkit.
3. Obtain source inputs through approved fixture/dummy contracts initially. Real lake/file authority requires its own review; a variables dictionary is not a governed-source grant.
4. Validate the consumer's expected entity scope and call the tool through the runtime bridge.
5. Preserve result validation scope and false authority/publication flags. Do not convert a structurally complete fixture to a factual-quality pass.
6. Pin the promoted target and helper hashes in the runtime catalog. Include the callable child in the actual installed bundle.
7. Prove both valid execution and wrong-scope/unavailable-tool/invalid-data failures before live use.

Compatible new domains can reuse the same toolkit version. Behavior/schema changes require a reviewed new version and compatibility proof. No automatic `latest` selection or arbitrary entrypoint invocation is supported.

## Count and loop policy

There are six toolkit operations, independent of the number of registered assets. Each demo executes one deterministic `assemble_preview` child; its internal finite checks do not invoke more assets or Agents.

The current direct callable builder defaults to eight uncached child executions and admits 1-256. This is an implementation ceiling, not a workload recommendation. Start with the smallest admitted plan; this proof uses one. The development proof constructs that plan locally; the consumer manifest alone does not set Core's live run budget. Any future parent loop needs explicit iteration/deadline bounds even when repeated calls hit the cache.

The current Agent semantic-tool loop permits at most three calls per provider step and at most 8,000 serialized result characters. Those limits do not apply as a universal catalog size limit or a whole-review Agent-call budget. Do not route a full source inventory back to a model when it exceeds that interface.

Keep transport attempts, logical Agent calls, deterministic child executions, provider turns and iterations separate. The runtime owns their enforcement. The toolkit cannot reset parent counters, authorize retries or create another queue. The direct callable V1 path is a leaf path; wrapping an entire Agent orchestration inside this tool is unsupported.

## Tests

From the adapter-intake repository root, with the development runtime installed:

```powershell
$Python = "E:\nusaibah_projects\demo_asset_project\.venv\Scripts\python.exe"
& $Python -m unittest discover -s tests -p "test_structured_review_toolkit.py" -v
& $Python -m unittest discover -s tests -p "test_adapter_intake_contract.py" -v
```

CI supplies the existing Adapter stub for stdlib-only deterministic tests. Stub invocation proves contracts, not worker availability.

Run the independent no-provider worker proof with `pi-obs-python-runtime >= 0.1.103` installed:

```powershell
& $Python tests\prove_review_toolkit_worker.py --report "$env:TEMP\review-toolkit-worker-proof.json"
```

No env file is loaded. The proof materializes only declared adapter/helper/manifest files through the official promotion planner, builds a catalog with exactly three identities, executes both synthetic domains through signed local-worker requests and actual isolated callable subprocesses, and verifies response signatures. It uses a fresh temporary test identity/secret, not live Core admission.

The same proof rejects missing callable authority, a modified source digest, the wrong consumer domain, an unavailable role and a modified reviewed helper. A real runtime session separately proves that cached results cannot be mutated through returned copies and a second uncached call exceeds the one-child budget. That session probe uses runtime-private APIs only in the integration test, not business adapters; review it when the runtime changes.

It reports the shared child hash, zero Agent/mutable calls, signed-response checks and explicit `live_admission_proven=false` / `semantic_quality_measured=false`. It is not a paid/provider run, deployment, wheel installation or S3 retention proof.

## Promotion and release order

Review and merge source changes, then use official intake promotion/materialization for the toolkit and required consumers. Review the resulting Assets promotion PR, package the runtime/bundle, verify catalog identities and module/helper hashes, and admit only the required parent/child contracts.

Generic source utilities belong in this intake; packaged copies belong to the Assets promotion output. Core changes are only necessary when live capability admission or plan controls need a separately reviewed adjustment. Existing provider transport code and pharma adapters are not modified by this package.

Do not install a wheel built from unmerged local edits into the running worker or mix helper revisions. Registration, consumer binding and live positive/negative proof remain separate. No new environment variables are introduced by these source assets.

If a case blocks, inspect its bounded input and the stable toolkit error class, preserve the original source/result bytes and fix the first invalid boundary. Do not drop source units, loosen gates or relaunch the same provider smoke merely to obtain completion.

## WP alignment

This change extracts and proves reuse of deterministic reference components. It leaves the historical pharma baseline, PR80 scoring, fixture truth and all WP readiness gates unchanged. WP1 scope/comparability and independent measurements, domain-specialist integration, generic runtime lifecycle proof, held-out admission and production operator states remain required.

The next generalization layer can reuse these operations for admitted specialist packets and authenticated semantic outputs. It must preserve the same authority and result-boundary distinctions.
