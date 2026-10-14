"""Source verification through real exact-span tools, fake public reads, no providers."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys, unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from test_final_cycle_v0_1_26 import SourceInputs
from structured_review_toolkit.tool_operations_v0_1_2 import execute_operation
from test_profile_primary_v0_1_43 import DraftInputs
from source_verification_v0_1_44 import TargetedSourceInputs, candidate_passage
from orchestration_v0_1_44 import invoke_v0_1_44
from profile_research_v0_1_44 import research_records
from critic_contract_v0_1_40 import select_validated_sections
from devtools.public_reference import PublicReferenceError
from devtools.skill_citation import CitationRef
import legacy_preparation_helpers_v0_1_23 as legacy

STATEMENT='Example Therapeutics reported a research facility in Amman, Jordan in 2025.'
URL='https://example.org/report'

def payload(url=URL, statement=STATEMENT):
    return {'role':'portfolio_researcher','claims':[{'claim_id':'c1','section_id':'company_profile',
        'statement':statement,'citation_locators':[url],'evidence_quotes':[]}]}

def response(url=URL, text=STATEMENT, **extra):
    return SimpleNamespace(final_url=url,text=text,title='Annual report',content_type='text/html',metadata={},**extra)

class Reader(SourceInputs):
    def __init__(self):super().__init__();self.reads=[];self.result=response()
    def open_reference(self,target,*,mode):
        self.reads.append(target.url)
        if isinstance(self.result,Exception):raise self.result
        return self.result
    def invoke_asset(self,role,*,variables,on_error):
        self.requests.append(variables)
        result=execute_operation(variables)
        if self.corrupt:result['output']['spans'][0]['end']+=1
        return {'status':'success','result':result}

def source(raw):return TargetedSourceInputs(raw,record={'company_id':13,'company':'Example'})

class SourceVerificationTests(unittest.TestCase):
    def test_query_only_response_retrieves_source_and_pins_exact_passage(self):
        raw=Reader();s=source(raw);original=payload('https://example.org/redirect')
        before=deepcopy(original)
        value,citations=s.verify_source_claims(original)
        claim=value['claims'][0];span=claim['source_spans'][0]
        self.assertEqual(before,original)
        self.assertEqual(STATEMENT,span['quote']);self.assertEqual(0,span['source_document_start'])
        self.assertNotIn('_source_issue',claim)
        self.assertEqual('literal_passage_pending_claim_critic',claim['source_verification'])
        self.assertEqual(URL,claim['citation_locators'][0]);self.assertTrue(raw.requests)
        self.assertTrue(any(c.locator==URL for c in citations))
        self.assertFalse(raw.requests[0].get('semantic_authority_verified',False))
        # Retrieval never sets the final business verification status.
        self.assertNotIn('verification_status',claim)
        rejected=select_validated_sections({'claims':[claim],'withheld_claims':[]},
            {'reviewed_claim_ids':['c1'],'rejected_claim_ids':['c1']})
        records,_=research_records(rejected)
        self.assertEqual('unverified',records[0]['verification_status'])

    def test_native_citation_path_does_not_add_reads(self):
        raw=Reader();s=source(raw)
        ref=CitationRef(locator=URL,title='Native',source_kind='agent_citation',
            provider_family='vertex_ai',provider_turn_index=1,source_pointer=('candidate','groundingMetadata'))
        value,_=s.verify_source_claims(payload(),admitted=[ref])
        self.assertTrue(value['claims'][0]['native_grounding']);self.assertFalse(raw.reads)

    def test_repeated_and_concurrent_calls_share_requested_and_final_url_cache(self):
        raw=Reader();s=source(raw)
        with ThreadPoolExecutor(max_workers=2) as pool:
            values=list(pool.map(lambda _:s.verify_source_claims(payload('https://example.org/redirect')),range(2)))
        s.verify_source_claims(payload())
        self.assertEqual(['https://example.org/redirect'],raw.reads)
        self.assertTrue(all(v[0]['claims'][0].get('source_spans') for v in values))

    def test_unavailable_challenge_empty_and_irrelevant_sources_stay_unverified(self):
        cases=[PublicReferenceError('public_reference_target_nonpublic'),response(text=''),
               response(text='Verify you are human before accessing this source.'),
               response(text='A different corporation has no connection to the target entity in this research.')]
        for result in cases:
            with self.subTest(result=type(result).__name__):
                raw=Reader();raw.result=result;s=source(raw)
                value,_=s.verify_source_claims(payload())
                self.assertNotIn('source_spans',value['claims'][0])
                self.assertEqual(STATEMENT,value['claims'][0]['statement'])

    def test_read_and_time_budgets_do_not_raise_or_manufacture_support(self):
        raw=Reader();s=source(raw);s._discovered_reads=48
        value,_=s.verify_source_claims(payload())
        self.assertFalse(raw.reads);self.assertNotIn('source_spans',value['claims'][0])
        self.assertTrue(any(o.get('reason')=='discovered_source_read_budget' for o in s.observations))
        raw=Reader();s=source(raw);s._verification_seconds=120
        with patch('source_verification_v0_1_44.monotonic',return_value=1000):
            value,_=s.verify_source_claims(payload())
        self.assertFalse(raw.reads);self.assertNotIn('source_spans',value['claims'][0])

    def test_thinking_between_research_pieces_does_not_consume_read_time(self):
        raw=Reader();s=source(raw)
        with patch('source_verification_v0_1_44.monotonic',return_value=1000):
            s.verify_source_claims(payload())
        with patch('source_verification_v0_1_44.monotonic',return_value=2200):
            s.verify_source_claims(payload('https://example.org/second-report'))
        self.assertEqual(2,len(raw.reads))

    def test_source_quotes_stay_with_critic_and_out_of_prose_writer_input(self):
        raw=Reader();s=source(raw)
        value,_=s.verify_source_claims(payload())
        before=deepcopy(value)
        critic=s.prepare_input(legacy.CRITIC_ROLE,{'research_evidence':value})
        synthesis=s.prepare_input(legacy.SYNTHESIS_ROLE,{'research_evidence':value})
        self.assertEqual(before,value)
        self.assertTrue(all(span['quote']==STATEMENT for span in critic['research_evidence']['exact_span_catalog'].values()))
        self.assertTrue(all('quote' not in span for span in synthesis['research_evidence']['exact_span_catalog'].values()))
        claim=synthesis['research_evidence']['claims'][0]
        self.assertNotIn('evidence_quotes',claim)
        self.assertNotIn('source_spans',claim)
        self.assertEqual(STATEMENT,claim['statement'])
        self.assertTrue(claim['exact_span_refs'])

    def test_corrupt_tool_response_keeps_claim_unverified(self):
        raw=Reader();raw.corrupt=True;s=source(raw)
        value,_=s.verify_source_claims(payload())
        self.assertNotIn('source_spans',value['claims'][0])
        self.assertTrue(any(o.get('reason')=='source_exact_span_unresolved' for o in s.observations))

    def test_pdf_page_location_and_whole_numeric_lines_are_preserved(self):
        raw=Reader();raw.result=response(text='[Page 39]\n\n'+STATEMENT)
        value,_=source(raw).verify_source_claims(payload())
        self.assertEqual(39,value['claims'][0]['source_spans'][0]['page_number'])
        text='Company 2025 revenue table\nExample Therapeutics total revenue 1,234.56 million\nUS revenue 900.00 million\n'
        selected=candidate_passage({'statement':'Example Therapeutics total revenue was 1,234.56 million in 2025.'},text)
        self.assertIsNotNone(selected);self.assertIn('1,234.56',selected[1])

    def test_partial_clause_requires_critic_review_despite_literal_match(self):
        raw=Reader();s=source(raw)
        value,_=s.verify_source_claims(payload(statement=STATEMENT+' It opened on January 1, 2025.'))
        self.assertTrue(value['claims'][0].get('source_spans'))
        prepared=s.prepare_input(legacy.CRITIC_ROLE,{'company_id':13})
        self.assertIn('EVERY material clause',prepared['source_verification_instruction'])
        self.assertIn('needs_review',prepared['source_verification_instruction'])

    def test_full_apply_retains_profile_when_every_source_is_unavailable(self):
        inputs=DraftInputs()
        row=invoke_v0_1_44(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.44')['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertEqual(0,row['accepted_claim_count'])
        self.assertEqual(4,row['required_section_coverage_count'])
        self.assertIn('Annex: Unverified Research',row['profile_document']['text'])
        self.assertNotIn(legacy.BENCHMARK_ROLE,inputs.role_calls)

    def test_full_apply_receives_literal_sources_in_existing_critic_without_new_agent_role(self):
        class Discoverable(DraftInputs):
            def __init__(self):super().__init__();self.discovered={};self.critic_spans=[]
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role==legacy.CRITIC_ROLE:
                    self.critic_spans.extend(input['research_evidence'].get('exact_span_catalog',{}).values())
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                if role in legacy.RESEARCH_ROLES:
                    for claim in envelope['result']['content'][0]['value']['claims']:
                        for locator in claim['citation_locators']:
                            self.discovered.setdefault(locator,[]).append(claim['statement'])
                return envelope
            def open_reference(self,target,*,mode):
                if target.url not in self.discovered:raise PublicReferenceError('public_reference_fixture_unavailable')
                return response(target.url,'\n\n'.join(dict.fromkeys(self.discovered[target.url])))
        inputs=Discoverable()
        row=invoke_v0_1_44(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.44')['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(inputs.critic_spans)
        self.assertGreater(row['accepted_claim_count'],0)
        self.assertTrue(row['skill_publication']['publication_complete'],row['skill_publication'])
        self.assertTrue(all(span.get('source_digest') for span in inputs.critic_spans))
        self.assertNotIn(legacy.BENCHMARK_ROLE,inputs.role_calls)
        self.assertNotIn(legacy.RESEARCH_RESOLVER_ROLE,inputs.role_calls)

    def test_exhausted_toolkit_budget_is_local_and_readable_text_survives(self):
        raw=Reader();s=source(raw);s.toolkit_calls=32
        value,_=s.verify_source_claims(payload())
        self.assertEqual(STATEMENT,value['claims'][0]['statement'])
        self.assertNotIn('source_spans',value['claims'][0]);self.assertFalse(raw.requests)

if __name__=='__main__':unittest.main()
