"""Offline promotion + signed local_worker + actual isolated callable proof.

Run with an installed pi-obs-python-runtime >= 0.1.103. No env file is loaded,
no provider is executed, and no production registration/binding is changed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import importlib.metadata
import json
import tempfile
import time
import uuid
from pathlib import Path

from adapters.runtime_catalog import AdapterEnvironmentBindingRegistry, AdapterRuntimeCatalogRegistry
from devtools import runtime_worker
from devtools.adapter_catalog import publish_catalog
from devtools.adapter_intake import inspect_adapter_intake_folder, promotion_options_from_adapter_yaml
from devtools.asset_promote import build_file_plan
from devtools.runtime_worker_capability_composition import install_runtime_worker_capabilities
from devtools.trusted_runtime_callable_invocation import (
    TRUSTED_CONTEXT_KEY, TrustedRuntimeCallableError, _TrustedCallableSession, _parse_plan,
)

from test_structured_review_toolkit import fixture

ROOT = Path(__file__).resolve().parents[1]
SLUGS = ("structured_review_toolkit", "company_review_tools_demo", "policy_review_tools_demo")
IDENTITIES = (*("nusaibah." + slug + ":0.1.0" for slug in SLUGS),
              "nusaibah.structured_review_toolkit:0.1.1")


def materialize(stage: Path, *, slugs: tuple[str, ...] = SLUGS) -> None:
    for slug in slugs:
        source = ROOT / "adapters" / "nusaibah" / slug
        yaml = source / "adapter.yaml"
        inspected = inspect_adapter_intake_folder(yaml)
        if inspected.get("status") != "ready":
            raise AssertionError("intake_not_ready: " + json.dumps(inspected))
        options = promotion_options_from_adapter_yaml(yaml)
        manifests = list(source.glob("*.asset.json"))
        if len(manifests) != 1:
            raise AssertionError("one_intake_manifest_required")
        manifest_path = manifests[0]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        selected = manifest["default"]
        plan = build_file_plan(root=source, manifest_path=manifest_path,
            asset_key=manifest["key"], asset_version=selected, version_manifest=manifest["versions"][selected],
            target_package="python_runtime/adapters/intake/nusaibah/" + slug,
            include_reviewed_helpers=True, reviewed_helpers=options["reviewed_helpers"],
            declared_support_files=options["declared_support_files"])
        if plan["status"] != "ready":
            raise AssertionError("copy_plan_not_ready")
        destination = stage / slug
        destination.mkdir()
        (destination / "__init__.py").write_text("", encoding="utf-8")
        for item in plan["copy_pairs"]:
            input_path = (source / item["source"]).resolve()
            if not input_path.is_relative_to(source.resolve()):
                raise AssertionError("copy_source_outside_intake")
            name = Path(item["destination"]).name
            (destination / name).write_bytes(input_path.read_bytes())


def signed_headers(body: bytes, request: dict, config) -> dict:
    timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
    digest = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((config.signature_version, runtime_worker.REQUEST_SCOPE, "POST", config.path,
        timestamp, nonce, digest, request["run"]["workflow_run_uuid"], request["adapter"]["key"],
        request["adapter"]["version"], request["context"]["execution_substrate"]))
    return {runtime_worker.AUTH_VERSION_HEADER: config.signature_version,
            runtime_worker.KEY_ID_HEADER: config.key_id, runtime_worker.SCOPE_HEADER: runtime_worker.REQUEST_SCOPE,
            runtime_worker.TIMESTAMP_HEADER: timestamp, runtime_worker.NONCE_HEADER: nonce,
            runtime_worker.BODY_SHA256_HEADER: digest,
            runtime_worker.SIGNATURE_HEADER: hmac.new(config.shared_secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()}


def assert_signed_response(response: dict, headers: dict, request: dict, config) -> None:
    digest = hashlib.sha256(json.dumps(response, ensure_ascii=False).encode()).hexdigest()
    if digest != headers[runtime_worker.BODY_SHA256_HEADER]:
        raise AssertionError("response_digest_mismatch")
    canonical = "\n".join((config.signature_version, runtime_worker.RESPONSE_SCOPE,
        headers[runtime_worker.TIMESTAMP_HEADER], headers[runtime_worker.NONCE_HEADER], digest,
        request["run"]["workflow_run_uuid"], request["adapter"]["key"], request["adapter"]["version"], response["status"]))
    expected = hmac.new(config.shared_secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, headers[runtime_worker.SIGNATURE_HEADER]):
        raise AssertionError("response_signature_mismatch")


def worker_request(kind: str) -> dict:
    values, _ = fixture(kind)
    key = "nusaibah." + kind + "_review_tools_demo"
    run_uuid = str(uuid.uuid4())
    plan = {"schema_version": "direct_runtime_callable_plan.v1",
        "run": {"run_uuid": run_uuid, "client_id": "synthetic-review-proof"},
        "asset": {"key": key, "version": "0.1.0"}, "execution": {"substrate": "local_worker"},
        "limits": {"max_child_calls": 1}, "roles": [{"role": "review_toolkit",
            "target": {"key": "nusaibah.structured_review_toolkit", "version": "0.1.0"},
            "callable_result": {"result_key": "tool_result", "result_shape": "object"},
            "required_prepared_roles": []}], "authority_values_included": False}
    plan["plan_revision"] = "drcp_" + hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"run": {"workflow_run_uuid": run_uuid}, "adapter": {"key": key, "version": "0.1.0"},
        "inputs": {"variables": values}, "context": {"run_uuid": run_uuid, "execution_substrate": "local_worker",
            TRUSTED_CONTEXT_KEY: {"enabled": True, "version": 1, "callable_plan": plan}}}


def prove_rejection(name: str, request: dict, config, registry) -> dict:
    body = json.dumps(request, ensure_ascii=False).encode()
    try:
        runtime_worker.handle_runtime_request(body, signed_headers(body, request, config), config=config,
            catalog_registry=registry, environment_registry=AdapterEnvironmentBindingRegistry(), signed_failures=True)
    except runtime_worker.RuntimeWorkerResponseError as exc:
        if exc.payload.get("status") != "error":
            raise AssertionError("invalid_failure_response")
        assert_signed_response(exc.payload, exc.headers, request, config)
        return {"case": name, "status": "rejected", "signed_response_verified": True}
    raise AssertionError("invalid_request_accepted: " + name)


def prove_budget(registry) -> dict:
    # Runtime-private session API is used only for this versioned integration proof.
    # It executes the real isolated child, not a replacement invoker.
    request = worker_request("company")
    plan = _parse_plan(request["context"][TRUSTED_CONTEXT_KEY], request)
    session = _TrustedCallableSession(plan, runtime_catalog=registry,
                                     environment_registry=AdapterEnvironmentBindingRegistry())
    values, method = fixture()
    variables = {"schema_version": "review_tool_request.v1", "operation": "assemble_preview",
                 "arguments": {**values, "methodology": method}}
    first = session.invoke("review_toolkit", variables)
    cached = session.invoke("review_toolkit", variables)
    if first["provenance"]["cache_hit"] or cached["provenance"]["cache_hit"] is not True:
        raise AssertionError("callable_cache_contract_failed")
    cached["result"]["output"]["publication_allowed"] = True
    if session.invoke("review_toolkit", variables)["result"]["output"]["publication_allowed"] is not False:
        raise AssertionError("callable_cache_mutation_leaked")
    distinct = copy.deepcopy(variables)
    distinct["arguments"]["policy"]["neighbor_units"] = 1
    try:
        session.invoke("review_toolkit", distinct)
    except TrustedRuntimeCallableError as exc:
        if str(exc) != "direct_runtime_callable_budget_exhausted":
            raise AssertionError("unexpected_call_budget_failure") from exc
    else:
        raise AssertionError("child_call_budget_not_enforced")
    return {"max_child_calls": 1, "cache_reuse_verified": True,
            "cached_result_isolation_verified": True, "second_uncached_call_rejected": True}


def prove(stage: Path) -> dict:
    version = importlib.metadata.version("pi-obs-python-runtime")
    if tuple(int(part) for part in version.split(".")) < (0, 1, 103):
        raise AssertionError("runtime_version_too_old")
    materialize(stage)
    catalog_path = stage / "adapter-runtime-catalog.json"
    publish_catalog(root=stage, catalog_path=catalog_path)
    registry = AdapterRuntimeCatalogRegistry(external_catalogs=(catalog_path,))
    if set(registry.entries()) != set(IDENTITIES):
        raise AssertionError("unexpected_runtime_identity_discovery")
    tool_hash = registry.resolve(IDENTITIES[0]).entry_hash
    install_runtime_worker_capabilities(runtime_worker)
    config = runtime_worker.WorkerConfig(key_id="synthetic-review-proof", shared_secret=uuid.uuid4().hex,
        adapter_roots=(str(stage),), allowed_adapters=IDENTITIES)
    reports = []
    for kind in ("company", "policy"):
        request = worker_request(kind)
        body = json.dumps(request, ensure_ascii=False).encode()
        response, headers = runtime_worker.handle_runtime_request(body, signed_headers(body, request, config),
            config=config, catalog_registry=registry, environment_registry=AdapterEnvironmentBindingRegistry())
        assert_signed_response(response, headers, request, config)
        preview = response["outputs"]["review_preview"]
        if response["status"] != "success" or preview["toolkit_version"] != "0.1.0":
            raise AssertionError("worker_tool_reuse_failed")
        if preview["agent_call_count"] != 0 or preview["mutable_call_count"] != 0:
            raise AssertionError("unexpected_provider_or_mutable_call")
        output = preview["output"]
        if not output["preview_only"] or output["publication_allowed"] or output["semantic_authority_verified"]:
            raise AssertionError("preview_authority_boundary_failed")
        reports.append({"consumer": request["adapter"]["key"], "status": "passed",
                        "toolkit_entry_hash": tool_hash, "tool_call_count": response["metrics"]["tool_call_count"],
                        "agent_call_count": 0, "mutable_call_count": 0, "signed_response_verified": True})
    failures = []
    request = worker_request("company")
    request["context"].pop(TRUSTED_CONTEXT_KEY)
    failures.append(prove_rejection("missing_callable_authority", request, config, registry))
    request = worker_request("company")
    request["inputs"]["variables"]["source_hash"] = "0" * 64
    failures.append(prove_rejection("modified_source_digest", request, config, registry))
    request = worker_request("company")
    request["inputs"]["variables"]["source"]["entity_id"] = "synthetic-policy:other"
    failures.append(prove_rejection("wrong_consumer_domain", request, config, registry))
    request = worker_request("company")
    request["context"][TRUSTED_CONTEXT_KEY]["callable_plan"]["roles"][0]["role"] = "undeclared"
    failures.append(prove_rejection("unavailable_declared_role", request, config, registry))
    budget = prove_budget(registry)
    helper = stage / "structured_review_toolkit" / "tool_operations.py"
    original = helper.read_bytes()
    try:
        helper.write_bytes(original + b"\n# deliberate integrity proof mutation\n")
        failures.append(prove_rejection("modified_reviewed_helper", worker_request("company"), config, registry))
    finally:
        helper.write_bytes(original)
    return {"schema_version": "shared_review_toolkit_worker_proof.v1", "safe": True, "values_included": False,
            "status": "passed", "runtime_version": version,
            "substrate": "local_worker", "proof_scope": "offline_signed_worker_and_actual_isolated_callable",
            "live_admission_proven": False, "semantic_quality_measured": False, "consumers": reports,
            "negative_cases": failures, "call_budget": budget}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    # TemporaryDirectory owns only this freshly created directory; no checkout is deleted.
    with tempfile.TemporaryDirectory(prefix="review_toolkit_proof_") as value:
        stage = Path(value).resolve()
        if not stage.name.startswith("review_toolkit_proof_"):
            raise AssertionError("temporary_proof_directory_invalid")
        report = prove(stage)
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
