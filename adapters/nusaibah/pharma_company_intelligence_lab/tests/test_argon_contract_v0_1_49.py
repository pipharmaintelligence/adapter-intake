"""Model migration preserves task meaning, authority and bounded execution."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ArgonContractTests(unittest.TestCase):
    def test_only_pro_roles_change_model_and_receive_new_contract_versions(self):
        manifest = json.loads((ROOT / 'nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        previous = manifest['versions']['0.1.48']
        current = deepcopy(manifest['versions']['0.1.49'])
        for role, version in (('strategic_analyst', '1.0.9'), ('evidence_critic', '1.0.16')):
            agent = current['agents'][role]
            self.assertEqual(version, agent['contract_version'])
            self.assertEqual(version, agent['definition']['chain']['version'])
            policy = agent['definition']['chain']['steps'][0]['provider_policy']
            self.assertEqual('gemini-4-argon', policy['model'])
            self.assertEqual('global', policy['provider_vault']['execution_location'])
            self.assertEqual({'max_tokens': 32000, 'thinking_level': 'high', 'response_format': 'json_object'},
                             policy['generation_policy'])
            old = previous['agents'][role]
            agent['contract_version'] = old['contract_version']
            agent['definition']['chain']['version'] = old['definition']['chain']['version']
            policy['model'] = old['definition']['chain']['steps'][0]['provider_policy']['model']
        # Prompts, scopes, tools, role count, budgets and unchanged contracts are identical.
        self.assertEqual(previous, current)

    def test_declared_runtime_floor_covers_argon_and_auth_failover(self):
        dependencies = json.loads((ROOT / 'adapter.dependencies.json').read_text())
        minimum = tuple(map(int, dependencies['runtime_package']['minimum_version'].split('.')))
        self.assertGreaterEqual(minimum, (0, 1, 110))


if __name__ == '__main__':
    unittest.main()
