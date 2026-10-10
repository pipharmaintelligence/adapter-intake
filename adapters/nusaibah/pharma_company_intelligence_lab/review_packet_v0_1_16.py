"""Inert, opt-in review evidence. Core owns retention and mutation authority."""
from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

SCHEMA_VERSION = "pharma_prepared_review.v1"
MAX_REVIEW_OUTPUT_BYTES = 512 * 1024


def review_packet_requested(inputs: Any) -> bool:
    value = inputs.get("variables", {}).get("retain_review_packet", False)
    if type(value) is not bool:
        raise ValueError("variables.retain_review_packet must be boolean.")
    return value


def _digest(value: str) -> str:
    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def require_output_bound(value: Any) -> None:
    if len(canonical_bytes(value)) > MAX_REVIEW_OUTPUT_BYTES:
        raise RuntimeError("Prepared review output exceeds its retention bound; no candidate was truncated.")


def _citations(values: Any) -> list[dict[str, Any]]:
    # Public evidence fields only: no runtime handles, credentials or raw envelopes.
    return [{"locator": item.locator, "title": item.title,
             "source_kind": item.source_kind, "provider_family": item.provider_family}
            for item in values]


def _section_proposal(*, role: str, section: str, text: str | None,
                      baseline_text: str, baseline_digest: str | None) -> dict[str, Any]:
    # These are the exact bytes passed to replace_section by the existing apply path.
    replacement = None if text is None else text.rstrip() + "\n"
    return {"role": role, "target_section": section,
            "baseline_content_digest": baseline_digest,
            "baseline_section_text": baseline_text,
            "replacement_text": replacement,
            "replacement_sha256": None if replacement is None else _digest(replacement)}


def build_review_packet(prepared: list[dict[str, Any]], *, asset_identity: str,
                        methodology_digest: str, memory_mode: str) -> dict[str, Any]:
    companies = []
    for state in prepared:
        candidate = state["memory_candidate"]
        memory = _section_proposal(
            role="company_memory", section=candidate.target_section, text=candidate.markdown,
            baseline_text=state["before_target_text"], baseline_digest=state["before_digest"],
        )
        memory["fact_ids"] = list(candidate.fact_ids)
        memory["mutation_eligible"] = state["memory_mutation_eligible"]
        learning = _section_proposal(
            role="company_methodology", section="Methodology Learning",
            text=state["methodology_learning_candidate"],
            baseline_text=state["methodology_learning_before_text"],
            baseline_digest=state["result"]["methodology_learning_before_digest"],
        )
        learning["initialized"] = state["methodology_learning_handle"] is not None
        role_evidence = []
        for role, research in state["research"].items():
            role_evidence.append({"role": role, "sections": research["sections"],
                                  "uncertainties": research["uncertainties"],
                                  "citations": _citations(research["_citations"])})
        companies.append({
            "company_id": state["company_id"], "company_name": state["company_name"],
            "memory_proposal": memory, "methodology_proposal": learning,
            "claims": state["joined_research"]["claims"],
            "evidence_granularity": "research_role; individual claim-to-citation mapping unavailable",
            "research_role_evidence": role_evidence,
            "memory_apply_citations": _citations(state["citations"][:24]),
            "methodology_plan": state["methodology_plan"].to_agent_input(),
            "planner_requirements": list(state["methodology_plan"].requirement_catalog()),
            "planner_chunks": list(state["planner_chunks"]),
            "critic": state["critic"], "strategic": state["strategic"],
            "benchmark": {"questions": list(state["benchmark_questions"]),
                          "before": state["before_benchmark"],
                          "projected": state["projected_after_benchmark"],
                          "basis": "projected_memory_candidate", "committed": None},
            "residual_uncertainties": state["residual_uncertainties"],
        })
    body = {"schema_version": SCHEMA_VERSION, "asset_identity": asset_identity,
            "fixed_methodology_digest": methodology_digest, "memory_mode": memory_mode,
            "preparation_stage": "before_mutation", "review_state": "not_reviewed",
            "apply_authority": False, "companies": companies}
    # The digest identifies this proposal; it is neither a commit receipt nor approval.
    body["packet_sha256"] = "sha256:" + sha256(canonical_bytes(body)).hexdigest()
    require_output_bound(body)
    return json.loads(canonical_bytes(body))
