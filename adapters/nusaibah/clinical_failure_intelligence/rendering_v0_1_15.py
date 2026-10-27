"""Deterministic graph and report projections of the same reviewed assertions."""

from __future__ import annotations
import html

if __package__:
    from .contracts_v0_1_15 import SCHEMA, digest, require, safe_json
else:
    from contracts_v0_1_15 import SCHEMA, digest, require, safe_json


def build_reason_graph(
    subject: dict,
    items: list[dict],
    evidence: list[dict],
    *,
    case_scope: dict | None = None,
    terminology: list[dict] | None = None,
) -> dict:
    """Render evidence/hypothesis edges without manufacturing a causal relationship."""
    subject_node = "subject:" + subject["subject_id"]
    nodes = [
        {"id": subject_node, "type": "subject", "reference": subject["subject_id"]}
    ]
    nodes.extend(
        {
            "id": "evidence:" + row["evidence_id"],
            "type": "evidence",
            "reference": row["evidence_id"],
        }
        for row in evidence
    )
    edges = []
    for item in items:
        node = "assertion:" + item["item_id"]
        nodes.append(
            {
                "id": node,
                "type": item["kind"],
                "reference": item["item_id"],
                "accepted": item["accepted"],
                "review_status": item["review_status"],
            }
        )
        edges.append(
            {
                "from": subject_node,
                "to": node,
                "relation": (
                    "HAS_OUTCOME" if item["kind"] == "outcome" else "HAS_HYPOTHESIS"
                ),
                "assertion_id": item["item_id"],
                "status": item["review_status"],
            }
        )
        for key, relation in (
            ("supporting_evidence_ids", "SUPPORTS"),
            ("contradicting_evidence_ids", "CONTRADICTS"),
        ):
            for ref in item[key]:
                edges.append(
                    {
                        "from": "evidence:" + ref,
                        "to": node,
                        "relation": relation,
                        "assertion_id": item["item_id"],
                        "evidence_ids": [ref],
                        "status": (
                            "reviewed_assertion"
                            if item["accepted"]
                            else "candidate_link"
                        ),
                        "scope": item.get(
                            "scope", {"trial_ids": item.get("trial_ids", [])}
                        ),
                    }
                )
        for dependency in item["depends_on"]:
            edges.append(
                {
                    "from": node,
                    "to": "assertion:" + dependency,
                    "relation": "DEPENDS_ON",
                    "assertion_id": item["item_id"],
                    "status": item["review_status"],
                }
            )
    # Identity/source relationships never imply treatment contribution or causality.
    scope = case_scope or {}
    for kind, values in (
        ("product", [subject.get("product_id")]),
        ("trial", subject.get("trial_ids", [])),
        ("indication", [scope.get("indication_id")]),
        ("regimen", [scope.get("regimen_id")]),
    ):
        for reference in values:
            if reference is None:
                continue
            node_id = kind + ":" + reference
            nodes.append({"id": node_id, "type": kind, "reference": reference})
            edges.append(
                {
                    "from": subject_node,
                    "to": node_id,
                    "relation": "SUBJECT_" + kind.upper(),
                    "status": "selected_identity_not_causality",
                }
            )
    source_nodes = set()
    for row in evidence:
        source = "source:" + row["source_id"]
        if source not in source_nodes:
            nodes.append(
                {"id": source, "type": "source", "reference": row["source_id"]}
            )
            source_nodes.add(source)
        edges.append(
            {
                "from": "evidence:" + row["evidence_id"],
                "to": source,
                "relation": "SOURCE_RECORD",
                "status": "source_available",
                "evidence_ids": [row["evidence_id"]],
            }
        )
    terminology_nodes = set()
    for term in terminology or []:
        node_id = (
            "terminology:"
            + digest(
                [term["cui"], term.get("source_vocabulary"), term.get("release")]
            ).split(":")[1][:24]
        )
        if node_id in terminology_nodes:
            continue
        terminology_nodes.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "type": "terminology",
                "reference": term["cui"],
                "mapping_status": "candidate",
                "clinical_equivalence_verified": False,
            }
        )
        edges.append(
            {
                "from": subject_node,
                "to": node_id,
                "relation": "TERM_CANDIDATE_FOR",
                "status": "candidate_link",
            }
        )
    for edge in edges:
        edge["id"] = "edge:" + digest(edge).split(":", 1)[1][:24]
    return {
        "schema_version": "clinical_reason_graph.v1",
        "nodes": sorted(nodes, key=lambda x: x["id"]),
        "edges": sorted(edges, key=lambda x: x["id"]),
    }


def validate_result(result: dict) -> None:
    """Require reference closure and truthful non-writing, non-persistence states."""
    safe_json(result)
    require(result.get("schema_version") == SCHEMA, "clinical_result_schema_invalid")
    items = result["case_assessments"] + result["hypothesis_results"]
    evidence_ids = {row["evidence_id"] for row in result["evidence"]}
    require(
        len(evidence_ids) == len(result["evidence"]),
        "clinical_result_evidence_duplicate",
    )
    item_ids = {item["item_id"] for item in items}
    require(len(item_ids) == len(items), "clinical_result_item_duplicate")
    for item in items:
        require(
            set(item["supporting_evidence_ids"] + item["contradicting_evidence_ids"])
            <= evidence_ids,
            "clinical_result_evidence_dangling",
        )
        require(
            set(item["depends_on"]) <= item_ids, "clinical_result_dependency_dangling"
        )
        if item["kind"] == "hypothesis" and item["verdict"] in {"supported", "refuted"}:
            refs = (
                item["supporting_evidence_ids"]
                if item["verdict"] == "supported"
                else item["contradicting_evidence_ids"]
            )
            require(
                item["accepted"]
                and item["review_status"] == "automated_reviewed"
                and bool(refs),
                "clinical_result_unreviewed_conclusion",
            )
    graph = result["reason_graph"]
    nodes = {node["id"] for node in graph["nodes"]}
    require(len(nodes) == len(graph["nodes"]), "clinical_graph_duplicate")
    require(
        len({edge["id"] for edge in graph["edges"]}) == len(graph["edges"]),
        "clinical_graph_edge_duplicate",
    )
    require(
        all(edge["from"] in nodes and edge["to"] in nodes for edge in graph["edges"]),
        "clinical_graph_dangling",
    )
    require(
        all(
            edge["relation"]
            in {
                "HAS_OUTCOME",
                "HAS_HYPOTHESIS",
                "SUPPORTS",
                "CONTRADICTS",
                "DEPENDS_ON",
                "SUBJECT_PRODUCT",
                "SUBJECT_TRIAL",
                "SUBJECT_INDICATION",
                "SUBJECT_REGIMEN",
                "SOURCE_RECORD",
                "TERM_CANDIDATE_FOR",
            }
            for edge in graph["edges"]
        ),
        "clinical_graph_causal_overreach",
    )
    require(
        result["memory_update"]["write_attempted"] is False,
        "clinical_preview_mutation_forbidden",
    )
    require(
        result["persistence"]["status"] == "not_attested",
        "clinical_persistence_not_attested",
    )
    if "memory_decision" in result:
        decision = result["memory_decision"]
        require(
            all(
                decision.get(flag) is False
                for flag in (
                    "write_attempted",
                    "commit_observed",
                    "readback_verified",
                    "history_verified",
                )
            )
            and decision.get("journal_status") == "not_attested",
            "clinical_memory_effect_not_attested",
        )
    if "decision_summary" in result:
        require(
            result["decision_summary"].get("predictive_success_probability") is None,
            "clinical_predictive_model_not_validated",
        )


def render_report(result: dict) -> str:
    """Render the attached-model headings from canonical JSON without new science."""

    def literal(value: object) -> str:
        return (
            html.escape(str(value))
            .replace("#", "&#35;")
            .replace("*", "&#42;")
            .replace("[", "&#91;")
        )

    lines = [
        "# Clinical hypothesis assessment",
        "",
        "Analysis: " + result["analysis_mode"],
        "Status: " + result["quality"]["status"],
        "",
        "Source acquisition, scientific review and memory persistence are separate states.",
        "",
    ]
    decision = result.get("decision_summary")
    if decision:
        lines.extend(
            [
                "Decision disposition: " + decision["disposition"],
                "Next evidence action: " + decision["next_action"],
                "Predictive probability and commercial recommendation: not assessed.",
                "",
            ]
        )
        lines.extend(
            [
                "## Reconciled case and causal questions",
                "",
                "A documented clinical outcome and its biological explanation are separate conclusions.",
                "Priorities below reflect reviewed support and exact scope; every full candidate is retained below.",
                "",
            ]
        )
        for group in decision.get("causal_priorities", []):
            lines.append(
                "- "
                + literal(group["review_tier"])
                + ": "
                + literal(group["reason_code"])
                + " — "
                + literal(group["scope"])
                + "; candidate IDs: "
                + literal(", ".join(group["candidate_ids"]))
            )
        coverage = decision.get("review_coverage", {})
        lines.extend(
            [
                "",
                "Review coverage: "
                + literal(coverage.get("reviewed", 0))
                + " reviewed; "
                + literal(coverage.get("unreviewed", 0))
                + " unreviewed.",
                "",
            ]
        )
    for item in result["case_assessments"]:
        lines.append(
            literal(item["dimension"])
            + ": "
            + literal(item["value"])
            + (" (reviewed)" if item["accepted"] else " (unresolved candidate)")
        )
    lines.append("")
    for number, item in enumerate(result["hypothesis_results"], 1):
        lines.extend(
            [
                "## " + str(number) + ". " + literal(item["item_id"]),
                "",
                "Hypothesis: " + literal(item["statement"]),
                "Verdict: " + item["verdict"],
                "Scope: " + literal(item["scope"]),
            ]
        )
        seed = item.get("source_assertion")
        if seed:
            lines.extend(
                [
                    "Original supplied hypothesis: " + literal(seed["statement"]),
                    "General Research Observation (supplied, not validated): "
                    + literal(
                        seed.get("general_research_observation") or "Not supplied"
                    ),
                    "Example Drugs (as supplied): "
                    + literal(", ".join(seed.get("example_drugs", []))),
                ]
            )
        lines.append("Indicators to Measure and Validate:")
        lines.extend("- " + literal(value) for value in item["validation_indicators"])
        lines.extend(
            [
                "Falsification condition: " + literal(item["falsification_condition"]),
                "Evidence: " + ", ".join(item["supporting_evidence_ids"]),
                "Counterevidence: " + ", ".join(item["contradicting_evidence_ids"]),
                "Alternative explanations: "
                + literal("; ".join(item["alternative_explanations"])),
                "Automated review: " + literal(item["review_reason"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
