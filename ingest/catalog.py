"""Fetch public SKILL.md packages without executing their content."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from agentforge_backend.models import Skill, SourceFile
from agentforge_backend.profiles import extract_profile, strings
from agentforge_backend.publish import PublishRequest, VersionInput, publish_rows, version_id_for
from ingest.discovery import POLICY_PATH, REPOSITORY_PATTERN, discover, load_policy

REPOSITORIES = [entry['repository'] for entry in load_policy()['direct']]


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
        'Design': [
            'design',
            'frontend',
            'canvas',
            'theme',
            'brand',
            'ui-',
            'impeccable',
            'animate',
            'typeset',
            'polish',
        ],
        'Writing': ['writing', 'humaniz', 'copy', 'docx', 'content', 'comms', 'doc-coauthor'],
        'Research': ['research', 'pdf', 'spreadsheet', 'xlsx', 'data', 'analysis'],
        'Engineering': [
            'code',
            'react',
            'test',
            'debug',
            'git',
            'deploy',
            'mcp',
            'python',
            'security',
            'develop',
            'vercel',
            'webapp',
            'azure',
            'api',
            'sdk',
        ],
        'Operations': ['plan', 'brainstorm', 'meeting', 'skill', 'agent', 'workflow', 'task', 'business'],
    }
    for group, words in groups.items():
        if any(word in text for word in words):
            return group
    if re.search(r'(?i)\b(?:SDK|API|cloud|software|programming|compiler|deployment|security audit)\b', description):
        return 'Engineering'
    return 'General'


def json_metadata(value: Any, depth: int = 0, budget: list[int] | None = None) -> Any:
    """YAML dates become ISO strings; unsupported values and recursive aliases fail."""
    if budget is None:
        budget = [4096, 16384]
    budget[0] -= 1
    budget[1] -= len(value.encode()) if isinstance(value, str) else 0
    if min(budget) < 0:
        raise ValueError('Metadata exceeds the supported size bound')
    if depth > 12:
        raise ValueError('Metadata nesting exceeds the supported bound')
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [json_metadata(item, depth + 1, budget) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        budget[1] -= sum(len(key.encode()) for key in value)
        if budget[1] < 0:
            raise ValueError('Metadata exceeds the supported size bound')
        return {key: json_metadata(item, depth + 1, budget) for key, item in value.items()}
    raise ValueError('Metadata must contain JSON-compatible values or YAML dates')


def parse_manifest(
    *, raw: bytes, repository: str, revision: str, path: str, license_id: str | None, checked_at: str
) -> tuple[Skill, str]:
    text = raw.decode('utf-8')
    match = re.match(r'\A---\s*\n(.*?)^---\s*\n?', text, flags=re.M | re.S)
    if not match:
        raise ValueError('Missing or incomplete skill metadata')
    metadata = yaml.safe_load(match[1])
    if not isinstance(metadata, dict):
        raise ValueError('Metadata must be a mapping')
    name, description = metadata.get('name'), metadata.get('description')
    if not isinstance(name, str) or not isinstance(description, str) or not name.strip() or not description.strip():
        raise ValueError('A skill needs a name and description')
    author_metadata = json_metadata(metadata)
    json.dumps(author_metadata, allow_nan=False)
    name = name.strip()[:120]
    summary = ' '.join(description.split())[:1800]
    own_license = metadata.get('license')
    if isinstance(own_license, str):
        license_id = own_license if re.fullmatch(r'[A-Za-z0-9.\-+]+', own_license) else None
    if license_id in {'NOASSERTION', 'OTHER'}:
        license_id = None
    directory = str(PurePosixPath(path).parent)
    repository = repository.casefold()
    skill_id = f'{repository}/{directory}'
    source_url = f'https://github.com/{repository}/tree/{revision}/{urllib.parse.quote(directory)}'
    body = text[match.end() :]
    profile, prompts, requirements, support = extract_profile(
        metadata=metadata,
        body=body,
        revision=revision,
        source_url=source_url,
        path=path,
        line_offset=text[: match.end()].count('\n'),
    )
    skill = Skill(
        skill_id=skill_id,
        name=name,
        summary=summary,
        category=category(name, summary),
        author_metadata=author_metadata,
        capabilities=strings(metadata.get('capabilities')) or profile.use_when[:6],
        example_prompts=prompts,
        requirements=requirements,
        exclusions=profile.avoid_when,
        compatibility={'harness': 'portable', 'status': 'unknown'},
        profile=profile,
        harness_support=support,
        license={'identifier': license_id, 'status': 'declared' if license_id else 'unknown'},
        source={
            'url': source_url,
            'repository': repository,
            'revision': revision,
            'skill_path': directory,
            'manifest_sha256': hashlib.sha256(raw).hexdigest(),
            'checked_at': checked_at,
        },
        adoption_status='review_required' if license_id else 'metadata_only',
    )
    return skill, body


def package_files(tree: list[dict], path: str, max_files: int) -> list[dict]:
    directory = str(PurePosixPath(path).parent)
    prefix = '' if directory == '.' else directory + '/'
    files = []
    for item in tree:
        if not item['path'].startswith(prefix):
            continue
        if item['type'] == 'commit':
            raise ValueError('Package submodules are not supported')
        if item['type'] != 'blob':
            continue
        relative = item['path'][len(prefix) :]
        if (
            item.get('mode') == '120000'
            or '\\' in relative
            or any(part in {'', '.', '..'} for part in relative.split('/'))
            or relative.startswith('/')
        ):
            raise ValueError('Unsafe package path or symlink')
        files.append({'path': relative, 'git_blob_sha1': item['sha']})
    if len(files) > max_files:
        raise ValueError('Package file manifest exceeds policy; refusing truncation')
    return sorted(files, key=lambda item: item['path'])


def collect(*, repositories: list[str] | None = None, destination: Path, policy_path: Path = POLICY_PATH) -> dict:
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        result = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True)
        token = result.stdout.strip() if result.returncode == 0 else None
    policy = load_policy(policy_path)
    checked = dt.datetime.now(dt.UTC).isoformat().replace('+00:00', 'Z')
    audit = destination.parent / (destination.stem + '.sources')
    if repositories is None:
        entries, errors = discover(policy, fetch=fetch, audit=audit)
    else:
        entries = [
            {
                'repository': repo.casefold(),
                'max_skills': 100,
                'roots': [''],
                'discovered_via': [f'https://github.com/{repo.casefold()}'],
            }
            for repo in dict.fromkeys(repositories)
        ]
        errors = []
    if len(entries) > policy['max_repositories']:
        raise ValueError('Repository discovery exceeds policy; refusing an incomplete refresh')
    tasks = []
    complete = []
    revisions = {}
    for entry in entries:
        repository = entry['repository']
        if not REPOSITORY_PATTERN.fullmatch(repository):
            raise ValueError('Invalid GitHub repository')
        try:
            info = json.loads(fetch(f'https://api.github.com/repos/{repository}', token=token))
            if info.get('private'):
                raise ValueError('Only public sources are permitted')
            canonical_repo = info.get('full_name', repository).casefold()
            if canonical_repo != repository:
                raise ValueError('Repository relocated; source policy review required')
            commit = json.loads(
                fetch(f'https://api.github.com/repos/{repository}/commits/{info["default_branch"]}', token=token)
            )['sha']
            tree_data = json.loads(
                fetch(
                    f'https://api.github.com/repos/{repository}/git/trees/{commit}?recursive=1',
                    token=token,
                    limit=8_000_000,
                )
            )
            if tree_data.get('truncated'):
                raise ValueError('The source tree is incomplete')
            tree = tree_data['tree']
            paths = [
                item['path']
                for item in tree
                if item['type'] == 'blob' and PurePosixPath(item['path']).name == 'SKILL.md'
            ]
            paths = [
                path
                for path in paths
                if path not in entry.get('excluded_manifests', [])
                and not any(part.casefold() in policy['excluded_components'] for part in path.split('/'))
                and any(path.startswith(root) for root in entry['roots'])
            ]
            # Nested SKILL.md files belong to their ancestor package's resources.
            paths = [
                path
                for path in paths
                if not any(other != path and path.startswith(str(PurePosixPath(other).parent) + '/') for other in paths)
            ]
            if len(paths) > entry['max_skills'] or len(tasks) + len(paths) > policy['max_skills']:
                raise OverflowError(f'Source exceeds collection limit; refusing an incomplete refresh: {repository}')
            repository_tasks = []
            for path in paths:
                files = package_files(tree, path, policy['max_files_per_skill'])
                repository_tasks.append(
                    (
                        repository,
                        commit,
                        path,
                        (info.get('license') or {}).get('spdx_id'),
                        files,
                        entry['discovered_via'],
                    )
                )
            tasks.extend(repository_tasks)
            revisions[repository] = commit
            complete.append(repository)
        except OverflowError as exc:
            raise ValueError(str(exc)) from exc
        except Exception as exc:
            errors.append({'source': repository, 'error': type(exc).__name__, 'detail': str(exc)[:240]})
    rows = []

    def one(task):
        repository, revision, path, license_id, files, discovered_via = task
        raw_path = audit / repository / revision / path
        raw = (
            raw_path.read_bytes()
            if raw_path.exists()
            else fetch(
                f'https://raw.githubusercontent.com/{repository}/{revision}/{urllib.parse.quote(path)}', limit=128_000
            )
        )
        manifest = next(item for item in files if item['path'] == 'SKILL.md')
        if hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() != manifest['git_blob_sha1']:
            raise ValueError('Manifest does not match its pinned Git blob')
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(raw)
        skill, body = parse_manifest(
            raw=raw, repository=repository, revision=revision, path=path, license_id=license_id, checked_at=checked
        )
        skill.source.files = [SourceFile.model_validate(item) for item in files]
        skill.source.discovered_via = discovered_via
        return VersionInput(
            version_id=version_id_for(skill, body),
            skill_id=skill.skill_id,
            name=skill.name,
            description=skill.summary,
            body=body,
            examples=skill.example_prompts,
            payload=skill,
        ).model_dump()

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(one, task): task for task in tasks}
        for future in concurrent.futures.as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append(
                    {
                        'source': futures[future][0],
                        'path': futures[future][2],
                        'error': type(exc).__name__,
                        'detail': str(exc)[:240],
                    }
                )
    rows.sort(key=lambda row: row['skill_id'])
    if len({row['skill_id'] for row in rows}) != len(rows):
        raise ValueError('Duplicate canonical package identity')
    failed_sources = {error['source'] for error in errors}
    complete = [repo for repo in complete if repo not in failed_sources]
    counts = Counter(row['payload']['category'] for row in rows)
    kinds = Counter()
    for row in rows:
        for kind in {
            'registry' if url.startswith('https://skills.sh/') else 'github'
            for url in row['payload']['source']['discovered_via']
        }:
            kinds[kind] += 1
    summary = {
        'skills': len(rows),
        'repositories': len(entries),
        'complete_repositories': complete if not errors else [],
        'errors': errors,
        'checked_at': checked,
        'source_revisions': revisions,
        'by_task_family': dict(sorted(counts.items())),
        'by_source_kind': dict(sorted(kinds.items())),
        'extractor_version': rows[0]['payload']['profile']['extractor_version'] if rows else None,
        'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(),
    }
    # A failed run is inspectable but can never replace the last complete snapshot.
    output = destination.with_name(destination.stem + '.failed.json') if errors else destination
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(rows, ensure_ascii=False).encode()
    summary['snapshot_sha256'] = hashlib.sha256(encoded).hexdigest()
    output.write_bytes(encoded)
    output.with_suffix('.summary.json').write_text(json.dumps(summary, indent=2))
    return {**summary, 'snapshot': str(output)}


def validated_snapshot(snapshot: Path) -> PublishRequest:
    summary = json.loads(snapshot.with_suffix('.summary.json').read_text())
    if summary['errors'] or not summary['complete_repositories']:
        raise ValueError('A complete source collection is required for refresh.')
    raw = snapshot.read_bytes()
    if hashlib.sha256(raw).hexdigest() != summary.get('snapshot_sha256'):
        raise ValueError('Snapshot and completion summary must come from the same collection.')
    request = PublishRequest(rows=json.loads(raw), complete_repositories=summary['complete_repositories'])
    if len(request.rows) != summary['skills'] or any(
        row.payload.source.revision != summary['source_revisions'].get(row.payload.source.repository)
        for row in request.rows
    ):
        raise ValueError('Snapshot content must match the completed source collection.')
    return request


def publish(*, target: str, snapshot: Path) -> dict:
    import pixeltable as pxt

    request = validated_snapshot(snapshot)
    separator = '/' if target.startswith('pxt://') else '.'
    result = publish_rows(
        sources=pxt.get_table(target + separator + 'sources'),
        versions=pxt.get_table(target + separator + 'skill_versions'),
        rows=request.rows,
        complete_repositories=request.complete_repositories,
    )
    return {**result, 'target': target}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['collect', 'publish', 'refresh-http'])
    parser.add_argument('--snapshot', type=Path, default=Path('.audit/catalog-source.json'))
    parser.add_argument('--target', default='agentforge_dev')
    parser.add_argument('--repo', action='append')
    parser.add_argument('--policy', type=Path, default=POLICY_PATH)
    args = parser.parse_args()
    if args.action == 'collect':
        result = collect(repositories=args.repo, destination=args.snapshot, policy_path=args.policy)
        if result['errors']:
            print(json.dumps(result))
            raise SystemExit('Collection incomplete; publication refused.')
    elif args.action == 'publish':
        result = publish(target=args.target, snapshot=args.snapshot)
    else:
        request = validated_snapshot(args.snapshot)
        req = urllib.request.Request(
            os.environ['AGENTFORGE_REFRESH_URL'],
            data=request.model_dump_json().encode(),
            headers={
                'Content-Type': 'application/json',
                'X-api-key': os.environ['AGENTFORGE_REFRESH_SERVICE_KEY'],
                'X-AgentForge-Index-Key': os.environ['AGENTFORGE_INDEX_TOKEN'],
            },
        )
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.load(response)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
