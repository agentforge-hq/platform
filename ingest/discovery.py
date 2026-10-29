"""Bounded repository discovery via the first-party skills.sh search protocol."""

from __future__ import annotations

import json
import re
import urllib.parse
from collections.abc import Callable
from pathlib import Path

POLICY_PATH = Path(__file__).with_name('source-policy.json')
REPOSITORY_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*')


def load_policy(path: Path = POLICY_PATH) -> dict:
    policy = json.loads(path.read_text())
    if policy['version'] != 1 or not 1 <= policy['max_repositories'] <= 100 or not 1 <= policy['max_skills'] <= 2000:
        raise ValueError('Unsupported or unbounded source policy')
    registry = policy['registry']
    if registry['kind'] != 'skills.sh' or not 1 <= registry['result_limit'] <= 20 or len(registry['queries']) > 12:
        raise ValueError('Unsupported or unbounded registry policy')
    return policy


def discover(policy: dict, *, fetch: Callable, audit: Path) -> tuple[list[dict], list[dict]]:
    """Discover allowlisted repos, then enumerate their real directories on GitHub.

    A registry listing establishes discovery provenance, never package identity.
    Repeated queries and direct registrations merge into one repository entry.
    """
    selected: dict[str, dict] = {}
    for entry in policy['direct']:
        repository = entry['repository'].casefold()
        if not REPOSITORY_PATTERN.fullmatch(repository):
            raise ValueError('Invalid GitHub repository in source policy')
        selected[repository] = {
            **entry,
            'repository': repository,
            'discovered_via': [f'https://github.com/{repository}'],
        }
    registry = policy['registry']
    allowed = {entry['repository'].casefold(): entry for entry in registry['allowed_repositories']}
    errors = []
    audit.mkdir(parents=True, exist_ok=True)
    for index, query in enumerate(registry['queries']):
        params = {'q': query['query'], 'limit': registry['result_limit']}
        if query.get('owner'):
            params['owner'] = query['owner']
        url = 'https://skills.sh/api/search?' + urllib.parse.urlencode(params)
        try:
            raw = fetch(url, limit=512_000)
            data = json.loads(raw)
            if not isinstance(data.get('skills'), list) or len(data['skills']) > registry['result_limit']:
                raise ValueError('Unexpected registry response')
            (audit / f'registry-{index}.json').write_bytes(raw)
            for result in data['skills']:
                repository = str(result.get('source', '')).casefold()
                if not REPOSITORY_PATTERN.fullmatch(repository) or repository not in allowed:
                    continue
                if repository not in selected:
                    selected[repository] = {**allowed[repository], 'repository': repository, 'discovered_via': []}
                if url not in selected[repository]['discovered_via']:
                    selected[repository]['discovered_via'].append(url)
        except Exception as exc:
            errors.append({'source': url, 'error': type(exc).__name__})
    if len(selected) > policy['max_repositories']:
        raise ValueError('Repository discovery exceeds policy; refusing an incomplete refresh')
    # Missing an allowlisted registry source is not evidence of withdrawal.
    for repository in sorted(allowed.keys() - selected.keys()):
        errors.append({'source': repository, 'error': 'RegistrySourceNotResolved'})
    return sorted(selected.values(), key=lambda entry: entry['repository']), errors
