"""Execute a deterministic full fixture in the real Python-only isolation closure."""
import hashlib,json,shutil,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

RUNNER=r"""
import json,socket,sys,types
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'tests'));sys.path.insert(0,str(root))
assert not (root/'nusaibah_pharma_company_intelligence_lab.asset.json').exists()
# The fixture's runtime-tool bridge delegates to the real deterministic toolkit.
# This is test setup, not a direct import by production adapter code.
from adapters.intake.nusaibah.structured_review_toolkit.tool_operations_v0_1_1 import execute_operation
package=types.ModuleType('structured_review_toolkit');package.__path__=[]
module=types.ModuleType('structured_review_toolkit.tool_operations_v0_1_1');module.execute_operation=execute_operation
sys.modules[package.__name__]=package;sys.modules[module.__name__]=module
from test_automatic_enrichment_v0_1_27 import EnrichmentInputs,_fake_citations
import legacy_preparation_helpers_v0_1_23 as legacy
sys.modules.pop(package.__name__);sys.modules.pop(module.__name__)
sys.path.insert(0,str(root))
from nusaibah_pharma_company_intelligence_lab_v0_1_34_adapter import NusaibahPharmaCompanyIntelligenceLabV034Adapter
class Inputs(EnrichmentInputs):
    def __init__(self):
        super().__init__();self['variables']['company_ids']=[13]
        self.set_company_records([{'id':13,'company':'Fixture company','country':'SA'}])
    def invoke_agent(self,role,*,input,on_error='raise'):
        value=super().invoke_agent(role,input=input,on_error=on_error)
        if role==legacy.SYNTHESIS_ROLE:
            value['result']['content'][0]['value']['memory_candidate']['fact_ids']=list(dict.fromkeys(input['allowed_memory_fact_ids']))
        return value
inputs=Inputs()
with patch.object(socket.socket,'connect',side_effect=AssertionError('network_forbidden_in_closure_test')),patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
    value=NusaibahPharmaCompanyIntelligenceLabV034Adapter().invoke(inputs,{})
row=value['outputs']['intelligence_dossier']['company_results'][0]
assert row['skill_publication']['publication_complete'] is True
assert row['benchmark_agent_call_count']==0
assert row['portfolio_review_pass_count']==1
assert row['agent_input_preflight']['observed_peak_parallel_calls']<=2
assert all(p['within_input_budget'] for p in row['agent_input_preflight']['measurements'])
assert Path(sys.modules['orchestration_v0_1_34'].__file__).parent==root
assert Path(sys.modules['targeted_inputs_v0_1_34'].__file__).parent==root
print(json.dumps({'status':'passed','network_calls':0,'real_provider_calls':0,'real_skill_writes':0,'fixture_publication_complete':True,'json_manifest_present':False}))
"""

class IsolatedChunkTests(unittest.TestCase):
    def test_pinned_prompt_text_fits_reviewed_conservative_bound(self):
        manifest=json.loads((ROOT/'tests/fixtures/release-0.1.34/nusaibah_pharma_company_intelligence_lab.asset.json').read_text(encoding='utf-8'))
        for role,contract in manifest['versions']['0.1.34']['agents'].items():
            if isinstance(contract.get('definition'),dict):
                prompt=contract['definition']['chain']['steps'][0]['input']['text']
                self.assertLessEqual(len(prompt),8192,role)
    def test_complete_fixture_in_attested_python_only_closure(self):
        try:from devtools.isolated_adapter_runner import _materialized_adapter,_sha256
        except ImportError:self.skipTest('real SDK isolation mechanism unavailable in stubs')
        module=ROOT/'nusaibah_pharma_company_intelligence_lab_v0_1_34_adapter.py'
        from isolation_support import fixture_support_files
        config={'module_hash':_sha256(module),
            'support_files':[{'path':str(p),'sha256':_sha256(p)}
                for p in fixture_support_files(module, 'test_automatic_enrichment_v0_1_27')]}
        with _materialized_adapter(module,config) as isolated:
            shutil.copytree(ROOT/'tests',isolated.parent/'tests',ignore=shutil.ignore_patterns('__pycache__','stubs'))
            script=isolated.parent/'closure_fixture.py';script.write_text(RUNNER,encoding='utf-8')
            result=subprocess.run([sys.executable,'-I',str(script),str(isolated.parent)],capture_output=True,text=True,encoding='utf-8',timeout=40)
            self.assertEqual(0,result.returncode,result.stderr[-3000:])
            proof=json.loads(result.stdout)
            self.assertTrue(proof['fixture_publication_complete']);self.assertFalse(proof['json_manifest_present'])

if __name__=='__main__':unittest.main()
