"""Shared bounded quote orchestration for source-owned, versioned review contracts.

Historical 0.2.2 remains unchanged. New profiles reuse its structural primitives
without changing module globals or allowing inputs to configure execution limits.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import time
from typing import Any, Callable

if __package__:
    from . import supplied_source_quote_review as quote
else:
    import supplied_source_quote_review as quote

frozen = quote.frozen
SourceReviewError = quote.SourceReviewError
digest, _encode, _require, _extract = quote.digest, quote._encode, quote._require, quote._extract
_quote_requests, _span_request = quote._quote_requests, quote._span_request
_validate_span_result, _canonical_specialist = quote._validate_span_result, quote._canonical_specialist
_validate_verifier = quote._validate_verifier
ROLES, VERIFIER_ROLE, GLOBAL_RULES = quote.ROLES, quote.VERIFIER_ROLE, quote.GLOBAL_RULES
MAX_CONCURRENCY, MAX_LOGICAL_CALLS = quote.MAX_CONCURRENCY, quote.MAX_LOGICAL_CALLS
MAX_PACKET_BYTES, MAX_SPAN_REQUESTS = quote.MAX_PACKET_BYTES, quote.MAX_SPAN_REQUESTS
DEADLINE_SECONDS, TOOL_ROLE, TOOL_IDENTITY = quote.DEADLINE_SECONDS, quote.TOOL_ROLE, quote.TOOL_IDENTITY


@dataclass(frozen=True)
class ReviewContract:
    """Trusted source configuration; never loaded from runtime inputs."""
    methodology: dict[str, Any]
    questions: dict[str, str]
    prepare_review: Callable[..., dict[str, Any]]
    specialist_contract: Callable[..., dict[str, Any]]
    verifier_contract: Callable[..., dict[str, Any]]
    verification_material: Callable[..., dict[str, Any]]


def run_review(inputs: Any, *, profile: ReviewContract, clock: Any = time.monotonic) -> dict[str, Any]:
    review = profile.prepare_review(inputs)
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
                    "entity_name": review["entity_name"], "methodology_id": profile.methodology["schema_version"],
                    "methodology_digest": digest(profile.methodology), "global_rules": list(GLOBAL_RULES),
                    "requirements": {r: profile.questions[r] for r in ROLES[role]},
                    "source_chunk": chunk, "response_contract": profile.specialist_contract(review, chunk, role),
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
        candidates = [{"finding": f, "input_digest": digest(profile.verification_material(f, chunk))}
                      for f in chunk_findings]
        contract = profile.verifier_contract(review, chunk["chunk_id"], candidates, chunk_coverage)
        charge_agent()
        value = invoke(VERIFIER_ROLE, {
            "task_stage": "chunk_evidence_verification", "entity_id": review["entity_id"],
            "entity_name": review["entity_name"], "global_rules": list(GLOBAL_RULES),
            "requirements": profile.questions, "source_chunk": chunk, "candidates": candidates,
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
        global_contract = profile.verifier_contract(review, "global", global_candidates, [])
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
