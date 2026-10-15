"""Carry forward current business paragraphs once; Core owns historical versions."""
from hashlib import sha256
import html
import re
try:
    from .profile_rendering_v0_1_42 import BUSINESS_SECTIONS
    from .dossier_contract import SECTION_BY_ID
except ImportError:
    from profile_rendering_v0_1_42 import BUSINESS_SECTIONS
    from dossier_contract import SECTION_BY_ID


def prose_key(text):
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    text = re.sub(r'\[R\d+\]', '', text)
    text = re.sub(r'^\s*\*\*Unverified research\.\*\*\s*', '', text)
    # Numeric signs, decimal separators, dates and uncertainty are meaningful.
    return ' '.join(html.unescape(re.sub(r'\\([_*`\[\]])', r'\1', text)).casefold().split()).strip('. ')


def current_memory_records(before, incoming, paragraphs):
    """Never read Previous Memory recursively or promote old text to fresh evidence."""
    current = re.split(r'(?m)^#{1,6}\s+Annex:', before or '', maxsplit=1)[0]
    first_generation = (before or '').split('### Annex: Previous Memory', 1)[0]
    refs = {m.group(1): m.group(2).strip().strip('<>')
            for m in re.finditer(r'(?m)^\[(R\d+)\]\s+(.+)$', first_generation)}
    known = {prose_key(c['statement']) for c in incoming}
    known.update(prose_key(p['text']) for p in paragraphs)
    titles = {SECTION_BY_ID[s].title.casefold(): s for s in BUSINESS_SECTIONS}
    section = 'company_profile'
    records = []
    for block in re.split(r'\n\s*\n', current):
        heading = re.match(r'^\s*#{1,6}\s+(.+)', block)
        if heading:
            title = re.sub(r'^\d+\.\s*', '', heading.group(1).strip()).casefold()
            section = titles.get(title, section)
            continue
        text = re.sub(r'<!--.*?-->', '', block, flags=re.S).strip()
        locators = list(dict.fromkeys(refs[key] for key in re.findall(r'\[(R\d+)\]', text) if key in refs))
        text = re.sub(r'\s*\[R\d+\]', '', text).strip()
        text = re.sub(r'^\*\*Unverified research\.\*\*\s*', '', text)
        text = html.unescape(re.sub(r'\\([_*`\[\]])', r'\1', text))
        if not text or text.startswith('Research did not establish a useful finding'):
            continue
        key = prose_key(text)
        if not key or key in known:
            continue
        known.add(key)
        records.append({'claim_id': 'memory:' + sha256((section+'|'+key).encode()).hexdigest(),
                        'section_id': section, 'statement': text, 'citation_locators': locators,
                        'evidence_qualifiers': [], 'verification_status': 'unverified',
                        'verification_reason': 'prior_memory_not_independently_reverified',
                        'memory_provenance': 'previous_current_profile'})
    return records
