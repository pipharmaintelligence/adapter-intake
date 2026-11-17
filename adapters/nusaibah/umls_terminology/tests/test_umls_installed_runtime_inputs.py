"""Offline public-SDK contract tests for the unregistered UMLS adapter.

These tests use the actual installed RuntimeInputs class, not a test-owned
replacement. They do not start an Assets worker or reach Core, provider, or
network. Their CI skip is intentional until an official SDK wheel is present.
Set UMLS_REQUIRE_INSTALLED_RUNTIME=1 to fail closed when running in the E: venv.
"""

from __future__ import annotations

from importlib import import_module, metadata, util
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def sdk_runtime_inputs():
    """Use exactly the public class exposed by the installed runtime wheel."""
    required = os.environ.get("UMLS_REQUIRE_INSTALLED_RUNTIME") == "1"
    try:
        installed = metadata.version("pi-obs-python-runtime")
        runtime = import_module("system.runtime")
    except (metadata.PackageNotFoundError, ModuleNotFoundError) as exc:
        if required:
            pytest.fail("umls_sdk_runtime_wheel_unavailable", pytrace=False)
        pytest.skip("umls_sdk_wheel_not_installed_in_intake_ci")

    expected = os.environ.get("UMLS_EXPECT_RUNTIME_VERSION")
    if expected and installed != expected:
        pytest.fail("umls_sdk_runtime_wheel_version_mismatch", pytrace=False)
    assert runtime.RuntimeInputs.__module__ == "system.runtime"
    return runtime.RuntimeInputs


@pytest.fixture(scope="module")
def adapter_type(sdk_runtime_inputs):
    """Load exact intake source without adding the project root to sys.path."""
    location = Path(__file__).resolve().parents[1] / "umls_terminology_adapter.py"
    spec = util.spec_from_file_location("umls_installed_sdk_contract_adapter", location)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ASSET_KEY == "umls_terminology"
    assert module.ASSET_VERSION == "0.1.0"
    return module.UmlsTerminologyAdapter


def _call(adapter_type, values):
    """Read the real adapter's complete public result envelope."""
    return adapter_type().invoke(values, {})


def test_real_runtimeinputs_lazy_brac1_query_and_output(
    sdk_runtime_inputs, adapter_type
):
    calls = []

    def trusted_invoker(role, *, variables, cooldown_seconds):
        calls.append((role, variables, cooldown_seconds))
        return {
            "records": [
                {"ui": "C0000001", "name": "BRCA1"},
                {"ui": "C0000002", "name": "BRCA1 gene"},
            ],
            "metadata": {},
        }

    runtime = sdk_runtime_inputs(
        {
            "variables": {
                "operation": "search",
                "text": " BRCA1 ",
                "search_type": "exact",
            },
            "umls_response": {"records": []},
        },
        invoker=trusted_invoker,
    )
    response = _call(adapter_type, runtime)
    assert calls == [
        (
            "umls_response",
            {"string": "BRCA1", "searchType": "exact"},
            None,
        )
    ]
    assert response["response_version"] == "1"
    assert response["status"] == "success"
    assert response["metrics"] == {"record_count": 2}
    assert set(response["outputs"]) == {"terminology_result"}
    result = response["outputs"]["terminology_result"]
    assert result["operation"] == "search"
    assert result["status"] == "ok"
    assert len(result["records"]) == 2
    assert result["provenance"]["release"] is None
    assert result["completeness"] == {"returned_count": 2, "truncated": None}
    assert result["query_attested"] is False


def test_real_runtimeinputs_projects_optional_source_allowlist(
    sdk_runtime_inputs, adapter_type
):
    calls = []

    def trusted_invoker(role, *, variables, cooldown_seconds):
        calls.append((role, variables))
        return {"records": [], "metadata": {}}

    runtime = sdk_runtime_inputs(
        {
            "variables": {
                "operation": "search",
                "text": "BRCA1",
                "sources": ["SNOMEDCT_US", "RXNORM"],
            },
            "umls_response": {"records": []},
        },
        invoker=trusted_invoker,
    )
    result = _call(adapter_type, runtime)["outputs"]["terminology_result"]
    assert calls == [
        (
            "umls_response",
            {
                "string": "BRCA1",
                "searchType": "words",
                "sabs": "SNOMEDCT_US,RXNORM",
            },
        )
    ]
    assert result["records"] == []
    assert result["completeness"]["truncated"] is None


def test_real_runtimeinputs_never_trusts_caller_records(
    sdk_runtime_inputs, adapter_type
):
    runtime = sdk_runtime_inputs({
        "variables": {"operation": "search", "text": "BRCA1"},
        "umls_response": {
            "records": [{"ui": "C0000001", "name": "Caller data"}],
            "metadata": {},
        },
    })
    with pytest.raises(ValueError, match="^umls_runtime_source_fetch_failed$"):
        _call(adapter_type, runtime)


def test_real_runtimeinputs_rejects_missing_source_role(
    sdk_runtime_inputs, adapter_type
):
    calls = []

    def trusted_invoker(role, *, variables, cooldown_seconds):
        calls.append(role)
        return {"records": [], "metadata": {}}

    runtime = sdk_runtime_inputs(
        {"variables": {"operation": "search", "text": "BRCA1"}},
        invoker=trusted_invoker,
    )
    with pytest.raises(ValueError, match="^umls_runtime_source_not_prepared$"):
        _call(adapter_type, runtime)
    assert calls == []


def test_real_runtimeinputs_redacts_failed_invoker(
    sdk_runtime_inputs, adapter_type
):
    def failed_invoker(role, *, variables, cooldown_seconds):
        raise RuntimeError("non-public failure detail")

    runtime = sdk_runtime_inputs(
        {
            "variables": {"operation": "search", "text": "BRCA1"},
            "umls_response": {"records": []},
        },
        invoker=failed_invoker,
    )
    with pytest.raises(ValueError, match="^umls_runtime_source_fetch_failed$") as exc:
        _call(adapter_type, runtime)
    assert "non-public" not in str(exc.value)


def test_real_runtimeinputs_rejects_untrusted_result_shape(
    sdk_runtime_inputs, adapter_type
):
    def malformed_invoker(role, *, variables, cooldown_seconds):
        return {
            "records": [{"ui": "C0000001"}],
            "metadata": {},
            "untrusted_extra": "excluded",
        }

    runtime = sdk_runtime_inputs(
        {
            "variables": {"operation": "search", "text": "BRCA1"},
            "umls_response": {"records": []},
        },
        invoker=malformed_invoker,
    )
    with pytest.raises(ValueError, match="^umls_runtime_source_envelope_invalid$"):
        _call(adapter_type, runtime)


def test_real_runtimeinputs_describe_never_calls_source(
    sdk_runtime_inputs, adapter_type
):
    calls = []

    def trusted_invoker(role, *, variables, cooldown_seconds):
        calls.append(role)
        return {"records": [], "metadata": {}}

    runtime = sdk_runtime_inputs(
        {"variables": {"operation": "describe"}},
        invoker=trusted_invoker,
    )
    result = _call(adapter_type, runtime)["outputs"]["terminology_result"]
    assert result["operation"] == "describe"
    assert calls == []
