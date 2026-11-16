"""Select production closure plus the separate deterministic fixture's imports."""
import ast


def fixture_support_files(module, fixture_name):
    from devtools.adapter_catalog import _local_support_files
    root = module.parent.resolve()
    tests = root / 'tests'
    support = set(_local_support_files(module))
    pending = [tests / (fixture_name + '.py')]
    visited = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        tree = ast.parse(current.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for name in names:
                stem = name.split('.')[0]
                fixture = tests / (stem + '.py')
                local = root / (stem + '.py')
                if fixture.is_file():
                    pending.append(fixture)
                elif local.is_file() and local != module:
                    support.add(local)
                    support.update(_local_support_files(local))
    support.discard(module.resolve())
    return tuple(sorted(support))
