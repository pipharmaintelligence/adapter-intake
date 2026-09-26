from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit


ADAPTER_PATH = (
    Path(__file__).resolve().parents[1]
    / "adapters"
    / "nusaibah"
    / "agent_capability_lab"
    / "nusaibah_agent_capability_lab_adapter.py"
)


class PublicReferenceError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


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
        return citation.locator


class _Memory:
    def read(self) -> str:
        return "Existing governed company memory."


class _ResearchInputs:
    def __init__(
        self,
        *,
        failures: dict[str, str] | None = None,
        unreadable: set[str] | None = None,
    ) -> None:
        self.failures = failures or {}
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
        assert mode == "http"
        self.reference_calls.append(target)
        code = self.failures.get(target)
        if code is not None:
            raise PublicReferenceError(code)
        text = "" if target in self.unreadable else "Readable public evidence."
        return SimpleNamespace(text=text, transport="http")


def _namespace(functions: set[str]) -> dict[str, object]:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    constants = {
        "VERTEX_GROUNDED_AGENT_ROLE",
        "CANONICAL_COMPANY_ID",
        "CANONICAL_COMPANY_NAME",
        "MAX_RESEARCH_TEXT_CHARS",
        "MAX_CERTIFICATION_CITATIONS",
        "DEGRADABLE_PUBLIC_REFERENCE_CODES",
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
        "COMPANY_MEMORY_UPDATE_ROLE",
        "CERTIFICATION_SECTION",
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
        "urlsplit": urlsplit,
        "AgentCitationView": _CitationViewFactory,
        "ReferenceTarget": _ReferenceTargetFactory,
        "PublicReferenceError": PublicReferenceError,
    }
    exec(compile(module, str(ADAPTER_PATH), "exec"), namespace)
    return namespace


def _citation(locator: str, marker: str = "c") -> SimpleNamespace:
    return SimpleNamespace(
        provider_family="vertex_ai",
        locator=locator,
        marker=marker,
    )


def _research_namespace() -> dict[str, object]:
    return _namespace(
        {
            "_resolve_agent_result",
            "_vertex_format_instructions",
            "_validate_vertex_response_format",
            "_is_public_https_reference_candidate",
            "_is_degradable_public_reference_error",
            "_partition_vertex_reference_candidates",
            "_run_vertex_certification_research",
        }
    )


def test_only_public_https_candidates_are_opened() -> None:
    namespace = _research_namespace()
    _CitationViewFactory.citations = (
        _citation("doi:10.1234/example", "doi"),
        _citation("http://example.test/not-admitted", "http"),
        _citation("https://example.test/evidence", "https"),
    )
    inputs = _ResearchInputs()

    evidence, _text, citations = namespace["_run_vertex_certification_research"](
        inputs,
        _Memory(),
    )

    assert inputs.reference_calls == ["https://example.test/evidence"]
    assert tuple(item.locator for item in citations) == (
        "https://example.test/evidence",
    )
    assert evidence["vertex_certification_web_reference_candidate_count"] == 1
    assert evidence["vertex_certification_non_web_reference_count"] == 2
    assert evidence["vertex_certification_reference_status"] == "verified"
    assert evidence["vertex_certification_mutation_eligible"] is True


def test_blocked_or_unreachable_urls_degrade_without_aborting_research() -> None:
    namespace = _research_namespace()
    first = "https://first.example.test/evidence"
    second = "https://second.example.test/evidence"
    _CitationViewFactory.citations = (
        _citation(first, "first"),
        _citation(second, "second"),
    )
    inputs = _ResearchInputs(
        failures={
            first: "public_reference_http_failed",
            second: "public_reference_target_unresolvable",
        }
    )

    evidence, _text, citations = namespace["_run_vertex_certification_research"](
        inputs,
        _Memory(),
    )

    assert citations == ()
    assert inputs.reference_calls == [first, second]
    assert evidence["vertex_certification_reference_status"] == "degraded"
    assert evidence["vertex_certification_reference_verification_complete"] is False
    assert evidence["vertex_certification_mutation_eligible"] is False
    assert evidence["vertex_certification_reference_failure_count"] == 2


def test_security_or_contract_reference_failures_remain_fatal() -> None:
    namespace = _research_namespace()
    url = "https://private.example.test/evidence"
    _CitationViewFactory.citations = (_citation(url),)
    inputs = _ResearchInputs(
        failures={url: "public_reference_target_nonpublic"}
    )

    try:
        namespace["_run_vertex_certification_research"](inputs, _Memory())
    except PublicReferenceError as exc:
        assert exc.code == "public_reference_target_nonpublic"
    else:
        raise AssertionError("expected non-public target rejection to remain fatal")


def test_no_provider_citations_remains_a_contract_failure() -> None:
    namespace = _research_namespace()
    _CitationViewFactory.citations = ()

    try:
        namespace["_run_vertex_certification_research"](
            _ResearchInputs(),
            _Memory(),
        )
    except RuntimeError as exc:
        assert str(exc) == "Grounded Vertex result contained no admitted citations."
    else:
        raise AssertionError("expected missing provider citations to fail closed")


def test_certification_skips_mutation_when_reference_verification_is_degraded() -> None:
    namespace = _namespace({"_run_vertex_dynamic_skill_certification"})
    namespace["_required_as_of_date"] = lambda variables: "2026-09-26"
    namespace["_required_certification_cycle"] = lambda variables: "cycle-1"
    namespace["_canonical_company_memory"] = lambda inputs: object()
    namespace["_exercise_dynamic_skill_read_helpers"] = lambda memory: {
        "dynamic_skill_resource_read_exercised": True
    }
    namespace["_run_vertex_certification_research"] = lambda inputs, memory: (
        {
            "vertex_certification_reference_status": "degraded",
            "vertex_certification_mutation_eligible": False,
        },
        "provider research text",
        (),
    )

    class Inputs:
        def dynamic_skill(self, *args, **kwargs):
            raise AssertionError("degraded certification must not open mutable Skill handle")

    result = namespace["_run_vertex_dynamic_skill_certification"](
        Inputs(),
        {},
    )

    assert result["dynamic_skill_real_update_applied"] is False
    assert result["dynamic_skill_mutation_skipped"] is True
    assert (
        result["dynamic_skill_mutation_skip_reason"]
        == "public_reference_verification_degraded"
    )


def test_fresh_verification_still_proves_governed_state_when_urls_are_unreachable() -> None:
    namespace = _namespace(
        {
            "_is_public_https_reference_candidate",
            "_is_degradable_public_reference_error",
            "_partition_vertex_reference_candidates",
            "_verify_vertex_dynamic_skill_certification",
        }
    )
    namespace["_required_as_of_date"] = lambda variables: "2026-09-26"
    namespace["_required_certification_cycle"] = lambda variables: "cycle-1"
    namespace["_exercise_dynamic_skill_read_helpers"] = lambda handle: {
        "dynamic_skill_resource_read_exercised": True
    }

    citations = (
        _citation("doi:10.1234/example", "doi"),
        _citation("https://blocked.example.test/evidence", "web"),
    )

    class Metadata:
        as_of_date = "2026-09-26"
        citations = citations

        @staticmethod
        def canonical_dict() -> dict[str, object]:
            return {
                "company_id": 13,
                "company_name": "Tabuk Pharmaceuticals",
                "certification_cycle": "cycle-1",
                "provider": "vertex_ai",
            }

        @staticmethod
        def review_annotation() -> str:
            return "reviewed"

    class TargetIndex:
        @staticmethod
        def digest() -> str:
            return "sha256:index"

    class LatestChange:
        after_content_digest = "sha256:content"
        target_index_changed = True

    class LatestSnapshot:
        content_digest = "sha256:content"
        target_index_digest = "sha256:index"

    class History:
        @staticmethod
        def latest_change() -> LatestChange:
            return LatestChange()

        @staticmethod
        def latest() -> LatestSnapshot:
            return LatestSnapshot()

    class Handle:
        @staticmethod
        def provenance() -> SimpleNamespace:
            return SimpleNamespace(mutable=True)

        @staticmethod
        def content_digest() -> str:
            return "sha256:content"

        @staticmethod
        def target_index() -> TargetIndex:
            return TargetIndex()

        @staticmethod
        def target_metadata_for_section(section: str) -> Metadata:
            return Metadata()

        @staticmethod
        def history(limit: int) -> History:
            assert limit == 20
            return History()

    read_only = Handle()
    update = Handle()
    namespace["_canonical_company_memory"] = lambda inputs: read_only

    class Inputs:
        @staticmethod
        def dynamic_skill(role: str, *, variables: dict[str, object]) -> Handle:
            return update

        @staticmethod
        def open_reference(target: str, *, mode: str) -> SimpleNamespace:
            raise PublicReferenceError("public_reference_http_failed")

    result = namespace["_verify_vertex_dynamic_skill_certification"](
        Inputs(),
        {},
    )

    assert result["dynamic_skill_fresh_certification_verified"] is True
    assert result["dynamic_skill_governed_state_verified"] is True
    assert result["dynamic_skill_history_latest_change_verified"] is True
    assert result["dynamic_skill_history_target_index_verified"] is True
    assert result["dynamic_skill_reference_revalidation_status"] == "degraded"
    assert result["dynamic_skill_reference_revalidation_complete"] is False
    assert result["dynamic_skill_web_reference_candidate_count"] == 1
    assert result["dynamic_skill_non_web_reference_count"] == 1
    assert result["dynamic_skill_reference_revalidation_attempt_count"] == 1
    assert result["dynamic_skill_revalidated_reference_count"] == 0
