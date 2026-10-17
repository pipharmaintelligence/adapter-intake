"""Provider-free 0.1.0 contract tests for ClinicalTrials.gov source lookup.

Only synthetic registry-shaped records and an injected trusted-runtime helper
are used. These tests do not make requests, certify provider access, or admit a
Runtime Source to a production worker.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import sys
import types
import unittest
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
ASSET = REPO / 'adapters' / 'nusaibah' / 'clinical_trials_lookup'

# In a genuine adapter-intake or DataSpell environment the installed runtime
# supplies adapters.base. The tiny fallback is for offline contract-only tests.
try:
    from adapters.base import Adapter  # noqa: F401
except ImportError:
    adapter_package = types.ModuleType('adapters')
    adapter_package.__path__ = []
    base_package = types.ModuleType('adapters.base')
    base_package.Adapter = type('Adapter', (), {})
    sys.modules.setdefault('adapters', adapter_package)
    sys.modules.setdefault('adapters.base', base_package)

spec = importlib.util.spec_from_file_location('clinical_lookup_under_test', ASSET / 'clinical_trials_lookup_adapter.py')
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


STUDY = {
    'hasResults': True,
    'protocolSection': {
        'identificationModule': {
            'nctId': 'NCT01234567',
            'briefTitle': 'Synthetic randomized Phase 3 trial',
            'officialTitle': 'Synthetic Study with Drug Alpha',
            'orgStudyIdInfo': {'id': 'SYNTHETIC-01'},
        },
        'statusModule': {
            'overallStatus': 'COMPLETED',
            'lastUpdatePostDateStruct': {'date': '2026-01-15'},
            'primaryCompletionDateStruct': {'date': '2025-12-01'},
        },
        'designModule': {
            'studyType': 'INTERVENTIONAL', 'phases': ['PHASE3'],
            'enrollmentInfo': {'count': 250, 'type': 'ACTUAL'},
            'designInfo': {'primaryPurpose': 'TREATMENT', 'allocation': 'RANDOMIZED',
                           'maskingInfo': {'masking': 'QUADRUPLE'}},
        },
        'armsInterventionsModule': {
            'armGroups': [
                {'label': 'Alpha', 'type': 'EXPERIMENTAL', 'interventionNames': ['Drug: Alpha']},
                {'label': 'Placebo', 'type': 'PLACEBO_COMPARATOR', 'interventionNames': ['Drug: Placebo']},
            ],
            'interventions': [
                {'type': 'DRUG', 'name': 'Alpha', 'otherNames': ['ALPHA-01'], 'armGroupLabels': ['Alpha']},
            ],
        },
        'conditionsModule': {'conditions': ['Condition B'], 'keywords': ['outcome']},
        'outcomesModule': {'primaryOutcomes': [{'measure': 'Endpoint X', 'timeFrame': '24 weeks'}]},
        'sponsorCollaboratorsModule': {'leadSponsor': {'name': 'Synthetic Sponsor', 'class': 'INDUSTRY'}},
        'oversightModule': {'isFdaRegulatedDrug': None},
        'contactsLocationsModule': {'locations': [{'country': 'United States'}]},
        'descriptionModule': {'briefSummary': 'Synthetic, no real clinical evidence.'},
    },
    'resultsSection': {
        'participantFlowModule': {'preAssignmentDetails': 'Synthetic posted result'},
        'outcomeMeasuresModule': {'outcomeMeasures': [{'type': 'PRIMARY', 'title': 'Endpoint X'}]},
    },
}


class FakeInputs(dict):
    """Role-keyed test inputs with worker-injected deterministic resolver."""

    def __init__(self, response: dict[str, Any], *, roles: tuple[str, ...] = ('trials_search_runtime', 'trials_phase3_runtime', 'trials_detail_runtime')):
        super().__init__({name: {'records': []} for name in roles})
        self.response = response
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    def invoke(self, role: str, *, variables: dict[str, Any], on_error: str = 'raise') -> dict[str, Any]:
        self.calls.append((role, copy.deepcopy(variables), on_error))
        return copy.deepcopy(self.response)


def search_page(*studies: dict[str, Any], continuation: str | None = None, total: int | None = None) -> dict[str, Any]:
    page: dict[str, Any] = {'studies': [copy.deepcopy(study) for study in studies]}
    if continuation is not None:
        page['nextPageToken'] = continuation
    if total is not None:
        page['totalCount'] = total
    return {'records': [page], 'metadata': {'retrieved_at': '2026-10-17T00:00:00Z'}}


def invoke(variables: dict[str, Any], response: dict[str, Any]) -> tuple[dict[str, Any], FakeInputs]:
    fake = FakeInputs(response)
    fake['variables'] = variables
    return module.ClinicalTrialsLookupAdapter().invoke(fake, {}), fake


class ClinicalTrialsLookupTests(unittest.TestCase):
    def test_describe_absent_variables_is_zero_fetch(self) -> None:
        fake = FakeInputs({'records': []})
        result = module.ClinicalTrialsLookupAdapter().invoke(fake, {})['outputs']['trial_result']
        self.assertEqual('describe', result['operation'])
        self.assertEqual('completed', result['status'])
        self.assertIn('study_search', result['capabilities'])
        self.assertEqual([], fake.calls)

    def test_describe_empty_variables_is_zero_fetch(self) -> None:
        answer, fake = invoke({}, {'records': []})
        self.assertEqual('describe', answer['outputs']['trial_result']['operation'])
        self.assertEqual([], fake.calls)

    def test_search_free_text_structured_filter_and_cursor(self) -> None:
        variables = {
            'operation': 'study_search', 'intervention': 'drug alpha',
            'phase': 'PHASE3', 'study_type': 'INTERVENTIONAL',
            'status': ['COMPLETED', 'RECRUITING'], 'updated_from': '2025-01-01',
            'page_size': 2, 'view': 'research', 'sort': 'LastUpdatePostDate:desc',
        }
        answer, fake = invoke(variables, search_page(STUDY, continuation='next-2=', total=48))
        result = answer['outputs']['trial_result']
        self.assertEqual('completed', result['status'])
        self.assertEqual(1, result['record_count'])
        self.assertTrue(result['pagination']['has_more'])
        self.assertEqual('next-2=', result['pagination']['next_page_token'])
        self.assertEqual(48, result['pagination']['total_count'])
        role, params, policy = fake.calls[0]
        self.assertEqual('trials_search_runtime', role)
        self.assertEqual('raise', policy)
        self.assertEqual('drug alpha', params['query.intr'])
        self.assertEqual('COMPLETED,RECRUITING', params['filter.overallStatus'])
        self.assertIn('AREA[Phase]PHASE3', params['filter.advanced'])
        self.assertIn('AREA[StudyType]INTERVENTIONAL', params['filter.advanced'])
        self.assertIn('AREA[LastUpdatePostDate]RANGE[2025-01-01,MAX]', params['filter.advanced'])
        self.assertEqual(2, params['pageSize'])
        self.assertEqual('LastUpdatePostDate:desc', params['sort'])
        record = result['records'][0]
        self.assertEqual('NCT01234567', record['nct_id'])
        self.assertEqual('INDUSTRY', record['summary']['lead_sponsor_class'])
        self.assertEqual('2026-01-15', record['registry_update_date'])
        self.assertTrue(record['content_digest'].startswith('sha256:'))
        self.assertIn('armsInterventionsModule', record['registry_study']['protocolSection'])
        self.assertIn('outcomesModule', record['registry_study']['protocolSection'])
        self.assertIn('oversightModule', record['registry_study']['protocolSection'])
        self.assertIn('resultsSection', record['registry_study'])  # full source retained in research view

    def test_unambiguous_direct_input_infers_search_or_exact_get(self) -> None:
        answer, _ = invoke({'text': 'synthetic'}, search_page(STUDY))
        self.assertEqual('study_search', answer['outputs']['trial_result']['operation'])
        answer, _ = invoke({'nct_id': 'NCT01234567'}, {'records': [STUDY]})
        self.assertEqual('study_get', answer['outputs']['trial_result']['operation'])
        answer, _ = invoke({'nct_ids': ['NCT01234567']}, search_page(STUDY))
        self.assertEqual('study_batch', answer['outputs']['trial_result']['operation'])

    def test_alias_search_compiles_one_bounded_expression(self) -> None:
        _, fake = invoke({'operation': 'study_search',
                          'intervention_terms': ['Alpha', 'ALPHA-01']}, search_page())
        self.assertEqual('"Alpha" OR "ALPHA-01"', fake.calls[0][1]['query.intr'])
        self.assertEqual(1, len(fake.calls))

    def test_search_specific_named_query_areas(self) -> None:
        variables = {'operation': 'study_search', 'text': 'free text', 'condition': 'condition x', 'intervention': 'alpha',
                     'title': 'title x', 'outcome': 'outcome', 'sponsor': 'company',
                     'lead_sponsor': 'company', 'location': 'Paris',
                     'study_identifier': 'SYNTHETIC-01', 'patient_text': 'adult',
                     'country': 'France', 'sponsor_class': 'INDUSTRY', 'page_token': 'opaque==',
                     'advanced_filter': 'AREA[IsFDARegulatedDrug]true'}
        _, fake = invoke(variables, search_page())
        params = fake.calls[0][1]
        for key in module.SEARCH_TERMS.values():
            self.assertIn(key, params)
        self.assertIn('AREA[LocationCountry]France', params['filter.advanced'])
        self.assertIn('AREA[LeadSponsorClass]INDUSTRY', params['filter.advanced'])
        self.assertEqual('opaque==', params['pageToken'])

    def test_pinned_phase3_preset_uses_safe_scalar_parameters(self) -> None:
        variables = {'operation': 'study_search', 'intervention': 'alpha',
                     'preset': 'phase3_interventional', 'phase': 'PHASE3',
                     'study_type': 'INTERVENTIONAL', 'page_size': 5}
        answer, fake = invoke(variables, search_page(STUDY))
        self.assertEqual('completed', answer['outputs']['trial_result']['status'])
        self.assertEqual('trials_phase3_runtime', fake.calls[0][0])
        self.assertNotIn('filter.advanced', fake.calls[0][1])
        self.assertEqual('alpha', fake.calls[0][1]['query.intr'])
        # Client-defined aliases stay available; production Essie admission
        # remains an independently tested trusted-runtime capability.
        aliases, alias_fetch = invoke({'operation': 'study_search',
                       'preset': 'phase3_interventional',
                       'intervention_terms': ['Alpha', 'ALPHA-01']}, search_page(STUDY))
        self.assertEqual('completed', aliases['outputs']['trial_result']['status'])
        self.assertIn(' OR ', alias_fetch.calls[0][1]['query.intr'])
        fake = FakeInputs(search_page(STUDY))
        fake['variables'] = dict(variables, advanced_filter='AREA[Country]France')
        with self.assertRaisesRegex(ValueError, 'clinical_trials_preset_filter_conflict'):
            module.ClinicalTrialsLookupAdapter().invoke(fake, {})
        self.assertEqual([], fake.calls)
        wrong = copy.deepcopy(STUDY)
        wrong['protocolSection']['designModule']['phases'] = ['PHASE2']
        with self.assertRaisesRegex(ValueError, 'clinical_trials_preset_result_scope_mismatch'):
            invoke(variables, search_page(wrong))

    def test_missing_selector_does_not_issue_provider_scan(self) -> None:
        fake = FakeInputs(search_page())
        fake['variables'] = {'operation': 'study_search', 'page_size': 10}
        with self.assertRaisesRegex(ValueError, 'clinical_trials_search_selector_required'):
            module.ClinicalTrialsLookupAdapter().invoke(fake, {})
        self.assertEqual([], fake.calls)

    def test_invalid_count_total_rejected_without_fetch(self) -> None:
        fake = FakeInputs(search_page())
        fake['variables'] = {'operation': 'study_search', 'condition': 'X', 'count_total': 'true'}
        with self.assertRaisesRegex(ValueError, 'clinical_trials_count_total_invalid'):
            module.ClinicalTrialsLookupAdapter().invoke(fake, {})
        self.assertEqual([], fake.calls)

    def test_invalid_date_range_rejected_without_fetch(self) -> None:
        fake = FakeInputs(search_page())
        fake['variables'] = {'operation': 'study_search', 'text': 'X',
                             'updated_from': '2026-01-01', 'updated_to': '2025-01-01'}
        with self.assertRaisesRegex(ValueError, 'clinical_trials_updated_range_invalid'):
            module.ClinicalTrialsLookupAdapter().invoke(fake, {})
        self.assertEqual([], fake.calls)

    def test_bad_study_input_and_unknown_controls_fail_closed(self) -> None:
        fake = FakeInputs(search_page())
        for variables, code in [
            ({'operation': 'study_get', 'nct_id': 'not-nct'}, 'clinical_trials_nct_id_invalid'),
            ({'operation': 'study_search', 'text': 'X', 'credential': 'foo'}, 'clinical_trials_variable_not_allowed'),
            ({'operation': 'describe', 'text': 'X'}, 'clinical_trials_variable_not_allowed'),
            ({'operation': 'study_search', 'text': 'X', 'page_size': 200}, 'clinical_trials_page_size_invalid'),
            ({'operation': 'study_search', 'text': 'X', 'page_token': 'token with spaces'}, 'clinical_trials_page_token_invalid'),
            ({'operation': 'study_search', 'intervention_terms': ['same', 'same']}, 'clinical_trials_intervention_terms_duplicate'),
        ]:
            with self.subTest(code=code):
                fake['variables'] = variables
                with self.assertRaisesRegex(ValueError, code):
                    module.ClinicalTrialsLookupAdapter().invoke(fake, {})
        self.assertEqual([], fake.calls)

    def test_detail_exact_identity_and_not_found(self) -> None:
        answer, fake = invoke({'operation': 'study_get', 'nct_id': 'nct01234567'}, {'records': [STUDY]})
        result = answer['outputs']['trial_result']
        self.assertEqual('NCT01234567', result['records'][0]['nct_id'])
        self.assertEqual('NCT01234567', fake.calls[0][1]['nct_id'])
        self.assertIn('protocolSection', result['records'][0]['registry_study'])
        answer, _ = invoke({'operation': 'study_get', 'nct_id': 'NCT01234567'}, {'records': []})
        self.assertEqual('no_match', answer['outputs']['trial_result']['status'])
        wrong = copy.deepcopy(STUDY)
        wrong['protocolSection']['identificationModule']['nctId'] = 'NCT07654321'
        with self.assertRaisesRegex(ValueError, 'clinical_trials_detail_identity_mismatch'):
            invoke({'operation': 'study_get', 'nct_id': 'NCT01234567'}, {'records': [wrong]})

    def test_batch_reconciles_missing_identifiers_only_on_last_page(self) -> None:
        ids = ['NCT01234567', 'NCT07654321']
        answer, fake = invoke({'operation': 'study_batch', 'nct_ids': ids}, search_page(STUDY))
        result = answer['outputs']['trial_result']
        self.assertEqual(['NCT07654321'], result['missing_ids'])
        self.assertEqual('NCT01234567,NCT07654321', fake.calls[0][1]['filter.ids'])
        answer, _ = invoke({'operation': 'study_batch', 'nct_ids': ids}, search_page(STUDY, continuation='next-page'))
        self.assertIsNone(answer['outputs']['trial_result']['missing_ids'])

    def test_search_page_must_preserve_root_pagination(self) -> None:
        # Old records_path=studies would remove the nextPageToken - reject it.
        with self.assertRaisesRegex(ValueError, 'clinical_trials_search_root_page_required'):
            invoke({'operation': 'study_search', 'text': 'x'}, {'records': [STUDY]})
        with self.assertRaisesRegex(ValueError, 'clinical_trials_page_records_invalid'):
            invoke({'operation': 'study_search', 'text': 'x', 'page_size': 1}, search_page(STUDY, STUDY))

    def test_results_get_retains_posted_results_but_never_interprets_them(self) -> None:
        answer, _ = invoke({'operation': 'results_get', 'nct_id': 'NCT01234567'}, {'records': [STUDY]})
        result = answer['outputs']['trial_result']
        self.assertEqual('posted', result['results_state'])
        self.assertIn('resultsSection', result['records'][0]['registry_study'])
        self.assertNotIn('efficacy', str(result).lower())
        no_results = copy.deepcopy(STUDY)
        del no_results['resultsSection']
        answer, _ = invoke({'operation': 'results_get', 'nct_id': 'NCT01234567'}, {'records': [no_results]})
        self.assertEqual('not_present_in_record', answer['outputs']['trial_result']['results_state'])

    def test_study_too_large_fails_instead_of_dropping_research_fields(self) -> None:
        study = copy.deepcopy(STUDY)
        study['protocolSection']['descriptionModule']['briefSummary'] = 'X' * 280_000
        with self.assertRaisesRegex(ValueError, 'clinical_trials_result_too_large'):
            invoke({'operation': 'study_get', 'nct_id': 'NCT01234567'}, {'records': [study]})

    def test_runtime_failure_does_not_disclose_provider_error(self) -> None:
        fake = FakeInputs(search_page(), roles=('trials_detail_runtime',))
        fake['variables'] = {'operation': 'study_search', 'text': 'trial'}
        with self.assertRaisesRegex(ValueError, 'clinical_trials_runtime_source_not_prepared'):
            module.ClinicalTrialsLookupAdapter().invoke(fake, {})
        self.assertEqual([], fake.calls)

    def test_default_summary_preserves_arm_groups_and_declared_intervention_links(self) -> None:
        answer, _ = invoke({'operation': 'study_search', 'intervention': 'Alpha'}, search_page(STUDY))
        record = answer['outputs']['trial_result']['records'][0]
        summary = record['summary']
        self.assertEqual('EXPERIMENTAL', summary['arm_groups'][0]['type'])
        self.assertEqual(['Drug: Alpha'], summary['arm_groups'][0]['intervention_names'])
        self.assertEqual('PLACEBO_COMPARATOR', summary['arm_groups'][1]['type'])
        self.assertEqual(['Alpha'], summary['interventions'][0]['arm_group_labels'])
        self.assertEqual('EXPERIMENTAL', summary['declared_arm_links'][0]['arm_group_type'])
        self.assertTrue(summary['declared_arm_links'][0]['arm_label_found'])
        self.assertEqual([], summary['unmatched_arm_labels'])
        self.assertIsNone(summary['is_fda_regulated_drug'])

    def test_absent_arms_and_unmatched_labels_preserve_unknown(self) -> None:
        no_arms = copy.deepcopy(STUDY)
        del no_arms['protocolSection']['armsInterventionsModule']
        result, _ = invoke({'nct_id': 'NCT01234567'}, {'records':[no_arms]})
        self.assertEqual([], result['outputs']['trial_result']['records'][0]['summary']['arm_groups'])
        bad_link = copy.deepcopy(STUDY)
        bad_link['protocolSection']['armsInterventionsModule']['interventions'][0]['armGroupLabels'] = ['Unmapped']
        result, _ = invoke({'nct_id': 'NCT01234567'}, {'records':[bad_link]})
        summary = result['outputs']['trial_result']['records'][0]['summary']
        self.assertEqual(['Unmapped'], summary['unmatched_arm_labels'])
        self.assertFalse(summary['declared_arm_links'][0]['arm_label_found'])
        self.assertIsNone(summary['declared_arm_links'][0]['arm_group_type'])

    def test_arms_and_outcomes_get_are_exact_source_views(self) -> None:
        for operation, module_name in [('arms_get','armsInterventionsModule'),('outcomes_get','outcomesModule')]:
            with self.subTest(operation=operation):
                result, fake = invoke({'operation': operation, 'nct_id':'NCT01234567'}, {'records':[STUDY]})
                data=result['outputs']['trial_result']['records'][0]['registry_study']['protocolSection']
                self.assertEqual({'identificationModule',module_name}, set(data))
                self.assertEqual([('trials_detail_runtime',{'nct_id':'NCT01234567'},'raise')], fake.calls)

    def test_research_view_keeps_unknown_protocol_modules_and_derived_document_sections(self) -> None:
        expanded=copy.deepcopy(STUDY)
        expanded['protocolSection']['ipdSharingStatementModule']={'ipdSharing':'NO'}
        expanded['protocolSection']['futureModule']={'newField':'still visible'}
        expanded['derivedSection']={'conditionBrowseModule':{'meshes':[{'term':'Synthetic'}]}}
        expanded['documentSection']={'largeDocumentModule':{'notes':'Synthetic'}}
        result,_=invoke({'operation':'study_get','nct_id':'NCT01234567'}, {'records':[expanded]})
        record=result['outputs']['trial_result']['records'][0]
        self.assertEqual(expanded,record['registry_study'])
        self.assertIn('derivedSection',record['sections_available'])

    def test_results_group_modules_preserved_without_joining_protocol_arms(self) -> None:
        data=copy.deepcopy(STUDY)
        data['resultsSection']['participantFlowModule']['groups']=[{'id':'FG1','title':'Analysis Set'}]
        data['resultsSection']['baselineCharacteristicsModule']={'groups':[{'id':'BG1','title':'Total'}]}
        data['resultsSection']['adverseEventsModule']={'groups':[{'id':'AG1','title':'Safety'}]}
        result,_=invoke({'operation':'results_get','nct_id':'NCT01234567'}, {'records':[data]})
        record=result['outputs']['trial_result']['records'][0]
        self.assertEqual('FG1',record['results_group_modules']['participantFlowModule']['groups'][0]['id'])
        self.assertEqual('BG1',record['results_group_modules']['baselineCharacteristicsModule']['groups'][0]['id'])
        self.assertEqual('AG1',record['results_group_modules']['adverseEventsModule']['groups'][0]['id'])
        self.assertEqual(data['resultsSection'],record['registry_study']['resultsSection'])
        self.assertNotIn('armGroups',record['registry_study']['protocolSection'])

    def test_empty_page_with_cursor_is_not_absence(self) -> None:
        answer,_=invoke({'operation':'study_search','text':'Alpha'}, search_page(continuation='another_page=='))
        result=answer['outputs']['trial_result']
        self.assertEqual('completed',result['status'])
        self.assertEqual(0,result['record_count'])
        self.assertIsNone(result['pagination']['total_count'])
        self.assertTrue(result['pagination']['has_more'])

    def test_multiple_phase_study_matching_phase3_preset_is_accepted(self) -> None:
        mixed=copy.deepcopy(STUDY)
        mixed['protocolSection']['designModule']['phases']=['PHASE2','PHASE3']
        answer,_=invoke({'operation':'study_search','preset':'phase3_interventional','intervention':'Alpha'}, search_page(mixed))
        self.assertEqual('completed',answer['outputs']['trial_result']['status'])

    def test_intervention_plus_aliases_does_not_restrict_search(self) -> None:
        _,fake=invoke({'operation':'study_search','intervention':'alpha','intervention_terms':['ALPHA-01']}, search_page())
        self.assertEqual('"alpha" OR "ALPHA-01"',fake.calls[0][1]['query.intr'])

    def test_results_unposted_vs_missing_is_truthful(self) -> None:
        study=copy.deepcopy(STUDY)
        study.pop('resultsSection');study['hasResults']=False
        answer,_=invoke({'operation':'results_get','nct_id':'NCT01234567'}, {'records':[study]})
        self.assertEqual('not_posted',answer['outputs']['trial_result']['results_state'])
        study.pop('hasResults')
        answer,_=invoke({'operation':'results_get','nct_id':'NCT01234567'}, {'records':[study]})
        self.assertEqual('not_present_in_record',answer['outputs']['trial_result']['results_state'])

    def test_provider_error_codes_are_classified_only_for_known_safe_values(self) -> None:
        class Raising(FakeInputs):
            def __init__(self, code: str):
                super().__init__({'records': []})
                self.code=code
            def invoke(self, role: str, *, variables: dict[str, Any], on_error: str='raise') -> dict[str, Any]:
                raise RuntimeError(self.code)
        for message,expected in [
            ('runtime_source_dynamic_invocation_timed_out','clinical_trials_source_timeout'),
            ('runtime_source_provider_forbidden','clinical_trials_source_forbidden'),
            ('sensitive example user@example.com','clinical_trials_runtime_source_failed'),
        ]:
            with self.subTest(message=expected):
                fake=Raising(message);fake['variables']={'operation':'study_search','text':'Alpha'}
                with self.assertRaisesRegex(ValueError,'^'+expected+'$'):
                    module.ClinicalTrialsLookupAdapter().invoke(fake,{})

    def test_malformed_arm_list_is_rejected_not_silently_emptied(self) -> None:
        invalid=copy.deepcopy(STUDY)
        invalid['protocolSection']['armsInterventionsModule']['armGroups']='not a list'
        with self.assertRaisesRegex(ValueError,'clinical_trials_registry_list_invalid'):
            invoke({'operation':'study_get','nct_id':'NCT01234567'},{'records':[invalid]})

    def test_sort_allows_registry_numeric_field_and_pair(self) -> None:
        answer,fake=invoke({'operation':'study_search','condition':'Synthetic',
                            'sort':'EnrollmentCount:desc,StartDate:asc'},search_page())
        self.assertEqual('EnrollmentCount:desc,StartDate:asc',fake.calls[0][1]['sort'])
        self.assertEqual('no_match',answer['outputs']['trial_result']['status'])
        bad=FakeInputs(search_page());bad['variables']={'operation':'study_search',
              'condition':'Synthetic','sort':'StartDate:desc,OverallStatus,PrimaryCompletionDate'}
        with self.assertRaisesRegex(ValueError,'clinical_trials_sort_invalid'):
            module.ClinicalTrialsLookupAdapter().invoke(bad,{})
        self.assertEqual([],bad.calls)

    def test_results_group_key_names_are_preserved_for_future_source_variants(self) -> None:
        study=copy.deepcopy(STUDY)
        study['resultsSection']['participantFlowModule']['flowGroups']=[{'id':'FG10'}]
        result,_=invoke({'operation':'results_get','nct_id':'NCT01234567'},{'records':[study]})
        index=result['outputs']['trial_result']['records'][0]['results_group_modules']
        self.assertEqual('FG10',index['participantFlowModule']['flowGroups'][0]['id'])

    def test_exact_intake_identity_and_publication_template_status(self) -> None:
        manifest = json.loads((ASSET / 'clinical_trials_lookup.asset.json').read_text())
        self.assertEqual('0.1.0', manifest['default'])
        self.assertEqual(['local_worker', 'ecs'], manifest['execution']['allowed_substrates'])
        self.assertEqual('local_worker', manifest['execution']['default_substrate'])
        self.assertEqual({'0.1.0'}, set(manifest['versions']))
        self.assertFalse(manifest['versions']['0.1.0']['inputs']['variables']['required'])
        self.assertEqual('nusaibah.clinical_trials_lookup', module.ClinicalTrialsLookupAdapter.key)
        self.assertEqual('0.1.0', module.ClinicalTrialsLookupAdapter.version)
        capability = json.loads((ASSET / 'capabilities.v0.1.0.json').read_text())
        self.assertEqual('templates_only', capability['publication_status'])
        self.assertEqual(set(module.OPERATIONS), {
            entry['operation'] for entry in capability['capabilities'].values()
        })


if __name__ == '__main__':
    unittest.main()
