"""Retain useful draft prose after explicit, traceable sensitive-span redaction."""
from dataclasses import replace
from hashlib import sha256
import json
import re

from devtools.preview_output_validator import PreviewOutputValidationError

try:
    from .retention_v0_1_50 import preflight_publication as validate_candidates
    from .methodology_learning_v0_1_42 import fingerprint
except ImportError:
    from retention_v0_1_50 import preflight_publication as validate_candidates
    from methodology_learning_v0_1_42 import fingerprint

_PARAGRAPH = re.compile(r'<!-- profile_paragraph: (\d+):(\d+); verification: (verified|unverified) -->')
_GUIDANCE = re.compile(r'<!-- pharma-guidance:v1 (\{[^\n]*\}) -->')


def _refresh_guidance_ids(text):
    """Guidance identities must describe the sanitized advice that is published."""
    def rewrite(match):
        try:
            record = json.loads(match.group(1))
        except ValueError:
            return match.group()
        if record.get('schema_version') != 'pharma_future_research_guidance.v1':
            return match.group()
        original = {key: value for key, value in record.items() if key not in {'schema_version', 'guidance_id'}}
        record['guidance_id'] = fingerprint(original)
        return '<!-- pharma-guidance:v1 ' + json.dumps(record, ensure_ascii=True, separators=(',', ':')).replace('-->', '--\\u003e') + ' -->'
    return _GUIDANCE.sub(rewrite, text)


def _mark_changed_evidence(state, before, safe, receipt):
    """Never carry a fact attestation across a change to its supporting paragraph."""
    ranges = receipt['ranges']
    affected = set()
    covered = set()
    for match in _PARAGRAPH.finditer(before):
        end = before.find('\n\n', match.end())
        end = len(before) if end < 0 else end
        for index, span in enumerate(ranges):
            if span['start'] < end and span['end'] > match.end():
                affected.add((int(match.group(1)), int(match.group(2))))
                covered.add(index)
    # An unbounded receipt or changed evidence annex cannot be attributed to a
    # single paragraph safely. Preserve prose, remove all fact attestations.
    all_changed = receipt['additional_range_count'] > 0 or len(covered) != len(ranges)
    enrichment = state['result'].get('section_enrichment', {})
    removed = set()
    for paragraph in enrichment.get('paragraphs', []):
        coordinate = (paragraph.get('section_number'), paragraph.get('paragraph'))
        if all_changed or coordinate in affected:
            removed.update(paragraph['claim_ids'])
            paragraph['verification_status'] = 'unverified'
            paragraph['basis'] = 'sensitive_span_redaction'
            entry = {'section_number': coordinate[0], 'paragraph_number': coordinate[1]}
            if entry not in enrichment.setdefault('unverified_research', []):
                enrichment['unverified_research'].append(entry)
    candidate = state['memory_candidate']
    if all_changed:
        removed.update(candidate.fact_ids)
        if not enrichment.get('unverified_research'):
            enrichment['unverified_research'] = [{'reason': 'sensitive_span_redaction'}]
        safe = '**Unverified research after sensitive-span redaction.**\n\n' + safe
    def marker(match):
        coordinate = (int(match.group(1)), int(match.group(2)))
        if all_changed or coordinate in affected:
            return '<!-- profile_paragraph: ' + match.group(1) + ':' + match.group(2) + '; verification: unverified -->'
        return match.group()
    safe = _PARAGRAPH.sub(marker, safe)
    safe = re.sub(r'<!-- enrichment_fact: ([^\n]+) -->\n?',
                  lambda match: '' if match.group(1) in removed else match.group(), safe)
    state['memory_candidate'] = replace(candidate, markdown=safe,
        fact_ids=tuple(key for key in candidate.fact_ids if key not in removed))
    enrichment['added_fact_ids'] = [key for key in enrichment.get('added_fact_ids', []) if key not in removed]
    enrichment['verified_sections'] = list(dict.fromkeys(p['section_id'] for p in enrichment.get('paragraphs', [])
        if p.get('verification_status') == 'verified'))
    state['result']['verified_section_coverage_count'] = len(enrichment['verified_sections'])
    state['result']['verification_complete'] = False
    state['result']['redaction_affected_claim_count'] = len(removed)
    state['no_supported_enrichment'] = False
    document = state['result'].get('profile_document')
    if isinstance(document, dict):
        document.update(text=safe, paragraph_support=enrichment.get('paragraphs', []))
    return safe


def preflight_publication(states):
    from devtools.business_text_redaction import redact_business_text
    for state in states:
        candidate = state.get('memory_candidate')
        if candidate is None:
            continue
        receipts = {}
        for role, text in [('memory', candidate.markdown), ('methodology', state.get('methodology_learning_candidate'))]:
            if text is None:
                continue
            try:
                safe, receipt = redact_business_text(text)
            except PreviewOutputValidationError:
                # Existing admission owns unresolved cases. Do not silently
                # delete an unclassified paragraph or bypass required controls.
                continue
            if not receipt['redaction_count']:
                continue
            if role == 'memory':
                safe = _mark_changed_evidence(state, text, safe, receipt)
                state['candidate_changed'] = safe.strip() != (state.get('before_target_text') or '').strip()
            else:
                safe = _refresh_guidance_ids(safe)
                state['methodology_learning_candidate'] = safe
                state['result']['methodology_learning_proposal_digest'] = 'sha256:' + sha256(safe.encode()).hexdigest()
                state['result']['methodology_learning_rule_ids'] = [json.loads(m.group(1))['guidance_id'] for m in _GUIDANCE.finditer(safe)]
            receipt['after_sha256'] = sha256(safe.encode()).hexdigest()
            receipts[role] = receipt
        if receipts:
            state['result']['publication_redactions'] = receipts
    validate_candidates(states)
