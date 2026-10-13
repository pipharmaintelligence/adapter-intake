"""First-package publication uses admitted Core creation; existing updates stay unchanged."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from devtools.dynamic_skill_runtime import DynamicSkillRuntimeError
try:
 from devtools.skill_document import SkillDocument
 from devtools.skill_changes import SkillChangeSet
except ImportError:
 raise unittest.SkipTest("First-package SDK qualification requires the real runtime")
from automatic_publication_v0_1_38 import publish_company
from skill_initialization_v0_1_38 import initialize_section

class Inputs:
 def __init__(self):self.store={};self.initializations=[];self.fail_readback=False
 def dynamic_skill(self,role,*,variables):
  assert variables=={'company_id':'59'} and not role.endswith('_update')
  if role not in self.store:raise DynamicSkillRuntimeError('dynamic_skill_not_initialized')
  if self.fail_readback:raise DynamicSkillRuntimeError('dynamic_skill_delivery_failed')
  source=self.store[role];document=SkillDocument.parse(source)
  return SimpleNamespace(provenance=lambda:SimpleNamespace(mutable=False,package_digest='sha256:'+sha256(source.encode()).hexdigest()),
      read=lambda:source,content_digest=lambda:document.digest,has_section=document.has_section,section_text=document.section_text)
 def initialize_dynamic_skill(self,role,*,variables,markdown):
  assert variables=={'company_id':'59'} and role.endswith('_update')
  read_role=role.removesuffix('_update')
  if read_role in self.store:raise DynamicSkillRuntimeError('dynamic_skill_initialization_partition_exists')
  self.initializations.append(role);self.store[read_role]=markdown
  return {'status':'initialized','change_id':None,'after_digest':SkillDocument.parse(markdown).digest,
      'upload_id':len(self.initializations),'operation_id':'fixture-operation','upload_verified':True,
      'readback_verified':True,'history_verified':False}

def state(methodology=None):
 return {'company_id':59,'memory_candidate':SimpleNamespace(fact_ids=('f1',),target_section='Current Public Research',markdown='Supported fixture fact.'),
   'evidence_selection':SimpleNamespace(complete=True,public_citations=lambda:[]),
   'critic':{'section_outcomes':[{'section_id':'company_profile','status':'validated'}]},
   'joined_research':{'claims':[{'claim_id':'f1','section_id':'company_profile','source_spans':[{'fixture':True}]}]},
   'result':{'section_enrichment':{'baseline_preserved':True},'methodology_learning_before_digest':None},
   'before_target_text':None,'before_digest':None,'methodology_learning_candidate':methodology,'candidate_changed':True,
   'review_baselines':{'company_memory':{'package_digest':None},'company_methodology':{'package_digest':None}}}

class FirstPublicationTests(unittest.TestCase):
 def test_full_existing_company_pipeline_preserves_chunks_recovery_and_disabled_benchmark(self):
  from test_source_parity_v0_1_35 import Inputs as FullInputs,legacy,_fake_citations
  from orchestration_v0_1_38 import invoke_v0_1_38
  inputs=FullInputs()
  with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
   result=invoke_v0_1_38(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.38')
  dossier=result['outputs']['intelligence_dossier'];self.assertTrue(dossier['publication_complete'])
  row=dossier['company_results'][0]
  self.assertEqual(1,row['portfolio_review_pass_count']);self.assertFalse(row['benchmark_enabled'])
  self.assertEqual(0,row['benchmark_agent_call_count']);self.assertLessEqual(row['agent_input_preflight']['observed_peak_parallel_calls'],2)
 def test_absent_memory_creates_complete_document_and_does_not_invent_optional_learning(self):
  inputs=Inputs();result=publish_company(inputs,state())
  self.assertTrue(result['publication_complete']);self.assertEqual(['company_memory_update'],inputs.initializations)
  self.assertEqual('initialized',result['memory']['status']);self.assertEqual('no_change',result['methodology']['status'])
  self.assertIsNone(result['memory']['change_id']);self.assertFalse(result['memory']['history_verified'])
  self.assertNotIn('company_methodology',inputs.store)
  self.assertIn('## Current Public Research',inputs.store['company_memory'])
  self.assertIn('Supported fixture fact.',inputs.store['company_memory'])
 def test_eligible_new_learning_creates_its_own_complete_skill(self):
  inputs=Inputs();result=publish_company(inputs,state('Actual fixture procedural learning.'))
  self.assertTrue(result['publication_complete']);self.assertEqual(2,len(inputs.initializations))
  self.assertIn('## Methodology Learning',inputs.store['company_methodology'])
 def test_existing_memory_uses_the_same_update_helper_without_creation(self):
  inputs=Inputs();publish_company(inputs,state());inputs.initializations=[]
  existing=inputs.dynamic_skill('company_memory',variables={'company_id':'59'});candidate=state()
  candidate['before_digest']=existing.content_digest();candidate['before_target_text']=existing.section_text('Current Public Research')
  candidate['review_baselines']['company_memory']['package_digest']=existing.provenance().package_digest
  with patch('automatic_publication_v0_1_38._apply_section',return_value={'status':'applied','readback_verified':True,'history_verified':True}) as update:
   result=publish_company(inputs,candidate)
  self.assertTrue(result['publication_complete']);self.assertEqual([],inputs.initializations)
  self.assertEqual('company_memory_update',update.call_args.args[3])
 def test_stale_existing_baseline_stops_before_other_creation(self):
  inputs=Inputs();publish_company(inputs,state());inputs.initializations=[]
  result=publish_company(inputs,state('New procedural learning.'))
  self.assertFalse(result['publication_complete']);self.assertEqual([],inputs.initializations)
  self.assertEqual('baseline_changed',result['memory']['reason'])
 def test_critic_rejection_withholds_both_without_initialization(self):
  inputs=Inputs();candidate=state();candidate['critic']['section_outcomes'][0]['status']='needs_enrichment'
  result=publish_company(inputs,candidate)
  self.assertFalse(result['publication_complete']);self.assertEqual([],inputs.initializations)
 def test_readback_failure_preserves_known_upload_and_stops_second_write(self):
  inputs=Inputs();inputs.fail_readback=True;result=publish_company(inputs,state('New learning.'))
  self.assertFalse(result['publication_complete']);self.assertEqual(1,len(inputs.initializations))
  self.assertEqual('initialized_readback_unverified',result['memory']['status'])
  self.assertEqual(1,result['memory']['upload_id']);self.assertIsNone(result['methodology'])
 def test_concurrent_creator_is_never_overwritten_or_retried(self):
  class Racing(Inputs):
   def initialize_dynamic_skill(self,*args,**kwargs):
    self.initializations.append(args[0]);raise DynamicSkillRuntimeError('dynamic_skill_initialization_partition_exists')
  inputs=Racing();result=publish_company(inputs,state())
  self.assertFalse(result['publication_complete']);self.assertEqual(1,len(inputs.initializations));self.assertEqual({},inputs.store)
 def test_first_document_preserves_exact_sdk_citation_annotations(self):
  from devtools.skill_citation import CitationRef
  inputs=Inputs();receipt=initialize_section(inputs,59,'company_memory','company_memory_update','Current Public Research',
    'Supported fixture fact.',(CitationRef(locator='https://example.test/source',title='Fixture source'),))
  self.assertTrue(receipt['readback_verified']);self.assertIn('https://example.test/source',inputs.store['company_memory'])

if __name__=='__main__':unittest.main()
