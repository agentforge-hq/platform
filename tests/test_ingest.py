import json
import subprocess

import pytest

from ingest import catalog


def test_source_overflow_does_not_publish_an_incomplete_snapshot(monkeypatch, tmp_path):
    snapshot = tmp_path / 'catalog.json'
    snapshot.write_text('previous complete snapshot')
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, '', ''))

    def fetch(url, **kwargs):
        if '/git/trees/' in url:
            data = {'tree': [{'type': 'blob', 'path': f'skills/skill-{i}/SKILL.md'} for i in range(101)]}
        elif '/commits/' in url:
            data = {'sha': 'a' * 40}
        else:
            data = {'default_branch': 'main', 'license': {'spdx_id': 'MIT'}}
        return json.dumps(data).encode()

    monkeypatch.setattr(catalog, 'fetch', fetch)
    with pytest.raises(ValueError, match='refusing an incomplete refresh'):
        catalog.collect(repositories=['example/skills'], destination=snapshot)
    assert snapshot.read_text() == 'previous complete snapshot'
    assert not snapshot.with_suffix('.summary.json').exists()


def mocked_source(
    monkeypatch,
    *,
    raw=b'---\nname: sample\ndescription: Use when reviewing release notes.\n---\n## Outputs\n- A concise release review.\n',
    extra_files=None,
    truncated=False,
):
    import hashlib

    digest = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    tree = [{'type': 'blob', 'mode': '100644', 'path': 'skills/sample/SKILL.md', 'sha': digest}] + (extra_files or [])

    def fetch(url, **kwargs):
        if 'raw.githubusercontent.com' in url:
            return raw
        if '/git/trees/' in url:
            data = {'tree': tree, 'truncated': truncated}
        elif '/commits/' in url:
            data = {'sha': 'a' * 40}
        else:
            data = {'default_branch': 'main', 'license': {'spdx_id': 'MIT'}}
        return json.dumps(data).encode()

    monkeypatch.setattr(catalog, 'fetch', fetch)
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, '', ''))
    return tree


def test_collection_pins_supporting_files_and_validates_snapshot(monkeypatch, tmp_path):
    mocked_source(
        monkeypatch,
        extra_files=[{'type': 'blob', 'mode': '100644', 'path': 'skills/sample/scripts/review.py', 'sha': 'b' * 40}],
    )
    snapshot = tmp_path / 'catalog.json'
    result = catalog.collect(repositories=['example/skills'], destination=snapshot)
    assert result['skills'] == 1 and not result['errors']
    request = catalog.validated_snapshot(snapshot)
    skill = request.rows[0].payload
    assert [item.path for item in skill.source.files] == ['SKILL.md', 'scripts/review.py']
    assert skill.source.discovered_via == ['https://github.com/example/skills']
    assert request.rows[0].version_id == catalog.version_id_for(skill, request.rows[0].body)
    assert (tmp_path / 'catalog.sources/example/skills' / ('a' * 40) / 'skills/sample/SKILL.md').exists()


@pytest.mark.parametrize('failure', ['invalid_manifest', 'truncated_tree', 'symlink', 'too_many_files'])
def test_failed_source_preserves_complete_snapshot_and_cannot_refresh(monkeypatch, tmp_path, failure):
    extras = []
    if failure == 'symlink':
        extras = [{'type': 'blob', 'mode': '120000', 'path': 'skills/sample/script', 'sha': 'b' * 40}]
    if failure == 'too_many_files':
        extras = [
            {'type': 'blob', 'mode': '100644', 'path': f'skills/sample/file-{i}', 'sha': 'b' * 40} for i in range(201)
        ]
    kwargs = {'extra_files': extras, 'truncated': failure == 'truncated_tree'}
    if failure == 'invalid_manifest':
        kwargs['raw'] = b'This is not a manifest'
    mocked_source(monkeypatch, **kwargs)
    snapshot = tmp_path / 'catalog.json'
    snapshot.write_text('last complete snapshot')
    result = catalog.collect(repositories=['example/skills'], destination=snapshot)
    assert result['errors'] and result['complete_repositories'] == []
    assert snapshot.read_text() == 'last complete snapshot'
    with pytest.raises(ValueError, match='complete source collection'):
        catalog.validated_snapshot(tmp_path / 'catalog.failed.json')


def test_registry_discovery_deduplicates_upstream_and_retains_both_origins(tmp_path):
    from ingest.discovery import discover

    policy = {
        'direct': [{'repository': 'Example/Skills', 'roots': ['skills/'], 'max_skills': 100}],
        'registry': {
            'queries': [{'query': 'writing'}, {'query': 'review'}],
            'result_limit': 20,
            'allowed_repositories': [{'repository': 'example/skills', 'roots': ['skills/'], 'max_skills': 100}],
        },
        'max_repositories': 3,
    }

    def fetch(url, **kwargs):
        return json.dumps(
            {
                'skills': [
                    {'source': 'example/skills', 'name': 'sample', 'id': 'example/skills/sample'},
                    {'source': 'unregistered/copied', 'name': 'sample'},
                ]
            }
        ).encode()

    entries, errors = discover(policy, fetch=fetch, audit=tmp_path)
    assert errors == [] and len(entries) == 1
    assert entries[0]['repository'] == 'example/skills'
    assert len(entries[0]['discovered_via']) == 3
    assert entries[0]['roots'] == ['skills/']


def test_registry_failure_is_not_evidence_of_source_withdrawal(tmp_path):
    from ingest.discovery import discover, load_policy

    policy = load_policy()

    def fetch(url, **kwargs):
        raise TimeoutError('temporary')

    entries, errors = discover(policy, fetch=fetch, audit=tmp_path)
    assert entries and errors
    assert any(error['error'] == 'RegistrySourceNotResolved' for error in errors)


@pytest.mark.parametrize(
    'path,kind,mode',
    [
        ('skills/sample/../escape', 'blob', '100644'),
        ('skills/sample/submodule', 'commit', '160000'),
        ('skills/sample/unsafe', 'blob', '120000'),
    ],
)
def test_package_manifest_rejects_unsafe_or_unverifiable_resources(path, kind, mode):
    with pytest.raises(ValueError):
        catalog.package_files(
            [{'path': path, 'type': kind, 'mode': mode, 'sha': 'b' * 40}], 'skills/sample/SKILL.md', 200
        )


def test_snapshot_cannot_reuse_a_completion_summary_after_content_changes(monkeypatch, tmp_path):
    mocked_source(monkeypatch)
    snapshot = tmp_path / 'catalog.json'
    catalog.collect(repositories=['example/skills'], destination=snapshot)
    snapshot.write_text('[]')
    with pytest.raises(ValueError, match='same collection'):
        catalog.validated_snapshot(snapshot)
