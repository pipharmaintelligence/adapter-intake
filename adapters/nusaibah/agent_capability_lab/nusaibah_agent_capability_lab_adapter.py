from __future__ import annotations

from typing import Any, ClassVar

from adapters.base import Adapter
from devtools.agent_citation_view import AgentCitationView
from devtools.public_reference import ReferenceTarget

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
MAX_COMPANY_MEMORY_CHARS = 12000

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
    "vertex_grounded_dynamic_skill",
    "dynamic_skill_commit_verify",
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
    """

    key: ClassVar[str] = "nusaibah.agent_capability_lab"
    version: ClassVar[str] = "0.1.10"

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
                    }
                    else 0
                ),
                "dynamic_skill_mutations": (
                    1 if proof_stage == "vertex_grounded_dynamic_skill" else 0
                ),
            },
        }