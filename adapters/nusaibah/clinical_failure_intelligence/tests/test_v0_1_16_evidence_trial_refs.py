"""Synthetic source-to-ledger regressions; no private records or provider calls."""
from copy import deepcopy
import hashlib
import json
import pytest
from jsonschema import Draft202012Validator
from fakes import ASSET_ROOT
from test_source_bundle import case_inputs, entry, bundle, metadata, abstract, trial_result, NCT
from test_v0_1_16_candidate_scope import ScopeInputs
from clinical_failure_intelligence.contracts_v0_1_16 import (
    ContractError, MAX_EVIDENCE_TRIAL_IDS, digest, parse_request,
)
from clinical_failure_intelligence.evidence_v0_1_16 import EvidenceLedger
from clinical_failure_intelligence.evidence_v0_1_15 import EvidenceLedger as OldLedger
from clinical_failure_intelligence.contracts_v0_1_15 import ContractError as OldError
from clinical_failure_intelligence.orchestration_v0_1_16 import run_analysis
from clinical_failure_intelligence.rendering_v0_1_16 import validate_result
from clinical_failure_intelligence.source_bundle_v0_1_16 import prepare_bundle


def review(count, *, inline_extra=False):
    ids = [f'NCT{i:08d}' for i in range(1, count + 1)]
    meta = metadata(types=['Review'])
    meta['records'][0]['nct_ids_in_record'] = ids
    content = 'Synthetic review citation inventory; no case outcome is established.'
    if inline_extra:
        content += ' NCT99999999'
    return bundle(entry(meta, 'pubmed'), entry(abstract(content=content), 'pubmed')), ids


def request_data(count, **kwargs):
    raw = case_inputs()
    raw['variables'].update(memory_mode='off', enable_refinement=False,
        prepare_result_for_persistence=True, max_agent_calls=64)
    raw['clinical_evidence'], ids = review(count, **kwargs)
    return raw, ids


@pytest.mark.parametrize('count', [0, 1, 32, 33, 64, 128])
def test_preparation_ledger_and_model_free_result_preserve_complete_citations(count):
    raw, ids = request_data(count)
    before = deepcopy(raw)
    req = parse_request(raw)
    rows = req['prepared_sources']['evidence']
    assert len(rows) == 1 and rows[0]['trial_ids'] == ids
    ledger = EvidenceLedger(req['subject_id'], req['as_of_date'], rows)
    assert ledger.rows()[0]['trial_ids'] == ids
    assert raw == before
    raw['variables'].update(preflight_only=True, prepare_result_for_persistence=False)
    result = run_analysis(raw)['outputs']['clinical_intelligence']
    assert any(row['trial_ids'] == ids for row in result['evidence'])
    assert result['subject']['trial_ids'] == [NCT]
    assert result['execution']['logical_agent_calls'] == 0
    validate_result(result)  # Preflight DTO is not a staged publication record.


def test_64_review_citations_pass_full_analysis_and_staging_without_expanding_case_scope():
    raw, ids = request_data(64)
    host = ScopeInputs(raw, bad=False)
    outputs = run_analysis(host)['outputs']
    result = outputs['clinical_intelligence']
    assert result['asset'].endswith('@0.1.16')
    assert any(row['trial_ids'] == ids for row in result['evidence'])
    assert result['subject']['trial_ids'] == [NCT]
    assert all(set(row['trial_ids']) <= {NCT} for row in result['case_assessments'])
    assert outputs['clinical_intelligence_records']['records'] == [result]
    assert result['execution']['logical_agent_calls'] <= 64
    assert not result['memory_update']['write_attempted']
    Draft202012Validator(json.loads((ASSET_ROOT/'clinical_intelligence_v0_1_16.schema.json').read_text())).validate(result)


def test_original_015_still_rejects_64_ids_and_its_files_are_unchanged():
    raw, _ = request_data(64)
    req = parse_request(raw)
    with pytest.raises(OldError, match='clinical_id_list_invalid'):
        OldLedger(req['subject_id'], req['as_of_date'], req['prepared_sources']['evidence'])
    frozen = json.loads((ASSET_ROOT/'tests/reference/published_0_1_15_frozen.json').read_text())
    for name, expected in frozen['files'].items():
        assert hashlib.sha256((ASSET_ROOT/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == expected
    manifest = json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())
    for version, expected in frozen['versions_sha256'].items():
        encoded = json.dumps(manifest['versions'][version], sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == expected
    assert manifest['default'] == '0.1.16'


@pytest.mark.parametrize('inline_extra', [False, True])
def test_over_limit_defers_whole_window_with_exact_source_receipt_and_no_truncation(inline_extra):
    raw, ids = request_data(129 if not inline_extra else 128, inline_extra=inline_extra)
    before = deepcopy(raw['clinical_evidence'])
    req = parse_request(raw)
    prepared = req['prepared_sources']
    assert prepared['status'] == 'partial' and prepared['evidence'] == []
    omitted = prepared['omissions']
    assert len(omitted) == 1
    row = omitted[0]
    complete_ids = sorted(ids + (['NCT99999999'] if inline_extra else []))
    assert row['code'] == 'clinical_source_trial_references_require_partitioning'
    assert row['trial_id_count'] == 129 and row['maximum_trial_ids'] == MAX_EVIDENCE_TRIAL_IDS
    assert row['trial_ids_digest'] == digest(complete_ids)
    source = next(s for s in before['sources'] if s['source_result_id'] == row['source_result_id'])
    assert row['source_result_digest'] == source['result_digest']
    assert row['source_pointer'].endswith('/sections/0') and row['automatic_replay'] is False
    assert raw['clinical_evidence'] == before
    raw['variables'].update(preflight_only=True, prepare_result_for_persistence=False)
    result = run_analysis(raw)['outputs']['clinical_intelligence']
    assert result['execution']['logical_agent_calls'] == 0


def test_metadata_and_inline_mentions_deduplicate_without_removing_distinct_references():
    raw, ids = request_data(64)
    source = raw['clinical_evidence']['sources'][1]
    source['result']['records'][0]['sections'][0]['text'] += ' '+ids[0]+' NCT99999999'
    source['result_digest'] = digest(source['result'])
    rows = parse_request(raw)['prepared_sources']['evidence']
    assert rows[0]['trial_ids'] == sorted(ids + ['NCT99999999'])


def test_over_limit_review_preserves_valid_sibling_trial_evidence():
    raw, _ = request_data(129)
    raw['clinical_evidence']['sources'].append(entry(trial_result()))
    prepared = parse_request(raw)['prepared_sources']
    assert prepared['status'] == 'partial'
    assert prepared['evidence'] and len(prepared['omissions']) == 1
    assert all(row['trial_ids'] == [NCT] for row in prepared['evidence'])
    assert any(row['source_context']['evidence_use'] == 'posted_results'
               for row in prepared['evidence'])
    ledger = EvidenceLedger('CASE_SYN', '2025-02-01', prepared['evidence'])
    assert len(ledger.rows()) == len(prepared['evidence'])


@pytest.mark.parametrize('bad', [['NCT00000001', 'NCT00000001'], ['invalid id'], 'NCT00000001'])
def test_direct_evidence_still_rejects_duplicate_malformed_or_nonlist_ids(bad):
    raw, _ = request_data(64)
    req = parse_request(raw)
    row = deepcopy(req['prepared_sources']['evidence'][0]);row['trial_ids'] = bad
    with pytest.raises(ContractError):EvidenceLedger(req['subject_id'], req['as_of_date'], [row])


def test_case_trial_scope_limit_is_not_broadened_by_source_citation_fix():
    raw, _ = request_data(64)
    raw['clinical_context']['subject']['trial_ids'] = [f'NCT{i:08d}' for i in range(1, 34)]
    with pytest.raises(ContractError, match='clinical_id_list_invalid'):parse_request(raw)


def test_over_limit_direct_evidence_remains_rejected():
    raw, _ = request_data(64);req = parse_request(raw)
    row = deepcopy(req['prepared_sources']['evidence'][0])
    row['trial_ids'] = [f'NCT{i:08d}' for i in range(1, 130)]
    with pytest.raises(ContractError, match='clinical_id_list_invalid'):
        EvidenceLedger(req['subject_id'], req['as_of_date'], [row])
