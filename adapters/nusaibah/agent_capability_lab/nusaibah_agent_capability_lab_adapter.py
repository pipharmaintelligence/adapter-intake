from __future__ import annotations

from typing import Any, ClassVar

from adapters.base import Adapter

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

# Defensive local input bound for variables.application_number.
# This prevents accidentally sending an unexpectedly large semantic identifier
# into the governed Agent invocation path.
MAX_APPLICATION_NUMBER_LENGTH = 128


ALLOWED_PROOF_STAGES = {
    "scaffold",
    "agent_invocation",
    "fixed_skill_read",
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
    """Return a bounded OpenFDA application number for the agent proof.

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
            "for the agent_invocation proof stage."
        )

    application_number = str(raw_value).strip()

    if not application_number:
        raise ValueError(
            "variables.application_number is required "
            "for the agent_invocation proof stage."
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
    version: ClassVar[str] = "0.1.1"

    def invoke(
        self,
        inputs: Any,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one bounded capability-lab proof stage.

        Args:
            inputs: Runtime-provided inputs. The object may expose trusted
                capability helpers such as ``invoke_agent`` and ``skill``.
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
            capability_result.update(_read_fixed_skill(inputs))

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
            },
        }