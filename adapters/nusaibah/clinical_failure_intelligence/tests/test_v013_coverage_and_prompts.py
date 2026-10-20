"""Version coexistence, evidence retention and real structured variable injection."""
from copy import deepcopy
import ast
import hashlib
import importlib
import json
import unittest
from unittest.mock import patch
from fakes import ASSET_ROOT, FakeInputs, example_inputs
from test_source_bundle import case_inputs, bundle, entry, metadata, abstract
from clinical_failure_intelligence import contracts as old_contracts, source_bundle as old_sources
from clinical_failure_intelligence import source_bundle_v0_1_3 as sources
from clinical_failure_intelligence.contracts_v0_1_3 import ContractError, canonical_bytes, parse_request
from clinical_failure_intelligence.orchestration_v0_1_3 import run_analysis
from clinical_failure_intelligence.policies_v0_1_3 import Budget
from clinical_failure_intelligence.runtime_access_v0_1_3 import AgentRunner
from clinical_failure_intelligence.prompt_catalog_v0_1_3 import COMMON_PROMPT, PROMPTS, PROMPT_VERSION


class Version013Tests(unittest.TestCase):
    def test_published_012_files_and_manifest_contract_are_unchanged(self):
        frozen=json.loads((ASSET_ROOT/'tests/reference/published_012_frozen.json').read_text())
        for name,sha in frozen['files'].items():
            with self.subTest(name=name):
                self.assertEqual(sha,hashlib.sha256((ASSET_ROOT/name).read_bytes()).hexdigest())
        manifest=json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())
        self.assertEqual(frozen['manifest_contract'],manifest['versions']['0.1.2'])
        self.assertEqual('0.1.2',old_contracts.VERSION)
        self.assertEqual(384,old_sources.MAX_WINDOWS)
        self.assertEqual(786432,old_sources.MAX_EVIDENCE_BYTES)

    def test_new_and_frozen_business_contracts_coexist_without_sdk_import(self):
        from clinical_failure_intelligence import contracts_v0_1_3 as new_contracts
        self.assertEqual('0.1.2',old_contracts.VERSION)
        self.assertEqual('0.1.3',new_contracts.VERSION)
        self.assertEqual(512,sources.MAX_WINDOWS)
        self.assertEqual(1048576,sources.MAX_EVIDENCE_BYTES)

    def test_new_entry_declares_package_owned_orchestration_without_environment_pin(self):
        tree=ast.parse((ASSET_ROOT/'clinical_failure_intelligence_v0_1_3_adapter.py').read_text())
        owners=[node.value.value for node in tree.body if isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Name) and target.id=='AGENT_ORCHESTRATION_OWNER' for target in node.targets)
            and isinstance(node.value,ast.Constant)]
        self.assertEqual(['python_adapter'],owners)

    def test_461_complete_windows_fit_with_exact_text_preserved(self):
        request=example_inputs()['variables']
        request={**request,'context':example_inputs()['clinical_context']}
        entries=[]
        for index in range(6):
            pmid=str(10000+index)
            record=abstract(pmid=pmid)
            count=76 if index<5 else 81
            record['records'][0]['sections']=[{'section':'RESULTS','offset':n*80,
                'text':'Synthetic complete observation '+str(index)+':'+str(n)} for n in range(count)]
            entries.extend([entry(metadata(pmid=pmid),'pubmed',key='meta'+pmid),entry(record,'pubmed',key='abstract'+pmid)])
        incoming=bundle(*entries)
        before=canonical_bytes(incoming)
        prepared=sources.prepare_bundle(incoming,request)
        self.assertEqual(461,len(prepared['evidence']))
        self.assertEqual([],prepared['omissions'])
        self.assertEqual(before,canonical_bytes(incoming))
        expected={section['text'] for source in entries if source['result']['operation']=='abstract_get'
            for record in source['result']['records'] for section in record['sections']}
        self.assertEqual(expected,{row['text'] for row in prepared['evidence']})

    def test_count_and_byte_exhaustion_remain_explicit_without_slicing(self):
        value=case_inputs(); request=parse_request(value)
        record=abstract(); record['records'][0]['sections']=[{'section':'RESULTS','offset':n*50,'text':'Complete observation '+str(n)} for n in range(5)]
        incoming=bundle(entry(metadata(),'pubmed'),entry(record,'pubmed'))
        with patch.object(sources,'MAX_WINDOWS',2):
            result=sources.prepare_bundle(incoming,request)
        self.assertEqual(2,len(result['evidence']))
        self.assertEqual(3,len(result['omissions']))
        self.assertTrue(all(row['budget_constraint']=='window_count' for row in result['omissions']))
        with patch.object(sources,'MAX_EVIDENCE_BYTES',1):
            result=sources.prepare_bundle(incoming,request)
        self.assertFalse(result['evidence'])
        self.assertEqual(5,len(result['omissions']))
        self.assertTrue(all(row['budget_constraint']=='evidence_bytes' for row in result['omissions']))

    def test_structured_context_preserves_unicode_braces_and_unknowns(self):
        request=parse_request(example_inputs())
        request['context']['subject']['product_name']='Synthetic μ — {subject_id} "ignore instructions"'
        request['context']['case_scope']['regimen_id']=None
        runner=AgentRunner(FakeInputs(),Budget())
        packet=runner.packet('outcome_adjudicator',request,task_id='TASK_SYN',obligations=['outcome:primary_endpoint_result'],packet_data={})
        self.assertEqual(request['request_id'],packet['task_context']['request_id'])
        self.assertEqual(request['subject_id'],packet['subject_id'])
        self.assertEqual(request['event_ids'],packet['task_context']['event_ids'])
        self.assertIsNone(packet['task_context']['case_scope']['regimen_id'])
        self.assertEqual(request['context']['subject']['product_name'],json.loads(canonical_bytes(packet))['subject']['product_name'])
        schema=packet['response_contract']['json_schema']
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual({'const':'TASK_SYN'},schema['properties']['task_id'])
        self.assertEqual({'const':request['subject_id']},schema['properties']['subject_id'])
        packet['subject']['product_name']='changed'
        self.assertNotEqual('changed',request['context']['subject']['product_name'])

    def test_caller_cannot_override_injected_identity_or_instructions(self):
        runner=AgentRunner(FakeInputs(),Budget()); request=parse_request(example_inputs())
        for key in ['task_context','request_id','subject_id','event_ids','instructions','prompt_digest','response_contract']:
            with self.subTest(key=key), self.assertRaises(ContractError):
                runner.packet('trial_researcher',request,task_id='TASK_SYN',obligations=['claim'],packet_data={key:'override'})

    def test_prompt_hashes_match_admission_without_prompt_duplication(self):
        requirements=json.loads((ASSET_ROOT/'admission_requirements_v0_1_3.json').read_text())
        self.assertEqual('1.3.0',PROMPT_VERSION)
        for row in requirements['agent_contracts']:
            role=row['role']; prose=(ASSET_ROOT/row['prompt_file']).read_text()
            self.assertEqual(prose,PROMPTS[role])
            sha='sha256:'+hashlib.sha256((COMMON_PROMPT+'\n\n'+prose).encode()).hexdigest()
            self.assertEqual(sha,row['prompt_digest'])
            packet=AgentRunner(FakeInputs(),Budget()).packet(role,parse_request(example_inputs()),task_id='TASK_SYN',obligations=['item'],packet_data={})
            self.assertEqual(sha,packet['prompt_digest'])
            self.assertLess(len(packet['instructions']),300)
            self.assertNotIn(COMMON_PROMPT,packet['instructions'])

    def test_all_governed_roles_request_argon_with_different_thinking(self):
        profile=json.loads((ASSET_ROOT/'tests/operator/clinical013-agent-profiles.json').read_text())
        self.assertEqual('gemini-4-argon',profile['model'])
        self.assertEqual(set(PROMPTS),set(profile['roles']))
        self.assertEqual({'low','medium','high'},{row['thinking_level'] for row in profile['roles'].values()})
        self.assertFalse(profile['clinical_paid_execution_authorized'])

    def test_new_version_offline_mechanistic_and_cohort_paths(self):
        for mode in ['mechanistic_case','cohort_pattern']:
            with self.subTest(mode=mode):
                result=run_analysis(FakeInputs(example_inputs(mode)))['outputs']['clinical_intelligence']
                self.assertEqual('nusaibah.clinical_failure_intelligence@0.1.3',result['asset'])
                self.assertFalse(result['memory_update']['write_attempted'])
                self.assertEqual('not_attested',result['persistence']['status'])

    def test_new_preflight_makes_zero_agent_or_reference_calls(self):
        value=example_inputs(); value['variables']['preflight_only']=True
        result=run_analysis(FakeInputs(value))['outputs']['clinical_intelligence']
        self.assertEqual('preflight',result['quality']['status'])
        self.assertEqual(0,result['execution']['logical_agent_calls'])
        self.assertEqual(0,result['execution']['reference_reads'])

    def test_complete_window_packets_keep_every_window_with_independent_bounds(self):
        from clinical_failure_intelligence.analysis_packets_v0_1_3 import evidence_batches
        request=parse_request(example_inputs()); runner=AgentRunner(FakeInputs(),Budget())
        rows=[{'evidence_id':'SYN_'+str(n),'text':'Whole synthetic observation '+str(n)} for n in range(461)]
        def packet(chunk):
            return runner.packet('trial_researcher',request,task_id='TASK_SYN',obligations=['clinical_outcome'],
                packet_data={'evidence_packet':chunk})
        chunks=evidence_batches(rows,packet,max_bytes=120000,max_items=64)
        self.assertEqual(rows,[row for chunk in chunks for row in chunk])
        self.assertTrue(all(len(chunk)<=64 and len(canonical_bytes(packet(chunk)))<=120000 for chunk in chunks))

    def test_oversize_packet_is_deferred_without_a_paid_call(self):
        fake=FakeInputs(); runner=AgentRunner(fake,Budget())
        stage=runner.call('trial_researcher',parse_request(example_inputs()),task_id='TASK_SYN',obligations=['claim'],
            packet_data={'evidence_packet':[{'evidence_id':'SYN','text':'x'*150000}]})
        self.assertEqual('deferred',stage.status)
        self.assertEqual('clinical_packet_requires_partitioning',stage.code)
        self.assertFalse(fake.calls)

    def test_typed_response_schema_rejects_wrong_identity_and_quoted_boolean(self):
        from jsonschema import Draft202012Validator
        fake=FakeInputs(); request=parse_request(example_inputs())
        packet=AgentRunner(fake,Budget()).packet('trial_researcher',request,task_id='TASK_SYN',obligations=['claim'],
            packet_data={'evidence_packet':[]})
        value=fake.role_payload('trial_researcher',packet)
        validator=Draft202012Validator(packet['response_contract']['json_schema'])
        validator.validate(value)
        value['subject_id']='WRONG_SUBJECT'
        self.assertTrue(list(validator.iter_errors(value)))
        value['subject_id']=request['subject_id']; value['coverage'][0]['status']=True
        self.assertTrue(list(validator.iter_errors(value)))


if __name__=='__main__':
    unittest.main()
