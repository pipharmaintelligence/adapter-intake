from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ASSET_ROOT = Path(__file__).resolve().parents[1]
BASELINE_ROOT = ASSET_ROOT.parent / "pharma_company_intelligence_lab"
STUB_ROOT = BASELINE_ROOT / "tests" / "stubs"
PINNED_BASELINE_SOURCE_SHA256 = "5f0e8779be4c81d208dc84e6640e8fc276cc359da9e8087f552611eacd1c8ffa"
BASELINE_CLASS = "NusaibahPharmaCompanyIntelligenceLabAdapter"
PACKAGE = "adapters.intake.nusaibah.pharma_company_intelligence_lab_evaluation"


class EvaluationPackagingTests(unittest.TestCase):
    def test_version_023_packaged_import_uses_scoped_engine_and_scalar_summary(self):
        self._packaged_probe(f"""
import importlib
import sys
from unittest.mock import patch
before = list(sys.path)
module = importlib.import_module('{PACKAGE}.nusaibah_pharma_company_intelligence_lab_evaluation_v0_2_3_adapter')
scoped = importlib.import_module('{PACKAGE}.supplied_source_scoped_review')
assert module.run_review is scoped.run_review
assert sys.path == before
assert module.NusaibahPharmaCompanyIntelligenceLabEvaluationV023Adapter.version == '0.2.3'
result = {{'review_outcome':'review_complete_with_evidence_gaps', 'agent_call_count':5,
  'mutable_call_count':0, 'child_call_count':1, 'execution_state':'completed',
  'preview_only':True, 'publication_allowed':False, 'baseline_comparable':False,
  'external_truth_verified':False, 'accepted_findings':[{{'statement':'private evidence'}}],
  'withheld_findings':[], 'plan':{{'chunk_ids':['chunk-1']}}}}
with patch.object(module, 'run_review', return_value=result):
    response = module.NusaibahPharmaCompanyIntelligenceLabEvaluationV023Adapter().invoke({{}}, {{}})
summary = response['outputs']['evaluation_summary']
assert summary['schema_version'] == 'pharma_supplied_source_review_summary.v2'
assert summary['agent_call_count'] == 5 and summary['child_call_count'] == 1
assert all(isinstance(value, (str, bool, int)) for value in summary.values())
assert 'private' not in str(summary)
assert response['outputs']['evaluation_result'] is result
""")

    def test_version_023_changes_only_ownership_prompts_and_agent_versions(self):
        import copy
        manifest = json.loads((ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab_evaluation.asset.json").read_text())
        old, new = manifest["versions"]["0.2.2"], manifest["versions"]["0.2.3"]
        self.assertEqual({k: v for k, v in old.items() if k != "agents"},
                         {k: v for k, v in new.items() if k != "agents"})
        self.assertEqual(old["agents"]["source_regulatory_reviewer"], new["agents"]["source_regulatory_reviewer"])
        for role, version in (("source_portfolio_reviewer", "1.2.0"),
                              ("source_commercial_reviewer", "1.2.0"),
                              ("source_evidence_verifier", "1.1.0")):
            actual = copy.deepcopy(new["agents"][role])
            expected = old["agents"][role]
            self.assertEqual(version, actual["contract_version"])
            self.assertEqual(version, actual["definition"]["chain"]["version"])
            self.assertIn("requirement_scopes", actual["definition"]["chain"]["steps"][0]["input"]["text"])
            actual["contract_version"] = expected["contract_version"]
            actual["definition"]["chain"]["version"] = expected["definition"]["chain"]["version"]
            actual["definition"]["chain"]["steps"][0]["input"] = expected["definition"]["chain"]["steps"][0]["input"]
            self.assertEqual(expected, actual)

    def test_version_023_promotion_declares_all_new_helpers_and_retains_022_wrapper(self):
        contract = (ASSET_ROOT / "adapter.yaml").read_text(encoding="utf-8")
        self.assertIn("asset_version: 0.2.3", contract)
        self.assertIn("  - COMMERCIAL_ROLE_SCOPE.md\n", contract)
        for filename in ("quote_review_orchestration.py", "supplied_source_scoped_review.py",
                         "nusaibah_pharma_company_intelligence_lab_evaluation_v0_2_2_adapter.py"):
            self.assertEqual(1, contract.count("  - " + filename + "\n"))
        self.assertIn("adapter_module: nusaibah_pharma_company_intelligence_lab_evaluation_v0_2_3_adapter.py", contract)

    def test_version_022_package_import_and_bounded_summary_preserve_source_separation(self):
        self._packaged_probe(f"""
import importlib
import sys
from unittest.mock import patch
before = list(sys.path)
module = importlib.import_module('{PACKAGE}.nusaibah_pharma_company_intelligence_lab_evaluation_v0_2_2_adapter')
engine = importlib.import_module('{PACKAGE}.supplied_source_quote_review')
assert module.run_review is engine.run_review
assert sys.path == before
result = {{'review_outcome':'review_complete_with_evidence_gaps', 'agent_call_count':4,
  'mutable_call_count':0, 'child_call_count':1, 'execution_state':'completed',
  'preview_only':True, 'publication_allowed':False, 'baseline_comparable':False,
  'external_truth_verified':False, 'accepted_findings':[{{'statement':'private source'}}],
  'withheld_findings':[], 'plan':{{'chunk_ids':['chunk-1']}}}}
with patch.object(module, 'run_review', return_value=result):
    response = module.NusaibahPharmaCompanyIntelligenceLabEvaluationV022Adapter().invoke({{}}, {{}})
summary = response['outputs']['evaluation_summary']
assert summary['schema_version'] == 'pharma_supplied_source_review_summary.v2'
assert summary['child_call_count'] == 1 and summary['agent_call_count'] == 4
assert all(isinstance(value, (str, bool, int)) for value in summary.values())
assert 'private' not in str(summary)
assert response['outputs']['evaluation_result'] is result
""")

    def test_version_022_pins_child_and_changes_only_specialist_chain_version_and_quote_prompt(self):
        manifest = json.loads((ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab_evaluation.asset.json").read_text())
        old = manifest["versions"]["0.2.1"]
        new = manifest["versions"]["0.2.2"]
        self.assertEqual({key: value for key, value in old.items() if key != "agents"},
                         {key: value for key, value in new.items() if key not in {"agents", "callable_assets"}})
        self.assertEqual(new["callable_assets"]["review_toolkit"], {
            "asset_key": "nusaibah.structured_review_toolkit", "asset_version": "0.1.1",
            "result_key": "tool_result", "result_shape": "object"})
        self.assertEqual(old["agents"]["source_evidence_verifier"], new["agents"]["source_evidence_verifier"])
        import copy
        for role in ("source_portfolio_reviewer", "source_commercial_reviewer", "source_regulatory_reviewer"):
            actual = copy.deepcopy(new["agents"][role])
            self.assertEqual("1.1.0", actual["contract_version"])
            self.assertEqual("1.1.0", actual["definition"]["chain"]["version"])
            prompt = actual["definition"]["chain"]["steps"][0]["input"]["text"]
            self.assertIn("Do not return start/end offsets", prompt)
            expected = old["agents"][role]
            actual["contract_version"] = expected["contract_version"]
            actual["definition"]["chain"]["version"] = expected["definition"]["chain"]["version"]
            actual["definition"]["chain"]["steps"][0]["input"] = expected["definition"]["chain"]["steps"][0]["input"]
            self.assertEqual(expected, actual)

    def _packaged_probe(self, code: str) -> None:
        # Reproduce the materialized namespace without putting the asset folder
        # on sys.path. Runtime stubs provide only import-time public contracts.
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory)
            shutil.copytree(STUB_ROOT / "adapters", runtime_root / "adapters",
                            ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(STUB_ROOT / "devtools", runtime_root / "devtools",
                            ignore=shutil.ignore_patterns("__pycache__"))
            packaged_asset = runtime_root / "adapters/intake/nusaibah/pharma_company_intelligence_lab_evaluation"
            packaged_asset.mkdir(parents=True)
            for folder in [packaged_asset, packaged_asset.parent, packaged_asset.parent.parent]:
                (folder / "__init__.py").write_text("", encoding="utf-8")
            for source in ASSET_ROOT.glob("*.py"):
                shutil.copy2(source, packaged_asset / source.name)
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [sys.executable, "-c", code], cwd=runtime_root, env=env,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_packaged_imports_do_not_change_sys_path(self) -> None:
        self._packaged_probe(f"""
import importlib
import sys
before = list(sys.path)
replay = importlib.import_module('{PACKAGE}.evaluation_replay')
wrapper = importlib.import_module('{PACKAGE}.nusaibah_pharma_company_intelligence_lab_evaluation_adapter')
assert replay.BASELINE_ASSET_VERSION == '0.1.12'
assert wrapper.NusaibahPharmaCompanyIntelligenceLabEvaluationAdapter.version == '0.1.0'
assert sys.path == before, 'Package import leaked an asset-directory path'
""")

    def test_only_the_versioned_evaluation_wrappers_are_discoverable_adapters(self) -> None:
        self._packaged_probe(f"""
import importlib
import inspect
import pkgutil
from adapters.base import Adapter
package = importlib.import_module('{PACKAGE}')
found = []
for item in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
    module = importlib.import_module(item.name)
    for _, candidate in inspect.getmembers(module, inspect.isclass):
        if candidate is not Adapter and issubclass(candidate, Adapter) and candidate.__module__ == module.__name__:
            found.append((candidate.key, candidate.version))
assert sorted(found) == [('nusaibah.pharma_company_intelligence_lab_evaluation', '0.1.0'), ('nusaibah.pharma_company_intelligence_lab_evaluation', '0.1.1'), ('nusaibah.pharma_company_intelligence_lab_evaluation', '0.1.2'), ('nusaibah.pharma_company_intelligence_lab_evaluation', '0.2.0'), ('nusaibah.pharma_company_intelligence_lab_evaluation', '0.2.1'), ('nusaibah.pharma_company_intelligence_lab_evaluation', '0.2.2'), ('nusaibah.pharma_company_intelligence_lab_evaluation', '0.2.3')], found
frozen = importlib.import_module('{PACKAGE}.frozen_pharma_company_intelligence_lab')
assert not issubclass(frozen.NusaibahPharmaCompanyIntelligenceLabAdapter, Adapter)
""")

    def test_version_021_exports_only_bounded_scalar_summary_and_reuses_review_engine(self) -> None:
        self._packaged_probe(f"""
import importlib
from unittest.mock import patch
module = importlib.import_module('{PACKAGE}.nusaibah_pharma_company_intelligence_lab_evaluation_v0_2_1_adapter')
engine = importlib.import_module('{PACKAGE}.supplied_source_review')
assert module.run_review is engine.run_review
assert module.NusaibahPharmaCompanyIntelligenceLabEvaluationV021Adapter.version == '0.2.1'
for outcome, calls in [('review_complete', 5), ('review_complete_with_evidence_gaps', 4)]:
    result = {{'review_outcome':outcome, 'agent_call_count':calls, 'mutable_call_count':0,
      'execution_state':'completed', 'preview_only':True, 'publication_allowed':False,
      'baseline_comparable':False, 'external_truth_verified':False,
      'accepted_findings':[{{'statement':'private source quote'}}], 'withheld_findings':[],
      'plan':{{'chunk_ids':['chunk-1']}}, 'source_inventory':[{{'text':'private source text'}}]}}
    with patch.object(module, 'run_review', return_value=result) as review:
        response = module.NusaibahPharmaCompanyIntelligenceLabEvaluationV021Adapter().invoke({{}}, {{}})
        review.assert_called_once()
    assert response['outputs']['evaluation_result'] is result
    summary = response['outputs']['evaluation_summary']
    assert summary['review_outcome'] == outcome and summary['agent_call_count'] == calls
    assert summary['mutable_call_count'] == 0 and summary['publication_allowed'] is False
    assert summary['accepted_finding_count'] == 1
    assert all(isinstance(v, (str, bool, int)) for v in summary.values())
    assert 'private' not in str(summary)
""")

    def test_version_021_preserves_all_review_execution_contracts(self) -> None:
        manifest = json.loads((ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab_evaluation.asset.json").read_text())
        old = manifest["versions"]["0.2.0"]
        new = dict(manifest["versions"]["0.2.1"])
        outputs = dict(new["outputs"])
        self.assertEqual(outputs.pop("evaluation_summary"), {"required": True, "shape": "object"})
        new["outputs"] = outputs
        self.assertEqual(old, new)

    def test_frozen_business_ast_matches_pinned_baseline_with_only_registration_removed(self) -> None:
        baseline_source = (BASELINE_ROOT / "nusaibah_pharma_company_intelligence_lab_adapter.py").read_text(encoding="utf-8")
        self.assertEqual(hashlib.sha256(baseline_source.encode()).hexdigest(), PINNED_BASELINE_SOURCE_SHA256)
        expected = ast.parse(baseline_source)
        expected.body = [
            node for node in expected.body
            if not (isinstance(node, ast.ImportFrom) and node.module == "adapters.base"
                    and [(item.name, item.asname) for item in node.names] == [("Adapter", None)])
        ]
        classes = [node for node in expected.body if isinstance(node, ast.ClassDef) and node.name == BASELINE_CLASS]
        self.assertEqual(len(classes), 1)
        self.assertEqual(ast.dump(classes[0].bases[0]), "Name(id='Adapter', ctx=Load())")
        classes[0].bases = []
        actual = ast.parse((ASSET_ROOT / "frozen_pharma_company_intelligence_lab.py").read_text(encoding="utf-8"))
        self.assertEqual(ast.dump(actual, include_attributes=False), ast.dump(expected, include_attributes=False))

    def test_frozen_helper_contracts_match_the_baseline(self) -> None:
        for name in ["agent_contract.py", "dossier_contract.py", "input_contract.py", "memory_contract.py", "methodology_contract.py"]:
            with self.subTest(helper=name):
                self.assertEqual((ASSET_ROOT / name).read_text(encoding="utf-8"), (BASELINE_ROOT / name).read_text(encoding="utf-8"))

    def test_evaluation_manifest_preserves_agent_policy_and_fixed_skill_parity(self) -> None:
        baseline = json.loads((BASELINE_ROOT / "nusaibah_pharma_company_intelligence_lab.asset.json").read_text(encoding="utf-8"))
        evaluation = json.loads((ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab_evaluation.asset.json").read_text(encoding="utf-8"))
        self.assertEqual(evaluation["default"], "0.2.3")
        self.assertEqual(evaluation["versions"]["0.1.2"], evaluation["versions"]["0.1.1"])
        self.assertEqual(evaluation["versions"]["0.1.1"], evaluation["versions"]["0.1.0"])
        current = evaluation["versions"]["0.1.1"]
        proven = baseline["versions"]["0.1.12"]
        self.assertEqual(current["agents"], proven["agents"])
        self.assertEqual(current["published_skills"], proven["published_skills"])
        self.assertEqual(evaluation["execution"]["timeout_seconds"], baseline["execution"]["timeout_seconds"])
        self.assertEqual(evaluation["execution"]["default_substrate"], "local_worker")
        self.assertEqual(evaluation["execution"]["allowed_substrates"], ["local_worker"])
        self.assertEqual(set(current["inputs"]), {"evaluation_case", "variables"})
        self.assertNotIn("dynamic_skills", current)
        self.assertNotIn("tools", current)

    def test_evaluation_input_rejects_truth_and_document_mode_before_dispatch(self) -> None:
        self._packaged_probe(f"""
from {PACKAGE}.nusaibah_pharma_company_intelligence_lab_evaluation_adapter import NusaibahPharmaCompanyIntelligenceLabEvaluationAdapter as Evaluation
from {PACKAGE}.evaluation_replay import BaselineReplayError
case = {{'case_id':'company-small-identity-001', 'mode':'company_research', 'source_units':[{{'locator':'section:1', 'text':'Synthetic company evidence.', 'quality_flags':[]}}]}}
for extra in ['candidate_expected_findings', 'criticality', 'reviewer', 'provider_ref']:
    bad = {{**case, extra:'forbidden'}}
    try:
        Evaluation._evaluation_case({{'evaluation_case':{{'records':[bad]}}}})
    except BaselineReplayError:
        pass
    else:
        raise AssertionError(extra)
try:
    Evaluation._evaluation_case({{'evaluation_case':{{'records':[{{**case, 'mode':'document_review'}}]}}}})
except BaselineReplayError:
    pass
else:
    raise AssertionError('Document mode must remain unsupported')
""")

    def test_replay_rejects_mutation_and_unpinned_skill(self) -> None:
        self._packaged_probe(f"""
from {PACKAGE}.evaluation_replay import EvaluationReplayInputs, BaselineReplayError, PINNED_METHODOLOGY_REF
case = {{'case_id':'company-small-identity-001', 'mode':'company_research', 'source_units':[{{'locator':'section:1', 'text':'Synthetic company evidence.', 'quality_flags':[]}}]}}
inputs = EvaluationReplayInputs(case=case, case_index=0, runtime_delegate=object())
for role in ['company_memory_update', 'company_methodology_update']:
    try:
        inputs.dynamic_skill(role, variables={{'company_id':'900001'}})
    except BaselineReplayError:
        pass
    else:
        raise AssertionError(role)
try:
    inputs.skill('another.methodology')
except BaselineReplayError:
    pass
else:
    raise AssertionError('Unpinned methodology must be rejected')
""")

    def test_evaluation_quality_rejections_keep_all_six_stop_rules(self) -> None:
        self._packaged_probe(f"""
from {PACKAGE} import evaluation_failure as diagnostics
from {PACKAGE} import frozen_pharma_company_intelligence_lab as frozen
research = {{role: {{'_citations': [{{}}]}} for role in frozen.RESEARCH_ROLES}}
critic = {{'recommendation': 'pass', 'citation_coverage': {{'status': 'sufficient'}}, 'unsupported_claim_ids': [], 'missing_section_ids': [], 'unmet_plan_requirements': []}}
cases = [
    ('research_citations_missing', {{**research, frozen.RESEARCH_ROLES[0]: {{'_citations': []}}}}, critic),
    ('critic_rejected', research, {{**critic, 'recommendation': 'fail'}}),
    ('citation_coverage_insufficient', research, {{**critic, 'citation_coverage': {{'status': 'insufficient'}}}}),
    ('unsupported_claims', research, {{**critic, 'unsupported_claim_ids': ['claim_1']}}),
    ('mandatory_sections_missing', research, {{**critic, 'missing_section_ids': ['section_1']}}),
    ('methodology_requirements_unsatisfied', research, {{**critic, 'unmet_plan_requirements': [{{'disposition': 'unsatisfied'}}]}}),
]
for rule, evidence, decision in cases:
    try:
        frozen._require_pre_synthesis_quality(evidence, decision)
    except RuntimeError as original:
        projected = diagnostics.project_baseline_failure(original)
        assert projected.code == 'pharma_evaluation_quality_rejected'
        assert projected.proof_failure_detail['stage'] == 'pre_synthesis_quality'
        assert projected.proof_failure_detail['rule'] == rule
        assert str(projected) == projected.code
    else:
        raise AssertionError('Frozen guard stopped rejecting: ' + rule)
frozen._require_pre_synthesis_quality(research, critic)
""")

    def test_evaluation_critic_validation_preserves_safe_rules_and_redacts_values(self) -> None:
        self._packaged_probe(f"""
from {PACKAGE} import agent_contract as contract
from {PACKAGE} import evaluation_failure as diagnostics
valid = {{'unsupported_claim_ids': [], 'stale_claim_ids': [], 'missing_section_ids': [], 'unmet_plan_requirements': [], 'recommendation': 'pass', 'citation_coverage': {{'status': 'sufficient', 'notes': ''}}}}
cases = [
    ('unknown_claim_id', {{**valid, 'unsupported_claim_ids': ['private_claim']}}),
    ('unknown_section_id', {{**valid, 'missing_section_ids': ['private_section']}}),
    ('unknown_requirement_id', {{**valid, 'unmet_plan_requirements': [{{'requirement_id': 'private_requirement', 'disposition': 'unsatisfied', 'notes': 'private_text'}}]}}),
    ('duplicate_requirement_id', {{**valid, 'unmet_plan_requirements': [{{'requirement_id': 'req_1', 'disposition': 'unsatisfied', 'notes': 'private_text'}}] * 2}}),
    ('disposition_invalid', {{**valid, 'unmet_plan_requirements': [{{'requirement_id': 'req_1', 'disposition': 'private_disposition', 'notes': 'private_text'}}]}}),
    ('recommendation_invalid', {{**valid, 'recommendation': 'private_decision'}}),
    ('coverage_status_invalid', {{**valid, 'citation_coverage': {{'status': 'private_status'}}}}),
    ('string_required', {{**valid, 'recommendation': 7}}),
    ('token_shape', {{**valid, 'recommendation': 'private token'}}),
    ('list_bound', {{**valid, 'unsupported_claim_ids': 'private_text'}}),
    ('duplicate_values', {{**valid, 'unsupported_claim_ids': ['claim_1', 'claim_1']}}),
]
for rule, payload in cases:
    try:
        contract.validate_critic_payload(payload, company_id=900001, known_claim_ids={{'claim_1'}}, known_section_ids={{'section_1'}}, known_plan_requirement_ids={{'req_1'}})
    except ValueError as original:
        projected = diagnostics.project_baseline_failure(original)
        assert projected.code == 'pharma_evaluation_critic_schema_invalid'
        assert projected.proof_failure_detail['stage'] == 'critic_validation'
        assert projected.proof_failure_detail['rule'] == rule
        assert 'private' not in str(projected.proof_failure_detail)
    else:
        raise AssertionError(rule)
""")

    def test_diagnostics_are_opt_in_and_do_not_change_success_or_unknown_errors(self) -> None:
        self._packaged_probe(f"""
from unittest.mock import patch
from {PACKAGE} import evaluation_replay as replay
from {PACKAGE} import evaluation_failure as diagnostics
from {PACKAGE} import frozen_pharma_company_intelligence_lab as frozen
case = {{'case_id': 'company-small-identity-001', 'mode': 'company_research', 'source_units': [{{'locator': 'section:1', 'text': 'Synthetic company evidence.', 'quality_flags': []}}]}}
expected = {{'status': 'success', 'outputs': {{'intelligence_dossier': {{}}}}}}
with patch.object(replay.NusaibahPharmaCompanyIntelligenceLabAdapter, 'invoke', return_value=expected) as invoke:
    old = replay.run_company_replay_case(case, case_index=0, runtime_delegate=object())
    new = replay.run_company_replay_case(case, case_index=0, runtime_delegate=object(), diagnostic_failures=True)
    assert old == new
    assert invoke.call_count == 2
def reject(*args):
    research = {{role: {{'_citations': [{{}}]}} for role in frozen.RESEARCH_ROLES}}
    frozen._require_pre_synthesis_quality(research, {{'recommendation': 'fail'}})
with patch.object(replay.NusaibahPharmaCompanyIntelligenceLabAdapter, 'invoke', side_effect=reject):
    for enabled in (False, True):
        try:
            replay.run_company_replay_case(case, case_index=0, runtime_delegate=object(), diagnostic_failures=enabled)
        except RuntimeError as error:
            assert isinstance(error, diagnostics.EvaluationFailure) is enabled
            if enabled:
                assert error.proof_failure_detail['rule'] == 'critic_rejected'
        else:
            raise AssertionError('A rejected review became successful')
for error in [RuntimeError('Evidence critic rejected the company evidence package.'), ValueError('Critic referenced an unknown claim_id.'), RuntimeError('private unclassified error')]:
    try:
        raise error
    except Exception as original:
        assert diagnostics.project_baseline_failure(original) is None
""")


if __name__ == "__main__":
    unittest.main()
