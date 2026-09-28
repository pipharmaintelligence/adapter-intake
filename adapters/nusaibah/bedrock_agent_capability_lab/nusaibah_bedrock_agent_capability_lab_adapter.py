from __future__ import annotations

from typing import Any, ClassVar

from adapters.base import Adapter

try:
    from .execution_plan import validate_execution_plan
except ImportError:  # pragma: no cover - local adapter-root execution path
    from execution_plan import validate_execution_plan


AGENT_ORCHESTRATION_OWNER = "python_adapter"

BEDROCK_AGENT_ROLE = "bedrock_orchestrator"
FIXED_SKILL_REF = "nusaibah.capability-orchestration"
DYNAMIC_SKILL_ROLE = "company_memory"
MUTATION_FIXTURE_ROLE = "company_memory_mutation_fixture"

CANONICAL_COMPANY_ID = "13"
CANONICAL_COMPANY_NAME = "Tabuk Pharmaceuticals"
MUTATION_FIXTURE_COMPANY_ID = "900013"

OPENFDA_CALLABLE_ROLE = "openfda_application_lookup"
OPENFDA_CALLABLE_ASSET_KEY = "nusaibah.openfda_application_lookup"
OPENFDA_CALLABLE_ASSET_VERSION = "0.1.1"
OPENFDA_CAPABILITY = "openfda.application.lookup"

HEALTHCARE_NLP_TOOL_ROLE = "healthcare_nlp"
HEALTHCARE_NLP_CAPABILITY = "healthcare.nlp.analyze_entities"
DEFAULT_HEALTHCARE_TEXT = (
    "Synthetic test note: patient takes aspirin and metformin for type 2 diabetes."
)

MAX_APPLICATION_NUMBER_LENGTH = 128
MAX_COMPANY_MEMORY_CHARS = 12000
MAX_HEALTHCARE_TEXT_CHARS = 12000
MAX_AGENT_TEXT_CHARS = 12000
SYNTHETIC_ANALYSIS_SECTION = "Bedrock Synthetic Analysis"

ALLOWED_PROOF_STAGES = {
    "scaffold",
    "bedrock_agent_invocation",
    "fixed_skill_read",
    "dynamic_skill_read",
    "callable_asset_api",
    "healthcare_nlp_entities",
    "bedrock_dynamic_skill_analysis",
    "bedrock_healthcare_nlp_entities",
    "bedrock_dynamic_skill_mutation",
    "dynamic_skill_commit_verify",
    "bedrock_full_composition",
}


def _resolve_variables(inputs: Any) -> dict[str, Any]:
    """Return safe runtime variables as a shallow dictionary."""

    variables = inputs.get("variables", {})
    if variables is None:
        return {}
    if not isinstance(variables, dict):
        raise ValueError("inputs.variables must be an object when provided.")
    return dict(variables)


def _resolve_records(inputs: Any) -> list[Any]:
    """Return company records in the same bounded forms as the reference lab."""

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


def _resolve_proof_stage(variables: dict[str, Any]) -> str:
    """Validate and return the requested Bedrock proof stage."""

    proof_stage = str(variables.get("proof_stage", "scaffold")).strip()
    if proof_stage not in ALLOWED_PROOF_STAGES:
        allowed = ", ".join(sorted(ALLOWED_PROOF_STAGES))
        raise ValueError(
            f"Unsupported proof_stage '{proof_stage}'. Allowed stages: {allowed}."
        )
    return proof_stage


def _resolve_application_number(variables: dict[str, Any]) -> str:
    """Return one bounded semantic application number."""

    value = variables.get("application_number")
    if value is None:
        raise ValueError("variables.application_number is required for this proof stage.")
    application_number = str(value).strip()
    if not application_number:
        raise ValueError("variables.application_number is required for this proof stage.")
    if len(application_number) > MAX_APPLICATION_NUMBER_LENGTH:
        raise ValueError(
            "variables.application_number must not exceed "
            f"{MAX_APPLICATION_NUMBER_LENGTH} characters."
        )
    return application_number


def _resolve_healthcare_text(variables: dict[str, Any]) -> str:
    """Return bounded synthetic-or-caller-provided text for Healthcare NLP."""

    value = variables.get("healthcare_text", DEFAULT_HEALTHCARE_TEXT)
    if not isinstance(value, str):
        raise ValueError("variables.healthcare_text must be a string when provided.")
    text = value.strip()
    if not text:
        raise ValueError("variables.healthcare_text must not be empty.")
    if len(text) > MAX_HEALTHCARE_TEXT_CHARS:
        raise ValueError(
            f"variables.healthcare_text must not exceed {MAX_HEALTHCARE_TEXT_CHARS} characters."
        )
    return text


def _resolve_bedrock_result(envelope: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Validate one adapter-visible Bedrock Agent result without exposing raw provider data."""

    if not isinstance(envelope, dict) or envelope.get("status") != "completed":
        raise RuntimeError("Trusted Bedrock agent invocation did not complete.")

    result = envelope.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Trusted Bedrock agent invocation returned an invalid result.")
    if result.get("schema_version") != "agent_result.v1":
        raise RuntimeError("Trusted Bedrock agent invocation returned an unexpected schema.")

    text = result.get("text")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Trusted Bedrock agent result text is empty.")
    if len(text) > MAX_AGENT_TEXT_CHARS:
        raise RuntimeError("Trusted Bedrock agent result exceeds the proof bound.")

    provider_metadata = result.get("provider_metadata")
    if not isinstance(provider_metadata, dict):
        raise RuntimeError("Trusted Bedrock agent result provider metadata is missing.")
    turns = provider_metadata.get("turns")
    if not isinstance(turns, list) or not turns:
        raise RuntimeError("Trusted Bedrock agent result has no provider-turn evidence.")

    normalized_turns: list[dict[str, Any]] = []
    for turn in turns:
        if not isinstance(turn, dict):
            raise RuntimeError("Trusted Bedrock agent provider-turn evidence is invalid.")
        if turn.get("provider_family") != "bedrock":
            raise RuntimeError("Trusted Bedrock agent resolved an unexpected provider family.")
        normalized_turns.append(turn)

    return result, normalized_turns


def _invoke_bedrock_agent(
    inputs: Any,
    *,
    business_input: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Invoke the declared Bedrock logical role through the trusted runtime helper."""

    invoke_agent = getattr(inputs, "invoke_agent", None)
    if not callable(invoke_agent):
        raise RuntimeError("Trusted agent invocation is not available in this runtime.")

    envelope = invoke_agent(BEDROCK_AGENT_ROLE, input=business_input)
    result, turns = _resolve_bedrock_result(envelope)

    evidence = {
        "bedrock_agent_status": "completed",
        "bedrock_agent_completed": True,
        "bedrock_agent_role": BEDROCK_AGENT_ROLE,
        "bedrock_agent_result_schema": "agent_result.v1",
        "bedrock_agent_provider_family": "bedrock",
        "bedrock_agent_provider_turn_count": len(turns),
        "bedrock_agent_text_present": True,
    }
    return evidence, result


def _run_bedrock_agent_invocation(inputs: Any) -> dict[str, Any]:
    """Prove a minimal logical Bedrock Agent invocation."""

    evidence, result = _invoke_bedrock_agent(
        inputs,
        business_input={"task": "Return exactly: ok"},
    )
    if result["text"].strip().lower() != "ok":
        raise RuntimeError("Bedrock exact-response proof returned unexpected text.")
    evidence["bedrock_exact_response_verified"] = True
    return evidence


def _read_fixed_skill(inputs: Any) -> dict[str, Any]:
    """Read and inspect the manifest-pinned Fixed Skill."""

    skill_view = inputs.skill(FIXED_SKILL_REF)
    validation = skill_view.validate()
    text = skill_view.read()
    inspection = skill_view.inspect()
    return {
        "fixed_skill_status": validation.status,
        "fixed_skill_ref": validation.skill_ref,
        "fixed_skill_version": validation.version,
        "fixed_skill_resource_count": validation.resource_count,
        "fixed_skill_title": inspection.title,
        "fixed_skill_section_count": inspection.section_count,
        "fixed_skill_block_count": inspection.block_count,
        "fixed_skill_text_present": bool(text),
    }


def _canonical_company_memory(inputs: Any) -> Any:
    """Resolve canonical company memory through the governed Dynamic Skill helper."""

    dynamic_skill = getattr(inputs, "dynamic_skill", None)
    if not callable(dynamic_skill):
        raise RuntimeError("Dynamic Skill access is not available in this runtime.")

    memory = dynamic_skill(
        DYNAMIC_SKILL_ROLE,
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


def _dynamic_skill_read_evidence(memory: Any) -> dict[str, Any]:
    """Exercise bounded Dynamic Skill read/navigation surfaces."""

    inspection = memory.inspect()
    sections = memory.list_sections()
    toc = memory.table_of_contents()
    snapshot = memory.snapshot()
    history = memory.history(limit=20)

    if not sections:
        raise RuntimeError("Dynamic Skill read proof requires at least one section.")
    if snapshot.content_digest != memory.content_digest():
        raise RuntimeError("Dynamic Skill snapshot/content digest mismatch.")
    if inspection.content_digest != memory.content_digest():
        raise RuntimeError("Dynamic Skill inspection/content digest mismatch.")

    first = sections[0]
    if not memory.has_section(first.path):
        raise RuntimeError("Dynamic Skill section lookup disagrees with section inventory.")
    if not memory.section_text(first.path).strip():
        raise RuntimeError("Dynamic Skill first section is empty.")

    return {
        "dynamic_skill_status": "ready",
        "dynamic_skill_role": DYNAMIC_SKILL_ROLE,
        "dynamic_skill_company_id": int(CANONICAL_COMPANY_ID),
        "dynamic_skill_mutable": False,
        "dynamic_skill_content_digest": memory.content_digest(),
        "dynamic_skill_section_count": len(sections),
        "dynamic_skill_toc_count": len(toc),
        "dynamic_skill_snapshot_verified": True,
        "dynamic_skill_history_receipt_count": len(history.receipts),
    }


def _run_dynamic_skill_read(inputs: Any) -> dict[str, Any]:
    """Prove canonical read-only Dynamic Skill access."""

    return _dynamic_skill_read_evidence(_canonical_company_memory(inputs))


def _run_callable_api_lookup(
    inputs: Any,
    *,
    application_number: str,
) -> dict[str, Any]:
    """Invoke the governed callable asset and project bounded evidence only."""

    invoke_asset = getattr(inputs, "invoke_asset", None)
    if not callable(invoke_asset):
        raise RuntimeError("Trusted callable-asset invocation is not available in this runtime.")

    envelope = invoke_asset(
        OPENFDA_CALLABLE_ROLE,
        variables={"application_number": application_number},
    )
    if not isinstance(envelope, dict) or envelope.get("status") != "success":
        raise RuntimeError("Trusted callable-asset invocation did not succeed.")

    result = envelope.get("result")
    provenance = envelope.get("provenance")
    if not isinstance(result, dict) or result.get("capability") != OPENFDA_CAPABILITY:
        raise RuntimeError("Trusted callable-asset invocation returned an unexpected result.")
    if result.get("application_number") != application_number:
        raise RuntimeError("Trusted callable-asset invocation returned an unexpected application.")
    if not isinstance(provenance, dict) or provenance.get("callable_asset") is not True:
        raise RuntimeError("Trusted callable-asset invocation provenance is invalid.")
    if provenance.get("role") != OPENFDA_CALLABLE_ROLE:
        raise RuntimeError("Trusted callable-asset invocation role provenance is invalid.")
    if provenance.get("asset_key") != OPENFDA_CALLABLE_ASSET_KEY:
        raise RuntimeError("Trusted callable-asset invocation asset provenance is invalid.")
    if provenance.get("asset_version") != OPENFDA_CALLABLE_ASSET_VERSION:
        raise RuntimeError("Trusted callable-asset invocation version provenance is invalid.")

    return {
        "callable_asset_status": "success",
        "callable_asset_role": OPENFDA_CALLABLE_ROLE,
        "callable_asset_capability": OPENFDA_CAPABILITY,
        "callable_asset_result_present": True,
    }


def _summarize_healthcare_entity_record(record: Any) -> dict[str, Any]:
    """Project bounded Healthcare NLP shape evidence without clinical text."""

    if not isinstance(record, dict):
        raise RuntimeError("Healthcare NLP returned an invalid record.")
    mentions = record.get("entityMentions")
    entities = record.get("entities")
    relationships = record.get("relationships")
    fhir_bundle = record.get("fhirBundle")
    if not isinstance(mentions, list):
        raise RuntimeError("Healthcare NLP entityMentions must be a list.")
    if not isinstance(entities, list):
        raise RuntimeError("Healthcare NLP entities must be a list.")
    if not isinstance(relationships, list):
        raise RuntimeError("Healthcare NLP relationships must be a list.")
    if fhir_bundle is not None and not isinstance(fhir_bundle, dict):
        raise RuntimeError("Healthcare NLP fhirBundle must be an object when present.")

    return {
        "healthcare_nlp_entity_shape_verified": True,
        "healthcare_nlp_entity_mention_count": len(mentions),
        "healthcare_nlp_entity_count": len(entities),
        "healthcare_nlp_relationship_count": len(relationships),
        "healthcare_nlp_fhir_bundle_present": bool(fhir_bundle),
    }


def _run_healthcare_nlp_entities(
    inputs: Any,
    variables: dict[str, Any],
) -> dict[str, Any]:
    """Invoke the governed Healthcare NLP runtime tool."""

    invoke_tool = getattr(inputs, "invoke_tool", None)
    if not callable(invoke_tool):
        raise RuntimeError("Trusted runtime tool invocation is not available in this runtime.")

    text = _resolve_healthcare_text(variables)
    envelope = invoke_tool(
        HEALTHCARE_NLP_TOOL_ROLE,
        input={"body": {"documentContent": text}},
        on_error="raise",
    )
    if not isinstance(envelope, dict) or envelope.get("status") != "completed":
        raise RuntimeError("Healthcare NLP tool invocation did not complete.")
    if envelope.get("capability_ref") != HEALTHCARE_NLP_CAPABILITY:
        raise RuntimeError("Healthcare NLP returned unexpected capability provenance.")

    provenance = envelope.get("provenance")
    if (
        not isinstance(provenance, dict)
        or provenance.get("runtime_mcp_tool") is not True
        or provenance.get("role") != HEALTHCARE_NLP_TOOL_ROLE
    ):
        raise RuntimeError("Healthcare NLP runtime provenance is invalid.")

    records = envelope.get("records")
    if not isinstance(records, list) or len(records) != 1:
        raise RuntimeError("Healthcare NLP proof requires exactly one response record.")

    evidence = {
        "healthcare_nlp_status": "completed",
        "healthcare_nlp_capability": HEALTHCARE_NLP_CAPABILITY,
        "healthcare_nlp_role": HEALTHCARE_NLP_TOOL_ROLE,
        "healthcare_nlp_runtime_provenance_verified": True,
        "healthcare_nlp_record_count": 1,
        "healthcare_nlp_input_char_count": len(text),
    }
    evidence.update(_summarize_healthcare_entity_record(records[0]))
    return evidence


def _run_bedrock_dynamic_skill_analysis(inputs: Any) -> dict[str, Any]:
    """Compose canonical Dynamic Skill context with one Bedrock Agent invocation."""

    memory = _canonical_company_memory(inputs)
    evidence = _dynamic_skill_read_evidence(memory)
    agent_evidence, _ = _invoke_bedrock_agent(
        inputs,
        business_input={
            "company_id": CANONICAL_COMPANY_ID,
            "company_name": CANONICAL_COMPANY_NAME,
            "company_memory_context": memory.read(),
            "task": (
                "Summarize the supplied governed company memory. "
                "Do not claim external research or web access."
            ),
        },
    )
    evidence.update(agent_evidence)
    evidence["bedrock_dynamic_skill_combined_verified"] = True
    return evidence


def _run_bedrock_healthcare_nlp_entities(
    inputs: Any,
    variables: dict[str, Any],
) -> dict[str, Any]:
    """Compose Healthcare NLP aggregate evidence with Bedrock without forwarding clinical text."""

    healthcare = _run_healthcare_nlp_entities(inputs, variables)
    aggregate = {
        "entity_mention_count": healthcare["healthcare_nlp_entity_mention_count"],
        "entity_count": healthcare["healthcare_nlp_entity_count"],
        "relationship_count": healthcare["healthcare_nlp_relationship_count"],
        "fhir_bundle_present": healthcare["healthcare_nlp_fhir_bundle_present"],
    }
    agent_evidence, _ = _invoke_bedrock_agent(
        inputs,
        business_input={
            "task": "Summarize the supplied aggregate Healthcare NLP counts only.",
            "healthcare_nlp_summary": aggregate,
        },
    )
    evidence = dict(healthcare)
    evidence.update(agent_evidence)
    evidence["bedrock_healthcare_nlp_combined_verified"] = True
    evidence["bedrock_healthcare_nlp_raw_clinical_text_forwarded"] = False
    return evidence


def _render_inert_bedrock_evidence(text: str) -> str:
    """Render model text as inert quoted evidence for the synthetic mutation fixture."""

    return "Bedrock synthetic analysis (evidence only):\n\n" + "\n".join(
        "> " + line if line.strip() else ">"
        for line in text.strip().splitlines()
    )


def _run_bedrock_dynamic_skill_mutation(inputs: Any) -> dict[str, Any]:
    """Use Bedrock to propose a bounded update, then commit only to the synthetic fixture."""

    handle = inputs.dynamic_skill(MUTATION_FIXTURE_ROLE, variables={})
    provenance = handle.provenance()
    if provenance.mutable is not True or provenance.role != MUTATION_FIXTURE_ROLE:
        raise RuntimeError("Synthetic Dynamic Skill fixture is not mutable.")

    baseline = handle.read()
    if not isinstance(baseline, str) or not baseline.strip():
        raise RuntimeError("Synthetic Dynamic Skill fixture is empty.")
    if len(baseline) > MAX_COMPANY_MEMORY_CHARS:
        raise RuntimeError("Synthetic Dynamic Skill fixture exceeds the proof input bound.")

    agent_evidence, result = _invoke_bedrock_agent(
        inputs,
        business_input={
            "fixture_company_id": MUTATION_FIXTURE_COMPANY_ID,
            "fixture_memory_context": baseline,
            "task": (
                "Return a concise plain-text synthetic analysis suitable for a test-only "
                "memory update. Do not claim web research."
            ),
        },
    )

    changes = handle.new_changeset().upsert_section(
        SYNTHETIC_ANALYSIS_SECTION,
        _render_inert_bedrock_evidence(result["text"]),
    )
    before_digest = handle.content_digest()
    preview = handle.preview(changes)
    if preview.diff.old_digest != before_digest:
        raise RuntimeError("Dynamic Skill mutation preview baseline digest mismatch.")
    if preview.diff.new_digest == before_digest:
        raise RuntimeError("Dynamic Skill mutation preview produced no change.")

    receipt = handle.apply(changes, expected_digest=before_digest)
    if receipt.after_content_digest == before_digest:
        raise RuntimeError("Dynamic Skill mutation commit produced no content change.")

    evidence = dict(agent_evidence)
    evidence.update(
        {
            "dynamic_skill_fixture_company_id": int(MUTATION_FIXTURE_COMPANY_ID),
            "dynamic_skill_mutation_applied": True,
            "dynamic_skill_before_digest": before_digest,
            "dynamic_skill_after_digest": receipt.after_content_digest,
            "dynamic_skill_change_id": receipt.change_id,
            "dynamic_skill_operation_count": receipt.operation_count,
            "dynamic_skill_fresh_readback_required": True,
        }
    )
    return evidence


def _required_safe_token(
    variables: dict[str, Any],
    key: str,
    *,
    prefix: str | None = None,
    max_length: int = 256,
) -> str:
    """Return one bounded opaque verification token."""

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
    """Verify a synthetic Dynamic Skill mutation from a fresh adapter execution."""

    expected_change_id = _required_safe_token(
        variables, "expected_change_id", max_length=256
    )
    expected_after_digest = _required_safe_token(
        variables, "expected_after_digest", prefix="sha256:", max_length=80
    )

    handle = inputs.dynamic_skill(MUTATION_FIXTURE_ROLE, variables={})
    if handle.content_digest() != expected_after_digest:
        raise RuntimeError("Fresh Dynamic Skill readback digest mismatch.")

    history = handle.history(limit=50)
    latest = history.latest_change()
    if latest is None or latest.change_id != expected_change_id:
        raise RuntimeError("Fresh Dynamic Skill history does not contain the expected change.")
    if latest.after_content_digest != expected_after_digest:
        raise RuntimeError("Fresh Dynamic Skill history digest mismatch.")

    return {
        "dynamic_skill_fixture_company_id": int(MUTATION_FIXTURE_COMPANY_ID),
        "dynamic_skill_fresh_readback_verified": True,
        "dynamic_skill_history_verified": True,
        "dynamic_skill_verified_change_id": expected_change_id,
        "dynamic_skill_verified_after_digest": expected_after_digest,
    }


def _run_bedrock_full_composition(
    inputs: Any,
    variables: dict[str, Any],
) -> dict[str, Any]:
    """Exercise Fixed Skill, Dynamic Skill, callable asset, Healthcare NLP, and Bedrock in one run."""

    application_number = _resolve_application_number(variables)
    fixed = _read_fixed_skill(inputs)
    memory = _canonical_company_memory(inputs)
    dynamic = _dynamic_skill_read_evidence(memory)
    callable_evidence = _run_callable_api_lookup(
        inputs,
        application_number=application_number,
    )
    healthcare = _run_healthcare_nlp_entities(inputs, variables)

    safe_summary = {
        "fixed_skill_status": fixed["fixed_skill_status"],
        "dynamic_skill_company_id": dynamic["dynamic_skill_company_id"],
        "callable_asset_status": callable_evidence["callable_asset_status"],
        "healthcare_entity_count": healthcare["healthcare_nlp_entity_count"],
    }
    agent, _ = _invoke_bedrock_agent(
        inputs,
        business_input={
            "company_id": CANONICAL_COMPANY_ID,
            "company_name": CANONICAL_COMPANY_NAME,
            "company_memory_context": memory.read(),
            "capability_summary": safe_summary,
            "task": (
                "Confirm the supplied governed capability summary and company context "
                "in a concise response. Do not claim web research."
            ),
        },
    )

    evidence: dict[str, Any] = {}
    evidence.update(fixed)
    evidence.update(dynamic)
    evidence.update(callable_evidence)
    evidence.update(healthcare)
    evidence.update(agent)
    evidence["bedrock_full_composition_verified"] = True
    return evidence


class NusaibahBedrockAgentCapabilityLabAdapter(Adapter):
    """Reference adapter for governed AWS Bedrock Agent capability proofs."""

    key: ClassVar[str] = "nusaibah.bedrock_agent_capability_lab"
    version: ClassVar[str] = "0.1.2"

    def invoke(
        self,
        inputs: Any,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one bounded proof stage through trusted runtime helpers only."""

        del context

        records = _resolve_records(inputs)
        variables = _resolve_variables(inputs)
        plan = validate_execution_plan(variables.get("execution_plan"))
        proof_stage = _resolve_proof_stage(variables)

        capability_result: dict[str, Any] = {
            "record_count": len(records),
            "variables_present": bool(variables),
            "proof_stage": proof_stage,
            "execution_plan_schema": plan.schema_version,
            "execution_plan_company_id": plan.company_id,
            "execution_plan_step_count": len(plan.steps),
        }

        if proof_stage == "bedrock_agent_invocation":
            capability_result.update(_run_bedrock_agent_invocation(inputs))

        elif proof_stage == "fixed_skill_read":
            capability_result.update(_read_fixed_skill(inputs))

        elif proof_stage == "dynamic_skill_read":
            if plan.company_id != int(CANONICAL_COMPANY_ID):
                raise ValueError("dynamic_skill_read requires execution_plan.company_id=13.")
            capability_result.update(_run_dynamic_skill_read(inputs))

        elif proof_stage == "callable_asset_api":
            capability_result.update(
                _run_callable_api_lookup(
                    inputs,
                    application_number=_resolve_application_number(variables),
                )
            )

        elif proof_stage == "healthcare_nlp_entities":
            capability_result.update(_run_healthcare_nlp_entities(inputs, variables))

        elif proof_stage == "bedrock_dynamic_skill_analysis":
            if plan.company_id != int(CANONICAL_COMPANY_ID):
                raise ValueError(
                    "bedrock_dynamic_skill_analysis requires execution_plan.company_id=13."
                )
            capability_result.update(_run_bedrock_dynamic_skill_analysis(inputs))

        elif proof_stage == "bedrock_healthcare_nlp_entities":
            capability_result.update(
                _run_bedrock_healthcare_nlp_entities(inputs, variables)
            )

        elif proof_stage == "bedrock_dynamic_skill_mutation":
            capability_result.update(_run_bedrock_dynamic_skill_mutation(inputs))

        elif proof_stage == "dynamic_skill_commit_verify":
            capability_result.update(_verify_dynamic_skill_commit(inputs, variables))

        elif proof_stage == "bedrock_full_composition":
            if plan.company_id != int(CANONICAL_COMPANY_ID):
                raise ValueError(
                    "bedrock_full_composition requires execution_plan.company_id=13."
                )
            capability_result.update(
                _run_bedrock_full_composition(inputs, variables)
            )

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {"capability_result": capability_result},
            "logs": [
                {
                    "level": "info",
                    "message": f"Bedrock capability proof stage completed: {proof_stage}.",
                }
            ],
            "metrics": {
                "record_count": len(records),
                "proof_stage_validated": 1,
                "logical_bedrock_agent_invocations": (
                    1
                    if proof_stage
                    in {
                        "bedrock_agent_invocation",
                        "bedrock_dynamic_skill_analysis",
                        "bedrock_healthcare_nlp_entities",
                        "bedrock_dynamic_skill_mutation",
                        "bedrock_full_composition",
                    }
                    else 0
                ),
                "logical_callable_asset_invocations": (
                    1
                    if proof_stage in {"callable_asset_api", "bedrock_full_composition"}
                    else 0
                ),
                "logical_runtime_tool_invocations": (
                    1
                    if proof_stage
                    in {
                        "healthcare_nlp_entities",
                        "bedrock_healthcare_nlp_entities",
                        "bedrock_full_composition",
                    }
                    else 0
                ),
                "dynamic_skill_mutations": (
                    1 if proof_stage == "bedrock_dynamic_skill_mutation" else 0
                ),
            },
        }
