from copy import deepcopy
import pytest
from test_v018_completion import Inputs
from fakes import example_inputs
from clinical_failure_intelligence import orchestration_v0_1_13 as orchestration
from clinical_failure_intelligence.deferred_work_v0_1_13 import freeze_packet,hydrate_task
from clinical_failure_intelligence.contracts_v0_1_13 import digest,canonical_bytes,ContractError

def test_small_case_still_completes_all_roles_and_memory_preview():
    inputs=Inputs();dto=orchestration.run_analysis(inputs)['outputs']['clinical_intelligence']
    assert dto['asset'].endswith('@0.1.13') and dto['quality']['status']=='completed'
    assert all(dto['quality']['required_roles_completed'].values())
    assert dto['memory_update']['write_attempted'] is False

def test_expanding_hypothesis_plan_cannot_starve_every_critic(monkeypatch):
    original=orchestration.evidence_batches
    def expanded(rows,packet,**options):
        batches=original(rows,packet,**options)
        return batches*70 if packet([]).get('role')=='hypothesis_analyst' and packet([]).get('case_assessments') else batches
    monkeypatch.setattr(orchestration,'evidence_batches',expanded)
    raw=example_inputs();raw['variables'].update(max_agent_calls=64,enable_refinement=False)
    inputs=Inputs(raw);dto=orchestration.run_analysis(inputs)['outputs']['clinical_intelligence']
    assert dto['execution']['logical_agent_calls']<=64
    assert any(role=='evidence_critic' and not packet.get('review_kind') for role,packet in inputs.calls)
    assert any(item['review_status']=='automated_reviewed' for item in dto['case_assessments']+dto['hypothesis_results'])
    assert any(s['role']=='hypothesis_analyst' and s['status']=='deferred' for s in dto['execution']['stages'])
    assert dto['deferred_work']['automatic_replay'] is False
    assert dto['evidence'] and dto['memory_update']['write_attempted'] is False

def test_common_deferred_context_roundtrips_without_copying_or_authority():
    evidence=[];objects={};original={'case_assessments':[{'id':'C','statement':'whole synthetic value '*1000}], 'methodology':{'text':'fixed policy '*1000},'evidence_packet':[]}
    frozen=[freeze_packet(original,objects) for _ in range(80)]
    assert len(canonical_bytes({'packets':frozen,'objects':objects})) < len(canonical_bytes([original]*80))//8
    task={'input_packet':frozen[0],'input_digest':digest(original)}
    deferred={'source_ledger_digest':digest(evidence),'objects':objects}
    assert hydrate_task(task,deferred,evidence)==original
    bad=deepcopy(deferred);next(iter(bad['objects'].values()))['value']='changed'
    with pytest.raises(ContractError):hydrate_task(task,bad,evidence)

def test_legacy_frozen_task_still_hydrates_and_source_drift_fails():
    packet={'evidence_packet':[],'methodology':{'text':'legacy'}}
    task={'input_packet':packet,'input_digest':digest(packet)}
    deferred={'source_ledger_digest':digest([]),'objects':{}}
    assert hydrate_task(task,deferred,[])==packet
    with pytest.raises(ContractError):hydrate_task(task,deferred,[{'evidence_id':'forged'}])


def test_published_012_bytes_and_manifest_are_unchanged():
    from fakes import ASSET_ROOT
    import hashlib,json
    fixture=json.loads((ASSET_ROOT/'tests/reference/published_0_1_12_frozen.json').read_text())
    for name,checksum in fixture['files'].items():
        assert hashlib.sha256((ASSET_ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==checksum
    manifest=json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())
    assert hashlib.sha256(json.dumps(manifest['versions']['0.1.12'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()==fixture['version_sha256']


def test_context_reference_shaped_literal_data_is_not_interpreted_as_authority():
    original={'value':{'$context':'literal-business-value'},'evidence_packet':[]}
    objects={};task={'input_packet':freeze_packet(original,objects),'input_digest':digest(original)}
    assert hydrate_task(task,{'objects':objects,'source_ledger_digest':digest([])},[])==original


def test_size_warning_does_not_reclassify_completed_science_or_discard_evidence():
    from clinical_failure_intelligence.decision_outcome_v0_1_13 import finalize_output
    from clinical_failure_intelligence.rendering_v0_1_13 import validate_result
    dto=orchestration.run_analysis(Inputs())['outputs']['clinical_intelligence']
    evidence=deepcopy(dto['evidence']);roles=deepcopy(dto['quality']['required_roles_completed'])
    result=finalize_output(dto,max_bytes=1)
    assert result['quality']['status']=='completed'
    assert any(i['code']=='clinical_canonical_result_size_warning' for i in result['quality']['issues'])
    assert result['evidence']==evidence and result['quality']['required_roles_completed']==roles
    validate_result(result)
