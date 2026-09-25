from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace


ADAPTER_PATH = (
    Path(__file__).resolve().parents[1]
    / "adapters"
    / "nusaibah"
    / "agent_capability_lab"
    / "nusaibah_agent_capability_lab_adapter.py"
)


class PublicReferenceError(RuntimeError):
    pass


class _CitationView:
    def __init__(self, citations: tuple[SimpleNamespace, ...]) -> None:
        self._citations = citations

    def deduped_citations(self) -> tuple[SimpleNamespace, ...]:
        return self._citations


class _CitationViewFactory:
    @classmethod
    def from_agent_result(cls, result: dict[str, object]) -> _CitationView:
        assert result["schema_version"] == "agent_result.v1"
        return _CitationView(
            (
                SimpleNamespace(provider_family="vertex_ai", marker="first"),
                SimpleNamespace(provider_family="vertex_ai", marker="second"),
            )
        )


class _ReferenceTargetFactory:
    @classmethod
    def from_agent_citation(cls, citation: SimpleNamespace) -> str:
        return f"target:{citation.marker}"


class _Memory:
    def read(self) -> str:
        return "Existing governed company memory."


class _Inputs:
    def __init__(self) -> None:
        self.reference_calls: list[str] = []

    def invoke_agent(self, role: str, *, input: dict[str, object]) -> dict[str, object]:
        assert role == "vertex_grounded_orchestrator"
        return {
            "status": "completed",
            "result": {
                "schema_version": "agent_result.v1",
                "text": "\n".join(
                    [
                        "FORMAT_ID: capability_lab.vertex_grounded.v1",
                        "SUMMARY:",
                        "- summary one",
                        "- summary two",
                        "VERIFIED_UPDATES:",
                        "- update one",
                        "- update two",
                        "MEMORY_NOTE:",
                        "Evidence-based non-bullet note.",
                        "END_FORMAT",
                    ]
                ),
            },
        }

    def open_reference(self, target: str, *, mode: str) -> SimpleNamespace:
        self.reference_calls.append(target)
        assert mode == "http"

        if target == "target:first":
            raise PublicReferenceError("public_reference_http_failed")

        return SimpleNamespace(
            text="Readable public evidence.",
            transport="http",
        )


def _namespace() -> dict[str, object]:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    constants = {
        "VERTEX_GROUNDED_AGENT_ROLE",
        "CANONICAL_COMPANY_ID",
        "CANONICAL_COMPANY_NAME",
        "MAX_RESEARCH_TEXT_CHARS",
        "MAX_CERTIFICATION_CITATIONS",
        "VERTEX_RESPONSE_FORMAT_ID",
        "VERTEX_FORMAT_SUMMARY",
        "VERTEX_FORMAT_UPDATES",
        "VERTEX_FORMAT_MEMORY_NOTE",
        "VERTEX_FORMAT_END",
        "VERTEX_FORMAT_BULLET_PREFIX",
        "VERTEX_FORMAT_SUMMARY_MIN_ITEMS",
        "VERTEX_FORMAT_SUMMARY_MAX_ITEMS",
        "VERTEX_FORMAT_UPDATES_MIN_ITEMS",
        "VERTEX_FORMAT_UPDATES_MAX_ITEMS",
    }
    functions = {
        "_resolve_agent_result",
        "_vertex_format_instructions",
        "_validate_vertex_response_format",
        "_run_vertex_certification_research",
    }

    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if names & constants:
                selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in functions:
            selected.append(node)

    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)

    namespace: dict[str, object] = {
        "Any": object,
        "AgentCitationView": _CitationViewFactory,
        "ReferenceTarget": _ReferenceTargetFactory,
    }
    exec(compile(module, str(ADAPTER_PATH), "exec"), namespace)
    return namespace


def test_0_1_14_first_reference_failure_aborts_before_second_citation() -> None:
    """Prove the fatal-abort policy is owned by the adapter control flow.

    There is no Core call and no network call in this test. The first reference
    raises the same stable error identifier observed live, while the second
    reference is configured to succeed. Current 0.1.14 must exit before the
    second reference is attempted.
    """

    namespace = _namespace()
    inputs = _Inputs()

    try:
        namespace["_run_vertex_certification_research"](inputs, _Memory())
    except PublicReferenceError as exc:
        assert str(exc) == "public_reference_http_failed"
    else:
        raise AssertionError("expected first citation-open failure to escape")

    assert inputs.reference_calls == ["target:first"]
