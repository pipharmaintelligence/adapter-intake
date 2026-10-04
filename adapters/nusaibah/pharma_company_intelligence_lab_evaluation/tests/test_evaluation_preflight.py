from __future__ import annotations

import json
from pathlib import Path
import unittest

import test_evaluation_packaging as packaging
PACKAGE = packaging.PACKAGE

_ROOT = Path(__file__).resolve().parents[1]


class EvaluationPreflightTests(unittest.TestCase):
    _packaged_probe = packaging.EvaluationPackagingTests._packaged_probe
    def test_purpose_is_required_and_positive_web_smoke_is_blocked_without_calls(self):
        self._packaged_probe(f"""
from unittest.mock import patch
from {PACKAGE} import evaluation_preflight as preflight
from {PACKAGE}.nusaibah_pharma_company_intelligence_lab_evaluation_v0_1_2_adapter import NusaibahPharmaCompanyIntelligenceLabEvaluationV012Adapter as Evaluation
from {PACKAGE} import evaluation_replay as replay
case={{'case_id':'company-small-identity-001','mode':'company_research','source_units':[{{'locator':'company:1','text':'Fictional company evidence.','quality_flags':[]}}]}}
for purpose, rule in [(None, 'execution_purpose_required'), ('positive_web_smoke', 'positive_web_smoke_requires_separate_admission')]:
    variables={{'case_index':0}}
    if purpose: variables['execution_purpose']=purpose
    inputs={{'evaluation_case':{{'records':[case]}},'variables':variables}}
    with patch.object(replay.NusaibahPharmaCompanyIntelligenceLabAdapter, 'invoke') as frozen:
        report=preflight.preflight_inputs(inputs)
        assert report['projection_compatible'] is True
        assert report['execution_allowed'] is False
        assert report['positive_web_smoke_eligible'] is False
        assert rule in report['reason_codes']
        try: Evaluation().invoke(inputs, {{}})
        except preflight.EvaluationPreflightError as error:
            assert error.failure_code == 'pharma_evaluation_preflight_rejected'
            assert error.proof_failure_detail['stage'] == 'evaluation_preflight'
            assert error.proof_failure_detail['rule'] == rule
        else: raise AssertionError('Unexpected provider execution')
        frozen.assert_not_called()
""")

    def test_explicit_diagnostic_replay_preserves_success_and_quality_rejection(self):
        self._packaged_probe(f"""
from unittest.mock import patch
from {PACKAGE} import evaluation_preflight as preflight
from {PACKAGE}.nusaibah_pharma_company_intelligence_lab_evaluation_v0_1_2_adapter import NusaibahPharmaCompanyIntelligenceLabEvaluationV012Adapter as Evaluation
from {PACKAGE} import evaluation_replay as replay
from {PACKAGE} import frozen_pharma_company_intelligence_lab as frozen
from {PACKAGE}.evaluation_failure import EvaluationFailure
case={{'case_id':'company-small-identity-001','mode':'company_research','source_units':[{{'locator':'company:1','text':'Fictional company evidence.','quality_flags':[]}}]}}
inputs={{'evaluation_case':{{'records':[case]}},'variables':{{'case_index':0,'execution_purpose':'diagnostic_baseline_replay'}}}}
report=preflight.preflight_inputs(inputs)
assert report['execution_allowed'] is True
assert report['positive_web_smoke_eligible'] is False
with patch.object(replay.NusaibahPharmaCompanyIntelligenceLabAdapter,'invoke',return_value={{'status':'success','outputs':{{}}}}) as invoke:
    result=Evaluation().invoke(inputs,{{}})
    assert result['status']=='success'
    assert result['outputs']['evaluation_result']['execution_preflight']==report
    assert invoke.call_count==1
    assert invoke.call_args.args[0]['variables']['memory_mode']=='preview'
    assert invoke.call_args.args[0]['variables']['publish_dossier'] is False
def reject(*args):
    evidence={{role:{{'_citations':[]}} for role in frozen.RESEARCH_ROLES}}
    frozen._require_pre_synthesis_quality(evidence,{{'recommendation':'pass'}})
with patch.object(replay.NusaibahPharmaCompanyIntelligenceLabAdapter,'invoke',side_effect=reject):
    try: Evaluation().invoke(inputs,{{}})
    except EvaluationFailure as error:
        assert error.code=='pharma_evaluation_quality_rejected'
        assert error.proof_failure_detail['rule']=='research_citations_missing'
    else: raise AssertionError('Quality rejection became success')
""")

    def test_preflight_rejects_truth_authority_urls_and_unbounded_inputs(self):
        self._packaged_probe(f"""
import copy, json
from {PACKAGE} import evaluation_preflight as preflight
case={{'case_id':'company-small-identity-001','mode':'company_research','source_units':[{{'locator':'company:1','text':'Fictional company evidence.','quality_flags':[]}}]}}
valid={{'evaluation_case':{{'records':[case]}},'variables':{{'case_index':0,'execution_purpose':'diagnostic_baseline_replay'}}}}
bad=[]
for key in ('candidate_expected_findings','reviewer','provider_ref','research_target'):
    value=copy.deepcopy(valid); value['evaluation_case']['records'][0][key]='private'; bad.append(value)
value=copy.deepcopy(valid); value['evaluation_case']['records'][0]['source_units'][0]['expected_answer']='private'; bad.append(value)
value=copy.deepcopy(valid); value['evaluation_case']['records'][0]['source_units'][0]['locator']='https://private.test'; bad.append(value)
value=copy.deepcopy(valid); value['evaluation_case']['records'][0]['source_units']*=15; bad.append(value)
value=copy.deepcopy(valid); value['variables']['case_index']=24; bad.append(value)
value=copy.deepcopy(valid); value['evaluation_case']['records'][0]['source_units'][0]['text']='x'*4001; bad.append(value)
value=copy.deepcopy(valid); value['evaluation_case']['records'][0]['mode']='document_review'; bad.append(value)
value=copy.deepcopy(valid); value['credentials']='private'; bad.append(value)
value=copy.deepcopy(valid); value['variables']['execution_purpose']={{'private':True}}; bad.append(value)
for value in bad:
    report=preflight.preflight_inputs(value)
    assert report['execution_allowed'] is False
    assert report['provider_calls']==0
    assert 'private' not in json.dumps(report)
assert preflight.preflight_inputs(valid,purpose='positive_web_smoke')['execution_allowed'] is False
""")

    def test_previous_wrapper_bytes_and_frozen_semantics_are_retained(self):
        # Inherited packaging tests check baseline AST, helper and policy parity.
        self.assertIn("version: ClassVar[str] = \"0.1.1\"",
                      (_ROOT / "nusaibah_pharma_company_intelligence_lab_evaluation_v0_1_1_adapter.py").read_text())

if __name__ == "__main__":
    unittest.main()
