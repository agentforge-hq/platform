"""Fetch public SKILL.md manifests without executing their content."""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pixeltable as pxt
import yaml

from agentforge_backend.models import Skill

REPOSITORIES = ['anthropics/skills', 'openai/skills', 'vercel-labs/agent-skills', 'obra/superpowers', 'pbakaus/impeccable', 'blader/humanizer']
REPOSITORY_SKILL_ROOTS = {'pbakaus/impeccable': ['.agents/skills/']}
EXAMPLES = {
    'frontend-design': ['Build a distinctive landing page for my product.', 'Make this interface feel polished and easy to use.'],
    'humanizer': ['Make my writing sound like a person wrote it.', 'Remove the generic AI phrasing from this draft.'],
    'skill-creator': ['Turn our recurring workflow into a reusable agent skill.'],
    'pdf': ['Extract the tables from this PDF and check the layout.'],
    'docx': ['Create a professional Word document from these notes.'],
    'pptx': ['Turn my research into a presentation.'],
    'xlsx': ['Analyze this spreadsheet and explain the trends.'],
    'webapp-testing': ['Test my web app in a real browser and find broken interactions.'],
    'systematic-debugging': ['Find the root cause of this bug before changing the code.'],
    'brainstorming': ['Help me think through the approach before I start building.'],
    'writing-plans': ['Turn this idea into an implementation plan.'],
    'react-best-practices': ['Find unnecessary rerenders and slow loading in my React app.'],
    'vercel-react-best-practices': ['Make my React app faster and reduce its bundle size.'],
    'web-design-guidelines': ['Review my website for accessibility and usability problems.'],
}


def fetch(url: str, *, token: str | None = None, limit: int = 2_000_000) -> bytes:
    headers = {'User-Agent': 'AgentForge/0.1 (public skill catalog)', 'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError('Source exceeds the configured size limit')
    return body


def category(name: str, description: str) -> str:
    text = name.casefold()
    groups = {
        'Design': ['design', 'frontend', 'canvas', 'theme', 'brand', 'ui-', 'impeccable', 'animate', 'typeset', 'polish'],
        'Writing': ['writing', 'humaniz', 'copy', 'docx', 'content', 'comms', 'doc-coauthor'],
        'Research': ['research', 'pdf', 'spreadsheet', 'xlsx', 'data', 'analysis'],
        'Engineering': ['code', 'react', 'test', 'debug', 'git', 'deploy', 'mcp', 'python', 'security', 'develop', 'vercel', 'webapp'],
        'Operations': ['plan', 'brainstorm', 'meeting', 'skill', 'agent', 'workflow', 'task', 'business'],
    }
    for group, words in groups.items():
        if any(word in text for word in words):
            return group
    return 'General'


def parse_manifest(*, raw: bytes, repository: str, revision: str, path: str, license_id: str | None, checked_at: str) -> tuple[Skill, str]:
    text = raw.decode('utf-8')
    if not text.startswith('---'):
        raise ValueError('Missing skill metadata')
    parts = re.split(r'^---\s*$', text, maxsplit=2, flags=re.M)
    if len(parts) != 3:
        raise ValueError('Incomplete skill metadata')
    metadata = yaml.safe_load(parts[1])
    if not isinstance(metadata, dict):
        raise ValueError('Metadata must be a mapping')
    name = metadata.get('name')
    description = metadata.get('description')
    if not isinstance(name, str) or not isinstance(description, str) or not name.strip() or not description.strip():
        raise ValueError('A skill needs a name and description')
    name = name.strip()[:120]
    summary = ' '.join(description.split())[:1800]
    own_license = metadata.get('license')
    if isinstance(own_license, str):
        license_id = own_license if re.fullmatch(r'[A-Za-z0-9.\-+]+', own_license) else None
    if license_id in {'NOASSERTION', 'OTHER'}:
        license_id = None
    directory = str(Path(path).parent)
    skill_id = f'{repository}/{directory}'
    prompts = EXAMPLES.get(name, [f'Help me with {name.replace("-", " ")}.'])
    requirements = []
    if isinstance(metadata.get('compatibility'), str):
        requirements.append(metadata['compatibility'][:300])
    skill = Skill(
        skill_id=skill_id, name=name, summary=summary, category=category(name, summary),
        capabilities=[summary.split('. ')[0][:240]], example_prompts=prompts,
        requirements=requirements, exclusions=[], compatibility={'harness': 'portable', 'status': 'unknown'},
        license={'identifier': license_id, 'status': 'declared' if license_id else 'unknown'},
        source={
            'url': f'https://github.com/{repository}/tree/{revision}/{urllib.parse.quote(directory)}',
            'repository': repository, 'revision': revision, 'skill_path': directory,
            'manifest_sha256': hashlib.sha256(raw).hexdigest(), 'checked_at': checked_at,
        },
        adoption_status='review_required' if license_id else 'metadata_only',
    )
    return skill, parts[2]


def collect(*, repositories: list[str], destination: Path) -> dict:
    token_result = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True)
    token = token_result.stdout.strip() if token_result.returncode == 0 else None
    checked = dt.datetime.now(dt.UTC).isoformat().replace('+00:00', 'Z')
    tasks: list[tuple[str, str, str, str | None]] = []
    errors: list[dict] = []
    for repository in repositories:
        info = json.loads(fetch(f'https://api.github.com/repos/{repository}', token=token))
        commit = json.loads(fetch(f'https://api.github.com/repos/{repository}/commits/{info["default_branch"]}', token=token))['sha']
        tree = json.loads(fetch(f'https://api.github.com/repos/{repository}/git/trees/{commit}?recursive=1', token=token))
        if tree.get('truncated'):
            raise ValueError(f'The source tree is incomplete: {repository}')
        license_id = (info.get('license') or {}).get('spdx_id')
        paths = [item['path'] for item in tree.get('tree', []) if item['type'] == 'blob' and (item['path'] == 'SKILL.md' or item['path'].endswith('/SKILL.md')) and '.deprecated/' not in item['path']]
        paths = [path for path in paths if not any(part in {'tests', 'fixtures', 'testdata', 'node_modules'} for part in path.split('/'))]
        if repository in REPOSITORY_SKILL_ROOTS:
            paths = [path for path in paths if any(path.startswith(root) for root in REPOSITORY_SKILL_ROOTS[repository])]
        if len(paths) > 100:
            raise ValueError(f'Source exceeds the 100-skill collection limit; refusing an incomplete refresh: {repository}')
        tasks.extend((repository, commit, path, license_id) for path in paths)
    rows = []
    def one(task):
        repository, revision, path, license_id = task
        raw = fetch(f'https://raw.githubusercontent.com/{repository}/{revision}/{urllib.parse.quote(path)}', limit=128_000)
        skill, body = parse_manifest(raw=raw, repository=repository, revision=revision, path=path, license_id=license_id, checked_at=checked)
        return {
            'version_id': skill.skill_id + '@' + revision,
            'skill_id': skill.skill_id, 'name': skill.name, 'description': skill.summary,
            'body': body, 'examples': skill.example_prompts, 'payload': skill.model_dump(),
        }
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(one, task): task for task in tasks}
        for future in concurrent.futures.as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append({'source': futures[future][0], 'path': futures[future][2], 'error': type(exc).__name__})
    rows.sort(key=lambda row: row['skill_id'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(rows, ensure_ascii=False))
    destination.with_suffix('.summary.json').write_text(json.dumps({'complete_repositories': repositories if not errors else [], 'errors': errors}))
    return {'skills': len(rows), 'repositories': len(repositories), 'errors': errors, 'checked_at': checked}


def publish(*, target: str, snapshot: Path) -> dict:
    separator = '/' if target.startswith('pxt://') else '.'
    sources = pxt.get_table(target + separator + 'sources')
    versions = pxt.get_table(target + separator + 'skill_versions')
    rows = json.loads(snapshot.read_text())
    existing = {row['version_id'] for row in versions.select(versions.version_id).collect()}
    pending = [row for row in rows if row['version_id'] not in existing]
    # Publish pointers only after the entire batch and its embeddings succeed.
    for start in range(0, len(pending), 20):
        versions.insert(pending[start:start + 20])
    pointers = [{'skill_id': row['skill_id'], 'published_version': row['version_id'], 'checked_at': row['payload']['source']['checked_at']} for row in rows]
    if pointers:
        sources.batch_update(pointers, if_not_exists='insert')
    return {'published': len(pointers), 'new_versions': len(pending), 'target': target}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['collect', 'publish', 'refresh-http'])
    parser.add_argument('--snapshot', type=Path, default=Path('.audit/catalog-source.json'))
    parser.add_argument('--target', default='agentforge_dev')
    parser.add_argument('--repo', action='append')
    args = parser.parse_args()
    if args.action == 'collect':
        result = collect(repositories=args.repo or REPOSITORIES, destination=args.snapshot)
        if result['errors']:
            print(json.dumps(result)); raise SystemExit('Collection incomplete; publication refused.')
    elif args.action == 'publish':
        result = publish(target=args.target, snapshot=args.snapshot)
    else:
        import os
        summary = json.loads(args.snapshot.with_suffix('.summary.json').read_text())
        if summary['errors'] or not summary['complete_repositories']:
            raise SystemExit('A complete source collection is required for refresh.')
        payload = {'rows': json.loads(args.snapshot.read_text()), 'complete_repositories': summary['complete_repositories']}
        req = urllib.request.Request(os.environ['AGENTFORGE_REFRESH_URL'], data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'X-api-key': os.environ['AGENTFORGE_REFRESH_SERVICE_KEY'], 'X-AgentForge-Index-Key': os.environ['AGENTFORGE_INDEX_TOKEN']})
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.load(response)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
