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

    def test_only_the_evaluation_wrapper_is_a_discoverable_adapter(self) -> None:
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
assert found == [('nusaibah.pharma_company_intelligence_lab_evaluation', '0.1.0')], found
frozen = importlib.import_module('{PACKAGE}.frozen_pharma_company_intelligence_lab')
assert not issubclass(frozen.NusaibahPharmaCompanyIntelligenceLabAdapter, Adapter)
""")

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
        current = evaluation["versions"]["0.1.0"]
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


if __name__ == "__main__":
    unittest.main()
