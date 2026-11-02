import os

import pytest


@pytest.mark.skipif(not os.environ.get('AGENTFORGE_TEST_TARGET'), reason='A real isolated catalog is required')
def test_published_catalog_has_one_row_per_pointer():
    import app
    from agentforge_backend.publish import version_id_for

    app.TableModel.bind_all(os.environ['AGENTFORGE_TEST_TARGET'])
    pointers = app.published_versions()
    rows = app.current_rows(pointers)
    assert pointers
    assert len(rows) == len(set(pointers))
    assert len(rows) == len({r.skill_id for r in rows})
    versions = app.Versions.table
    stored = (
        versions.where(versions.version_id.isin(pointers))
        .select(versions.version_id, versions.payload, versions.body)
        .collect()
    )
    assert {version_id_for(app.Skill.model_validate(r['payload']), r['body']) for r in stored} == set(pointers)
    checked = {r['skill_id']: r['checked_at'] for r in app.Sources.table.collect()}
    assert all(row.source.checked_at == checked[row.skill_id] for row in rows)


@pytest.mark.skipif(not os.environ.get('AGENTFORGE_TEST_TARGET'), reason='A real isolated catalog is required')
def test_native_query_routes_read_the_published_tables():
    import app
    from fastapi.testclient import TestClient

    app.TableModel.bind_all(os.environ['AGENTFORGE_TEST_TARGET'])
    app.queries.bind(os.environ['AGENTFORGE_TEST_TARGET'])
    client = TestClient(app.application)
    response = client.get('/queries/sources')
    assert response.status_code == 200, response.text
    sources = response.json()['rows']
    assert {row['published_version'] for row in sources} == set(app.published_versions())
    selected = sources[:3]
    version_ids = [row['published_version'] for row in selected]
    skill_ids = [row['skill_id'] for row in selected]
    response = client.post('/queries/versions', json={'version_ids': version_ids})
    assert response.status_code == 200, response.text
    assert {row['version_id'] for row in response.json()['rows']} == set(version_ids)
    assert client.post('/queries/versions', json={'version_ids': []}).json() == {'rows': []}
    assert client.post('/queries/versions', json={'version_ids': {'unexpected': 'shape'}}).status_code == 422

    payload = {'query': 'Review authentication code', 'version_ids': version_ids, 'skill_ids': skill_ids[:1]}
    response = client.post('/queries/semantic', json=payload)
    assert response.status_code == 200, response.text
    candidates = response.json()['rows']
    assert {row['skill_id'] for row in candidates} == set(skill_ids[:1])
    expected = list(app.semantic_candidates_query(app.Versions.table, **payload).collect())
    assert candidates == expected
    assert client.post('/queries/semantic', json={**payload, 'skill_ids': []}).json() == {'rows': []}
    assert client.post('/queries/semantic', json={**payload, 'version_ids': []}).json() == {'rows': []}
