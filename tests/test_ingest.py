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
