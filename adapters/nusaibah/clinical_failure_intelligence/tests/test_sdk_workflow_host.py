"""SDK host protocol tests with mocked transport, never live submission evidence."""
from contextlib import ExitStack
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
import sys
from types import ModuleType
from unittest.mock import patch
from fakes import ASSET_ROOT
from clinical_failure_intelligence.contracts import ContractError
from clinical_failure_intelligence.source_workflow import SourceReadUnavailable

spec=importlib.util.spec_from_file_location('clinical_operator',ASSET_ROOT/'tests/operator/run_clinical_workflow.py')
operator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)
ASSET='nusaibah.clinical_trials_lookup'
ENV={'OBS_BASE_URL':'http://127.0.0.1:1','OBS_API_KEY_HEADER':'X-Test','OBS_API_KEY':'synthetic',
     'OBS_CLIENT_ID':'test_client'}
RUN=str(uuid.UUID(int=1))


class HostTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'checkpoint.json'
        self.config={'substrate':'local_worker','assets':{ASSET:{'entity_key':'test_entity'}}}
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        try:
            import devtools.obs_api_client
            # SDK 0.1.135 uses lazy exports. Earlier temporary-module fixtures
            # may have restored sys.modules without parent attributes.
            import devtools,importlib
            for name in ('connection_check','asset_preflight','obs_api_client','preview_result_inspect'):
                setattr(devtools,name,importlib.import_module('devtools.'+name))
        except ImportError:
            # Source-only CI deliberately installs no runtime SDK. These are
            # explicit transport doubles, not package or real-SDK qualification.
            modules={name:ModuleType(name) for name in ('devtools','devtools.connection_check',
                'devtools.asset_preflight','devtools.obs_api_client','devtools.preview_result_inspect')}
            modules['devtools'].__path__=[]
            for name,module in modules.items():
                if '.' in name:setattr(modules['devtools'],name.split('.')[1],module)
            def unexpected(*args,**kwargs):raise AssertionError('unpatched SDK transport double')
            for name,attributes in {
                'devtools.connection_check':['load_env_file'],
                'devtools.asset_preflight':['_request_asset_preflight'],
                'devtools.obs_api_client':['execute_asset','poll_run'],
                'devtools.preview_result_inspect':['download_preview_result']}.items():
                for attribute in attributes:setattr(modules[name],attribute,unexpected)
            modules['devtools.obs_api_client'].build_asset_execute_payload=lambda **kwargs:kwargs
            self.stack.enter_context(patch.dict(sys.modules,modules))
        self.stack.enter_context(patch('devtools.connection_check.load_env_file',return_value=ENV))
        self.preflight=self.stack.enter_context(patch('devtools.asset_preflight._request_asset_preflight',
            return_value={'http_status':200,'decoded':{'data':{'status':'ready'}}}))
        self.launch=self.stack.enter_context(patch('devtools.obs_api_client.execute_asset',return_value={'data':{'run_uuid':RUN}}))
        self.poll=self.stack.enter_context(patch('devtools.obs_api_client.poll_run',return_value={'terminal':True,'final_status':'completed'}))
        self.download=self.stack.enter_context(patch('devtools.preview_result_inspect.download_preview_result',side_effect=self.artifact))
        self.failure_detail=self.stack.enter_context(patch.object(operator,'source_failure_detail',side_effect=lambda api,run_uuid:{'run_uuid':run_uuid,'failure_code':'synthetic_failure'}))
    def artifact(self,config,run,destination,app):
        content=json.dumps({'schema_version':'test','run_uuid':run,'asset_identity':ASSET+':0.1.1',
                           'outputs':{'trial_result':{'operation':'study_get','records':[]}}}).encode()
        Path(destination).write_bytes(content)
        return {'checksum_sha256':hashlib.sha256(content).hexdigest()}
    def host(self,**kwargs):return operator.SdkWorkflowHost(self.config,{},'protected.env',self.path,**kwargs)
    def execute(self,host):return host.execute(ASSET,'0.1.1','trial_result',{'operation':'study_get','nct_id':'NCT00000001'})
    def source(self):
        return {'trials_detail_runtime':{'runtime_source_id':'rt_src_'+'a'*32,
            'operation':'study_get','capability_ref':'clinical_trials.study.get','resolve':'lazy','input':{}}}
    def test_governed_source_selectors_and_lazy_worker_mode_reach_sdk(self):
        sources=self.source();self.config['assets'][ASSET]['runtime_source_inputs']=sources
        self.execute(self.host())
        payload=self.launch.call_args.kwargs['payload']
        self.assertEqual('worker',payload['runtime_source_resolution'])
        self.assertEqual(sources['trials_detail_runtime'],payload['inputs']['trials_detail_runtime'])
        self.assertEqual({'operation':'study_get','nct_id':'NCT00000001'},payload['inputs']['variables'])
        self.assertEqual(payload,self.preflight.call_args.kwargs['payload'])
    def test_unconfigured_sources_keep_existing_eager_request_behavior(self):
        self.execute(self.host())
        self.assertNotIn('runtime_source_resolution',self.launch.call_args.kwargs['payload'])
    def test_forged_source_configuration_fails_before_transport(self):
        for mutation in ({'records':[]},{'runtime_source_id':'forged'},
                         {'resolve':'invalid'},{'input':{'records':[]}},
                         {'capability_ref':'https://forged.example'}):
            with self.subTest(mutation=mutation):
                sources=self.source();sources['trials_detail_runtime'].update(mutation)
                self.config['assets'][ASSET]['runtime_source_inputs']=sources
                with self.assertRaisesRegex(ContractError,'source_configuration_invalid'):
                    self.execute(self.host(resume=self.path.exists()))
                self.launch.assert_not_called();self.preflight.assert_not_called()
                # A new configuration needs a new checkpoint even before submission.
                self.path.unlink()
    def test_source_roles_cannot_replace_variables_or_retained_evidence(self):
        for role in ('variables','trial_study_result'):
            with self.subTest(role=role):
                sources={role:next(iter(self.source().values()))}
                self.config['assets'][ASSET]['runtime_source_inputs']=sources
                with self.assertRaisesRegex(ContractError,'source_role_collision'):
                    self.host().execute(ASSET,'0.1.1','trial_result',{},references={'trial_study_result':{'run_uuid':RUN}})
                self.launch.assert_not_called();self.preflight.assert_not_called();self.path.unlink()
    def test_completed_run_resume_uses_saved_result_without_resubmitting(self):
        self.execute(self.host())
        result=self.execute(self.host(resume=True))
        self.assertEqual(RUN,result['run_uuid'])
        self.assertEqual(1,self.launch.call_count)
        self.assertEqual(1,self.poll.call_count)
        self.assertEqual(1,self.download.call_count)
    def test_unknown_submission_ack_is_saved_and_never_replayed(self):
        self.launch.side_effect=TimeoutError('test')
        with self.assertRaises(TimeoutError):self.execute(self.host())
        self.launch.side_effect=None
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):self.execute(self.host(resume=True))
        self.assertEqual(1,self.launch.call_count)
    def test_poll_timeout_resumes_same_uuid(self):
        self.poll.return_value={'terminal':False,'final_status':'processing'}
        with self.assertRaisesRegex(ContractError,'not_terminal'):self.execute(self.host())
        self.poll.return_value={'terminal':True,'final_status':'completed'}
        self.execute(self.host(resume=True))
        self.assertEqual(1,self.launch.call_count)
        self.assertTrue(all(call.kwargs['run_uuid']==RUN for call in self.poll.call_args_list))
    def test_known_failed_source_is_not_resubmitted_or_repolled(self):
        self.poll.return_value={'terminal':True,'final_status':'failed'}
        with self.assertRaises(SourceReadUnavailable):self.execute(self.host())
        with self.assertRaises(SourceReadUnavailable):self.execute(self.host(resume=True))
        self.assertEqual(1,self.launch.call_count);self.assertEqual(1,self.poll.call_count)
    def test_local_retained_tampering_detected_on_resume(self):
        host=self.host();self.execute(host)
        next(host.artifacts.glob('*.json')).write_text('{}')
        with self.assertRaisesRegex(ContractError,'integrity_failed'):self.execute(self.host(resume=True))
        self.assertEqual(1,self.launch.call_count)
    def test_producer_identity_checked_after_download(self):
        self.config['assets']['other']={'entity_key':'test_entity'}
        with self.assertRaisesRegex(ContractError,'identity_failed'):
            self.host().execute('other','0.1.1','trial_result',{'operation':'study_get'})
    def test_no_resubmission_on_blocked_preflight(self):
        self.preflight.return_value={'http_status':200,'decoded':{'data':{'status':'blocked'}}}
        with self.assertRaisesRegex(ContractError,'admission_not_ready'):self.execute(self.host())
        self.launch.assert_not_called()
        self.assertEqual({},json.loads(self.path.read_text())['operations'])
    def test_resume_cannot_change_server_or_code(self):
        self.host()
        with patch('devtools.connection_check.load_env_file',return_value={**ENV,'OBS_BASE_URL':'http://other'}):
            with self.assertRaisesRegex(ContractError,'identity_mismatch'):self.host(resume=True)
        with patch.object(operator,'implementation_digest',return_value='different_code'):
            with self.assertRaisesRegex(ContractError,'identity_mismatch'):self.host(resume=True)
    def test_checkpoint_lock_never_removes_another_owner(self):
        lock=self.root/'owner.lock';lock.write_text('other')
        with self.assertRaises(FileExistsError):
            with operator.checkpoint_lock(lock):pass
        self.assertEqual('other',lock.read_text())
        lock.unlink()
        with self.assertRaises(RuntimeError):
            with operator.checkpoint_lock(lock):raise RuntimeError('test')
        self.assertFalse(lock.exists())
    def test_default_plan_loads_no_credentials_and_creates_no_checkpoint(self):
        config=self.root/'config.json';config.write_text(json.dumps(self.config))
        variables=self.root/'variables.json';variables.write_text('{}')
        with (patch('devtools.connection_check.load_env_file',side_effect=AssertionError('no credential read')),
              patch('sys.stdout',new_callable=io.StringIO) as output):
            self.assertEqual(0,operator.main(['--config',str(config),'--variables-file',str(variables),'--checkpoint',str(self.path)]))
        self.assertEqual('plan_only',json.loads(output.getvalue())['status'])
        self.assertFalse(self.path.exists());self.launch.assert_not_called()
