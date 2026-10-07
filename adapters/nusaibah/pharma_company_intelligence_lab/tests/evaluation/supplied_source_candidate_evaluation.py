from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any
from uuid import UUID

from reference.release_evaluation import evaluate_cases

HERE = Path(__file__).resolve().parent
SUITE_PATH = HERE / "review_evaluation_suite.v1.json"

REPORT_SCHEMA = "pharma_supplied_source_candidate_evaluation.v1"
SAFE_STATUS_SCHEMA = "pharma_supplied_source_candidate_status.v1"
REVIEW_SCHEMA = "pharma_supplied_source_candidate_review.v1"

CANDIDATE_ASSET_KEY = "nusaibah.pharma_company_intelligence_lab_evaluation"
CANDIDATE_ASSET_VERSION = "0.2.1"
CANDIDATE_ASSET_IDENTITY = f"{CANDIDATE_ASSET_KEY}:{CANDIDATE_ASSET_VERSION}"
CANDIDATE_VERSIONS = ("0.2.1", "0.2.2")

CASE_STATUSES = frozenset({"evaluated", "blocked", "not_executable", "pending_review"})
EXPECTED_DECISIONS = frozenset({"matched", "missed"})
OBSERVED_DECISIONS = frozenset({"matched_expected", "supported_additional", "unsupported"})
CRITICALITY = frozenset({"noncritical", "high"})

WRONG_ENTITY_FLAGS = frozenset({"wrong_entity_distractor", "wrong_company_distractor"})
INACCESSIBLE_FLAGS = frozenset({"inaccessible", "no_source_access"})

MAX_UNITS = 12
MAX_EXECUTABLE_TARGET_CHUNKS = 4
MAX_UNIT_CHARS = 6000
MAX_SOURCE_CHARS = 24000
MAX_RELATED_LOCATORS = 3

# Reuse only the unchanged, standard-library-only source preparation contract.
# Loading this module and calling prepare_review never invokes an Agent.
_SOURCE_PATH = HERE.parents[2] / "pharma_company_intelligence_lab_evaluation" / "supplied_source_review.py"
_SOURCE_SPEC = importlib.util.spec_from_file_location("candidate_source_contract", _SOURCE_PATH)
SOURCE_REVIEW = importlib.util.module_from_spec(_SOURCE_SPEC)
_SOURCE_SPEC.loader.exec_module(SOURCE_REVIEW)


class CandidateEvaluationError(ValueError):
    """Raised when retained candidate evidence is incomplete or inconsistent."""


def _source_contract(version: str) -> Any:
    if version not in CANDIDATE_VERSIONS:
        raise CandidateEvaluationError("Unsupported candidate version.")
    if version == "0.2.1":
        return SOURCE_REVIEW
    # Private package namespace permits reviewed relative imports without
    # inserting an asset directory into sys.path or importing runtime adapters.
    folder = _SOURCE_PATH.parent
    package_name = "_quote_candidate_" + hashlib.sha256(str(folder).encode()).hexdigest()[:16]
    if package_name not in sys.modules:
        package = ModuleType(package_name)
        package.__path__ = [str(folder)]
        sys.modules[package_name] = package
    return importlib.import_module(package_name + ".supplied_source_quote_review")


def _candidate_version(context: dict[str, Any]) -> str:
    version = context.get("candidate_asset_version", CANDIDATE_ASSET_VERSION)
    if not isinstance(version, str) or version not in CANDIDATE_VERSIONS:
        raise CandidateEvaluationError("Unsupported candidate version.")
    return version


def _canonical_digest(value: Any) -> str:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CandidateEvaluationError("Evaluation evidence must be JSON-compatible.") from exc
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def load_json(path: Path) -> dict[str, Any]:
    """Load one JSON object from disk."""
    return _load_json_with_digest(path)[0]


def _load_json_with_digest(path: Path) -> tuple[dict[str, Any], str]:
    payload = path.read_bytes()
    value = json.loads(payload.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise CandidateEvaluationError(f"{path.name} must contain a JSON object.")
    return value, hashlib.sha256(payload).hexdigest()


def _nonempty_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CandidateEvaluationError(f"{field} must be non-empty text.")
    return value.strip()


def _require_exact_keys(value: Any, expected: set[str], *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise CandidateEvaluationError(f"{field} fields do not match the required contract.")
    return value


def find_fixture(suite: dict[str, Any], case_id: str) -> dict[str, Any]:
    """Return exactly one adjudicated fixture by immutable case ID."""
    matches = [
        case
        for case in suite.get("cases", [])
        if isinstance(case, dict) and case.get("case_id") == case_id
    ]
    if len(matches) != 1:
        raise CandidateEvaluationError(f"Expected exactly one fixture for case_id={case_id!r}.")

    case = matches[0]
    _require_development_case(case)
    if case.get("adjudication", {}).get("status") != "adjudicated":
        raise CandidateEvaluationError("Candidate evaluation requires an adjudicated fixture.")
    adjudication = case["adjudication"]
    _nonempty_text(adjudication.get("primary_reviewer"), field="fixture.primary_reviewer")
    if adjudication.get("disagreement"):
        _nonempty_text(adjudication.get("secondary_reviewer"), field="fixture.secondary_reviewer")
    if case.get("source_identity", {}).get("digest_status") != "frozen":
        raise CandidateEvaluationError("Candidate fixture source digest must be frozen.")

    expected_digest = case.get("source_identity", {}).get("content_sha256")
    actual_digest = hashlib.sha256(
        json.dumps(
            case.get("source_units"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    if expected_digest != actual_digest:
        raise CandidateEvaluationError("Fixture source digest no longer matches adjudicated content.")

    return case


def _require_development_case(case: dict[str, Any]) -> None:
    if case.get("split") == "held_out":
        raise CandidateEvaluationError(
            "Held-out evaluation requires a reviewed development-freeze contract; "
            "this evaluator admits development cases only."
        )
    if case.get("split") != "development":
        raise CandidateEvaluationError("Fixture split must be development.")


def assess_fixture_compatibility(case: dict[str, Any]) -> dict[str, Any]:
    """Classify static compatibility with the 0.2.1 supplied-source contract."""
    reasons: list[str] = []
    source_units = case.get("source_units")

    if case.get("mode") != "company_research":
        reasons.append("candidate_mode_not_supported")

    if not isinstance(source_units, list) or not source_units:
        reasons.append("source_units_missing")
    else:
        if len(source_units) > MAX_UNITS:
            reasons.append("source_unit_limit_exceeded")

        total_chars = 0
        for unit in source_units:
            if not isinstance(unit, dict):
                reasons.append("source_unit_invalid")
                continue
            text = unit.get("text")
            if not isinstance(text, str):
                reasons.append("source_text_invalid")
                continue
            total_chars += len(text)
            if len(text) > MAX_UNIT_CHARS:
                reasons.append("source_unit_character_limit_exceeded")

            related = unit.get("related_locators", [])
            if not isinstance(related, list) or len(related) > MAX_RELATED_LOCATORS:
                reasons.append("related_locator_limit_exceeded")

        if total_chars > MAX_SOURCE_CHARS:
            reasons.append("source_character_limit_exceeded")

    reasons = sorted(set(reasons))
    return {
        "status": "not_executable" if reasons else "compatible_pending_input_projection",
        "reason_codes": reasons,
    }


def validate_inputs_against_fixture(
    case: dict[str, Any],
    inputs: dict[str, Any],
    *, candidate_version: str = CANDIDATE_ASSET_VERSION,
) -> dict[str, Any]:
    """Validate a truth-free 0.2.1 input projection against one adjudicated fixture."""
    _require_development_case(case)
    source_contract = _source_contract(candidate_version)
    try:
        prepared = source_contract.prepare_review(inputs)
    except source_contract.SourceReviewError as exc:
        raise CandidateEvaluationError(
            "Candidate preflight rejected the input projection: "
            + exc.proof_failure_detail["rule"]
        ) from exc
    _require_exact_keys(inputs, {"evaluation_case", "variables"}, field="inputs")
    variables = _require_exact_keys(
        inputs["variables"],
        {"execution_purpose"},
        field="inputs.variables",
    )
    if variables["execution_purpose"] != "supplied_source_review":
        raise CandidateEvaluationError("inputs.variables.execution_purpose must be supplied_source_review.")

    evaluation_case = _require_exact_keys(
        inputs["evaluation_case"],
        {"records"},
        field="inputs.evaluation_case",
    )
    records = evaluation_case["records"]
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        raise CandidateEvaluationError("inputs.evaluation_case.records must contain exactly one object.")

    record = _require_exact_keys(
        records[0],
        {"case_id", "mode", "synthetic", "entity_id", "entity_name", "source_units"},
        field="inputs.evaluation_case.records[0]",
    )
    if record["case_id"] != case["case_id"]:
        raise CandidateEvaluationError("Input case_id does not match the adjudicated fixture.")
    if record["mode"] != "supplied_source_review" or record["synthetic"] is not True:
        raise CandidateEvaluationError("Input case must use synthetic supplied_source_review mode.")

    target_entity_id = _nonempty_text(record["entity_id"], field="inputs.entity_id")
    _nonempty_text(record["entity_name"], field="inputs.entity_name")

    projected_units = record["source_units"]
    fixture_units = case.get("source_units")
    if not isinstance(projected_units, list) or not isinstance(fixture_units, list):
        raise CandidateEvaluationError("Input and fixture source_units must be lists.")
    if len(projected_units) != len(fixture_units):
        raise CandidateEvaluationError("Input projection must preserve every fixture source unit exactly once.")

    fixture_by_locator: dict[str, dict[str, Any]] = {}
    for unit in fixture_units:
        locator = _nonempty_text(unit.get("locator"), field="fixture.source_units.locator")
        if locator in fixture_by_locator:
            raise CandidateEvaluationError("Fixture contains duplicate source locators.")
        fixture_by_locator[locator] = unit

    projected_by_locator: dict[str, dict[str, Any]] = {}
    target_chunk_count = 0
    target_chars = 0
    for index, unit in enumerate(projected_units):
        if not isinstance(unit, dict):
            raise CandidateEvaluationError(f"inputs.source_units[{index}] must be an object.")
        required = {"locator", "entity_id", "text"}
        optional = {"accessible", "related_locators"}
        if not required <= set(unit) or set(unit) - required - optional:
            raise CandidateEvaluationError("Input source unit fields exceed the supplied-source contract.")

        locator = _nonempty_text(unit.get("locator"), field=f"inputs.source_units[{index}].locator")
        if locator in projected_by_locator:
            raise CandidateEvaluationError("Input projection contains duplicate source locators.")
        projected_by_locator[locator] = unit

        fixture_unit = fixture_by_locator.get(locator)
        if fixture_unit is None:
            raise CandidateEvaluationError("Input projection contains a locator absent from the fixture.")
        if unit.get("text") != fixture_unit.get("text"):
            raise CandidateEvaluationError("Input projection changed frozen fixture source text.")

        flags = set(fixture_unit.get("quality_flags", []))
        projected_entity_id = _nonempty_text(
            unit.get("entity_id"),
            field=f"inputs.source_units[{index}].entity_id",
        )
        if flags & WRONG_ENTITY_FLAGS:
            if projected_entity_id == target_entity_id:
                raise CandidateEvaluationError("Wrong-company fixture text must not be projected as the target entity.")
        elif projected_entity_id != target_entity_id:
            raise CandidateEvaluationError("Target fixture text must retain the target entity identity.")

        expected_accessible = not bool(flags & INACCESSIBLE_FLAGS)
        actual_accessible = unit.get("accessible", True)
        if actual_accessible is not expected_accessible:
            raise CandidateEvaluationError("Input source accessibility does not match the frozen fixture.")

        fixture_related = fixture_unit.get("related_locators", [])
        projected_related = unit.get("related_locators", [])
        if projected_related != fixture_related:
            raise CandidateEvaluationError("Input related_locators must match the frozen fixture exactly.")

        if projected_entity_id == target_entity_id and expected_accessible:
            target_chunk_count += 1
            target_chars += len(unit.get("text", ""))

    if set(projected_by_locator) != set(fixture_by_locator):
        raise CandidateEvaluationError("Input projection must preserve the exact fixture locator set.")
    if target_chunk_count > MAX_EXECUTABLE_TARGET_CHUNKS:
        raise CandidateEvaluationError("Input projection exceeds the 0.2.1 executable target-chunk limit.")
    if target_chars > MAX_SOURCE_CHARS:
        raise CandidateEvaluationError("Input projection exceeds the 0.2.1 source character limit.")

    return {
        "candidate_asset_version": candidate_version,
        "case_id": record["case_id"],
        "target_entity_id": target_entity_id,
        "target_entity_name": record["entity_name"],
        "source_units_by_locator": projected_by_locator,
        "target_chunk_count": target_chunk_count,
        "prepared_review": prepared,
    }


def _validate_summary_agreement(
    result: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    comparisons = {
        "review_outcome": result.get("review_outcome"),
        "execution_state": result.get("execution_state"),
        "agent_call_count": result.get("agent_call_count"),
        "mutable_call_count": result.get("mutable_call_count"),
        "preview_only": result.get("preview_only"),
        "publication_allowed": result.get("publication_allowed"),
        "baseline_comparable": result.get("baseline_comparable"),
        "external_truth_verified": result.get("external_truth_verified"),
        "accepted_finding_count": len(result.get("accepted_findings", [])),
        "withheld_finding_count": len(result.get("withheld_findings", [])),
    }
    if result.get("schema_version") == "supplied_source_review_result.v2":
        comparisons["child_call_count"] = result.get("child_call_count")
    for field, expected in comparisons.items():
        if type(summary.get(field)) is not type(expected) or summary.get(field) != expected:
            raise CandidateEvaluationError(f"evaluation_summary disagrees with evaluation_result on {field}.")


def validate_retained_result(
    case: dict[str, Any],
    input_context: dict[str, Any],
    retained: dict[str, Any],
) -> dict[str, Any]:
    """Validate retained-result identity, source spans, accounting and summary agreement."""
    if retained.get("schema_version") != "adapter_preview_result.v1":
        raise CandidateEvaluationError("Unexpected retained preview schema.")

    run_uuid = _nonempty_text(retained.get("run_uuid"), field="retained.run_uuid")
    try:
        if str(UUID(run_uuid)) != run_uuid:
            raise ValueError("noncanonical UUID")
    except ValueError as exc:
        raise CandidateEvaluationError("retained.run_uuid must be a canonical UUID.") from exc
    version = _candidate_version(input_context)
    source_contract = _source_contract(version)
    if retained.get("asset_identity") != f"{CANDIDATE_ASSET_KEY}:{version}":
        raise CandidateEvaluationError("Retained result is not for the explicitly selected candidate asset.")

    outputs = retained.get("outputs")
    if not isinstance(outputs, dict):
        raise CandidateEvaluationError("Retained result outputs are required.")
    result = outputs.get("evaluation_result")
    summary = outputs.get("evaluation_summary")
    if not isinstance(result, dict) or not isinstance(summary, dict):
        raise CandidateEvaluationError("Retained result must include evaluation_result and evaluation_summary.")
    suffix = "v2" if version == "0.2.2" else "v1"
    if (result.get("schema_version") != f"supplied_source_review_result.{suffix}"
            or summary.get("schema_version") != f"pharma_supplied_source_review_summary.{suffix}"
            or result.get("scope") != "focused_company_review"
            or result.get("synthetic") is not True):
        raise CandidateEvaluationError("Retained result scope or schema differs from the candidate contract.")

    if result.get("case_id") != case["case_id"]:
        raise CandidateEvaluationError("Retained result case_id does not match the fixture.")
    if result.get("entity_id") != input_context["target_entity_id"]:
        raise CandidateEvaluationError("Retained result entity_id does not match the projected target.")
    if result.get("execution_state") != "completed":
        raise CandidateEvaluationError("Candidate quality scoring requires a completed result.")
    if result.get("preview_only") is not True or result.get("publication_allowed") is not False:
        raise CandidateEvaluationError("Candidate result must remain preview-only with publication disabled.")
    if result.get("baseline_comparable") is not False:
        raise CandidateEvaluationError("0.2.1 supplied-source results must remain baseline_comparable=false.")
    if result.get("external_truth_verified") is not False:
        raise CandidateEvaluationError("Supplied-source preview must not claim external truth verification.")

    accepted = result.get("accepted_findings")
    withheld = result.get("withheld_findings")
    coverage = result.get("coverage")
    inventory = result.get("source_inventory")
    plan = result.get("plan")
    if not isinstance(accepted, list) or not isinstance(withheld, list):
        raise CandidateEvaluationError("Retained findings collections are invalid.")
    if not isinstance(coverage, list) or not isinstance(inventory, list) or not isinstance(plan, dict):
        raise CandidateEvaluationError("Retained coverage, source inventory and plan are required.")

    prepared = input_context["prepared_review"]
    if result.get("snapshot_id") != prepared["snapshot_id"]:
        raise CandidateEvaluationError("Retained snapshot does not bind to the exact input projection.")
    if _canonical_digest(plan) != _canonical_digest(prepared["plan"]):
        raise CandidateEvaluationError("Retained plan does not match the candidate's canonical finite plan.")
    chunks = {chunk["chunk_id"]: chunk for chunk in prepared["chunks"]}

    _validate_summary_agreement(result, summary)

    source_units = input_context["source_units_by_locator"]
    inventory_by_locator: dict[str, dict[str, Any]] = {}
    for item in inventory:
        if not isinstance(item, dict):
            raise CandidateEvaluationError("source_inventory entries must be objects.")
        locator = item.get("locator")
        if not isinstance(locator, str) or locator not in source_units or locator in inventory_by_locator:
            raise CandidateEvaluationError("source_inventory must account for each input locator exactly once.")
        inventory_by_locator[locator] = item
    if set(inventory_by_locator) != set(source_units):
        raise CandidateEvaluationError("source_inventory does not cover the exact input locator set.")

    for locator, unit in source_units.items():
        disposition = inventory_by_locator[locator].get("disposition")
        if unit["entity_id"] != input_context["target_entity_id"]:
            if disposition != "excluded_by_entity":
                raise CandidateEvaluationError("Wrong-company input was not excluded by entity.")
        elif unit.get("accessible", True) is False:
            if disposition != "inaccessible":
                raise CandidateEvaluationError("Inaccessible target source was not accounted for as inaccessible.")

    for expected in prepared["inventory"]:
        actual = inventory_by_locator[expected["locator"]]
        expected = dict(expected)
        if expected["disposition"] == "assigned":
            if actual.get("disposition") not in {"reviewed", "unreviewed"}:
                raise CandidateEvaluationError("Target source disposition is inconsistent with its plan.")
            expected["disposition"] = actual["disposition"]
        if actual != expected:
            raise CandidateEvaluationError("Source inventory differs from the canonical source/chunk mapping.")

    accepted_by_id: dict[str, dict[str, Any]] = {}
    accepted_ids_in_coverage: set[str] = set()
    runtime_obligations_disposed = True
    expected_rows = {
        (chunk["chunk_id"], role, requirement): chunk["primary_locator"]
        for chunk in chunks.values()
        for role, requirements in SOURCE_REVIEW.ROLES.items()
        for requirement in requirements
    }
    rows_by_identity = {}
    all_finding_ids = set()
    for row in coverage:
        if not isinstance(row, dict):
            raise CandidateEvaluationError("coverage rows must be objects.")
        identity = (row.get("chunk_id"), row.get("role"), row.get("requirement_id"))
        if (not all(isinstance(value, str) for value in identity)
                or identity not in expected_rows or identity in rows_by_identity
                or row.get("primary_locator") != expected_rows[identity]):
            raise CandidateEvaluationError("Coverage must represent each planned obligation exactly once.")
        rows_by_identity[identity] = row
        if type(row.get("reviewed")) is not bool or type(row.get("unrepresented_evidence")) is not bool:
            raise CandidateEvaluationError("Coverage review flags must be booleans.")
        if row.get("reviewed") is not True or row.get("unrepresented_evidence") is True:
            runtime_obligations_disposed = False
        ids = row.get("accepted_finding_ids", [])
        if not isinstance(ids, list):
            raise CandidateEvaluationError("coverage.accepted_finding_ids must be a list.")
        finding_ids = row.get("finding_ids")
        if (not isinstance(finding_ids, list)
                or len(finding_ids) > SOURCE_REVIEW.MAX_FINDINGS_PER_REQUIREMENT
                or not all(isinstance(fid, str) and fid for fid in finding_ids + ids)
                or len(set(finding_ids)) != len(finding_ids)
                or len(set(ids)) != len(ids)
                or not set(ids) <= set(finding_ids)
                or set(finding_ids) & all_finding_ids):
            raise CandidateEvaluationError("Coverage finding references are invalid or duplicated.")
        if (row.get("specialist_disposition") != ("findings" if finding_ids else "no_evidence")
                or row.get("evidence_state") != ("supported" if ids else "insufficient")):
            raise CandidateEvaluationError("Coverage evidence state disagrees with finding disposition.")
        all_finding_ids.update(finding_ids)
        for finding_id in ids:
            if isinstance(finding_id, str):
                accepted_ids_in_coverage.add(finding_id)
    if set(rows_by_identity) != set(expected_rows):
        raise CandidateEvaluationError("Coverage is missing planned obligations.")

    for finding in accepted:
        if not isinstance(finding, dict):
            raise CandidateEvaluationError("accepted_findings entries must be objects.")
        finding_id = _nonempty_text(finding.get("finding_id"), field="accepted_findings.finding_id")
        if finding_id in accepted_by_id:
            raise CandidateEvaluationError("accepted_findings contains duplicate finding IDs.")
        accepted_by_id[finding_id] = finding

        if finding.get("entity_id") != input_context["target_entity_id"]:
            raise CandidateEvaluationError("Accepted finding belongs to the wrong entity.")
        if finding.get("snapshot_id") != result.get("snapshot_id"):
            raise CandidateEvaluationError("Accepted finding snapshot_id does not match the result snapshot.")
        identity = (finding.get("chunk_id"), finding.get("role"), finding.get("requirement_id"))
        if not all(isinstance(value, str) for value in identity) or identity not in rows_by_identity:
            raise CandidateEvaluationError("Accepted finding does not belong to a planned obligation.")
        row = rows_by_identity[identity]
        if finding_id not in row["accepted_finding_ids"]:
            raise CandidateEvaluationError("Accepted finding is attached to a different coverage obligation.")

        evidence = finding.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise CandidateEvaluationError("Every accepted finding must include cited supplied evidence.")
        seen_spans = set()
        for citation in evidence:
            _require_exact_keys(citation, {"locator", "start", "end", "quote"}, field="finding.evidence")
            locator = citation.get("locator")
            if not isinstance(locator, str):
                raise CandidateEvaluationError("Finding evidence locator must be text.")
            unit = source_units.get(locator)
            if unit is None:
                raise CandidateEvaluationError("Finding cites a locator absent from the exact input.")
            if unit["entity_id"] != input_context["target_entity_id"]:
                raise CandidateEvaluationError("Accepted finding cites wrong-company evidence.")
            start = citation.get("start")
            end = citation.get("end")
            quote = citation.get("quote")
            text = unit.get("text")
            if (
                isinstance(start, bool)
                or isinstance(end, bool)
                or not isinstance(start, int)
                or not isinstance(end, int)
                or not isinstance(text, str)
                or start < 0
                or end <= start
                or end > len(text)
                or quote != text[start:end]
            ):
                raise CandidateEvaluationError("Finding citation does not match the exact source span.")
            chunk_locators = {unit["locator"] for unit in chunks[identity[0]]["units"]}
            if locator not in chunk_locators:
                raise CandidateEvaluationError("Finding evidence was not in the declared source chunk.")
            span = (locator, start, end)
            if span in seen_spans:
                raise CandidateEvaluationError("Finding contains duplicate evidence spans.")
            seen_spans.add(span)

        material_fields = {"entity_id", "snapshot_id", "chunk_id", "role", "requirement_id", "ordinal", "statement", "evidence"}
        if not material_fields <= set(finding):
            raise CandidateEvaluationError("Accepted finding is missing canonical material.")
        material = {key: finding[key] for key in material_fields}
        if finding.get("provenance_strength") != "inspected_supplied_span" or finding.get("external_truth_verified") is not False:
            raise CandidateEvaluationError("Accepted finding must preserve supplied-source provenance limits.")
        if (type(finding["ordinal"]) is not int
                or finding["ordinal"] != row["finding_ids"].index(finding_id)
                or not SOURCE_REVIEW._text(finding["statement"], 600)
                or not 1 <= len(evidence) <= SOURCE_REVIEW.MAX_EVIDENCE_PER_FINDING
                or any(not SOURCE_REVIEW._text(ref["quote"], 600) for ref in evidence)
                or _canonical_digest(material) != finding_id):
            raise CandidateEvaluationError("Accepted finding identity does not bind to its exact material.")

        local_material = {
            "finding": {**material, "finding_id": finding_id},
            "source_units": chunks[identity[0]]["units"],
            "methodology_digest": prepared["plan"]["methodology_digest"],
        }

        for verification_field in ("verification", "global_verification"):
            verification = finding.get(verification_field)
            if not isinstance(verification, dict):
                raise CandidateEvaluationError(f"Accepted finding lacks {verification_field}.")
            if verification.get("finding_id") != finding_id or verification.get("state") != "supported":
                raise CandidateEvaluationError(f"Accepted finding {verification_field} is inconsistent.")
            verdict_material = (local_material if verification_field == "verification" else
                                {**material, "finding_id": finding_id, "verification": finding["verification"]})
            if verification.get("input_digest") != _canonical_digest(verdict_material):
                raise CandidateEvaluationError(f"Accepted finding {verification_field} digest is inconsistent.")

    if set(accepted_by_id) != accepted_ids_in_coverage:
        raise CandidateEvaluationError("Coverage accepted_finding_ids do not match accepted_findings exactly.")

    withheld_ids = set()
    for finding in withheld:
        if not isinstance(finding, dict):
            raise CandidateEvaluationError("Withheld finding entries must be objects.")
        fid = finding.get("finding_id")
        identity = (finding.get("chunk_id"), finding.get("role"), finding.get("requirement_id"))
        if (not isinstance(fid, str) or fid in withheld_ids or fid in accepted_by_id
                or not all(isinstance(value, str) for value in identity)
                or identity not in rows_by_identity or fid not in rows_by_identity[identity]["finding_ids"]
                or finding.get("state") not in {"contradicted", "insufficient", "wrong_entity", "unreviewed_context"}):
            raise CandidateEvaluationError("Withheld finding identity or disposition is inconsistent.")
        withheld_ids.add(fid)
    if set(accepted_by_id) | withheld_ids != all_finding_ids:
        raise CandidateEvaluationError("Coverage finding IDs do not account for accepted and withheld findings.")

    for expected in prepared["inventory"]:
        if expected["disposition"] != "assigned":
            continue
        rows = [row for identity, row in rows_by_identity.items() if identity[0] == expected["chunk_id"]]
        reviewed = all(row["reviewed"] and not row["unrepresented_evidence"] for row in rows)
        if inventory_by_locator[expected["locator"]]["disposition"] != ("reviewed" if reviewed else "unreviewed"):
            raise CandidateEvaluationError("Source disposition disagrees with planned obligation coverage.")
        if not reviewed and any(row["accepted_finding_ids"] for row in rows):
            raise CandidateEvaluationError("Incomplete chunks cannot retain accepted findings.")

    incomplete = (not runtime_obligations_disposed
                  or any(item["disposition"] == "inaccessible" for item in prepared["inventory"]))
    has_gaps = bool(withheld) or any(row["evidence_state"] != "supported" for row in coverage)
    expected_outcome = ("review_incomplete" if incomplete else
                        "review_complete_with_evidence_gaps" if has_gaps else "review_complete")
    if result.get("review_outcome") != expected_outcome:
        raise CandidateEvaluationError("Review outcome disagrees with source and obligation accounting.")

    logical_call_limit = plan.get("logical_call_limit")
    agent_call_count = result.get("agent_call_count")
    if (
        isinstance(logical_call_limit, bool)
        or not isinstance(logical_call_limit, int)
        or isinstance(agent_call_count, bool)
        or not isinstance(agent_call_count, int)
        or agent_call_count < len(chunks) * 4
        or agent_call_count > logical_call_limit
        or (accepted and agent_call_count != logical_call_limit)
        or (not all_finding_ids and agent_call_count != len(chunks) * 4)
    ):
        raise CandidateEvaluationError("Agent call count exceeds or cannot be checked against the plan.")

    if type(result.get("mutable_call_count")) is not int or result.get("mutable_call_count") != 0:
        raise CandidateEvaluationError("Candidate evaluation requires zero mutable calls.")

    if type(summary.get("chunk_count")) is not int or summary.get("chunk_count") != len(plan["chunk_ids"]):
        raise CandidateEvaluationError("evaluation_summary.chunk_count disagrees with the finite plan.")

    if version == "0.2.2":
        try:
            source_contract.validate_resolution_receipts(result, prepared)
        except (source_contract.SourceReviewError, KeyError, TypeError, ValueError) as exc:
            raise CandidateEvaluationError("Candidate span-resolution receipts are invalid.") from exc

    return {
        "candidate_asset_version": version,
        "run_uuid": run_uuid,
        "result": result,
        "summary": summary,
        "accepted_by_id": accepted_by_id,
        "runtime_obligations_disposed": runtime_obligations_disposed,
        "logical_call_limit": logical_call_limit,
    }


def build_review_template(
    suite: dict[str, Any],
    case: dict[str, Any],
    retained_context: dict[str, Any],
    *,
    inputs_file_sha256: str,
    retained_file_sha256: str,
) -> dict[str, Any]:
    """Build a reviewer receipt bound to exact fixture, input and retained-result bytes."""
    _require_development_case(case)
    result = retained_context["result"]
    return {
        "schema_version": REVIEW_SCHEMA,
        "suite_id": suite.get("suite_id"),
        "suite_input_digest": _canonical_digest(suite),
        "case_id": case["case_id"],
        "split": case["split"],
        "fixture_source_sha256": case["source_identity"]["content_sha256"],
        "methodology_digest": case["methodology_identity"]["skill_digest"],
        "candidate_methodology_digest": result["plan"]["methodology_digest"],
        "candidate_asset": {
            "asset_key": CANDIDATE_ASSET_KEY,
            "asset_version": _candidate_version(retained_context),
        },
        "run_uuid": retained_context["run_uuid"],
        "inputs_file_sha256": inputs_file_sha256,
        "retained_result_file_sha256": retained_file_sha256,
        "reviewer": {
            "name": None,
            "qualification_basis": None,
        },
        "expected_finding_decisions": [
            {
                "expected_finding_id": item["finding_id"],
                "decision": "pending",
                "observed_finding_id": None,
                "notes": None,
            }
            for item in case["candidate_expected_findings"]
        ],
        "observed_finding_decisions": [
            {
                "observed_finding_id": item["finding_id"],
                "decision": "pending",
                "expected_finding_id": None,
                "criticality": None,
                "notes": None,
            }
            for item in result["accepted_findings"]
        ],
        "fixture_obligations": [
            {
                "requirement_id": requirement_id,
                "disposed": None,
                "notes": None,
            }
            for requirement_id in case["applicable_requirements"]
        ],
        "truthful_incomplete": None,
        "case_status": "pending_review",
        "status_reason": None,
        "notes": None,
    }


def _validate_review_bindings(
    suite: dict[str, Any],
    case: dict[str, Any],
    retained_context: dict[str, Any],
    review: dict[str, Any],
    *,
    inputs_file_sha256: str,
    retained_file_sha256: str,
) -> str:
    if review.get("schema_version") != REVIEW_SCHEMA:
        raise CandidateEvaluationError("Unsupported candidate-review schema.")
    if review.get("suite_id") != suite.get("suite_id"):
        raise CandidateEvaluationError("Review suite identity mismatch.")
    if review.get("suite_input_digest") != _canonical_digest(suite):
        raise CandidateEvaluationError("Review does not bind to the exact current adjudicated suite.")
    if review.get("case_id") != case["case_id"] or review.get("split") != case["split"]:
        raise CandidateEvaluationError("Review case identity or split mismatch.")
    if review.get("fixture_source_sha256") != case["source_identity"]["content_sha256"]:
        raise CandidateEvaluationError("Review fixture digest mismatch.")
    if review.get("methodology_digest") != case["methodology_identity"]["skill_digest"]:
        raise CandidateEvaluationError("Review methodology digest mismatch.")
    if review.get("candidate_methodology_digest") != retained_context["result"]["plan"]["methodology_digest"]:
        raise CandidateEvaluationError("Review candidate methodology digest mismatch.")
    if review.get("candidate_asset") != {
        "asset_key": CANDIDATE_ASSET_KEY,
        "asset_version": _candidate_version(retained_context),
    }:
        raise CandidateEvaluationError("Review candidate asset identity mismatch.")
    if review.get("run_uuid") != retained_context["run_uuid"]:
        raise CandidateEvaluationError("Review run identity mismatch.")
    if review.get("inputs_file_sha256") != inputs_file_sha256:
        raise CandidateEvaluationError("Review input-file digest mismatch.")
    if review.get("retained_result_file_sha256") != retained_file_sha256:
        raise CandidateEvaluationError("Review retained-result digest mismatch.")

    case_status = review.get("case_status")
    if case_status not in CASE_STATUSES:
        raise CandidateEvaluationError("Review case_status is invalid.")
    return case_status


def _validate_evaluated_review(
    case: dict[str, Any],
    retained_context: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, dict):
        raise CandidateEvaluationError("reviewer must be an object.")
    _nonempty_text(reviewer.get("name"), field="reviewer.name")
    _nonempty_text(reviewer.get("qualification_basis"), field="reviewer.qualification_basis")

    expected_truth = {item["finding_id"]: item for item in case["candidate_expected_findings"]}
    accepted = retained_context["accepted_by_id"]

    expected_decisions = review.get("expected_finding_decisions")
    if not isinstance(expected_decisions, list):
        raise CandidateEvaluationError("expected_finding_decisions must be a list.")
    expected_by_id: dict[str, dict[str, Any]] = {}
    for item in expected_decisions:
        if not isinstance(item, dict):
            raise CandidateEvaluationError("Expected finding decisions must be objects.")
        expected_id = item.get("expected_finding_id")
        if expected_id not in expected_truth or expected_id in expected_by_id:
            raise CandidateEvaluationError("Expected finding decisions must cover each fixture finding exactly once.")
        if item.get("decision") not in EXPECTED_DECISIONS:
            raise CandidateEvaluationError("Expected finding decision must be matched or missed.")
        observed_id = item.get("observed_finding_id")
        if item["decision"] == "matched":
            if observed_id not in accepted:
                raise CandidateEvaluationError("Matched expected finding must reference an accepted observed finding.")
        elif observed_id is not None:
            raise CandidateEvaluationError("Missed expected finding cannot reference an observed finding.")
        _nonempty_text(item.get("notes"), field=f"expected_finding_decisions[{expected_id}].notes")
        expected_by_id[expected_id] = item
    if set(expected_by_id) != set(expected_truth):
        raise CandidateEvaluationError("Expected finding decisions do not cover the exact fixture truth set.")

    observed_decisions = review.get("observed_finding_decisions")
    if not isinstance(observed_decisions, list):
        raise CandidateEvaluationError("observed_finding_decisions must be a list.")
    observed_by_id: dict[str, dict[str, Any]] = {}
    for item in observed_decisions:
        if not isinstance(item, dict):
            raise CandidateEvaluationError("Observed finding decisions must be objects.")
        observed_id = item.get("observed_finding_id")
        if observed_id not in accepted or observed_id in observed_by_id:
            raise CandidateEvaluationError("Observed finding decisions must cover each accepted finding exactly once.")
        decision = item.get("decision")
        if decision not in OBSERVED_DECISIONS:
            raise CandidateEvaluationError("Observed finding decision is invalid.")
        expected_id = item.get("expected_finding_id")
        criticality = item.get("criticality")

        if decision == "matched_expected":
            if expected_id not in expected_truth:
                raise CandidateEvaluationError("Matched observed finding must reference fixture truth.")
            reciprocal = expected_by_id[expected_id]
            if reciprocal.get("decision") != "matched" or reciprocal.get("observed_finding_id") != observed_id:
                raise CandidateEvaluationError("Expected and observed match decisions must be reciprocal.")
            expected_criticality = expected_truth[expected_id]["criticality"]
            if criticality not in (None, expected_criticality):
                raise CandidateEvaluationError("Matched finding criticality must agree with fixture truth.")
        else:
            if expected_id is not None:
                raise CandidateEvaluationError("Additional or unsupported findings cannot claim an expected_finding_id.")
            if criticality not in CRITICALITY:
                raise CandidateEvaluationError("Additional or unsupported findings require reviewed criticality.")

        _nonempty_text(item.get("notes"), field=f"observed_finding_decisions[{observed_id}].notes")
        observed_by_id[observed_id] = item

    if set(observed_by_id) != set(accepted):
        raise CandidateEvaluationError("Observed decisions do not cover the exact accepted finding set.")
    for expected_id, item in expected_by_id.items():
        if item["decision"] == "matched":
            reciprocal = observed_by_id[item["observed_finding_id"]]
            if reciprocal["decision"] != "matched_expected" or reciprocal["expected_finding_id"] != expected_id:
                raise CandidateEvaluationError("Expected and observed match decisions must be reciprocal.")

    obligations = review.get("fixture_obligations")
    if not isinstance(obligations, list):
        raise CandidateEvaluationError("fixture_obligations must be a list.")
    obligation_by_id: dict[str, dict[str, Any]] = {}
    for item in obligations:
        if not isinstance(item, dict):
            raise CandidateEvaluationError("Fixture obligation decisions must be objects.")
        requirement_id = item.get("requirement_id")
        if requirement_id not in case["applicable_requirements"] or requirement_id in obligation_by_id:
            raise CandidateEvaluationError("Fixture obligations must cover each applicable requirement exactly once.")
        if not isinstance(item.get("disposed"), bool):
            raise CandidateEvaluationError("fixture_obligations.disposed must be boolean.")
        _nonempty_text(item.get("notes"), field=f"fixture_obligations[{requirement_id}].notes")
        obligation_by_id[requirement_id] = item
    if set(obligation_by_id) != set(case["applicable_requirements"]):
        raise CandidateEvaluationError("Fixture obligations do not cover the exact requirement set.")

    truthful_incomplete = review.get("truthful_incomplete")
    if not isinstance(truthful_incomplete, bool):
        raise CandidateEvaluationError("truthful_incomplete must be boolean for an evaluated case.")
    if case["candidate_expected_complete"] and truthful_incomplete:
        raise CandidateEvaluationError("A fixture expected to complete cannot be marked truthful_incomplete.")
    if truthful_incomplete and retained_context["result"]["review_outcome"] != "review_incomplete":
        raise CandidateEvaluationError("Truthful incomplete requires an actually incomplete business outcome.")

    matched_expected_ids = {
        expected_id
        for expected_id, item in expected_by_id.items()
        if item["decision"] == "matched"
    }
    missed_expected_ids = set(expected_truth) - matched_expected_ids

    noncritical_tp = sum(
        expected_truth[expected_id]["criticality"] == "noncritical"
        for expected_id in matched_expected_ids
    )
    noncritical_fn = sum(
        expected_truth[expected_id]["criticality"] == "noncritical"
        for expected_id in missed_expected_ids
    )
    critical_recovered = sum(
        expected_truth[expected_id]["criticality"] == "high"
        for expected_id in matched_expected_ids
    )
    critical_expected = sum(
        item["criticality"] == "high"
        for item in expected_truth.values()
    )

    supported_additional_noncritical = sum(
        item["decision"] == "supported_additional" and item["criticality"] == "noncritical"
        for item in observed_by_id.values()
    )
    unsupported_noncritical = sum(
        item["decision"] == "unsupported" and item["criticality"] == "noncritical"
        for item in observed_by_id.values()
    )
    unsupported_high = sum(
        item["decision"] == "unsupported" and item["criticality"] == "high"
        for item in observed_by_id.values()
    )
    supported_material_claim_count = sum(
        item["decision"] != "unsupported"
        for item in observed_by_id.values()
    )

    all_fixture_obligations_disposed = all(
        item["disposed"] for item in obligation_by_id.values()
    )
    all_obligations_disposed = (
        all_fixture_obligations_disposed
        and retained_context["runtime_obligations_disposed"]
    )

    metric_case = {
        "material_claim_count": len(accepted),
        "supported_material_claim_count": supported_material_claim_count,
        "noncritical_true_positive": noncritical_tp,
        "noncritical_supported_additional": supported_additional_noncritical,
        "noncritical_false_positive": unsupported_noncritical,
        "noncritical_false_negative": noncritical_fn,
        "critical_expected": critical_expected,
        "critical_recovered": critical_recovered,
        "accepted_unsupported_high_impact": unsupported_high,
        "expected_complete": case["candidate_expected_complete"],
        "truthful_incomplete": truthful_incomplete,
        "all_obligations_disposed": all_obligations_disposed,
        "strata": list(case["strata"]),
    }

    return {
        "metric_case": metric_case,
        "expected_finding_count": len(expected_truth),
        "matched_expected_count": len(matched_expected_ids),
        "missed_expected_count": len(missed_expected_ids),
        "supported_additional_count": sum(
            item["decision"] == "supported_additional"
            for item in observed_by_id.values()
        ),
        "unsupported_accepted_count": sum(
            item["decision"] == "unsupported"
            for item in observed_by_id.values()
        ),
    }


def extract_usage(usage_payload: dict[str, Any] | None, *, run_uuid: str) -> dict[str, Any] | None:
    """Return bounded existing-run usage without inferring missing values."""
    if usage_payload is None:
        return None

    payload_run_uuid = usage_payload.get("run_uuid")
    if payload_run_uuid != run_uuid:
        raise CandidateEvaluationError("Usage evidence belongs to a different run.")

    evidence = usage_payload.get("execution_evidence")
    if evidence is None:
        evidence = usage_payload.get("agent_execution_evidence")
    if not isinstance(evidence, dict):
        raise CandidateEvaluationError("Usage payload does not contain execution evidence.")

    safe: dict[str, Any] = {
        "status": evidence.get("status") if evidence.get("status") in ("available", "partial", "unavailable", "not_available") else None,
        "usage_status": evidence.get("usage_status") if evidence.get("usage_status") in ("provider_reported", "partial", "unknown", "not_reported", "unavailable") else None,
    }
    for field in (
        "receipt_count",
        "completed_invocation_count",
        "agent_call_count",
        "provider_turn_count",
        "tool_call_count",
        "retry_count",
    ):
        value = evidence.get(field)
        safe[field] = value if type(value) is int and value >= 0 else None

    usage = evidence.get("usage")
    safe["usage"] = {}
    if isinstance(usage, dict):
        for field in ("input_tokens", "output_tokens", "thought_tokens", "total_tokens"):
            value = usage.get(field)
            safe["usage"][field] = value if type(value) is int and value >= 0 else None

    return safe


def evaluate_candidate_case(
    suite: dict[str, Any],
    case: dict[str, Any],
    input_context: dict[str, Any],
    retained_context: dict[str, Any],
    review: dict[str, Any],
    *,
    inputs_file_sha256: str,
    retained_file_sha256: str,
    usage_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one retained 0.2.1 candidate result against independently reviewed truth."""
    _require_development_case(case)
    case_status = _validate_review_bindings(
        suite,
        case,
        retained_context,
        review,
        inputs_file_sha256=inputs_file_sha256,
        retained_file_sha256=retained_file_sha256,
    )

    review_result = None
    quality_metrics = None
    metric_case = None
    if case_status == "evaluated":
        review_result = _validate_evaluated_review(case, retained_context, review)
        metric_case = review_result["metric_case"]
        quality_metrics = _candidate_quality_metrics([metric_case])
    else:
        reason = review.get("status_reason")
        _nonempty_text(reason, field="status_reason")

    usage = extract_usage(usage_payload, run_uuid=retained_context["run_uuid"])
    result = retained_context["result"]

    return {
        "schema_version": REPORT_SCHEMA,
        "safe": False,
        "values_included": True,
        "suite_id": suite.get("suite_id"),
        "suite_input_digest": _canonical_digest(suite),
        "candidate_methodology_digest": result["plan"]["methodology_digest"],
        "case_id": case["case_id"],
        "split": case["split"],
        "case_status": case_status,
        "status_reason": review.get("status_reason"),
        "candidate_asset": {
            "asset_key": CANDIDATE_ASSET_KEY,
            "asset_version": _candidate_version(retained_context),
            "baseline_comparable": False,
        },
        "run_uuid": retained_context["run_uuid"],
        "integrity": {
            "fixture_source_digest_verified": True,
            "truth_free_input_projection_verified": True,
            "retained_result_identity_verified": True,
            "citation_spans_verified": True,
            "summary_agreement_verified": True,
            "runtime_call_bound_verified": True,
        },
        "business_outcome": {
            "review_outcome": result.get("review_outcome"),
            "execution_state": result.get("execution_state"),
            "accepted_finding_count": len(result.get("accepted_findings", [])),
            "withheld_finding_count": len(result.get("withheld_findings", [])),
            "runtime_obligations_disposed": retained_context["runtime_obligations_disposed"],
        },
        "review_counts": review_result,
        "metric_case": metric_case,
        "quality_metrics": quality_metrics,
        "usage": usage,
        "frozen_wp1_baseline_completed": False,
        "next_action": (
            "inspect quality blockers before another provider execution"
            if case_status == "evaluated"
            else "resolve the recorded case status before provider execution"
        ),
    }


def safe_status(report: dict[str, Any]) -> dict[str, Any]:
    """Return a text-free status projection suitable for shared progress reporting."""
    metrics = report.get("quality_metrics")
    business = report.get("business_outcome") or {}
    metric_case = report.get("metric_case") or {}
    usage = report.get("usage") or {}

    return {
        "schema_version": SAFE_STATUS_SCHEMA,
        "safe": True,
        "values_included": False,
        "suite_id": report.get("suite_id"),
        "case_id": report.get("case_id"),
        "split": report.get("split"),
        "case_status": report.get("case_status"),
        "run_uuid": report.get("run_uuid"),
        "asset_key": CANDIDATE_ASSET_KEY,
        "asset_version": (report.get("candidate_asset") or {}).get("asset_version", CANDIDATE_ASSET_VERSION),
        "baseline_comparable": False,
        "review_outcome": business.get("review_outcome"),
        "accepted_finding_count": business.get("accepted_finding_count"),
        "withheld_finding_count": business.get("withheld_finding_count"),
        "critical_expected": metric_case.get("critical_expected"),
        "critical_recovered": metric_case.get("critical_recovered"),
        "accepted_unsupported_high_impact": metric_case.get("accepted_unsupported_high_impact"),
        "complete_accounting": metrics.get("complete_accounting") if isinstance(metrics, dict) else None,
        "usage_status": usage.get("usage_status") if isinstance(usage, dict) else None,
        "frozen_wp1_baseline_completed": False,
    }


def _candidate_quality_metrics(metric_cases: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = evaluate_cases(metric_cases)
    supported = sum(case["noncritical_true_positive"] + case.get("noncritical_supported_additional", 0) for case in metric_cases)
    unsupported = sum(case["noncritical_false_positive"] for case in metric_cases)
    metrics["noncritical_precision"] = None if supported + unsupported == 0 else supported / (supported + unsupported)
    return metrics


def aggregate_candidate_reports(
    reports: list[dict[str, Any]], *, expected_case_ids: list[str],
) -> dict[str, Any]:
    """Aggregate finite candidate reports without silently dropping blocked cases."""
    if not reports:
        raise CandidateEvaluationError("At least one candidate report is required.")
    if (not isinstance(expected_case_ids, list) or not expected_case_ids
            or not all(isinstance(case_id, str) and case_id for case_id in expected_case_ids)
            or len(set(expected_case_ids)) != len(expected_case_ids)):
        raise CandidateEvaluationError("A finite list of unique expected case IDs is required.")

    status_counts = {status: 0 for status in sorted(CASE_STATUSES)}
    metric_cases = []
    seen_case_ids = set()
    suite_id = reports[0].get("suite_id")
    suite_digest = reports[0].get("suite_input_digest")
    candidate_asset = reports[0].get("candidate_asset")
    candidate_methodology = reports[0].get("candidate_methodology_digest")
    for report in reports:
        case_id = report.get("case_id")
        if not isinstance(case_id, str) or case_id in seen_case_ids:
            raise CandidateEvaluationError("Candidate batch contains invalid or duplicate case IDs.")
        if (report.get("suite_id") != suite_id or report.get("suite_input_digest") != suite_digest
                or report.get("split") != "development"
                or report.get("candidate_asset") != candidate_asset
                or report.get("candidate_methodology_digest") != candidate_methodology):
            raise CandidateEvaluationError("Candidate batch mixes suite identity, candidate identity, methodology or unadmitted splits.")
        seen_case_ids.add(case_id)
        status = report.get("case_status")
        if status not in CASE_STATUSES:
            raise CandidateEvaluationError("Candidate report has an invalid case_status.")
        status_counts[status] += 1
        metric_case = report.get("metric_case")
        if status == "evaluated":
            if not isinstance(metric_case, dict):
                raise CandidateEvaluationError("Evaluated report is missing metric_case.")
            metric_cases.append(metric_case)
    if seen_case_ids != set(expected_case_ids):
        raise CandidateEvaluationError("Candidate batch does not account for the exact declared case set.")

    return {
        "schema_version": "pharma_supplied_source_candidate_batch.v1",
        "case_count": len(reports),
        "expected_case_count": len(expected_case_ids),
        "status_counts": status_counts,
        "evaluated_quality_metrics": _candidate_quality_metrics(metric_cases) if metric_cases else None,
        "all_cases_evaluated": status_counts["evaluated"] == len(reports),
        "quality_gate": None,
        "quality_gate_reason": "candidate thresholds require an explicit compatibility/calibration decision",
        "frozen_wp1_baseline_completed": False,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    """Emit a bound review template or evaluate a retained candidate result offline."""
    parser = argparse.ArgumentParser(
        description="Evaluate retained 0.2.1 supplied-source previews against adjudicated fixtures."
    )
    parser.add_argument("--suite", default=str(SUITE_PATH))
    parser.add_argument("--candidate-version", choices=CANDIDATE_VERSIONS, default=CANDIDATE_ASSET_VERSION)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--retained-result", required=True)
    parser.add_argument("--usage")
    parser.add_argument("--review-file")
    parser.add_argument("--emit-review-template")
    parser.add_argument("--safe-status-output")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    if bool(args.review_file) == bool(args.emit_review_template):
        parser.error("Choose exactly one of --review-file or --emit-review-template.")

    try:
        return _evaluate_cli(args)
    except (CandidateEvaluationError, OSError, ValueError) as exc:
        report = {
            "schema_version": SAFE_STATUS_SCHEMA, "safe": True, "values_included": False,
            "case_status": "blocked", "failure_code": "candidate_evaluation_evidence_rejected",
            "frozen_wp1_baseline_completed": False,
        }
        if isinstance(exc, CandidateEvaluationError):
            report["message"] = str(exc)
        if args.safe_status_output:
            _write_json(Path(args.safe_status_output), report)
        print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
        return 2


def _evaluate_cli(args: argparse.Namespace) -> int:

    suite_path = Path(args.suite)
    inputs_path = Path(args.inputs)
    retained_path = Path(args.retained_result)

    suite = load_json(suite_path)
    case = find_fixture(suite, args.case_id)

    compatibility = assess_fixture_compatibility(case)
    if compatibility["status"] == "not_executable":
        report = {
            "schema_version": SAFE_STATUS_SCHEMA,
            "safe": True,
            "values_included": False,
            "suite_id": suite.get("suite_id"),
            "suite_input_digest": _canonical_digest(suite),
            "case_id": case["case_id"],
            "split": case["split"],
            "case_status": "not_executable",
            "candidate_asset": {"asset_key": CANDIDATE_ASSET_KEY,
                                "asset_version": args.candidate_version, "baseline_comparable": False},
            "candidate_methodology_digest": _source_contract(args.candidate_version).digest(
                _source_contract(args.candidate_version).METHOD),
            "reason_codes": compatibility["reason_codes"],
            "frozen_wp1_baseline_completed": False,
        }
        if args.safe_status_output:
            _write_json(Path(args.safe_status_output), report)
        print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
        return 0

    inputs, inputs_sha = _load_json_with_digest(inputs_path)
    input_context = validate_inputs_against_fixture(case, inputs, candidate_version=args.candidate_version)
    retained, retained_sha = _load_json_with_digest(retained_path)
    retained_context = validate_retained_result(case, input_context, retained)

    if args.emit_review_template:
        template = build_review_template(
            suite,
            case,
            retained_context,
            inputs_file_sha256=inputs_sha,
            retained_file_sha256=retained_sha,
        )
        _write_json(Path(args.emit_review_template), template)
        report = {
            "schema_version": SAFE_STATUS_SCHEMA,
            "safe": True,
            "values_included": False,
            "suite_id": suite.get("suite_id"),
            "case_id": case["case_id"],
            "split": case["split"],
            "case_status": "pending_review",
            "candidate_asset": {"asset_key": CANDIDATE_ASSET_KEY,
                                "asset_version": args.candidate_version, "baseline_comparable": False},
            "candidate_methodology_digest": retained_context["result"]["plan"]["methodology_digest"],
            "run_uuid": retained_context["run_uuid"],
            "review_template_emitted": True,
            "frozen_wp1_baseline_completed": False,
        }
        if args.safe_status_output:
            _write_json(Path(args.safe_status_output), report)
        print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
        return 0

    review = load_json(Path(args.review_file))
    usage = load_json(Path(args.usage)) if args.usage else None
    report = evaluate_candidate_case(
        suite,
        case,
        input_context,
        retained_context,
        review,
        inputs_file_sha256=inputs_sha,
        retained_file_sha256=retained_sha,
        usage_payload=usage,
    )

    if args.safe_status_output:
        _write_json(Path(args.safe_status_output), safe_status(report))

    print(json.dumps(report, indent=2 if args.pretty else None, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
