"""Generate Python prompt constants for SDK wheels and asset bundles.

The reviewed Markdown remains the editable source. Runtime imports never require
development prose files to be present in a package archive.
"""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("trial_researcher", "literature_researcher", "event_researcher",
         "outcome_adjudicator", "hypothesis_analyst", "evidence_critic", "product_memory_editor")


def render():
    header = ('"""Generated prompt constants; edit prompt_*.md and run tests/build_prompt_catalog.py.\n'
              '\nExact text and role digests are checked by the provider-free package tests.\n"""\n'
              'PROMPT_VERSION = "1.2.0"\n\n')
    def literal(value, indent):
        return '\n'.join(indent + repr(line) for line in value.splitlines(keepends=True))
    common = (ROOT / 'prompt_common.md').read_text(encoding='utf-8')
    value = header + 'COMMON_PROMPT = (\n' + literal(common, '    ') + '\n)\n\nPROMPTS = {\n'
    for role in ROLES:
        prompt = (ROOT / ('prompt_' + role + '.md')).read_text(encoding='utf-8')
        value += '    ' + repr(role) + ': (\n' + literal(prompt, '        ') + '\n    ),\n'
    return value + '}\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    target = ROOT / 'prompt_catalog.py'
    value = render()
    if args.check:
        if target.read_text(encoding='utf-8') != value:
            raise SystemExit('Prompt catalog is stale; run tests/build_prompt_catalog.py.')
    else:
        target.write_text(value, encoding='utf-8')


if __name__ == '__main__':
    main()
