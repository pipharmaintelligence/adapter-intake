"""Offline signed bridge/isolated-child proof; no provider or live admission."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile
import uuid

import prove_review_toolkit_worker as shared

BRIDGE = "nusaibah.exact_span_bridge_proof"
VERSIONS = ("0.1.0", "0.1.1", "0.1.2", "0.2.0", "0.2.1", "0.2.2")
IDENTITIES = (*shared.IDENTITIES, *(f"nusaibah.pharma_company_intelligence_lab_evaluation:{v}" for v in VERSIONS),
              BRIDGE + ":0.1.0")
# This parent exists only in the fresh temporary test catalog, never in intake/promotion.
PARENT = '''
from adapters.base import Adapter
class SpanProofRejected(RuntimeError):
    def __init__(self, rule):
        self.failure_code = "span_proof_quote_rejected"
        self.proof_stage = "agent_contract"
        self.proof_failure_detail = {"schema_version":"proof_failure_detail.v1",
            "proof_kind":"agent_contract", "role":"review_toolkit",
            "stage":"source_review_span_resolution", "rule":rule}
        super().__init__(self.failure_code)
class ExactSpanProofAdapter(Adapter):
    key = "nusaibah.exact_span_bridge_proof"
    version = "0.1.0"
    def invoke(self, inputs, context):
        result = inputs.invoke_asset("review_toolkit", variables=inputs["variables"], on_error="raise")
        if result["status"] != "success":
            raise ValueError("span_proof_child_failed")
        if result["result"]["output"]["status"] != "resolved":
            raise SpanProofRejected(result["result"]["output"]["reason_code"])
        return {"response_version":"1", "status":"success", "outputs":{"spans":result["result"]},
                "metrics":{"tool_call_count":1, "agent_call_count":0, "mutable_dynamic_skill_call_count":0}}
'''


def variables(kind="company") -> dict:
    material = {"entity_id": kind, "snapshot_id": "sha256:" + "a" * 64,
                "source_units": [{"locator": "source:1", "entity_id": kind,
                                 "text": "Before 😀\r\nExact evidence. After.", "accessible": True}]}
    digest = hashlib.sha256(json.dumps(material, ensure_ascii=False,
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"schema_version": "review_tool_request.v1", "operation": "resolve_exact_spans",
            "arguments": {**material, "source_digest": digest,
                          "requests": [{"request_id": "r1", "locator": "source:1", "quote": "Exact evidence."}]}}


def request(kind="company") -> dict:
    value = shared.worker_request("company")
    value["adapter"]["key"] = BRIDGE
    value["inputs"]["variables"] = variables(kind)
    plan = value["context"][shared.TRUSTED_CONTEXT_KEY]["callable_plan"]
    plan["asset"]["key"] = BRIDGE
    plan["roles"][0]["target"]["version"] = "0.1.1"
    plan.pop("plan_revision")
    plan["plan_revision"] = "drcp_" + hashlib.sha256(json.dumps(
        plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return value


def prove(stage: Path) -> dict:
    shared.materialize(stage, slugs=(*shared.SLUGS, "pharma_company_intelligence_lab_evaluation"))
    parent = stage / "exact_span_bridge_proof"
    parent.mkdir()
    (parent / "__init__.py").write_text("", encoding="utf-8")
    (parent / "exact_span_proof_adapter.py").write_text(PARENT, encoding="utf-8")
    manifest = {"key": BRIDGE, "default": "0.1.0", "allowed_modes": ["balanced"],
        "versions": {"0.1.0": {"state": "active", "inputs": {"variables": {"source": "direct", "shape": "object"}},
            "outputs": {"spans": {"shape": "object"}},
            "callable_assets": {"review_toolkit": {"asset_key": "nusaibah.structured_review_toolkit",
                "asset_version": "0.1.1", "result_key": "tool_result", "result_shape": "object"}}}}}
    (parent / "exact_span_proof.asset.json").write_text(json.dumps(manifest), encoding="utf-8")
    catalog = stage / "adapter-runtime-catalog.json"
    shared.publish_catalog(root=stage, catalog_path=catalog)
    registry = shared.AdapterRuntimeCatalogRegistry(external_catalogs=(catalog,))
    if set(registry.entries()) != set(IDENTITIES):
        raise AssertionError("unexpected_identity_discovery")
    shared.install_runtime_worker_capabilities(shared.runtime_worker)
    config = shared.runtime_worker.WorkerConfig(key_id="span-proof", shared_secret=uuid.uuid4().hex,
        adapter_roots=(str(stage),), allowed_adapters=IDENTITIES)
    consumers = []
    for kind in ("company", "policy"):
        value = request(kind)
        body = json.dumps(value, ensure_ascii=False).encode()
        response, headers = shared.runtime_worker.handle_runtime_request(body,
            shared.signed_headers(body, value, config), config=config, catalog_registry=registry,
            environment_registry=shared.AdapterEnvironmentBindingRegistry())
        shared.assert_signed_response(response, headers, value, config)
        result = response["outputs"]["spans"]
        span = result["output"]["spans"][0]
        if (result["toolkit_version"] != "0.1.1" or (span["start"], span["end"]) != (10, 25)
                or result["output"]["semantic_authority_verified"] is not False):
            raise AssertionError("exact_span_bridge_failed")
        consumers.append({"domain": kind, "signed_response_verified": True,
                          "actual_isolated_child": True, "child_calls": 1,
                          "agent_calls": 0, "mutable_calls": 0})
    failures = []
    value = request()
    value["context"].pop(shared.TRUSTED_CONTEXT_KEY)
    failures.append(shared.prove_rejection("missing_callable_authority", value, config, registry))
    value = request()
    value["inputs"]["variables"]["arguments"]["source_digest"] = "0" * 64
    failures.append(shared.prove_rejection("stale_source_digest", value, config, registry))
    value = request()
    value["inputs"]["variables"]["arguments"]["requests"][0]["quote"] = "missing"
    body = json.dumps(value, ensure_ascii=False).encode()
    try:
        shared.runtime_worker.handle_runtime_request(body, shared.signed_headers(body, value, config),
            config=config, catalog_registry=registry,
            environment_registry=shared.AdapterEnvironmentBindingRegistry(), signed_failures=True)
    except shared.runtime_worker.RuntimeWorkerResponseError as exc:
        shared.assert_signed_response(exc.payload, exc.headers, value, config)
        if exc.payload.get("error", {}).get("proof_failure_detail", {}).get("rule") != "evidence_quote_missing":
            raise AssertionError("typed_rejection_rule_not_preserved") from exc
        failures.append({"case": "missing_literal_quote", "status": "rejected",
                         "rule": "evidence_quote_missing", "signed_response_verified": True})
    else:
        raise AssertionError("missing_quote_accepted")
    value = request()
    plan = shared._parse_plan(value["context"][shared.TRUSTED_CONTEXT_KEY], value)
    session = shared._TrustedCallableSession(plan, runtime_catalog=registry,
        environment_registry=shared.AdapterEnvironmentBindingRegistry())
    first = session.invoke("review_toolkit", variables())
    cached = session.invoke("review_toolkit", variables())
    cached["result"]["output"]["spans"][0]["start"] = True
    if (first["provenance"]["cache_hit"] or cached["provenance"]["cache_hit"] is not True
            or type(session.invoke("review_toolkit", variables())["result"]["output"]["spans"][0]["start"]) is not int):
        raise AssertionError("cache_isolation_failed")
    changed = copy.deepcopy(variables())
    changed["arguments"]["requests"][0]["quote"] = "After."
    try:
        session.invoke("review_toolkit", changed)
    except shared.TrustedRuntimeCallableError as exc:
        if str(exc) != "direct_runtime_callable_budget_exhausted":
            raise AssertionError("unexpected_budget_failure") from exc
    else:
        raise AssertionError("child_budget_not_enforced")
    helper = stage / "structured_review_toolkit" / "exact_spans.py"
    original = helper.read_bytes()
    try:
        helper.write_bytes(original + b"\n# integrity probe\n")
        failures.append(shared.prove_rejection("changed_reviewed_span_helper", request(), config, registry))
    finally:
        helper.write_bytes(original)
    return {"schema_version": "exact_span_worker_proof.v1", "safe": True, "values_included": False,
        "status": "passed", "runtime_version": importlib.metadata.version("pi-obs-python-runtime"),
        "catalog_identity_count": len(IDENTITIES), "evaluation_versions_resolve": list(VERSIONS),
        "toolkit_identity": "nusaibah.structured_review_toolkit:0.1.1",
        "toolkit_entry_hash": registry.resolve("nusaibah.structured_review_toolkit:0.1.1").entry_hash,
        "consumers": consumers, "negative_cases": failures, "max_child_calls": 1,
        "second_uncached_child_rejected": True, "cache_isolation_verified": True,
        "live_admission_proven": False, "candidate_provider_execution_proven": False,
        "semantic_quality_measured": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="exact_span_proof_") as directory:
        report = prove(Path(directory).resolve())
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        if args.report.exists():
            raise AssertionError("existing_report_preserved")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
