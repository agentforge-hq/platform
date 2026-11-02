"""Export only the public read API and its reachable OpenAPI definitions."""

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import application

schema = application.openapi()
schema['paths'] = {
    '/api' + path: value for path, value in schema['paths'].items() if path in {'/v1/search', '/v1/catalog'}
}
schema['info']['description'] = 'Shared public search and browse contract for the website and native skill client.'
components = schema.get('components', {})
reachable: set[tuple[str, str]] = set()


def visit(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            visit(item)
    elif isinstance(value, dict):
        reference = value.get('$ref', '')
        if reference.startswith('#/components/'):
            _, _, section, name = reference.split('/')
            key = section, name
            if key not in reachable:
                reachable.add(key)
                visit(components[section][name])
        for item in value.values():
            visit(item)


visit(schema['paths'])
schema['components'] = {
    section: {name: value for name, value in entries.items() if (section, name) in reachable}
    for section, entries in components.items()
    if any((section, name) in reachable for name in entries)
}
Path('contracts/search.openapi.json').write_text(json.dumps(schema, indent=2) + '\n')
