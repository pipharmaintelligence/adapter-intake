"""Versioned role ownership for supplied-source company review (0.2.3)."""
from __future__ import annotations

import copy
import time
from typing import Any

if __package__:
    from . import supplied_source_quote_review as quote
    from .quote_review_orchestration import ReviewContract, run_review as run_quote_review
else:
    import supplied_source_quote_review as quote
    from quote_review_orchestration import ReviewContract, run_review as run_quote_review

PURPOSE, ROLES, VERIFIER_ROLE = quote.PURPOSE, quote.ROLES, quote.VERIFIER_ROLE
TOOL_IDENTITY, TOOL_ROLE = quote.TOOL_IDENTITY, quote.TOOL_ROLE
SourceReviewError, digest = quote.SourceReviewError, quote.digest
GLOBAL_RULES = quote.GLOBAL_RULES
QUESTION_OVERRIDES = {'company_identity': 'What legal-name, headquarters, registered-address, incorporation or '
                     'other company-profile identity facts does this source explicitly state '
                     'about the target company? Location alone does not establish a sales '
                     'market, customer market or distribution territory.',
 'commercial_signals': 'What explicitly stated sales or customer markets, distribution '
                       'territories, commercial launches, revenue, market-access facts, or '
                       'commercialization/licensing partnerships relate to the target company? '
                       'Geography is commercial only when explicitly tied to one of those '
                       'activities. Headquarters, registered addresses, incorporation and '
                       'identity-only location belong to company_identity. If the source '
                       'contains only identity facts, return no_evidence with an empty '
                       'findings list for commercial_signals.'}
QUESTIONS = {**quote.QUESTIONS, **QUESTION_OVERRIDES}
REQUIREMENT_SCOPES = {'company_identity': {'included_fact_types': ['legal_name',
                                              'headquarters',
                                              'registered_address',
                                              'incorporation',
                                              'company_profile_identity'],
                      'excluded_fact_types': ['sales_market',
                                              'customer_market',
                                              'distribution_territory',
                                              'commercialization_partnership',
                                              'licensing',
                                              'market_access',
                                              'commercial_launch',
                                              'revenue'],
                      'rules': ['Report company-profile identity facts in company_identity.',
                                'Do not infer commercial presence from a headquarters or '
                                'registered address.']},
 'commercial_signals': {'included_fact_types': ['sales_market',
                                                'customer_market',
                                                'distribution_territory',
                                                'commercialization_partnership',
                                                'licensing',
                                                'market_access',
                                                'commercial_launch',
                                                'revenue'],
                        'excluded_fact_types': ['legal_name',
                                                'headquarters',
                                                'registered_address',
                                                'incorporation',
                                                'identity_only_geography'],
                        'rules': ['Require an explicit commercial activity, market '
                                  'relationship or commercialization agreement.',
                                  'Headquarters and identity-only geography belong to '
                                  'company_identity.',
                                  'Geography alone is not evidence of commercial presence.',
                                  'A headquarters-only or registered-address-only source '
                                  'requires no_evidence and an empty commercial_signals '
                                  'findings list.',
                                  'A source may support distinct identity and commercial '
                                  'claims using the same literal span; preserve each claim in '
                                  'its owning requirement.']}}
METHOD = {**copy.deepcopy(quote.METHOD), "schema_version": "supplied_source_methodology.v3",
          "questions": QUESTIONS, "requirement_scopes": REQUIREMENT_SCOPES}


def prepare_review(inputs: Any) -> dict[str, Any]:
    review = quote.prepare_review(inputs)
    plan = {key: value for key, value in review["plan"].items() if key != "plan_digest"}
    plan.update({"methodology_id": METHOD["schema_version"], "methodology_digest": digest(METHOD)})
    return {**review, "plan": {**plan, "plan_digest": digest(plan)}}


def preflight(inputs: Any) -> dict[str, Any]:
    review = prepare_review(inputs)
    return {"schema_version": "supplied_source_preflight.v2", "status": "ready",
            "baseline_comparable": False, "plan": review["plan"],
            "source_unit_count": len(review["inventory"]), "chunk_count": len(review["chunks"]),
            "inaccessible_count": sum(x["disposition"] == "inaccessible" for x in review["inventory"]),
            "excluded_entity_count": sum(x["disposition"] == "excluded_by_entity" for x in review["inventory"])}


def _specialist_contract(review: dict[str, Any], chunk: dict[str, Any], role: str) -> dict[str, Any]:
    contract = quote._specialist_contract(review, chunk, role)
    scopes = {rid: copy.deepcopy(REQUIREMENT_SCOPES[rid]) for rid in ROLES[role]
              if rid in REQUIREMENT_SCOPES}
    if scopes:
        contract["requirement_scopes"] = scopes
        contract["rules"] = [*contract["rules"],
                             "Apply the supplied requirement_scopes to each proposed finding.",
                             "An identity-only source has no commercial evidence; return no_evidence with findings []."]
    return contract


def _verifier_contract(review: dict[str, Any], chunk_id: str,
                       candidates: list[dict[str, Any]], obligations: list[dict[str, Any]]) -> dict[str, Any]:
    contract = quote._verifier_contract(review, chunk_id, candidates, obligations)
    contract["requirement_scopes"] = copy.deepcopy(REQUIREMENT_SCOPES)
    contract["coverage_rules"] = [*contract["coverage_rules"],
        "A supported finding must also belong to its assigned requirement under requirement_scopes.",
        "Source-supported headquarters or registered-address facts are insufficient for commercial_signals.",
        "Identity-only geography is not omitted commercial evidence; a reviewed commercial no_evidence disposition is valid.",
        "Distinct identity and commercial claims may share an exact quote; citation equality alone is not duplication."]
    return contract


def _verification_material(finding: dict[str, Any], chunk: dict[str, Any]) -> dict[str, Any]:
    return {"finding": finding, "source_units": chunk["units"], "methodology_digest": digest(METHOD)}


CONTRACT = ReviewContract(METHOD, QUESTIONS, prepare_review, _specialist_contract,
                          _verifier_contract, _verification_material)


def run_review(inputs: Any, *, clock: Any = time.monotonic) -> dict[str, Any]:
    return run_quote_review(inputs, profile=CONTRACT, clock=clock)


validate_resolution_receipts = quote.validate_resolution_receipts
