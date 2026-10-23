"""Regressions for the real file-binding/range transport mismatch; no providers."""
from copy import deepcopy
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import uuid
import pytest
from fakes import ASSET_ROOT
from test_v010_completion_range import selected
from clinical_failure_intelligence.product_range_v0_1_11 import range_selection,scoped_inputs
from clinical_failure_intelligence.contracts_v0_1_11 import ContractError
from clinical_failure_intelligence.orchestration_v0_1_11 import run_analysis
from clinical_failure_intelligence.range_workflow_v0_1_11 import ProductRangeWorkflow


def bound():
    data=selected();data['variables']['source_object_id']=148
    return data


def test_file_selector_survives_selection_case_hydration_and_scientific_preflight():
    data=bound();plan=range_selection(data)['outputs']['product_selection']
    assert plan['selection_receipt']['selected_product_ids']==['P0','P1']
    for case in plan['cases']:
        assert case['variables']['source_object_id']==148
        hydrated={'variables':case['variables'],'clinical_context':data['clinical_context']}
        scoped,receipt=scoped_inputs(hydrated)
        assert scoped['variables']['source_object_id']==148
        result=run_analysis(scoped)
        assert result['outputs']['clinical_intelligence']['asset'].endswith('@0.1.11')
        assert result['outputs']['clinical_intelligence']['subject']['product_id']==case['product_id']
        assert result['metrics']['logical_agent_calls']==0


@pytest.mark.parametrize('bad',[True,False,0,-1,'148',None,1.5])
def test_invalid_transport_selector_rejected_before_dispatch(bad):
    data=bound();data['variables']['source_object_id']=bad
    with pytest.raises(ContractError,match='source_object_id_invalid'):range_selection(data)


@pytest.mark.parametrize('field,value',[('product_id','P0'),('subject_id','CASE'),('event_ids',['0']),('indication_id','I'),('trial_id','NCT03626545')])
def test_real_case_selectors_still_conflict_with_range(field,value):
    data=bound();data['variables'][field]=value
    with pytest.raises(ContractError,match='selector_conflict'):range_selection(data)


def test_transport_selector_cannot_disable_snapshot_revalidation():
    data=bound();plan=range_selection(data)['outputs']['product_selection']
    envelope=deepcopy(data['clinical_context']);envelope['provenance']['sha256']='b'*64
    with pytest.raises(ContractError,match='snapshot_changed'):
        scoped_inputs({'variables':plan['cases'][0]['variables'],'clinical_context':envelope})


def test_two_product_orchestrator_carries_binding_selector_to_every_case_request():
    data=bound();calls=[]
    def factory(key,variables):
        def execute(asset,version,output,values,**kwargs):
            calls.append((key,deepcopy(values)))
            assert version=='0.1.11' and values['source_object_id']==148
            if output=='product_selection':
                return {'run_uuid':str(uuid.uuid4()),'result':range_selection(data)['outputs'][output]}
            return {'run_uuid':str(uuid.uuid4()),'result':{'subject':{'product_id':values['product_id']}}}
        return execute
    result=ProductRangeWorkflow(factory).run(data['variables'])
    assert result['status']=='preflight_completed' and len(result['cases'])==2
    assert len(calls)==3


def test_all_published_runtime_bytes_and_manifest_versions_preserved():
    frozen=json.loads((ASSET_ROOT/'tests/reference/published_010_frozen.json').read_text())
    for name,checksum in frozen['files'].items():assert hashlib.sha256((ASSET_ROOT/name).read_bytes()).hexdigest()==checksum
    manifest=json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())
    for version,checksum in frozen['versions'].items():
        assert hashlib.sha256(json.dumps(manifest['versions'][version],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()==checksum


def operator(name):
    directory=ASSET_ROOT/'tests/operator';sys.path.insert(0,str(directory))
    spec=importlib.util.spec_from_file_location('clinical011_test_'+name,directory/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('normalized_ack',[True,False])
def test_sdk_host_preserves_explicit_queue_and_collects_warning_completion(tmp_path,monkeypatch,normalized_ack):
    from devtools import obs_api_client,asset_preflight,preview_result_inspect
    host_module=operator('run_clinical_workflow');captured=[]
    asset='nusaibah.clinical_failure_intelligence';run=str(uuid.uuid4())
    env=tmp_path/'test.env';env.write_text('OBS_BASE_URL=http://127.0.0.1:1\nOBS_API_KEY_HEADER=X-Test\nOBS_API_KEY=test-only\nOBS_CLIENT_ID=1\n')
    config={'substrate':'local_worker','assets':{asset:{'entity_key':'TEST_ENTITY','queue_name':'clinical011-qualified'}}}
    monkeypatch.setattr(asset_preflight,'_request_asset_preflight',lambda *a,**k:{'http_status':200,'decoded':{'data':{'status':'ready'}}})
    def execute(**kwargs):
        captured.append(kwargs['payload'])
        return {'run_uuid':run,'initial_status':'pending'} if normalized_ack else {'data':{'run_uuid':run}}
    monkeypatch.setattr(obs_api_client,'execute_asset',execute)
    monkeypatch.setattr(obs_api_client,'poll_run',lambda **k:{'terminal':True,'final_status':'completed_with_warnings'})
    def download(connection,run_uuid,destination,source_app):
        body=json.dumps({'run_uuid':run,'asset_identity':asset+':0.1.11','outputs':{'clinical_intelligence':{'ok':True}}}).encode()
        Path(destination).write_bytes(body);return {'checksum_sha256':hashlib.sha256(body).hexdigest()}
    monkeypatch.setattr(preview_result_inspect,'download_preview_result',download)
    host=host_module.SdkWorkflowHost(config,{},str(env),tmp_path/'checkpoint.json')
    result=host.execute(asset,'0.1.11','clinical_intelligence',{})
    assert result['result']=={'ok':True} and captured[0]['queue_name']=='clinical011-qualified'
    assert captured[0]['retain_preview_result'] is True
    assert host.execute(asset,'0.1.11','clinical_intelligence',{})==result and len(captured)==1


def test_live_range_requires_explicit_worker_queues_before_checkpoint_or_network(tmp_path):
    module=operator('run_product_range')
    config=tmp_path/'config.json';config.write_text(json.dumps({'substrate':'local_worker','assets':{}}))
    variables=tmp_path/'variables.json';variables.write_text(json.dumps(bound()['variables']))
    with pytest.raises(module.ContractError,match='execution_queue_required'):
        module.main(['--config',str(config),'--variables-file',str(variables),'--product-index-range','0:1',
            '--checkpoint-directory',str(tmp_path/'checkpoints'),'--env-file','unused.env','--live'])
    assert not (tmp_path/'checkpoints').exists()
