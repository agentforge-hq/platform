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
