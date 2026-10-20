from copy import deepcopy
import hashlib
import json
import pytest
from fakes import ASSET_ROOT, FakeInputs, example_inputs
from clinical_failure_intelligence.evidence_v0_1_5 import EvidenceLedger
from clinical_failure_intelligence.contracts_v0_1_5 import text_digest
from clinical_failure_intelligence.policies_v0_1_5 import Budget
from clinical_failure_intelligence.orchestration_v0_1_5 import run_analysis


def fixture(text='α ≥ 5 μg 😀. The endpoint was not met.'):
    raw = example_inputs()['clinical_context']['evidence'][0]
    raw['text'] = text
    ledger = EvidenceLedger('CASE_SYN','2025-02-01',[raw])
    source = ledger.rows()[0]
    quote = 'The endpoint was not met.'
    row = {'claim_id':'C1', 'subject_id':'CASE_SYN','statement':'The primary endpoint was not met.',
        'claim_kind':'observation', 'supporting_evidence_ids':[source['evidence_id']], 'contradicting_evidence_ids':[],
        'source_spans':[{'evidence_id':source['evidence_id'], 'start':9999,'end':10000,
            'quote':quote,'text_digest':source['text_digest']}]}
    return ledger,row


@pytest.mark.parametrize('offsets', [(9999,10000), (0,4), (True,20), (-1,3), ('15','40')])
def test_unique_verbatim_unicode_quote_is_reanchored_without_changing_science(offsets):
    ledger,row = fixture()
    row['source_spans'][0].update(start=offsets[0],end=offsets[1])
    before = deepcopy(ledger.rows())
    valid,issues = ledger.validate_claims([row],stage_id='research:0')
    assert not issues
    span = valid[0]['source_spans'][0]
    assert before[0]['text'][span['start']:span['end']] == span['quote']
    assert valid[0]['statement'] == row['statement']
    assert valid[0]['anchor_adjustments'][0]['method'] == 'unique_verbatim_reanchor'
    assert valid[0]['review_status'] == 'unreviewed'
    assert ledger.rows() == before


@pytest.mark.parametrize('mutation', ['digest','negation','unit','ambiguous','missing'])
def test_repair_never_fabricates_a_digest_or_accepts_changed_scientific_text(mutation):
    ledger,row = fixture()
    span = row['source_spans'][0]
    if mutation == 'digest':
        span['text_digest'] = 'sha256:'+'0'*64
    elif mutation == 'negation':
        span['quote'] = 'The endpoint was met.'
    elif mutation == 'unit':
        span['quote'] = 'α ≥ 5 mg'
    elif mutation == 'ambiguous':
        ledger,row = fixture('The endpoint was not met. The endpoint was not met.')
    else:
        span['quote'] = ''
    valid,issues = ledger.validate_claims([row],stage_id='research:0')
    assert not valid
    assert len(issues) == 1


def test_new_full_budget_keeps_call_concurrency_and_richness_caps():
    policy = Budget().policy
    assert policy.deadline_seconds == 32*1200*1.25+300
    assert policy.max_agent_calls == 32
    assert policy.research_concurrency == 2
    assert policy.completion_reserve_seconds == 300
    assert policy.stage_allowance_seconds == 1200


def test_previous_version_files_and_contracts_are_unchanged():
    frozen = json.loads((ASSET_ROOT/'tests/reference/published_014_frozen.json').read_text())
    manifest = json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())
    for version,value in frozen['manifest_contracts'].items():
        assert manifest['versions'][version] == value
    for name,sha in frozen['files'].items():
        assert hashlib.sha256((ASSET_ROOT/name).read_bytes()).hexdigest() == sha


def test_all_seven_argon_profiles_and_prompt_digests_preserve_scientific_task_injection():
    from clinical_failure_intelligence.prompt_catalog_v0_1_5 import COMMON_PROMPT, PROMPTS, PROMPT_VERSION
    from clinical_failure_intelligence.runtime_access_v0_1_5 import AgentRunner
    from clinical_failure_intelligence.contracts_v0_1_5 import parse_request
    requirements = json.loads((ASSET_ROOT/'admission_requirements_v0_1_5.json').read_text())
    assert PROMPT_VERSION == '1.4.0'
    assert len(requirements['agent_contracts']) == 7
    for row in requirements['agent_contracts']:
        role = row['role']
        assert (ASSET_ROOT/row['prompt_file']).read_text() == PROMPTS[role]
        sha = 'sha256:'+hashlib.sha256((COMMON_PROMPT+'\n\n'+PROMPTS[role]).encode()).hexdigest()
        assert sha == row['prompt_digest']
        policy = row['request_policy']
        assert policy['model'] == 'gemini-4-argon' and policy['timeout_seconds'] == 1200
        assert policy['thinking_level'] == row['reasoning_policy']['level']
        packet = AgentRunner(FakeInputs(),Budget()).packet(role,parse_request(example_inputs()),
            task_id='TASK_SYN', obligations=['item'], packet_data={'evidence_packet':[{'text':'μg ≥ 5 {untrusted} 😀'}]})
        assert packet['prompt_digest'] == sha
        assert packet['evidence_packet'][0]['text'] == 'μg ≥ 5 {untrusted} 😀'
        assert len(packet['instructions']) < 300


def test_new_orchestration_remains_preview_and_uses_structured_role_inputs():
    class Inputs(FakeInputs):
        def agent_input_budget(self, role):
            return {'schema_version':'agent_input_budget.v1','scope':'single_step_initial_request',
                'max_input_json_chars':160000,'max_input_json_bytes':262144}
    inputs = Inputs(example_inputs())
    result = run_analysis(inputs)['outputs']['clinical_intelligence']
    assert result['asset'].endswith('@0.1.5')
    assert not result['memory_update']['write_attempted']
    assert inputs.calls
