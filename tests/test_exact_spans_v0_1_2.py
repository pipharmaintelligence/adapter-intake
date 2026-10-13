import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'adapters/nusaibah'
sys.path.insert(0,str(ROOT))
from structured_review_toolkit.tool_operations_v0_1_2 import execute_operation
from structured_review_toolkit.tool_operations_v0_1_1 import execute_operation as historical
from structured_review_toolkit.source_chunks import stable_digest

def request(text):
    material={'entity_id':'company:14','snapshot_id':'snapshot:bounded',
        'source_units':[{'locator':'source:1','entity_id':'company:14','text':text,'accessible':True}]}
    return {'schema_version':'review_tool_request.v1','operation':'resolve_exact_spans',
        'arguments':{**material,'source_digest':stable_digest(material),
            'requests':[{'request_id':'quote:1','locator':'source:1','quote':'UNIQUE'}]}}

class ExactSpanBudgetTests(unittest.TestCase):
    def test_large_atomic_unit_and_original_offsets_are_verified(self):
        text='a'*59995+'UNIQUE';text=text[:60000-6]+'UNIQUE'
        value=execute_operation(request(text));span=value['output']['spans'][0]
        self.assertEqual((59994,60000),(span['start'],span['end']))
        self.assertEqual(0,value['agent_call_count']);self.assertEqual(0,value['mutable_call_count'])
    def test_historical_unit_limit_is_unchanged(self):
        with self.assertRaises(ValueError):historical(request('a'*7193+'UNIQUE'))
        self.assertEqual('resolved',execute_operation(request('a'*7193+'UNIQUE'))['output']['status'])
    def test_oversized_unit_and_request_are_rejected(self):
        with self.assertRaises(ValueError):execute_operation(request('a'*60001+'UNIQUE'))
        r=request('漢'*59994+'UNIQUE')
        r['arguments']['source_units'].append({**r['arguments']['source_units'][0],'locator':'source:2'})
        r['arguments']['source_digest']=stable_digest({k:r['arguments'][k] for k in ('entity_id','snapshot_id','source_units')})
        with self.assertRaises(ValueError):execute_operation(r)
    def test_multiple_units_cannot_exceed_total_character_budget(self):
        r=request('a'*60000);u=r['arguments']['source_units'][0]
        r['arguments']['source_units']=[{**u,'locator':str(i)} for i in range(3)]
        r['arguments']['source_digest']=stable_digest({k:r['arguments'][k] for k in ('entity_id','snapshot_id','source_units')})
        with self.assertRaises(ValueError):execute_operation(r)
    def test_real_isolated_child_accepts_long_source_without_provider_calls(self):
        try:
            from devtools.asset_dependency_runtime import invoke_adapter_module
            from adapters.runtime_catalog import canonical_source_hash
        except ImportError:self.skipTest('real isolated runtime unavailable in stubs')
        root=ROOT/'structured_review_toolkit'
        module=root/'structured_review_toolkit_v0_1_2_adapter.py'
        value=invoke_adapter_module(sys.executable,adapter_id='nusaibah.structured_review_toolkit:0.1.2',
            adapter_module=module,inputs={'variables':request('a'*7193+'UNIQUE')},context={},
            execution_timeout_seconds=20,module_hash=canonical_source_hash(module),
            support_files=tuple((p,canonical_source_hash(p)) for p in root.glob('*.py') if p!=module))
        self.assertEqual('resolved',value['outputs']['tool_result']['output']['status'])
        self.assertEqual(0,value['metrics']['agent_call_count'])
        self.assertEqual(0,value['metrics']['mutable_dynamic_skill_call_count'])
    def test_authority_fields_are_rejected(self):
        r=request('UNIQUE');r['arguments']['credential']='blocked'
        with self.assertRaises(ValueError):execute_operation(r)
