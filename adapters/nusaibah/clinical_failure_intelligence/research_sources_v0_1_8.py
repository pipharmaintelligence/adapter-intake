"""Provider-grounded discovery leads become evidence only after trusted HTTP inspection.

This is deterministic adapter orchestration. Agent/provider grounding and public
HTTPS retrieval remain owned by the signed Assets/Core runtime; no direct I/O or
model-authored URL is treated as evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit
from typing import Any

if __package__:
    from .contracts_v0_1_8 import ContractError, digest, identifier, iso_date, require, text, text_digest
    from .policies_v0_1_8 import Budget, DeferredWork
else:
    from contracts_v0_1_8 import ContractError, digest, identifier, iso_date, require, text, text_digest
    from policies_v0_1_8 import Budget, DeferredWork

DISCOVERY_ROLES = ("trial_researcher", "literature_researcher", "event_researcher")
MAX_REFERENCES_PER_ROLE = 2
MAX_INSPECTED_CHARS = 12000
MAX_QUERY_CHARS = 500


def query_plan(request: dict) -> dict[str, str]:
    """Build three bounded queries from only the resolved case identity."""
    subject = request["context"]["subject"]
    metadata = request["context"].get("source_event_metadata") or {}
    events = metadata.get("events", [])
    sponsors = [row.get("reported_sponsor") for row in events if isinstance(row, dict)]
    sponsor = next((value for value in sponsors if isinstance(value, str) and value.strip()), "")
    name = subject.get("product_name") or subject["product_id"] or ""
    indication = subject.get("indication") or ""
    trial = next((value for value in subject["trial_ids"] if isinstance(value, str)
                  and len(value) == 11 and value.startswith("NCT") and value[3:].isdigit()), "")
    seed = " ".join(value for value in (name, indication, trial) if value).strip()
    require(bool(seed), "clinical_discovery_identity_missing")
    planned = {
        "trial_researcher": f"{seed} clinical trial registry primary outcome status",
        "literature_researcher": f"{seed} PubMed original clinical results mechanism exposure PK PD target engagement biomarkers contrary evidence",
        "event_researcher": f"{seed} {sponsor} sponsor regulator clinical programme announcement",
    }
    return {role: value.strip()[:MAX_QUERY_CHARS] for role, value in planned.items()}


def _provider_citations(metadata: Any) -> tuple:
    """Use the installed SDK's native citation projector, never generated prose URLs."""
    if not isinstance(metadata, Mapping) or metadata.get("schema_version") != "agent_provider_metadata.v1":
        return ()
    try:
        from devtools.agent_citation_view import AgentCitationView, AgentCitationViewError
    except ImportError as exc:
        raise ContractError("clinical_citation_projection_unavailable") from exc
    try:
        return AgentCitationView.from_agent_result({
            "schema_version": "agent_result.v1",
            "provider_metadata": metadata,
        }).deduped_citations()
    except AgentCitationViewError:
        return ()


def _admit_inspected(
    inspection: Any, citation: Any, request: dict,
) -> dict:
    """Build a source window from retrieved text without inventing source assertions."""
    source_text = getattr(inspection, "text", None)
    final_url = getattr(inspection, "final_url", None)
    require(isinstance(source_text, str) and bool(source_text.strip()),
            "clinical_inspected_text_missing")
    require(len(source_text) <= MAX_INSPECTED_CHARS, "clinical_source_window_requires_partitioning")
    require(isinstance(final_url, str) and bool(final_url), "clinical_inspected_locator_missing")
    host = urlsplit(final_url).hostname
    require(isinstance(host, str) and bool(host), "clinical_inspected_locator_invalid")
    metadata = getattr(inspection, "metadata", {})
    published = metadata.get("published_on") if isinstance(metadata, Mapping) else None
    if published is not None:
        require(iso_date(published) <= request["as_of_date"], "clinical_evidence_temporal_leak")
    subjects = request["context"]["subject"]
    known_trial = next((item for item in subjects["trial_ids"] if isinstance(item, str)
                        and item.startswith("NCT") and len(item) == 11 and item[3:].isdigit()), None)
    matching_trial = known_trial is not None and known_trial.casefold() in (final_url + " " + source_text).casefold()
    product_name = subjects.get("product_name")
    matching_product = bool(isinstance(product_name, str) and product_name.strip()
                            and product_name.casefold() in source_text.casefold())
    # The same citation is not proof that its content describes the selected case.
    require(matching_trial or matching_product, "clinical_inspected_case_scope_unverified")
    if host in {"clinicaltrials.gov", "www.clinicaltrials.gov"}:
        require(matching_trial, "clinical_inspected_trial_identity_unverified")
        source_type, extent = "trial_registry", "registry_record"
    elif host in {"pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov"}:
        # An index entry is not automatically a verified original clinical trial.
        source_type, extent = "publication", "abstract" if host.startswith("pubmed.") else "excerpt"
    else:
        # Sponsor/news/regulator authority requires a separate semantic adjudication.
        source_type, extent = "news", "excerpt"
    checksum = text_digest(source_text)
    source_key = digest({"final_url": final_url})
    identity = digest({"final_url": final_url, "text_digest": checksum})
    title = getattr(inspection, "title", None) or getattr(citation, "title", None)
    return {
        "evidence_id": "WEB_" + identity.split(":", 1)[1][:24],
        "source_id": "web:" + source_key.split(":", 1)[1][:24],
        "subject_id": request["subject_id"],
        "source_type": source_type,
        "source_version": checksum,
        "published_on": published,
        "accessible_extent": extent,
        "text": source_text,
        "trial_ids": [known_trial] if matching_trial else [],
        "reference": final_url,
        "title": title if isinstance(title, str) and title.strip() else None,
        "declared_text_digest": checksum,
    }


def acquire_sources(inputs: Any, request: dict, runner: Any, budget: Budget, ledger: Any,
                    stages: list, *, roles: list[str] | None = None) -> list[dict]:
    """Discover source leads, inspect a bounded set, and admit only inspected windows.

    Each failure is an explicit unresolved obligation; no citation or snippet is
    promoted directly to clinical evidence and no unadmitted public URL is opened.
    """
    issues: list[dict] = []
    if not callable(getattr(inputs, "open_reference", None)):
        return [{"code": "clinical_reference_capability_unavailable"}]
    queries = query_plan(request)
    seen: set[str] = set()
    selected_roles = list(DISCOVERY_ROLES) if roles is None else roles
    require(all(role in DISCOVERY_ROLES for role in selected_roles)
            and len(set(selected_roles)) == len(selected_roles), "clinical_discovery_roles_invalid")
    for role in selected_roles:
        try:
            budget.reserve_search(role)
        except DeferredWork as exc:
            issues.append({'code':exc.code})
            continue
        stage = runner.call(role, request, task_id="discovery:" + role,
            obligations=["discovery:" + role], downstream_reserve=5,
            packet_data={
                "evidence_packet": [],
                "research_phase": "source_discovery",
                "search_queries": [queries[role]],
                "source_admission_rule": (
                    "Use server-admitted provider grounding. Return items=[] and "
                    "followup_requests=[]; source citations must be provider-native. "
                    "Do not invent URLs or treat search snippets as clinical evidence."
                ),
            })
        stages.append(stage)
        if stage.status != "completed" or stage.payload is None:
            issues.append({"stage_id": stage.task_id,
                           "code": stage.code or "clinical_discovery_incomplete"})
            continue
        if stage.payload["items"] or stage.payload["followup_requests"]:
            issues.append({"stage_id": stage.task_id,
                           "code": "clinical_discovery_unadmitted_claims_rejected"})
        issues.extend(inspect_stage_sources(inputs, request, budget, ledger, stage, seen=seen))
    return issues


def inspect_stage_sources(inputs, request, budget, ledger, stage, *, seen=None):
    """Inspect native citations from one admitted research task, including reflection."""
    issues=[]
    seen=set() if seen is None else seen
    citations = _provider_citations(stage.semantic_metadata.get("provider_metadata"))
    if not citations:
        issues.append({"stage_id": stage.task_id,
                       "code": "clinical_discovery_no_provider_citations"})
        return issues
    for citation in citations[:MAX_REFERENCES_PER_ROLE]:
        locator = getattr(citation, "locator", None)
        if not isinstance(locator, str) or locator in seen:
            continue
        seen.add(locator)
        try:
            budget.reserve(kind="reference")
        except DeferredWork as exc:
            issues.append({"stage_id": stage.task_id, "code": exc.code})
            return issues
        try:
            from devtools.public_reference import ReferenceTarget, PublicReferenceError
            from devtools.public_web_runtime import PublicWebRuntimeError
        except ImportError as exc:
            raise ContractError("clinical_reference_runtime_unavailable") from exc
        try:
            result = inputs.open_reference(
                ReferenceTarget.from_agent_citation(citation), mode="http"
            )
            evidence = _admit_inspected(result, citation, request)
            ledger.add(evidence)
        except ContractError as exc:
            issues.append({"stage_id": stage.task_id, "code": exc.code})
        except (PublicReferenceError, PublicWebRuntimeError) as exc:
            issues.append({"stage_id": stage.task_id,
                           "code": "clinical_reference_inspection_unavailable"})
        except Exception as exc:
            # Provider/network transport is runtime-owned, not retried in Python.
            raise ContractError("clinical_reference_runtime_blocked") from None
    return issues
