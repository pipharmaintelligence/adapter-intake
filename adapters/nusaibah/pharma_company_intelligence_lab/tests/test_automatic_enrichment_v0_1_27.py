import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_final_cycle_v0_1_26 import FullCycleInputs,semantic,Handle
from types import SimpleNamespace
from test_orchestration_preview import _fake_citations
from orchestration_v0_1_27 import invoke_v0_1_27
from targeted_inputs_v0_1_27 import pack_source_chunks,MAX_SOURCE_CHUNK_CHARS,MAX_PACKED_SOURCE_CHUNKS,MAX_AGENT_INPUT_CHARS,TargetedSourceInputs,compact_evidence
from section_enrichment_v0_1_27 import build_enrichment_candidate
from company_preparation_v0_1_27 import _benchmark_change
from memory_contract import MemoryCandidate
import legacy_preparation_helpers_v0_1_23 as legacy

class PreviewHandle(Handle):
    def preview(self,changes):
        preview=super().preview(changes)
        preview.document=SimpleNamespace(section_text=lambda path:changes.text)
        return preview

class EnrichmentInputs(FullCycleInputs):
    def __init__(self):
        super().__init__();self['variables'].update(memory_mode='apply',portfolio_review_passes=1)
    def dynamic_skill(self,role,*,variables):
        mutable=role.endswith('_update');role=role.removesuffix('_update')
        if mutable:self.mutables.append(role)
        return PreviewHandle(self.store,(int(variables['company_id']),role),mutable)

def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_27(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.27')

class AutomaticEnrichmentTests(unittest.TestCase):
    def test_every_agent_chain_matches_its_admitted_identity_and_version(self):
        version=json.loads((ROOT/'tests/fixtures/release-0.1.27/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())['versions']['0.1.27']
        for role,contract in version['agents'].items():
            with self.subTest(role=role):
                self.assertEqual(contract['contract_version'],contract['definition']['chain']['version'])
                self.assertEqual(contract['contract_key'],contract['definition']['chain']['chain_id'])
    def test_business_input_limit_is_checked_before_agent_dispatch(self):
        inputs=EnrichmentInputs()
        source=TargetedSourceInputs(inputs,record={'company_id':14,'company_name':'Fixture','corporate_id':1})
        with self.assertRaises(legacy.AgentContractValidationError) as raised:
            source.invoke_agent(legacy.STRATEGIC_ROLE,input={'company_id':14,'memory':'x'*(MAX_AGENT_INPUT_CHARS+1)})
        self.assertEqual('section_input_budget_exceeded',raised.exception.proof_failure_detail['rule'])
        self.assertEqual([],inputs.role_calls)
    def test_resource_only_concurrent_change_stops_before_any_mutation(self):
        from automatic_publication_v0_1_27 import publish_company
        def concurrent(inputs,state):
            inputs.store[(state['company_id'],'company_memory')]['resource']='New archive resource'
            return publish_company(inputs,state)
        inputs=EnrichmentInputs()
        with patch('orchestration_v0_1_27.publish_company',side_effect=lambda i,s:concurrent(i,s)):
            rows=invoke(inputs)['outputs']['intelligence_dossier']['company_results']
        self.assertEqual([],inputs.mutables)
        self.assertTrue(all(r['skill_publication']['memory']['reason']=='baseline_changed' for r in rows))
    def test_each_critic_has_only_one_section_and_its_role_requirements(self):
        inputs=EnrichmentInputs();invoke(inputs)
        critics=[p for role,_,p in inputs.agent_inputs if role==legacy.CRITIC_ROLE]
        self.assertEqual(8,len(critics))
        for p in critics:
            section=p['reviewed_section_ids'][0]
            owner=next(r for r in legacy.RESEARCH_ROLES if section in legacy.RESEARCH_ROLE_SECTIONS[r])
            self.assertTrue(all(c['section_id']==section for c in p['research_evidence']['claims']))
            self.assertTrue(all(s['section_id']==section for s in p['research_evidence']['sections']))
            self.assertTrue(all(r['role'] in (owner,None) and r['reviewed_section_id']==section
                                for r in p['planner_requirements']))
    def test_rejected_section_does_not_erase_valid_sibling_enrichment(self):
        class Partial(EnrichmentInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                if role==legacy.CRITIC_ROLE and input['reviewed_section_ids']==['company_profile']:
                    value=envelope['result']['content'][0]['value']
                    value['recommendation']='fail'
                    value['unsupported_claim_ids']=[c['claim_id'] for c in input['research_evidence']['claims']]
                return envelope
        inputs=Partial();rows=invoke(inputs)['outputs']['intelligence_dossier']['company_results']
        for row in rows:
            self.assertTrue(row['research_incomplete'])
            self.assertTrue(row['skill_publication']['publication_complete'])
            self.assertNotIn('company_profile',row['section_enrichment']['sections'])
            self.assertEqual('needs_enrichment',row['section_enrichment_checks'][0]['status'])
            self.assertTrue(row['withheld_claim_count']>0)
    def test_real_sdk_citation_rendering_is_the_readback_target(self):
        try:
            from devtools.skill_changes import SkillChangeSet
            from devtools.skill_document import SkillDocument
            from devtools.skill_navigation import find_sections
            from devtools.skill_citation import CitationRef
        except ImportError:self.skipTest('SDK rendering is tested in the real-runtime suite')
        from skill_publication_v0_1_27 import apply_section
        class SDKHandle(Handle):
            def new_changeset(self):return SkillChangeSet()
            def preview(self,changes):return changes.preview(self.read())
            def section_text(self,name):return SkillDocument.parse(self.read()).section_text(name)
            def find_sections(self,name):return find_sections(SkillDocument.parse(self.read()),name)
            def apply(self,changes,*,expected_digest):
                self.assert_baseline(expected_digest)
                preview=self.preview(changes);self.store[self.key]['text']=preview.source
                receipt=SimpleNamespace(change_id='sdk-fixture',before_content_digest=preview.diff.old_digest,
                    after_content_digest=preview.diff.new_digest)
                self.store[self.key]['receipt']=receipt;return receipt
            def assert_baseline(self,digest):assert self.mutable and self.content_digest()==digest
        class Inputs:
            def dynamic_skill(self,role,*,variables):return SDKHandle(store,key,role.endswith('_update'))
        key=(14,'company_memory');store={key:{'text':'---\nname: company-memory\ndescription: Fixture.\n---\n\n# Company\n\n## Current Public Research\n\nExisting.\n\n## Other\n\nPreserved.\n'}}
        baseline=SDKHandle(store,key)
        result=apply_section(Inputs(),14,'company_memory','company_memory_update','Current Public Research',
            'Existing.\n\n### Enrichment\n\nSupported fact.',baseline.content_digest(),baseline.provenance().package_digest,
            [CitationRef(locator='https://example.test/evidence',title='Source')])
        self.assertEqual('applied',result['status']);self.assertTrue(result['readback_verified'])
        self.assertTrue(result['history_verified']);self.assertIn('example.test/evidence',store[key]['text'])
        self.assertIn('## Other\n\nPreserved.',store[key]['text'])
    def test_source_qualifications_keep_event_and_publication_dates_distinct(self):
        claim={'claim_id':'f1','section_id':'company_profile','statement':'Agreement announced.',
            'as_of_date':'2026-10-01','semantic_context':semantic(event_state='announced',event_date='2026-09-29',
                publication_date='2026-10-01'),
            'source_spans':[{'locator':'source:1','source_snapshot_id':'snapshot:1'}]}
        value,_=build_enrichment_candidate(MemoryCandidate(14,legacy.MEMORY_TARGET_SECTION,'Unused.',('f1',)),
            'Baseline.',[claim])
        self.assertIn('event_date: 2026-09-29',value.markdown)
        self.assertIn('publication_date: 2026-10-01',value.markdown)
    def test_one_pass_applies_without_caller_review_and_preserves_each_baseline(self):
        inputs=EnrichmentInputs();result=invoke(inputs)
        dossier=result['outputs']['intelligence_dossier']
        self.assertTrue(dossier['publication_complete']);self.assertIs(False,dossier['human_approval_required'])
        self.assertNotIn('review_packet',dossier)
        for row in dossier['company_results']:
            self.assertEqual(['validated'],[p['status'] for p in row['portfolio_review_trace']])
            self.assertTrue(inputs.store[(row['company_id'],'company_memory')]['text'].startswith('Before company_memory'))
            for role in ('memory','methodology'):
                self.assertEqual('applied',row['skill_publication'][role]['status'])
                self.assertTrue(row['skill_publication'][role]['readback_verified'])
                self.assertTrue(row['skill_publication'][role]['history_verified'])
            self.assertNotIn('independent_review_status',row)
            self.assertEqual(row['skill_publication']['memory']['change_id'],row['memory_change_id'])
            self.assertTrue(row['memory_readback_verified'])
        self.assertEqual(2,inputs.role_calls.count('portfolio_researcher'))
    def test_optional_extra_pass_is_rejected_before_dispatch(self):
        inputs=EnrichmentInputs();inputs['variables']['portfolio_review_passes']=2
        with self.assertRaisesRegex(ValueError,'one targeted'):
            invoke(inputs)
        self.assertEqual([],inputs.role_calls)
    def test_partial_methodology_commit_failure_is_retained_and_other_company_continues(self):
        inputs=EnrichmentInputs();cid=inputs['variables']['company_ids'][0]
        inputs.store[(cid,'company_methodology')]['deny']=True
        rows=invoke(inputs)['outputs']['intelligence_dossier']['company_results']
        self.assertEqual('applied',rows[0]['skill_publication']['memory']['status'])
        self.assertFalse(rows[0]['skill_publication']['publication_complete'])
        self.assertTrue(rows[1]['skill_publication']['publication_complete'])
    def test_subsection_ids_and_literal_offsets_survive_bounded_packing(self):
        text='identity\n'+('product portfolio exact original line\n'*190)
        units=[{'locator':'source:1','entity_id':'company:1','text':text,'accessible':True}]
        sections=legacy._section_requests(legacy.RESEARCH_ROLE_SECTIONS['portfolio_researcher'])
        chunks=pack_source_chunks(units,sections,{'focus':'products'},'snapshot:1')
        self.assertLessEqual(len(chunks),MAX_PACKED_SOURCE_CHUNKS)
        for c in chunks:
            self.assertLessEqual(len(c['text']),MAX_SOURCE_CHUNK_CHARS)
            self.assertEqual(text[c['source_start']:c['source_end']],c['text'])
            self.assertEqual([s['section_id'] for s in sections],c['section_ids'])
        self.assertTrue(all(s['subsection_ids'] for s in sections))
        self.assertEqual(chunks,pack_source_chunks(units,sections,{'focus':'products'},'snapshot:1'))
    def test_per_question_regression_cannot_hide_behind_a_matching_total(self):
        before={'results':[{'question_id':'a','coverage':'covered'},{'question_id':'b','coverage':'not_covered'}]}
        after={'results':[{'question_id':'a','coverage':'not_covered'},{'question_id':'b','coverage':'covered'}]}
        self.assertIs(False,_benchmark_change(before,after)[0])
    def test_downstream_packing_keeps_every_claim_and_exact_quote_once(self):
        span={'locator':'source:1','quote':'Exact original quote','start':4,'end':24,'source_snapshot_id':'snapshot:1'}
        claims=[{'claim_id':'f'+str(i),'section_id':'company_profile','statement':'Claim '+str(i),
                 'semantic_context':semantic(),'source_spans':[span],'evidence_quotes':[{'locator':'source:1','quote':span['quote']}]} for i in range(16)]
        evidence={'claims':claims,'sections':[{'section_id':'company_profile','content':'Unbound prose','subsections':[{'subsection_id':'identity','content':'Unbound prose'}]}]}
        packed=compact_evidence(evidence)
        self.assertEqual(16,len(packed['claims']));self.assertEqual(1,len(packed['exact_span_catalog']))
        for old,new in zip(claims,packed['claims']):
            self.assertEqual(old['statement'],new['statement']);self.assertEqual(old['semantic_context'],new['semantic_context'])
            self.assertEqual(span,packed['exact_span_catalog'][new['exact_span_refs'][0]])
        self.assertEqual('identity',packed['sections'][0]['subsections'][0]['subsection_id'])
        self.assertNotIn('content',packed['sections'][0])
    def test_existing_facts_do_not_create_a_fake_memory_delta(self):
        claim={'claim_id':'f1','section_id':'company_profile','statement':'Known supported identity.',
               'source_spans':[{'locator':'source:1','source_snapshot_id':'snapshot:1'}]}
        candidate=MemoryCandidate(1,legacy.MEMORY_TARGET_SECTION,'Model prose.',('f1',))
        value,summary=build_enrichment_candidate(candidate,'Known supported identity.',[claim])
        self.assertEqual('Known supported identity.',value.markdown)
        self.assertEqual((),value.fact_ids);self.assertEqual([],summary['sections'])
    def test_quoted_markdown_cannot_create_another_memory_section(self):
        claim={'claim_id':'f1','section_id':'company_profile','statement':'A statement\n## Other Section\n<script>',
               'source_spans':[{'locator':'source:1','source_snapshot_id':'snapshot:1'}]}
        candidate=MemoryCandidate(1,legacy.MEMORY_TARGET_SECTION,'Model prose.',('f1',))
        value,_=build_enrichment_candidate(candidate,'Previous baseline',[claim])
        self.assertNotIn('\n## Other Section',value.markdown)
        self.assertNotIn('<script>',value.markdown)
    def test_new_research_contract_has_one_json_turn_and_old_contract_is_preserved_in_fixture(self):
        manifest=json.loads((ROOT/'tests/fixtures/release-0.1.27/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        for role in ('portfolio_researcher','market_researcher','regulatory_risk_researcher'):
            chain=manifest['versions']['0.1.27']['agents'][role]['definition']['chain']
            self.assertEqual(1,len(chain['steps']))
            self.assertEqual('json_object',chain['steps'][0]['provider_policy']['generation_policy']['response_format'])
            self.assertIs(False,chain['steps'][0]['provider_policy']['search_enabled'])
        historical=json.loads((ROOT/'tests/fixtures/release-0.1.26/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        self.assertEqual(2,len(historical['versions']['0.1.26']['agents']['portfolio_researcher']['definition']['chain']['steps']))

if __name__=='__main__':unittest.main()
