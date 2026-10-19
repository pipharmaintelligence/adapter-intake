"""Top-level source coordination and retained-contract tests; no live authority."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import uuid
from fakes import FakeInputs
from test_source_bundle import case_inputs, trial_result, metadata, abstract, terminology, NCT
from clinical_failure_intelligence.contracts import ContractError, parse_request
from clinical_failure_intelligence.retained_sources import SOURCE_ROLES
from clinical_failure_intelligence.source_workflow import ClinicalSourceWorkflow, SourcePolicy, SourceReadUnavailable
from clinical_failure_intelligence.orchestration import run_analysis


class SourceExecutor:
    def __init__(self,pmids=('12345',)):
        self.calls=[]
        self.completed={}
        self.pmids=pmids
    def __call__(self,asset,version,output,variables):
        self.calls.append((asset,version,output,deepcopy(variables)))
        operation=variables['operation']
        if asset.endswith('clinical_trials_lookup'):
            value=trial_result(operation=operation)
        elif asset=='umls_terminology':
            self.assert_umls(variables)
            value=terminology()
        elif operation=='trial_publications':
            value={'schema_version':'pubmed_evidence.v1','status':'completed' if self.pmids else 'no_match',
                   'operation':operation,'records':[{'pmid':pmid} for pmid in self.pmids],
                   'record_count':len(self.pmids),'coverage':{'has_more':False}}
        elif operation=='abstract_get':
            value=abstract(pmid=variables['pmid'])
        else:
            ids=variables.get('pmids') or [variables['pmid']]
            value=metadata(pmid=ids[0])
            value['operation']=operation
            value['records']=[metadata(pmid=pmid)['records'][0] for pmid in ids]
            value['record_count']=len(ids)
        run=str(uuid.UUID(int=len(self.calls)))
        self.completed[run]=(asset,version,output,deepcopy(value))
        return {'run_uuid':run,'result':value}
    def assert_umls(self,variables):
        assert set(variables)=={'operation','text','search_type','limit'}
        assert variables['search_type']=='exact' and variables['limit']==3


def selection():
    raw=case_inputs()
    variables={**raw['variables'],'product_id':'PRODUCT_SYN','trial_id':NCT}
    return raw,variables,raw['clinical_context']['subject']


def hydrated_inputs(raw,prepared,executor):
    value=deepcopy(raw)
    for role,ref in prepared['input_references'].items():
        asset,version,output,result=executor.completed[ref['run_uuid']]
        value[role]={'value':result,'provenance':{'source':'retained_asset_output','authority':'core_artifact',
            'run_uuid':ref['run_uuid'],'asset_identity':asset+':'+version,'output_role':output,'checksum_sha256':'1'*64}}
    return value


class SourceWorkflowTests(unittest.TestCase):
    def test_three_sources_execute_in_order_with_ids_from_actual_discovery(self):
        raw,variables,subject=selection()
        executor=SourceExecutor()
        prepared=ClinicalSourceWorkflow(executor).prepare(subject,variables)
        self.assertEqual(7,len(executor.calls))
        self.assertEqual({'nusaibah.clinical_trials_lookup','nusaibah.pubmed_evidence','umls_terminology'},
                         {row[0] for row in executor.calls})
        self.assertEqual(['12345'],executor.calls[3][3]['pmids'])
        self.assertTrue(all(set(ref)=={'run_uuid'} for ref in prepared['input_references'].values()))
        self.assertFalse(prepared['clinical_execution_submitted'])
    def test_real_consumer_normalizes_retained_three_source_contracts(self):
        raw,variables,subject=selection()
        executor=SourceExecutor()
        prepared=ClinicalSourceWorkflow(executor).prepare(subject,variables)
        data=hydrated_inputs(raw,prepared,executor)
        data['variables'].update(preflight_only=True,memory_mode='off',supplementary_search=False)
        result=run_analysis(FakeInputs(data))['outputs']['clinical_intelligence']
        self.assertEqual('preflight',result['quality']['status'])
        self.assertEqual([],result['prepared_sources']['omissions'])
        self.assertTrue(any(row.get('source_context',{}).get('evidence_use')=='publication_text' for row in result['evidence']))
        self.assertFalse(result['prepared_sources']['terminology'][0]['may_support_outcome'])
        self.assertEqual(0,result['execution']['logical_agent_calls'])
    def test_no_match_keeps_registry_and_terminology_results(self):
        raw,variables,subject=selection()
        executor=SourceExecutor(pmids=())
        prepared=ClinicalSourceWorkflow(executor).prepare(subject,variables)
        self.assertEqual(4,len(executor.calls))
        self.assertIn('clinical_no_publication_candidates',{row['code'] for row in prepared['issues']})
        normalized=parse_request(FakeInputs(hydrated_inputs(raw,prepared,executor)))
        self.assertTrue(normalized['prepared_sources']['evidence'])
    def test_three_publications_are_bounded_to_eleven_source_calls(self):
        raw,variables,subject=selection()
        executor=SourceExecutor(pmids=('12345','12346','12347'))
        result=ClinicalSourceWorkflow(executor).prepare(subject,variables)
        self.assertEqual(11,result['source_calls'])
        self.assertEqual(3,sum(row[3]['operation']=='abstract_get' for row in executor.calls))
    def test_call_budget_preserves_completed_references(self):
        raw,variables,subject=selection()
        executor=SourceExecutor()
        result=ClinicalSourceWorkflow(executor,policy=SourcePolicy(max_source_calls=2)).prepare(subject,variables)
        self.assertEqual(2,len(executor.calls))
        self.assertEqual({'trial_study_result','trial_results_result'},set(result['input_references']))
        self.assertIn('clinical_source_call_budget_exhausted',{row['code'] for row in result['issues']})
    def test_completed_requests_are_not_reissued_in_same_workflow(self):
        raw,variables,subject=selection()
        executor=SourceExecutor()
        flow=ClinicalSourceWorkflow(executor)
        flow.prepare(subject,variables)
        flow.prepare(subject,variables)
        self.assertEqual(7,len(executor.calls))
    def test_wrong_trial_or_product_rejected_before_invocation(self):
        for override in ({'trial_id':'NCT00000002'},{'product_id':'OTHER'}):
            raw,variables,subject=selection()
            executor=SourceExecutor()
            with self.assertRaises(ContractError):
                ClinicalSourceWorkflow(executor).prepare(subject,{**variables,**override})
            self.assertEqual([],executor.calls)
    def test_unknown_executor_failure_is_not_treated_as_no_results(self):
        raw,variables,subject=selection()
        def failure(*args): raise RuntimeError('unknown execution outcome')
        with self.assertRaises(RuntimeError): ClinicalSourceWorkflow(failure).prepare(subject,variables)
    def test_confirmed_source_unavailability_preserves_other_sources(self):
        raw,variables,subject=selection()
        executor=SourceExecutor()
        def selective(asset,*args):
            if asset=='umls_terminology': raise SourceReadUnavailable('source_no_access')
            return executor(asset,*args)
        result=ClinicalSourceWorkflow(selective).prepare(subject,variables)
        self.assertTrue(result['input_references'])
        self.assertNotIn('terminology_source_result',result['input_references'])
        self.assertEqual('source_no_access',result['issues'][-1]['code'])
    def test_manifest_retained_policies_are_exact_producer_and_role(self):
        root=Path(__file__).resolve().parents[1]
        manifest=json.loads((root/'clinical_failure_intelligence.asset.json').read_text())
        roles=manifest['versions']['0.1.2']['inputs']
        for role,(asset,version,output,operations,purpose) in SOURCE_ROLES.items():
            self.assertEqual('direct',roles[role]['source'])
            self.assertEqual({'asset_identity':asset+':'+version,'output_role':output},roles[role]['retained_output'])
    def test_wrong_producer_and_raw_unhydrated_values_fail_closed(self):
        raw,variables,subject=selection()
        executor=SourceExecutor()
        prepared=ClinicalSourceWorkflow(executor).prepare(subject,variables)
        good=hydrated_inputs(raw,prepared,executor)
        bad=deepcopy(good)
        bad['trial_study_result']={'run_uuid':str(uuid.UUID(int=1))}
        with self.assertRaises(ContractError): parse_request(FakeInputs(bad))
        bad=deepcopy(good)
        bad['trial_study_result']['provenance']['asset_identity']='unrelated.source:0.1.0'
        with self.assertRaisesRegex(ContractError,'identity_mismatch'): parse_request(FakeInputs(bad))
