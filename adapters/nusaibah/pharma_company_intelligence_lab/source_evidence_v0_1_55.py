"""Bound native evidence expansion without weakening source or claim authority."""
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
import json

try:
    from .source_evidence_v0_1_39 import SourceEvidenceInputs as LiteralInputs, RESEARCH_ROLES
    from .claim_evidence_contract_v0_1_21 import MAX_CITATION_REFS_PER_CLAIM, MAX_QUALIFIERS_PER_CLAIM, MAX_QUALIFIER_CHARS
except ImportError:
    from source_evidence_v0_1_39 import SourceEvidenceInputs as LiteralInputs, RESEARCH_ROLES
    from claim_evidence_contract_v0_1_21 import MAX_CITATION_REFS_PER_CLAIM, MAX_QUALIFIERS_PER_CLAIM, MAX_QUALIFIER_CHARS


def supported_native_locators(statement, result, admitted):
    """Return explicit admitted support, stopping at the first over-budget URI.

    Provider segments remain generated text, not source quotations. A sentinel
    25th URI proves overflow; callers withhold the claim rather than truncate it
    into accepted evidence. Malformed optional metadata confers no authority.
    """
    locators = []
    seen = set()
    if not isinstance(result, Mapping):
        return locators
    metadata = result.get('provider_metadata')
    if not isinstance(metadata, Mapping):
        return locators
    turns = metadata.get('turns')
    if not isinstance(turns, list):
        return locators
    spellings = (statement, json.dumps(statement, ensure_ascii=False)[1:-1])
    for turn in turns:
        if not isinstance(turn, Mapping) or turn.get('provider_schema') != 'vertex.generate_content.metadata.v1':
            continue
        native = turn.get('native')
        candidate = native.get('candidate') if isinstance(native, Mapping) else None
        grounding = candidate.get('groundingMetadata') if isinstance(candidate, Mapping) else None
        if not isinstance(grounding, Mapping):
            continue
        chunks, supports = grounding.get('groundingChunks'), grounding.get('groundingSupports')
        if not isinstance(chunks, list) or not isinstance(supports, list):
            continue
        for support in supports:
            if not isinstance(support, Mapping):
                continue
            segment = support.get('segment')
            text = segment.get('text') if isinstance(segment, Mapping) else None
            indices = support.get('groundingChunkIndices')
            if not isinstance(text, str) or not isinstance(indices, list) or not any(s in text for s in spellings):
                continue
            for index in indices:
                if type(index) is not int or not 0 <= index < len(chunks):
                    continue
                chunk = chunks[index]
                web = chunk.get('web') if isinstance(chunk, Mapping) else None
                uri = web.get('uri') if isinstance(web, Mapping) else None
                if isinstance(uri, str) and uri in admitted and uri not in seen:
                    seen.add(uri)
                    locators.append(uri)
                    if len(locators) > MAX_CITATION_REFS_PER_CLAIM:
                        return locators
    return locators


def withhold_claim(claim, observations, *, rule, field, observed_count=None, allowed_count=None):
    """Discard no sibling claim; expose only bounded, content-free diagnostics."""
    claim['_source_issue'] = claim.get('_source_issue') or rule
    claim['citation_locators'] = []
    claim['evidence_quotes'] = []
    claim.pop('native_grounding', None)
    claim.pop('source_spans', None)
    observation = {'status': 'claim_withheld', 'phase': 'claim_evidence_bounds',
                   'rule': rule, 'field': field,
                   'claim_id_sha256': sha256(str(claim.get('claim_id', '')).encode()).hexdigest()}
    if observed_count is not None:
        observation['observed_count_at_least'] = observed_count
    if allowed_count is not None:
        observation['allowed_count'] = allowed_count
    observations.append(observation)


def enforce_claim_field_bounds(claim, observations):
    """Keep post-transform leaf fields within the existing strict index bounds."""
    for field, limit, chars, invalid, overflow in (
        ('citation_locators', MAX_CITATION_REFS_PER_CLAIM, None,
         'claim_citation_locator_invalid', 'claim_citation_locator_budget_exceeded'),
        ('evidence_qualifiers', MAX_QUALIFIERS_PER_CLAIM, MAX_QUALIFIER_CHARS,
         'claim_evidence_qualifier_invalid', 'claim_evidence_qualifier_budget_exceeded'),
    ):
        value = claim.get(field, [])
        over = isinstance(value, list) and len(value) > limit
        bad = not isinstance(value, list) or not over and any(
            not isinstance(item, str) or not item.strip()
            or any(ord(c) < 0x20 or ord(c) == 0x7f for c in item.strip())
            or chars is not None and len(item.strip()) > chars
            for item in value
        )
        if bad or over:
            withhold_claim(claim, observations, rule=overflow if over else invalid,
                           field=field, observed_count=len(value) if isinstance(value, list) else None,
                           allowed_count=limit)
            # A withheld field must also be safe for the unchanged index parser.
            claim['evidence_qualifiers'] = []
            return False
    return True


class SourceEvidenceInputs(LiteralInputs):
    def verify_source_claims(self, payload, *, admitted=(), agent_result=None):
        value = deepcopy(payload)
        native = {c.locator: c for c in admitted if c.source_kind == 'agent_citation' and c.source_pointer}
        local = {u['locator'] for u in self.units}
        literal = []
        for claim in value['claims']:
            if not enforce_claim_field_bounds(claim, self.observations):
                continue
            quotes = claim.get('evidence_quotes') or []
            if any(q.get('locator') in local for q in quotes):
                literal.append(claim)
                continue
            refs = list(dict.fromkeys(uri for uri in claim['citation_locators'] if uri in native))
            mapped = supported_native_locators(claim['statement'], agent_result or {}, native)
            refs = list(dict.fromkeys(refs + mapped))
            if len(refs) > MAX_CITATION_REFS_PER_CLAIM:
                withhold_claim(claim, self.observations, rule='claim_citation_locator_budget_exceeded',
                               field='citation_locators', observed_count=len(refs),
                               allowed_count=MAX_CITATION_REFS_PER_CLAIM)
                continue
            if not refs:
                claim['_source_issue'] = 'runtime_grounding_or_readable_source_missing'
                continue
            claim['citation_locators'] = refs
            claim['evidence_quotes'] = []
            claim['native_grounding'] = {
                'verification': 'provider_grounding_pending_claim_critic',
                'literal_source_verified': False,
                'references': [{'locator': uri, 'provider_family': native[uri].provider_family,
                    'provider_turn_index': native[uri].provider_turn_index,
                    'source_pointer': list(native[uri].source_pointer)} for uri in refs],
                'provider_support_matched': bool(mapped),
            }
        if literal:
            verified, _ = LiteralInputs.verify_source_claims(self, {**value, 'claims': literal})
            by_id = {c['claim_id']: c for c in verified['claims']}
            value['claims'] = [by_id.get(c['claim_id'], c) for c in value['claims']]
        return value, tuple(self.citations) + tuple(native.values())
