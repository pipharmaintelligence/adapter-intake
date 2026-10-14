"""Use runtime grounding and readable exact spans without confusing their authority."""
from copy import deepcopy
import json
try:
    from .source_evidence_v0_1_39 import SourceEvidenceInputs as LiteralInputs, RESEARCH_ROLES
except ImportError:
    from source_evidence_v0_1_39 import SourceEvidenceInputs as LiteralInputs, RESEARCH_ROLES


def supported_native_locators(statement, result, admitted):
    """Map only explicit provider support text to its admitted grounding chunks.

    A provider segment is generated answer text, never a verbatim website quote.
    No guessed URLs, redirects, fuzzy matching, or title-based attribution.
    """
    locators=[]
    for turn in (result.get('provider_metadata') or {}).get('turns', []):
        if turn.get('provider_schema') != 'vertex.generate_content.metadata.v1':
            continue
        grounding=((turn.get('native') or {}).get('candidate') or {}).get('groundingMetadata') or {}
        chunks=grounding.get('groundingChunks') or []
        for support in grounding.get('groundingSupports') or []:
            segment=(support.get('segment') or {}).get('text')
            # JSON strings may be escaped in the provider's supported segment.
            if not isinstance(segment,str) or not any(s in segment for s in (statement,json.dumps(statement,ensure_ascii=False)[1:-1])):
                continue
            for index in support.get('groundingChunkIndices') or []:
                if type(index) is not int or not 0 <= index < len(chunks):
                    continue
                uri=(chunks[index].get('web') or {}).get('uri')
                if uri in admitted and uri not in locators:
                    locators.append(uri)
    return locators


class SourceEvidenceInputs(LiteralInputs):
    def verify_source_claims(self, payload, *, admitted=(), agent_result=None):
        value=deepcopy(payload)
        native={c.locator:c for c in admitted if c.source_kind=='agent_citation' and c.source_pointer}
        local={u['locator'] for u in self.units}
        literal=[]
        for claim in value['claims']:
            # A known local source must still pass the pinned exact-span toolkit.
            quotes=claim.get('evidence_quotes') or []
            if any(q.get('locator') in local for q in quotes):
                literal.append(claim)
                continue
            refs=[uri for uri in claim['citation_locators'] if uri in native]
            mapped=supported_native_locators(claim['statement'],agent_result or {},native)
            refs=list(dict.fromkeys(refs+mapped))
            if not refs:
                claim['_source_issue']='runtime_grounding_or_readable_source_missing'
                continue
            # Authoritative locators replace unadmitted model-written alternatives.
            claim['citation_locators']=refs
            claim['evidence_quotes']=[]
            claim['native_grounding']={
                'verification':'provider_grounding_pending_claim_critic',
                'literal_source_verified':False,
                'references':[{'locator':uri,'provider_family':native[uri].provider_family,
                    'provider_turn_index':native[uri].provider_turn_index,
                    'source_pointer':list(native[uri].source_pointer)} for uri in refs],
                'provider_support_matched':bool(mapped),
            }
        if literal:
            verified,_=super().verify_source_claims({**value,'claims':literal})
            by_id={c['claim_id']:c for c in verified['claims']}
            value['claims']=[by_id.get(c['claim_id'],c) for c in value['claims']]
        return value,tuple(self.citations)+tuple(native.values())
