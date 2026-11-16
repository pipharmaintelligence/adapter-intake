"""Provider-free regression for overflow after successful model validation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import sys
from threading import Lock
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]
from devtools.skill_citation import CitationRef
import devtools.agent_citation_view as citation_view
from claim_evidence_contract_v0_1_21 import build_claim_evidence_index, ClaimEvidenceError
from source_evidence_v0_1_40 import SourceEvidenceInputs as PreviousNative
from source_evidence_v0_1_39 import SourceEvidenceInputs as LiteralInputs
from source_evidence_v0_1_55 import SourceEvidenceInputs, supported_native_locators, enforce_claim_field_bounds
from source_verification_v0_1_55 import TargetedSourceInputs
from test_source_verification_v0_1_45 import Reader, payload as literal_payload
from test_durable_batched_v0_1_51 import GroundedBatchedInputs
from orchestration_v0_1_54 import invoke_v0_1_54
from orchestration_v0_1_55 import invoke_v0_1_55
import legacy_preparation_helpers_v0_1_23 as legacy


def citations(count):
    return [CitationRef(locator=f'https://evidence.example/{i}', title='Synthetic source',
        source_kind='agent_citation', provider_family='vertex_ai', provider_turn_index=0,
        source_pointer=('candidate', 'groundingMetadata')) for i in range(count)]


def claim(identity='one', statement='A bounded supported statement.', refs=None):
    return {'claim_id': identity, 'section_id': 'company_profile', 'statement': statement,
        'evidence_kind': 'grounded_external', 'inference': False, 'evidence_qualifiers': [],
        'citation_locators': refs or ['https://evidence.example/0'], 'evidence_quotes': []}


def metadata(refs, claims, indices=None):
    return {'provider_metadata': {'turns': [{'provider_schema': 'vertex.generate_content.metadata.v1',
        'provider_family': 'vertex_ai', 'turn_index': 0,
        'native': {'candidate': {'groundingMetadata': {
            'groundingChunks': [{'web': {'uri': ref.locator}} for ref in refs],
            'groundingSupports': [{'segment': {'text': c['statement']},
                'groundingChunkIndices': list(range(len(refs))) if indices is None else indices} for c in claims],
        }}}}]}}


def view(cls=SourceEvidenceInputs):
    value = object.__new__(cls)
    value.units = []
    value.citations = []
    value.observations = []
    return value


def index(value, refs):
    forced = {c['claim_id']: c['_source_issue'] for c in value['claims'] if c.get('_source_issue')}
    return build_claim_evidence_index(role='portfolio_researcher', pass_number=1,
        claims=value['claims'], citations=refs, forced_withheld=forced)


class BoundsTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('unexpected network'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_reproduces_original_fatal_overflow_and_new_path_withholds_only_affected_claim(self):
        refs = citations(25)
        bad, good = claim(), claim('two', 'Independent supported statement.', [refs[-1].locator])
        original = {'claims': [bad, good]}
        unchanged = deepcopy(original)
        native = metadata(refs, [bad])
        previous, _ = view(PreviousNative).verify_source_claims(original, admitted=refs, agent_result=native)
        with self.assertRaisesRegex(ClaimEvidenceError, 'claim_citation_locators_invalid'):
            index(previous, refs)
        checked = view()
        value, admitted = checked.verify_source_claims(original, admitted=refs, agent_result=native)
        evidence = index(value, admitted)
        self.assertEqual(('two',), evidence.accepted_claim_ids)
        self.assertEqual(('one',), evidence.withheld_claim_ids)
        self.assertEqual('claim_citation_locator_budget_exceeded', evidence.record('one').issue_code)
        self.assertEqual([], value['claims'][0]['citation_locators'])
        self.assertNotIn('native_grounding', value['claims'][0])
        self.assertEqual(25, checked.observations[0]['observed_count_at_least'])
        self.assertEqual(unchanged, original)
        self.assertNotIn('https:', json.dumps(checked.observations))

    def test_exact_twenty_four_preserves_previous_evidence_and_requires_downstream_critic(self):
        refs = citations(24)
        original = {'claims': [claim()]}
        native = metadata(refs, original['claims'])
        old, _ = view(PreviousNative).verify_source_claims(original, admitted=refs, agent_result=native)
        current, admitted = view().verify_source_claims(original, admitted=refs, agent_result=native)
        self.assertEqual(old, current)
        self.assertEqual(('one',), index(current, admitted).accepted_claim_ids)
        self.assertFalse(current['claims'][0]['native_grounding']['literal_source_verified'])
        self.assertNotIn('verification_status', current['claims'][0])

    def test_combined_model_and_native_refs_cannot_bypass_the_same_bound(self):
        refs = citations(25)
        original = {'claims': [claim(refs=[refs[-1].locator])]}
        native = metadata(refs, original['claims'], indices=list(range(24)))
        current, admitted = view().verify_source_claims(original, admitted=refs, agent_result=native)
        self.assertEqual(('one',), index(current, admitted).withheld_claim_ids)

    def test_duplicate_native_indices_do_not_consume_distinct_reference_allowance(self):
        refs = citations(1)
        current, admitted = view().verify_source_claims({'claims': [claim()]}, admitted=refs,
            agent_result=metadata(refs, [claim()], indices=[0] * 10000))
        self.assertEqual([refs[0].locator], current['claims'][0]['citation_locators'])
        self.assertEqual(('one',), index(current, admitted).accepted_claim_ids)

    def test_expansion_stops_at_twenty_fifth_distinct_uri_instead_of_scanning_huge_support(self):
        class CountingIndices(list):
            visited = 0
            def __iter__(self):
                for value in super().__iter__():
                    self.visited += 1
                    if self.visited > 25:
                        raise AssertionError('unbounded native expansion')
                    yield value
        refs = citations(30)
        indices = CountingIndices(range(10000))
        values = supported_native_locators(claim()['statement'], metadata(refs, [claim()], indices),
                                           {r.locator: r for r in refs})
        self.assertEqual(25, len(values))
        self.assertEqual(25, indices.visited)

    def test_non_admitted_or_unmatched_support_never_becomes_claim_evidence(self):
        refs = citations(2)
        original = {'claims': [claim(refs=['invented:reference'])]}
        native = metadata(refs, [claim(statement='A different statement.')])
        current, admitted = view().verify_source_claims(original, admitted=refs[:1], agent_result=native)
        self.assertEqual(('one',), index(current, admitted).withheld_claim_ids)
        self.assertNotIn('native_grounding', current['claims'][0])

    def test_boolean_negative_and_out_of_range_indices_never_select_sources(self):
        refs = citations(1)
        original = {'claims': [claim(refs=['invented:reference'])]}
        current, admitted = view().verify_source_claims(original, admitted=refs,
            agent_result=metadata(refs, [claim()], [True, False, -1, 1, '0', None]))
        self.assertEqual(('one',), index(current, admitted).withheld_claim_ids)

    def test_malformed_optional_provider_metadata_is_inert_and_does_not_crash(self):
        refs = citations(1)
        samples = [None, [], {'provider_metadata': []}, {'provider_metadata': {'turns': [None, 'bad']}},
            {'provider_metadata': {'turns': [{'provider_schema': 'vertex.generate_content.metadata.v1', 'native': []}]}}]
        for value in samples:
            with self.subTest(value=value):
                current, admitted = view().verify_source_claims({'claims': [claim(refs=['invented:reference'])]},
                    admitted=refs, agent_result=value)
                self.assertEqual(('one',), index(current, admitted).withheld_claim_ids)

    def test_malformed_support_and_chunk_shapes_never_manufacture_authority(self):
        refs = citations(1)
        native = metadata(refs, [claim()])
        grounding = native['provider_metadata']['turns'][0]['native']['candidate']['groundingMetadata']
        grounding['groundingChunks'] = [{'web': {'uri': {}}}, 'bad', None]
        grounding['groundingSupports'] += ['bad', None, {'segment': [], 'groundingChunkIndices': [0]}]
        current, admitted = view().verify_source_claims({'claims': [claim(refs=['invented:reference'])]},
            admitted=refs, agent_result=native)
        self.assertEqual(('one',), index(current, admitted).withheld_claim_ids)

    def test_leaf_field_errors_are_contained_without_relaxing_existing_raw_limits(self):
        for field, value in [('citation_locators', ['x'] * 25), ('citation_locators', None),
                ('citation_locators', [{}]), ('evidence_qualifiers', ['x'] * 9),
                ('citation_locators', ['bad\x00ref']), ('evidence_qualifiers', ['bad\x7fvalue']),
                ('evidence_qualifiers', ['x' * 501]), ('evidence_qualifiers', 'bad')]:
            with self.subTest(field=field, value_type=type(value).__name__):
                record = claim()
                record[field] = value
                observations = []
                self.assertFalse(enforce_claim_field_bounds(record, observations))
                self.assertEqual([], record['citation_locators'])
                self.assertEqual([], record['evidence_qualifiers'])
                self.assertEqual(('one',), index({'claims': [record]}, []).withheld_claim_ids)

    def test_qualifier_exact_boundary_matches_unchanged_index_whitespace_semantics(self):
        record = claim()
        record['evidence_qualifiers'] = [' ' + 'x' * 500 + ' ']
        self.assertTrue(enforce_claim_field_bounds(record, []))
        self.assertEqual(('one',), index({'claims': [record]}, citations(1)).accepted_claim_ids)

    def test_leaf_overflow_is_checked_before_iterating_oversized_values(self):
        class Oversized(list):
            def __iter__(self):
                raise AssertionError('oversized field should not be traversed')
        record = claim()
        record['evidence_qualifiers'] = Oversized(['x'] * 10000)
        self.assertFalse(enforce_claim_field_bounds(record, []))

    def test_claim_identity_errors_remain_fatal_even_when_overflow_is_contained(self):
        original = {'claims': [claim('bad identity with spaces')]}
        refs = citations(25)
        value, admitted = view().verify_source_claims(original, admitted=refs,
            agent_result=metadata(refs, original['claims']))
        with self.assertRaisesRegex(ClaimEvidenceError, 'claim_evidence_forced_withheld_invalid'):
            index(value, admitted)

    def test_unexpected_toolkit_authority_failure_is_not_swallowed(self):
        raw = Reader()
        source = TargetedSourceInputs(raw, record={'company_id': 13, 'company': 'Example'})
        with patch.object(LiteralInputs, 'verify_source_claims', side_effect=RuntimeError('authority_rejected')):
            with self.assertRaisesRegex(RuntimeError, 'authority_rejected'):
                source.verify_source_claims(literal_payload())

    def test_corrupt_literal_spans_remain_unverified(self):
        raw = Reader()
        raw.corrupt = True
        source = TargetedSourceInputs(raw, record={'company_id': 13, 'company': 'Example'})
        value, _ = source.verify_source_claims(literal_payload())
        self.assertNotIn('source_spans', value['claims'][0])
        self.assertTrue(any(o.get('reason') == 'source_exact_span_unresolved' for o in source.observations))

    def test_real_literal_toolkit_path_is_preserved(self):
        raw = Reader()
        source = TargetedSourceInputs(raw, record={'company_id': 13, 'company': 'Example'})
        value, _ = source.verify_source_claims(literal_payload())
        self.assertTrue(value['claims'][0]['source_spans'])
        self.assertNotIn('_source_issue', value['claims'][0])
        self.assertEqual(1, len(raw.reads))

    def test_parallel_pieces_with_overflow_do_not_add_network_repairs_or_shared_state_loss(self):
        raw = Reader()
        source = TargetedSourceInputs(raw, record={'company_id': 13, 'company': 'Example'})
        refs = citations(25)
        original = {'claims': [claim()]}
        with ThreadPoolExecutor(max_workers=15) as pool:
            results = list(pool.map(lambda _: source.verify_source_claims(original, admitted=refs,
                agent_result=metadata(refs, [claim()])), range(30)))
        self.assertTrue(all(index(value, admitted).withheld_claim_ids == ('one',) for value, admitted in results))
        self.assertEqual(30, len([x for x in source.observations if x.get('phase') == 'claim_evidence_bounds']))
        self.assertFalse(raw.reads)
        self.assertFalse(raw.requests)

    def test_current_adapter_imports_in_the_catalog_attested_python_only_closure(self):
        try:
            from devtools.isolated_adapter_runner import _materialized_adapter, _sha256
            from devtools.adapter_catalog import _local_support_files
        except ImportError:
            self.skipTest('Real SDK isolation mechanism unavailable in intake stubs')
        module = ROOT / 'nusaibah_pharma_company_intelligence_lab_v0_1_55_adapter.py'
        support = _local_support_files(module)
        self.assertLessEqual(len(support), 256)
        config = {'module_hash': _sha256(module), 'support_files': [
            {'path': str(p), 'sha256': _sha256(p)} for p in support]}
        with _materialized_adapter(module, config) as isolated:
            script = isolated.parent / 'fixture_import.py'
            script.write_text('import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\n'
                'from nusaibah_pharma_company_intelligence_lab_v0_1_55_adapter import NusaibahPharmaCompanyIntelligenceLabV055Adapter as Adapter\n'
                'assert Adapter.version == "0.1.55"\n'
                'assert not list(Path(__file__).parent.glob("*.json"))\n'
                'import source_evidence_v0_1_55\n'
                'assert Path(source_evidence_v0_1_55.__file__).parent == Path(__file__).parent\n', encoding='utf-8')
            result = subprocess.run([sys.executable, '-I', str(script)], capture_output=True,
                                    text=True, encoding='utf-8', timeout=30)
            self.assertEqual(0, result.returncode, result.stderr[-2000:])


class OverflowInputs(GroundedBatchedInputs):
    def __init__(self):
        super().__init__()
        self.overflow_lock = Lock()
        self.overflow_statement = None
    def _single_invoke(self, role, *, input, on_error='raise'):
        envelope = super()._single_invoke(role, input=input, on_error=on_error)
        if role == legacy.RESEARCH_ROLES[0]:
            with self.overflow_lock:
                claims = envelope['result']['content'][0]['value']['claims']
                if claims and self.overflow_statement is None:
                    target = deepcopy(claims[0])
                    target['claim_id'] += '-overflow'
                    target['statement'] = 'The isolated overflow fixture must never become accepted company evidence.'
                    claims.append(target)
                    self.overflow_statement = target['statement']
                    refs = citations(25)
                    grounding = metadata(refs, [target])['provider_metadata']['turns']
                    grounding[0]['turn_index'] = len(envelope['result']['provider_metadata']['turns'])
                    envelope['result']['provider_metadata']['turns'].extend(grounding)
        return envelope


class FullCycleTests(unittest.TestCase):
    setUp = BoundsTests.setUp

    @unittest.skipUnless(hasattr(citation_view, '_validated_turns'), 'Requires real SDK citation projection')
    def test_published_054_aborts_on_the_same_valid_provider_fixture_before_publication(self):
        value = OverflowInputs()
        with self.assertRaisesRegex(ClaimEvidenceError, 'claim_citation_locators_invalid'):
            invoke_v0_1_54(value, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.54')
        self.assertFalse(any(role.endswith('_update') for role in value.mutables))
    @unittest.skipUnless(hasattr(citation_view, '_validated_turns'), 'Requires real SDK citation projection')
    def test_normal_canonical_publication_and_call_count_match_published_054(self):
        old, new = GroundedBatchedInputs(), GroundedBatchedInputs()
        before = invoke_v0_1_54(old, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.54')
        after = invoke_v0_1_55(new, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.55')
        self.assertEqual(before['metrics']['agent_call_count'], after['metrics']['agent_call_count'])
        for role in ('company_memory', 'company_methodology'):
            self.assertEqual(old.store[(13, role)]['text'], new.store[(13, role)]['text'])
        self.assertTrue(after['outputs']['intelligence_dossier']['company_results'][0]['skill_publication']['publication_complete'])

    @unittest.skipUnless(hasattr(citation_view, '_validated_turns'), 'Requires real SDK citation projection')
    def test_overflow_full_cycle_preserves_safe_siblings_and_publishes_with_actual_receipts(self):
        value = OverflowInputs()
        result = invoke_v0_1_55(value, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.55')
        row = result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(value.overflow_statement)
        self.assertTrue(row['research_incomplete'])
        self.assertGreater(row['accepted_claim_count'], 0)
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertTrue(row['skill_publication']['memory']['readback_verified'])
        diagnostics = [o for o in row['source_retrieval'] if o.get('phase') == 'claim_evidence_bounds']
        self.assertEqual(1, len(diagnostics))
        self.assertEqual('claim_citation_locator_budget_exceeded', diagnostics[0]['rule'])
        research = [c for c in row['profile_research'] if c.get('statement') == value.overflow_statement]
        self.assertEqual(1, len(research))
        self.assertEqual('unverified', research[0]['verification_status'])
        text = value.store[(13, 'company_memory')]['text']
        paragraph = next(p for p in text.split('\n\n') if value.overflow_statement in p)
        self.assertIn('**Unverified research.**', paragraph)
        self.assertNotIn('[R', paragraph)
        self.assertIn('Annex: Need Review', value.store[(13, 'company_memory')]['text'])

    def test_all_nine_argon_contracts_and_published_versions_remain_immutable(self):
        manifest = json.loads((ROOT / 'nusaibah_pharma_company_intelligence_lab.asset.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['versions']['0.1.54'], manifest['versions']['0.1.55'])
        self.assertEqual('0.1.55', manifest['default'])
        self.assertEqual(9, len(manifest['versions']['0.1.55']['agents']))


if __name__ == '__main__':
    unittest.main()
