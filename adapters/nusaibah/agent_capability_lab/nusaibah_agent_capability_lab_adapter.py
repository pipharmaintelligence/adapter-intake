from __future__ import annotations

from datetime import date
from typing import Any, ClassVar
from urllib.parse import urlsplit

from adapters.base import Adapter
from devtools.agent_citation_view import AgentCitationView
from devtools.public_reference import PublicReferenceError, ReferenceTarget

try:
    from .execution_plan import validate_execution_plan
except ImportError:  # pragma: no cover - local adapter-root execution path
    from execution_plan import validate_execution_plan


# Explicitly declares that this exact packaged adapter version owns
# its Agent orchestration through inputs.invoke_agent(...).
#
# This is source-controlled adapter identity metadata. It is NOT a credential,
# provider setting, model setting, URL, or deployment environment variable.
AGENT_ORCHESTRATION_OWNER = "python_adapter"

AGENT_ROLE = "capability_orchestrator"
VERTEX_GROUNDED_AGENT_ROLE = "vertex_grounded_orchestrator"

CANONICAL_COMPANY_ID = "13"
CANONICAL_COMPANY_NAME = "Tabuk Pharmaceuticals"
MUTATION_FIXTURE_COMPANY_ID = "900013"
MUTATION_FIXTURE_ROLE = "company_memory_mutation_fixture"
COMPANY_MEMORY_UPDATE_ROLE = "company_memory_update"
MAX_COMPANY_MEMORY_CHARS = 12000
MAX_RESEARCH_TEXT_CHARS = 12000
MAX_CERTIFICATION_CITATIONS = 3
CERTIFICATION_SECTION = "Current Public Research"

# Public-reference failures in this set describe external reachability/content
# conditions. They may degrade evidence verification but must not be confused
# with bridge/admission/security contract failures.
DEGRADABLE_PUBLIC_REFERENCE_CODES = frozenset(
    {
        "public_reference_http_failed",
        "public_reference_http_timeout",
        "public_reference_http_too_large",
        "public_reference_http_content_invalid",
        "public_reference_http_redirect_limit",
        "public_reference_target_unresolvable",
    }
)

VERTEX_RESPONSE_FORMAT_ID = "capability_lab.vertex_grounded.v1"
VERTEX_FORMAT_SUMMARY = "SUMMARY:"
VERTEX_FORMAT_UPDATES = "VERIFIED_UPDATES:"
VERTEX_FORMAT_MEMORY_NOTE = "MEMORY_NOTE:"
VERTEX_FORMAT_END = "END_FORMAT"
VERTEX_FORMAT_BULLET_PREFIX = "- "
VERTEX_FORMAT_SUMMARY_MIN_ITEMS = 2
VERTEX_FORMAT_SUMMARY_MAX_ITEMS = 4
VERTEX_FORMAT_UPDATES_MIN_ITEMS = 2
VERTEX_FORMAT_UPDATES_MAX_ITEMS = 6

# Logical callable role declared by this parent asset.
OPENFDA_CALLABLE_ROLE = "openfda_application_lookup"

# Exact governed callable target expected behind the logical role.
OPENFDA_CALLABLE_ASSET_KEY = "nusaibah.openfda_application_lookup"
OPENFDA_CALLABLE_ASSET_VERSION = "0.1.1"

# Safe capability identifier expected from the callable child's bounded result.
OPENFDA_CAPABILITY = "openfda.application.lookup"

# Defensive local input bound for variables.application_number.
# This prevents accidentally sending an unexpectedly large semantic identifier
# into either the governed Agent or callable-asset invocation path.
MAX_APPLICATION_NUMBER_LENGTH = 128


ALLOWED_PROOF_STAGES = {
    "scaffold",
    "agent_invocation",
    "fixed_skill_read",
    "callable_asset_api",
    "vertex_grounded_citation",
    "vertex_dynamic_skill_certify",
    "vertex_dynamic_skill_verify",
}


def _resolve_proof_stage(variables: dict[str, Any]) -> str:
    """Return the requested proof stage after validating its allow-list.

    Args:
        variables: Safe runtime variables supplied to the adapter.

    Returns:
        The normalized proof-stage name.

    Raises:
        ValueError: If the requested stage is not supported by this adapter.
    """
    proof_stage = str(variables.get("proof_stage", "scaffold")).strip()

    if proof_stage not in ALLOWED_PROOF_STAGES:
        allowed = ", ".join(sorted(ALLOWED_PROOF_STAGES))
        raise ValueError(
            f"Unsupported proof_stage '{proof_stage}'. "
            f"Allowed stages: {allowed}."
        )

    return proof_stage


def _resolve_variables(inputs: Any) -> dict[str, Any]:
    """Return the runtime variables bag as a mutable dictionary.

    Args:
        inputs: Runtime-provided adapter inputs.

    Returns:
        A shallow dictionary containing the safe execution variables.

    Raises:
        ValueError: If the variables role is present but is not an object.
    """
    variables = inputs.get("variables", {})

    if variables is None:
        return {}

    if not isinstance(variables, dict):
        raise ValueError("inputs.variables must be an object when provided.")

    return dict(variables)


def _resolve_records(inputs: Any) -> list[Any]:
    """Return company records while preserving legacy fixture compatibility.

    The manifest declares ``companies`` as a list. Older development fixtures
    may still wrap that list as ``{"records": [...]}``, so both bounded forms
    are accepted during the local capability-lab transition.

    Args:
        inputs: Runtime-provided adapter inputs.

    Returns:
        A shallow list of company records.

    Raises:
        ValueError: If the companies input does not match either supported form.
    """
    companies = inputs.get("companies", [])

    if isinstance(companies, list):
        return list(companies)

    if isinstance(companies, dict):
        records = companies.get("records", [])

        if isinstance(records, list):
            return list(records)

    raise ValueError(
        "inputs.companies must be a list or an object containing a records list."
    )


def _resolve_application_number(variables: dict[str, Any]) -> str:
    """Return a bounded application number for proof stages that require it.

    Args:
        variables: Safe runtime variables supplied to the adapter.

    Returns:
        The normalized application number.

    Raises:
        ValueError: If the value is missing, empty, or exceeds the local bound.
    """
    raw_value = variables.get("application_number")

    if raw_value is None:
        raise ValueError(
            "variables.application_number is required "
            "for capability proof stages that require it."
        )

    application_number = str(raw_value).strip()

    if not application_number:
        raise ValueError(
            "variables.application_number is required "
            "for capability proof stages that require it."
        )

    if len(application_number) > MAX_APPLICATION_NUMBER_LENGTH:
        raise ValueError(
            "variables.application_number must not exceed "
            f"{MAX_APPLICATION_NUMBER_LENGTH} characters."
        )

    return application_number


def _run_agent_invocation(
    inputs: Any,
    *,
    application_number: str,
) -> dict[str, Any]:
    """Invoke one admitted logical agent and project bounded safe evidence.

    The adapter owns only the logical role and semantic input. Provider
    credentials, model selection, MCP/callable admission, retries, transport,
    Runtime Source authority, and provider payloads remain runtime-owned.

    Args:
        inputs: Runtime inputs exposing the trusted ``invoke_agent`` helper.
        application_number: Validated semantic application number.

    Returns:
        Count/status-only evidence suitable for the capability-lab output.

    Raises:
        RuntimeError: If the runtime helper is unavailable, returns an invalid
            result, or does not reach the expected terminal state.
    """
    invoke_agent = getattr(inputs, "invoke_agent", None)

    if not callable(invoke_agent):
        raise RuntimeError(
            "Trusted agent invocation is not available in this runtime."
        )

    agent_result = invoke_agent(
        AGENT_ROLE,
        input={
            "application_number": application_number,
        },
    )

    if not isinstance(agent_result, dict):
        raise RuntimeError(
            "Trusted agent invocation returned an invalid result."
        )

    if agent_result.get("status") != "completed":
        raise RuntimeError("Trusted agent invocation did not complete.")

    # Never project raw provider/tool/callable payloads into adapter evidence.
    return {
        "agent_status": "completed",
        "agent_completed": True,
        "agent_role": AGENT_ROLE,
    }


def _resolve_agent_result(agent_envelope: dict[str, Any]) -> dict[str, Any]:
    """Return one completed typed agent result or fail closed."""

    if agent_envelope.get("status") != "completed":
        raise RuntimeError("Trusted grounded agent invocation did not complete.")

    result = agent_envelope.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Trusted grounded agent invocation returned an invalid result.")

    if result.get("schema_version") != "agent_result.v1":
        raise RuntimeError("Trusted grounded agent invocation returned an unexpected schema.")

    return result


def _canonical_company_memory(inputs: Any) -> Any:
    """Resolve the canonical company memory as read-only governed context."""

    dynamic_skill = getattr(inputs, "dynamic_skill", None)
    if not callable(dynamic_skill):
        raise RuntimeError("Dynamic Skill access is not available in this runtime.")

    memory = dynamic_skill(
        "company_memory",
        variables={"company_id": CANONICAL_COMPANY_ID},
    )

    provenance = memory.provenance()
    if provenance.mutable is not False:
        raise RuntimeError("Canonical company memory must remain read-only.")

    text = memory.read()
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Canonical company memory is empty.")
    if len(text) > MAX_COMPANY_MEMORY_CHARS:
        raise RuntimeError("Canonical company memory exceeds the proof input bound.")

    return memory


def _run_vertex_grounded_citation(inputs: Any) -> tuple[dict[str, Any], Any]:
    """Run the Vertex-grounded company proof and inspect one safe citation."""

    memory = _canonical_company_memory(inputs)
    invoke_agent = getattr(inputs, "invoke_agent", None)
    if not callable(invoke_agent):
        raise RuntimeError("Trusted agent invocation is not available in this runtime.")

    envelope = invoke_agent(
        VERTEX_GROUNDED_AGENT_ROLE,
        input={
            "company_id": CANONICAL_COMPANY_ID,
            "company_name": CANONICAL_COMPANY_NAME,
            "company_memory_context": memory.read(),
            "task": (
                "Research current public information about Tabuk Pharmaceuticals, "
                "use provider grounding, and return a concise evidence-backed update."
            ),
        },
    )
    if not isinstance(envelope, dict):
        raise RuntimeError("Trusted grounded agent invocation returned an invalid envelope.")

    result = _resolve_agent_result(envelope)
    citations = AgentCitationView.from_agent_result(result).deduped_citations()
    if not citations:
        raise RuntimeError("Grounded Vertex result contained no admitted citations.")

    citation = citations[0]
    target = ReferenceTarget.from_agent_citation(citation)
    inspection = inputs.open_reference(target, mode="http")

    evidence = {
        "vertex_grounded_status": "completed",
        "vertex_grounded_agent_role": VERTEX_GROUNDED_AGENT_ROLE,
        "vertex_grounded_result_schema": "agent_result.v1",
        "vertex_grounded_citation_count": len(citations),
        "vertex_grounded_first_provider_family": citation.provider_family,
        "vertex_grounded_first_turn_index": citation.provider_turn_index,
        "vertex_grounded_first_title_present": bool(citation.title),
        "vertex_reference_transport": inspection.transport,
        "vertex_reference_text_present": bool(inspection.text),
        "canonical_company_memory_digest": memory.content_digest(),
        "canonical_company_memory_mutable": memory.provenance().mutable,
    }
    return evidence, citation


def _mutation_target(handle: Any) -> Any:
    """Choose one deterministic existing section for citation attachment."""

    evidence_sections = handle.find_sections("Evidence")
    if len(evidence_sections) == 1:
        return evidence_sections[0].path

    sections = handle.list_sections()
    if not sections:
        raise RuntimeError("Mutation fixture Dynamic Skill has no addressable section.")

    return sections[0].path


def _run_vertex_grounded_dynamic_skill(inputs: Any) -> dict[str, Any]:
    """Compose grounded Vertex evidence with the governed mutable Skill fixture."""

    evidence, citation = _run_vertex_grounded_citation(inputs)
    handle = inputs.dynamic_skill(MUTATION_FIXTURE_ROLE, variables={})

    provenance = handle.provenance()
    if provenance.mutable is not True:
        raise RuntimeError("Synthetic Dynamic Skill fixture is not mutable.")
    if provenance.role != MUTATION_FIXTURE_ROLE:
        raise RuntimeError("Synthetic Dynamic Skill fixture role mismatch.")

    before_digest = handle.content_digest()
    history_before = handle.history(limit=20)

    changes = handle.new_changeset().add_citation(_mutation_target(handle), citation)
    preview = handle.preview(changes)
    if preview.diff.old_digest != before_digest:
        raise RuntimeError("Dynamic Skill preview baseline digest mismatch.")
    if preview.diff.new_digest == before_digest:
        raise RuntimeError("Dynamic Skill citation preview produced no change.")

    receipt = handle.apply(changes, expected_digest=before_digest)

    evidence.update({
        "dynamic_skill_fixture_company_id": MUTATION_FIXTURE_COMPANY_ID,
        "dynamic_skill_mutation_applied": True,
        "dynamic_skill_before_digest": before_digest,
        "dynamic_skill_after_digest": receipt.after_content_digest,
        "dynamic_skill_change_id": receipt.change_id,
        "dynamic_skill_operation_count": receipt.operation_count,
        "dynamic_skill_history_before_count": len(history_before.receipts),
        "dynamic_skill_fresh_readback_required": True,
    })
    return evidence



def _required_as_of_date(variables: dict[str, Any]) -> str:
    """Return one exact ISO date used for durable certification annotations."""

    value = variables.get("research_as_of_date")
    if not isinstance(value, str) or value != value.strip():
        raise ValueError("variables.research_as_of_date must be an exact ISO date.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("variables.research_as_of_date must be an exact ISO date.") from exc
    if parsed.isoformat() != value:
        raise ValueError("variables.research_as_of_date must be an exact ISO date.")
    return value


def _required_certification_cycle(variables: dict[str, Any]) -> str:
    """Return one bounded cycle marker persisted as canonical Skill metadata."""

    value = variables.get("certification_cycle")
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 128
    ):
        raise ValueError("variables.certification_cycle must be a bounded exact string.")
    return value


def _exercise_dynamic_skill_read_helpers(handle: Any) -> dict[str, Any]:
    """Exercise every safe read/navigation helper on one resolved Dynamic Skill."""

    text = handle.read()
    inspection = handle.inspect()
    sections = handle.list_sections()
    toc = handle.table_of_contents()
    if not text.strip() or not sections:
        raise RuntimeError("Dynamic Skill helper certification requires non-empty content.")

    first_section = sections[0]
    path = first_section.path
    if not handle.has_section(path):
        raise RuntimeError("Dynamic Skill has_section helper disagrees with list_sections.")
    if handle.section(path).path != path:
        raise RuntimeError("Dynamic Skill section helper returned an unexpected path.")

    section_text = handle.section_text(path)
    blocks = handle.list_blocks(path)
    paragraphs = handle.paragraphs(path)
    handle.subsections(path)
    handle.subsections(path, recursive=True)
    handle.parent_section(path)
    depth = handle.section_depth(path)
    found_sections = handle.find_sections(path.parts[-1])
    if not found_sections:
        raise RuntimeError("Dynamic Skill find_sections helper did not resolve a known heading.")

    searchable_block = next(
        (block for block in blocks if isinstance(block.text, str) and block.text.strip()),
        None,
    )
    if searchable_block is None:
        for section in sections[1:]:
            candidates = handle.list_blocks(section.path)
            searchable_block = next(
                (
                    block
                    for block in candidates
                    if isinstance(block.text, str) and block.text.strip()
                ),
                None,
            )
            if searchable_block is not None:
                break
    if searchable_block is None:
        raise RuntimeError("Dynamic Skill helper certification requires an addressable block.")

    if handle.block(searchable_block.ref).ref != searchable_block.ref:
        raise RuntimeError("Dynamic Skill block helper returned an unexpected block.")

    needle = searchable_block.text.strip().split()[0]
    if not handle.find(needle):
        raise RuntimeError("Dynamic Skill find helper did not resolve known text.")
    if not handle.find_blocks(text=needle):
        raise RuntimeError("Dynamic Skill find_blocks helper did not resolve known text.")

    resources = handle.list_resources()
    resource_read = False
    if resources:
        first_resource = resources[0]
        if not handle.resource_exists(first_resource.path):
            raise RuntimeError("Dynamic Skill resource_exists helper disagrees with list_resources.")
        resource_text = handle.read_resource(first_resource.path)
        if not isinstance(resource_text, str):
            raise RuntimeError("Dynamic Skill read_resource returned an invalid value.")
        resource_read = True

    snapshot = handle.snapshot()
    history = handle.history(limit=20)
    target_index = handle.target_index() if callable(getattr(handle, "target_index", None)) else None
    if snapshot.content_digest != handle.content_digest():
        raise RuntimeError("Dynamic Skill snapshot/content digest mismatch.")
    if inspection.content_digest != handle.content_digest():
        raise RuntimeError("Dynamic Skill inspection/content digest mismatch.")

    return {
        "dynamic_skill_read_helpers_verified": True,
        "dynamic_skill_section_count": len(sections),
        "dynamic_skill_block_count": handle.block_count(),
        "dynamic_skill_paragraph_count": handle.paragraph_count(),
        "dynamic_skill_toc_count": len(toc),
        "dynamic_skill_first_section_depth": depth,
        "dynamic_skill_first_section_text_present": bool(section_text.strip()),
        "dynamic_skill_resource_count": len(resources),
        "dynamic_skill_resource_read_exercised": resource_read,
        "dynamic_skill_snapshot_verified": True,
        "dynamic_skill_history_receipt_count": len(history.receipts),
        "dynamic_skill_target_index_present": target_index is not None,
    }


def _vertex_format_instructions() -> dict[str, Any]:
    """Return the exact line-oriented response grammar used by certification.

    Authoring invariant:
        This instruction builder and _validate_vertex_response_format are one
        versioned protocol contract. Do not describe a broader format than the
        validator accepts. The phrase "Markdown bullets" is intentionally
        avoided because Markdown permits multiple bullet markers while this
        certification protocol accepts only the ASCII "- " prefix.

        Any grammar change must update the shared constants, this instruction
        text, the validator, deterministic positive/negative tests, the README,
        and the adapter version in the same change.

    Returns:
        A provider-portable grammar with an explicit minimum valid template.
        The template is illustrative content only; marker, line-shape, and
        item-count rules are normative.
    """

    return {
        "format_id": VERTEX_RESPONSE_FORMAT_ID,
        "requirements": [
            f"First line must be exactly: FORMAT_ID: {VERTEX_RESPONSE_FORMAT_ID}",
            f"Then emit exactly these labels in order: {VERTEX_FORMAT_SUMMARY}, "
            f"{VERTEX_FORMAT_UPDATES}, {VERTEX_FORMAT_MEMORY_NOTE}",
            (
                "SUMMARY must contain "
                f"{VERTEX_FORMAT_SUMMARY_MIN_ITEMS} to "
                f"{VERTEX_FORMAT_SUMMARY_MAX_ITEMS} items. "
                "Every item must be exactly one physical line beginning with "
                f"the ASCII prefix {VERTEX_FORMAT_BULLET_PREFIX!r} "
                "(hyphen followed by one space)."
            ),
            (
                "VERIFIED_UPDATES must contain "
                f"{VERTEX_FORMAT_UPDATES_MIN_ITEMS} to "
                f"{VERTEX_FORMAT_UPDATES_MAX_ITEMS} items with the same exact "
                f"{VERTEX_FORMAT_BULLET_PREFIX!r} one-physical-line grammar."
            ),
            (
                "Do not use asterisk, plus, numbered bullets, wrapped bullet "
                "continuation lines, or additional non-bullet lines inside "
                "SUMMARY or VERIFIED_UPDATES."
            ),
            (
                "MEMORY_NOTE must contain concise prose outside the item-list grammar. "
                "Under this protocol, no MEMORY_NOTE line may begin with the exact "
                f"{VERTEX_FORMAT_BULLET_PREFIX!r}."
            ),
            "Do not add extra section labels, URLs, or a source list in the text; "
            "provider citations are captured separately by the runtime.",
            f"Final non-empty line must be exactly: {VERTEX_FORMAT_END}",
        ],
        "minimum_valid_template": [
            f"FORMAT_ID: {VERTEX_RESPONSE_FORMAT_ID}",
            VERTEX_FORMAT_SUMMARY,
            f"{VERTEX_FORMAT_BULLET_PREFIX}<summary item 1>",
            f"{VERTEX_FORMAT_BULLET_PREFIX}<summary item 2>",
            VERTEX_FORMAT_UPDATES,
            f"{VERTEX_FORMAT_BULLET_PREFIX}<verified update 1>",
            f"{VERTEX_FORMAT_BULLET_PREFIX}<verified update 2>",
            VERTEX_FORMAT_MEMORY_NOTE,
            "<concise evidence-based non-bullet note>",
            VERTEX_FORMAT_END,
        ],
    }


def _validate_vertex_response_format(text: str) -> dict[str, Any]:
    """Validate the exact certification grammar emitted to the grounded model.

    This is a protocol validator, not a generic Markdown parser. SUMMARY and
    VERIFIED_UPDATES deliberately accept only one physical line per item with
    the shared ASCII "- " prefix and the shared item-count bounds.

    Maintenance rule:
        Keep this function synchronized with _vertex_format_instructions.
        A prompt/validator mismatch is an adapter contract defect even when the
        provider invocation succeeds. When changing this grammar, update the
        shared constants, instructions, tests, README, and adapter version
        together instead of relying on prose interpretation.
    """

    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Vertex format proof requires non-empty result text.")

    lines = [line.rstrip() for line in text.strip().splitlines()]
    nonempty = [line for line in lines if line.strip()]
    expected_first = f"FORMAT_ID: {VERTEX_RESPONSE_FORMAT_ID}"
    if not nonempty or nonempty[0] != expected_first:
        raise RuntimeError("Vertex response did not honor the required format id.")
    if nonempty[-1] != VERTEX_FORMAT_END:
        raise RuntimeError("Vertex response did not honor the required format end marker.")

    labels = (
        VERTEX_FORMAT_SUMMARY,
        VERTEX_FORMAT_UPDATES,
        VERTEX_FORMAT_MEMORY_NOTE,
    )
    positions: list[int] = []
    for label in labels:
        matches = [index for index, line in enumerate(lines) if line.strip() == label]
        if len(matches) != 1:
            raise RuntimeError("Vertex response format labels are missing or duplicated.")
        positions.append(matches[0])

    if positions != sorted(positions) or len(set(positions)) != len(positions):
        raise RuntimeError("Vertex response format labels are out of order.")

    summary_lines = [
        line.strip()
        for line in lines[positions[0] + 1 : positions[1]]
        if line.strip()
    ]
    update_lines = [
        line.strip()
        for line in lines[positions[1] + 1 : positions[2]]
        if line.strip()
    ]
    memory_lines = [
        line.strip()
        for line in lines[positions[2] + 1 :]
        if line.strip() and line.strip() != VERTEX_FORMAT_END
    ]

    summary_bullets = [
        line
        for line in summary_lines
        if line.startswith(VERTEX_FORMAT_BULLET_PREFIX)
    ]
    update_bullets = [
        line
        for line in update_lines
        if line.startswith(VERTEX_FORMAT_BULLET_PREFIX)
    ]
    if (
        not (
            VERTEX_FORMAT_SUMMARY_MIN_ITEMS
            <= len(summary_bullets)
            <= VERTEX_FORMAT_SUMMARY_MAX_ITEMS
        )
        or len(summary_bullets) != len(summary_lines)
    ):
        raise RuntimeError("Vertex SUMMARY did not honor the required bullet format.")
    if (
        not (
            VERTEX_FORMAT_UPDATES_MIN_ITEMS
            <= len(update_bullets)
            <= VERTEX_FORMAT_UPDATES_MAX_ITEMS
        )
        or len(update_bullets) != len(update_lines)
    ):
        raise RuntimeError("Vertex VERIFIED_UPDATES did not honor the required bullet format.")
    if (
        not memory_lines
        or any(
            line.startswith(VERTEX_FORMAT_BULLET_PREFIX)
            for line in memory_lines
        )
    ):
        raise RuntimeError("Vertex MEMORY_NOTE did not honor the required paragraph format.")

    return {
        "vertex_format_instruction_id": VERTEX_RESPONSE_FORMAT_ID,
        "vertex_format_instruction_followed": True,
        "vertex_format_summary_bullet_count": len(summary_bullets),
        "vertex_format_update_bullet_count": len(update_bullets),
        "vertex_format_memory_note_present": True,
    }

def _is_public_https_reference_candidate(citation: Any) -> bool:
    """Return whether one inert citation locator is eligible for public-web opening.

    This is only a deterministic structural classification. Runtime-owned public
    target validation remains authoritative for DNS, public-address safety,
    ports, redirects, and transport admission.
    """

    locator = getattr(citation, "locator", None)
    if not isinstance(locator, str) or not locator.strip():
        return False
    if locator != locator.strip() or any(character.isspace() for character in locator):
        return False
    if "\\" in locator:
        return False

    try:
        parsed = urlsplit(locator)
    except ValueError:
        return False

    return (
        parsed.scheme.lower() == "https"
        and bool(parsed.netloc)
        and parsed.hostname is not None
    )


def _is_degradable_public_reference_error(exc: PublicReferenceError) -> bool:
    """Return whether a public-reference failure is safe to treat as degraded."""

    return getattr(exc, "code", str(exc)) in DEGRADABLE_PUBLIC_REFERENCE_CODES


def _partition_vertex_reference_candidates(
    citations: tuple[Any, ...],
) -> tuple[tuple[Any, ...], int, int]:
    """Partition Vertex citations into public-HTTPS candidates and inert provenance."""

    web_candidates: list[Any] = []
    non_web_count = 0

    for citation in citations:
        if citation.provider_family != "vertex_ai":
            raise RuntimeError("Vertex certification returned a non-Vertex citation.")

        if _is_public_https_reference_candidate(citation):
            web_candidates.append(citation)
        else:
            non_web_count += 1

    return (
        tuple(web_candidates[:MAX_CERTIFICATION_CITATIONS]),
        len(web_candidates),
        non_web_count,
    )


def _run_vertex_certification_research(
    inputs: Any,
    memory: Any,
) -> tuple[dict[str, Any], str, tuple[Any, ...]]:
    """Run grounded Vertex research and independently inspect eligible web citations."""

    invoke_agent = getattr(inputs, "invoke_agent", None)
    if not callable(invoke_agent):
        raise RuntimeError("Trusted agent invocation is not available in this runtime.")

    envelope = invoke_agent(
        VERTEX_GROUNDED_AGENT_ROLE,
        input={
            "company_id": CANONICAL_COMPANY_ID,
            "company_name": CANONICAL_COMPANY_NAME,
            "company_memory_context": memory.read(),
            "task": (
                "Research current public information about Tabuk Pharmaceuticals. "
                "Use provider grounding and return a concise factual update suitable "
                "for refreshing governed company memory. Prefer primary or authoritative "
                "public sources and preserve evidence-backed statements. "
                "Follow the supplied format_instructions exactly."
            ),
            "format_instructions": _vertex_format_instructions(),
        },
    )
    if not isinstance(envelope, dict):
        raise RuntimeError("Trusted grounded agent invocation returned an invalid envelope.")

    result = _resolve_agent_result(envelope)
    research_text = result.get("text")
    if (
        not isinstance(research_text, str)
        or not research_text.strip()
        or len(research_text) > MAX_RESEARCH_TEXT_CHARS
    ):
        raise RuntimeError("Grounded Vertex result text is empty or exceeds the proof bound.")
    research_text = research_text.strip()
    format_evidence = _validate_vertex_response_format(research_text)

    citations = AgentCitationView.from_agent_result(result).deduped_citations()
    if not citations:
        raise RuntimeError("Grounded Vertex result contained no admitted citations.")

    selected, web_candidate_count, non_web_count = _partition_vertex_reference_candidates(
        citations
    )

    transports: set[str] = set()
    validated: list[Any] = []
    failed = 0

    for citation in selected:
        try:
            target = ReferenceTarget.from_agent_citation(citation)
            inspection = inputs.open_reference(target, mode="http")
        except PublicReferenceError as exc:
            if not _is_degradable_public_reference_error(exc):
                raise
            failed += 1
            continue

        if not isinstance(inspection.text, str) or not inspection.text.strip():
            failed += 1
            continue

        transports.add(str(inspection.transport))
        validated.append(citation)

    reference_status = (
        "verified"
        if validated
        else ("not_applicable" if web_candidate_count == 0 else "degraded")
    )
    evidence = {
        "vertex_certification_status": "completed",
        "vertex_certification_result_schema": "agent_result.v1",
        "vertex_certification_result_text_present": True,
        "vertex_certification_citation_count": len(citations),
        "vertex_certification_web_reference_candidate_count": web_candidate_count,
        "vertex_certification_non_web_reference_count": non_web_count,
        "vertex_certification_reference_attempt_count": len(selected),
        "vertex_certification_validated_reference_count": len(validated),
        "vertex_certification_reference_failure_count": failed,
        "vertex_certification_reference_transport_count": len(transports),
        "vertex_certification_reference_status": reference_status,
        "vertex_certification_reference_verification_complete": bool(validated),
        "vertex_certification_mutation_eligible": bool(validated),
    }
    evidence.update(format_evidence)
    return evidence, research_text, tuple(validated)

def _research_evidence_markdown(text: str) -> str:
    """Render provider-grounded research as inert quoted evidence, not instructions."""

    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Grounded research text is required.")
    rendered = "\n".join(
        "> " + line if line.strip() else ">"
        for line in text.strip().splitlines()
    )
    return (
        "Provider-grounded public research summary (evidence only):\n\n"
        + rendered
        + "\n"
    )


def _preview_structural_mutation_helpers(handle: Any, citation: Any) -> int:
    """Preview every structural mutation primitive without committing company memory."""

    if handle.provenance().mutable is not True:
        raise RuntimeError("Company memory update role must be mutable for preview.")

    sections = handle.list_sections()
    if not sections:
        raise RuntimeError("Company memory update role has no sections.")
    first_path = sections[0].path
    section_body = handle.section_text(first_path)
    paragraphs = [
        block
        for section in sections
        for block in handle.paragraphs(section.path)
    ]
    if not paragraphs:
        raise RuntimeError("Synthetic Dynamic Skill fixture has no paragraph blocks.")
    paragraph = paragraphs[0]

    previews = [
        handle.new_changeset().replace_section(
            first_path,
            section_body + "\n\nCertification preview replacement.\n",
        ),
        handle.new_changeset().add_section(
            "Certification Preview Add",
            "Preview-only section.\n",
        ),
        handle.new_changeset().add_subsection(
            first_path,
            "Certification Preview Child",
            "Preview-only child section.\n",
        ),
        handle.new_changeset().upsert_section(
            "Certification Preview Upsert",
            "Preview-only upsert section.\n",
        ),
        handle.new_changeset().replace_block(
            paragraph.ref,
            "Certification preview block replacement.\n",
        ),
        handle.new_changeset().replace_paragraph(
            paragraph.ref,
            "Certification preview paragraph replacement.",
        ),
        handle.new_changeset().append_paragraph(
            first_path,
            "Certification preview appended paragraph.",
        ),
        handle.new_changeset().add_citation(first_path, citation),
        handle.new_changeset().add_citations(first_path, (citation,)),
    ]
    for changes in previews:
        preview = handle.preview(changes)
        if preview.diff.operation_count < 1:
            raise RuntimeError("Dynamic Skill structural mutation preview produced no operation.")
    return len(previews)


def _preview_indexed_mutation_helpers(
    handle: Any,
    citation: Any,
    *,
    as_of_date: str,
    certification_cycle: str,
) -> int:
    """Preview every indexed mutation primitive without writing company memory."""

    sections = handle.list_sections()
    if not sections:
        raise RuntimeError("Company memory update role has no sections.")
    first_path = sections[0].path
    section_body = handle.section_text(first_path)
    paragraphs = [
        block
        for section in sections
        for block in handle.paragraphs(section.path)
    ]
    if not paragraphs:
        raise RuntimeError("Company memory update role has no paragraph blocks.")
    paragraph = paragraphs[0]
    canonical = {
        "company_id": int(CANONICAL_COMPANY_ID),
        "certification_cycle": certification_cycle,
        "provider": "vertex_ai",
    }

    previews = [
        handle.new_indexed_changeset().replace_section(
            first_path,
            section_body + "\n\nIndexed certification preview.\n",
            citations=(citation,),
            as_of_date=as_of_date,
            canonical=canonical,
        ),
        handle.new_indexed_changeset().add_section(
            "Certification Indexed Add",
            "Preview-only indexed section.\n",
            citations=(citation,),
            as_of_date=as_of_date,
            canonical=canonical,
        ),
        handle.new_indexed_changeset().add_subsection(
            first_path,
            "Certification Indexed Child",
            "Preview-only indexed child.\n",
            citations=(citation,),
            as_of_date=as_of_date,
            canonical=canonical,
        ),
        handle.new_indexed_changeset().append_paragraph(
            first_path,
            "Preview-only indexed paragraph.",
            citations=(citation,),
            as_of_date=as_of_date,
            canonical=canonical,
        ),
        handle.new_indexed_changeset().replace_paragraph(
            paragraph.ref,
            "Preview-only indexed paragraph replacement.",
            citations=(citation,),
            as_of_date=as_of_date,
            canonical=canonical,
        ),
    ]
    for changes in previews:
        preview = handle.preview_indexed(changes)
        if preview.diff.operation_count < 1 or not preview.target_index.entries:
            raise RuntimeError("Dynamic Skill indexed mutation preview was incomplete.")
    return len(previews)


def _run_vertex_dynamic_skill_certification(
    inputs: Any,
    variables: dict[str, Any],
) -> dict[str, Any]:
    """Research company 13 online and commit one annotated governed memory update."""

    as_of_date = _required_as_of_date(variables)
    certification_cycle = _required_certification_cycle(variables)
    memory = _canonical_company_memory(inputs)
    evidence = _exercise_dynamic_skill_read_helpers(memory)

    vertex_evidence, research_text, citations = _run_vertex_certification_research(
        inputs,
        memory,
    )
    evidence.update(vertex_evidence)

    if not citations:
        evidence.update(
            {
                "dynamic_skill_company_id": int(CANONICAL_COMPANY_ID),
                "dynamic_skill_update_role": COMPANY_MEMORY_UPDATE_ROLE,
                "dynamic_skill_real_update_applied": False,
                "dynamic_skill_mutation_skipped": True,
                "dynamic_skill_mutation_skip_reason": "public_reference_verification_degraded",
                "dynamic_skill_fresh_execution_verification_required": True,
            }
        )
        return evidence

    update = inputs.dynamic_skill(
        COMPANY_MEMORY_UPDATE_ROLE,
        variables={"company_id": CANONICAL_COMPANY_ID},
    )
    if update.provenance().mutable is not True:
        raise RuntimeError("Company memory update role must be mutable.")
    if update.provenance().role != COMPANY_MEMORY_UPDATE_ROLE:
        raise RuntimeError("Company memory update role mismatch.")
    if update.content_digest() != memory.content_digest():
        raise RuntimeError("Read-only and mutable company memory baselines differ.")

    evidence["dynamic_skill_structural_preview_count"] = _preview_structural_mutation_helpers(
        update,
        citations[0],
    )
    evidence["dynamic_skill_indexed_preview_count"] = _preview_indexed_mutation_helpers(
        update,
        citations[0],
        as_of_date=as_of_date,
        certification_cycle=certification_cycle,
    )

    canonical = {
        "company_id": int(CANONICAL_COMPANY_ID),
        "company_name": CANONICAL_COMPANY_NAME,
        "certification_cycle": certification_cycle,
        "provider": "vertex_ai",
    }
    research_markdown = _research_evidence_markdown(research_text)
    changes = update.new_indexed_changeset()
    if update.has_section(CERTIFICATION_SECTION):
        changes.replace_section(
            CERTIFICATION_SECTION,
            research_markdown,
            citations=citations,
            as_of_date=as_of_date,
            canonical=canonical,
        )
    else:
        changes.add_section(
            CERTIFICATION_SECTION,
            research_markdown,
            citations=citations,
            as_of_date=as_of_date,
            canonical=canonical,
        )

    before_digest = update.content_digest()
    preview = update.preview_indexed(changes)
    metadata = preview.target_index.metadata_for_section(
        preview.document,
        CERTIFICATION_SECTION,
    )
    if metadata is None:
        raise RuntimeError("Certification target metadata was not created.")
    if metadata.as_of_date != as_of_date:
        raise RuntimeError("Certification target as-of metadata mismatch.")
    if metadata.canonical_dict() != canonical:
        raise RuntimeError("Certification canonical metadata mismatch.")
    if len(metadata.citations) != len(citations):
        raise RuntimeError("Certification citation annotation count mismatch.")

    receipt = update.apply_indexed(changes, expected_digest=before_digest)
    if not receipt.document_changed or not receipt.target_index_changed:
        raise RuntimeError("Certification commit did not change content and annotations.")

    committed = inputs.dynamic_skill(
        COMPANY_MEMORY_UPDATE_ROLE,
        variables={"company_id": CANONICAL_COMPANY_ID},
    )
    if committed.content_digest() != receipt.after_content_digest:
        raise RuntimeError("Same-run committed Dynamic Skill digest mismatch.")
    committed_index = committed.target_index()
    if committed_index is None:
        raise RuntimeError("Committed Dynamic Skill target index is missing.")
    committed_metadata = committed.target_metadata_for_section(
        CERTIFICATION_SECTION,
    )
    if committed_metadata is None or committed_metadata.canonical_dict() != canonical:
        raise RuntimeError("Committed Dynamic Skill annotation metadata mismatch.")

    history = committed.history(limit=20)
    latest = history.latest_change()
    if latest is None or latest.change_id != receipt.change_id:
        raise RuntimeError("Committed Dynamic Skill history is missing the certification change.")
    if latest.after_content_digest != receipt.after_content_digest:
        raise RuntimeError("Committed Dynamic Skill history content digest mismatch.")
    if latest.target_index_changed is not True:
        raise RuntimeError("Committed Dynamic Skill history did not record annotation change.")

    evidence.update({
        "dynamic_skill_company_id": int(CANONICAL_COMPANY_ID),
        "dynamic_skill_update_role": COMPANY_MEMORY_UPDATE_ROLE,
        "dynamic_skill_baseline_digest_match": True,
        "dynamic_skill_real_update_applied": True,
        "dynamic_skill_document_changed": receipt.document_changed,
        "dynamic_skill_target_index_changed": receipt.target_index_changed,
        "dynamic_skill_after_digest": receipt.after_content_digest,
        "dynamic_skill_after_target_index_digest": receipt.after_target_index_digest,
        "dynamic_skill_change_id": receipt.change_id,
        "dynamic_skill_operation_count": receipt.operation_count,
        "dynamic_skill_committed_citation_count": len(committed_metadata.citations),
        "dynamic_skill_committed_as_of_date": committed_metadata.as_of_date,
        "dynamic_skill_same_run_history_verified": True,
        "dynamic_skill_fresh_execution_verification_required": True,
    })
    return evidence


def _verify_vertex_dynamic_skill_certification(
    inputs: Any,
    variables: dict[str, Any],
) -> dict[str, Any]:
    """Fresh-run verification of company-13 content, annotations, history, and references."""

    as_of_date = _required_as_of_date(variables)
    certification_cycle = _required_certification_cycle(variables)
    read_only = _canonical_company_memory(inputs)
    update = inputs.dynamic_skill(
        COMPANY_MEMORY_UPDATE_ROLE,
        variables={"company_id": CANONICAL_COMPANY_ID},
    )
    if update.provenance().mutable is not True:
        raise RuntimeError("Company memory update role must remain mutable.")
    if read_only.content_digest() != update.content_digest():
        raise RuntimeError("Fresh read-only and mutable company memory digests differ.")

    target_index = read_only.target_index()
    if target_index is None:
        raise RuntimeError("Fresh company memory target index is missing.")
    metadata = read_only.target_metadata_for_section(
        CERTIFICATION_SECTION,
    )
    if metadata is None:
        raise RuntimeError("Fresh company memory certification metadata is missing.")
    canonical = metadata.canonical_dict()
    if canonical.get("company_id") != int(CANONICAL_COMPANY_ID):
        raise RuntimeError("Fresh company memory canonical company_id mismatch.")
    if canonical.get("company_name") != CANONICAL_COMPANY_NAME:
        raise RuntimeError("Fresh company memory canonical company name mismatch.")
    if canonical.get("certification_cycle") != certification_cycle:
        raise RuntimeError("Fresh company memory certification cycle mismatch.")
    if canonical.get("provider") != "vertex_ai":
        raise RuntimeError("Fresh company memory provider annotation mismatch.")
    if metadata.as_of_date != as_of_date:
        raise RuntimeError("Fresh company memory as-of annotation mismatch.")
    if not metadata.citations:
        raise RuntimeError("Fresh company memory has no persisted citations.")

    selected, web_candidate_count, non_web_count = _partition_vertex_reference_candidates(
        tuple(metadata.citations)
    )
    opened = 0
    attempted = 0
    failed = 0
    for citation in selected:
        attempted += 1
        try:
            inspection = inputs.open_reference(
                ReferenceTarget.from_agent_citation(citation),
                mode="http",
            )
        except PublicReferenceError as exc:
            if not _is_degradable_public_reference_error(exc):
                raise
            failed += 1
            continue

        if not isinstance(inspection.text, str) or not inspection.text.strip():
            failed += 1
            continue
        opened += 1

    reference_status = (
        "verified"
        if opened > 0
        else ("not_applicable" if web_candidate_count == 0 else "degraded")
    )

    history = update.history(limit=20)
    latest = history.latest_change()
    if latest is None:
        raise RuntimeError("Fresh company memory history has no committed change.")
    if latest.after_content_digest != update.content_digest():
        raise RuntimeError("Fresh company memory history/content digest mismatch.")
    if latest.target_index_changed is not True:
        raise RuntimeError("Fresh company memory history lacks target-index mutation evidence.")
    latest_snapshot = history.latest()
    if latest_snapshot.content_digest != update.content_digest():
        raise RuntimeError("Fresh company memory latest snapshot digest mismatch.")
    if latest_snapshot.target_index_digest != target_index.digest():
        raise RuntimeError("Fresh company memory historical target-index digest mismatch.")

    helper_evidence = _exercise_dynamic_skill_read_helpers(read_only)
    if helper_evidence.get("dynamic_skill_resource_read_exercised") is not True:
        raise RuntimeError("Fresh annotated company memory resource read was not exercised.")
    helper_evidence.update({
        "dynamic_skill_company_id": int(CANONICAL_COMPANY_ID),
        "dynamic_skill_fresh_certification_verified": opened > 0,
        "dynamic_skill_governed_state_verified": True,
        "dynamic_skill_read_write_digest_match": True,
        "dynamic_skill_persisted_citation_count": len(metadata.citations),
        "dynamic_skill_web_reference_candidate_count": web_candidate_count,
        "dynamic_skill_non_web_reference_count": non_web_count,
        "dynamic_skill_reference_revalidation_attempt_count": attempted,
        "dynamic_skill_revalidated_reference_count": opened,
        "dynamic_skill_reference_revalidation_failure_count": failed,
        "dynamic_skill_reference_revalidation_status": reference_status,
        "dynamic_skill_reference_revalidation_complete": opened > 0,
        "dynamic_skill_annotation_review_present": bool(metadata.review_annotation()),
        "dynamic_skill_history_latest_change_verified": True,
        "dynamic_skill_history_target_index_verified": True,
    })
    return helper_evidence


def _required_safe_token(
    variables: dict[str, Any],
    key: str,
    *,
    prefix: str | None = None,
    max_length: int = 256,
) -> str:
    """Return one bounded opaque verification token from caller variables."""

    value = variables.get(key)
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"variables.{key} must be a non-empty exact string.")
    if len(value) > max_length:
        raise ValueError(f"variables.{key} exceeds the verification bound.")
    if prefix is not None and not value.startswith(prefix):
        raise ValueError(f"variables.{key} has an unexpected format.")
    return value


def _verify_dynamic_skill_commit(
    inputs: Any,
    variables: dict[str, Any],
) -> dict[str, Any]:
    """Verify one prior commit from a fresh adapter execution."""

    expected_change_id = _required_safe_token(
        variables,
        "expected_change_id",
        max_length=256,
    )
    expected_after_digest = _required_safe_token(
        variables,
        "expected_after_digest",
        prefix="sha256:",
        max_length=80,
    )

    handle = inputs.dynamic_skill(MUTATION_FIXTURE_ROLE, variables={})
    if handle.content_digest() != expected_after_digest:
        raise RuntimeError("Fresh Dynamic Skill readback digest mismatch.")

    history = handle.history(limit=50)
    latest_change = history.latest_change()
    if latest_change is None or latest_change.change_id != expected_change_id:
        raise RuntimeError("Fresh Dynamic Skill history does not contain the expected latest change.")
    if latest_change.after_content_digest != expected_after_digest:
        raise RuntimeError("Fresh Dynamic Skill history digest mismatch.")
    if history.latest().content_digest != expected_after_digest:
        raise RuntimeError("Fresh Dynamic Skill latest snapshot digest mismatch.")

    return {
        "dynamic_skill_fixture_company_id": MUTATION_FIXTURE_COMPANY_ID,
        "dynamic_skill_fresh_readback_verified": True,
        "dynamic_skill_history_verified": True,
        "dynamic_skill_verified_change_id": expected_change_id,
        "dynamic_skill_verified_after_digest": expected_after_digest,
        "dynamic_skill_history_count": len(history.receipts),
    }


def _run_callable_api_lookup(
    inputs: Any,
    *,
    application_number: str,
) -> dict[str, Any]:
    """Invoke the governed openFDA callable asset and return bounded evidence.

    The capability-lab adapter supplies only semantic variables. The child
    adapter owns its declared Runtime Source input contract, while Assets/Core
    retain authority for Runtime Source resolution, credentials, transport,
    admission, retries, and execution.

    Args:
        inputs: Runtime inputs exposing the trusted ``invoke_asset`` helper.
        application_number: Validated Drugs@FDA application number.

    Returns:
        Safe bounded evidence showing that the expected callable asset completed.

    Raises:
        RuntimeError: If the callable bridge is unavailable or returns an
            unexpected envelope, result, capability, or provenance identity.
    """
    invoke_asset = getattr(inputs, "invoke_asset", None)

    if not callable(invoke_asset):
        raise RuntimeError(
            "Trusted callable-asset invocation is not available in this runtime."
        )

    callable_result = invoke_asset(
        OPENFDA_CALLABLE_ROLE,
        variables={
            "application_number": application_number,
        },
    )

    if not isinstance(callable_result, dict):
        raise RuntimeError(
            "Trusted callable-asset invocation returned an invalid envelope."
        )

    if callable_result.get("status") != "success":
        raise RuntimeError(
            "Trusted callable-asset invocation did not succeed."
        )

    result = callable_result.get("result")

    if not isinstance(result, dict):
        raise RuntimeError(
            "Trusted callable-asset invocation returned an invalid result."
        )

    if result.get("capability") != OPENFDA_CAPABILITY:
        raise RuntimeError(
            "Trusted callable-asset invocation returned an unexpected capability."
        )

    if result.get("application_number") != application_number:
        raise RuntimeError(
            "Trusted callable-asset invocation returned an unexpected application."
        )

    provenance = callable_result.get("provenance")

    if not isinstance(provenance, dict):
        raise RuntimeError(
            "Trusted callable-asset invocation returned invalid provenance."
        )

    if provenance.get("callable_asset") is not True:
        raise RuntimeError(
            "Trusted callable-asset invocation provenance is not callable-asset scoped."
        )

    if provenance.get("role") != OPENFDA_CALLABLE_ROLE:
        raise RuntimeError(
            "Trusted callable-asset invocation returned unexpected role provenance."
        )

    if provenance.get("asset_key") != OPENFDA_CALLABLE_ASSET_KEY:
        raise RuntimeError(
            "Trusted callable-asset invocation returned unexpected asset provenance."
        )

    if provenance.get("asset_version") != OPENFDA_CALLABLE_ASSET_VERSION:
        raise RuntimeError(
            "Trusted callable-asset invocation returned unexpected version provenance."
        )

    # Do not copy the child record or provider response into the lab output.
    # The primitive proof needs only bounded status/presence evidence.
    return {
        "callable_asset_status": "success",
        "callable_asset_role": OPENFDA_CALLABLE_ROLE,
        "callable_asset_capability": OPENFDA_CAPABILITY,
        "callable_asset_result_present": True,
        "callable_asset_brand_name_present": bool(
            result.get("brand_name")
        ),
        "callable_asset_submission_date_present": bool(
            result.get("submission_status_date")
        ),
    }


def _read_fixed_skill(inputs: Any) -> dict[str, Any]:
    """Read and inspect the manifest-pinned Fixed Skill without executing it.

    Args:
        inputs: Runtime inputs exposing the trusted Fixed Skill resolver.

    Returns:
        Bounded validation and inspection metadata for the admitted Skill.
    """
    skill_view = inputs.skill("nusaibah.capability-orchestration")
    skill_validation = skill_view.validate()
    skill_text = skill_view.read()
    skill_inspection = skill_view.inspect()

    return {
        "fixed_skill_status": skill_validation.status,
        "fixed_skill_ref": skill_validation.skill_ref,
        "fixed_skill_version": skill_validation.version,
        "fixed_skill_resource_count": skill_validation.resource_count,
        "fixed_skill_title": skill_inspection.title,
        "fixed_skill_section_count": skill_inspection.section_count,
        "fixed_skill_block_count": skill_inspection.block_count,
        "fixed_skill_text_present": bool(skill_text),
    }


class NusaibahAgentCapabilityLabAdapter(Adapter):
    """Exercise progressive adapter capabilities through governed runtime APIs.

    This development adapter keeps business logic deterministic except where a
    proof stage explicitly calls an approved runtime-owned capability helper.
    It never owns credentials, provider connection details, storage locations,
    Runtime Source transport, MCP transport, publication, queues, retries, or
    Core/OBS authority.

    Development lesson:
        Strict model-output formats are versioned adapter protocols. Prompt
        wording must never be broader or looser than the parser that consumes
        it. Shared grammar constants plus deterministic negative tests prevent
        a successful provider response from being rejected only because prompt
        prose and validation semantics drifted apart.
    """

    key: ClassVar[str] = "nusaibah.agent_capability_lab"
    version: ClassVar[str] = "0.1.16"

    def invoke(
        self,
        inputs: Any,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one bounded capability-lab proof stage.

        Args:
            inputs: Runtime-provided inputs. The object may expose trusted
                capability helpers such as ``invoke_agent``, ``invoke_asset``,
                and ``skill``.
            context: Safe runtime context metadata. The current adapter does not
                use context values to select providers, tools, assets, or data.

        Returns:
            A standard adapter response containing bounded capability evidence.

        Raises:
            ValueError: If local semantic input or proof-stage input is invalid.
            RuntimeError: If a requested trusted runtime helper is unavailable
                or its invocation does not reach the expected terminal state.
        """
        del context  # Reserved for future safe metadata; never used as authority.

        records = _resolve_records(inputs)
        variables = _resolve_variables(inputs)

        # Validate developer-authored orchestration intent before any helper call.
        execution_plan_data = variables.get("execution_plan")
        validated_plan = validate_execution_plan(execution_plan_data)
        proof_stage = _resolve_proof_stage(variables)

        capability_result: dict[str, Any] = {
            "record_count": len(records),
            "variables_present": bool(variables),
            "proof_stage": proof_stage,
            "execution_plan_schema": validated_plan.schema_version,
            "execution_plan_company_id": validated_plan.company_id,
            "execution_plan_step_count": len(validated_plan.steps),
        }

        if proof_stage == "agent_invocation":
            application_number = _resolve_application_number(variables)

            capability_result.update(
                _run_agent_invocation(
                    inputs,
                    application_number=application_number,
                )
            )

        elif proof_stage == "fixed_skill_read":
            capability_result.update(
                _read_fixed_skill(inputs)
            )

        elif proof_stage == "callable_asset_api":
            application_number = _resolve_application_number(variables)

            capability_result.update(
                _run_callable_api_lookup(
                    inputs,
                    application_number=application_number,
                )
            )

        elif proof_stage == "vertex_grounded_citation":
            if validated_plan.company_id != int(CANONICAL_COMPANY_ID):
                raise ValueError(
                    "vertex_grounded_citation requires execution_plan.company_id=13."
                )
            capability_result.update(_run_vertex_grounded_citation(inputs)[0])

        elif proof_stage == "vertex_grounded_dynamic_skill":
            if validated_plan.company_id != int(CANONICAL_COMPANY_ID):
                raise ValueError(
                    "vertex_grounded_dynamic_skill requires execution_plan.company_id=13."
                )
            capability_result.update(_run_vertex_grounded_dynamic_skill(inputs))

        elif proof_stage == "dynamic_skill_commit_verify":
            capability_result.update(
                _verify_dynamic_skill_commit(inputs, variables)
            )

        elif proof_stage == "vertex_dynamic_skill_certify":
            if validated_plan.company_id != int(CANONICAL_COMPANY_ID):
                raise ValueError(
                    "vertex_dynamic_skill_certify requires execution_plan.company_id=13."
                )
            capability_result.update(
                _run_vertex_dynamic_skill_certification(inputs, variables)
            )

        elif proof_stage == "vertex_dynamic_skill_verify":
            if validated_plan.company_id != int(CANONICAL_COMPANY_ID):
                raise ValueError(
                    "vertex_dynamic_skill_verify requires execution_plan.company_id=13."
                )
            capability_result.update(
                _verify_vertex_dynamic_skill_certification(inputs, variables)
            )

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "capability_result": capability_result,
            },
            "logs": [
                {
                    "level": "info",
                    "message": (
                        "Capability proof stage completed: "
                        f"{proof_stage}."
                    ),
                },
            ],
            "metrics": {
                "record_count": len(records),
                "proof_stage_validated": 1,
                "logical_agent_invocations": (
                    1 if proof_stage == "agent_invocation" else 0
                ),
                "logical_callable_asset_invocations": (
                    1 if proof_stage == "callable_asset_api" else 0
                ),
                "logical_grounded_agent_invocations": (
                    1
                    if proof_stage in {
                        "vertex_grounded_citation",
                        "vertex_grounded_dynamic_skill",
                        "vertex_dynamic_skill_certify",
                    }
                    else 0
                ),
                "dynamic_skill_mutations": (
                    1
                    if proof_stage in {
                        "vertex_grounded_dynamic_skill",
                        "vertex_dynamic_skill_certify",
                    }
                    else 0
                ),
            },
        }