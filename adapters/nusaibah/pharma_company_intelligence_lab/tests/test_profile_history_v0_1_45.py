"""Current profile consolidation, real toolkit IDs and whole-execution read bounds."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import sys, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from test_source_verification_v0_1_44 import Reader, payload, response, STATEMENT
from test_profile_primary_v0_1_43 import DraftInputs
from source_verification_v0_1_45 import TargetedSourceInputs, digest
from profile_research_v0_1_45 import build_profile_candidate
from memory_contract import MemoryCandidate, MEMORY_TARGET_SECTION
from reference_budget_v0_1_45 import ReferenceBudgetInputs
from orchestration_v0_1_45 import invoke_v0_1_45
from devtools.public_reference import ReferenceTarget
from devtools.public_web_runtime import PublicWebRuntimeError


def candidate():return MemoryCandidate(59,MEMORY_TARGET_SECTION,'',())
def claim(text,identity='draft'):
    return {'claim_id':identity,'section_id':'company_profile','statement':text,
            'citation_locators':[],'verification_status':'unverified','evidence_qualifiers':[]}


class ProfileHistoryTests(unittest.TestCase):
    def test_three_updates_keep_one_current_profile_and_unique_old_knowledge(self):
        first,_=build_profile_candidate(candidate(),'',[ ],research=[claim('The company researches medicines.')],company_name='Pfizer')
        nested=first.markdown+'\n\n### Annex: Previous Memory\n\nOBSOLETE DUPLICATE\n\n### Annex: Previous Memory\n\nOLDER DUPLICATE'
        second,_=build_profile_candidate(candidate(),nested,[],research=[claim('The company operates a laboratory.','new')],company_name='Pfizer')
        third,_=build_profile_candidate(candidate(),second.markdown,[],research=[claim('The company operates a laboratory.','new')],company_name='Pfizer')
        self.assertEqual(second.markdown,third.markdown)
        self.assertNotIn('Annex: Previous Memory',third.markdown)
        self.assertNotIn('OBSOLETE DUPLICATE',third.markdown)
        self.assertEqual(1,third.markdown.count('The company researches medicines.'))
        self.assertEqual(1,third.markdown.count('The company operates a laboratory.'))
        self.assertEqual((),third.fact_ids)
        self.assertLess(len(third.markdown),5000)

    def test_new_evidence_duplicate_does_not_copy_old_paragraph(self):
        first,_=build_profile_candidate(candidate(),'',[],research=[claim('The company researches medicines.')])
        next_,_=build_profile_candidate(candidate(),first.markdown,[],research=[claim('The company researches medicines.','different-id')])
        self.assertEqual(1,next_.markdown.count('The company researches medicines.'))

    def test_missing_new_research_keeps_existing_document_unchanged(self):
        before='Existing current profile.'
        result,_=build_profile_candidate(candidate(),before,[],research=[])
        self.assertEqual(before,result.markdown)

    def test_memory_dedup_preserves_numeric_signs_dates_and_qualifications(self):
        from profile_memory_v0_1_45 import current_memory_records
        old='#### 1. Company Profile\n\nMargin was -5% in 2025.\n\nRevenue was 1.5 million in 2024.'
        rows=current_memory_records(old,[claim('Margin was 5% in 2025.'),claim('Revenue was 15 million in 2024.')],[])
        self.assertEqual(2,len(rows))
        self.assertTrue(all(r['verification_status']=='unverified' for r in rows))

    def test_long_url_uses_bound_short_toolkit_locator_without_rewriting_proof(self):
        raw=Reader();url='https://example.org/'+('long-path/'*30)+'report.pdf'
        raw.result=response(url,text='[Page 9]\n\n'+STATEMENT)
        original=payload(url);saved=deepcopy(original)
        value,citations=TargetedSourceInputs(raw,record={'company_id':13,'company':'Example'}).verify_source_claims(original)
        self.assertEqual(saved,original)
        row=value['claims'][0];span=row['source_spans'][0]
        locator=span['locator'];binding=span['source_binding']
        self.assertLess(len(locator),128)
        self.assertEqual('source:'+digest(binding),locator)
        self.assertEqual(url,binding['source_url'])
        self.assertEqual(url,row['citation_locators'][0])
        self.assertEqual(locator,raw.requests[0]['arguments']['requests'][0]['locator'])
        self.assertEqual(locator,raw.requests[0]['arguments']['source_units'][0]['locator'])
        self.assertEqual(STATEMENT,span['quote']);self.assertEqual(9,span['page_number'])
        self.assertTrue(any(c.locator==url for c in citations))

    def test_whole_invocation_budget_is_shared_and_atomic(self):
        raw=Reader();bounded=ReferenceBudgetInputs(raw)
        target=ReferenceTarget.business_url('https://example.org')
        def read(_):
            try:bounded.open_reference(target,mode='http');return True
            except PublicWebRuntimeError as e:
                self.assertEqual('public_web_reference_budget_exhausted',e.code);return False
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(read,range(40)))
        self.assertEqual(20,len(raw.reads));self.assertEqual(20,sum(results))
        self.assertEqual(0,bounded.remaining_reference_reads)

    def test_initial_long_website_also_keeps_exact_toolkit_identity(self):
        raw=Reader();url='https://example.org/'+('long/'*40)
        raw.result=response(url,text=STATEMENT+' Public company report details.')
        raw.result.links=[];raw.result.transport='http'
        source=TargetedSourceInputs(raw,record={'company_id':13,'company':'Example','website':url})
        logical=next(u['locator'] for u in source.units if u['text'].startswith(STATEMENT))
        value=payload(logical)
        value['claims'][0]['evidence_quotes']=[{'locator':logical,'quote':STATEMENT}]
        resolved,_=source.verify_source_claims(value)
        span=resolved['claims'][0]['source_spans'][0]
        self.assertEqual('source:'+digest(span['source_binding']),span['locator'])
        self.assertEqual(url,resolved['claims'][0]['citation_locators'][0])

    def test_two_initial_reads_leave_only_eighteen_discovered_attempts(self):
        raw=Reader();source=TargetedSourceInputs(raw,record={'company_id':13,'company':'Example'})
        source.web_reads=2
        for i in range(3):
            value=payload('https://example.org/report'+str(i))
            value['claims']=[dict(value['claims'][0],claim_id='c'+str(n),
                                  citation_locators=['https://example.org/report'+str(i)+'-'+str(n)]) for n in range(16)]
            source.verify_source_claims(value)
        self.assertEqual(18,len(raw.reads))
        self.assertTrue(any(o.get('reason')=='discovered_source_read_budget' for o in source.observations))

    def test_full_two_pass_apply_preserves_profile_and_uses_existing_history(self):
        inputs=DraftInputs();inputs['variables']['portfolio_review_passes']=2
        row=invoke_v0_1_45(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.45')['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'],row['skill_publication'])
        self.assertEqual(2,row['portfolio_review_pass_count'])
        self.assertNotIn('Annex: Previous Memory',row['profile_document']['text'])
        self.assertIn('Annex: Unverified Research',row['profile_document']['text'])
        self.assertTrue(row['skill_publication']['memory']['history_verified'])


if __name__=='__main__':unittest.main()
