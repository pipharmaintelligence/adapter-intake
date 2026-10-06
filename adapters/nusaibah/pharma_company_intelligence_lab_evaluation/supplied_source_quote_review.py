"""Versioned quote-selection orchestration; deterministic spans come from a callable asset."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import time
from typing import Any

if __package__:
    from . import supplied_source_review as frozen
else:
    import supplied_source_review as frozen

# Reuse immutable source preparation and semantic/accounting primitives.
# No child implementation is imported into this domain adapter.
PURPOSE = frozen.PURPOSE
ROLES = frozen.ROLES
VERIFIER_ROLE = frozen.VERIFIER_ROLE
QUESTIONS = frozen.QUESTIONS
GLOBAL_RULES = frozen.GLOBAL_RULES
MAX_FINDINGS_PER_REQUIREMENT = frozen.MAX_FINDINGS_PER_REQUIREMENT
MAX_EVIDENCE_PER_FINDING = frozen.MAX_EVIDENCE_PER_FINDING
MAX_CONCURRENCY = frozen.MAX_CONCURRENCY
MAX_LOGICAL_CALLS = frozen.MAX_LOGICAL_CALLS
MAX_PACKET_BYTES = frozen.MAX_PACKET_BYTES
MAX_INPUT_BYTES = frozen.MAX_INPUT_BYTES
DEADLINE_SECONDS = frozen.DEADLINE_SECONDS
TOOL_ROLE = "review_toolkit"
TOOL_IDENTITY = "nusaibah.structured_review_toolkit:0.1.1"
MAX_SPAN_REQUESTS = 16
SPAN_REJECTIONS = frozenset({"evidence_quote_missing", "evidence_quote_ambiguous",
                            "evidence_locator_invalid", "evidence_entity_mismatch", "evidence_inaccessible"})
SourceReviewError = frozen.SourceReviewError
digest, _encode = frozen.digest, frozen._encode
_keys, _text, _require = frozen._keys, frozen._text, frozen._require
_extract = frozen._extract
_verifier_contract, _validate_verifier = frozen._verifier_contract, frozen._validate_verifier
METHOD = {**frozen.METHOD, "schema_version": "supplied_source_methodology.v2",
          "evidence_selection": "unique_literal_quote",
          "span_resolver": TOOL_IDENTITY, "span_operation": "resolve_exact_spans"}


def prepare_review(inputs: Any) -> dict[str, Any]:
    review = frozen.prepare_review(inputs)
    plan = {key: value for key, value in review["plan"].items() if key != "plan_digest"}
    plan.update({"schema_version": "supplied_source_plan.v2",
                 "methodology_id": METHOD["schema_version"], "methodology_digest": digest(METHOD),
                 "toolkit_identity": TOOL_IDENTITY, "child_call_limit": len(review["chunks"]),
                 "max_span_requests_per_chunk": MAX_SPAN_REQUESTS})
    return {**review, "plan": {**plan, "plan_digest": digest(plan)}}


def preflight(inputs: Any) -> dict[str, Any]:
    review = prepare_review(inputs)
    return {"schema_version": "supplied_source_preflight.v2", "status": "ready",
            "baseline_comparable": False, "plan": review["plan"],
            "source_unit_count": len(review["inventory"]), "chunk_count": len(review["chunks"]),
            "inaccessible_count": sum(x["disposition"] == "inaccessible" for x in review["inventory"]),
            "excluded_entity_count": sum(x["disposition"] == "excluded_by_entity" for x in review["inventory"])}


def _specialist_contract(review: dict[str, Any], chunk: dict[str, Any], role: str) -> dict[str, Any]:
    contract = frozen._specialist_contract(review, chunk, role)
    contract.pop("offset_semantics")
    contract.update({"schema_version": "supplied_source_specialist.v2",
                     "evidence_fields": ["locator", "quote"],
                     "rules": [*contract["rules"],
                               "Select a unique literal quote within its admitted locator.",
                               "Do not return character offsets. Trusted code resolves exact spans."]})
    return contract


def _quote_requests(value: dict[str, Any], review: dict[str, Any],
                    chunk: dict[str, Any], role: str) -> list[dict[str, Any]]:
    kw = {"stage": "source_review_findings", "role": role}
    contract = _specialist_contract(review, chunk, role)
    _keys(value, set(contract["required_fields"]), "specialist_fields_invalid", **kw)
    for key in ("schema_version", "entity_id", "snapshot_id", "chunk_id", "role", "status"):
        _require(type(value[key]) is type(contract[key]) and value[key] == contract[key],
                 "specialist_identity_invalid", **kw)
    requirements = value["requirements"]
    _require(isinstance(requirements, list) and len(requirements) == len(ROLES[role]),
             "requirement_coverage_invalid", **kw)
    index = {u["locator"]: u for u in chunk["units"]}
    requests = []
    for expected, req in zip(ROLES[role], requirements):
        _keys(req, {"requirement_id", "disposition", "findings"}, "requirement_fields_invalid", **kw)
        _require(req["requirement_id"] == expected and req["disposition"] in ("findings", "no_evidence"),
                 "requirement_identity_invalid", **kw)
        findings = req["findings"]
        _require(isinstance(findings, list) and len(findings) <= MAX_FINDINGS_PER_REQUIREMENT
                 and bool(findings) == (req["disposition"] == "findings"), "finding_count_invalid", **kw)
        for ordinal, finding in enumerate(findings):
            _keys(finding, {"statement", "evidence"}, "finding_fields_invalid", **kw)
            _require(_text(finding["statement"], 600), "finding_statement_invalid", **kw)
            refs = finding["evidence"]
            _require(isinstance(refs, list) and 1 <= len(refs) <= MAX_EVIDENCE_PER_FINDING,
                     "evidence_count_invalid", **kw)
            seen = set()
            for ref_index, ref in enumerate(refs):
                _keys(ref, {"locator", "quote"}, "evidence_fields_invalid", **kw)
                locator, quote = ref["locator"], ref["quote"]
                _require(isinstance(locator, str) and locator in index, "evidence_locator_invalid", **kw)
                _require(_text(quote, 600), "evidence_quote_invalid", **kw)
                _require((locator, quote) not in seen, "evidence_duplicate", **kw)
                seen.add((locator, quote))
                requests.append({"request_id": f"{role}:{expected}:{ordinal}:{ref_index}",
                                 "locator": locator, "quote": quote})
    return requests


def _span_request(review: dict[str, Any], chunk: dict[str, Any],
                  requests: list[dict[str, Any]]) -> dict[str, Any]:
    material = {"entity_id": review["entity_id"], "snapshot_id": review["snapshot_id"],
                "source_units": [{key: unit[key] for key in ("locator", "entity_id", "text", "accessible")}
                                 for unit in chunk["units"]]}
    return {"schema_version": "review_tool_request.v1", "operation": "resolve_exact_spans",
            "arguments": {**material, "source_digest": digest(material).removeprefix("sha256:"),
                          "requests": requests}}


def _validate_span_result(result: Any, request: dict[str, Any]) -> list[dict[str, Any]]:
    kw = {"stage": "source_review_span_resolution", "role": TOOL_ROLE}
    _keys(result, {"schema_version", "toolkit_version", "operation", "request_digest",
                   "validation_scope", "agent_call_count", "mutable_call_count", "output"},
          "span_result_fields_invalid", **kw)
    _require(result["schema_version"] == "review_tool_result.v1"
             and result["toolkit_version"] == "0.1.1" and result["operation"] == "resolve_exact_spans"
             and result["request_digest"] == digest(request).removeprefix("sha256:")
             and result["validation_scope"] == "structural_and_supplied_verdict_only"
             and type(result["agent_call_count"]) is int and result["agent_call_count"] == 0
             and type(result["mutable_call_count"]) is int and result["mutable_call_count"] == 0,
             "span_result_binding_invalid", **kw)
    output, args = result["output"], request["arguments"]
    _keys(output, {"entity_id", "snapshot_id", "source_digest", "spans", "semantic_authority_verified",
                   "status", "reason_code", "rejected_request_index"},
          "span_output_fields_invalid", **kw)
    _require(all(output[key] == args[key] for key in ("entity_id", "snapshot_id", "source_digest"))
             and output["semantic_authority_verified"] is False, "span_source_binding_invalid", **kw)
    if output["status"] == "rejected":
        rejected_index = output["rejected_request_index"]
        _require(output["spans"] == [] and isinstance(output["reason_code"], str)
                 and output["reason_code"] in SPAN_REJECTIONS
                 and type(rejected_index) is int and 0 <= rejected_index < len(args["requests"]),
                 "span_rejection_invalid", **kw)
        # The caller generated these IDs from fixed role/requirement ordering.
        role = args["requests"][rejected_index]["request_id"].split(":", 1)[0]
        raise SourceReviewError(output["reason_code"], **{**kw, "role": role if role in ROLES else TOOL_ROLE})
    _require(output["status"] == "resolved" and output["reason_code"] is None
             and output["rejected_request_index"] is None,
             "span_resolution_status_invalid", **kw)
    spans = output["spans"]
    _require(isinstance(spans, list) and len(spans) == len(args["requests"]) <= MAX_SPAN_REQUESTS,
             "span_result_count_invalid", **kw)
    index = {unit["locator"]: unit for unit in args["source_units"]}
    for span, expected in zip(spans, args["requests"]):
        _keys(span, {"request_id", "locator", "start", "end", "quote"}, "span_fields_invalid", **kw)
        _require(all(span[key] == expected[key] for key in ("request_id", "locator", "quote")),
                 "span_request_binding_invalid", **kw)
        unit = index[expected["locator"]]
        _require(unit["entity_id"] == args["entity_id"] and unit["accessible"] is True,
                 "span_source_not_admitted", **kw)
        start, end, quote, text = span["start"], span["end"], span["quote"], unit["text"]
        _require(type(start) is int and type(end) is int, "evidence_span_type_invalid", **kw)
        _require(0 <= start < end <= len(text), "evidence_span_range_invalid", **kw)
        _require(_text(quote, 600), "evidence_quote_invalid", **kw)
        _require(text[start:end] == quote, "evidence_quote_mismatch", **kw)
        first = text.find(quote)
        _require(first == start and text.find(quote, first + 1) < 0, "evidence_quote_ambiguous", **kw)
    return spans


def _canonical_specialist(value: dict[str, Any], spans: dict[str, dict[str, Any]],
                          role: str) -> dict[str, Any]:
    canonical = json.loads(_encode(value))
    canonical["schema_version"] = "supplied_source_specialist.v1"
    for req in canonical["requirements"]:
        for ordinal, finding in enumerate(req["findings"]):
            for ref_index, ref in enumerate(finding["evidence"]):
                span = spans[f"{role}:{req['requirement_id']}:{ordinal}:{ref_index}"]
                ref.update({"start": span["start"], "end": span["end"]})
    return canonical


def _verification_material(finding: dict[str, Any], chunk: dict[str, Any]) -> dict[str, Any]:
    return {"finding": finding, "source_units": chunk["units"], "methodology_digest": digest(METHOD)}


def validate_resolution_receipts(result: dict[str, Any], review: dict[str, Any]) -> None:
    """Offline check after canonical finding/coverage validation; never invokes a helper."""
    kw = {"stage": "source_review_span_resolution", "role": TOOL_ROLE}
    receipts = result.get("span_resolution_receipts")
    _require(isinstance(receipts, list) and len(receipts) == len(review["chunks"]),
             "span_receipt_count_invalid", **kw)
    _require(type(result.get("child_call_count")) is int
             and result["child_call_count"] == len(receipts) <= review["plan"]["child_call_limit"]
             and result.get("toolkit_identity") == TOOL_IDENTITY, "span_call_accounting_invalid", **kw)
    rows = {(row["chunk_id"], row["role"], row["requirement_id"]): row for row in result["coverage"]}
    accepted = {(f["chunk_id"], f["role"], f["requirement_id"], f["ordinal"]): f
                for f in result["accepted_findings"]}
    for receipt, chunk in zip(receipts, review["chunks"]):
        _keys(receipt, {"chunk_id", "result"}, "span_receipt_fields_invalid", **kw)
        _require(receipt["chunk_id"] == chunk["chunk_id"], "span_receipt_chunk_invalid", **kw)
        tool_result = receipt["result"]
        _require(isinstance(tool_result, dict) and isinstance(tool_result.get("output"), dict)
                 and isinstance(tool_result["output"].get("spans"), list),
                 "span_receipt_shape_invalid", **kw)
        spans = tool_result["output"]["spans"]
        _require(len(spans) <= MAX_SPAN_REQUESTS, "span_result_count_invalid", **kw)
        requests = []
        for span in spans:
            _keys(span, {"request_id", "locator", "start", "end", "quote"}, "span_fields_invalid", **kw)
            _require(isinstance(span["request_id"], str), "span_request_binding_invalid", **kw)
            requests.append({key: span[key] for key in ("request_id", "locator", "quote")})
        ids = [item["request_id"] for item in requests]
        _require(len(set(ids)) == len(ids), "span_request_binding_invalid", **kw)
        by_id = {span["request_id"]: span for span in spans}
        expected_ids = []
        for role, requirements in ROLES.items():
            for requirement in requirements:
                row = rows[(chunk["chunk_id"], role, requirement)]
                for ordinal in range(len(row["finding_ids"])):
                    for ref_index in range(MAX_EVIDENCE_PER_FINDING):
                        request_id = f"{role}:{requirement}:{ordinal}:{ref_index}"
                        _require(ref_index != 0 or request_id in by_id,
                                 "span_finding_accounting_invalid", **kw)
                        if request_id not in by_id:
                            break
                        expected_ids.append(request_id)
                    finding = accepted.get((chunk["chunk_id"], role, requirement, ordinal))
                    if finding:
                        expected = [{key: by_id[f"{role}:{requirement}:{ordinal}:{i}"][key]
                                     for key in ("locator", "start", "end", "quote")}
                                    for i in range(len(finding["evidence"]))
                                    if f"{role}:{requirement}:{ordinal}:{i}" in by_id]
                        _require(finding["evidence"] == expected, "span_finding_binding_invalid", **kw)
                        _require(len([i for i in expected_ids if i.startswith(
                            f"{role}:{requirement}:{ordinal}:")]) == len(finding["evidence"]),
                            "span_finding_accounting_invalid", **kw)
        _require(ids == expected_ids, "span_finding_accounting_invalid", **kw)
        request = _span_request(review, chunk, requests)
        _require(all(isinstance(item["locator"], str)
                     and item["locator"] in {unit["locator"] for unit in chunk["units"]}
                     for item in requests), "span_source_not_admitted", **kw)
        _validate_span_result(tool_result, request)


def run_review(inputs: Any, *, clock: Any = time.monotonic) -> dict[str, Any]:
    review = prepare_review(inputs)
    invoker = getattr(inputs, "invoke_agent", None)
    _require(callable(invoker), "trusted_agent_helper_required")
    child_invoker = getattr(inputs, "invoke_asset", None)
    _require(callable(child_invoker), "trusted_callable_helper_required")
    started = clock()
    call_count = child_count = 0
    span_receipts = []

    def check_deadline() -> None:
        _require(clock() - started < DEADLINE_SECONDS, "deadline_exceeded",
                 stage="source_review_execution", role=VERIFIER_ROLE)

    def charge_agent() -> None:
        nonlocal call_count
        check_deadline()
        _require(call_count < review["plan"]["logical_call_limit"], "call_limit_exceeded",
                 stage="source_review_execution", role=VERIFIER_ROLE)
        call_count += 1

    def invoke(role: str, packet: dict[str, Any]) -> dict[str, Any]:
        check_deadline()
        _require(len(_encode(packet)) <= MAX_PACKET_BYTES, "packet_size_exceeded",
                 stage="source_review_execution", role=role)
        # No adapter retry/repair loop. The trusted runtime admits each call.
        envelope = invoker(role, input=packet, on_error="raise")
        check_deadline()
        return json.loads(_encode(_extract(envelope, role)))

    all_findings, ledger = [], []
    for chunk in review["chunks"]:
        check_deadline()
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY, thread_name_prefix="source-review") as pool:
            futures = {}
            for role in ROLES:
                packet = {
                    "task_stage": "specialist_review", "entity_id": review["entity_id"],
                    "entity_name": review["entity_name"], "methodology_id": METHOD["schema_version"],
                    "methodology_digest": digest(METHOD), "global_rules": list(GLOBAL_RULES),
                    "requirements": {r: QUESTIONS[r] for r in ROLES[role]},
                    "source_chunk": chunk, "response_contract": _specialist_contract(review, chunk, role),
                }
                charge_agent()
                futures[role] = pool.submit(invoke, role, packet)
            # Validate every quote-selection proposal before any child/verifier call.
            values, requests = {}, []
            for role in ROLES:
                values[role] = futures[role].result()
                requests.extend(_quote_requests(values[role], review, chunk, role))
        check_deadline()
        _require(len(requests) <= MAX_SPAN_REQUESTS, "span_request_limit_exceeded",
                 stage="source_review_span_resolution", role=TOOL_ROLE)
        _require(child_count < review["plan"]["child_call_limit"], "child_call_limit_exceeded",
                 stage="source_review_execution", role=TOOL_ROLE)
        request = _span_request(review, chunk, requests)
        _require(len(_encode(request)) <= MAX_PACKET_BYTES, "span_request_size_exceeded",
                 stage="source_review_span_resolution", role=TOOL_ROLE)
        child_count += 1
        response = child_invoker(TOOL_ROLE, variables=json.loads(_encode(request)), on_error="raise")
        check_deadline()
        _require(isinstance(response, dict) and response.get("status") == "success",
                 "span_tool_not_completed", stage="source_review_span_resolution", role=TOOL_ROLE)
        try:
            encoded_result = _encode(response.get("result"))
        except (TypeError, ValueError, UnicodeError) as exc:
            raise SourceReviewError("span_result_encoding_invalid",
                stage="source_review_span_resolution", role=TOOL_ROLE) from exc
        _require(len(encoded_result) <= 262144, "span_result_size_exceeded",
                 stage="source_review_span_resolution", role=TOOL_ROLE)
        tool_result = json.loads(encoded_result)
        spans = _validate_span_result(tool_result, request)
        span_receipts.append({"chunk_id": chunk["chunk_id"], "result": tool_result})
        by_request = {span["request_id"]: span for span in spans}
        chunk_findings, chunk_coverage = [], []
        for role in ROLES:
            canonical = _canonical_specialist(values[role], by_request, role)
            findings, coverage = frozen._validate_specialist(canonical, review, chunk, role)
            chunk_findings.extend(findings)
            chunk_coverage.extend(coverage)
        candidates = [{"finding": f, "input_digest": digest(_verification_material(f, chunk))}
                      for f in chunk_findings]
        contract = _verifier_contract(review, chunk["chunk_id"], candidates, chunk_coverage)
        charge_agent()
        value = invoke(VERIFIER_ROLE, {
            "task_stage": "chunk_evidence_verification", "entity_id": review["entity_id"],
            "entity_name": review["entity_name"], "global_rules": list(GLOBAL_RULES),
            "requirements": QUESTIONS, "source_chunk": chunk, "candidates": candidates,
            "obligations": chunk_coverage, "response_contract": contract,
        })
        verdicts, verification_coverage = _validate_verifier(value, contract)
        by_id = {v["finding_id"]: v for v in verdicts}
        for finding in chunk_findings:
            all_findings.append({**finding, "verification": by_id[finding["finding_id"]]})
        for entry, checked in zip(chunk_coverage, verification_coverage):
            ledger.append({**entry, "reviewed": checked["reviewed"],
                           "unrepresented_evidence": checked["unrepresented_evidence"]})

    # Global consistency sees compact, locally supported claims only. It cannot
    # supply missing evidence or promote any withheld local finding.
    incomplete_chunk_ids = {
        entry["chunk_id"] for entry in ledger
        if not entry["reviewed"] or entry["unrepresented_evidence"]
    }
    global_candidates = []
    for finding in all_findings:
        if (finding["verification"]["state"] == "supported"
                and finding["chunk_id"] not in incomplete_chunk_ids):
            compact = {key: finding[key] for key in (
                "finding_id", "entity_id", "snapshot_id", "chunk_id", "role",
                "requirement_id", "statement",
            )}
            global_candidates.append({"finding": compact, "input_digest": digest(finding)})
    global_by_id = {}
    if global_candidates:
        global_contract = _verifier_contract(review, "global", global_candidates, [])
        charge_agent()
        global_value = invoke(VERIFIER_ROLE, {
            "task_stage": "global_consistency", "entity_id": review["entity_id"],
            "entity_name": review["entity_name"], "global_rules": list(GLOBAL_RULES),
            "candidates": global_candidates, "response_contract": global_contract,
            "rules": ["Local evidence verification has already completed.",
                      "Judge cross-claim consistency, not independent factual truth.",
                      "Mark conflicting claims contradicted; uncertainty insufficient.",
                      "You cannot introduce, rewrite or promote any claim."],
        })
        global_verdicts, _ = _validate_verifier(global_value, global_contract)
        global_by_id = {v["finding_id"]: v for v in global_verdicts}
    _require(call_count <= review["plan"]["logical_call_limit"] <= MAX_LOGICAL_CALLS,
             "call_limit_exceeded", stage="source_review_execution", role=VERIFIER_ROLE)
    accepted, withheld = [], []
    for finding in all_findings:
        first = finding["verification"]
        final = global_by_id.get(finding["finding_id"])
        if (finding["chunk_id"] not in incomplete_chunk_ids
                and first["state"] == "supported" and final and final["state"] == "supported"):
            accepted.append({**finding, "global_verification": final,
                             "provenance_strength": "inspected_supplied_span",
                             "external_truth_verified": False})
        else:
            state = ("unreviewed_context" if finding["chunk_id"] in incomplete_chunk_ids else
                     first["state"] if first["state"] != "supported" else final["state"])
            withheld.append({"finding_id": finding["finding_id"], "chunk_id": finding["chunk_id"],
                             "role": finding["role"], "requirement_id": finding["requirement_id"],
                             "state": state})
    accepted_ids = {f["finding_id"] for f in accepted}
    for entry in ledger:
        entry["accepted_finding_ids"] = [fid for fid in entry["finding_ids"] if fid in accepted_ids]
        entry["evidence_state"] = ("supported" if entry["accepted_finding_ids"] else "insufficient")
    incomplete = (any(x["disposition"] == "inaccessible" for x in review["inventory"])
                  or any(not x["reviewed"] or x["unrepresented_evidence"] for x in ledger))
    has_gaps = bool(withheld) or any(x["evidence_state"] != "supported" for x in ledger)
    outcome = ("review_incomplete" if incomplete else
               "review_complete_with_evidence_gaps" if has_gaps else "review_complete")
    inventory = [dict(item) for item in review["inventory"]]
    for item in inventory:
        if item["disposition"] == "assigned":
            obligations = [x for x in ledger if x["chunk_id"] == item["chunk_id"]]
            item["disposition"] = ("reviewed" if all(x["reviewed"] and not x["unrepresented_evidence"]
                                                     for x in obligations) else "unreviewed")
    return {
        "schema_version": "supplied_source_review_result.v2", "case_id": review["case_id"],
        "entity_id": review["entity_id"], "snapshot_id": review["snapshot_id"],
        "execution_state": "completed", "review_outcome": outcome,
        "scope": "focused_company_review", "synthetic": True, "preview_only": True,
        "baseline_comparable": False, "external_truth_verified": False,
        "publication_allowed": False,
        "plan": review["plan"], "source_inventory": inventory, "coverage": ledger,
        "accepted_findings": accepted, "withheld_findings": withheld,
        "agent_call_count": call_count, "mutable_call_count": 0,
        "child_call_count": child_count, "toolkit_identity": TOOL_IDENTITY,
        "span_resolution_receipts": span_receipts,
        "limitations": ["Evidence is support within supplied text, not independent public verification.",
                        "Semantic verification is model-assessed and requires domain quality evaluation.",
                        "Focused synthetic company review does not establish full document coverage or WP1 baseline scores."],
    }
