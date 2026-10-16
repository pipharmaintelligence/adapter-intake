"""Independent Skill candidate admission and bounded workflow report projection.

No storage operations live here. Dynamic Skills own memory publication; the
shared runtime sends the resulting report to Core's artifact retention lane.
"""
from copy import deepcopy
from hashlib import sha256
import json

from devtools.preview_output_validator import validate_preview_outputs, PreviewOutputValidationError

REPORT_BYTES = 1760 * 1024
OUTPUT_BYTES = 2 * 1024 * 1024


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def preflight_publication(states):
    """Only candidate safety can veto publication, never report diagnostics.

The existing publisher still checks evidence, critic verdicts, package/content
baselines, governed mutable roles, write receipts and fresh readback/history.
"""
    for state in states:
        candidate = state.get('memory_candidate')
        if candidate is None:
            continue
        try:
            validate_preview_outputs({'proposed_skills': {
                'memory_text': candidate.markdown,
                'methodology_text': state.get('methodology_learning_candidate')}})
        except PreviewOutputValidationError as error:
            state['incomplete_schema_preview'] = True
            state['no_supported_enrichment'] = False
            state['result']['memory_admission'] = {
                'status': 'blocked', 'rule': error.rule,
                'path': error.safe_path, 'publication_withheld': True}
        else:
            state['result']['memory_admission'] = {
                'status': 'ready', 'exact_candidate_validated': True,
                'publication_withheld': bool(state.get('incomplete_schema_preview'))}


def prepare_report(states, coordinator):
    for state in states:
        state['result']['agent_input_preflight'] = coordinator.proof()


# Publication truth and operator continuation must survive report compaction.
# Content is retained preferentially, but the report is not canonical memory.
ESSENTIAL = frozenset({
    'company_id', 'status', 'skill_publication', 'business_result_state',
    'memory_update_status', 'methodology_learning_update_status',
    'memory_change_id', 'memory_after_digest', 'memory_readback_verified',
    'memory_history_verified', 'methodology_learning_change_id',
    'methodology_learning_after_digest', 'methodology_learning_readback_verified',
    'methodology_learning_history_verified', 'memory_admission',
    'accepted_claim_count', 'research_incomplete', 'retention_admission',
})


def retain_dossier(dossier, maximum=REPORT_BYTES):
    """Project report copies only; never mutate canonical candidates or receipts.

Whole optional fields may be omitted with a byte count and hash. No paragraph
is sliced and no unsafe content is reclassified to bypass validation. Ordinary
reports retain all safe fields; oversized reports retain publication truth.
"""
    result = deepcopy(dossier)
    omissions = []
    def omit(container, key, company_id, reason):
        raw = encode(container.pop(key))
        omissions.append({'company_id': company_id,
                          'field_sha256': sha256(key.encode()).hexdigest(),
                          'size_bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
                          'reason': reason})

    rows = result['company_results']
    for row in rows:
        for key, value in list(row.items()):
            try:
                validate_preview_outputs({'intelligence_dossier': {key: value}})
            except PreviewOutputValidationError:
                if key in ESSENTIAL:
                    # A corrupt publication receipt is not evidence of success.
                    raise
                omit(row, key, row['company_id'], 'output_validation')
    for key in ('research_response_observations', 'agent_invocation_response_issues'):
        try:
            validate_preview_outputs({'intelligence_dossier': {key: result.get(key)}})
        except PreviewOutputValidationError:
            omit(result, key, None, 'output_validation')

    admission = {'status': 'complete', 'publication_independent': True,
                 'candidate_truncated': False, 'omitted_fields': omissions}
    result['report_retention'] = admission
    # Remove bulky diagnostic/source copies first; keep the profile until last.
    fields = [(result, key, None) for key in
              ('research_response_observations', 'agent_invocation_response_issues') if key in result]
    fields += [(row, key, row['company_id']) for row in rows for key in row
               if key not in ESSENTIAL and key != 'profile_document']
    fields.sort(key=lambda entry: len(encode(entry[0][entry[1]])), reverse=True)
    fields += [(row, 'profile_document', row['company_id']) for row in rows if 'profile_document' in row]
    for container, key, company_id in fields:
        if len(encode(result)) <= maximum:
            break
        omit(container, key, company_id, 'report_size_budget')
        admission['status'] = 'complete_with_omissions'
    if omissions:
        admission['status'] = 'complete_with_omissions'
    validate_preview_outputs({'intelligence_dossier': result})
    if len(encode(result)) > maximum or len(encode({'intelligence_dossier': result})) > OUTPUT_BYTES:
        raise ValueError('retention_receipt_budget_invalid')
    return result
