"""Select complete case-critical windows; never infer clinical verdicts from text."""
import json
import re


def case_context_ids(evidence, trial_ids=None):
    """Share identity/status/primary-result sources across otherwise local batches.

    Every selected item remains an original whole evidence window. PRIMARY is
    read only from a typed registry outcome declaration, never a lexical guess.
    Model-assessed claims and outcome acceptance remain separate responsibilities.
    """
    allowed=set(trial_ids or [])
    rows=[row for row in evidence if not allowed or set(row.get('trial_ids',[])) & allowed]
    def identity(row):
        context=row.get('source_context') or {}
        return (context.get('source_result_id') or row['source_id'],tuple(row.get('trial_ids',[])))
    primary=[];selected=set()
    modules={'identificationModule','statusModule','descriptionModule','designModule'}
    for row in rows:
        context=row.get('source_context') or {};pointer=context.get('source_pointer','')
        if pointer.startswith('/registry_study/protocolSection/') and pointer.rsplit('/',1)[-1] in modules:
            selected.add(row['evidence_id'])
        if (context.get('evidence_use')=='publication_text' and context.get('purpose')=='case'):
            selected.add(row['evidence_id'])
        if re.fullmatch(r'/registry_study/resultsSection/outcomeMeasuresModule/outcomeMeasures/[0-9]+',pointer):
            try:value=json.loads(row['text'])
            except (ValueError,TypeError):continue
            if isinstance(value,dict) and value.get('type')=='PRIMARY':
                primary.append((identity(row),pointer));selected.add(row['evidence_id'])
    for row in rows:
        pointer=(row.get('source_context') or {}).get('source_pointer','')
        if any(identity(row)==source and pointer.startswith(root+'/') for source,root in primary):
            selected.add(row['evidence_id'])
    return selected


def evidence_breadth(evidence):
    """Report source breadth without equating window count with corroboration."""
    counts={};publications=set()
    for row in evidence:
        kind=row.get('source_type','unknown');counts[kind]=counts.get(kind,0)+1
        context=row.get('source_context') or {};ids=context.get('identifiers') or {}
        if ids.get('pmid'):publications.add(str(ids['pmid']))
    return {'window_counts_by_source_type':counts,'identified_publication_count':len(publications),
        'publication_breadth_status':'limited' if len(publications)<2 else 'multiple_records_not_independent_verification',
        'recommended_source_followups':(['Seek scoped original mechanistic and exposure/biomarker evidence, including contrary findings.'] if len(publications)<2 else []),
        'independent_verification_claimed':False,
        'limitations':['Source windows are not independent studies.','Source support and causal validation are separate assessments.']}
