"""Content-free publication decisions for the shared runtime's durable journal."""
import re


def _code(value):
    return value if isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_.]{0,99}', value) else None


def _digest(value):
    return value if isinstance(value, str) and re.fullmatch(r'(?:sha256:)?[a-f0-9]{64}', value) else None


def effect_for(role, receipt, *, requested):
    receipt = receipt or {}
    status = receipt.get('status', 'unverified' if requested else 'not_requested')
    allowed = {'applied', 'initialized', 'no_change', 'withheld', 'not_requested',
               'apply_failed_or_unconfirmed', 'committed_readback_unverified', 'initialized_readback_unverified', 'unverified'}
    if status not in allowed:
        status = 'unverified'
    change = receipt.get('change_id')
    operation = receipt.get('operation_id')
    upload = receipt.get('upload_id')
    return {'role': role, 'status': status,
            'reason_code': _code(receipt.get('reason') or receipt.get('failure_code') or receipt.get('publication_rule')),
            'change_id': change if isinstance(change, str) and re.fullmatch(r'dynchg_[a-f0-9]{32}', change) else None,
            'before_digest': _digest(receipt.get('before_digest')), 'after_digest': _digest(receipt.get('after_digest')),
            'readback_verified': receipt.get('readback_verified') is True,
            'history_verified': receipt.get('history_verified') is True,
            'upload_verified': receipt.get('upload_verified') is True,
            'no_change_verified': receipt.get('no_change_verified') is True,
            'write_attempted': receipt.get('write_attempted') is True or status in {
                'applied','initialized','committed_readback_unverified','initialized_readback_unverified'},
            'upload_id': upload if type(upload) is int and upload > 0 else None,
            'operation_id': operation if isinstance(operation, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,119}', operation) else None}


def outcome_for(states, request, *, agent_counts=None):
    subjects = []
    requested = request.memory_mode == 'apply'
    for state in states:
        candidate = state.get('memory_candidate')
        result = state['result']
        publication = state.get('publication', {})
        admission = result.get('memory_admission', {})
        checks = {key: value for key, value in publication.get('enrichment_checks', {}).items()
                  if key in {'selected_claim_critic_complete','selected_evidence_complete','current_profile_consolidated'}
                  and type(value) is bool}
        checks.update(candidate_present=candidate is not None,
            candidate_admitted=admission.get('status') == 'ready' and not admission.get('publication_withheld'),
            candidate_changed=state.get('candidate_changed') is True,
            publication_complete=publication.get('publication_complete') is True,
            coverage_complete=result.get('profile_coverage_complete') is True)
        metrics = {'candidate_char_count': len(candidate.markdown) if candidate is not None else 0,
                   'candidate_byte_count': len(candidate.markdown.encode('utf-8')) if candidate is not None else 0,
                   'selected_fact_count': len(candidate.fact_ids) if candidate is not None else 0,
                   'accepted_claim_count': result.get('accepted_claim_count', 0),
                   'section_coverage_count': result.get('required_section_coverage_count', 0)}
        proof = (state.get('critic') or {}).get('review_batching', {})
        if 'original_packet_count' in proof:
            metrics['critic_packet_count'] = proof['original_packet_count']
        if agent_counts is not None:
            metrics['critic_call_count'] = agent_counts(state['company_id']).get('evidence_critic', 0)
        metrics = {key: value for key,value in metrics.items() if type(value) is int and value >= 0}
        subjects.append({'subject_type': 'company', 'subject_id': state['company_id'],
            'effects': [effect_for(role, publication.get(name), requested=requested)
                        for role,name in [('company_memory_update','memory'),('company_methodology_update','methodology')]],
            'checks': checks, 'content_metrics': metrics,
            'admission_reason_code': _code(admission.get('rule')) or (
                'preparation_incomplete' if state.get('incomplete_schema_preview') else
                'candidate_missing' if candidate is None else None)})
    # The runtime owns durable delivery and composite finalization. This does
    # not grant a mutation, storage operation, provider call or paid retry.
    return {'schema_version': 'runtime_business_outcome.v1', 'publication_required': requested, 'subjects': subjects}
