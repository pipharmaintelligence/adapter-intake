"""Editorial regression tests; no providers or real storage writes."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json, sys, unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
from test_profile_primary_v0_1_43 import DraftInputs
from orchestration_v0_1_44 import invoke_v0_1_44
from profile_research_v0_1_44 import qualified_statement, build_profile_candidate, BUSINESS_SECTIONS
from downstream_chunks_v0_1_44 import packets_for_synthesis
from agent_chunks_v0_1_42 import ChunkCoordinator
from targeted_inputs_v0_1_43 import TargetedSourceInputs
from preparation_context_v0_1_43 import PreparationContextInputs
from memory_contract import MemoryCandidate, MEMORY_TARGET_SECTION
import legacy_preparation_helpers_v0_1_23 as legacy


def claim(i=0, section='company_profile', **extra):
    return {'claim_id':str(i), 'section_id':section,
        'statement':'As of February 19, 2026, Example reported an observation '+str(i)+'.',
        'as_of_date':'2026-02-19', 'evidence_qualifiers':[], 'citation_locators':[],
        'verification_status':'unverified', **extra}


def packet_inputs():
    # Real projections, guidance and measurement with a provider-free handle.
    fake = DraftInputs()
    fake.coordinator = ChunkCoordinator()
    source = TargetedSourceInputs(fake, record={'company_id':13, 'company':'Example'}, memory_text='', memory_digest=None)
    return PreparationContextInputs(source, learned_methodology_text='')


def packet_base():
    return {'company_id':13, 'company_name':'Example', 'methodology_packet':{'memory_rules':[]},
        'canonical_sections':legacy._section_requests(BUSINESS_SECTIONS),
        'narrative_instruction':'Editorial instructions.',
        'response_contract':legacy.response_contract_for_role(legacy.SYNTHESIS_ROLE, company_id=13),
        'critic_findings':{'unrelated_notes':'old critic record ' * 6000},
        'existing_company_memory':'old history ' * 6000,
        'strategic_analysis':{'unrelated':'prior analysis ' * 6000},
        'methodology_plan':{'research_focus':[]}}


class ReadableProseTests(unittest.TestCase):
    def test_equivalent_dates_are_not_prefixed_again(self):
        for date in ('February 19, 2026','19 February 2026','Feb. 19th, 2026','2026-02-19'):
            with self.subTest(date=date):
                c = claim(statement='As of '+date+', Example reported unchanged rights.')
                self.assertEqual(c['statement'], qualified_statement(c))

    def test_different_material_dates_and_qualifications_survive(self):
        c = claim(statement='On January 2, 2025, Example had not secured regional rights.',
                  inference=True, evidence_qualifiers=['historical_snapshot','rights_unconfirmed'])
        result = qualified_statement(c)
        self.assertIn('2026-02-19',result)
        self.assertIn(c['statement'], result)
        self.assertIn('Interpretation', result)
        self.assertIn('rights unconfirmed', result)
        self.assertEqual('historical_snapshot', c['evidence_qualifiers'][0])

    def test_adjacent_duplicate_dates_only_are_collapsed(self):
        c = claim(statement='As of 2026-02-19, As of February 19, 2026, Example reported unchanged rights.')
        self.assertEqual('As of 2026-02-19, Example reported unchanged rights.', qualified_statement(c))
        c['statement']='As of 2026-02-19, As of January 2, 2025, Example had not secured rights.'
        self.assertEqual(c['statement'], qualified_statement(c))

    def test_fallback_preserves_separate_statements_and_numeric_annex(self):
        claims=[claim(i) for i in range(7)]
        candidate=MemoryCandidate(13,MEMORY_TARGET_SECTION,'',())
        result,meta=build_profile_candidate(candidate,'Existing exact memory.',[],research=claims,company_name='Example')
        self.assertEqual(7,len(meta['paragraphs']))
        self.assertTrue(all(len(p['claim_ids'])==1 for p in meta['paragraphs']))
        for c in claims:
            self.assertEqual(1,result.markdown.count(c['statement']))
        annex=result.markdown.split('### Annex: Unverified Research\n',1)[1].split('### Annex:',1)[0]
        self.assertNotIn('Example',annex)
        self.assertEqual((),result.fact_ids)
        self.assertIn('Existing exact memory.',result.markdown)

    def test_fifty_claims_fit_four_section_packets_with_unchanged_limits(self):
        inputs=packet_inputs()
        claims=[claim(i, BUSINESS_SECTIONS[i % 4],
            semantic_context={'actor':'Example','counterparty':None,'event_state':'reported','scope':'qualified ' * 35},
            citation_locators=['https://example.org/report/'+str(i)],
            semantic_rule_ids=['rule'+str(j) for j in range(10)]) for i in range(50)]
        before=deepcopy(claims)
        packets,omitted=packets_for_synthesis(inputs,{'claims':claims},packet_base())
        self.assertFalse(omitted)
        self.assertEqual(4,len(packets))
        self.assertEqual(set(str(i) for i in range(50)),{c['claim_id'] for p in packets for c in p['_piece_claims']})
        self.assertEqual(before,claims)
        for packet in packets:
            self.assertTrue(inputs.coordinator.measure(legacy.SYNTHESIS_ROLE,packet)['within_input_budget'])
            self.assertNotIn('critic_findings',packet)
            self.assertNotIn('existing_company_memory',packet)
            self.assertIn('prior_critic_guidance',packet)
            self.assertEqual(packet['_piece_claims'],packet['research_evidence']['claims'])
            self.assertEqual([],packet['allowed_memory_fact_ids'])
        self.assertEqual(6,inputs.coordinator.role_budgets[legacy.SYNTHESIS_ROLE])
        self.assertEqual(48,inputs.coordinator.max_calls)

    def test_each_section_gets_a_turn_before_overflow(self):
        inputs=packet_inputs()
        claims=[claim(i, statement='Complete qualified observation '+str(i)+': '+('word '*410)) for i in range(10)]
        claims += [claim(100+i,sid) for i,sid in enumerate(BUSINESS_SECTIONS[1:])]
        packets,omitted=packets_for_synthesis(inputs,{'claims':claims},packet_base())
        self.assertFalse(omitted)
        self.assertEqual(list(BUSINESS_SECTIONS),[p['_piece_section_ids'][0] for p in packets[:4]])
        self.assertEqual(len(claims),sum(len(p['_piece_claims']) for p in packets))

    def test_full_apply_uses_real_sdk_readback_without_grounding_gate(self):
        inputs=DraftInputs()
        row=invoke_v0_1_44(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.44')['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'],row['skill_publication'])
        self.assertEqual(0,row['accepted_claim_count'])
        self.assertEqual(4,len(row['section_enrichment']['sections']))
        self.assertTrue(all(p['basis']=='synthesized_unverified_research' for p in row['section_enrichment']['paragraphs']))
        self.assertTrue(row['retention_admission']['exact_candidate_validated'])
        self.assertEqual(row['profile_document']['text'].strip(),inputs.dynamic_skill('company_memory',variables={'company_id':'13'}).section_text('Current Public Research').strip())
        self.assertNotIn(legacy.BENCHMARK_ROLE,inputs.role_calls)

    def test_optional_reflection_still_publishes_once_and_reads_previous_prose(self):
        inputs=DraftInputs();inputs['variables']['portfolio_review_passes']=2
        row=invoke_v0_1_44(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.44')['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        second=[p for role,_,p in inputs.agent_inputs if role in legacy.RESEARCH_ROLES and p['review_iteration']['pass_number']==2]
        self.assertTrue(second)
        self.assertTrue(any('Unverified research.' in p['prior_profile_context'] for p in second))
        self.assertEqual(2,inputs.mutables.count('company_memory'))

    def test_unresolved_synthesis_preserves_research_and_does_not_stop_apply(self):
        class Unresolved(DraftInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role==legacy.SYNTHESIS_ROLE:
                    raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(
                        role=role,stage='agent_response_payload',field='sections',rule='fixture_unresolved'))
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Unresolved()
        row=invoke_v0_1_44(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.44')['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertTrue(row['chunk_phase_issues'])
        self.assertEqual({c['claim_id'] for c in row['profile_research']},
                         {c for p in row['section_enrichment']['paragraphs'] for c in p['claim_ids']})
        self.assertTrue(all(len(p['claim_ids'])==1 for p in row['section_enrichment']['paragraphs']))
        self.assertEqual(0,row['accepted_claim_count'])

    def test_historical_contracts_and_all_other_agent_roles_are_unchanged(self):
        m=json.loads((ROOT/'nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        previous={k:v for k,v in m['versions'].items() if k!='0.1.44'}
        self.assertEqual('abdeefb6e64f0c933ad1ca2e895dd0ffacdb074b8bf737d20ccbb45d415cbb95',sha256(json.dumps(previous,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        old=m['versions']['0.1.43'];new=m['versions']['0.1.44']
        self.assertEqual({k:v for k,v in old.items() if k!='agents'},{k:v for k,v in new.items() if k!='agents'})
        for role in old['agents']:
            if role!=legacy.SYNTHESIS_ROLE:self.assertEqual(old['agents'][role],new['agents'][role])
        self.assertEqual('1.0.11',new['agents'][legacy.SYNTHESIS_ROLE]['contract_version'])
        old_policy=old['agents'][legacy.SYNTHESIS_ROLE]['definition']['chain']['steps'][0]['provider_policy']
        self.assertEqual(old_policy,new['agents'][legacy.SYNTHESIS_ROLE]['definition']['chain']['steps'][0]['provider_policy'])


if __name__=='__main__':unittest.main()
