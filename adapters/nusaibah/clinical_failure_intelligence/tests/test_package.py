"""Declared-file closure tests; Adapter is explicitly stubbed for imports only."""
import ast
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from fakes import ASSET_ROOT, FakeInputs, example_inputs
from clinical_failure_intelligence.contracts import canonical_bytes
from clinical_failure_intelligence.orchestration import run_analysis
from clinical_failure_intelligence import prompt_catalog
try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None


def declaration():
    """Read only the strict scalar/block YAML convention used by this package."""
    values = {}; current = None
    for line in (ASSET_ROOT / 'adapter.yaml').read_text().splitlines():
        if line and not line[0].isspace():
            key, _, value = line.partition(':'); current = key; values[key] = value.strip()
        elif line.startswith('  - '):
            if not isinstance(values[current], list): values[current] = []
            values[current].append(line[4:])
    return values


class PackageTests(unittest.TestCase):
    def test_declared_python_closure_complete(self):
        meta = declaration()
        self.assertEqual(sorted(p.name for p in ASSET_ROOT.glob('*.py')), sorted(meta['reviewed_helpers'] + [meta['adapter_module']]))
        self.assertTrue(all('/' not in name for key in ('reviewed_helpers', 'reviewed_support_files', 'optional_files') for name in meta[key]))
        self.assertTrue(all(name.endswith('.json') for name in meta['reviewed_support_files']))
        for key in ('reviewed_helpers', 'reviewed_support_files', 'optional_files'):
            for name in meta[key]: self.assertTrue((ASSET_ROOT / name).is_file(), name)
    def test_manifest_identity_and_binding_ownership(self):
        data = json.loads((ASSET_ROOT / 'clinical_failure_intelligence.asset.json').read_text()); meta = declaration()
        self.assertEqual(data['key'], meta['asset_key']); self.assertEqual(data['default'], meta['asset_version'])
        version = data['versions']['0.1.2']; self.assertEqual('binding', version['inputs']['clinical_context']['source'])
        self.assertEqual({'profiles': ['reference_read'], 'modes': ['http']}, version['public_web'])
        self.assertEqual({'product_memory'}, set(version['runtime_skills']))
        role = version['runtime_skills']['product_memory']
        self.assertEqual({'lake_ref': 'test_database_lake', 'node_key': 'clinical_product_memory_packages'}, role['source'])
        self.assertEqual('read_only', role['mutation'])
        self.assertEqual('current', role['resolution'])
        self.assertEqual({'product_id': {'from_variable': 'product_id'}}, role['partition'])
        self.assertNotIn('product_memory_update', version['runtime_skills'])
        self.assertFalse(version['outputs']['clinical_intelligence_records']['required'])
        self.assertEqual('dlm_file_artifact_output', version['output_contracts']['clinical_intelligence_records']['target_kind'])
        self.assertEqual('dry_run', version['output_contracts']['clinical_intelligence_records']['write_mode'])
        self.assertNotIn('callable_assets', version)
        self.assertEqual(['local_worker', 'ecs'], data['execution']['allowed_substrates'])
        self.assertEqual(['local_worker', 'ecs'], version['execution']['allowed_substrates'])
        self.assertEqual('local_worker', version['execution']['default_substrate'])
    def test_role_references_and_prompt_hashes(self):
        data = json.loads((ASSET_ROOT / 'admission_requirements.json').read_text())
        for row in data['agent_contracts']:
            prompt = (ASSET_ROOT / row['prompt_file']).read_text()
            self.assertEqual(prompt, prompt_catalog.PROMPTS[row['role']])
            sha = 'sha256:' + hashlib.sha256((prompt_catalog.COMMON_PROMPT + '\n\n' + prompt).encode()).hexdigest()
            self.assertEqual(sha, row['prompt_digest']); self.assertEqual('not_admitted', row['role_admission_status'])
    def test_fixed_skill_exact_bytes_digest(self):
        skill = ASSET_ROOT / 'skills/clinical-failure-methodology'
        entries = [{'path': p.relative_to(skill).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in sorted(skill.rglob('*')) if p.is_file()]
        sha = 'sha256:' + hashlib.sha256(canonical_bytes(entries)).hexdigest()
        manifest = json.loads((ASSET_ROOT / 'clinical_failure_intelligence.asset.json').read_text())
        self.assertEqual(sha, manifest['versions']['0.1.2']['skills'][0]['digest'])
    def test_source_seed_indices_are_not_gold_verdicts(self):
        seeds = json.loads((ASSET_ROOT / 'tests/reference/source_hypothesis_catalog.json').read_text())
        self.assertEqual(13, len(seeds)); self.assertTrue(all(x['verdict'] == 'untested' for x in seeds))
        self.assertEqual(8, sum(x['analysis_mode'] == 'mechanistic_case' for x in seeds))
    def test_python_310_grammar(self):
        for path in ASSET_ROOT.rglob('*.py'):
            ast.parse(path.read_text(encoding='utf8'), filename=str(path), feature_version=(3, 10))
    def test_no_pharma_or_provider_transport_dependency(self):
        for path in ASSET_ROOT.glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom): self.assertNotIn('pharma_company', node.module or '')
                if isinstance(node, ast.Import):
                    for name in node.names:
                        self.assertNotIn(name.name.split('.')[0], {'requests', 'httpx', 'boto3', 'botocore', 'socket'})
    def test_isolated_flat_and_package_import_base_stub(self):
        meta = declaration()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); package = root / 'clinical_failure_intelligence'; package.mkdir()
            for name in meta['reviewed_helpers'] + meta['reviewed_support_files'] + meta['optional_files'] + [meta['adapter_module']]:
                target = package / name; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ASSET_ROOT / name, target)
            # This proves source closure, NOT the official runtime base or worker.
            script = """import sys,types,importlib
sys.path.insert(0,sys.argv[1])
a=types.ModuleType('adapters');a.__path__=[]
b=types.ModuleType('adapters.base');b.Adapter=type('Adapter',(),{})
sys.modules['adapters']=a;sys.modules['adapters.base']=b
m=importlib.import_module(sys.argv[2])
classes=[x for x in vars(m).values() if isinstance(x,type) and getattr(x,'key',None)=='nusaibah.clinical_failure_intelligence']
assert len(classes)==1 and classes[0].version=='0.1.3'
print('declared_import_closure_passed')
"""
            for package_mode in (True, False):
                entry = Path(meta['adapter_module']).stem
                name = 'clinical_failure_intelligence.' + entry if package_mode else entry
                completed = subprocess.run([sys.executable, '-I', '-c', script, str(root if package_mode else package), name],
                                           capture_output=True, text=True, encoding='utf8', timeout=20)
                self.assertEqual(0, completed.returncode, completed.stderr)
    def test_python_closure_imports_without_development_prose(self):
        meta = declaration()
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / 'clinical_failure_intelligence'
            package.mkdir()
            for name in meta['reviewed_helpers'] + [meta['adapter_module']]:
                shutil.copyfile(ASSET_ROOT / name, package / name)
            script = """import sys,types,importlib
sys.path.insert(0,sys.argv[1])
a=types.ModuleType('adapters');a.__path__=[]
b=types.ModuleType('adapters.base');b.Adapter=type('Adapter',(),{})
sys.modules['adapters']=a;sys.modules['adapters.base']=b
m=importlib.import_module('clinical_failure_intelligence.clinical_failure_intelligence_v0_1_3_adapter')
assert m.ClinicalFailureIntelligenceAdapter.version=='0.1.3'
"""
            completed = subprocess.run([sys.executable, '-I', '-B', '-c', script, temporary],
                                       capture_output=True, text=True, encoding='utf8', timeout=20)
            self.assertEqual(0, completed.returncode, completed.stderr)
    def test_prompt_catalog_is_reproducible(self):
        completed = subprocess.run([sys.executable, '-I', '-B', str(ASSET_ROOT / 'tests/build_prompt_catalog.py'), '--check'],
                                   capture_output=True, text=True, encoding='utf8', timeout=20)
        self.assertEqual(0, completed.returncode, completed.stderr)
    def test_development_fixtures_are_not_runtime_files(self):
        self.assertFalse((ASSET_ROOT / 'fixtures').exists())
        self.assertEqual({'mechanistic_case.json', 'cohort_pattern.json', 'prepared_evidence_preflight.json'},
                         {p.name for p in (ASSET_ROOT / 'tests/fixtures').glob('*.json')})
    @unittest.skipUnless(Draft202012Validator, 'jsonschema is not installed')
    def test_schemas_validate_fixture_results(self):
        request = json.loads((ASSET_ROOT / 'tests/reference/analysis_request.v1.schema.json').read_text())
        output = json.loads((ASSET_ROOT / 'tests/reference/clinical_intelligence.v1.schema.json').read_text())
        Draft202012Validator.check_schema(request); Draft202012Validator.check_schema(output)
        for mode in ('mechanistic_case', 'cohort_pattern'):
            data = example_inputs(mode); Draft202012Validator(request).validate(data)
            value = run_analysis(FakeInputs(data))['outputs']['clinical_intelligence']; Draft202012Validator(output).validate(value)
    @unittest.skipUnless(Draft202012Validator, 'jsonschema is not installed')
    def test_schema_rejects_false_verification_and_writes(self):
        schema = json.loads((ASSET_ROOT / 'tests/reference/clinical_intelligence.v1.schema.json').read_text())
        value = run_analysis(FakeInputs())['outputs']['clinical_intelligence']; value['quality']['external_truth_verified'] = True
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(value)))
        value['quality']['external_truth_verified'] = False; value['memory_update']['write_attempted'] = True
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(value)))


if __name__ == '__main__': unittest.main()
