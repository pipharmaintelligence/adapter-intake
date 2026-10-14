"""Provider-free full candidate-to-Skill readback, paragraph quality and parity."""
import json, sys, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from test_grounded_profile_v0_1_40 import Inputs, NativeInputs
from test_orchestration_preview import _fake_citations
import legacy_preparation_helpers_v0_1_23 as legacy
from orchestration_v0_1_42 import invoke_v0_1_42
from profile_rendering_v0_1_42 import build_profile_candidate, PROFILE_MARKER
from profile_narrative_v0_1_42 import extract_paragraphs
from memory_contract import MemoryCandidate, MEMORY_TARGET_SECTION


class NarrativeInputs(Inputs):
    reject_narrative=False
    def invoke_agent(self,role,*,input,on_error='raise'):
        envelope=super().invoke_agent(role,input=input,on_error=on_error)
        value=envelope['result']['content'][0]['value']
        if role==legacy.SYNTHESIS_ROLE:
            claims=input['research_evidence']['claims']
            for section in value['sections']:
                section['content']=''
                for sub in section['subsections']:sub['content']=''
                own=[c for c in claims if c['section_id']==section['section_id']]
                if own:
                    text=' '.join(c['statement']+' [['+c['claim_id']+']]' for c in own)
                    if section['subsections']:section['subsections'][0]['content']=text
                    else:section['content']=text
        if role==legacy.CRITIC_ROLE and input.get('review_phase')=='narrative_entailment':
            value['future_guidance']=[]
            if self.reject_narrative:
                for r in value['claim_reviews']:r['decision']='needs_review'
        return envelope


def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_42(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.42')


class ReadableProfileTests(unittest.TestCase):
    def test_every_synthesized_paragraph_receives_its_own_review(self):
        class ParagraphInputs(NarrativeInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                if role==legacy.SYNTHESIS_ROLE:
                    value=envelope['result']['content'][0]['value']
                    for section in value['sections']:
                        for piece in [section,*section['subsections']]:
                            piece['content']=piece['content'].replace(']] ',']]\n\n')
                return envelope
        inputs=ParagraphInputs(); row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        reviewed=[payload for role,_,payload in inputs.agent_inputs
                  if role==legacy.CRITIC_ROLE and payload.get('review_phase')=='narrative_entailment']
        published=[p for p in row['section_enrichment']['paragraphs']
                   if p['basis']=='synthesized_and_critic_reviewed']
        self.assertGreater(len(reviewed),1)
        expected=sum(len(payload['research_evidence']['claims']) for role,_,payload in inputs.agent_inputs
                     if role==legacy.SYNTHESIS_ROLE)
        self.assertEqual(expected,len(reviewed))
        self.assertTrue(published) # Equivalent claims may be deduplicated by the renderer.
        self.assertTrue(all(len(p['research_evidence']['claims'])==1 for p in reviewed))

    def test_synthesized_paragraph_is_published_in_the_actual_skill(self):
        inputs=NarrativeInputs(); result=invoke(inputs)
        row=result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'], row['skill_publication'])
        text=inputs.store[(13,'company_memory')]['text']
        self.assertIn(PROFILE_MARKER,text)
        self.assertIn('### Annex: Evidence',text)
        self.assertIn('### Annex: Previous Memory',text)
        self.assertTrue(any(p['basis']=='synthesized_and_critic_reviewed' for p in row['section_enrichment']['paragraphs']))
        self.assertNotIn('[[',text)
        self.assertIn(row['profile_document']['text'].strip(),text)
        self.assertNotIn(legacy.BENCHMARK_ROLE,inputs.role_calls)

    def test_unresolved_narrative_falls_back_without_losing_valid_research(self):
        inputs=NarrativeInputs();inputs.reject_narrative=True
        row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertGreater(row['accepted_claim_count'],0)
        self.assertTrue(row['section_enrichment']['narrative_issues'])
        self.assertTrue(all(p['basis']=='reviewed_claim_prose_fallback' for p in row['section_enrichment']['paragraphs']))
        self.assertIn('Annex: Need Review',inputs.store[(13,'company_memory')]['text'])

    def test_unmapped_or_cross_section_prose_is_never_approved(self):
        paragraphs,issues=extract_paragraphs([{'section_id':'company_profile','content':'Unfounded fact. [[c1]]',
            'subsections':[]}],[{'claim_id':'c1','section_id':'markets_commercial_signals'}])
        self.assertEqual([],paragraphs);self.assertTrue(issues)

    def test_old_fixture_without_prose_mappings_still_publishes_supported_paragraphs(self):
        inputs=Inputs();row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertIn(PROFILE_MARKER,inputs.store[(13,'company_memory')]['text'])

    def test_historical_date_and_qualifiers_survive_fallback_and_sources_appear_once(self):
        claim={'claim_id':'c1','section_id':'company_profile','statement':'Example was recorded in Amman.',
            'as_of_date':'2019-09-08','evidence_qualifiers':['historical_governed_baseline_snapshot'],
            'source_spans':[{'start':0,'end':20}], 'citation_locators':['https://example.org/report']}
        candidate=MemoryCandidate(59,MEMORY_TARGET_SECTION,'',('c1',))
        result,meta=build_profile_candidate(candidate,'Previous exact memory.',[claim],company_name='Example')
        self.assertIn('2019-09-08',result.markdown.split('### Annex: Evidence')[0])
        self.assertEqual(1,result.markdown.count('https://example.org/report'))
        self.assertIn('Previous exact memory.',result.markdown)
        self.assertTrue(meta['baseline_preserved'])

    def test_budget_trace_is_actual_dispatch_and_never_whole_memory_for_downstream(self):
        inputs=NarrativeInputs();row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(all(m['within_input_budget'] for m in row['agent_input_preflight']['measurements']))
        self.assertLessEqual(row['agent_input_preflight']['observed_peak_parallel_calls'],2)
        self.assertLessEqual(row['agent_input_preflight']['provider_dispatch_count'],48)
        for role,_,payload in inputs.agent_inputs:
            if role in {legacy.STRATEGIC_ROLE,legacy.SYNTHESIS_ROLE}:
                self.assertIn('prior_memory_scope',payload)
                self.assertLessEqual(len(payload['existing_company_memory']),2400)

    def test_two_passes_reflect_before_one_publication_phase(self):
        inputs=NarrativeInputs();inputs['variables']['portfolio_review_passes']=2
        row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertEqual(2,row['portfolio_review_pass_count'])
        self.assertTrue(row['methodology_feedback_consumed'])
        self.assertEqual(2,inputs.mutables.count('company_memory')) # preview and apply, once

    def test_preview_never_writes(self):
        inputs=NarrativeInputs();inputs['variables']['memory_mode']='preview'
        row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertFalse(inputs.mutables)
        self.assertEqual('not_requested',row['skill_publication']['status'])

    def test_real_runtime_retains_native_grounding_and_readable_profile(self):
        import devtools.preview_output_validator as validator
        if getattr(validator,'IS_TEST_STUB',False):self.skipTest('Runtime qualification uses the real validator')
        # No network/provider: fixture envelopes exercise the real citation and
        # retention code, including Markdown in the proposed Skill document.
        inputs=NativeInputs();inputs.text_mode=True
        result=invoke_v0_1_42(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.42')
        row=result['outputs']['intelligence_dossier']['company_results'][0]
        validator.validate_preview_outputs(result['outputs'])
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertTrue(row['retention_admission']['exact_candidate_validated'])

    def test_prepublication_retention_rejection_never_reaches_mutation(self):
        from devtools.preview_output_validator import PreviewOutputValidationError
        inputs=NarrativeInputs()
        def reject(outputs):
            if 'proposed_skills' in outputs:
                raise PreviewOutputValidationError('unsafe_runtime_value',('response','outputs','proposed_skills','text'))
        with patch('retention_preflight_v0_1_42.validate_preview_outputs',side_effect=reject):
            row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertFalse(inputs.mutables)
        self.assertFalse(row['skill_publication']['publication_complete'])
        self.assertTrue(row['retention_admission']['publication_withheld'])

    def test_bad_optional_source_projection_keeps_safe_exact_profile(self):
        from devtools.preview_output_validator import PreviewOutputValidationError
        inputs=NarrativeInputs()
        def reject_source(outputs):
            if 'retrieved_source_snapshot' in outputs.get('intelligence_dossier',{}):
                raise PreviewOutputValidationError('unsafe_runtime_value',('response','outputs','result','text'))
        with patch('retention_preflight_v0_1_42.validate_preview_outputs',side_effect=reject_source):
            row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertNotIn('retrieved_source_snapshot',row)
        self.assertEqual('ready_with_omissions',row['retention_admission']['status'])
        self.assertEqual('retrieved_source_snapshot',row['retention_admission']['omitted_fields'][0]['field'])

    def test_repeated_run_does_not_republish_identical_profile_or_guidance(self):
        inputs=NarrativeInputs();invoke(inputs);before=inputs.store[(13,'company_memory')]['text']
        inputs.mutables.clear()
        row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual(before,inputs.store[(13,'company_memory')]['text'])
        self.assertEqual('no_change',row['skill_publication']['memory']['status'])

    def test_guidance_deduplicates_the_same_action_without_changing_resolution(self):
        from methodology_learning_v0_1_42 import build_methodology_learning_proposal,read_guidance
        row={'section_id':'company_profile','subsection_id':'identity','observation':'Missing source.',
            'next_action':'Read the dated report.','success_check':'Exact entity and date.','origin':'section_critic'}
        first=build_methodology_learning_proposal('',feedback=[row])
        second=build_methodology_learning_proposal(first.candidate,feedback=[{**row,'observation':'Still missing source.'}])
        self.assertFalse(second.changed)
        self.assertEqual(1,len(read_guidance(second.candidate)))

if __name__=='__main__':unittest.main()
