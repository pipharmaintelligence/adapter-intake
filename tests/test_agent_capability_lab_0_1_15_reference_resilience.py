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


class PublicReferenceError(ValueError):
    pass


class _CitationView:
    def __init__(self, citations: tuple[SimpleNamespace, ...]) -> None:
        self._citations = citations

    def deduped_citations(self) -> tuple[SimpleNamespace, ...]:
        return self._citations


class _CitationViewFactory:
    citations: tuple[SimpleNamespace, ...] = ()

    @classmethod
    def from_agent_result(cls, result: dict[str, object]) -> _CitationView:
        assert result["schema_version"] == "agent_result.v1"
        return _CitationView(cls.citations)


class _ReferenceTargetFactory:
    @classmethod
    def from_agent_citation(cls, citation: SimpleNamespace) -> str:
        return f"target:{citation.marker}"


class _Memory:
    def read(self) -> str:
        return "Existing governed company memory."


class _Inputs:
    def __init__(
        self,
        *,
        failing: set[str] | None = None,
        unreadable: set[str] | None = None,
    ) -> None:
        self.failing = failing or set()
        self.unreadable = unreadable or set()
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

        if target in self.failing:
            raise PublicReferenceError("public_reference_http_failed")

        text = "" if target in self.unreadable else "Readable public evidence."
        return SimpleNamespace(text=text, transport="http")


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
        "PublicReferenceError": PublicReferenceError,
    }
    exec(compile(module, str(ADAPTER_PATH), "exec"), namespace)
    return namespace


def _citations() -> tuple[SimpleNamespace, ...]:
    return (
        SimpleNamespace(provider_family="vertex_ai", marker="first"),
        SimpleNamespace(provider_family="vertex_ai", marker="second"),
        SimpleNamespace(provider_family="vertex_ai", marker="third"),
    )


def test_first_http_failure_second_success_passes_with_only_validated_citation() -> None:
    namespace = _namespace()
    _CitationViewFactory.citations = _citations()
    inputs = _Inputs(failing={"target:first"})

    evidence, _text, citations = namespace["_run_vertex_certification_research"](
        inputs,
        _Memory(),
    )

    assert inputs.reference_calls == ["target:first", "target:second", "target:third"]
    assert tuple(citation.marker for citation in citations) == ("second", "third")
    assert evidence["vertex_certification_reference_attempt_count"] == 3
    assert evidence["vertex_certification_validated_reference_count"] == 2
    assert evidence["vertex_certification_reference_failure_count"] == 1


def test_unreadable_reference_is_skipped_when_later_reference_is_readable() -> None:
    namespace = _namespace()
    _CitationViewFactory.citations = _citations()[:2]
    inputs = _Inputs(unreadable={"target:first"})

    evidence, _text, citations = namespace["_run_vertex_certification_research"](
        inputs,
        _Memory(),
    )

    assert tuple(citation.marker for citation in citations) == ("second",)
    assert evidence["vertex_certification_validated_reference_count"] == 1
    assert evidence["vertex_certification_reference_failure_count"] == 1


def test_all_selected_reference_failures_fail_closed() -> None:
    namespace = _namespace()
    _CitationViewFactory.citations = _citations()[:2]
    inputs = _Inputs(failing={"target:first", "target:second"})

    try:
        namespace["_run_vertex_certification_research"](inputs, _Memory())
    except RuntimeError as exc:
        assert str(exc) == (
            "Vertex certification could not inspect any selected citation with readable text."
        )
    else:
        raise AssertionError("expected all-reference failure to fail closed")


def test_no_provider_citations_still_fails_closed() -> None:
    namespace = _namespace()
    _CitationViewFactory.citations = ()

    try:
        namespace["_run_vertex_certification_research"](_Inputs(), _Memory())
    except RuntimeError as exc:
        assert str(exc) == "Grounded Vertex result contained no admitted citations."
    else:
        raise AssertionError("expected missing citations to fail closed")
