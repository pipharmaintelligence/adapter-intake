# PI-2061 — governed source node compatibility, development 0.1.1

## Intended source and ownership

The user reports an upload into lake test_database_lake, node clinical_development_events. The expected object is the prior clinical_event_source.v1 JSONL (508 original event rows). This repo neither fetches that object nor supplies credentials. Core retains lake/node/storage authority.

The exact asset identity is python_asset:nusaibah.clinical_failure_intelligence@0.1.1, logical role clinical_context with required source=binding and shape=object. No fallback to source=either/direct. Use the DLM/Assets authoring and readiness workflow to bind this specific node/asset-version/client/role. For an unpartitioned JSONL object, file_object with a Core-approved numeric object ID mapped from source_object_id is a candidate; never substitute event_id for the object ID.

The existing runtime file-input record projection yields {records: [...], provenance: {...}}, with runtime-attested complete, source_ref, access_mode, record_count, sha256. Select a complete json_object /records materializer with max_records at least 508 and adequate max_bytes. Upload acceptance alone does not prove the object format, active object identity, binding readiness or child compatibility. If the actual uploaded object is XLSX, do not relabel it JSONL: inspect/migrate through a governed source workflow before this mapping.

## Selection request

Illustrative variables only, not a live run; source_object_id is a fake placeholder and must be replaced with an approved numeric ID:

    {"schema_version":"clinical_analysis_request.v1",
     "request_id":"CASE_79_913","subject_id":"CASE_79_913",
     "analysis_mode":"mechanistic_case","as_of_date":"2026-10-16",
     "event_ids":["79"],"product_id":"913",
     "indication_id":"3026","trial_id":"NCT03626545",
     "source_object_id":123,"memory_mode":"preview",
     "enable_pharmacological_class":false}

The source object is never passed in callable variables. The invoked child independently resolves its own binding. Existing governed clinical_context.v1 consumers remain compatible.

## Mapping and scientific integrity

- The binding-owned source contains one original record per event. Source event IDs are unique. All nonselected rows are excluded before Agent calls.
- Select product_id explicitly; event-level multi-product associations do not prove which treatment arm or molecule caused a reported failure.
- Multi-indication and multi-NCT fields require explicit matching semantic selectors; do not Cartesian-join them.
- Named studies remain leads, not verified NCT IDs. Missing trial_id stays null and a distinct Event <id> trial unreported memory path is used; regimen stays null with Regimen unreported section.
- Two events may share one analysis when product, indication and trial scope agree; unresolved distinct event-scoped trials are split.
- Input result_text is only an unverified source assertion. No trial-registry, PubMed or regulator evidence is fabricated; returned evidence is empty until approved retrieval supplies actual citations.
- Model research must not turn source-sheet negatives into confirmed primary endpoint failures. Partial output explicitly records independent evidence required.
- Never auto-write Dynamic Skills. Preview only; class analysis stays opt-in and disabled by default.
- Reject missing/duplicate event IDs, out-of-scope selections, future event dates, incomplete provenance, record count mismatch, authority-bearing payloads and oversize input before any Agent or Skill call.
- Source hashes, IDs, association scope, screening labels and unresolved flags remain in source_event_metadata alongside canonical results.

## Binding and release gates

B0 is authored in the exact manifest: role clinical_context is binding-owned and still an object.
B1/B2: verify actual node file type, active Core object id, exact binding mode and selector.
B3-B6: prove selected binding active/ready for the exact client and @0.1.2; no ambiguous binding.
B7: prove Core/Assets materialized complete 508 source rows with file provenance, no direct override.
B8/B9: reconcile requested event/product/indication/trial against returned records and mapper output.
Next: certify independent Agent/tool admissions, Fixed and product Dynamic Skill reads, signed parent-child composition, and only then a retained-analysis barrier plus mutable Skill receipt/readback/history.

Assets V5 callable's earliest implementation emphasized materialized_query. If child file_object input hydration has not been qualified on the exact deployed head, treat it as an Assets runtime gate; do not bypass with a direct parent payload. A top-level approved file-binding test can isolate the source contract before invoking the parent.

## Compatibility proof scope

Provider-free test_source_events plus all prior intake tests. This is not a live DLM binding result, deployed worker, registered Gemini provider, or approved Skill mutation.
