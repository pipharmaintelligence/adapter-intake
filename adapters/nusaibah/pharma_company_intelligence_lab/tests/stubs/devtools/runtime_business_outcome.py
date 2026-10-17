"""Provider-free metadata interface only; production validation is owned by SDK 0.1.110.
This stub is excluded from materialized assets and cannot persist any receipt.
"""
import json
import re
from typing import Any
SCHEMA = 'runtime_business_outcome.v1'
MAX_BYTES = 16384
STATUSES = {'applied', 'initialized', 'no_change', 'withheld', 'not_requested',
            'apply_failed_or_unconfirmed', 'committed_readback_unverified',
            'initialized_readback_unverified', 'unverified'}
CHECKS = {'candidate_present', 'candidate_admitted', 'candidate_changed',
          'selected_claim_critic_complete', 'selected_evidence_complete',
          'current_profile_consolidated', 'publication_complete', 'coverage_complete'}
METRICS = {'candidate_char_count', 'candidate_byte_count', 'accepted_claim_count',
           'selected_fact_count', 'section_coverage_count', 'report_omission_count',
           'critic_packet_count', 'critic_call_count'}
EFFECT_KEYS = {'role', 'status', 'reason_code', 'change_id', 'before_digest', 'after_digest',
               'readback_verified', 'history_verified', 'upload_verified', 'no_change_verified',
               'write_attempted', 'upload_id', 'operation_id'}

def encode(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def validate_business_outcome(value: Any) -> dict[str, Any]:
    def require(condition: bool) -> None:
        if not condition:
            raise ValueError('runtime_business_outcome_invalid')
    def identifier(item: Any, maximum: int = 100) -> bool:
        return isinstance(item, str) and re.fullmatch(r'[a-z][a-z0-9_.]{0,'+str(maximum-1)+'}', item) is not None
    require(isinstance(value, dict) and set(value) == {'schema_version', 'publication_required', 'subjects'})
    require(value['schema_version'] == SCHEMA and type(value['publication_required']) is bool)
    subjects = value['subjects']
    require(isinstance(subjects, list) and 1 <= len(subjects) <= 2)
    seen_subjects = set()
    for subject in subjects:
        require(isinstance(subject, dict) and set(subject) == {
            'subject_type', 'subject_id', 'effects', 'checks', 'content_metrics', 'admission_reason_code'})
        require(identifier(subject['subject_type'], 40) and type(subject['subject_id']) is int
                and 1 <= subject['subject_id'] <= 9007199254740991)
        identity = (subject['subject_type'], subject['subject_id'])
        require(identity not in seen_subjects)
        seen_subjects.add(identity)
        require(subject['admission_reason_code'] is None or identifier(subject['admission_reason_code']))
        for name, allowed, booleans in [('checks', CHECKS, True), ('content_metrics', METRICS, False)]:
            entries = subject[name]
            require(isinstance(entries, dict) and set(entries).issubset(allowed))
            for item in entries.values():
                require(type(item) is bool if booleans else type(item) is int and 0 <= item <= 16777216)
        effects = subject['effects']
        require(isinstance(effects, list) and 1 <= len(effects) <= 8)
        seen_roles = set()
        for effect in effects:
            require(isinstance(effect, dict) and set(effect) == EFFECT_KEYS)
            require(identifier(effect['role'], 80) and effect['role'] not in seen_roles and effect['status'] in STATUSES)
            seen_roles.add(effect['role'])
            require(effect['reason_code'] is None or identifier(effect['reason_code']))
            require(effect['change_id'] is None or isinstance(effect['change_id'], str)
                    and re.fullmatch(r'dynchg_[a-f0-9]{32}', effect['change_id']) is not None)
            for name in ('before_digest', 'after_digest'):
                item = effect[name]
                require(item is None or isinstance(item, str) and re.fullmatch(r'(?:sha256:)?[a-f0-9]{64}', item) is not None)
            for name in ('readback_verified', 'history_verified', 'upload_verified', 'no_change_verified', 'write_attempted'):
                require(type(effect[name]) is bool)
            require(effect['upload_id'] is None or type(effect['upload_id']) is int and effect['upload_id'] > 0)
            require(effect['operation_id'] is None or isinstance(effect['operation_id'], str)
                    and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,119}', effect['operation_id']) is not None)
            if not value['publication_required']:
                require(effect['status'] in {'not_requested', 'no_change', 'withheld'} and not effect['write_attempted'])
    require(len(encode(value)) <= MAX_BYTES)
    return json.loads(encode(value))


def publication_status(outcome: dict[str, Any]) -> str:
    if not outcome['publication_required']:
        return 'not_requested'
    effects = [effect for subject in outcome['subjects'] for effect in subject['effects']]
    for effect in effects:
        status = effect['status']
        if status not in {'applied', 'initialized', 'no_change', 'withheld'}:
            return 'unverified'
        if status == 'applied' and not (effect['change_id'] and effect['after_digest']
                and effect['readback_verified'] and effect['history_verified']):
            return 'unverified'
        if status == 'initialized' and not (effect['upload_id'] and effect['operation_id']
                and effect['after_digest'] and effect['readback_verified'] and effect['upload_verified']):
            return 'unverified'
        if status == 'no_change' and not (effect['before_digest'] == effect['after_digest']
                and (effect['readback_verified'] or effect['no_change_verified']
                     or effect['before_digest'] is None and not effect['write_attempted'])):
            return 'unverified'
    if any(effect['status'] == 'withheld' for effect in effects):
        return 'withheld'
    return 'no_change' if all(effect['status'] == 'no_change' for effect in effects) else 'published'
