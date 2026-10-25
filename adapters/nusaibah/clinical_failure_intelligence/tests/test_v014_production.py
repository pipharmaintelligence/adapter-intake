"""Provider-free production planning and retained-scope regressions."""

from copy import deepcopy
import hashlib, json
import pytest
from fakes import ASSET_ROOT, example_inputs
from test_v018_completion import Inputs
from clinical_failure_intelligence import orchestration_v0_1_14 as current
from clinical_failure_intelligence.orchestration_v0_1_13 import (
    run_analysis as prior_analysis,
)
from clinical_failure_intelligence.deferred_work_v0_1_13 import deferred_work
from clinical_failure_intelligence.continuation_v0_1_14 import (
    continue_analysis,
    preparation,
)
from clinical_failure_intelligence.contracts_v0_1_14 import (
    ContractError,
    digest,
    parse_request,
)
from clinical_failure_intelligence.runtime_access_v0_1_14 import AgentRunner
from clinical_failure_intelligence.policies_v0_1_14 import Budget, ExecutionPolicy
from clinical_failure_intelligence.review_packets_v0_1_14 import critic_batches


def test_small_case_remains_complete_and_candidate_cap_is_in_real_schema():
    host = Inputs()
    dto = current.run_analysis(host)["outputs"]["clinical_intelligence"]
    assert dto["asset"].endswith("@0.1.14") and dto["quality"]["status"] == "completed"
    assert all(dto["quality"]["required_roles_completed"].values())
    assert not dto["memory_update"]["write_attempted"]
    packets = [p for role, p in host.calls if role == "hypothesis_analyst"]
    assert packets and all(
        p["response_contract"]["json_schema"]["properties"]["items"]["maxItems"]
        == p["candidate_budget"]["max_items"]
        for p in packets
    )


def test_actual_review_cost_protected_when_hypothesis_plan_expands(monkeypatch):
    original = current.evidence_batches

    def expanded(rows, packet, **options):
        chunks = original(rows, packet, **options)
        return (
            chunks * 70
            if packet([]).get("role") == "hypothesis_analyst"
            and packet([]).get("case_assessments")
            else chunks
        )

    monkeypatch.setattr(current, "evidence_batches", expanded)
    ordinary = current.critic_batches

    def one_candidate(*args, **kwargs):
        kwargs["max_items"] = 1
        return ordinary(*args, **kwargs)

    monkeypatch.setattr(current, "critic_batches", one_candidate)
    raw = example_inputs()
    raw["variables"].update(max_agent_calls=64, enable_refinement=False)
    host = Inputs(raw)
    dto = current.run_analysis(host)["outputs"]["clinical_intelligence"]
    assert dto["execution"]["logical_agent_calls"] <= 64
    assert any(
        p.get("phase") == "hypothesis_review_admission" and p["known_review_calls"] > 1
        for p in dto["execution"]["phase_plans"]
    )
    assert any(
        s["role"] == "hypothesis_analyst" and s["status"] == "deferred"
        for s in dto["execution"]["stages"]
    )
    assert all(
        i["review_status"] == "automated_reviewed"
        for i in dto["case_assessments"] + dto["hypothesis_results"]
    )
    assert not any(
        i["code"] == "clinical_critic_item_not_reviewed"
        for i in dto["quality"]["issues"]
    )
    assert (
        not dto["deferred_work"]["automatic_replay"]
        and not dto["memory_update"]["write_attempted"]
    )


def pending_013():
    prior = prior_analysis(Inputs())["outputs"]["clinical_intelligence"]
    original = deepcopy(prior["hypothesis_results"][0])
    prior["hypothesis_results"] = []
    for index in range(4):
        item = deepcopy(original)
        item.update(
            item_id="test_hypothesis_" + str(index),
            review_status="unreviewed",
            accepted=False,
            review_reason="clinical_critic_item_not_reviewed",
        )
        prior["hypothesis_results"].append(item)
    prior["quality"]["status"] = "partial"
    prior["quality"]["required_roles_completed"]["evidence_critic"] = False
    prior["deferred_work"] = deferred_work(prior, {})
    data = example_inputs()
    selected = [
        task["work_id"]
        for task in prior["deferred_work"]["tasks"]
        if task["kind"] == "candidate_review"
    ][:3]
    data["variables"].update(
        resume_work_ids=selected, max_continuation_calls=8, memory_mode="off"
    )
    data["previous_assessment_013"] = {
        "value": prior,
        "provenance": {
            "source": "retained_asset_output",
            "authority": "core_artifact",
            "run_uuid": "11111111-2222-4333-8444-555555555555",
            "asset_identity": "nusaibah.clinical_failure_intelligence:0.1.13",
            "output_role": "clinical_intelligence",
            "checksum_sha256": "a" * 64,
        },
    }
    return data


def test_selected_013_continuation_batches_reviews_without_research_or_scope_growth():
    data = pending_013()
    before = deepcopy(data["previous_assessment_013"]["value"])
    host = Inputs(data)
    outputs = continue_analysis(host)["outputs"]
    dto = outputs["clinical_intelligence"]
    assert len(host.calls) == 1 and host.calls[0][0] == "evidence_critic"
    assert len(host.calls[0][1]["candidate_items"]) == 3
    assert dto["case_assessments"] == before["case_assessments"]
    assert dto["hypothesis_results"][-1] == before["hypothesis_results"][-1]
    assert (
        dto["evidence"] == before["evidence"]
        and data["previous_assessment_013"]["value"] == before
    )
    assert len(outputs["continuation_receipt"]["resolved_work_ids"]) == 3
    assert not dto["memory_update"]["write_attempted"]


@pytest.mark.parametrize(
    "change",
    ["wrong_identity", "caller_authority", "two_retained_roles", "source_drift"],
)
def test_new_retained_role_fails_closed_before_any_dispatch(change):
    data = pending_013()
    if change == "wrong_identity":
        data["previous_assessment_013"]["provenance"][
            "asset_identity"
        ] = "nusaibah.clinical_failure_intelligence:0.1.12"
    elif change == "caller_authority":
        data["previous_assessment_013"]["provenance"]["authority"] = "caller"
    elif change == "two_retained_roles":
        data["previous_continuation"] = deepcopy(data["previous_assessment_013"])
    else:
        data["clinical_context"]["evidence"][0]["text"] += " changed"
    host = Inputs(data)
    with pytest.raises(ContractError):
        continue_analysis(host)
    assert not host.calls


def test_candidate_budget_must_be_small_integer_and_role_scoped():
    host = Inputs()
    runner = AgentRunner(host, Budget(ExecutionPolicy()))
    request = parse_request(host)
    for bad in [False, 0, 33, "4"]:
        with pytest.raises(ContractError):
            runner.packet(
                "hypothesis_analyst",
                request,
                task_id="test",
                obligations=["hypothesis_assessment"],
                packet_data={"candidate_budget": {"max_items": bad}},
            )
    with pytest.raises(ContractError):
        runner.packet(
            "evidence_critic",
            request,
            task_id="test",
            obligations=["review:test"],
            packet_data={"candidate_budget": {"max_items": 1}},
        )


def test_published_013_modules_and_manifest_remain_exact():
    fixture = json.loads(
        (ASSET_ROOT / "tests/reference/published_0_1_13_frozen.json").read_text(
            encoding="utf-8"
        )
    )
    for name, checksum in fixture["files"].items():
        assert (
            hashlib.sha256(
                (ASSET_ROOT / name).read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
            == checksum
        )
    manifest = json.loads(
        (ASSET_ROOT / "clinical_failure_intelligence.asset.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        hashlib.sha256(
            json.dumps(
                manifest["versions"]["0.1.13"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        == fixture["version_sha256"]
    )
    assert manifest["versions"]["0.1.14"]["inputs"]["previous_assessment_013"][
        "retained_output"
    ]["asset_identity"].endswith(":0.1.13")


@pytest.mark.parametrize("always_omit", [False, True])
def test_missing_critic_verdict_retries_only_omitted_identity_without_recursion(
    always_omit,
):
    omitted = []

    def omit(value, packet):
        if not packet.get("candidate_items"):
            return value
        if not packet.get("missing_verdict_recovery"):
            key = packet["candidate_items"][0]["item_id"]
            omitted.append(key)
            value["items"] = [row for row in value["items"] if row["item_id"] != key]
        elif always_omit:
            value["items"] = []
        return value

    data = example_inputs()
    data["variables"].update(enable_refinement=True, memory_mode="off")
    host = Inputs(data, transforms={"evidence_critic": omit})
    dto = current.run_analysis(host)["outputs"]["clinical_intelligence"]
    retries = [
        packet for role, packet in host.calls if packet.get("missing_verdict_recovery")
    ]
    assert retries and len(retries) <= 2
    assert all(len(packet["candidate_items"]) == 1 for packet in retries)
    assert all(packet["candidate_items"][0]["item_id"] in omitted for packet in retries)
    assert dto["execution"]["logical_agent_calls"] <= 64
    if always_omit:
        assert dto["quality"]["status"] == "partial"
        assert any(
            row["kind"] == "candidate_review" for row in dto["deferred_work"]["tasks"]
        )
    else:
        assert all(
            row["review_status"] == "automated_reviewed"
            for row in dto["case_assessments"] + dto["hypothesis_results"]
        )
    assert not dto["memory_update"]["write_attempted"]


def test_production_deadline_cannot_outlive_the_new_case_execution_manifest():
    data = example_inputs()
    data["variables"]["max_product_seconds"] = 3601
    with pytest.raises(ContractError, match="clinical_product_time_budget_invalid"):
        parse_request(data)
    data["variables"]["max_product_seconds"] = 3600
    assert parse_request(data)["max_product_seconds"] == 3600
    assert ExecutionPolicy().deadline_seconds == 3600


def test_new_version_review_metadata_and_schema_are_explicitly_declared_for_promotion():
    handoff = (ASSET_ROOT / "adapter.yaml").read_text()
    for filename in [
        "admission_requirements_v0_1_14.json",
        "clinical_intelligence_v0_1_14.schema.json",
        "PRODUCTION_READINESS_0_1_14.md",
    ]:
        assert handoff.count("  - " + filename + "\n") == 1
        assert (ASSET_ROOT / filename).is_file()


def test_unchanged_agent_contracts_keep_real_reviewed_prompt_files():
    current = json.loads(
        (ASSET_ROOT / "admission_requirements_v0_1_14.json").read_text()
    )
    old = json.loads((ASSET_ROOT / "admission_requirements_v0_1_13.json").read_text())
    assert len(current["agent_contracts"]) == 8
    for before, after in zip(old["agent_contracts"], current["agent_contracts"]):
        assert before == after
        assert (ASSET_ROOT / after["prompt_file"]).is_file()


def snapshot():
    return {
        "source_ref": "aib_" + "1" * 32,
        "file_sha256": "b" * 64,
        "record_count": 508,
        "access_mode": "file_object",
        "complete": True,
    }


def test_same_file_new_core_binding_is_recorded_without_saved_authority():
    from clinical_failure_intelligence.continuation_v0_1_14 import (
        _source_snapshot_transition,
    )

    old = snapshot()
    new = deepcopy(old)
    new.update(source_ref="aib_" + "2" * 32, file_sha256="sha256:" + old["file_sha256"])
    receipt = _source_snapshot_transition(old, new)
    assert (
        receipt["canonical_file_unchanged"]
        and receipt["current_core_binding_authority_required"]
    )
    assert not receipt["saved_result_grants_authority"] and old == snapshot()


@pytest.mark.parametrize(
    "field,value",
    [
        ("file_sha256", "c" * 64),
        ("record_count", 507),
        ("access_mode", "partition_file"),
        ("complete", False),
        ("source_ref", "caller_invented"),
    ],
)
def test_binding_handoff_cannot_hide_a_changed_or_incomplete_snapshot(field, value):
    from clinical_failure_intelligence.continuation_v0_1_14 import (
        _source_snapshot_transition,
    )

    old = snapshot()
    new = {**old, "source_ref": "aib_" + "2" * 32, field: value}
    with pytest.raises(
        ContractError, match="clinical_continuation_input_snapshot_changed"
    ):
        _source_snapshot_transition(old, new)


def test_signed_qualification_can_use_zero_agent_finalization_record_path():
    from jsonschema import Draft202012Validator

    data = pending_013()
    old_proof = snapshot()
    new_proof = {**old_proof, "source_ref": "aib_" + "2" * 32}
    prior = data["previous_assessment_013"]["value"]
    prior["source_event_metadata"] = {"provenance": old_proof}
    data["clinical_context"]["source_event_metadata"] = {"provenance": new_proof}
    data["variables"].update(
        finalize_only=True,
        resume_work_ids=[],
        preflight_only=False,
        memory_mode="off",
        enable_refinement=False,
        supplementary_search=False,
        enable_pharmacological_class=False,
        prepare_result_for_persistence=True,
    )
    before = deepcopy(prior)
    host = Inputs(data)
    output = continue_analysis(host)["outputs"]
    dto = output["clinical_intelligence"]
    assert not host.calls and output["clinical_intelligence_records"]["records"] == [
        dto
    ]
    assert dto["evidence"] == before["evidence"] and dto["quality"] == before["quality"]
    assert not dto["execution"]["retained_finalization"][
        "scientific_processing_repeated"
    ]
    assert dto["execution"]["retained_finalization"]["source_binding_transition"][
        "canonical_file_unchanged"
    ]
    assert not dto["publication_readiness"]["publication_confirmed"]
    schema = json.loads(
        (ASSET_ROOT / "clinical_intelligence_v0_1_14.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(dto)
