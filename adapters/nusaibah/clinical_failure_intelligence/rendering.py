"""Deterministic graph and report projections of the same reviewed assertions."""
from __future__ import annotations
import html
if __package__:
    from .contracts import SCHEMA, digest, require, safe_json
else:
    from contracts import SCHEMA, digest, require, safe_json


def build_reason_graph(subject: dict, items: list[dict], evidence: list[dict]) -> dict:
    """Render evidence/hypothesis edges without manufacturing a causal relationship."""
    subject_node = "subject:" + subject["subject_id"]
    nodes = [{"id": subject_node, "type": "subject", "reference": subject["subject_id"]}]
    nodes.extend({"id": "evidence:" + row["evidence_id"], "type": "evidence", "reference": row["evidence_id"]}
                 for row in evidence)
    edges = []
    for item in items:
        node = "assertion:" + item["item_id"]
        nodes.append({"id": node, "type": item["kind"], "reference": item["item_id"],
                      "accepted": item["accepted"], "review_status": item["review_status"]})
        edges.append({"from": subject_node, "to": node,
            "relation": "HAS_OUTCOME" if item["kind"] == "outcome" else "HAS_HYPOTHESIS",
            "assertion_id": item["item_id"], "status": item["review_status"]})
        for key, relation in (("supporting_evidence_ids", "SUPPORTS"), ("contradicting_evidence_ids", "CONTRADICTS")):
            for ref in item[key]:
                edges.append({"from": "evidence:" + ref, "to": node, "relation": relation,
                    "assertion_id": item["item_id"], "evidence_ids": [ref],
                    "status": "reviewed_assertion" if item["accepted"] else "candidate_link",
                    "scope": item.get("scope", {"trial_ids": item.get("trial_ids", [])})})
        for dependency in item["depends_on"]:
            edges.append({"from": node, "to": "assertion:" + dependency, "relation": "DEPENDS_ON",
                          "assertion_id": item["item_id"], "status": item["review_status"]})
    for edge in edges:
        edge["id"] = "edge:" + digest(edge).split(":", 1)[1][:24]
    return {"schema_version": "clinical_reason_graph.v1", "nodes": sorted(nodes, key=lambda x: x["id"]),
            "edges": sorted(edges, key=lambda x: x["id"])}


def validate_result(result: dict) -> None:
    """Require reference closure and truthful non-writing, non-persistence states."""
    safe_json(result)
    require(result.get("schema_version") == SCHEMA, "clinical_result_schema_invalid")
    items = result["case_assessments"] + result["hypothesis_results"]
    evidence_ids = {row["evidence_id"] for row in result["evidence"]}
    require(len(evidence_ids) == len(result["evidence"]), "clinical_result_evidence_duplicate")
    item_ids = {item["item_id"] for item in items}
    require(len(item_ids) == len(items), "clinical_result_item_duplicate")
    for item in items:
        require(set(item["supporting_evidence_ids"] + item["contradicting_evidence_ids"]) <= evidence_ids,
                "clinical_result_evidence_dangling")
        require(set(item["depends_on"]) <= item_ids, "clinical_result_dependency_dangling")
        if item["kind"] == "hypothesis" and item["verdict"] in {"supported", "refuted"}:
            refs = item["supporting_evidence_ids"] if item["verdict"] == "supported" else item["contradicting_evidence_ids"]
            require(item["accepted"] and item["review_status"] == "automated_reviewed" and bool(refs),
                    "clinical_result_unreviewed_conclusion")
    graph = result["reason_graph"]
    nodes = {node["id"] for node in graph["nodes"]}
    require(len(nodes) == len(graph["nodes"]), "clinical_graph_duplicate")
    require(len({edge["id"] for edge in graph["edges"]}) == len(graph["edges"]), "clinical_graph_edge_duplicate")
    require(all(edge["from"] in nodes and edge["to"] in nodes for edge in graph["edges"]), "clinical_graph_dangling")
    require(all(edge["relation"] in {"HAS_OUTCOME", "HAS_HYPOTHESIS", "SUPPORTS", "CONTRADICTS", "DEPENDS_ON"}
                for edge in graph["edges"]), "clinical_graph_causal_overreach")
    require(result["memory_update"]["write_attempted"] is False, "clinical_preview_mutation_forbidden")
    require(result["persistence"]["status"] == "not_attested", "clinical_persistence_not_attested")


def render_report(result: dict) -> str:
    """Render the attached-model headings from canonical JSON without new science."""
    def literal(value: object) -> str:
        return html.escape(str(value)).replace("#", "&#35;").replace("*", "&#42;").replace("[", "&#91;")
    lines = ["# Clinical hypothesis assessment", "", "Analysis: " + result["analysis_mode"],
             "Status: " + result["quality"]["status"], ""]
    for number, item in enumerate(result["hypothesis_results"], 1):
        lines.extend(["## " + str(number) + ". " + literal(item["item_id"]), "",
            "Hypothesis: " + literal(item["statement"]), "Verdict: " + item["verdict"],
            "Scope: " + literal(item["scope"])])
        seed = item.get("source_assertion")
        if seed:
            lines.extend(["Original supplied hypothesis: " + literal(seed["statement"]),
                "General Research Observation (supplied, not validated): " + literal(seed.get("general_research_observation") or "Not supplied"),
                "Example Drugs (as supplied): " + literal(", ".join(seed.get("example_drugs", [])))])
        lines.append("Indicators to Measure and Validate:")
        lines.extend("- " + literal(value) for value in item["validation_indicators"])
        lines.extend(["Falsification condition: " + literal(item["falsification_condition"]),
            "Evidence: " + ", ".join(item["supporting_evidence_ids"]),
            "Counterevidence: " + ", ".join(item["contradicting_evidence_ids"]),
            "Alternative explanations: " + literal("; ".join(item["alternative_explanations"])),
            "Automated review: " + literal(item["review_reason"]), ""])
    return "\n".join(lines).rstrip() + "\n"
