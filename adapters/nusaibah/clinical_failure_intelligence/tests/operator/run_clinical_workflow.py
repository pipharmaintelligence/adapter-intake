"""Official SDK orchestration; default is a no-network plan, not clinical execution.

Source adapters execute independently. Clinical inputs contain only retained
producer run UUIDs and the approved clinical-context binding. No nested calls,
direct Core/storage/provider traffic or raw input-role overrides are introduced.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import uuid
from contextlib import contextmanager

ASSET_ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ASSET_ROOT.parent))
from clinical_failure_intelligence.contracts import ContractError, digest, require, safe_json
from clinical_failure_intelligence.source_workflow import ClinicalSourceWorkflow, SourceReadUnavailable

CLINICAL='nusaibah.clinical_failure_intelligence'
VERSION='0.1.2'


def implementation_digest():
    """A resume may not silently change selector, validation or execution code."""
    paths=sorted(ASSET_ROOT.glob('*.py'))+[ASSET_ROOT/'clinical_failure_intelligence.asset.json',Path(__file__)]
    return digest({path.relative_to(ASSET_ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in paths})


@contextmanager
def checkpoint_lock(path):
    """Own only a newly created marker; always release it after preserving state."""
    with path.open('x',encoding='utf-8') as marker:
        marker.write(str(os.getpid()))
    try:
        yield
    finally:
        path.unlink()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path,value):
    temporary=path.with_name(path.name+'.writing')
    with temporary.open('w',encoding='utf-8') as output:
        json.dump(value,output,indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary,path)


def runtime_source_inputs(selection, substrate, references):
    """Forward safe selectors only; Assets/Core remains the admission authority."""
    import re
    sources=selection.get('runtime_source_inputs',{})
    require(isinstance(sources,dict),'clinical_source_configuration_invalid')
    require(not sources or substrate in {'local_worker','ecs'},'clinical_source_substrate_invalid')
    require(not set(sources)&({'variables'}|set(references or {})),'clinical_source_role_collision')
    allowed={'runtime_source_id','operation','capability_ref','input','resolve'}
    for role,value in sources.items():
        require(isinstance(role,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,119}',role)
            and isinstance(value,dict) and set(value)<=allowed,'clinical_source_configuration_invalid')
        require(isinstance(value.get('runtime_source_id'),str) and
            re.fullmatch(r'rt_src_[a-f0-9]{32}',value['runtime_source_id']),
            'clinical_source_configuration_invalid')
        for field in ('operation','capability_ref'):
            require(isinstance(value.get(field),str) and
                re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}',value[field]),'clinical_source_configuration_invalid')
        require(value.get('resolve','eager') in {'eager','lazy'},'clinical_source_configuration_invalid')
        parameters=value.get('input',{})
        require(isinstance(parameters,dict) and not set(parameters)&{'records','metadata','provenance'},
            'clinical_source_configuration_invalid')
        safe_json(parameters)
    return sources


class ConfirmedSourceFailure(SourceReadUnavailable):
    """Known terminal source failure with optional safe SDK status diagnostics."""
    def __init__(self, code, detail):
        super().__init__(code)
        self.detail=detail


def source_failure_detail(api, run_uuid):
    detail={'run_uuid':run_uuid}
    try:
        from devtools.obs_api_client import get_run_status
        response=get_run_status(**api,run_uuid=run_uuid)
        data=response.get('data',{})
        import re
        for field in ('failure_code','failure_cause_code','proof_stage'):
            value=data.get(field)
            if isinstance(value,str) and re.fullmatch(r'[a-z0-9_:-]{1,120}',value):detail[field]=value
    except Exception:
        # Diagnostics are read-only and may be unavailable. Preserve the known
        # failed run identity; never invent a cause or resubmit the execution.
        pass
    return detail


class SdkWorkflowHost:
    """Bounded, checkpointed official SDK submissions and retained-result reads."""
    def __init__(self,config,variables,env_file,checkpoint,*,resume=False):
        from devtools.connection_check import load_env_file
        self.config=config
        self.variables=variables
        self.path=Path(checkpoint).resolve()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.artifacts=self.path.parent/(self.path.stem+'-retained')
        self.artifacts.mkdir(exist_ok=True)
        env=load_env_file(env_file)
        self.env=env
        self.api={'base_url':env.get('OBS_BASE_URL',''),'api_key_header':env.get('OBS_API_KEY_HEADER',''),
                  'api_key':env.get('OBS_API_KEY',''),'client_id':env.get('OBS_CLIENT_ID') or env.get('CLIENT_ID'),
                  'source_app':env.get('OBS_SOURCE_APP','clinical-workflow')}
        require(all(self.api[key] for key in ('base_url','api_key_header','api_key','client_id')),
                'clinical_sdk_configuration_missing')
        require(config.get('substrate','local_worker') in {'local_worker','ecs'},'clinical_substrate_invalid')
        identity=digest({'config':config,'variables':variables,'client_id':self.api['client_id'],
                         'server':self.api['base_url'].rstrip('/'),'implementation':implementation_digest()})
        if self.path.exists():
            require(resume,'clinical_checkpoint_exists_use_resume')
            self.state=read(self.path)
            require(self.state.get('identity')==identity,'clinical_checkpoint_identity_mismatch')
        else:
            require(not resume,'clinical_resume_checkpoint_missing')
            self.state={'schema_version':'clinical_workflow_checkpoint.v1','identity':identity,'operations':{},
                        'status':'prepared','maximum_workflow_submissions':14}
            save(self.path,self.state)

    def execute(self,asset,version,output,variables,*,references=None):
        from devtools.obs_api_client import build_asset_execute_payload, execute_asset, poll_run
        from devtools.asset_preflight import _request_asset_preflight
        from devtools.preview_result_inspect import download_preview_result
        safe_json(variables)
        selection=self.config.get('assets',{}).get(asset)
        require(isinstance(selection,dict) and isinstance(selection.get('entity_key'),str),
                'clinical_registered_entity_configuration_missing')
        substrate=self.config.get('substrate','local_worker')
        sources=runtime_source_inputs(selection,substrate,references)
        inputs={'variables':variables,**sources,**(references or {})}
        payload=build_asset_execute_payload(entity_key=selection['entity_key'],asset_key=asset,asset_version=version,
            inputs=inputs,route='agent',mode='balanced',execution_substrate=self.config.get('substrate','local_worker'),
            input_binding_selection=selection.get('input_binding_selection'),retain_preview_result=True)
        if sources:payload['runtime_source_resolution']='worker'
        queue=selection.get('queue_name')
        if queue is not None:
            import re
            require(isinstance(queue,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,120}',queue) is not None,
                    'clinical_execution_queue_invalid')
            payload['queue_name']=queue
        key=digest({'asset':asset,'version':version,'inputs':inputs})
        entry=self.state['operations'].get(key)
        if entry is None:
            require(len(self.state['operations'])<14,'clinical_workflow_submission_budget_exhausted')
            readiness=_request_asset_preflight(self.env,payload=payload,timeout=45)
            require(readiness.get('http_status')==200 and
                    readiness.get('decoded',{}).get('data',{}).get('status')=='ready',
                    'clinical_workflow_admission_not_ready')
            entry={'asset_key':asset,'asset_version':version,'output_role':output,
                   'submission_attempted':True,'run_uuid':None}
            self.state['operations'][key]=entry
            save(self.path,self.state)
            # Save the attempt before transport: unknown acknowledgements are never replayed.
            launched=execute_asset(**self.api,payload=payload)
            data=launched.get('data',{})
            run=launched.get('run_uuid') or data.get('run_uuid') or data.get('run',{}).get('run_uuid')
            require(isinstance(run,str),'clinical_submission_acknowledgement_unconfirmed')
            entry['run_uuid']=str(uuid.UUID(run))
            save(self.path,self.state)
        require(entry.get('run_uuid') is not None,'clinical_submission_outcome_unknown_reconcile_before_resume')
        if entry.get('terminal_status') in {'failed','cancelled','canceled'}:
            if asset==CLINICAL:
                require(False,'clinical_execution_failed_inspect_saved_run')
            raise ConfirmedSourceFailure('source_output_unavailable',entry.get('failure_detail',{'run_uuid':entry['run_uuid']}))
        if not entry.get('completed'):
            polled=poll_run(**self.api,run_uuid=entry['run_uuid'],interval_seconds=3,timeout_seconds=2100)
            status=polled.get('final_status')
            require(polled.get('terminal') is True,'clinical_run_not_terminal_resume_same_checkpoint')
            require(status in {'completed','completed_with_warnings','success','succeeded','failed','cancelled','canceled'},
                    'clinical_run_not_terminal_resume_same_checkpoint')
            entry['terminal_status']=status
            if asset!=CLINICAL and status in {'failed','cancelled','canceled'}:
                entry['failure_detail']=source_failure_detail(self.api,entry['run_uuid'])
            save(self.path,self.state)
            if status not in {'completed','completed_with_warnings','success','succeeded'}:
                if asset==CLINICAL:
                    require(False,'clinical_execution_failed_inspect_saved_run')
                raise ConfirmedSourceFailure('source_output_unavailable',entry.get('failure_detail',{'run_uuid':entry['run_uuid']}))
            destination=self.artifacts/(entry['run_uuid']+'.json')
            if not destination.exists():
                proof=download_preview_result({'obs_base_url':self.api['base_url'],
                    'api_key_header':self.api['api_key_header'],'api_key':self.api['api_key'],
                    'client_id':self.api['client_id']},entry['run_uuid'],str(destination),self.api['source_app'])
                entry['artifact_sha256']=proof['checksum_sha256']
                entry['artifact']=str(destination)
                entry['completed']=True
                save(self.path,self.state)
            else:
                require(entry.get('artifact_sha256') is not None,
                        'clinical_retained_download_outcome_requires_reconciliation')
        path=Path(entry['artifact'])
        require(hashlib.sha256(path.read_bytes()).hexdigest()==entry['artifact_sha256'],
                'clinical_retained_local_integrity_failed')
        retained=read(path)
        require(retained.get('run_uuid')==entry['run_uuid'] and retained.get('asset_identity')==asset+':'+version
                and isinstance(retained.get('outputs',{}).get(output),dict),'clinical_retained_identity_failed')
        return {'run_uuid':entry['run_uuid'],'result':retained['outputs'][output]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--variables-file',required=True)
    parser.add_argument('--checkpoint',required=True)
    parser.add_argument('--env-file')
    parser.add_argument('--live',action='store_true',help='Allow bounded source reads and clinical preflight.')
    parser.add_argument('--analyze',action='store_true',help='Also allow paid scientific Agent execution; memory remains preview.')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args(argv)
    config,variables=read(args.config),read(args.variables_file)
    safe_json(variables)
    require(not args.analyze or args.live,'clinical_analysis_requires_live')
    if not args.live:
        print(json.dumps({'status':'plan_only','asset':CLINICAL+':'+VERSION,'source_call_limit':12,
                          'publication_limit':3,'maximum_workflow_submissions':14,'nested_calls':False,
                          'provider_calls':0,'network_calls':0,'checkpoint_created':False}))
        return 0
    require(bool(args.env_file),'clinical_env_file_required')
    lock=Path(args.checkpoint).resolve().with_suffix('.lock')
    lock.parent.mkdir(parents=True,exist_ok=True)
    with checkpoint_lock(lock):
        host=SdkWorkflowHost(config,variables,args.env_file,args.checkpoint,resume=args.resume)
        selectors={**variables,'preflight_only':True,'memory_mode':'off','enable_refinement':False,
                   'enable_pharmacological_class':False,'supplementary_search':False,
                   'prepare_result_for_persistence':False}
        scope=host.execute(CLINICAL,VERSION,'clinical_intelligence',selectors)
        prepared=ClinicalSourceWorkflow(host.execute).prepare(scope['result']['subject'],variables)
        host.state['source_preparation']=prepared
        save(host.path,host.state)
        selected={**variables,'preflight_only':not args.analyze,'memory_mode':'preview' if args.analyze else 'off',
                  'enable_refinement':bool(args.analyze),'enable_pharmacological_class':False,
                  'supplementary_search':bool(args.analyze),'prepare_result_for_persistence':False}
        result=host.execute(CLINICAL,VERSION,'clinical_intelligence',selected,references=prepared['input_references'])
        workflow_status=('partial' if prepared['issues'] or result['result']['quality']['status']=='partial' else 'completed')
        host.state.update(status=workflow_status,clinical_run_uuid=result['run_uuid'],
                          clinical_quality=result['result']['quality']['status'])
        save(host.path,host.state)
        print(json.dumps({'status':workflow_status,'run_uuid':result['run_uuid'],
                          'quality':result['result']['quality']['status'],'source_calls':prepared['source_calls'],
                          'memory_writes':0,'publication':False}))
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except ContractError as error:
        print(json.dumps({'status':'blocked','reason_code':error.code,'resume_requires_same_checkpoint':True}))
        raise SystemExit(2)
    except FileExistsError:
        print(json.dumps({'status':'blocked','reason_code':'clinical_checkpoint_locked_inspect_owner'}))
        raise SystemExit(2)
    except Exception:
        print(json.dumps({'status':'blocked','reason_code':'clinical_sdk_operation_unconfirmed_inspect_checkpoint'}))
        raise SystemExit(2)
