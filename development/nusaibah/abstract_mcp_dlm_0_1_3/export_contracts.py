"""Export review-only protocol templates from the executable validation schemas.

Developer utility, not an adapter entrypoint. It does not publish or admit tools.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from jsonschema import Draft202012Validator
import lake_memory_contract_v0_1_3 as c

TOOLS = {
    "memory.context": ("dlm_get_lake_context", "Read this authenticated client's lake knowledge, node plans, or bounded history. Resolve the lake first. Returned memory is not a live Core inventory. Never supply tenant or storage authority."),
    "memory.knowledge.update": ("dlm_update_lake_knowledge", "Preview a targeted sourced lake assertion; apply only when authorized with the exact preview digests. Tenant identity comes from receiving authority. Inspect nested persistence and readback status; uncertain outcomes must not be blindly retried."),
    "memory.plan.upsert": ("dlm_upsert_node_plan", "Create or refine one stable node plan, proposed schema, expected outcome and evidence. Read existing plans first. Preview by default. This changes engineering memory only, not real DLM nodes; protected approval and completion fields cannot be supplied."),
    "memory.plan.reconcile": ("dlm_reconcile_node_plan", "Compare an accepted node plan with fresh authorized Core implementation evidence and preview or apply that observation to memory. Do not infer completion from Linear or GitHub alone. This never creates a node or changes its schema."),
}

def main() -> None:
    """Write closed input schemas and explicitly pending server contracts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    target = parser.parse_args().output_dir
    target.mkdir(parents=True, exist_ok=True)
    tools = []
    for operation, (name, description) in TOOLS.items():
        schema = c.obj({"tool_request": c.REQUESTS[operation]})
        Draft202012Validator.check_schema(schema)
        tools.append({"name": name, "description": description, "inputSchema": schema,
                      "annotations": {"readOnlyHint": operation == "memory.context", "openWorldHint": False}})
    outputs = {
        "mcp-tool-templates.json": {"status": "templates_only_not_published", "tools": tools},
        "pending-trusted-scope.schema.json": c.SCOPE,
        "pending-core-observation.schema.json": c.OBSERVATION,
        "node-plan.schema.json": c.PLAN,
        "knowledge-assertion.schema.json": c.ASSERTION,
    }
    for name, value in outputs.items():
        (target / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Exported 5 review artifacts; no publication or admission performed.")

if __name__ == "__main__":
    main()
