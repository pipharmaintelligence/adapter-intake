from __future__ import annotations

import ast
from pathlib import Path


ADAPTER_PATH = (
    Path(__file__).resolve().parents[1]
    / 'adapters'
    / 'nusaibah'
    / 'agent_capability_lab'
    / 'nusaibah_agent_capability_lab_adapter.py'
)
README_PATH = ADAPTER_PATH.with_name('README.md')


FORMAT_NAMES = {
    'VERTEX_RESPONSE_FORMAT_ID',
    'VERTEX_FORMAT_SUMMARY',
    'VERTEX_FORMAT_UPDATES',
    'VERTEX_FORMAT_MEMORY_NOTE',
    'VERTEX_FORMAT_END',
    'VERTEX_FORMAT_BULLET_PREFIX',
    'VERTEX_FORMAT_SUMMARY_MIN_ITEMS',
    'VERTEX_FORMAT_SUMMARY_MAX_ITEMS',
    'VERTEX_FORMAT_UPDATES_MIN_ITEMS',
    'VERTEX_FORMAT_UPDATES_MAX_ITEMS',
}


def _contract_namespace() -> dict[str, object]:
    source = ADAPTER_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if names & FORMAT_NAMES:
                selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in {
            '_vertex_format_instructions',
            '_validate_vertex_response_format',
        }:
            selected.append(node)

    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {'Any': object}
    exec(compile(module, str(ADAPTER_PATH), 'exec'), namespace)
    return namespace


def _valid_text(*, summary_count: int = 2, update_count: int = 2) -> str:
    summary = '\n'.join(f'- summary {index}' for index in range(1, summary_count + 1))
    updates = '\n'.join(f'- update {index}' for index in range(1, update_count + 1))
    return '\n'.join(
        [
            'FORMAT_ID: capability_lab.vertex_grounded.v1',
            'SUMMARY:',
            summary,
            'VERIFIED_UPDATES:',
            updates,
            'MEMORY_NOTE:',
            'Evidence-based non-bullet note.',
            'END_FORMAT',
        ]
    )


def _assert_rejected(validate, text: str, expected_message: str) -> None:
    try:
        validate(text)
    except RuntimeError as exc:
        assert str(exc) == expected_message
    else:
        raise AssertionError('expected strict format rejection')


def test_0_1_15_source_and_documentation_declare_same_strict_grammar() -> None:
    source = ADAPTER_PATH.read_text(encoding='utf-8')
    readme = README_PATH.read_text(encoding='utf-8')

    assert 'version: ClassVar[str] = "0.1.15"' in source
    assert 'VERTEX_FORMAT_BULLET_PREFIX = "- "' in source
    assert 'Every item must be exactly one physical line' in source
    assert 'prompt grammar and validator grammar are one contract' in readme
    assert '`* `, `+ `, numbered bullets, continuation lines' in readme


def test_minimum_template_emitted_by_instruction_builder_passes_validator() -> None:
    namespace = _contract_namespace()
    instructions = namespace['_vertex_format_instructions']()
    validate = namespace['_validate_vertex_response_format']

    template = '\n'.join(instructions['minimum_valid_template'])
    evidence = validate(template)

    assert evidence['vertex_format_instruction_followed'] is True
    assert evidence['vertex_format_summary_bullet_count'] == 2
    assert evidence['vertex_format_update_bullet_count'] == 2


def test_valid_summary_and_update_bounds_pass() -> None:
    validate = _contract_namespace()['_validate_vertex_response_format']

    for summary_count in (2, 3, 4):
        for update_count in (2, 3, 6):
            evidence = validate(
                _valid_text(
                    summary_count=summary_count,
                    update_count=update_count,
                )
            )
            assert evidence['vertex_format_summary_bullet_count'] == summary_count
            assert evidence['vertex_format_update_bullet_count'] == update_count


def test_markdown_alternative_markers_are_rejected_by_strict_summary_protocol() -> None:
    validate = _contract_namespace()['_validate_vertex_response_format']
    base = _valid_text()
    expected = 'Vertex SUMMARY did not honor the required bullet format.'

    for marker in ('* ', '+ '):
        candidate = base.replace('- summary 1', f'{marker}summary 1').replace(
            '- summary 2',
            f'{marker}summary 2',
        )
        _assert_rejected(validate, candidate, expected)


def test_summary_continuation_and_count_violations_are_rejected() -> None:
    validate = _contract_namespace()['_validate_vertex_response_format']
    expected = 'Vertex SUMMARY did not honor the required bullet format.'

    continuation = _valid_text().replace(
        '- summary 1',
        '- summary 1\n  wrapped continuation',
    )
    _assert_rejected(validate, continuation, expected)
    _assert_rejected(validate, _valid_text(summary_count=1), expected)
    _assert_rejected(validate, _valid_text(summary_count=5), expected)


def test_update_count_violations_are_rejected() -> None:
    validate = _contract_namespace()['_validate_vertex_response_format']
    expected = 'Vertex VERIFIED_UPDATES did not honor the required bullet format.'

    _assert_rejected(validate, _valid_text(update_count=1), expected)
    _assert_rejected(validate, _valid_text(update_count=7), expected)


def test_memory_note_must_remain_non_bullet_prose() -> None:
    validate = _contract_namespace()['_validate_vertex_response_format']
    candidate = _valid_text().replace(
        'Evidence-based non-bullet note.',
        '- Evidence-based note.',
    )
    _assert_rejected(
        validate,
        candidate,
        'Vertex MEMORY_NOTE did not honor the required paragraph format.',
    )
