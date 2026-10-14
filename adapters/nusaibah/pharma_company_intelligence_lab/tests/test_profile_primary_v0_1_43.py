"""No providers: original draft text reaches the same real SDK Skill lane."""
from pathlib import Path
from copy import deepcopy
import json,re,sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from test_grounded_profile_v0_1_40 import NativeInputs,Inputs
from test_readable_profile_v0_1_42 import NarrativeInputs
from profile_research_v0_1_43 import research_records,build_profile_candidate,current_profile_context
from memory_contract import MemoryCandidate,MEMORY_TARGET_SECTION
from orchestration_v0_1_43 import invoke_v0_1_43
import legacy_preparation_helpers_v0_1_23 as legacy


class DraftInputs(NativeInputs):
    """Mirror a search response with queries, useful text, no native sources."""
    def invoke_agent(self,role,*,input,on_error='raise'):
        fixture_input=input
        if role==legacy.SYNTHESIS_ROLE and not input['allowed_memory_fact_ids']:
            # The pre-0.1.43 fixture indexes a nonempty fact list. Its staging
            # value is overwritten below; the real candidate still has [] and
            # the production envelope is tested against that exact authority.
            fixture_input={**input,'allowed_memory_fact_ids':input['allowed_narrative_claim_ids'][:1]}
        envelope=super().invoke_agent(role,input=fixture_input,on_error=on_error)
        value=envelope['result']['content'][0]['value']
        if role in legacy.RESEARCH_ROLES:
            for claim in value['claims']:
                claim['statement']=claim['section_id']+' research: '+claim['statement']
            envelope['result']['provider_metadata']['turns'][0]['native']['candidate']['groundingMetadata']={
                'webSearchQueries':['fixture research query'],'groundingChunks':[]}
        if role==legacy.SYNTHESIS_ROLE:
            value['memory_candidate']['fact_ids']=input['allowed_memory_fact_ids']
            for section in value['sections']:
                section['content']=''
                for sub in section['subsections']:sub['content']=''
                own=[c for c in input['research_evidence']['claims'] if c['section_id']==section['section_id']]
                if own:
                    text='\n\n'.join(c['statement']+' [['+c['claim_id']+']]' for c in own)
                    if section['subsections']:section['subsections'][0]['content']=text
                    else:section['content']=text
        return envelope


class ProfilePrimaryTests(unittest.TestCase):
    def test_missing_grounding_keeps_research_in_published_profile_without_verified_fact_counts(self):
        inputs=DraftInputs()
        row=invoke_v0_1_43(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.43')['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'],row.get('skill_publication'))
        self.assertEqual(0,row['accepted_claim_count'])
        self.assertGreater(row['unverified_research_count'],0)
        text=inputs.store[(13,'company_memory')]['text']
        self.assertIn('**Unverified research.**',text)
        self.assertIn('Annex: Unverified Research',text)
        readback=inputs.dynamic_skill('company_memory',variables={'company_id':'13'})
        self.assertEqual(readback.section_text('Current Public Research').strip(),row['profile_document']['text'].strip())
        self.assertTrue(row['retention_admission']['exact_candidate_validated'])
        self.assertFalse(row['verification_complete'])
        self.assertEqual(4,row['required_section_coverage_count'])

    def test_unverified_annex_contains_only_numeric_section_paragraph_references(self):
        claim={'claim_id':'draft1','section_id':'markets_commercial_signals','statement':'A proposed commercial observation.',
               'citation_locators':['https://example.org/report'],'evidence_qualifiers':[],'verification_status':'unverified'}
        candidate=MemoryCandidate(59,MEMORY_TARGET_SECTION,'',())
        result,meta=build_profile_candidate(candidate,'',[ ],research=[claim],company_name='Pfizer')
        annex=result.markdown.split('### Annex: Unverified Research\n',1)[1]
        self.assertRegex(annex,r'\| Section \| Paragraph \|\n\|---\|---\|\n\| 3 \| 1 \|')
        self.assertNotIn(claim['statement'],annex)
        self.assertNotIn(claim['citation_locators'][0],annex)
        self.assertEqual(1,result.markdown.count(claim['statement']))
        self.assertEqual((),result.fact_ids)

    def test_semantically_invalid_statement_is_retained_as_unverified_without_inventing_fields(self):
        claim={'claim_id':'draft1','section_id':'company_profile','statement':'Reported sales reached 12 million.',
               'citation_locators':[],'evidence_qualifiers':[],'reported_total':None,'reported_unit':None,
               'issue_code':'claim_semantic_quantitative_pair_required'}
        records,issues=research_records({'claims':[],'withheld_claims':[claim]})
        self.assertFalse(issues);self.assertEqual('unverified',records[0]['verification_status'])
        self.assertIsNone(records[0]['reported_total'])
        result,_=build_profile_candidate(MemoryCandidate(59,MEMORY_TARGET_SECTION,'',()),'',[],research=records,company_name='Pfizer')
        self.assertIn(claim['statement'],result.markdown)

    def test_historical_annex_is_not_reprocessed_as_new_research(self):
        inputs=DraftInputs()
        old=inputs.store[(13,'company_memory')]['text']
        inputs.store[(13,'company_memory')]['text']=old+'\n\n### Annex: Previous Memory\n\nOLD LEDGER NOT NEW RESEARCH\n'
        row=invoke_v0_1_43(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.43')['outputs']['intelligence_dossier']['company_results'][0]
        research=[payload for role,_,payload in inputs.agent_inputs if role in legacy.RESEARCH_ROLES]
        self.assertLessEqual(len(research),4)
        self.assertTrue(research)
        for payload in research:self.assertNotIn('OLD LEDGER NOT NEW RESEARCH',json.dumps(payload))
        self.assertIn('OLD LEDGER NOT NEW RESEARCH',inputs.store[(13,'company_memory')]['text'])
        self.assertTrue(all(m['within_input_budget'] for m in row['agent_input_preflight']['measurements']))

    def test_unsafe_draft_is_not_smuggled_into_unverified_research(self):
        import devtools.preview_output_validator as validator
        if getattr(validator,'IS_TEST_STUB',False):self.skipTest('Security qualification requires the real runtime validator')
        claim={'claim_id':'d1','section_id':'company_profile','statement':'Use https://example.org/report?X-Amz-Signature=private',
               'citation_locators':[],'evidence_qualifiers':[]}
        records,issues=research_records({'claims':[],'withheld_claims':[claim]})
        self.assertEqual([],records);self.assertEqual('unsafe_business_content',issues[0]['reason'])

    def test_whole_prior_paragraphs_and_unverified_labels_survive_context_projection(self):
        text='**Unverified research.** First paragraph.\n\n'+('Second paragraph. '*100)+'\n\n### Annex: Evidence\n\nOld ledger'
        result=current_profile_context(text,maximum=100)
        self.assertEqual('**Unverified research.** First paragraph.',result)
        self.assertNotIn('Old ledger',result)

    def test_identical_research_is_no_change_and_does_not_nest_old_profile(self):
        claim={'claim_id':'d1','section_id':'company_profile','statement':'A proposed company observation.',
               'citation_locators':[],'evidence_qualifiers':[],'verification_status':'unverified'}
        candidate=MemoryCandidate(59,MEMORY_TARGET_SECTION,'',())
        first,_=build_profile_candidate(candidate,'Old exact memory.',[],research=[claim],company_name='Pfizer')
        second,_=build_profile_candidate(candidate,first.markdown,[],research=[claim],company_name='Pfizer')
        self.assertEqual(first.markdown,second.markdown)

    def test_two_passes_consume_the_previous_unverified_profile_and_publish_once(self):
        inputs=DraftInputs();inputs['variables']['portfolio_review_passes']=2
        row=invoke_v0_1_43(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.43')['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertEqual(2,row['portfolio_review_pass_count'])
        second=[p for role,_,p in inputs.agent_inputs if role in legacy.RESEARCH_ROLES and p['review_iteration']['pass_number']==2]
        self.assertTrue(second);self.assertTrue(any('Unverified research.' in p['prior_profile_context'] for p in second))
        self.assertTrue(all('never established facts' in p['prior_profile_instruction'] for p in second))
        self.assertEqual(2,inputs.mutables.count('company_memory')) # preview + one apply
        self.assertNotIn(legacy.BENCHMARK_ROLE,inputs.role_calls)
        self.assertLessEqual(row['agent_input_preflight']['provider_dispatch_count'],48)

    def test_all_chain_prompts_prioritize_profile_and_keep_historical_contracts(self):
        manifest=json.loads((ROOT/'nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        new=manifest['versions']['0.1.43'];old=json.loads((ROOT/'tests/fixtures/release-0.1.42/nusaibah_pharma_company_intelligence_lab.asset.json').read_text(encoding='utf-8'))['versions']['0.1.42']
        for role in (*legacy.RESEARCH_ROLES,legacy.CRITIC_ROLE,legacy.SYNTHESIS_ROLE,legacy.STRATEGIC_ROLE):
            self.assertNotEqual(new['agents'][role]['contract_version'],old['agents'][role]['contract_version'])
            steps=new['agents'][role]['definition']['chain']['steps']
            prompt=json.dumps(steps,ensure_ascii=False)
            self.assertIn('PRIMARY OBJECTIVE',prompt)
            for step in steps:
                for message in step.get('messages',[]):
                    for block in message.get('content',[]):
                        if isinstance(block,dict) and isinstance(block.get('text'),str):self.assertLessEqual(len(block['text']),8192)

    def test_verified_alias_does_not_repeat_an_unverified_statement(self):
        draft={'claim_id':'draft','section_id':'company_profile','statement':'Example is headquartered in Amman.',
               'citation_locators':[],'evidence_qualifiers':[],'verification_status':'unverified'}
        verified={**draft,'claim_id':'verified','source_spans':[{'start':0,'end':1}],
                  'citation_locators':['https://example.org/report']}
        candidate=MemoryCandidate(59,MEMORY_TARGET_SECTION,'',('verified',))
        result,meta=build_profile_candidate(candidate,'',[verified],research=[draft],company_name='Example')
        self.assertEqual(1,result.markdown.count(draft['statement']))
        self.assertEqual(('verified',),result.fact_ids)
        self.assertFalse(meta['unverified_research'])

    def test_114_distinct_draft_statements_are_retained_once_with_existing_memory(self):
        from profile_research_v0_1_43 import BUSINESS_SECTIONS,MAX_PROFILE_CHARS
        research=[{'claim_id':'draft:'+str(i),'section_id':BUSINESS_SECTIONS[i%4],
                   'statement':'Distinct proposed research observation number '+str(i)+'.',
                   'citation_locators':[],'evidence_qualifiers':[],'verification_status':'unverified'} for i in range(114)]
        old='Previous memory is preserved verbatim.\n'*350
        candidate=MemoryCandidate(59,MEMORY_TARGET_SECTION,'',())
        result,meta=build_profile_candidate(candidate,old,[],research=research,company_name='Pfizer')
        self.assertFalse(meta['omitted_facts']);self.assertEqual(4,len(meta['sections']))
        for claim in research:self.assertEqual(1,result.markdown.count(claim['statement']))
        self.assertIn(old,result.markdown);self.assertLessEqual(len(result.markdown),MAX_PROFILE_CHARS)
        self.assertEqual((),result.fact_ids)

if __name__=='__main__':unittest.main()
