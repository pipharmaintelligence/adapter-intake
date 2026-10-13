import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from company_scope_selection_adapter import CompanyScopeSelectionAdapter
from scope_contract import CompanyScopeError

def inputs(rows):
    return {'variables':{'company_id':59},'companies':{'records':rows,'row_count':len(rows),
        'exactness':'exact','partial_reason':None,'provenance':{
            'source':'dlm_node','authority':'dlm_node','lake_id':'fixture','node_key':'companies','pages_read':1}}}

class SelectionTests(unittest.TestCase):
    def test_verified_empty_selection_is_not_found_without_agent_or_write(self):
        value=CompanyScopeSelectionAdapter().invoke(inputs([]),{})
        row=value['outputs']['company_scope_result']
        self.assertEqual('not_found',row['resolution']);self.assertEqual([59],row['missing_company_ids'])
        self.assertEqual([],row['records']);self.assertTrue(row['complete'])
        self.assertEqual(0,value['metrics']['agent_call_count'])
    def test_matching_corporate_one_record_preserves_dto(self):
        row=CompanyScopeSelectionAdapter().invoke(inputs([{'id':59,'company':'Fixture','corporate':1}]),{})['outputs']['company_scope_result']
        self.assertEqual('resolved',row['resolution']);self.assertEqual([],row['missing_company_ids'])
        self.assertEqual(1,row['records'][0]['corporate_id'])
    def test_partial_source_wrong_company_and_wrong_corporate_remain_errors(self):
        values=[inputs([{'id':60,'company':'Wrong','corporate':1}]),inputs([{'id':59,'company':'Wrong','corporate':2}])]
        partial=inputs([]);partial['companies']['exactness']='partial';values.append(partial)
        for value in values:
            with self.assertRaises(CompanyScopeError):CompanyScopeSelectionAdapter().invoke(value,{})
if __name__=='__main__':unittest.main()
